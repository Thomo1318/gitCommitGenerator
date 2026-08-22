"""S6 Slice 7 offline R11 amend brief engine (Issue #246 / §8.6).

Builds and persists an ``amend_brief_v1`` document from already-landed Layer-A
evidence (Slice 3 case results / bundles), plus optional doctor output and
last-N Lane C/dogfood attachments. **Fully offline** — no Opik, no network, no
scoring re-run (RK-S6-12).

Laws:
* L1 rollups (``regime``, ``family_rollups``, ``failure_ids``, ``path_class``,
  ``gold_counters``, ``blocking``) are **computed projections** from score
  rows/gates — never assumed as bundle fields.
* ``session_thread_id`` / ``message_versions`` are referenced from the landed
  S3 session twin when supplied; a preference pair is emitted only when the
  twin carries >= 2 real message versions (M7 — never invented).
* ``authority`` is always ``advisory`` — the brief is never an accept/golden
  gate and never blocks the product path.
* Persistence is atomic + contained under ``.eval/amend_briefs/`` (N19.3).

Import law: import-light. Path / schema / explain helpers are lazy.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

SCHEMA_VERSION: Final[str] = "amend_brief_v1"
CASE_RESULT_SCHEMA: Final[str] = "local_case_score_v0"
DEFAULT_REDACTION: Final[str] = "default_scrub"

_SAFE_ID: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
#: Family letter → metric-id prefix (catalog law).
_FAMILY_PREFIX: Final[dict[str, str]] = {
    "a": "A",
    "b": "B",
    "c": "C",
    "d": "D",
    "e": "E",
    "f": "F",
    "g": "G",
    "h": "H",
    "i": "I",
    "cprime": "Cprime",
    "gate": "gate",
    "human": "human",
    "dogfood": "dogfood",
}
_REGIMES: Final[frozenset[str]] = frozenset({"A", "B", "unknown"})
#: Gold counters surfaced from Family D signals (computed, not bundle fields).
_GOLD_COUNTER_METRICS: Final[tuple[str, ...]] = (
    "d.strict_fail_set",
    "d.skeleton_fallback_final",
)


class AmendBriefError(ValueError):
    """Deterministic amend-brief failure (fail-closed)."""

    def __init__(self, message: str, *, code: str, exit_code: int, hint: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code
        self.hint = hint


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _load_json(path: Path, *, code: str = "EVAL_STORE_INTEGRITY", exit_code: int = 4) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AmendBriefError(f"cannot read {path.name}: {exc}", code=code, exit_code=exit_code) from exc
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AmendBriefError(f"{path.name} is not valid JSON: {exc}", code=code, exit_code=exit_code) from exc
    if not isinstance(obj, dict):
        raise AmendBriefError(f"{path.name} must contain a JSON object", code=code, exit_code=exit_code)
    return obj


def _atomic_write(path: Path, payload: dict[str, Any]) -> Path:
    from git_cg.eval.binding.paths import LayerAPathError, atomic_write_json

    try:
        return atomic_write_json(path, payload)
    except LayerAPathError as exc:
        raise AmendBriefError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc


def _briefs_dir(repo: Path) -> Path:
    from git_cg.eval.binding.paths import LayerAPathError, amend_briefs_dir

    try:
        return amend_briefs_dir(repo)
    except LayerAPathError as exc:
        raise AmendBriefError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc


def _dogfood_dir(repo: Path) -> Path:
    from git_cg.eval.binding.paths import LayerAPathError, dogfood_dir

    try:
        return dogfood_dir(repo)
    except LayerAPathError as exc:
        raise AmendBriefError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc


def _family_of(metric_id: str) -> str | None:
    token = str(metric_id).strip().lower()
    if not token:
        return None
    if token.startswith("cprime."):
        return "Cprime"
    head = token.split(".", 1)[0]
    return _FAMILY_PREFIX.get(head)


def _score_rows(case: dict[str, Any]) -> list[dict[str, Any]]:
    return [r for r in (case.get("scores") or []) if isinstance(r, dict) and r.get("metric_id")]


def _family_rollups(cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per-family rollup projections computed from score rows (not bundle fields)."""
    by_family: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        for row in _score_rows(case):
            fam = _family_of(str(row["metric_id"]))
            if fam is None or fam == "gate":
                continue
            by_family.setdefault(fam, []).append(row)
    rollups: dict[str, dict[str, Any]] = {}
    for fam in sorted(by_family):
        rows = by_family[fam]
        scored = [r for r in rows if r.get("passed") is not None]
        passed = [r for r in scored if r.get("passed") is True]
        entry: dict[str, Any] = {
            "metrics": len(rows),
            "scored": len(scored),
            "passed": len(passed),
            "failed": len(scored) - len(passed),
        }
        if scored:
            entry["pass_rate"] = round(len(passed) / len(scored), 6)
        failing_ids = sorted({str(r["metric_id"]) for r in scored if r.get("passed") is False})
        if failing_ids:
            entry["failing_metric_ids"] = failing_ids
        rollups[fam] = entry
    return rollups


