"""S6 Slice 5 deterministic ``eval diagnose`` + issue store (Issue #246).

Implements the ``diag_issue_v1`` upsert law (plan §18.4 / FIND-021 / INT-07,08,36):

* **Stable fingerprint** over the normative inclusion list — sorted
  ``failure_ids`` + sorted ``metric_ids`` + ``blame_span`` + ``regime`` +
  ``artifact_class`` + topology missing-span set + path-class key. The
  fingerprint MUST exclude trace IDs, timestamps, raw text, URLs, usernames,
  and absolute paths. Slice 5 consumes the already-sanitised Family I
  ``evidence["diag_fingerprint_inputs"]`` (span digests), never raw names.
* **Idempotent upsert by fingerprint:** re-diagnosing the same failure bumps
  ``last_seen_at`` / ``occurrence_count`` rather than duplicating a row.
* **Closed transition matrix:** ``open→{acknowledged,resolved,suppressed}``,
  ``acknowledged→{resolved,suppressed,reopened}``,
  ``resolved|suppressed→{reopened}``, ``reopened→{acknowledged,resolved,suppressed}``.
  ``resolve`` requires ``resolution_evidence``; ``suppress`` requires a reason.
  Transitions are idempotent (no-op when already in target state).
* ``prevention_ids`` render only when supplied on source evidence; never
  fabricated from ``metric_ids``.

Persistence honours the Slice 1 Layer-A write law: ``issues_dir`` /
``diagnostics_dir`` containment + ``atomic_write_json`` (N19.3). Every written
row validates against the frozen ``schemas/eval/diag_issue_v1.schema.json``
before persist (fail-closed).

Import law: import-light. Path law, schema validation, and the explain reader
are imported lazily inside functions.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from git_cg.eval.evidence_scrub import mask_secrets_in_text, project_secret_safe

SCHEMA_NAME: Final[str] = "diag_issue_v1"
SCHEMA_VERSION: Final[str] = "diag_issue_v1"

# Closed five-value lifecycle (frozen schema enum).
STATUS_OPEN: Final[str] = "open"
STATUS_ACKNOWLEDGED: Final[str] = "acknowledged"
STATUS_RESOLVED: Final[str] = "resolved"
STATUS_SUPPRESSED: Final[str] = "suppressed"
STATUS_REOPENED: Final[str] = "reopened"

#: Closed transition matrix (plan §18.4). Target sets are explicit; no others.
TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    STATUS_OPEN: frozenset({STATUS_ACKNOWLEDGED, STATUS_RESOLVED, STATUS_SUPPRESSED}),
    STATUS_ACKNOWLEDGED: frozenset({STATUS_RESOLVED, STATUS_SUPPRESSED, STATUS_REOPENED}),
    STATUS_RESOLVED: frozenset({STATUS_REOPENED}),
    STATUS_SUPPRESSED: frozenset({STATUS_REOPENED}),
    STATUS_REOPENED: frozenset({STATUS_ACKNOWLEDGED, STATUS_RESOLVED, STATUS_SUPPRESSED}),
}

# Severity rollup from failing Family I / catalog severities (block wins).
_SEVERITY_ORDER: Final[tuple[str, ...]] = ("block", "warn", "info")

_SAFE_ID: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


class DiagnoseError(ValueError):
    """Deterministic diagnose/issue-store failure (fail-closed)."""

    def __init__(self, message: str, *, code: str, exit_code: int, hint: str | None = None) -> None:
        """Attach diagnose failure code, exit class, and operator hint."""
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code
        self.hint = hint


def _issues_dir(repo: Path) -> Path:
    """Resolve the governed diagnostic issues store directory."""
    from git_cg.eval.binding.paths import LayerAPathError, issues_dir

    try:
        return issues_dir(repo)
    except LayerAPathError as exc:
        raise DiagnoseError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc


def _diagnostics_dir(repo: Path) -> Path:
    """Resolve the governed diagnostics store directory."""
    from git_cg.eval.binding.paths import LayerAPathError, diagnostics_dir

    try:
        return diagnostics_dir(repo)
    except LayerAPathError as exc:
        raise DiagnoseError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc


def _atomic_write(repo: Path, path: Path, payload: dict[str, Any]) -> Path:
    """Atomically write JSON through the Layer-A path helper (fail closed)."""
    from git_cg.eval.binding.paths import LayerAPathError, atomic_write_json

    try:
        return atomic_write_json(path, payload)
    except LayerAPathError as exc:
        raise DiagnoseError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc


def _validate(row: dict[str, Any]) -> None:
    """Fail-closed schema validation against the frozen diag_issue_v1 schema."""
    from git_cg.eval.schema_pack import SchemaPackError, validate_instance

    try:
        validate_instance(SCHEMA_NAME, row)
    except SchemaPackError as exc:
        raise DiagnoseError(
            f"diag_issue_v1 validation failed: {exc}",
            code="EVAL_STORE_INTEGRITY",
            exit_code=4,
        ) from exc


def _utc_now() -> str:
    """Return the current UTC timestamp as an ISO-8601 Zulu string."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def compute_fingerprint(inputs: dict[str, Any]) -> str:
    """Canonical SHA256 fingerprint over the normative inclusion list.

    Preimage keys (and only these): ``failure_ids`` (sorted), ``metric_ids``
    (sorted), ``blame_span``, ``regime``, ``artifact_class``,
    ``missing_required_spans`` (topology missing-span set, sorted),
    ``path_class_key``. Serialised as canonical JSON (sorted keys) so the digest
    is order-stable. Excludes trace ids, timestamps, raw text, URLs, usernames,
    absolute paths — guaranteed by consuming the sanitised Family I inputs.
    """
    preimage = {
        "failure_ids": sorted(str(x) for x in (inputs.get("failure_ids") or [])),
        "metric_ids": sorted(str(x) for x in (inputs.get("metric_ids") or [])),
        "blame_span": inputs.get("blame_span"),
        "regime": inputs.get("regime"),
        "artifact_class": inputs.get("artifact_class"),
        "missing_required_spans": sorted(str(x) for x in (inputs.get("missing_required_spans") or [])),
        "path_class_key": inputs.get("path_class_key"),
    }
    canonical = json.dumps(preimage, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _issue_path(repo: Path, issue_id: str) -> Path:
    """Resolve one diagnostic issue path with containment checks."""
    if not _SAFE_ID.fullmatch(issue_id):
        raise DiagnoseError(
            f"invalid issue_id: {issue_id!r}",
            code="EVAL_USAGE",
            exit_code=2,
        )
    return _issues_dir(repo) / f"{issue_id}.json"


def _load_issue(repo: Path, issue_id: str) -> dict[str, Any]:
    """Load a governed artifact from the Layer-A store (fail closed)."""
    path = _issue_path(repo, issue_id)
    if not path.is_file():
        raise DiagnoseError(
            f"issue not found: {issue_id!r}",
            code="EVAL_USAGE",
            exit_code=2,
            hint="Pass an issue id from `git-cg eval issue list`.",
        )
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DiagnoseError(
            f"issue row unreadable: {issue_id!r}: {exc}",
            code="EVAL_STORE_INTEGRITY",
            exit_code=4,
        ) from exc
    if not isinstance(obj, dict) or obj.get("schema_version") != SCHEMA_VERSION:
        raise DiagnoseError(
            f"issue row has unexpected schema: {issue_id!r}",
            code="EVAL_STORE_INTEGRITY",
            exit_code=4,
        )
    return obj


def _find_issue_by_fingerprint(repo: Path, fingerprint: str) -> dict[str, Any] | None:
    """Find an existing issue row by stable fingerprint (idempotent diagnose)."""
    root = _issues_dir(repo)
    if not root.is_dir():
        return None
    for path in sorted(root.glob("*.json")):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            # Fail closed: skipping damaged rows would mint duplicate fingerprints.
            raise DiagnoseError(
                f"issue row unreadable: {path.name}: {exc}",
                code="EVAL_STORE_INTEGRITY",
                exit_code=4,
            ) from exc
        if isinstance(obj, dict) and obj.get("fingerprint") == fingerprint:
            return obj
    return None


def _build_issue_row(
    *,
    fingerprint: str,
    failing: list[dict[str, Any]],
    aggregate_inputs: dict[str, Any],
    code: str | None,
    title: str | None,
    product_impact: str,
    now: str,
    sample_bundle_ids: list[str],
    sample_trace_ids: list[str],
    owner: str | None,
    schema_pack: str | None,
    metric_catalog: str | None,
    notes: str | None,
) -> dict[str, Any]:
    """Build a structured row/payload for the local operator store."""
    from git_cg.eval.explain import BLAME_SPAN_SURFACES

    metric_ids = sorted({str(m) for m in (aggregate_inputs.get("metric_ids") or [])})
    failure_ids = sorted({str(f) for f in (aggregate_inputs.get("failure_ids") or [])})
    blame_span = aggregate_inputs.get("blame_span")

    # prevention_ids only when supplied on source evidence (never fabricated).
    prevention_ids: list[str] = []
    for m in failing:
        if isinstance(m.get("prevention_ids"), list):
            prevention_ids.extend(str(p) for p in m["prevention_ids"])

    surfaces: list[str] = []
    if isinstance(blame_span, str) and blame_span in BLAME_SPAN_SURFACES:
        surfaces = list(BLAME_SPAN_SURFACES[blame_span])

    resolved_code = code or (failure_ids[0] if failure_ids else "EVAL_DIAGNOSTIC")
    resolved_title = (
        mask_secrets_in_text(title or f"{resolved_code}: {blame_span or 'deterministic eval failure'}") or ""
    )

    row: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "id": f"issue-{fingerprint[:16]}",
        "issue_id": f"issue-{fingerprint[:16]}",
        "fingerprint": fingerprint,
        "code": resolved_code,
        "status": STATUS_OPEN,
        "severity": _severity_from(failing),
        "title": resolved_title,
        "first_seen_at": now,
        "last_seen_at": now,
        "occurrence_count": 1,
        "failure_ids": failure_ids,
        "metric_ids": metric_ids,
        "product_impact": product_impact,
    }
    if prevention_ids:
        row["prevention_ids"] = sorted(set(prevention_ids))
    if isinstance(aggregate_inputs.get("regime"), str) and aggregate_inputs["regime"].strip():
        row["regime"] = aggregate_inputs["regime"].strip()
    if isinstance(blame_span, str) and blame_span.strip():
        row["blame_span"] = blame_span.strip()
    if isinstance(aggregate_inputs.get("artifact_class"), str) and aggregate_inputs["artifact_class"].strip():
        row["artifact_class"] = aggregate_inputs["artifact_class"].strip()
    if isinstance(aggregate_inputs.get("path_class_key"), str) and aggregate_inputs["path_class_key"].strip():
        row["path_class"] = aggregate_inputs["path_class_key"].strip()
    if aggregate_inputs.get("missing_required_spans"):
        row["topology_missing_spans"] = sorted(str(x) for x in aggregate_inputs["missing_required_spans"])
    if sample_bundle_ids:
        row["sample_bundle_ids"] = sample_bundle_ids[:32]
    if sample_trace_ids:
        row["sample_trace_ids"] = sample_trace_ids[:32]
    if surfaces:
        row["suggested_surfaces"] = surfaces
    if owner and owner.strip():
        row["owner"] = mask_secrets_in_text(owner.strip()) or owner.strip()
    if schema_pack and schema_pack.strip():
        row["schema_pack"] = schema_pack.strip()
    if metric_catalog and metric_catalog.strip():
        row["metric_catalog"] = metric_catalog.strip()
    if notes and notes.strip():
        row["notes"] = mask_secrets_in_text(notes.strip()) or notes.strip()
    return project_secret_safe(row)


