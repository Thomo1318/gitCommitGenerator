"""S6 Slice 8 offline ``eval triage`` router (Issue #246 / D27).

Composes landed library engines — never Typer presentation functions:

* :func:`git_cg.eval.doctor.run_local_doctor`
* :func:`git_cg.eval.explain.list_failures`
* :func:`git_cg.eval.explain.explain`

Contract locks:

* Offline / network-free. No Opik SDK import.
* Advisory router only — **not** score law, accept-path, gold promotion,
  ranking, or a second ``user_acceptance`` threshold surface.
* Stable ``eval_triage_v0`` projection with nulls for skipped sections.
* Exit precedence (highest first): usage ``2`` → store ``4`` → doctor compat
  ``3`` → doctor block-red ``1`` → advisory success ``0`` (listed failures alone
  never force non-zero).
* Explain auto-select: explicit ``--case``; else exactly one failing case;
  else omit with a deterministic note.

Import law: heavy helpers are imported lazily inside :func:`run_triage` so the
CLI import graph stays binder/Opik-free.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

SCHEMA_VERSION: Final[str] = "eval_triage_v0"
AUTHORITY: Final[str] = "advisory_offline_router"

REPLACEMENTS_FOR_LEGACY_SCRIPT: Final[tuple[str, ...]] = (
    "git-cg eval triage",
    "git-cg eval doctor",
    "git-cg eval failures",
    "git-cg eval explain",
)

_DEFAULT_SUITE: Final[str] = "cm-eval-fixtures-core"


class TriageError(ValueError):
    """Deterministic triage failure (fail-closed usage/config)."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        exit_code: int,
        hint: str | None = None,
    ) -> None:
        """Attach triage failure code, exit class, and operator hint."""
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code
        self.hint = hint


@dataclass(frozen=True, slots=True)
class TriageReport:
    """Aggregated offline triage projection + process exit code."""

    data: dict[str, Any]
    exit_code: int
    ok: bool

    def to_data(self) -> dict[str, Any]:
        """Envelope ``data`` payload (machine-readable)."""
        return dict(self.data)


def _doctor_exit(exit_code: int) -> int:
    """Normalise doctor exit codes into the triage precedence set."""
    if exit_code in {0, 1, 3}:
        return exit_code
    # Unknown doctor codes stay fail-closed as block-red rather than success.
    if exit_code != 0:
        return 1
    return 0


def _merge_doctor_exit(current: int, doctor_exit: int) -> int:
    """Fold doctor exit into triage exit (doctor never emits usage/store)."""
    candidate = _doctor_exit(doctor_exit)
    # Precedence among success-path codes: 3 > 1 > 0.
    if current in {2, 4}:
        return current
    if 3 in (candidate, current):
        return 3
    if candidate == 1 or current == 1:
        return 1
    return 0


def run_triage(
    repo: Path,
    *,
    suite_id: str = _DEFAULT_SUITE,
    fixture_root: Path | None = None,
    experiment_id: str | None = None,
    case_id: str | None = None,
    skip_doctor: bool = False,
    skip_failures: bool = False,
    skip_explain: bool = False,
) -> TriageReport:
    """Run the offline triage router and return one ``eval_triage_v0`` report.

    Raises:
        TriageError: usage/config problems owned by this router.
        ExplainError: store/usage failures from failures/explain engines
            (``code`` / ``exit_code`` / ``hint`` preserved for the CLI mapper).
    """
    if skip_doctor and skip_failures and skip_explain:
        raise TriageError(
            "all triage sections skipped",
            code="EVAL_USAGE",
            exit_code=2,
            hint="Omit at least one of --skip-doctor / --skip-failures / --skip-explain.",
        )

    # Lazy imports keep git_cg.eval.cli import-light (doctor/explain pull scoring).
    from git_cg.eval.doctor import run_local_doctor
    from git_cg.eval.explain import explain, list_failures

    sections_run: list[str] = []
    sections_skipped: list[str] = []
    notes: list[str] = []
    exit_code = 0

    doctor_data: dict[str, Any] | None = None
    if skip_doctor:
        sections_skipped.append("doctor")
    else:
        report = run_local_doctor(
            repo_root=repo,
            suite_id=suite_id,
            fixture_root=fixture_root,
        )
        doctor_data = report.to_data()
        sections_run.append("doctor")
        exit_code = _merge_doctor_exit(exit_code, int(report.exit_code))

    failures_data: dict[str, Any] | None = None
    if skip_failures:
        sections_skipped.append("failures")
    else:
        failures_data = list_failures(repo, experiment_id=experiment_id)
        sections_run.append("failures")

    explain_data: dict[str, Any] | None = None
    if skip_explain:
        sections_skipped.append("explain")
    else:
        explain_data, explain_notes = _select_explain(
            repo,
            experiment_id=experiment_id,
            case_id=case_id,
            failures_data=failures_data,
            failures_skipped=skip_failures,
            explain_fn=explain,
        )
        notes.extend(explain_notes)
        if explain_data is not None:
            sections_run.append("explain")
        else:
            sections_skipped.append("explain")

    data: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "authority": AUTHORITY,
        "not_score_law": True,
        "doctor": doctor_data,
        "failures": failures_data,
        "explain": explain_data,
        "sections_run": sections_run,
        "sections_skipped": sections_skipped,
        "notes": notes,
        "replacements_for_legacy_script": list(REPLACEMENTS_FOR_LEGACY_SCRIPT),
    }

    ok = True if doctor_data is None else bool(doctor_data.get("green"))
    return TriageReport(data=data, exit_code=exit_code, ok=ok)


def _select_explain(
    repo: Path,
    *,
    experiment_id: str | None,
    case_id: str | None,
    failures_data: dict[str, Any] | None,
    failures_skipped: bool,
    explain_fn: Any,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Apply locked explain-selection rules; return payload + notes."""
    notes: list[str] = []

    if case_id is not None:
        payload = explain_fn(repo, experiment_id=experiment_id, case_id=case_id)
        return payload, notes

    if failures_skipped or failures_data is None:
        notes.append(
            "explain omitted: pass --case to select a case (or run failures section for single-failure auto-select)."
        )
        return None, notes

    failing = list(failures_data.get("failing_cases") or [])
    exp = failures_data.get("experiment_id")
    if len(failing) == 1:
        only_id = str(failing[0].get("case_id") or "")
        if not only_id:
            notes.append("explain omitted: single failing case missing case_id")
            return None, notes
        payload = explain_fn(
            repo,
            experiment_id=str(exp) if exp else experiment_id,
            case_id=only_id,
        )
        notes.append(f"auto-selected single failing case: {only_id}")
        return payload, notes

    if len(failing) > 1:
        notes.append(
            f"{len(failing)} failing cases; pass --case <id> to explain one (or run `git-cg eval explain --case <id>`)."
        )
        return None, notes

    notes.append("no failing cases; explain section omitted")
    return None, notes