def _failure_ids(cases: list[dict[str, Any]]) -> list[str]:
    ids: set[str] = set()
    for case in cases:
        for row in _score_rows(case):
            if row.get("passed") is False:
                ids.update(str(f) for f in (row.get("failure_ids") or []))
        ids.update(str(f) for f in (case.get("failed_metric_ids") or []))
    return sorted(ids)


def _gold_counters(cases: list[dict[str, Any]]) -> dict[str, int]:
    """Family-D gold counter projections (strict fails, skeleton fallbacks)."""
    strict_fail = 0
    skeleton_fallback = 0
    for case in cases:
        for row in _score_rows(case):
            mid = str(row.get("metric_id") or "")
            if mid == "d.strict_fail_set":
                value = row.get("value")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    strict_fail += int(value)
                elif row.get("passed") is False:
                    strict_fail += 1
            elif mid == "d.skeleton_fallback_final":
                if row.get("value") is True or row.get("passed") is False:
                    skeleton_fallback += 1
    return {"strict_fail": strict_fail, "skeleton_fallback_final": skeleton_fallback}


def _regime(cases: list[dict[str, Any]], bundle: dict[str, Any] | None) -> str:
    if bundle is not None:
        token = str(bundle.get("regime") or (bundle.get("meta") or {}).get("regime") or "").strip().upper()
        if token in _REGIMES:
            return token
    for case in cases:
        for row in _score_rows(case):
            ev = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
            fp = ev.get("diag_fingerprint_inputs") if isinstance(ev.get("diag_fingerprint_inputs"), dict) else {}
            token = str(fp.get("regime") or "").strip().upper()
            if token in _REGIMES:
                return token
    return "unknown"


def _path_class(cases: list[dict[str, Any]], bundle: dict[str, Any] | None) -> str:
    if bundle is not None:
        for key in ("path_class_gate", "path_class"):
            token = str(bundle.get(key) or "").strip()
            if token:
                return token
        gti = bundle.get("generation_task_input") if isinstance(bundle.get("generation_task_input"), dict) else {}
        token = str(gti.get("path_class_gate") or gti.get("path_class") or "").strip()
        if token:
            return token
    for case in cases:
        for row in _score_rows(case):
            ev = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
            fp = ev.get("diag_fingerprint_inputs") if isinstance(ev.get("diag_fingerprint_inputs"), dict) else {}
            token = str(fp.get("path_class_key") or fp.get("path_class") or "").strip()
            if token:
                return token
    return "unknown"


def _blocking(cases: list[dict[str, Any]]) -> dict[str, Any]:
    codes: list[str] = []
    reasons: list[str] = []
    for case in cases:
        if case.get("deterministic_pass") is False:
            codes.append("gate.deterministic_pass")
        for gate in case.get("gates") or []:
            if not isinstance(gate, dict):
                continue
            if gate.get("passed") is False:
                codes.append(str(gate.get("metric_id") or gate.get("gate_id") or "gate"))
                reason = gate.get("reason")
                if isinstance(reason, str) and reason.strip():
                    reasons.append(reason.strip())
    codes = sorted(set(codes))
    return {"blocked": bool(codes), "codes": codes, "reasons": sorted(set(reasons))}


