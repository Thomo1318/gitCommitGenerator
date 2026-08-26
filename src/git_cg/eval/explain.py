"""S6 Slice 5 deterministic explain / failures / compare engines (Issue #246).

§18.3 debug loop surfaces over landed Slice 3 Layer-A case results. These are
**read-only projections** — they never re-run scoring (RK-S6-12), never mutate
the store, and never emit opaque LLM RCA (FIND-020 forbidden behaviour).

Data source: ``.eval/experiments/<experiment_id>/cases/<case>.json`` rows of
schema ``local_case_score_v0`` written by the Slice 3 run orchestrator. Each row
carries full ``scores``/``gates`` (``metric_id``, ``failure_ids``, ``evidence``)
plus a precomputed ``failed_metric_ids`` list.

Family I rows already carry the sanitised N11 fingerprint substrate at
``evidence["diag_fingerprint_inputs"]``; this module surfaces those inputs but
never re-derives or re-hashes raw span names (RK-S6-09).

Import law: import-light. Heavier helpers (path law, schema validation) are
imported lazily inside functions so ``git_cg.eval.cli`` import stays clean and
offline tests never touch the network or Opik SDK.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from git_cg.eval.evidence_scrub import project_secret_safe

# Local case-result row schema written by ``run_orchestrator._write_case_result``.
CASE_RESULT_SCHEMA: Final[str] = "local_case_score_v0"

# Closed blame_span → suggested code-surface map (plan §18.4, FIND-021/INT-36).
# Static copy map only; never model output. Unknown/digested blame spans map to
# an empty surface list rather than guessing.
BLAME_SPAN_SURFACES: Final[dict[str, tuple[str, ...]]] = {
    "diff_extraction": ("diff collect / file summary modules",),
    "path_classification": ("path-class gate / intent path features",),
    "intent_ranking": ("intent.py / SOP ranker",),
    "contract_resolution": ("semantic contract selection",),
    "llm_generation": ("AI client / prompts / instructor",),
    "plan_normalisation": ("plan normaliser",),
    "gold_evaluation": ("commit_gold / gold report",),
    "presentation_guard": ("Hybrid/render guards",),
    "regeneration": ("regen loop / counters",),
    "fallback": ("skeleton/fallback paths",),
    "final_render": ("commit message render",),
    "accept_path_finalization": ("hooks / COMMIT_EDITMSG bind",),
    "opik_export": ("eval export / config",),
}


class ExplainError(ValueError):
    """Deterministic explain/compare/failures failure (fail-closed)."""

    def __init__(self, message: str, *, code: str, exit_code: int, hint: str | None = None) -> None:
        """Initialize structured error/context fields for operator engines."""
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code
        self.hint = hint


def _load_json(path: Path, *, code: str, exit_code: int, hint: str | None = None) -> dict[str, Any]:
    """Load one JSON object row; fail closed on unreadable/invalid payload."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ExplainError(
            f"cannot read {path.name}: {exc}",
            code=code,
            exit_code=exit_code,
            hint=hint,
        ) from exc
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ExplainError(
            f"{path.name} is not valid JSON: {exc}",
            code=code,
            exit_code=exit_code,
            hint=hint,
        ) from exc
    if not isinstance(obj, dict):
        raise ExplainError(
            f"{path.name} must contain a JSON object",
            code=code,
            exit_code=exit_code,
            hint=hint,
        )
    return obj


def _experiments_dir(repo: Path) -> Path:
    """Resolve the contained experiments dir (lazy import; N19.3 law)."""
    from git_cg.eval.binding.paths import LayerAPathError, experiments_dir

    try:
        return experiments_dir(repo)
    except LayerAPathError as exc:
        raise ExplainError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc


def _iter_experiment_ids(repo: Path) -> list[str]:
    """Return experiment ids (dir names), newest directory first."""
    root = _experiments_dir(repo)
    if not root.is_dir():
        return []
    ids = [p.name for p in root.iterdir() if p.is_dir() and (p / "experiment.json").is_file()]
    # Deterministic, newest-first by directory mtime then name (read-only).
    ids.sort(key=lambda n: (root / n).stat().st_mtime if (root / n).exists() else 0.0, reverse=True)
    return ids


