"""S6 suite run / resume / recompute orchestrator (Issue #246 Slice 3).

Wraps landed ``score_bundle`` / ``prepare_suite_cases`` only — no second scorer.
Defaults: offline, Lane C off, dogfood attachments off.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from git_cg.eval.binding.paths import (
    LayerAPathError,
    acceptpath_bundles_dir,
    atomic_write_json,
    experiments_dir,
    resolve_repo_root,
)
from git_cg.eval.checkpoint_store import (
    CheckpointStoreError,
    build_checkpoint_record,
    load_checkpoint,
    prune_checkpoints,
    utc_now_iso,
    write_checkpoint,
)
from git_cg.eval.compat import (
    COMPAT_HASH_MISMATCH_CODE,
    CompatHashMismatchError,
    assert_compat_hash,
    compute_compat_hash,
)
from git_cg.eval.mirror.experiments import build_experiment
from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin
from git_cg.eval.scoring.runner import PreparedSuite, ScoreCaseResult, prepare_suite_cases, score_bundle

__all__ = [
    "RunMode",
    "RunOrchestratorError",
    "RunRequest",
    "RunResult",
    "run_evaluation",
]

RunMode = Literal[
    "fresh_suite_run",
    "resume_missing",
    "recompute_scores",
    "replay_generation",
    "export_only",
]

_SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,190}$")


class RunOrchestratorError(ValueError):
    """Orchestrator failure with CLI exit-code class."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        exit_code: int,
        hint: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Attach orchestrator failure code, exit class, hint, and data."""
        self.code = code
        self.exit_code = exit_code
        self.hint = hint
        self.data = data or {}
        super().__init__(message)


@dataclass(slots=True)
class RunRequest:
    """Inputs for :func:`run_evaluation`."""

    mode: RunMode = "fresh_suite_run"
    suite_id: str = "cm-eval-fixtures-core"
    fixture_root: Path | None = None
    repo_root: Path | None = None
    gold_mode: str = "strict"
    network_policy: str = "offline_required"
    offline: bool = True
    enable_lane_c: bool = False
    enable_dogfood: bool = False
    keep_last: int = 10
    keep_checkpoint: bool = False
    checkpoint_id: str | None = None
    experiment_id: str | None = None
    case_ids: tuple[str, ...] | None = None
    allow_replay_generation: bool = False
    judge_pack_pin: str | None = None


@dataclass(slots=True)
class CaseSummary:
    """Compact per-case summary used in run progress and resume."""

    case_id: str
    deterministic_pass: bool | None
    failed_metric_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the case summary for checkpoint and envelope payloads."""
        return {
            "case_id": self.case_id,
            "deterministic_pass": self.deterministic_pass,
            "failed_metric_ids": list(self.failed_metric_ids),
        }


@dataclass(slots=True)
class RunResult:
    """Terminal orchestrator result projected into the CLI envelope data payload."""

    status: Literal["completed", "failed", "blocked"]
    mode: RunMode
    suite_id: str
    experiment_id: str
    parent_experiment_id: str | None
    checkpoint_id: str | None
    compat_hash: str
    completed_case_ids: list[str]
    pending_case_ids: list[str]
    case_results: list[CaseSummary]
    all_pass: bool
    keep_last: int
    pruned_checkpoint_ids: list[str] = field(default_factory=list)
    exit_code: int = 0
    notes: str | None = None
    triage_filter: list[str] | None = None

    def to_data(self) -> dict[str, Any]:
        """Project the run result into the supported envelope ``data`` shape."""
        payload: dict[str, Any] = {
            "status": self.status,
            "mode": self.mode,
            "suite_id": self.suite_id,
            "experiment_id": self.experiment_id,
            "checkpoint_id": self.checkpoint_id,
            "compat_hash": self.compat_hash,
            "completed_case_ids": list(self.completed_case_ids),
            "pending_case_ids": list(self.pending_case_ids),
            "case_results": [c.to_dict() for c in self.case_results],
            "all_pass": self.all_pass,
            "keep_last": self.keep_last,
        }
        if self.parent_experiment_id is not None:
            payload["parent_experiment_id"] = self.parent_experiment_id
        if self.pruned_checkpoint_ids:
            payload["pruned_checkpoint_ids"] = list(self.pruned_checkpoint_ids)
        if self.triage_filter is not None:
            payload["triage_filter"] = list(self.triage_filter)
            payload["triage_only"] = True
        if self.notes:
            payload["notes"] = self.notes
        return payload


