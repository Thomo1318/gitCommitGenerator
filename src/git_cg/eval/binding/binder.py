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

import base64
import contextlib
import hashlib
import json
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from git_cg.eval.binding import paths
from git_cg.eval.binding.lock import acquire_bind_lock
from git_cg.eval.binding.profiles import capture_enabled
from git_cg.eval.corpus.canonical import message_sha256
from git_cg.eval.enums import ArtifactClass, ProvenanceLabel, RedactionProfile
from git_cg.eval.evidence_scrub import mask_secrets_in_text, project_secret_safe
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
    """Return the full 64-hex SHA-256 of the *original* message bytes.

    Bytes-aware counterpart to :func:`git_cg.eval.corpus.canonical.message_sha256`
    (N19.4): when given ``bytes`` it hashes them directly so the exact accepted
    bytes remain the hash authority; when given ``str`` it matches the corpus
    helper (UTF-8 encode) to preserve Family A text compatibility.
    """
    if isinstance(data, bytes):
        return hashlib.sha256(data).hexdigest()
    return message_sha256(data)


def _project_final_text(data: bytes | str) -> tuple[str, dict[str, Any]]:
    """Project exact bytes to the schema-valid ``final_message`` text field.

    Returns ``(text, meta_extra)``. Valid UTF-8 decodes cleanly; invalid UTF-8
    decodes with ``errors="replace"`` and records the encoding + original byte
    length under ``meta`` (N20.3). When bytes are not valid UTF-8, also records
    ancillary ``meta.final_message_b64`` for lossless round-trip of the original
    accepted bytes — never a scored primary field.
    Never raises on decode failure.
    """
    if isinstance(data, str):
        return data, {}
    try:
        return data.decode("utf-8"), {}
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace"), {
            "final_message_encoding": "utf-8-replace",
            "final_message_byte_length": len(data),
            "final_message_b64": base64.b64encode(data).decode("ascii"),
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


#: Acceptpath reuse-scan cache schema version (rebuildable; never sole authority).
_INDEX_VERSION = 1

#: Cache key field separator for scoped reuse triples.
_INDEX_KEY_SEP = "::"


def _index_entry_key(key: tuple[str, str, str]) -> str:
    """Serialize a scoped reuse triple into a stable cache key string."""
    repo_root, token, final_sha = key
    return f"{repo_root}{_INDEX_KEY_SEP}{token}{_INDEX_KEY_SEP}{final_sha}"


def _load_index(index_path: Path) -> dict[str, str] | None:
    """Load the acceptpath reuse-scan cache, or ``None`` when unusable.

    Returns ``None`` for missing, corrupt, wrong-version, or schema-invalid
    indexes. Cache absence must never alter binding behaviour.
    """
    try:
        if not index_path.is_file():
            return None
        raw = index_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except OSError, json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError:
        return None
    if not isinstance(data, dict):
        return None
    if data.get("version") != _INDEX_VERSION:
        return None
    entries = data.get("entries")
    if not isinstance(entries, dict):
        return None
    out: dict[str, str] = {}
    for key, value in entries.items():
        if isinstance(key, str) and isinstance(value, str) and key and value.strip():
            out[key] = value
    return out


def _write_index(index_path: Path, entries: dict[str, str]) -> None:
    """Best-effort atomic write of the reuse-scan cache. Never raises."""
    payload = {"version": _INDEX_VERSION, "entries": dict(entries)}
    with contextlib.suppress(OSError, paths.LayerAPathError, TypeError, ValueError):
        paths.atomic_write_json(index_path, payload)


def _cache_lookup_session(index_path: Path, key: tuple[str, str, str]) -> str | None:
    """Return cached ``session_thread_id`` for ``key``, or ``None`` on miss."""
    entries = _load_index(index_path)
    if not entries:
        return None
    value = entries.get(_index_entry_key(key))
    if isinstance(value, str) and value.strip():
        return value
    return None


def _cache_write_through(index_path: Path, key: tuple[str, str, str], session_id: str) -> None:
    """Merge ``session_id`` into the cache for ``key`` (best-effort)."""
    if not session_id or not session_id.strip():
        return
    entries = _load_index(index_path) or {}
    entries[_index_entry_key(key)] = session_id
    _write_index(index_path, entries)


def _load_bundle_for_session(bundles_dir: Path, session_id: str) -> dict[str, Any] | None:
    """Load an authoritative bundle by session id when present and well-formed."""
    if not session_id or not session_id.strip():
        return None
    path = bundles_dir / f"{session_id}.json"
    try:
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError, UnicodeDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _bundle_matches_key(data: dict[str, Any], key: tuple[str, str, str]) -> bool:
    """True when authoritative bundle ``data`` matches scoped reuse ``key``."""
    repo_root, token, final_sha = key
    if data.get("final_message_sha256") != final_sha:
        return False
    meta = data.get("meta")
    accept_event = meta.get("accept_event") if isinstance(meta, dict) else None
    if not isinstance(accept_event, dict):
        return False
    if accept_event.get("token") != token:
        return False
    stored_root = accept_event.get("repo_root")
    return (not stored_root) or stored_root == repo_root