def _preference_pair_from_twin(twin: dict[str, Any] | None) -> dict[str, Any] | None:
    """Emit a preference pair only when the twin carries >= 2 real versions (M7)."""
    if not isinstance(twin, dict):
        return None
    versions = [v for v in (twin.get("message_versions") or []) if isinstance(v, dict)]
    if len(versions) < 2:
        return None

    def _vid(v: dict[str, Any], idx: int) -> str:
        sha = str(v.get("message_sha256") or "")
        kind = str(v.get("kind") or "version")
        return f"{kind}:{sha[:12]}" if sha else f"{kind}:{idx}"

    chosen_idx = next(
        (i for i in range(len(versions) - 1, -1, -1) if versions[i].get("kind") == "final_accept"),
        len(versions) - 1,
    )
    chosen = _vid(versions[chosen_idx], chosen_idx)
    rejected = [_vid(v, i) for i, v in enumerate(versions) if i != chosen_idx]
    if not rejected:
        return None
    return {
        "chosen_version_id": chosen,
        "rejected_version_ids": rejected,
        "owner_approved": True,
        "notes": "chosen=final accepted version; rejected=earlier observed versions (chronological).",
    }


def _lane_c_attachments(repo: Path, *, last_n: int) -> list[dict[str, Any]]:
    """Last-N dogfood attachments (advisory, bounded; never required)."""
    root = _dogfood_dir(repo)
    if not root.is_dir():
        return []
    rows: list[tuple[float, Path]] = []
    for path in root.glob("*.json"):
        try:
            rows.append((path.stat().st_mtime, path))
        except OSError:
            continue
    rows.sort(key=lambda t: (t[0], t[1].name), reverse=True)
    out: list[dict[str, Any]] = []
    for _, path in rows[: max(0, last_n)]:
        try:
            obj = _load_json(path)
        except AmendBriefError:
            continue
        if obj.get("schema_version") != "dogfood_attachment_v1":
            continue
        out.append(
            {
                "run_id": str(obj.get("run_id") or path.stem),
                "judge_id": str(obj.get("judge_id") or "unknown"),
                "pin_ref": str(obj.get("pin_ref") or ""),
                "mode": str(obj.get("mode") or "off"),
                "authority": "advisory",
                **({"score": obj["score"]} if isinstance(obj.get("score"), (int, float)) else {}),
                **({"polarity": obj["polarity"]} if isinstance(obj.get("polarity"), str) else {}),
                **({"rationale_short": obj["rationale_short"]} if isinstance(obj.get("rationale_short"), str) else {}),
            }
        )
    return out


def _resolve_case_rows(
    repo: Path,
    *,
    experiment_id: str | None,
    case_id: str | None,
) -> tuple[str | None, list[dict[str, Any]]]:
    """Load landed case results (latest experiment when omitted). Empty when absent."""
    from git_cg.eval.binding.paths import LayerAPathError, experiments_dir

    try:
        root = experiments_dir(repo)
    except LayerAPathError as exc:
        raise AmendBriefError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc
    if not root.is_dir():
        raise AmendBriefError(
            "no local experiments store (.eval/experiments/) — nothing to brief",
            code="EVAL_STORE_INTEGRITY",
            exit_code=4,
            hint="Run `git-cg eval run` first to land a local score run.",
        )

    exp = experiment_id
    if not exp:
        ids = [p.name for p in root.iterdir() if p.is_dir() and (p / "experiment.json").is_file()]
        if not ids:
            raise AmendBriefError(
                "no local experiment with experiment.json found",
                code="EVAL_STORE_INTEGRITY",
                exit_code=4,
            )
        ids.sort(key=lambda n: (root / n).stat().st_mtime if (root / n).exists() else 0.0, reverse=True)
        exp = ids[0]
    elif not (root / exp).is_dir():
        raise AmendBriefError(
            f"experiment not found: {exp!r}",
            code="EVAL_USAGE",
            exit_code=2,
            hint="Pass an experiment id from .eval/experiments/ (or omit for latest).",
        )

    cases_root = root / exp / "cases"
    if not cases_root.is_dir():
        return exp, []
    rows: list[dict[str, Any]] = []
    for path in sorted(cases_root.glob("*.json")):
        obj = _load_json(path)
        if obj.get("schema_version") != CASE_RESULT_SCHEMA:
            raise AmendBriefError(
                f"{path.name} has unexpected schema_version {obj.get('schema_version')!r}",
                code="EVAL_STORE_INTEGRITY",
                exit_code=4,
                hint="Only local_case_score_v0 rows feed the amend brief.",
            )
        rows.append(obj)
    if case_id is not None:
        rows = [r for r in rows if str(r.get("case_id")) == case_id]
        if not rows:
            raise AmendBriefError(
                f"case not found in experiment {exp!r}: {case_id!r}",
                code="EVAL_USAGE",
                exit_code=2,
                hint="Pass a case_id present in the experiment's case results.",
            )
    return exp, rows


