"""S3 accept-path final-bytes binder (Issue #231, S3-contract-v1.4 / D4, N2, N6, N19).

Lane A local source of truth: bind the **exact accepted final message bytes**
(``COMMIT_EDITMSG`` content) into a schema-valid ``ape_bundle_v1`` with
``artifact_class=final_accept`` on the honest happy path, with explicit
bound/unbound labeling and scoped idempotent persistence under the repo-local
``.eval/`` tree.

Contract locks honoured here:

* **N2 / D4** — primary scored artifact is the exact final bytes; the bundle
  persists ``final_message`` (text projection) + ``final_message_sha256``
  (full 64-hex hash of the *original bytes*). Cards live under ``meta``
  (``ape_bundle_v1.additionalProperties=false`` forbids top-level cards).
* **N6** — honest bound/unbound: never fake ``bound=true``; unbound requires a
  non-empty reason and a non-``final_accept`` class (``EVAL_FAKE_BOUND``).
* **N19.2 / N20.1** — scoped identity: ``reuse_key = (repo_root,
  accept_event_token, final_message_sha256)``. Same scoped event + same bytes ⇒
  reuse; new event + same bytes ⇒ new session; no token ⇒ fail closed to new
  session; same event + changed bytes ⇒ new bundle (never silently overwrite a
  closed twin's identity).
* **N19.3** — atomic persist (temp + ``os.replace``), restrictive modes,
  containment under the resolved ``.eval/`` tree, bundle files are authority.
* **N19.4 / N20.3** — bytes-aware: ``final_message: bytes | str``; hash the
  original bytes; invalid UTF-8 projects with ``utf-8-replace`` and records
  ``meta.final_message_encoding`` / ``meta.final_message_byte_length``.
* **D9 / N18** — ``session_thread_id`` is always a freshly minted (or
  scoped-reuse) ``sess_`` id; ``GenerationTelemetry.thread_id`` (``repo-…``) is
  correlation-only and never becomes the session id.
* **D1 / N19.5** — capture gated by :func:`profiles.capture_enabled`; when off,
  return ``bound=False, unbound_reason="capture_disabled"`` with zero writes.

No network. No Opik import. No product-accept blocking: :func:`bind_final_accept`
never raises for product-accept reasons — it reports outcomes via
:class:`BindResult`.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from git_cg.eval.binding import paths
from git_cg.eval.binding.profiles import capture_enabled
from git_cg.eval.corpus.canonical import message_sha256
from git_cg.eval.enums import ArtifactClass, ProvenanceLabel, RedactionProfile
from git_cg.eval.schema_pack import SchemaPackError, validate_instance

__all__ = [
    "BindInput",
    "BindResult",
    "bind_final_accept",
    "bind_unbound",
    "message_sha256_bytes",
]

#: Redaction profile applied to local twins when none is supplied (D6).
_DEFAULT_REDACTION = RedactionProfile.DEFAULT_SCRUB.value

#: Producer tag recorded under ``meta.producer`` (D4).
_PRODUCER = "acceptpath_binder"

#: Unbound artifact classes permitted when ``bound=false`` (never final_accept).
_UNBOUND_CLASSES = frozenset(
    {
        ArtifactClass.OPIK_UNBOUND.value,
        ArtifactClass.FIXTURE.value,
        ArtifactClass.LIVE_REGEN.value,
    }
)


def message_sha256_bytes(data: bytes | str) -> str:
    """
    Hash a message using its original bytes where available.

    Parameters:
        data (bytes | str): Message bytes or text to hash.

    Returns:
        str: The full 64-character hexadecimal SHA-256 digest.
    """
    if isinstance(data, bytes):
        return hashlib.sha256(data).hexdigest()
    return message_sha256(data)


def _project_final_text(data: bytes | str) -> tuple[str, dict[str, Any]]:
    """Project exact bytes to the schema-valid ``final_message`` text field.

    Returns ``(text, meta_extra)``. Valid UTF-8 decodes cleanly; invalid UTF-8
    decodes with ``errors="replace"`` and records the encoding + original byte
    length under ``meta`` (N20.3). Never raises on decode failure.
    """
    if isinstance(data, str):
        return data, {}
    try:
        return data.decode("utf-8"), {}
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace"), {
            "final_message_encoding": "utf-8-replace",
            "final_message_byte_length": len(data),
        }


@dataclass(frozen=True, slots=True)
class BindInput:
    """Inputs for an accept-path bind (D4). Frozen + slotted (N19.7 KEEP).

    Attributes:
        final_message: Exact accepted final bytes (preferred) or text.
        generated_message: Best-effort redacted/pre-BetterLeaks draft evidence —
            **not** guaranteed raw model output (N19.5 / NTH-U5).
        score_card: Product deterministic score card dict when available.
        trace_id: Generation trace id (correlation only).
        thread_id: ``GenerationTelemetry.thread_id`` — repo-scoped Opik
            correlation thread (``repo-…``); **never** the session id (D9).
        session_thread_id: Pre-minted ``sess_`` id to reuse, else minted.
        accept_event_token: Immutable accept-event token for scoped reuse
            (N19.2/N20.1); ``None`` ⇒ fail closed to a new session.
        edit_provenance: Product ``classify_edit`` value when known.
        meta: Additive non-authoritative fields only.
        redaction_profile: Override; defaults to ``default_scrub`` (D6).
    """

    final_message: bytes | str
    generated_message: str | None = None
    score_card: dict[str, Any] | None = None
    trace_id: str | None = None
    thread_id: str | None = None
    session_thread_id: str | None = None
    accept_event_token: str | None = None
    edit_provenance: str | None = None
    meta: dict[str, Any] | None = None
    redaction_profile: str | None = None


@dataclass(frozen=True, slots=True)
class BindResult:
    """Outcome of a bind attempt. Never raises for product-accept reasons."""

    bound: bool
    bundle: dict[str, Any] | None = None
    session_thread: dict[str, Any] | None = None
    trajectory: dict[str, Any] | None = None
    unbound_reason: str | None = None
    paths_written: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


def _mint_session_id() -> str:
    """Mint a fresh ``sess_`` capture-episode id (D9)."""
    return f"sess_{secrets.token_hex(16)}"


def _reuse_key(repo_root: Path, accept_event_token: str | None, final_sha: str) -> tuple[str, str, str] | None:
    """Return the scoped reuse key, or ``None`` when no reliable token (N19.2)."""
    if not accept_event_token or not accept_event_token.strip():
        return None
    return (str(Path(repo_root).resolve()), accept_event_token, final_sha)


def _scan_reuse_key(bundles_dir: Path, key: tuple[str, str, str]) -> dict[str, Any] | None:
    """Find an existing authoritative acceptpath bundle matching ``key``.

    Scans authoritative bundle JSON files (index caches are ignored — bundle
    files are the sole authority, N19.2/N19.3). Matches on the scoped reuse
    triple persisted under ``meta.accept_event`` + top-level hash field.
    """
    if not bundles_dir.is_dir():
        return None
    repo_root, token, final_sha = key
    for path in sorted(bundles_dir.glob("*.json")):
        if path.name == "index.json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            continue  # corrupt file is not authority; skip
        if not isinstance(data, dict):
            continue
        if data.get("final_message_sha256") != final_sha:
            continue
        meta = data.get("meta")
        accept_event = meta.get("accept_event") if isinstance(meta, dict) else None
        if not isinstance(accept_event, dict):
            continue
        if accept_event.get("token") != token:
            continue
        if accept_event.get("repo_root") and accept_event.get("repo_root") != repo_root:
            continue
        return data
    return None


def bind_final_accept(
    inp: BindInput,
    *,
    repo_root: Path | None = None,
    write: bool = True,
) -> BindResult:
    """
    Bind the exact final message to schema-valid ``final_accept`` evidence.

    Capture-disabled, absent-message, unresolved-repository, and schema-invalid
    outcomes are returned as unbound results. Existing evidence may be reused when
    the repository, accept-event token, and message hash match. Persistence
    failures are reported in the result without blocking product acceptance.

    Parameters:
        inp (BindInput): Final message and optional binding metadata.
        repo_root (Path | None): Repository root used for persistence and reuse
            scoping.
        write (bool): Whether to persist the evidence bundle.

    Returns:
        BindResult: Binding status, bundle data, persistence paths, and any errors.
    """
    if not capture_enabled():
        return BindResult(bound=False, unbound_reason="capture_disabled")

    final_bytes = inp.final_message
    text, encoding_meta = _project_final_text(final_bytes)
    if not text.strip():
        return BindResult(bound=False, unbound_reason="final_message_absent")

    final_sha = message_sha256_bytes(final_bytes)

    # Resolve repo root only when we may write.
    root: Path | None = None
    if write:
        try:
            root = Path(repo_root).resolve() if repo_root is not None else paths.resolve_repo_root()
        except paths.RepoRootUnresolvedError:
            return BindResult(bound=False, unbound_reason="repo_root_unresolved")

    # Scoped idempotent reuse (N19.2): same event + same bytes ⇒ reuse identity.
    session_id = inp.session_thread_id
    case_id: str | None = None
    key = _reuse_key(root, inp.accept_event_token, final_sha) if root is not None else None
    if key is not None:
        existing = _scan_reuse_key(paths.acceptpath_bundles_dir(root), key)
        if existing is not None:
            existing_session = existing.get("session_thread_id")
            existing_case = existing.get("case_id")
            if isinstance(existing_session, str) and existing_session.strip():
                session_id = existing_session
            if isinstance(existing_case, str) and existing_case.strip():
                case_id = existing_case

    if session_id is None or not session_id.strip():
        session_id = _mint_session_id()
    if case_id is None:
        case_id = f"acceptpath:{session_id}"

    redaction = inp.redaction_profile or _DEFAULT_REDACTION

    meta: dict[str, Any] = {"producer": _PRODUCER}
    meta.update(encoding_meta)
    if inp.meta:
        # Additive non-authoritative fields only; never override binder authority.
        for key, value in inp.meta.items():
            meta.setdefault(key, value)
    if inp.score_card:
        meta["score_card"] = dict(inp.score_card)
    binding_meta: dict[str, Any] = {"state": "bound"}
    if inp.trace_id:
        binding_meta["trace_id"] = inp.trace_id
    if inp.thread_id:
        binding_meta["thread_id"] = inp.thread_id  # correlation only (D9)
    meta["binding"] = binding_meta
    if inp.accept_event_token:
        meta["accept_event"] = {
            "token": inp.accept_event_token,
            "repo_root": str(root) if root is not None else None,
        }

    bundle: dict[str, Any] = {
        "schema_version": "ape_bundle_v1",
        "case_id": case_id,
        "artifact_class": ArtifactClass.FINAL_ACCEPT.value,
        "bound": True,
        "final_message": text,
        "final_message_sha256": final_sha,
        "session_thread_id": session_id,
        "redaction_profile": redaction,
        "provenance_label": ProvenanceLabel.FINAL_ACCEPT.value,
        "meta": meta,
    }

    # Fail closed: the bundle we claim must validate against the frozen schema.
    # Schema drift / rejected caller meta must not escape the non-blocking path.
    try:
        validate_instance("ape_bundle_v1", bundle)
    except SchemaPackError as exc:
        return BindResult(bound=False, unbound_reason="schema_invalid", errors=(str(exc),))

    paths_written: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    if write and root is not None:
        try:
            out = paths.acceptpath_bundles_dir(root) / f"{session_id}.json"
            paths.atomic_write_json(out, bundle)
            paths_written = (out.relative_to(root).as_posix(),)
        except (OSError, paths.LayerAPathError) as exc:
            # Persistence failure must not block product accept; report honestly.
            errors = (f"bind_write_error: {exc}",)

    return BindResult(
        bound=True,
        bundle=bundle,
        paths_written=paths_written,
        errors=errors,
    )


def bind_unbound(
    *,
    reason: str,
    final_message: str | None = None,
    artifact_class: str = ArtifactClass.OPIK_UNBOUND.value,
    **kwargs: Any,
) -> BindResult:
    """
    Constructs validated evidence for an outcome that is explicitly unbound.

    Parameters:
        reason (str): Explanation for why the evidence is unbound.
        final_message (str | None): Optional final message to include and hash.
        artifact_class (str): Allowed unbound evidence classification.
        **kwargs (Any): Optional bundle metadata, including ``case_id``.

    Returns:
        BindResult: An unbound result containing the validated evidence bundle.

    Raises:
        ValueError: If the reason is blank, the artifact class is unsupported, or
            the artifact class claims ``final_accept``.
    """
    if not reason or not reason.strip():
        raise ValueError("unbound bind requires a non-empty reason (EVAL_FAKE_BOUND)")
    if artifact_class == ArtifactClass.FINAL_ACCEPT.value:
        raise ValueError("unbound bind cannot claim final_accept (EVAL_FAKE_BOUND)")
    if artifact_class not in _UNBOUND_CLASSES:
        raise ValueError(f"unbound artifact_class must be one of {sorted(_UNBOUND_CLASSES)}")

    bundle: dict[str, Any] = {
        "schema_version": "ape_bundle_v1",
        "case_id": kwargs.get("case_id") or "acceptpath:unbound",
        "artifact_class": artifact_class,
        "bound": False,
        "unbound_reason": reason,
    }
    if final_message is not None:
        bundle["final_message"] = final_message
        bundle["final_message_sha256"] = message_sha256(final_message)
    validate_instance("ape_bundle_v1", bundle)
    return BindResult(bound=False, bundle=bundle, unbound_reason=reason)