def _safe_id(prefix: str) -> str:
    """Mint a filesystem-safe identifier with the given prefix."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _resolve_repo(req: RunRequest) -> Path:
    """Resolve a path/id against the governed store root (containment-checked)."""
    if req.repo_root is not None:
        return Path(req.repo_root).resolve()
    try:
        return resolve_repo_root()
    except Exception as exc:  # RepoRootUnresolvedError
        raise RunOrchestratorError(
            f"repo root unresolved: {exc}",
            code="EVAL_CHECKPOINT_IO",
            exit_code=4,
        ) from exc


def _network_policy_from_suite(prepared: PreparedSuite, fallback: str) -> str:
    """Derive offline/network policy tokens from the prepared suite."""
    meta = prepared.suite_doc.get("meta") if isinstance(prepared.suite_doc.get("meta"), dict) else {}
    value = meta.get("network_policy") if isinstance(meta, dict) else None
    text = str(value or fallback).strip()
    return text or fallback


def _live_compat_hash(prepared: PreparedSuite, req: RunRequest) -> str:
    """Compute the live compat hash used for resume integrity."""
    return compute_compat_hash(
        schema_pack_pin=schema_pack_pin(),
        metric_catalog_pin=metric_catalog_pin(),
        suite_id=prepared.suite_id,
        snapshot_hash=prepared.suite_snapshot_pin,
        gold_mode=req.gold_mode,
        network_policy=_network_policy_from_suite(prepared, req.network_policy),
        judge_pack_pin_or_none=req.judge_pack_pin,
    )


def _failed_metrics(case: ScoreCaseResult) -> list[str]:
    """List metric ids that failed on a scored case."""
    failed: list[str] = []
    for row in case.all_results:
        if row.passed is False:
            failed.append(row.metric_id)
    return failed


def _summarize(case: ScoreCaseResult) -> CaseSummary:
    """Collapse a scored case into the compact run summary shape."""
    return CaseSummary(
        case_id=case.case_id,
        deterministic_pass=case.deterministic_pass,
        failed_metric_ids=_failed_metrics(case),
    )


def _case_result_path(repo: Path, experiment_id: str, case_id: str) -> Path:
    """Resolve the on-disk path for one experiment case result."""
    if not _SAFE.fullmatch(experiment_id):
        raise RunOrchestratorError(
            f"invalid experiment_id: {experiment_id!r}",
            code="EVAL_USAGE",
            exit_code=2,
        )
    safe_case = re.sub(r"[^A-Za-z0-9._:-]+", "_", case_id).strip("._") or "case"
    return experiments_dir(repo) / experiment_id / "cases" / f"{safe_case}.json"


def _write_case_result(repo: Path, experiment_id: str, case: ScoreCaseResult) -> Path:
    """Persist a governed artifact via atomic write (fail closed)."""
    payload = {
        "schema_version": "local_case_score_v0",
        "experiment_id": experiment_id,
        "case_id": case.case_id,
        "deterministic_pass": case.deterministic_pass,
        "suite_snapshot_pin": case.suite_snapshot_pin,
        "evaluator_errors": list(case.evaluator_errors),
        "scores": [s.model_dump(mode="json") for s in case.scores],
        "gates": [g.model_dump(mode="json") for g in case.gates],
        "failed_metric_ids": _failed_metrics(case),
    }
    try:
        return atomic_write_json(_case_result_path(repo, experiment_id, case.case_id), payload)
    except LayerAPathError as exc:
        raise RunOrchestratorError(str(exc), code="EVAL_CHECKPOINT_IO", exit_code=4) from exc


def _load_parent_experiment(repo: Path, parent_experiment_id: str) -> dict[str, Any]:
    """Load parent experiment.json or fail closed (exit 4)."""
    parent = str(parent_experiment_id or "").strip()
    if not parent or not _SAFE.fullmatch(parent):
        raise RunOrchestratorError(
            f"invalid parent experiment_id: {parent_experiment_id!r}",
            code="EVAL_USAGE",
            exit_code=2,
        )
    path = experiments_dir(repo) / parent / "experiment.json"
    if not path.is_file():
        raise RunOrchestratorError(
            f"recompute parent experiment not found: {parent}",
            code="EVAL_EVIDENCE_MISSING",
            exit_code=4,
            hint="Pass an existing local experiment id that retains evidence/results.",
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RunOrchestratorError(
            f"unreadable parent experiment {parent}: {exc}",
            code="EVAL_CHECKPOINT_IO",
            exit_code=4,
        ) from exc
    if not isinstance(raw, dict):
        raise RunOrchestratorError(
            f"parent experiment {parent} is not a JSON object",
            code="EVAL_CHECKPOINT_IO",
            exit_code=4,
        )
    return raw


def _score_history_for_child(
    parent_record: Mapping[str, Any] | None,
    *,
    parent_experiment_id: str | None,
    child_experiment_id: str,
    mode: RunMode,
    at: str,
) -> list[dict[str, Any]]:
    """Append-only score history: retain parent chain, never rewrite prior rows."""
    history: list[dict[str, Any]] = []
    if parent_record is not None:
        parent_meta = parent_record.get("meta") if isinstance(parent_record.get("meta"), dict) else {}
        prior = parent_meta.get("score_history") if isinstance(parent_meta, dict) else None
        if isinstance(prior, list):
            for item in prior:
                if isinstance(item, dict):
                    history.append(dict(item))
        elif parent_experiment_id:
            history.append(
                {
                    "experiment_id": parent_experiment_id,
                    "role": "parent",
                    "mode": str(parent_record.get("resume_mode") or "fresh_suite_run"),
                }
            )
    elif parent_experiment_id:
        history.append(
            {
                "experiment_id": parent_experiment_id,
                "role": "parent",
                "mode": "unknown",
            }
        )
    history.append(
        {
            "experiment_id": child_experiment_id,
            "role": "recompute" if mode == "recompute_scores" else "run",
            "mode": mode,
            "at": at,
            "parent_experiment_id": parent_experiment_id,
        }
    )
    return history


def _write_experiment_record(
    repo: Path,
    *,
    experiment: dict[str, Any],
    suite_id: str,
    snapshot_id: str,
    compat_hash: str,
    mode: RunMode,
    checkpoint_id: str | None,
    parent_experiment_id: str | None,
    started_at: str,
    finished_at: str | None = None,
    parent_record: Mapping[str, Any] | None = None,
) -> Path:
    """Persist a governed artifact via atomic write (fail closed)."""
    from git_cg.eval.schema_pack import SchemaPackError, validate_instance

    record = dict(experiment)
    record["suite_id"] = suite_id
    record["snapshot_id"] = snapshot_id
    record["compat_hash"] = compat_hash
    record["resume_mode"] = mode
    if checkpoint_id:
        record["checkpoint_id"] = checkpoint_id
    record["started_at"] = started_at
    if finished_at:
        record["finished_at"] = finished_at
    meta = dict(record.get("meta") or {})
    if parent_experiment_id:
        meta["parent_experiment_id"] = parent_experiment_id
    meta["score_history"] = _score_history_for_child(
        parent_record,
        parent_experiment_id=parent_experiment_id,
        child_experiment_id=str(record["id"]),
        mode=mode,
        at=started_at,
    )
    meta["score_history_policy"] = "append_only"
    # Keep pins authoritative under meta.pins when present.
    record["meta"] = meta
    try:
        validate_instance("experiment_v1", record)
    except SchemaPackError as exc:
        raise RunOrchestratorError(
            f"invalid experiment record: {exc}",
            code="EVAL_CHECKPOINT_IO",
            exit_code=4,
        ) from exc
    path = experiments_dir(repo) / str(record["id"]) / "experiment.json"
    try:
        return atomic_write_json(path, record)
    except LayerAPathError as exc:
        raise RunOrchestratorError(str(exc), code="EVAL_CHECKPOINT_IO", exit_code=4) from exc


def _mint_experiment(
    repo: Path,
    *,
    suite_id: str,
    snapshot_id: str,
    mode: RunMode,
    parent_experiment_id: str | None = None,
) -> dict[str, Any]:
    """Mint a new governed experiment/export identity."""
    meta: dict[str, Any] = {"suite_id": suite_id, "resume_mode": mode}
    if parent_experiment_id:
        meta["parent_experiment_id"] = parent_experiment_id
    # content_key forces unique experiment ids even within the same UTC second
    # (recompute child must not collide with parent).
    content_key = "|".join(
        [
            mode,
            suite_id,
            snapshot_id or "",
            parent_experiment_id or "",
            uuid.uuid4().hex,
        ]
    )
    return build_experiment(
        lane="suite",
        catalog_version="v0",
        repo_root=repo,
        network_export=False,
        suite_snapshot=snapshot_id,
        artifact_class="fixture",
        meta=meta,
        content_key=content_key,
    )


def _filter_workset(
    prepared: PreparedSuite,
    *,
    pending: Sequence[str] | None,
    case_filter: Sequence[str] | None,
) -> list[tuple[str, dict[str, Any]]]:
    """Filter a workset by operator selectors without mutating authority."""
    pairs = list(prepared.encoded_pairs)
    if pending is not None:
        pending_set = set(pending)
        pairs = [(c, b) for c, b in pairs if c in pending_set]
    if case_filter is not None:
        wanted = set(case_filter)
        pairs = [(c, b) for c, b in pairs if c in wanted]
    return pairs


def _score_one(
    prepared: PreparedSuite,
    *,
    case_id: str,
    bundle: dict[str, Any],
    req: RunRequest,
) -> ScoreCaseResult:
    """Project or compute score rows used by operator surfaces (not product accept)."""
    if req.enable_lane_c:
        raise RunOrchestratorError(
            "Lane C attachments are not enabled on the default suite-run path",
            code="EVAL_USAGE",
            exit_code=2,
            hint="Omit Lane C flags; dogfood/lane_c land in later slices.",
        )
    return score_bundle(
        bundle,
        suite=prepared.suite_doc,
        suite_snapshot_pin=prepared.suite_snapshot_pin,
        require_block=prepared.require_block,
        require_topology=prepared.require_topology,
        session_thread_index=prepared.session_thread_index,
        gold_mode=req.gold_mode,
        offline=req.offline,
        case_id=case_id,
        enable_lane_c=False,
    )


def _persist_checkpoint(
    repo: Path,
    *,
    checkpoint_id: str,
    experiment_id: str,
    compat_hash: str,
    completed: list[str],
    pending: list[str],
    mode: RunMode,
    suite_id: str,
    snapshot_id: str,
    started_at: str,
    status: str,
) -> dict[str, Any]:
    """Persist a governed intermediate artifact for resume/audit."""
    cursor = pending[0] if pending else (completed[-1] if completed else "")
    record = build_checkpoint_record(
        checkpoint_id=checkpoint_id,
        experiment_id=experiment_id,
        compat_hash=compat_hash,
        completed_case_ids=completed,
        pending_case_ids=pending,
        mode=mode,
        last_progress_at=utc_now_iso(),
        suite_id=suite_id,
        snapshot_id=snapshot_id,
        schema_pack=schema_pack_pin(),
        metric_catalog=metric_catalog_pin(),
        cursor=cursor or None,
    )
    write_checkpoint(repo, record, started_at=started_at, status=status)  # type: ignore[arg-type]
    return record


def _load_prior_case_summaries(repo: Path, experiment_id: str, case_ids: Sequence[str]) -> list[CaseSummary]:
    """Load a governed artifact from the Layer-A store (fail closed)."""
    out: list[CaseSummary] = []
    for cid in case_ids:
        path = _case_result_path(repo, experiment_id, cid)
        if not path.is_file():
            out.append(CaseSummary(case_id=cid, deterministic_pass=None, failed_metric_ids=[]))
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            out.append(CaseSummary(case_id=cid, deterministic_pass=None, failed_metric_ids=[]))
            continue
        out.append(
            CaseSummary(
                case_id=cid,
                deterministic_pass=raw.get("deterministic_pass"),
                failed_metric_ids=[str(x) for x in (raw.get("failed_metric_ids") or [])],
            )
        )
    return out


def _evidence_bundles_for_recompute(
    repo: Path,
    prepared: PreparedSuite,
    *,
    parent_experiment_id: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Return (case_id → bundle, parent_experiment_record) for recompute.

    Fail closed when the parent experiment is missing/unreadable.

    Evidence sources (in order):
    1. Encoded fixture bundles from the prepared suite (offline default)
    2. Accept-path bundles under ``.eval/bundles/acceptpath/`` when present

    Recompute never regenerates bundles implicitly (that is replay_generation).
    """
    parent_record = _load_parent_experiment(repo, parent_experiment_id)

    # Parent case score artifacts must remain readable (append-only law).
    parent_cases = experiments_dir(repo) / parent_experiment_id / "cases"
    if parent_cases.is_dir():
        # Presence is enough; we do not mutate parent case files.
        _ = list(parent_cases.glob("*.json"))

    bundles = {cid: bundle for cid, bundle in prepared.encoded_pairs}
    if bundles:
        return bundles, parent_record

    # Fallback: accept-path store (live evidence) when fixtures are unavailable.
    root = acceptpath_bundles_dir(repo)
    if root.is_dir():
        for path in root.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except OSError, json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            cid = str(payload.get("case_id") or path.stem)
            bundles[cid] = payload
    if not bundles:
        raise RunOrchestratorError(
            f"recompute evidence missing for experiment {parent_experiment_id}",
            code="EVAL_EVIDENCE_MISSING",
            exit_code=4,
            hint="Retain fixture bundles or Layer-A accept-path bundles before recompute_scores.",
        )
    return bundles, parent_record