def _load_bundle(repo: Path, bundle_id: str | None) -> dict[str, Any] | None:
    if bundle_id is None:
        return None
    if not _SAFE_ID.fullmatch(bundle_id):
        raise AmendBriefError(f"invalid bundle id: {bundle_id!r}", code="EVAL_USAGE", exit_code=2)
    from git_cg.eval.binding.paths import LayerAPathError, acceptpath_bundles_dir

    try:
        root = acceptpath_bundles_dir(repo)
    except LayerAPathError as exc:
        raise AmendBriefError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc
    path = root / f"{bundle_id}.json"
    if not path.is_file():
        raise AmendBriefError(
            f"bundle not found: {bundle_id!r}",
            code="EVAL_USAGE",
            exit_code=2,
            hint="Pass a bundle id from .eval/bundles/acceptpath/.",
        )
    return _load_json(path)


def _load_session_twin(repo: Path, session_thread_id: str | None) -> dict[str, Any] | None:
    if not session_thread_id:
        return None
    from git_cg.eval.sessions import SessionsError, read_session_twin

    try:
        return read_session_twin(repo, session_thread_id).get("twin")
    except SessionsError:
        # Session reference is optional for the brief — surface absence, never block.
        return None


def build_amend_brief(
    repo: Path,
    *,
    experiment_id: str | None = None,
    case_id: str | None = None,
    bundle_id: str | None = None,
    session_thread_id: str | None = None,
    include_doctor: bool = False,
    doctor_report: dict[str, Any] | None = None,
    lane_c_last_n: int = 0,
    commit_subject: str | None = None,
    trailers: dict[str, str] | None = None,
    notes: str | None = None,
    redaction_profile: str = DEFAULT_REDACTION,
    brief_id: str | None = None,
) -> dict[str, Any]:
    """Build a schema-valid ``amend_brief_v1`` from landed local evidence.

    Fully offline; advisory only; never an accept/golden gate.
    """
    _exp, cases = _resolve_case_rows(repo, experiment_id=experiment_id, case_id=case_id)
    bundle = _load_bundle(repo, bundle_id)
    twin = _load_session_twin(repo, session_thread_id)

    l1 = {
        "regime": _regime(cases, bundle),
        "family_rollups": _family_rollups(cases),
        "failure_ids": _failure_ids(cases),
        "path_class": _path_class(cases, bundle),
        "gold_counters": _gold_counters(cases),
        "blocking": _blocking(cases),
    }

    bid = brief_id or f"brief-{uuid.uuid4().hex[:12]}"
    if not _SAFE_ID.fullmatch(bid):
        raise AmendBriefError(f"invalid brief_id: {bid!r}", code="EVAL_USAGE", exit_code=2)

    brief: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "id": bid,
        "brief_id": bid,
        "l1": l1,
        "authority": "advisory",
        "redaction_profile": redaction_profile,
        "created_at": _utc_now(),
    }

    if session_thread_id:
        brief["session_thread_id"] = session_thread_id
    if case_id:
        brief["case_id"] = case_id
    if bundle_id:
        brief["bundle_id"] = bundle_id
    if commit_subject:
        brief["commit_subject"] = commit_subject
    if trailers:
        brief["trailers"] = dict(trailers)

    pair = _preference_pair_from_twin(twin)
    if pair is not None:
        brief["preference_pair"] = pair

    attachments = _lane_c_attachments(repo, last_n=lane_c_last_n) if lane_c_last_n else []
    if attachments:
        brief["lane_c_attachments"] = attachments

    if include_doctor:
        doctor: dict[str, Any]
        if doctor_report is not None:
            checks = doctor_report.get("checks") if isinstance(doctor_report.get("checks"), list) else []
            block = doctor_report.get("block_failures") if isinstance(doctor_report.get("block_failures"), list) else []
            doctor = {
                "green": bool(doctor_report.get("green")),
                "check_ids": [str(c.get("check_id")) for c in checks if isinstance(c, dict) and c.get("check_id")],
                "failure_ids": [str(x) for x in block],
            }
        else:
            doctor = {"green": True, "check_ids": [], "failure_ids": [], "notes": "doctor not run; no data attached"}
        brief["doctor"] = doctor

    if notes:
        brief["notes"] = notes

    from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin

    brief["schema_pack"] = schema_pack_pin()
    brief["metric_catalog"] = metric_catalog_pin()

    from git_cg.eval.schema_pack import SchemaPackError, validate_instance

    try:
        validate_instance(SCHEMA_VERSION, brief)
    except SchemaPackError as exc:
        raise AmendBriefError(
            f"amend_brief_v1 validation failed: {exc}",
            code="EVAL_STORE_INTEGRITY",
            exit_code=4,
        ) from exc
    return brief