def _load_experiment_record(repo: Path, experiment_id: str) -> dict[str, Any]:
    """Load a governed artifact from the Layer-A store (fail closed)."""
    path = _experiments_dir(repo) / experiment_id / "experiment.json"
    if not path.is_file():
        raise ExplainError(
            f"experiment not found: {experiment_id!r}",
            code="EVAL_USAGE",
            exit_code=2,
            hint="Provide a valid experiment id from `git-cg eval failures` / suite run output.",
        )
    return _load_json(
        path,
        code="EVAL_STORE_INTEGRITY",
        exit_code=4,
        hint="The experiment record under .eval/experiments/ is corrupt.",
    )


def _iter_case_results(repo: Path, experiment_id: str) -> list[dict[str, Any]]:
    """Load all ``local_case_score_v0`` rows for one experiment (sorted by case)."""
    cases_root = _experiments_dir(repo) / experiment_id / "cases"
    if not cases_root.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(cases_root.glob("*.json")):
        obj = _load_json(
            path,
            code="EVAL_STORE_INTEGRITY",
            exit_code=4,
            hint="A case result under .eval/experiments/ is corrupt; inspect or rebuild.",
        )
        if obj.get("schema_version") != CASE_RESULT_SCHEMA:
            raise ExplainError(
                f"{path.name} has unexpected schema_version {obj.get('schema_version')!r}",
                code="EVAL_STORE_INTEGRITY",
                exit_code=4,
                hint="Only local_case_score_v0 rows are readable by this command.",
            )
        rows.append(obj)
    rows.sort(key=lambda r: str(r.get("case_id") or ""))
    return rows


def _resolve_experiment_and_case(
    repo: Path,
    *,
    experiment_id: str | None,
    case_id: str | None,
) -> tuple[str, list[dict[str, Any]]]:
    """Resolve target experiment (latest when omitted) + case rows."""
    exp = experiment_id
    if not exp:
        ids = _iter_experiment_ids(repo)
        if not ids:
            raise ExplainError(
                "no local experiment runs found",
                code="EVAL_USAGE",
                exit_code=2,
                hint="Run `git-cg eval run` first to produce Layer-A case results.",
            )
        exp = ids[0]
    cases = _iter_case_results(repo, exp)
    if case_id is not None:
        cases = [c for c in cases if str(c.get("case_id")) == case_id]
        if not cases:
            raise ExplainError(
                f"case not found in experiment {exp!r}: {case_id!r}",
                code="EVAL_USAGE",
                exit_code=2,
                hint="Pass a case_id present in the experiment's case results.",
            )
    return exp, cases


def _failing_metric_rows(case: dict[str, Any]) -> list[dict[str, Any]]:
    """Return failing score rows (passed=False) with ids + fingerprint inputs."""
    out: list[dict[str, Any]] = []
    for row in case.get("scores") or []:
        if not isinstance(row, dict):
            continue
        passed = row.get("passed")
        if passed is False:
            evidence = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
            out.append(
                {
                    "metric_id": row.get("metric_id"),
                    "reason": row.get("reason"),
                    "failure_ids": list(row.get("failure_ids") or []),
                    "diag_fingerprint_inputs": evidence.get("diag_fingerprint_inputs"),
                }
            )
    return out


_ALLOWED_SEVERITIES: Final[frozenset[str]] = frozenset({"block", "warn", "info"})


def _case_failing_score_rows(case: dict[str, Any]) -> list[dict[str, Any]]:
    """Return full failing score rows (passed is False) from a case result."""
    out: list[dict[str, Any]] = []
    for row in case.get("scores") or []:
        if isinstance(row, dict) and row.get("passed") is False:
            out.append(row)
    return out


def _metric_family(metric_id: str | None) -> str | None:
    """Derive catalog family letter/token from a metric_id prefix (a.* → A)."""
    if not metric_id or not isinstance(metric_id, str):
        return None
    head = metric_id.split(".", 1)[0].strip()
    if not head:
        return None
    # Catalog uses single-letter families plus a few tokens (gate/human/lab/...).
    if len(head) == 1:
        return head.upper()
    return head.lower()


def _row_regime(row: dict[str, Any]) -> str | None:
    """Project one row field used by filter/export classification."""
    evidence = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
    fp = evidence.get("diag_fingerprint_inputs") if isinstance(evidence.get("diag_fingerprint_inputs"), dict) else {}
    regime = fp.get("regime")
    if isinstance(regime, str) and regime.strip():
        return regime.strip()
    return None


def _row_severity(row: dict[str, Any]) -> str | None:
    """Project one row field used by filter/export classification."""
    sev = row.get("severity")
    if isinstance(sev, str) and sev.strip():
        return sev.strip().lower()
    evidence = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
    sev2 = evidence.get("severity")
    if isinstance(sev2, str) and sev2.strip():
        return sev2.strip().lower()
    return None


