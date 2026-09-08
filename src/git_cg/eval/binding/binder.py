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
* **Hash source** — :func:`bind_final_accept` hashes original bytes via
  :func:`message_sha256_bytes`. :func:`bind_unbound` hashes supplied
  projected text via :func:`git_cg.eval.corpus.canonical.message_sha256`.
  Accept identity is original bytes; unbound identity is projected text.
* **Draft persistence** — ``meta.generated_message`` is stored only when
  :func:`mask_secrets_in_text` returns a non-empty scrubbed draft. Empty or
  fully-scrubbed drafts are omitted. Draft text is evidence only, never the
  scored artifact.
* **Validation asymmetry** — :func:`bind_final_accept` never raises for
  product-accept reasons; it reports outcomes on :class:`BindResult`.
  :func:`bind_unbound` raises ``ValueError`` for a blank reason, a
  ``final_accept`` class, or an unknown class (``EVAL_FAKE_BOUND``).
* **D9 / N18** — ``session_thread_id`` is always a freshly minted (or
  scoped-reuse) ``sess_`` id; ``GenerationTelemetry.thread_id`` (``repo-…``) is
  correlation-only and never becomes the session id.
* **D1 / N19.5** — capture gated by :func:`profiles.capture_enabled`; when off,
  return ``bound=False, unbound_reason="capture_disabled"`` with zero writes.
* **Cache / authority** — ``index.json`` is rebuildable and never sole
  authority. Schema version is injective v2 (canonical JSON-array keys);
  wrong-version, corrupt, oversized, or malformed indexes are ignored and
  rebuilt. No dual-read.
* **Lock-gated cache writes** — index write-through runs only while a
  bind lock is held. Lock failure still persists the authoritative
  bundle best-effort and never blocks accept.
* **Miss-scan** — skip ``index.json``, symlinks, and non-regular files.
  Hard links remain regular files. Listing still walks every ``*.json``.
* **Session-ID grammar** — cached ids must match ``sess_`` + 32 lowercase
  hex before path construction; violations are silent misses.
* **Privacy boundary** — evidence surfaces are always projected secret-safe.
  Final accepted bytes are never scrubbed. ``meta.final_message_b64`` stays
  local-bundle-only.
* **Bounded miss-scan** — cache miss selects at most K recent regular
  ``*.json`` bundles (default 512; ``GIT_CG_EVAL_ACCEPTPATH_SCAN_WINDOW``).
  Sort is mtime descending, filename ascending. ``index.json``,
  symlinks, and non-regular files are skipped. Listing still walks
  every ``*.json``; only parse cost is capped at K. A recency index or
  bounded directory cursor is a separate follow-up.
  ``GIT_CG_EVAL_ACCEPTPATH_FULL_SCAN=1`` removes the parse bound.
  ``meta.scan_bounded=true`` means the eligible set exceeded K, so the
  scan did not inspect the whole directory. The marker is set on
  truncated misses and on truncated-but-found reuse. Never on cache
  hit, non-truncated scan, or full-scan override. Refs: #257.

No network. No Opik import. No product-accept blocking: :func:`bind_final_accept`
never raises for product-accept reasons — it reports outcomes via
:class:`BindResult`.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from git_cg.eval.binding import paths
from git_cg.eval.binding.lock import acquire_bind_lock
from git_cg.eval.binding.profiles import capture_enabled
from git_cg.eval.binding.scan_window import (
    DEFAULT_SCAN_WINDOW,
    FULL_SCAN_ENV,
    SCAN_WINDOW_ENV,
)
from git_cg.eval.cache_json import object_pairs_reject_duplicates, read_bounded_json
from git_cg.eval.corpus.canonical import message_sha256
from git_cg.eval.enums import ArtifactClass, ProvenanceLabel, RedactionProfile
from git_cg.eval.evidence_scrub import mask_secrets_in_text, project_secret_safe
from git_cg.eval.schema_pack import SchemaPackError, is_valid, validate_instance

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
            **not** guaranteed raw model output (N19.5 / NTH-U5). Persisted
            under ``meta.generated_message`` only when the scrubbed result is
            non-empty.
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
_INDEX_VERSION = 2
#: Defensive limits apply only to the rebuildable index, never to bundles.
_INDEX_MAX_BYTES = 1_048_576
_INDEX_MAX_ENTRIES = 4096
_INDEX_MAX_KEY_BYTES = 4096
_INDEX_MAX_SESSION_ID_BYTES = 256