def write_amend_brief(repo: Path, brief: dict[str, Any]) -> Path:
    """Persist a validated brief under ``.eval/amend_briefs/`` (atomic, contained)."""
    bid = str(brief.get("brief_id") or brief.get("id") or "")
    if not _SAFE_ID.fullmatch(bid):
        raise AmendBriefError(f"invalid brief_id: {bid!r}", code="EVAL_USAGE", exit_code=2)
    path = _briefs_dir(repo) / f"{bid}.json"
    cleaned = {k: v for k, v in brief.items() if v is not None}
    return _atomic_write(path, cleaned)


def amend_brief(
    repo: Path,
    *,
    experiment_id: str | None = None,
    case_id: str | None = None,
    bundle_id: str | None = None,
    session_thread_id: str | None = None,
    include_doctor: bool = False,
    doctor_report: dict[str, Any] | None = None,
    lane_c_last_n: int = 0,
    commit_subject: str | None = None,
    trailers: dict[str, str] | None = None,
    notes: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Build + (optionally) persist an amend brief; return CLI data payload."""
    brief = build_amend_brief(
        repo,
        experiment_id=experiment_id,
        case_id=case_id,
        bundle_id=bundle_id,
        session_thread_id=session_thread_id,
        include_doctor=include_doctor,
        doctor_report=doctor_report,
        lane_c_last_n=lane_c_last_n,
        commit_subject=commit_subject,
        trailers=trailers,
        notes=notes,
    )
    path: Path | None = write_amend_brief(repo, brief) if write else None
    return {
        "brief": brief,
        "brief_id": brief["brief_id"],
        "written": path is not None,
        "path": path.as_posix() if path is not None else None,
        "experiment_id": experiment_id,
        "authority": "advisory",
        "blocking": brief["l1"]["blocking"]["blocked"],
        "preference_pair_emitted": "preference_pair" in brief,
        "lane_c_attachments": len(brief.get("lane_c_attachments") or []),
    }


__all__ = [
    "SCHEMA_VERSION",
    "AmendBriefError",
    "amend_brief",
    "build_amend_brief",
    "write_amend_brief",
]