def _row_family(row: dict[str, Any]) -> str | None:
    """Project one row field used by filter/export classification."""
    fam = row.get("family")
    if isinstance(fam, str) and fam.strip():
        token = fam.strip()
        return token.upper() if len(token) == 1 else token.lower()
    return _metric_family(str(row.get("metric_id") or "") or None)


def _normalize_filter_token(value: str | None, *, field: str) -> str | None:
    """Normalize operator/input tokens into the closed vocabulary form."""
    if value is None:
        return None
    token = value.strip()
    if not token:
        raise ExplainError(
            f"empty {field} filter",
            code="EVAL_USAGE",
            exit_code=2,
            hint=f"Pass a non-empty --{field.replace('_', '-')} value.",
        )
    return token


def list_failures(
    repo: Path,
    *,
    experiment_id: str | None = None,
    regime: str | None = None,
    family: str | None = None,
    failure_id: str | None = None,
    severity: str | None = None,
) -> dict[str, Any]:
    """§18.3 ``eval failures``: failing cases with metric_ids + failure_ids.

    Optional deterministic filters (NTH-02) are AND-combined across dimensions.
    A case is kept when at least one failing score row matches every provided
    filter. When filters are active, ``metric_ids`` / ``failure_ids`` project the
    matching failing-score subset (not the unfiltered case union).
    """
    regime_f = _normalize_filter_token(regime, field="regime")
    family_raw = _normalize_filter_token(family, field="family")
    failure_f = _normalize_filter_token(failure_id, field="failure-id")
    severity_f = _normalize_filter_token(severity, field="severity")

    family_f: str | None = None
    if family_raw is not None:
        family_f = family_raw.upper() if len(family_raw) == 1 else family_raw.lower()

    if severity_f is not None and severity_f.lower() not in _ALLOWED_SEVERITIES:
        raise ExplainError(
            f"invalid severity filter: {severity!r}",
            code="EVAL_USAGE",
            exit_code=2,
            hint=f"Allowed: {sorted(_ALLOWED_SEVERITIES)}",
        )
    if severity_f is not None:
        severity_f = severity_f.lower()

    exp = experiment_id
    if not exp:
        ids = _iter_experiment_ids(repo)
        if not ids:
            return {
                "experiment_id": None,
                "failing_cases": [],
                "case_count": 0,
                "filters": {
                    "regime": regime_f,
                    "family": family_f,
                    "failure_id": failure_f,
                    "severity": severity_f,
                },
            }
        exp = ids[0]
    cases = _iter_case_results(repo, exp)
    failing: list[dict[str, Any]] = []
    for case in cases:
        if case.get("deterministic_pass") is True:
            continue
        score_rows = _case_failing_score_rows(case)
        # Fallback projection path when scores[] is empty but failed_metric_ids set.
        if not score_rows and case.get("failed_metric_ids"):
            score_rows = [
                {
                    "metric_id": mid,
                    "passed": False,
                    "failure_ids": [],
                    "family": _metric_family(str(mid)),
                }
                for mid in case.get("failed_metric_ids") or []
            ]

        matched_rows: list[dict[str, Any]] = []
        for row in score_rows:
            if regime_f is not None and _row_regime(row) != regime_f:
                continue
            if family_f is not None and _row_family(row) != family_f:
                continue
            if severity_f is not None and _row_severity(row) != severity_f:
                continue
            fids = [str(x) for x in (row.get("failure_ids") or [])]
            if failure_f is not None and failure_f not in fids:
                continue
            matched_rows.append(row)

        # When no filters are set, keep the legacy unfiltered failing-case shape
        # even if score rows are sparse (use failed_metric_ids fallback).
        filters_active = any(v is not None for v in (regime_f, family_f, failure_f, severity_f))
        if filters_active and not matched_rows:
            continue
        if not filters_active:
            failing_metrics = _failing_metric_rows(case)
            metric_ids = sorted({str(m["metric_id"]) for m in failing_metrics if m.get("metric_id")})
            failure_ids = sorted({fid for m in failing_metrics for fid in (m.get("failure_ids") or [])})
            out_metric_ids = metric_ids or list(case.get("failed_metric_ids") or [])
            out_failure_ids = failure_ids
        else:
            out_metric_ids = sorted({str(r.get("metric_id")) for r in matched_rows if r.get("metric_id")})
            out_failure_ids = sorted({str(fid) for r in matched_rows for fid in (r.get("failure_ids") or []) if fid})

        failing.append(
            {
                "case_id": case.get("case_id"),
                "deterministic_pass": bool(case.get("deterministic_pass")),
                "metric_ids": out_metric_ids,
                "failure_ids": out_failure_ids,
                "evaluator_errors": list(case.get("evaluator_errors") or []),
            }
        )
    return project_secret_safe(
        {
            "experiment_id": exp,
            "failing_cases": failing,
            "case_count": len(failing),
            "filters": {
                "regime": regime_f,
                "family": family_f,
                "failure_id": failure_f,
                "severity": severity_f,
            },
        }
    )