def _acceptpath_scan_window() -> int:
    """Return the miss-scan window, failing closed to the default."""
    raw = os.environ.get(SCAN_WINDOW_ENV)
    if raw is None:
        return DEFAULT_SCAN_WINDOW
    token = raw.strip()
    if not token.isascii() or not token.isdigit():
        return DEFAULT_SCAN_WINDOW
    value = int(token, 10)
    if value < 1:
        return DEFAULT_SCAN_WINDOW
    return value


def _acceptpath_full_scan() -> bool:
    """True only for the diagnostic full-scan override token ``1``."""
    raw = os.environ.get(FULL_SCAN_ENV)
    return raw is not None and raw.strip() == "1"


def _miss_scan_candidates(bundles_dir: Path) -> tuple[list[Path], bool]:
    """Select miss-scan files: mtime desc, filename asc, optional K-window.

    Returns ``(paths, truncated)``. Listing still walks every ``*.json``.
    ``truncated`` is True only when the eligible set exceeded K and the
    full-scan override is off, including truncated-but-found reuse.
    """
    eligible: list[tuple[float, str, Path]] = []
    for path in bundles_dir.glob("*.json"):
        if path.name == "index.json" or path.is_symlink() or not path.is_file():
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        eligible.append((mtime, path.name, path))
    eligible.sort(key=lambda item: (-item[0], item[1]))
    if _acceptpath_full_scan():
        return [item[2] for item in eligible], False
    window = _acceptpath_scan_window()
    truncated = len(eligible) > window
    return [item[2] for item in eligible[:window]], truncated


def _index_entry_admissible(key: object, value: object) -> bool:
    """Return whether one cache entry stays within index shape and byte bounds."""
    try:
        return (
            isinstance(key, str)
            and bool(key)
            and len(key.encode("utf-8")) <= _INDEX_MAX_KEY_BYTES
            and isinstance(value, str)
            and bool(value.strip())
            and len(value.encode("utf-8")) <= _INDEX_MAX_SESSION_ID_BYTES
        )
    except UnicodeEncodeError:
        return False


def _index_object_pairs(pairs: list[tuple[Any, Any]]) -> dict[Any, Any]:
    """Binder-index JSON object hook; reject duplicate keys fail-closed."""
    return object_pairs_reject_duplicates(pairs)


