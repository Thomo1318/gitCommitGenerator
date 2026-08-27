"""S6 Slice 6 deterministic ``eval replay`` engine (Issue #246).

FIND-023 / INT-18 / §7.2.16 / §18.3:

* Read an existing source bundle (accept-path or explicit path).
* Write a **new** replay bundle + schema-valid ``replay_compare_v1``.
* Preserve ``session_thread_id``; mint new replay identity / trace / bundle hash.
* Pin harness + metric catalog + schema pack identities on the compare record.
* **Never** mutate the source bundle (immutability law).

Offline-first: this engine performs a structural lineage replay (copy with new
identity + compare). Live generation resume is a separate ``replay_generation``
run-orchestrator mode and is out of scope here.

Import law: import-light. Path law, pins, and schema validation are lazy.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

SCHEMA_NAME: Final[str] = "replay_compare_v1"
SCHEMA_VERSION: Final[str] = "replay_compare_v1"
BUNDLE_SCHEMA: Final[str] = "ape_bundle_v1"

_SAFE_ID: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


class ReplayError(ValueError):
    """Deterministic replay failure (fail-closed)."""

    def __init__(self, message: str, *, code: str, exit_code: int, hint: str | None = None) -> None:
        """Initialize structured error/context fields for operator engines."""
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code
        self.hint = hint


def _utc_now() -> str:
    """Return the current UTC timestamp as an ISO-8601 Zulu string."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _replays_dir(repo: Path) -> Path:
    """Resolve the governed replay compare store directory."""
    from git_cg.eval.binding.paths import LayerAPathError, replays_dir

    try:
        return replays_dir(repo)
    except LayerAPathError as exc:
        raise ReplayError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc


def _acceptpath_dir(repo: Path) -> Path:
    """Resolve the governed accept-path store directory."""
    from git_cg.eval.binding.paths import LayerAPathError, acceptpath_bundles_dir

    try:
        return acceptpath_bundles_dir(repo)
    except LayerAPathError as exc:
        raise ReplayError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc


def _atomic_write(path: Path, payload: dict[str, Any]) -> Path:
    """Atomically write JSON through the Layer-A path helper (fail closed)."""
    from git_cg.eval.binding.paths import LayerAPathError, atomic_write_json

    try:
        return atomic_write_json(path, payload)
    except LayerAPathError as exc:
        raise ReplayError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc


def _validate_compare(row: dict[str, Any]) -> None:
    """Validate a payload against the closed schema/contract (fail closed)."""
    from git_cg.eval.schema_pack import SchemaPackError, validate_instance

    try:
        validate_instance(SCHEMA_NAME, row)
    except SchemaPackError as exc:
        raise ReplayError(
            f"replay_compare_v1 validation failed: {exc}",
            code="EVAL_STORE_INTEGRITY",
            exit_code=4,
        ) from exc


def _validate_bundle(row: dict[str, Any]) -> None:
    """Validate a payload against the closed schema/contract (fail closed)."""
    from git_cg.eval.schema_pack import SchemaPackError, validate_instance

    try:
        validate_instance(BUNDLE_SCHEMA, row)
    except SchemaPackError as exc:
        raise ReplayError(
            f"ape_bundle_v1 validation failed: {exc}",
            code="EVAL_STORE_INTEGRITY",
            exit_code=4,
        ) from exc