def _reuse_key(repo_root: Path, accept_event_token: str | None, final_sha: str) -> tuple[str, str, str] | None:
    """Return the scoped reuse key, or ``None`` when no reliable token (N19.2)."""
    if not accept_event_token or not accept_event_token.strip():
        return None
    return (str(Path(repo_root).resolve()), accept_event_token, final_sha)


def _scan_reuse_key(bundles_dir: Path, key: tuple[str, str, str]) -> dict[str, Any] | None:
    """Find an existing authoritative acceptpath bundle matching ``key``.

    Consults the optional rebuildable ``index.json`` cache first. On cache hit,
    still verifies the authoritative bundle file before reuse. On miss,
    corrupt, or stale cache, falls through to a linear directory scan of bundle
    JSON files (index caches are never sole authority; N19.2/N19.3). Linear-scan
    hits write through to the cache best-effort.
    """
    if not bundles_dir.is_dir():
        return None

    index_path = bundles_dir / "index.json"
    cached_session = _cache_lookup_session(index_path, key)
    if cached_session is not None:
        cached_bundle = _load_bundle_for_session(bundles_dir, cached_session)
        if cached_bundle is not None and _bundle_matches_key(cached_bundle, key):
            return cached_bundle
        # Stale/wrong cache entry — ignore and fall through to linear scan.

    for path in sorted(bundles_dir.glob("*.json")):
        if path.name == "index.json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            continue  # corrupt file is not authority; skip
        if not isinstance(data, dict):
            continue
        if not _bundle_matches_key(data, key):
            continue
        # Write-through after authoritative scan hit (best-effort).
        session_id = data.get("session_thread_id")
        if isinstance(session_id, str) and session_id.strip():
            _cache_write_through(index_path, key, session_id)
        return data
    return None


def bind_final_accept(
    inp: BindInput,
    *,
    repo_root: Path | None = None,
    write: bool = True,
) -> BindResult:
    """Bind exact final bytes into ``final_accept`` evidence (D4).

    Never raises for product-accept reasons. Behaviour:

    * Capture disabled ⇒ ``bound=False, unbound_reason="capture_disabled"``,
      zero writes (D1/N19.5).
    * Empty/whitespace final message ⇒ ``bound=False,
      unbound_reason="final_message_absent"``.
    * Schema-invalid / unresolved-repo outcomes return unbound results with
      reasons (never product-blocking).
    * Same ``(repo_root, accept_event_token, final_message_sha256)`` may reuse
      an existing bundle (N19.2); persistence failures are reported on the
      result without blocking accept.
    * Otherwise build a schema-valid ``ape_bundle_v1`` with
      ``artifact_class=final_accept``, ``bound=true``, stored
      ``final_message_sha256`` over the original bytes, and (when ``write``)
      atomically persist under ``.eval/bundles/acceptpath/``.
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
    # Short-lived lock around reuse-scan-plus-write; lock failure falls back to
    # unlocked atomic-replace and never blocks product accept.
    session_id = inp.session_thread_id
    case_id: str | None = None
    key = _reuse_key(root, inp.accept_event_token, final_sha) if root is not None else None
    bundles_dir: Path | None = paths.acceptpath_bundles_dir(root) if root is not None else None
    bind_lock = acquire_bind_lock(bundles_dir) if (write and bundles_dir is not None) else None
    try:
        if key is not None and bundles_dir is not None:
            existing = _scan_reuse_key(bundles_dir, key)
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
            # Project secret-safe so evidence surfaces never persist raw secrets.
            safe_meta = project_secret_safe(dict(inp.meta))
            if isinstance(safe_meta, dict):
                for meta_key, value in safe_meta.items():
                    meta.setdefault(meta_key, value)
        if inp.generated_message is not None and str(inp.generated_message).strip():
            # Draft evidence only — redact secret shapes; never the scored final.
            masked_draft = mask_secrets_in_text(str(inp.generated_message))
            if masked_draft is not None and str(masked_draft).strip():
                meta["generated_message"] = masked_draft
        if inp.score_card:
            # Score card is evidence under meta; project secret-safe.
            safe_card = project_secret_safe(dict(inp.score_card))
            if isinstance(safe_card, dict):
                meta["score_card"] = safe_card
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
        if write and root is not None and bundles_dir is not None:
            try:
                out = bundles_dir / f"{session_id}.json"
                paths.atomic_write_json(out, bundle)
                paths_written = (out.relative_to(root).as_posix(),)
                # Best-effort reuse-scan cache write-through after successful bind.
                if key is not None:
                    _cache_write_through(bundles_dir / "index.json", key, session_id)
            except (OSError, paths.LayerAPathError) as exc:
                # Persistence failure must not block product accept; report honestly.
                errors = (f"bind_write_error: {exc}",)

        return BindResult(
            bound=True,
            bundle=bundle,
            paths_written=paths_written,
            errors=errors,
        )
    finally:
        if bind_lock is not None:
            bind_lock.release()


def bind_unbound(
    *,
    reason: str,
    final_message: str | None = None,
    artifact_class: str = ArtifactClass.OPIK_UNBOUND.value,
    **kwargs: Any,
) -> BindResult:
    """Explicit unbound helper (N6). ``artifact_class`` must NOT be final_accept.

    Fails closed when the reason is blank or the class is ``final_accept``
    (``EVAL_FAKE_BOUND``). Does not write by default; the returned bundle (when
    constructed) is honest unbound evidence for offline scoring.
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