def _headers(experiment_record: dict[str, Any]) -> dict[str, Any]:
    """INT-29 report headers pulled from the experiment record pins/meta."""
    meta = experiment_record.get("meta") if isinstance(experiment_record.get("meta"), dict) else {}
    pins = meta.get("pins") if isinstance(meta.get("pins"), dict) else {}
    return {
        "project_lane": pins.get("project_lane"),
        "environment": pins.get("environment"),
        "export_status": meta.get("export_status"),
        "redaction_profile": pins.get("redaction_profile"),
        "schema_pack_hash": experiment_record.get("schema_pack") or pins.get("schema_pack"),
        "metric_catalog_hash": experiment_record.get("metric_catalog") or pins.get("metric_catalog"),
        "harness_version": pins.get("harness_version"),
    }


def _explain_one(case: dict[str, Any], experiment_record: dict[str, Any]) -> dict[str, Any]:
    """§18.3 deterministic explain contract for one case result."""
    failing = _failing_metric_rows(case)
    metric_ids = sorted({str(m["metric_id"]) for m in failing if m.get("metric_id")})
    failure_ids = sorted({fid for m in failing for fid in (m.get("failure_ids") or [])})

    blame_span: str | None = None
    first_divergent_span: str | None = None
    artifact_class: str | None = None
    prevention_ids: list[str] = []
    topology_missing_spans: list[str] = []
    counter_span_consistent: bool | None = None
    scored_field_source: str | None = None

    for m in failing:
        fp = m.get("diag_fingerprint_inputs")
        if not isinstance(fp, dict):
            continue
        blame_span = blame_span or fp.get("blame_span")
        first_divergent_span = first_divergent_span or fp.get("first_divergent_span")
        artifact_class = artifact_class or fp.get("artifact_class")
        if not topology_missing_spans and fp.get("missing_required_spans"):
            topology_missing_spans = list(fp.get("missing_required_spans") or [])

    # prevention_ids only ever render when present on source evidence (§18.3 law:
    # never fabricate). Format-metric scored-field source surfaces when present.
    for row in case.get("scores") or []:
        if not isinstance(row, dict):
            continue
        evidence = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
        if isinstance(evidence.get("prevention_ids"), list):
            prevention_ids.extend(str(p) for p in evidence["prevention_ids"])
        if scored_field_source is None and isinstance(evidence.get("scored_field_source"), str):
            scored_field_source = evidence["scored_field_source"]
        if counter_span_consistent is None and row.get("metric_id") == "i.counter_span_consistent":
            counter_span_consistent = bool(row.get("passed"))

    experiment_id = str(experiment_record.get("id") or case.get("experiment_id") or "")
    case_id = str(case.get("case_id") or "")
    replay_command = (
        f"git-cg eval replay --experiment-id {experiment_id} --case {case_id}"
        if experiment_id and case_id
        else "git-cg eval replay <bundle>"
    )
    bundle_path = str(case.get("case_id") or "")

    surfaces: list[str] = []
    if blame_span and blame_span in BLAME_SPAN_SURFACES:
        surfaces = list(BLAME_SPAN_SURFACES[blame_span])

    headers = _headers(experiment_record)
    return {
        "experiment_id": experiment_id,
        "case_id": case_id,
        "thread_id": case.get("session_thread_id"),
        "trace_id": case.get("trace_id"),
        "bundle_path": bundle_path,
        "artifact_class": artifact_class,
        "deterministic_pass": bool(case.get("deterministic_pass")),
        "first_divergent_span": first_divergent_span,
        "blame_span": blame_span,
        "metric_ids": metric_ids,
        "failure_ids": failure_ids,
        "prevention_ids": sorted(set(prevention_ids)),
        "topology_missing_spans": topology_missing_spans,
        "counter_span_consistent": counter_span_consistent,
        "scored_field_source": scored_field_source,
        "export_status": headers.get("export_status"),
        "suggested_surfaces": surfaces,
        "replay_command": replay_command,
        "evaluator_errors": list(case.get("evaluator_errors") or []),
        "headers": headers,
    }