def _load_json(path: Path, *, code: str = "EVAL_STORE_INTEGRITY", exit_code: int = 4) -> dict[str, Any]:
    """Load a JSON object from disk; map I/O and decode failures to the module error type."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReplayError(f"cannot read {path.name}: {exc}", code=code, exit_code=exit_code) from exc
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ReplayError(f"{path.name} is not valid JSON: {exc}", code=code, exit_code=exit_code) from exc
    if not isinstance(obj, dict):
        raise ReplayError(f"{path.name} must contain a JSON object", code=code, exit_code=exit_code)
    return obj


def _bundle_hash(bundle: dict[str, Any]) -> str:
    """Compute the stable content hash used for bundle lineage."""
    from git_cg.eval.corpus.canonical import content_sha256

    return content_sha256(bundle)


def _harness_version() -> str:
    """Best-effort package version; never raises."""
    try:
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version("gitcommitgenerator")
        except PackageNotFoundError:
            pass
    except Exception:
        pass
    try:
        import tomllib

        root = Path(__file__).resolve().parents[3]
        data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        project = data.get("project") if isinstance(data, dict) else None
        if isinstance(project, dict):
            ver = str(project.get("version") or "").strip()
            if ver:
                return ver
    except Exception:
        pass
    return "0.0.0"


def _current_pins() -> tuple[str, str]:
    """Read the current schema/metric pins for offline integrity checks."""
    from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin

    return schema_pack_pin(), metric_catalog_pin()


def _pin_or_current(value: Any, *, current: str) -> str:
    """Use an explicit pin when provided, otherwise the current frozen pin."""
    text = str(value or "").strip()
    if re.fullmatch(r"^[a-z0-9_]+_v[0-9]+@[a-f0-9]{64}$", text):
        return text
    return current


def _extract_trace_id(bundle: dict[str, Any]) -> str:
    """Extract a typed field from a bundle/record without inventing defaults that mute integrity failures."""
    meta = bundle.get("meta") if isinstance(bundle.get("meta"), dict) else {}
    binding = meta.get("binding") if isinstance(meta.get("binding"), dict) else {}
    for candidate in (
        binding.get("trace_id"),
        meta.get("trace_id"),
        bundle.get("trace_id"),
    ):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return ""


def _extract_split_group(bundle: dict[str, Any]) -> str | None:
    """Extract a typed field from a bundle/record without inventing defaults that mute integrity failures."""
    meta = bundle.get("meta") if isinstance(bundle.get("meta"), dict) else {}
    for candidate in (meta.get("split_group_id"), bundle.get("split_group_id")):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    session = bundle.get("session_thread_id")
    if isinstance(session, str) and session.strip():
        return f"sg:{session.strip()}"
    case_id = bundle.get("case_id")
    if isinstance(case_id, str) and case_id.strip():
        return f"sg:{case_id.strip()}"
    return None


def _resolve_source_bundle(
    repo: Path,
    *,
    bundle: str | None,
    experiment_id: str | None,
    case_id: str | None,
) -> tuple[dict[str, Any], Path]:
    """Locate the immutable source bundle.

    Resolution order:
    1. Explicit ``bundle`` path (absolute/relative file).
    2. ``bundle`` as accept-path session_thread_id / stem under
       ``.eval/bundles/acceptpath/``.
    3. ``experiment_id`` + ``case_id`` case-result → session_thread_id / case_id
       lookup under accept-path (explain-command contract).
    """
    if bundle and bundle.strip():
        token = bundle.strip()
        as_path = Path(token)
        candidates: list[Path] = []
        if as_path.is_file():
            candidates.append(as_path)
        else:
            root = _acceptpath_dir(repo)
            if _SAFE_ID.fullmatch(token):
                candidates.append(root / f"{token}.json")
            # Also allow bare filename.
            candidates.append(root / token)
            if not token.endswith(".json"):
                candidates.append(root / f"{token}.json")
        for path in candidates:
            if path.is_file():
                obj = _load_json(path, code="EVAL_USAGE", exit_code=2)
                if obj.get("schema_version") != BUNDLE_SCHEMA:
                    raise ReplayError(
                        f"source is not ape_bundle_v1: {path.name}",
                        code="EVAL_USAGE",
                        exit_code=2,
                        hint="Pass an accept-path bundle path or session_thread_id.",
                    )
                return obj, path
        raise ReplayError(
            f"source bundle not found: {token!r}",
            code="EVAL_USAGE",
            exit_code=2,
            hint="Pass --bundle path|session_thread_id or --experiment-id + --case.",
        )

    if experiment_id and case_id:
        from git_cg.eval.binding.paths import LayerAPathError, experiments_dir

        try:
            exp_root = experiments_dir(repo)
        except LayerAPathError as exc:
            raise ReplayError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc
        case_path = exp_root / experiment_id / "cases" / f"{case_id}.json"
        if not case_path.is_file():
            raise ReplayError(
                f"case not found: experiment={experiment_id!r} case={case_id!r}",
                code="EVAL_USAGE",
                exit_code=2,
                hint="Pass a case id from `git-cg eval failures` / `eval explain`.",
            )
        case = _load_json(case_path, code="EVAL_STORE_INTEGRITY", exit_code=4)
        session = case.get("session_thread_id") or case.get("case_id")
        if not isinstance(session, str) or not session.strip():
            raise ReplayError(
                "case row lacks session_thread_id/case_id for bundle lookup",
                code="EVAL_USAGE",
                exit_code=2,
            )
        return _resolve_source_bundle(repo, bundle=session.strip(), experiment_id=None, case_id=None)

    raise ReplayError(
        "replay requires --bundle or --experiment-id + --case",
        code="EVAL_USAGE",
        exit_code=2,
        hint="Example: git-cg eval replay --bundle <session_thread_id>",
    )


def _build_replay_bundle(
    source: dict[str, Any],
    *,
    replay_id: str,
    replay_trace_id: str,
    source_hash: str,
    source_trace_id: str,
    schema_pack: str,
    metric_catalog: str,
) -> dict[str, Any]:
    """Construct a new ape_bundle_v1 that preserves thread lineage."""
    replay = json.loads(json.dumps(source))  # deep copy via JSON (JSON-safe bundles)
    session = str(source.get("session_thread_id") or "").strip()
    if not session:
        # Fail closed on missing thread — lineage law requires retention when present;
        # mint a stable synthetic thread only when source never had one.
        session = f"thread:{replay_id}"
        replay["session_thread_id"] = session
    else:
        replay["session_thread_id"] = session

    # New identity: case_id becomes a replay-scoped id; source case retained in meta.
    source_case = str(source.get("case_id") or "unknown")
    replay["case_id"] = f"replay:{replay_id}:{source_case}"

    meta = replay.get("meta") if isinstance(replay.get("meta"), dict) else {}
    meta = dict(meta)
    binding = meta.get("binding") if isinstance(meta.get("binding"), dict) else {}
    binding = dict(binding)
    binding["trace_id"] = replay_trace_id
    binding["state"] = binding.get("state") or ("bound" if source.get("bound") else "unbound")
    meta["binding"] = binding
    meta["replay_of_trace_id"] = source_trace_id
    meta["replay_of_bundle_hash"] = source_hash
    meta["replay_id"] = replay_id
    split = _extract_split_group(source)
    if split:
        meta["split_group_id"] = split
    meta["producer"] = meta.get("producer") or "git_cg.eval.replay"
    replay["meta"] = meta

    # Preserve/pin pack identities on the bundle when the schema allows.
    replay["schema_pack"] = _pin_or_current(source.get("schema_pack") or meta.get("schema_pack"), current=schema_pack)
    replay["metric_catalog"] = _pin_or_current(
        source.get("metric_catalog") or meta.get("metric_catalog"),
        current=metric_catalog,
    )

    _validate_bundle(replay)
    return replay


def _regression_status(*, input_equal: bool, lineage_ok: bool) -> str:
    """Classify replay/compare regression status from metric deltas."""
    if not lineage_ok:
        return "incomparable"
    if input_equal:
        return "unchanged"
    return "incomparable"


def replay(
    repo: Path,
    *,
    bundle: str | None = None,
    experiment_id: str | None = None,
    case_id: str | None = None,
    notes: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Execute offline structural replay + write ``replay_compare_v1``.

    Returns a result dict with compare record, paths, and hashes. Source path
    bytes are re-read after write to prove immutability when not dry-run.
    """
    source, source_path = _resolve_source_bundle(
        repo,
        bundle=bundle,
        experiment_id=experiment_id,
        case_id=case_id,
    )
    source_bytes_before = source_path.read_bytes()
    source_hash = _bundle_hash(source)
    source_trace = _extract_trace_id(source)
    source_id = str(source.get("case_id") or source_path.stem)

    schema_pack, metric_catalog = _current_pins()
    # Prefer source pins when already well-formed; else current repo pins.
    pinned_schema = _pin_or_current(source.get("schema_pack"), current=schema_pack)
    pinned_catalog = _pin_or_current(source.get("metric_catalog"), current=metric_catalog)
    harness = _harness_version()

    replay_id = f"replay-{uuid.uuid4().hex[:12]}"
    replay_trace_id = f"trace-replay-{uuid.uuid4().hex}"
    session_thread_id = str(source.get("session_thread_id") or f"thread:{replay_id}")

    replay_bundle = _build_replay_bundle(
        source,
        replay_id=replay_id,
        replay_trace_id=replay_trace_id,
        source_hash=source_hash,
        source_trace_id=source_trace,
        schema_pack=pinned_schema,
        metric_catalog=pinned_catalog,
    )
    replay_hash = _bundle_hash(replay_bundle)

    # Structural offline replay: generation_task_input equality defines input_equal.
    src_input = source.get("generation_task_input")
    rep_input = replay_bundle.get("generation_task_input")
    input_equal = src_input == rep_input
    lineage_ok = bool(session_thread_id) and bool(source_hash) and source_hash != replay_hash

    compare: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "id": f"cmp-{replay_id}",
        "source_id": source_id,
        "replay_id": replay_id,
        "lineage_ok": lineage_ok,
        "session_thread_id": session_thread_id,
        "source_bundle_hash": source_hash,
        "replay_bundle_hash": replay_hash,
        "source_trace_id": source_trace,
        "replay_trace_id": replay_trace_id,
        "pinned": {
            "harness_version": harness,
            "metric_catalog": pinned_catalog,
            "schema_pack": pinned_schema,
        },
        "deltas": {
            "input_equal": input_equal,
            "metric_deltas": [],
        },
        "regression_status": _regression_status(input_equal=input_equal, lineage_ok=lineage_ok),
        "schema_pack": pinned_schema,
        "metric_catalog": pinned_catalog,
        "created_at": _utc_now(),
    }
    if notes and notes.strip():
        compare["notes"] = notes.strip()

    _validate_compare(compare)

    compare_path = _replays_dir(repo) / f"{replay_id}.json"
    bundle_path = _replays_dir(repo) / f"{replay_id}.bundle.json"

    if not dry_run:
        _atomic_write(bundle_path, replay_bundle)
        _atomic_write(compare_path, compare)
        # Immutability proof: source bytes must be unchanged.
        source_bytes_after = source_path.read_bytes()
        if source_bytes_after != source_bytes_before:
            raise ReplayError(
                "source bundle mutated during replay (immutability violation)",
                code="EVAL_STORE_INTEGRITY",
                exit_code=4,
            )

    return {
        "compare": compare,
        "replay_bundle": replay_bundle,
        "source_path": str(source_path),
        "compare_path": str(compare_path),
        "replay_bundle_path": str(bundle_path),
        "source_bundle_hash": source_hash,
        "replay_bundle_hash": replay_hash,
        "dry_run": dry_run,
        "source_mutated": False,
    }


def show_replay(repo: Path, *, replay_id: str) -> dict[str, Any]:
    """Load one stored ``replay_compare_v1`` row."""
    if not _SAFE_ID.fullmatch(replay_id):
        raise ReplayError(f"invalid replay_id: {replay_id!r}", code="EVAL_USAGE", exit_code=2)
    path = _replays_dir(repo) / f"{replay_id}.json"
    if not path.is_file():
        raise ReplayError(
            f"replay not found: {replay_id!r}",
            code="EVAL_USAGE",
            exit_code=2,
            hint="Pass a replay_id from a prior `git-cg eval replay`.",
        )
    row = _load_json(path)
    if row.get("schema_version") != SCHEMA_VERSION:
        raise ReplayError(
            f"replay row has unexpected schema: {replay_id!r}",
            code="EVAL_STORE_INTEGRITY",
            exit_code=4,
        )
    return {"compare": row, "compare_path": str(path)}


__all__ = [
    "SCHEMA_NAME",
    "SCHEMA_VERSION",
    "ReplayError",
    "replay",
    "show_replay",
]