def _finalize_gc(
    repo: Path,
    *,
    suite_id: str,
    keep_last: int,
    keep_checkpoint: bool,
    checkpoint_id: str | None,
    status: str,
) -> list[str]:
    """Run terminal GC/finalization for a completed run."""
    protect: list[str] = []
    if keep_checkpoint and checkpoint_id:
        protect.append(checkpoint_id)
    if status != "completed" and checkpoint_id:
        # Failed/running: retain this run's checkpoint regardless of age.
        protect.append(checkpoint_id)
    try:
        return prune_checkpoints(
            repo,
            suite_id=suite_id,
            keep_last=keep_last,
            protect_ids=protect,
        )
    except CheckpointStoreError as exc:
        raise RunOrchestratorError(str(exc), code=exc.code, exit_code=4) from exc


def _run_export_only(req: RunRequest, repo: Path) -> RunResult:
    """export_only never scores and never creates checkpoints."""
    exp_id = (req.experiment_id or "").strip()
    if not exp_id:
        raise RunOrchestratorError(
            "export_only requires --experiment <id> with local results present",
            code="EVAL_USAGE",
            exit_code=2,
            hint="Provide an existing local experiment id; export_only never scores.",
        )
    exp_path = experiments_dir(repo) / exp_id / "experiment.json"
    cases_dir = experiments_dir(repo) / exp_id / "cases"
    if not exp_path.is_file():
        raise RunOrchestratorError(
            f"export_only: local experiment not found: {exp_id}",
            code="EVAL_EVIDENCE_MISSING",
            exit_code=4,
            hint="export_only projects existing local results only.",
        )
    case_files = sorted(cases_dir.glob("*.json")) if cases_dir.is_dir() else []
    summaries: list[CaseSummary] = []
    for path in case_files:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            continue
        summaries.append(
            CaseSummary(
                case_id=str(raw.get("case_id") or path.stem),
                deterministic_pass=raw.get("deterministic_pass"),
                failed_metric_ids=[str(x) for x in (raw.get("failed_metric_ids") or [])],
            )
        )
    all_pass = bool(summaries) and all(s.deterministic_pass is True for s in summaries)
    return RunResult(
        status="completed" if summaries else "failed",
        mode="export_only",
        suite_id=req.suite_id,
        experiment_id=exp_id,
        parent_experiment_id=None,
        checkpoint_id=None,
        compat_hash="",
        completed_case_ids=[s.case_id for s in summaries],
        pending_case_ids=[],
        case_results=summaries,
        all_pass=all_pass,
        keep_last=req.keep_last,
        exit_code=0 if summaries else 1,
        notes="export_only: no scoring; no checkpoint created; local projection only",
    )