def explain(
    repo: Path,
    *,
    experiment_id: str | None = None,
    case_id: str | None = None,
) -> dict[str, Any]:
    """§18.3 ``eval explain``: deterministic explain for one/many cases.

    No opaque LLM RCA, no automatic code/rule edits, no Ollie requirement.
    """
    exp, cases = _resolve_experiment_and_case(repo, experiment_id=experiment_id, case_id=case_id)
    record = _load_experiment_record(repo, exp)
    explained = [_explain_one(case, record) for case in cases]
    return project_secret_safe(
        {
            "experiment_id": exp,
            "case_count": len(explained),
            "cases": explained,
            "headers": _headers(record),
        }
    )


def _score_index(case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Project or compute score rows used by operator surfaces (not product accept)."""
    out: dict[str, dict[str, Any]] = {}
    for row in case.get("scores") or []:
        if isinstance(row, dict) and row.get("metric_id"):
            out[str(row["metric_id"])] = row
    return out


def compare(
    repo: Path,
    a_experiment_id: str,
    a_case_id: str,
    b_experiment_id: str,
    b_case_id: str,
) -> dict[str, Any]:
    """§18.3 ``eval compare``: structural + metric delta between two case results.

    Uses lineage only when the two experiments are lineage-linked (recompute
    child ↔ parent); the delta itself is always derived deterministically from
    the two case-result rows. Replay writing is a Slice 6 concern; compare only
    reads.
    """
    _, a_cases = _resolve_experiment_and_case(repo, experiment_id=a_experiment_id, case_id=a_case_id)
    _, b_cases = _resolve_experiment_and_case(repo, experiment_id=b_experiment_id, case_id=b_case_id)
    a = a_cases[0]
    b = b_cases[0]

    a_record = _load_experiment_record(repo, a_experiment_id)
    b_record = _load_experiment_record(repo, b_experiment_id)
    a_meta = a_record.get("meta") if isinstance(a_record.get("meta"), dict) else {}
    b_meta = b_record.get("meta") if isinstance(b_record.get("meta"), dict) else {}
    lineage_linked = bool(
        (a_meta.get("parent_experiment_id") == b_experiment_id)
        or (b_meta.get("parent_experiment_id") == a_experiment_id)
    )

    a_scores = _score_index(a)
    b_scores = _score_index(b)
    metric_ids = sorted(set(a_scores) | set(b_scores))
    metric_delta: list[dict[str, Any]] = []
    for mid in metric_ids:
        ra = a_scores.get(mid)
        rb = b_scores.get(mid)
        pa = ra.get("passed") if isinstance(ra, dict) else None
        pb = rb.get("passed") if isinstance(rb, dict) else None
        va = ra.get("value") if isinstance(ra, dict) else None
        vb = rb.get("value") if isinstance(rb, dict) else None
        if ra is None or rb is None or pa != pb or va != vb:
            metric_delta.append(
                {
                    "metric_id": mid,
                    "a": {"present": ra is not None, "passed": pa, "value": va},
                    "b": {"present": rb is not None, "passed": pb, "value": vb},
                    "changed": not (ra is not None and rb is not None and pa == pb and va == vb),
                }
            )

    structural_delta = {
        "deterministic_pass": {
            "a": bool(a.get("deterministic_pass")),
            "b": bool(b.get("deterministic_pass")),
            "changed": bool(a.get("deterministic_pass")) != bool(b.get("deterministic_pass")),
        },
        "failed_metric_ids": {
            "a": sorted(a.get("failed_metric_ids") or []),
            "b": sorted(b.get("failed_metric_ids") or []),
            "changed": sorted(a.get("failed_metric_ids") or []) != sorted(b.get("failed_metric_ids") or []),
        },
    }

    return project_secret_safe(
        {
            "a": {"experiment_id": a_experiment_id, "case_id": a_case_id},
            "b": {"experiment_id": b_experiment_id, "case_id": b_case_id},
            "lineage_linked": lineage_linked,
            # Delta is always derived from case-result rows; lineage is orthogonal.
            "compare_source": "case_result_delta",
            "metric_delta": metric_delta,
            "structural_delta": structural_delta,
        }
    )


__all__ = [
    "BLAME_SPAN_SURFACES",
    "CASE_RESULT_SCHEMA",
    "ExplainError",
    "compare",
    "explain",
    "list_failures",
]