def _index_entry_key(key: tuple[str, str, str]) -> str:
    """Serialize a scoped reuse triple as an injective canonical JSON array."""
    repo_root, token, final_sha = key
    return json.dumps(
        [repo_root, token, final_sha],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _load_index(index_path: Path) -> dict[str, str] | None:
    """Load a bounded, well-shaped index, or return ``None`` on any defect.

    Returns ``None`` for missing, corrupt, wrong-version, oversized, or
    schema-invalid indexes. Any malformed entry discards the whole document.
    Cache absence must never alter binding behaviour.
    """
    data = read_bounded_json(
        index_path,
        max_bytes=_INDEX_MAX_BYTES,
        object_pairs_hook=_index_object_pairs,
        require_mapping=True,
    )
    if data is None or data.get("version") != _INDEX_VERSION:
        return None
    entries = data.get("entries")
    if not isinstance(entries, dict) or len(entries) > _INDEX_MAX_ENTRIES:
        return None
    out: dict[str, str] = {}
    for key, value in entries.items():
        if not _index_entry_admissible(key, value):
            return None
        out[key] = value
    return out


def _write_index(index_path: Path, entries: dict[str, str]) -> None:
    """Best-effort atomic write of a bounded reuse-scan cache. Never raises."""
    if len(entries) > _INDEX_MAX_ENTRIES:
        return
    if any(not _index_entry_admissible(key, value) for key, value in entries.items()):
        return
    payload = {"version": _INDEX_VERSION, "entries": dict(entries)}
    try:
        encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    except TypeError, ValueError:
        return
    if len(encoded) + 1 > _INDEX_MAX_BYTES:
        return
    with contextlib.suppress(OSError, paths.LayerAPathError, TypeError, ValueError):
        paths.atomic_write_json(index_path, payload, serialized=encoded)


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
    """Load an authoritative bundle by session id when present and well-formed.

    Path construction is :func:`paths.session_bundle_path`. Malformed or
    escaped ids are silent misses, never bind failures.
    """
    path = paths.session_bundle_path(bundles_dir, session_id)
    if path is None:
        return None
    try:
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError, UnicodeDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _bundle_matches_key(data: dict[str, Any], key: tuple[str, str, str]) -> bool:
    """True when authoritative bundle ``data`` matches scoped reuse ``key``.

    Stored ``meta.accept_event.repo_root`` must be a nonempty exact match.
    Missing, empty, or cross-root values fail closed.
    """
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
    return isinstance(stored_root, str) and bool(stored_root.strip()) and stored_root == repo_root


def _reuse_identity_adoptable(
    data: dict[str, Any],
    key: tuple[str, str, str],
    *,
    expected_session_id: str | None = None,
    bundle_path: Path | None = None,
) -> bool:
    """True when ``data`` may donate reuse identity.

    Cache hits and miss-scan candidates share this fail-closed gate.
    """
    if not _bundle_matches_key(data, key):
        return False
    if data.get("bound") is not True:
        return False
    if data.get("artifact_class") != ArtifactClass.FINAL_ACCEPT.value:
        return False
    session_id = data.get("session_thread_id")
    if not isinstance(session_id, str) or not session_id.strip():
        return False
    if expected_session_id is not None and session_id != expected_session_id:
        return False
    if bundle_path is not None and bundle_path.stem != session_id:
        return False
    return is_valid("ape_bundle_v1", data)


def _reuse_key(repo_root: Path, accept_event_token: str | None, final_sha: str) -> tuple[str, str, str] | None:
    """Return the scoped reuse key, or ``None`` when no reliable token (N19.2)."""
    if not accept_event_token or not accept_event_token.strip():
        return None
    return (str(Path(repo_root).resolve()), accept_event_token, final_sha)


def _scan_reuse_key(
    bundles_dir: Path,
    key: tuple[str, str, str],
    *,
    index_path: Path | None = None,
    counters: dict[str, int] | None = None,
    scan_state: dict[str, bool] | None = None,
    allow_cache_write: bool = True,
) -> dict[str, Any] | None:
    """Find an existing authoritative acceptpath bundle matching ``key``.

    Consults the optional rebuildable ``index.json`` cache first. Cache hits
    and miss-scan hits are adopted only after reuse-identity validation
    against the authoritative bundle. Cached session ids use
    :func:`paths.session_bundle_path`; malformed or escaped values are
    silent misses. On miss, corrupt, stale, or unadoptable cache, fall
    through to the bounded miss-scan (index caches are never sole
    authority; N19.2/N19.3). Scan hits write through best-effort when
    ``allow_cache_write`` is true.

    When ``index_path`` is omitted, the cache is ``bundles_dir / "index.json"``.

    The miss-scan skips ``index.json``, symlinks, and non-regular
    files. Hard links remain regular files. Candidates are mtime
    descending, filename ascending, and parse-bounded to K unless the
    full-scan override is set. Listing still walks every ``*.json``.
    Only selected candidates are parsed. When the eligible set is
    truncated, ``scan_state["truncated"]`` is set True, including
    truncated-but-found reuse. Cache hits never set that flag.
    """
    if not bundles_dir.is_dir():
        return None

    cache_path = index_path if index_path is not None else bundles_dir / "index.json"
    cached_session = _cache_lookup_session(cache_path, key)
    cached_path = paths.session_bundle_path(bundles_dir, cached_session)
    if cached_path is not None and cached_session is not None:
        cached_bundle = _load_bundle_for_session(bundles_dir, cached_session)
        if cached_bundle is not None and _reuse_identity_adoptable(
            cached_bundle,
            key,
            expected_session_id=cached_session,
            bundle_path=cached_path,
        ):
            _bump_counters(counters, cache_hits=1)
            return cached_bundle
        # Ignore stale or unadoptable cache and fall through.
    _bump_counters(counters, cache_misses=1)

    candidates, truncated = _miss_scan_candidates(bundles_dir)
    if truncated and scan_state is not None:
        scan_state["truncated"] = True

    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError, UnicodeDecodeError:
            continue  # corrupt file is not authority; skip
        if not isinstance(data, dict):
            continue
        if not _reuse_identity_adoptable(data, key, bundle_path=path):
            continue
        # Write-through after authoritative scan hit (best-effort).
        session_id = data.get("session_thread_id")
        if allow_cache_write and isinstance(session_id, str) and session_id.strip():
            _cache_write_through(cache_path, key, session_id)
        return data
    return None


def _resolve_reuse_identity(
    session_id: str | None,
    key: tuple[str, str, str] | None,
    bundles_dir: Path | None,
    index_path: Path | None,
    counters: dict[str, int] | None = None,
    scan_state: dict[str, bool] | None = None,
    allow_cache_write: bool = True,
) -> tuple[str, str]:
    """Return ``(session_id, case_id)`` after optional reuse adoption."""
    case_id: str | None = None
    if key is not None and bundles_dir is not None:
        existing = _scan_reuse_key(
            bundles_dir,
            key,
            index_path=index_path,
            counters=counters,
            scan_state=scan_state,
            allow_cache_write=allow_cache_write,
        )
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
    return session_id, case_id


def _build_bundle_meta(
    inp: BindInput,
    *,
    encoding_meta: dict[str, Any],
    root: Path | None,
    scan_bounded: bool = False,
) -> dict[str, Any]:
    """Assemble secret-safe bind metadata. Final bytes are never included."""
    meta: dict[str, Any] = {"producer": _PRODUCER}
    meta.update(encoding_meta)
    if inp.meta:
        # Additive non-authoritative fields only; never override binder authority.
        # Project secret-safe so evidence surfaces never persist raw secrets.
        safe_meta = project_secret_safe(dict(inp.meta))
        if isinstance(safe_meta, dict):
            for meta_key, value in safe_meta.items():
                meta.setdefault(meta_key, value)
    if scan_bounded:
        meta["scan_bounded"] = True
    else:
        meta.pop("scan_bounded", None)
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
    return meta


def _persist_bundle(
    *,
    root: Path,
    bundles_dir: Path,
    session_id: str,
    bundle: dict[str, Any],
    key: tuple[str, str, str] | None,
    index_path: Path | None,
    allow_cache_write: bool = True,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Atomically persist a bundle and best-effort cache write-through.

    Persistence failures are returned as errors and never raised.
    Cache write-through runs only when ``allow_cache_write`` is true.
    """
    paths_written: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    try:
        out = bundles_dir / f"{session_id}.json"
        paths.atomic_write_json(out, bundle)
        paths_written = (out.relative_to(root).as_posix(),)
        if allow_cache_write and key is not None and index_path is not None:
            _cache_write_through(index_path, key, session_id)
    except (OSError, paths.LayerAPathError) as exc:
        # Persistence failure must not block product accept; report honestly.
        errors = (f"bind_write_error: {exc}",)
    return paths_written, errors


def _bump_counters(counters: dict[str, int] | None, **deltas: int) -> None:
    """Accumulate best-effort counter deltas in memory."""
    if counters is None:
        return
    for name, amount in deltas.items():
        if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            continue
        counters[name] = counters.get(name, 0) + amount


def _flush_counters(anchor: Path | None, counters: dict[str, int], *, write: bool) -> None:
    """Persist accumulated counters on the write path. Never raises."""
    if not write or not counters:
        return
    try:
        from git_cg.eval.binding.diagnostics import increment_binder_counters

        increment_binder_counters(_diagnostics_repo_root(anchor), **counters)
    except Exception:
        return


def _diagnostics_repo_root(anchor: Path | None) -> Path | None:
    """Resolve a repo root for diagnostics from a repo or acceptpath directory."""
    if anchor is None:
        return None
    try:
        resolved = Path(anchor).resolve()
    except OSError:
        return None
    parts = resolved.parts
    marker = (".eval", "bundles", "acceptpath")
    if len(parts) >= 3 and parts[-3:] == marker:
        return resolved.parents[2]
    return resolved


def bind_final_accept(
    inp: BindInput,
    *,
    repo_root: Path | None = None,
    write: bool = True,
) -> BindResult:
    """Bind exact final bytes into ``final_accept`` evidence (D4).

    Hash source is the original ``final_message`` bytes via
    :func:`message_sha256_bytes`, not the stored UTF-8 projection. Invalid
    UTF-8 still projects with ``utf-8-replace`` for the schema text field;
    ``final_message_sha256`` remains the hash of those original bytes.

    Never raises for product-accept reasons. :func:`bind_unbound` may raise
    ``ValueError`` on invalid reason or class inputs.
    Behaviour:

    * Capture disabled ⇒ ``bound=False, unbound_reason="capture_disabled"``,
      zero writes (D1/N19.5).
    * Empty/whitespace final message ⇒ ``bound=False,
      unbound_reason="final_message_absent"``.
    * Invalid ``redaction_profile`` ⇒ ``bound=False,
      unbound_reason="invalid_redaction_profile"``, zero writes.
    * Schema-invalid / unresolved-repo outcomes return unbound results with
      reasons (never product-blocking).
    * ``meta.generated_message`` is persisted only when the scrubbed draft
      is non-empty; empty or fully-scrubbed drafts are omitted.
    * Same ``(repo_root, accept_event_token, final_message_sha256)`` may reuse
      an existing bundle (N19.2); persistence failures are reported on the
      result without blocking accept.
    * Otherwise build a schema-valid ``ape_bundle_v1`` with
      ``artifact_class=final_accept``, ``bound=true``, stored
      ``final_message_sha256`` over the original bytes, and (when ``write``)
      atomically persist under ``.eval/bundles/acceptpath/``.
    * Index write-through runs only while a bind lock is held. Lock
      failure still persists the authoritative bundle and never blocks
      accept.
    """
    if not capture_enabled():
        return BindResult(bound=False, unbound_reason="capture_disabled")

    stats: dict[str, int] = {}

    # Fail closed before hashing, projection, lock, or any filesystem writes.
    redaction = inp.redaction_profile or _DEFAULT_REDACTION
    try:
        redaction = RedactionProfile(redaction).value
    except TypeError, ValueError:
        return BindResult(bound=False, unbound_reason="invalid_redaction_profile")

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
        _bump_counters(stats, bind_attempts=1)

    # Scoped idempotent reuse (N19.2): same event + same bytes ⇒ reuse identity.
    # Short-lived lock around reuse-scan-plus-write; lock failure falls back to
    # unlocked atomic-replace and never blocks product accept.
    session_id = inp.session_thread_id
    key = _reuse_key(root, inp.accept_event_token, final_sha) if root is not None else None
    bundles_dir: Path | None = paths.acceptpath_bundles_dir(root) if root is not None else None
    index_path: Path | None = paths.acceptpath_index_file(root) if root is not None else None
    lock_attempted = bool(write and bundles_dir is not None)
    bind_lock = acquire_bind_lock(bundles_dir) if lock_attempted else None
    if lock_attempted and bind_lock is None:
        _bump_counters(stats, lock_fallbacks=1)
    allow_cache_write = bind_lock is not None
    try:
        scan_state: dict[str, bool] = {}
        session_id, case_id = _resolve_reuse_identity(
            session_id,
            key,
            bundles_dir,
            index_path,
            counters=stats,
            scan_state=scan_state,
            allow_cache_write=allow_cache_write,
        )
        meta = _build_bundle_meta(
            inp,
            encoding_meta=encoding_meta,
            root=root,
            scan_bounded=bool(scan_state.get("truncated")),
        )

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
            # Schema-invalid bind is zero-write, including diagnostics.
            return BindResult(bound=False, unbound_reason="schema_invalid", errors=(str(exc),))

        paths_written: tuple[str, ...] = ()
        errors: tuple[str, ...] = ()
        if write and root is not None and bundles_dir is not None:
            paths_written, errors = _persist_bundle(
                root=root,
                bundles_dir=bundles_dir,
                session_id=session_id,
                bundle=bundle,
                key=key,
                index_path=index_path,
                allow_cache_write=allow_cache_write,
            )

        _bump_counters(stats, bind_success=1)
        _flush_counters(root if root is not None else repo_root, stats, write=write)
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

    Raises ``ValueError`` when the reason is blank, the class is
    ``final_accept``, or the class is not an allowed unbound class
    (``EVAL_FAKE_BOUND``). :func:`bind_final_accept` never raises for
    product-accept reasons. Does not write by default; the returned bundle
    (when constructed) is honest unbound evidence for offline scoring.

    Hash source is the supplied ``final_message`` text via
    :func:`git_cg.eval.corpus.canonical.message_sha256`. This helper accepts
    projected text only; it has no original-byte input.
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