def run_evaluation(req: RunRequest) -> RunResult:
    """Execute one governed suite mode and return a CLI-ready result."""
    if req.enable_dogfood:
        raise RunOrchestratorError(
            "dogfood attachments are off by default on suite run",
            code="EVAL_USAGE",
            exit_code=2,
        )
    if req.mode == "replay_generation" and not req.allow_replay_generation:
        raise RunOrchestratorError(
            "replay_generation is flag-gated and refused by default offline",
            code="EVAL_USAGE",
            exit_code=2,
            hint="Pass an explicit allow flag only when network policy permits live regen.",
        )
    if req.mode == "replay_generation":
        raise RunOrchestratorError(
            "replay_generation live regen is not implemented in Slice 3 offline path",
            code="EVAL_CLI_NOT_IMPLEMENTED",
            exit_code=2,
            hint="Use fresh_suite_run offline or wait for the gated regen path.",
        )

    repo = _resolve_repo(req)

    if req.mode == "export_only":
        return _run_export_only(req, repo)

    try:
        prepared = prepare_suite_cases(
            req.suite_id,
            fixture_root=req.fixture_root,
        )
    except Exception as exc:
        raise RunOrchestratorError(
            f"invalid suite/fixture selection: {exc}",
            code="EVAL_USAGE",
            exit_code=2,
        ) from exc

    # recompute_scores may fall back to accept-path bundles when fixtures are empty.
    if not prepared.encoded_pairs and req.mode != "recompute_scores":
        raise RunOrchestratorError(
            f"suite {prepared.suite_id!r} has no cases",
            code="EVAL_USAGE",
            exit_code=2,
        )

    started_at = utc_now_iso()
    live_hash = _live_compat_hash(prepared, req)
    parent_experiment_id: str | None = None
    checkpoint_id: str | None = None
    experiment_id: str
    completed: list[str] = []
    pending: list[str] = [cid for cid, _ in prepared.encoded_pairs]
    prior_summaries: list[CaseSummary] = []
    mode: RunMode = req.mode

    if mode == "resume_missing":
        if not req.checkpoint_id:
            raise RunOrchestratorError(
                "resume_missing requires --checkpoint",
                code="EVAL_USAGE",
                exit_code=2,
            )
        try:
            ckpt = load_checkpoint(repo, req.checkpoint_id)
        except CheckpointStoreError as exc:
            raise RunOrchestratorError(str(exc), code=exc.code, exit_code=4) from exc
        checkpoint_id = str(ckpt["checkpoint_id"])
        try:
            assert_compat_hash(str(ckpt["compat_hash"]), live_hash, checkpoint_id=checkpoint_id)
        except CompatHashMismatchError as exc:
            raise RunOrchestratorError(
                str(exc),
                code=COMPAT_HASH_MISMATCH_CODE,
                exit_code=3,
                hint=exc.recovery_hint(),
                data={
                    "checkpoint_id": checkpoint_id,
                    "expected_compat_hash": exc.expected,
                    "actual_compat_hash": exc.actual,
                    "preserved_read_only": True,
                },
            ) from exc
        experiment_id = str(ckpt["experiment_id"])
        completed = [str(x) for x in ckpt.get("completed_case_ids") or []]
        pending = [str(x) for x in ckpt.get("pending_case_ids") or []]
        if not pending:
            # Nothing left — treat as completed resume no-op.
            summaries = _load_prior_case_summaries(repo, experiment_id, completed)
            all_pass = bool(summaries) and all(s.deterministic_pass is True for s in summaries)
            return RunResult(
                status="completed" if all_pass else "failed",
                mode=mode,
                suite_id=prepared.suite_id,
                experiment_id=experiment_id,
                parent_experiment_id=None,
                checkpoint_id=checkpoint_id,
                compat_hash=live_hash,
                completed_case_ids=completed,
                pending_case_ids=[],
                case_results=summaries,
                all_pass=all_pass,
                keep_last=req.keep_last,
                exit_code=0 if all_pass else 1,
            )
        prior_summaries = _load_prior_case_summaries(repo, experiment_id, completed)
        work = _filter_workset(prepared, pending=pending, case_filter=req.case_ids)

    elif mode == "recompute_scores":
        parent = (req.experiment_id or "").strip()
        if not parent:
            raise RunOrchestratorError(
                "recompute_scores requires --experiment <parent_id>",
                code="EVAL_USAGE",
                exit_code=2,
            )
        parent_experiment_id = parent
        # Evidence preconditions: parent experiment + snapshot pin + packs + bundles.
        evidence_bundles, parent_record = _evidence_bundles_for_recompute(repo, prepared, parent_experiment_id=parent)
        if not prepared.suite_snapshot_pin:
            raise RunOrchestratorError(
                "recompute_scores requires suite snapshot pin",
                code="EVAL_EVIDENCE_MISSING",
                exit_code=4,
            )
        experiment = _mint_experiment(
            repo,
            suite_id=prepared.suite_id,
            snapshot_id=prepared.suite_snapshot_pin,
            mode=mode,
            parent_experiment_id=parent,
        )
        experiment_id = str(experiment["id"])
        checkpoint_id = _safe_id("ckpt")
        completed = []
        # Workset is the retained evidence set (fixtures or accept-path), not regen.
        pending = list(evidence_bundles.keys()) if evidence_bundles else [cid for cid, _ in prepared.encoded_pairs]
        if req.case_ids is not None:
            wanted = set(req.case_ids)
            pending = [cid for cid in pending if cid in wanted]
        # Prefer prepared fixture pairs when present; else accept-path map.
        if prepared.encoded_pairs:
            work = _filter_workset(prepared, pending=pending, case_filter=req.case_ids)
        else:
            work = [(cid, evidence_bundles[cid]) for cid in pending if cid in evidence_bundles]
        if not work:
            raise RunOrchestratorError(
                f"recompute_scores has no scorable cases for experiment {parent}",
                code="EVAL_EVIDENCE_MISSING",
                exit_code=4,
            )
        _write_experiment_record(
            repo,
            experiment=experiment,
            suite_id=prepared.suite_id,
            snapshot_id=prepared.suite_snapshot_pin,
            compat_hash=live_hash,
            mode=mode,
            checkpoint_id=checkpoint_id,
            parent_experiment_id=parent,
            started_at=started_at,
            parent_record=parent_record,
        )

    elif mode == "fresh_suite_run":
        experiment = _mint_experiment(
            repo,
            suite_id=prepared.suite_id,
            snapshot_id=prepared.suite_snapshot_pin,
            mode=mode,
        )
        experiment_id = str(experiment["id"])
        checkpoint_id = _safe_id("ckpt")
        completed = []
        pending = [cid for cid, _ in prepared.encoded_pairs]
        work = _filter_workset(prepared, pending=None, case_filter=req.case_ids)
        # If triage filter applied, pending becomes the filtered workset only.
        if req.case_ids is not None:
            pending = [cid for cid, _ in work]
        _write_experiment_record(
            repo,
            experiment=experiment,
            suite_id=prepared.suite_id,
            snapshot_id=prepared.suite_snapshot_pin,
            compat_hash=live_hash,
            mode=mode,
            checkpoint_id=checkpoint_id,
            parent_experiment_id=None,
            started_at=started_at,
        )
    else:
        raise RunOrchestratorError(
            f"unsupported mode: {mode}",
            code="EVAL_USAGE",
            exit_code=2,
        )

    # Initial checkpoint (fresh/recompute) or refresh (resume).
    assert checkpoint_id is not None
    try:
        _persist_checkpoint(
            repo,
            checkpoint_id=checkpoint_id,
            experiment_id=experiment_id,
            compat_hash=live_hash,
            completed=list(completed),
            pending=list(pending),
            mode=mode,
            suite_id=prepared.suite_id,
            snapshot_id=prepared.suite_snapshot_pin,
            started_at=started_at,
            status="running",
        )
    except CheckpointStoreError as exc:
        raise RunOrchestratorError(str(exc), code=exc.code, exit_code=4) from exc

    new_summaries: list[CaseSummary] = []
    remaining = [cid for cid, _ in work]
    try:
        for case_id, bundle in work:
            case = _score_one(prepared, case_id=case_id, bundle=bundle, req=req)
            _write_case_result(repo, experiment_id, case)
            summary = _summarize(case)
            new_summaries.append(summary)
            if case_id not in completed:
                completed.append(case_id)
            if case_id in remaining:
                remaining.remove(case_id)
            if case_id in pending:
                pending = [p for p in pending if p != case_id]
            _persist_checkpoint(
                repo,
                checkpoint_id=checkpoint_id,
                experiment_id=experiment_id,
                compat_hash=live_hash,
                completed=list(completed),
                pending=list(pending),
                mode=mode,
                suite_id=prepared.suite_id,
                snapshot_id=prepared.suite_snapshot_pin,
                started_at=started_at,
                status="running",
            )
    except RunOrchestratorError:
        _persist_checkpoint(
            repo,
            checkpoint_id=checkpoint_id,
            experiment_id=experiment_id,
            compat_hash=live_hash,
            completed=list(completed),
            pending=list(pending),
            mode=mode,
            suite_id=prepared.suite_id,
            snapshot_id=prepared.suite_snapshot_pin,
            started_at=started_at,
            status="failed",
        )
        raise
    except Exception as exc:
        _persist_checkpoint(
            repo,
            checkpoint_id=checkpoint_id,
            experiment_id=experiment_id,
            compat_hash=live_hash,
            completed=list(completed),
            pending=list(pending),
            mode=mode,
            suite_id=prepared.suite_id,
            snapshot_id=prepared.suite_snapshot_pin,
            started_at=started_at,
            status="failed",
        )
        raise RunOrchestratorError(
            f"suite run failed: {exc}",
            code="EVAL_SUITE_FAIL",
            exit_code=1,
        ) from exc

    summaries = [*prior_summaries, *new_summaries]
    # De-dupe by case_id preserving last write.
    by_id = {s.case_id: s for s in summaries}
    ordered_ids = list(completed)
    summaries = [by_id[c] for c in ordered_ids if c in by_id]

    all_pass = bool(summaries) and all(s.deterministic_pass is True for s in summaries)
    status: Literal["completed", "failed", "blocked"] = "completed" if all_pass else "failed"
    ckpt_status = "completed" if not pending else ("failed" if not all_pass else "running")
    # If workset finished (pending empty for this experiment scope), mark completed/failed.
    if not pending:
        ckpt_status = "completed" if all_pass else "failed"

    _persist_checkpoint(
        repo,
        checkpoint_id=checkpoint_id,
        experiment_id=experiment_id,
        compat_hash=live_hash,
        completed=list(completed),
        pending=list(pending),
        mode=mode,
        suite_id=prepared.suite_id,
        snapshot_id=prepared.suite_snapshot_pin,
        started_at=started_at,
        status=ckpt_status,
    )

    # Finalize experiment finished_at when terminal.
    exp_path = experiments_dir(repo) / experiment_id / "experiment.json"
    if exp_path.is_file() and ckpt_status in {"completed", "failed"}:
        try:
            from git_cg.eval.schema_pack import validate_instance

            exp_raw = json.loads(exp_path.read_text(encoding="utf-8"))
            if isinstance(exp_raw, dict):
                exp_raw["finished_at"] = utc_now_iso()
                validate_instance("experiment_v1", exp_raw)
                atomic_write_json(exp_path, exp_raw)
        except Exception:
            # Best-effort finalize; case scores + checkpoint remain authoritative.
            pass

    pruned: list[str] = []
    if ckpt_status in {"completed", "failed"}:
        pruned = _finalize_gc(
            repo,
            suite_id=prepared.suite_id,
            keep_last=req.keep_last,
            keep_checkpoint=req.keep_checkpoint,
            checkpoint_id=checkpoint_id,
            status=ckpt_status,
        )
        # Successful completed runs may drop their own checkpoint unless kept.
        if ckpt_status == "completed" and not req.keep_checkpoint and checkpoint_id and checkpoint_id not in pruned:
            # keep-last still retains recent history; do not force-delete current
            # beyond prune policy. Current remains as the newest completed row.
            pass

    exit_code = 0 if all_pass else 1
    return RunResult(
        status=status,
        mode=mode,
        suite_id=prepared.suite_id,
        experiment_id=experiment_id,
        parent_experiment_id=parent_experiment_id,
        checkpoint_id=checkpoint_id,
        compat_hash=live_hash,
        completed_case_ids=list(completed),
        pending_case_ids=list(pending),
        case_results=summaries,
        all_pass=all_pass,
        keep_last=req.keep_last,
        pruned_checkpoint_ids=pruned,
        exit_code=exit_code,
        triage_filter=list(req.case_ids) if req.case_ids is not None else None,
        notes=(
            "R9 case filter applied — triage/lab only; CI golden corpus remains full suite snapshot"
            if req.case_ids is not None
            else None
        ),
    )