def _severity_from(failing: list[dict[str, Any]]) -> str:
    """Roll up severity from failing rows; block wins, else warn, else info."""
    seen: set[str] = set()
    for m in failing:
        sev = m.get("severity")
        if isinstance(sev, str) and sev in _SEVERITY_ORDER:
            seen.add(sev)
    for sev in _SEVERITY_ORDER:
        if sev in seen:
            return sev
    return "block"


def _merge_fingerprint_inputs(cases: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Merge per-case sanitised Family I fingerprint inputs into one aggregate.

    Returns ``(failing_rows, aggregate_inputs)`` where aggregate_inputs holds the
    unioned/sorted inclusion-list fields used for both fingerprint and row.
    """
    failing: list[dict[str, Any]] = []
    failure_ids: set[str] = set()
    metric_ids: set[str] = set()
    missing_spans: set[str] = set()
    blame_span: str | None = None
    regime: str | None = None
    artifact_class: str | None = None
    path_class_key: str | None = None

    for case in cases:
        for row in case.get("scores") or []:
            if not isinstance(row, dict) or row.get("passed") is not False:
                continue
            evidence = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
            fp = (
                evidence.get("diag_fingerprint_inputs")
                if isinstance(evidence.get("diag_fingerprint_inputs"), dict)
                else {}
            )
            failing.append(
                {
                    "metric_id": row.get("metric_id"),
                    "severity": evidence.get("severity") or row.get("severity"),
                    "prevention_ids": evidence.get("prevention_ids"),
                }
            )
            for fid in row.get("failure_ids") or []:
                failure_ids.add(str(fid))
            if row.get("metric_id"):
                metric_ids.add(str(row["metric_id"]))
            # Prefer the sanitised fingerprint inputs over raw evidence fields.
            blame_span = blame_span or fp.get("blame_span")
            regime = regime or fp.get("regime")
            artifact_class = artifact_class or fp.get("artifact_class")
            path_class_key = path_class_key or fp.get("path_class_key")
            for sp in fp.get("missing_required_spans") or evidence.get("missing_required_spans") or []:
                missing_spans.add(str(sp))

    aggregate = {
        "failure_ids": sorted(failure_ids),
        "metric_ids": sorted(metric_ids),
        "blame_span": blame_span,
        "regime": regime,
        "artifact_class": artifact_class,
        "path_class_key": path_class_key,
        "missing_required_spans": sorted(missing_spans),
    }
    return failing, aggregate


def diagnose(
    repo: Path,
    *,
    experiment_id: str | None = None,
    case_id: str | None = None,
    code: str | None = None,
    title: str | None = None,
    product_impact: str = "unknown",
    owner: str | None = None,
    notes: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Upsert a ``diag_issue_v1`` row for the failing case(s) (idempotent).

    Re-running on the same fingerprint updates ``last_seen_at`` and
    ``occurrence_count`` (and appends capped samples) instead of duplicating.

    When ``dry_run=True`` (NTH-03), the issue row is fully built + schema-validated
    and a would-write summary is returned, but neither the issue store nor the
    diagnostics snapshot is mutated.
    """
    from git_cg.eval.explain import ExplainError, _load_experiment_record, _resolve_experiment_and_case
    from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin

    try:
        exp, cases = _resolve_experiment_and_case(repo, experiment_id=experiment_id, case_id=case_id)
    except ExplainError as exc:
        raise DiagnoseError(str(exc), code=exc.code, exit_code=exc.exit_code, hint=exc.hint) from exc

    failing_cases = [c for c in cases if c.get("deterministic_pass") is not True]
    if not failing_cases:
        raise DiagnoseError(
            "no failing cases to diagnose",
            code="EVAL_USAGE",
            exit_code=2,
            hint="`eval diagnose` operates on failing case results; none found for the target.",
        )

    failing, aggregate = _merge_fingerprint_inputs(failing_cases)
    fingerprint = compute_fingerprint(aggregate)
    now = _utc_now()

    sample_bundle_ids = sorted({str(c.get("case_id")) for c in failing_cases if c.get("case_id")})
    sample_trace_ids = sorted({str(c.get("trace_id")) for c in failing_cases if isinstance(c.get("trace_id"), str)})

    # Resolve pins defensively: the experiment record may be absent for a
    # minimal synthetic fixture; pins fall back to the live catalog helpers.
    try:
        record = _load_experiment_record(repo, exp)
    except ExplainError:
        # A missing/unreadable experiment.json is non-fatal for diagnose: the
        # issue fingerprint + lifecycle do not depend on it. Pins fall back to
        # the live catalog helpers.
        record = {}
    meta = record.get("meta") if isinstance(record.get("meta"), dict) else {}
    pins = meta.get("pins") if isinstance(meta.get("pins"), dict) else {}

    existing = _find_issue_by_fingerprint(repo, fingerprint)
    if existing is not None:
        row = dict(existing)
        row["last_seen_at"] = now
        try:
            row["occurrence_count"] = max(1, int(existing.get("occurrence_count", 1))) + 1
        except TypeError, ValueError:
            row["occurrence_count"] = 2
        # Append capped samples without unbounded growth (schema maxItems 32).
        merged_bundles = sorted(set(existing.get("sample_bundle_ids") or []) | set(sample_bundle_ids))
        merged_traces = sorted(set(existing.get("sample_trace_ids") or []) | set(sample_trace_ids))
        if merged_bundles:
            row["sample_bundle_ids"] = merged_bundles[:32]
        if merged_traces:
            row["sample_trace_ids"] = merged_traces[:32]
        # Operator-supplied free text on re-diagnose must not be silently dropped.
        if code and str(code).strip():
            row["code"] = str(code).strip()
        if title and str(title).strip():
            row["title"] = mask_secrets_in_text(str(title).strip()) or str(title).strip()
        if owner and str(owner).strip():
            row["owner"] = mask_secrets_in_text(str(owner).strip()) or str(owner).strip()
        if notes and str(notes).strip():
            row["notes"] = mask_secrets_in_text(str(notes).strip()) or str(notes).strip()
        row = project_secret_safe(row)
        upserted = True
    else:
        row = _build_issue_row(
            fingerprint=fingerprint,
            failing=failing,
            aggregate_inputs=aggregate,
            code=code,
            title=title,
            product_impact=product_impact,
            now=now,
            sample_bundle_ids=sample_bundle_ids,
            sample_trace_ids=sample_trace_ids,
            owner=owner,
            schema_pack=str(pins.get("schema_pack") or schema_pack_pin() or "") or None,
            metric_catalog=str(pins.get("metric_catalog") or metric_catalog_pin() or "") or None,
            notes=notes,
        )
        upserted = False

    _validate(row)
    path = _issue_path(repo, str(row["issue_id"]))
    snapshot_path = _diagnostics_dir(repo) / f"{row['issue_id']}.json"

    # Diagnostics snapshot row (observability; rebuildable, never authority).
    snapshot = {
        "schema_version": "diag_snapshot_v0",
        "issue_id": row["issue_id"],
        "fingerprint": fingerprint,
        "experiment_id": exp,
        "diagnosed_at": now,
        "upserted": upserted,
        "occurrence_count": row["occurrence_count"],
    }

    if not dry_run:
        _atomic_write(repo, path, row)
        _atomic_write(repo, snapshot_path, snapshot)

    return project_secret_safe(
        {
            "issue": row,
            "upserted": upserted,
            "issue_path": str(path),
            "dry_run": dry_run,
            "would_write": {
                "issue_path": str(path),
                "diagnostics_path": str(snapshot_path),
                "fingerprint": fingerprint,
                "occurrence_count": row["occurrence_count"],
                "status": row.get("status"),
            },
        }
    )


def list_issues(repo: Path, *, status: str | None = None) -> dict[str, Any]:
    """``eval issue list``: all stored issues, newest ``last_seen_at`` first."""
    root = _issues_dir(repo)
    rows: list[dict[str, Any]] = []
    if root.is_dir():
        for path in sorted(root.glob("*.json")):
            try:
                obj = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise DiagnoseError(
                    f"issue row unreadable: {path.name}: {exc}",
                    code="EVAL_STORE_INTEGRITY",
                    exit_code=4,
                ) from exc
            if isinstance(obj, dict) and obj.get("schema_version") == SCHEMA_VERSION:
                rows.append(obj)
    if status is not None:
        rows = [r for r in rows if r.get("status") == status]
    rows.sort(key=lambda r: str(r.get("last_seen_at") or ""), reverse=True)
    return project_secret_safe({"issues": rows, "issue_count": len(rows)})


def show_issue(repo: Path, *, issue_id: str) -> dict[str, Any]:
    """``eval issue show``: one issue row by id."""
    return project_secret_safe({"issue": _load_issue(repo, issue_id)})


def transition_issue(
    repo: Path,
    *,
    issue_id: str,
    target: str,
    resolution_evidence: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Apply one closed-matrix lifecycle transition (idempotent).

    * Illegal transitions fail closed (exit 2).
    * ``resolve`` requires ``resolution_evidence``; ``suppress`` requires ``reason``.
    * Re-applying the current status is a no-op success (idempotent).
    """
    if target not in TRANSITIONS:
        raise DiagnoseError(
            f"unknown target status: {target!r}",
            code="EVAL_USAGE",
            exit_code=2,
        )
    row = _load_issue(repo, issue_id)
    current = str(row.get("status") or STATUS_OPEN)

    if current == target:
        # Idempotent no-op; still enforce required evidence/reason on the verbs
        # so a scripted resolve/suppress always carries provenance.
        _require_transition_args(target, resolution_evidence=resolution_evidence, reason=reason)
        return project_secret_safe({"issue": row, "transitioned": False, "from": current, "to": target})

    allowed = TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise DiagnoseError(
            f"illegal transition: {current} -> {target}",
            code="EVAL_USAGE",
            exit_code=2,
            hint=f"Allowed from {current}: {sorted(allowed)}.",
        )

    _require_transition_args(target, resolution_evidence=resolution_evidence, reason=reason)

    updated = dict(row)
    updated["status"] = target
    updated["last_seen_at"] = _utc_now()
    if target == STATUS_RESOLVED and resolution_evidence and resolution_evidence.strip():
        updated["resolution_evidence"] = (
            mask_secrets_in_text(resolution_evidence.strip()) or resolution_evidence.strip()
        )
    if target == STATUS_SUPPRESSED and reason and reason.strip():
        safe_reason = mask_secrets_in_text(reason.strip()) or reason.strip()
        note = f"suppressed: {safe_reason}"
        existing_notes = str(updated.get("notes") or "").strip()
        updated["notes"] = f"{existing_notes}\n{note}".strip() if existing_notes else note

    # Final free-text projection before persist (S6-C08).
    updated = project_secret_safe(updated)
    _validate(updated)
    path = _issue_path(repo, issue_id)
    _atomic_write(repo, path, updated)
    return project_secret_safe({"issue": updated, "transitioned": True, "from": current, "to": target})


def _require_transition_args(
    target: str,
    *,
    resolution_evidence: str | None,
    reason: str | None,
) -> None:
    """Require the argument set mandated by a state transition."""
    if target == STATUS_RESOLVED and not (resolution_evidence and resolution_evidence.strip()):
        raise DiagnoseError(
            "resolve requires resolution evidence",
            code="EVAL_USAGE",
            exit_code=2,
            hint="Pass --resolution-evidence describing the fix verification.",
        )
    if target == STATUS_SUPPRESSED and not (reason and reason.strip()):
        raise DiagnoseError(
            "suppress requires a reason",
            code="EVAL_USAGE",
            exit_code=2,
            hint="Pass --reason explaining why the issue is suppressed.",
        )


__all__ = [
    "SCHEMA_NAME",
    "SCHEMA_VERSION",
    "STATUS_ACKNOWLEDGED",
    "STATUS_OPEN",
    "STATUS_REOPENED",
    "STATUS_RESOLVED",
    "STATUS_SUPPRESSED",
    "TRANSITIONS",
    "DiagnoseError",
    "compute_fingerprint",
    "diagnose",
    "list_issues",
    "show_issue",
    "transition_issue",
]
