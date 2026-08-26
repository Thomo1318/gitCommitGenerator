"""``git-cg eval`` operator CLI (S3-S6).

Extends the landed corpus helpers and S4 mirror surface with the S6 operator
command skeleton (Issue #246 Slice 2). Behaviour for most S6 commands lands in
later slices; help names and nested groups are real now so the operator API
map cannot drift from the Typer tree.

Import law (locked):
* No binder invocation at import time.
* No hard Opik SDK import at module import time.
* Opik is resolved lazily inside drain transport construction only.
* Not a general-purpose Python SDK — CLI is the primary public API.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
from typer.core import TyperGroup

from git_cg.eval.cli_output import (
    DEFAULT_KEEP_LAST,
    REMOVAL_TARGET,
    build_envelope,
    deprecation_warning,
    emit_deprecation_human,
    emit_json_envelope,
    emit_not_implemented,
)


class EvalHelpGroup(TyperGroup):
    """Order ``git-cg eval --help`` panels by operator workflow.

    Typer registers leaf commands before nested groups, so plain registration
    order always pushes Review/session groups to the bottom. This group keeps
    command resolution unchanged while listing commands in panel-priority order
    for Rich help rendering.
    """

    _HELP_PANEL_ORDER: tuple[str, ...] = (
        "Corpus",
        "Run",
        "Inspect",
        "Review & sessions",
        "Export & train",
        "Advanced",
        "Deprecated",
    )

    def list_commands(self, ctx: typer.Context) -> list[str]:  # type: ignore[override]
        names = list(super().list_commands(ctx))
        priority = {name: idx for idx, name in enumerate(self._HELP_PANEL_ORDER)}
        default_panel = "Commands"

        def sort_key(command_name: str) -> tuple[int, int]:
            command = self.get_command(ctx, command_name)
            panel = default_panel
            if command is not None:
                panel = getattr(command, "rich_help_panel", None) or default_panel
            panel_rank = priority.get(panel, len(priority))
            # Stable within-panel: preserve registration order among peers.
            return (panel_rank, names.index(command_name))

        return sorted(names, key=sort_key)


eval_app = typer.Typer(
    cls=EvalHelpGroup,
    add_completion=False,
    help=(
        "Run and inspect local evaluation suites, debug failures, manage "
        "review/sessions, and operate the export queue. Does not change "
        "product commit ranking."
    ),
    no_args_is_help=True,
)


# Nested groups declared early so top-level help panels order by workflow:
# Corpus → Run → Inspect → Review & sessions → Export & train → Advanced → Deprecated.
review_app = typer.Typer(
    add_completion=False,
    help="Local human review queue (advisory only).",
    no_args_is_help=True,
)
session_app = typer.Typer(
    add_completion=False,
    help="Inspect local commit sessions.",
    no_args_is_help=True,
)
thread_app = typer.Typer(
    add_completion=False,
    help="Inspect local session threads.",
    no_args_is_help=True,
)
issue_app = typer.Typer(
    add_completion=False,
    help="Manage local diagnostic issues.",
    no_args_is_help=True,
)
opik_app = typer.Typer(
    add_completion=False,
    help="Opik health checks and secret-safe config.",
    no_args_is_help=True,
)
opik_config_app = typer.Typer(
    add_completion=False,
    help="Inspect Opik/mirror config without exposing secrets.",
    no_args_is_help=True,
)
export_app = typer.Typer(
    add_completion=False,
    help="Export-queue status, retry, and drain.",
    no_args_is_help=True,
)

# Register groups before leaf Export/Advanced commands so panel order matches workflow.
eval_app.add_typer(review_app, name="review", rich_help_panel="Review & sessions")
eval_app.add_typer(session_app, name="session", rich_help_panel="Review & sessions")
eval_app.add_typer(thread_app, name="thread", rich_help_panel="Review & sessions")
eval_app.add_typer(issue_app, name="issue", rich_help_panel="Review & sessions")
eval_app.add_typer(opik_app, name="opik", rich_help_panel="Export & train")
opik_app.add_typer(opik_config_app, name="config")
eval_app.add_typer(export_app, name="export", rich_help_panel="Export & train")


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------


def _stub(
    command: str,
    *,
    slice_hint: str,
    as_json: bool = False,
) -> None:
    """Thin Slice-2 stub: real help name, behaviour later."""
    emit_not_implemented(command, slice_hint=slice_hint, as_json=as_json)


# --------------------------------------------------------------------------
# Corpus helpers (landed S3)
# --------------------------------------------------------------------------


@eval_app.command("materialize-core-goldens", rich_help_panel="Corpus")
def materialize_core_goldens_cmd(
    root: Path | None = typer.Option(
        None,
        "--root",
        help="Fixture root (defaults to tests/fixtures/eval).",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
) -> None:
    """Write checked-in core golden bundles and snapshot."""
    from git_cg.eval.corpus.materialize import materialize_core_goldens

    try:
        result = materialize_core_goldens(fixture_root=root)
    except Exception as exc:  # corpus helpers raise ValueError subclasses
        typer.echo(f"materialize-core-goldens failed: {exc}", err=True)
        raise typer.Exit(code=1) from None

    typer.echo(f"core_snapshot {result['core_snapshot']}")
    if result["archive_snapshot"]:
        typer.echo(f"archive_snapshot {result['archive_snapshot']}")
    typer.echo(f"core_bundles {len(result['core_bundles'])}")
    typer.echo(f"archive_bundles {len(result['archive_bundles'])}")
    raise typer.Exit(code=0)


@eval_app.command("encode-fixture", rich_help_panel="Corpus")
def encode_fixture_cmd(
    path: Path | None = typer.Option(
        None,
        "--path",
        help="Path to a fixture JSON file (canonical encode form).",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
    fixture_id: str | None = typer.Option(
        None,
        "--id",
        help="Optional case_id resolver against known suite/fixture roots.",
    ),
    suite_id: str | None = typer.Option(
        None,
        "--suite",
        help="Suite id to resolve --id against (default: cm-eval-fixtures-core).",
    ),
) -> None:
    """Encode a fixture and print its identity summary.

    Requires exactly one of ``--path`` or ``--id``; exits non-zero
    on invalid options, missing fixtures, or encode failures.
    """
    from git_cg.eval.corpus.encoder import encode_fixture
    from git_cg.eval.corpus.fixtures import (
        FixtureLoadError,
        default_fixture_root,
        load_fixture_dict,
        load_suite_fixtures,
    )
    from git_cg.eval.corpus.suites import load_suite

    if path is None and fixture_id is None:
        typer.echo("encode-fixture requires --path <fixture.json> or --id <case_id>", err=True)
        raise typer.Exit(code=2)
    if path is not None and fixture_id is not None:
        typer.echo("encode-fixture accepts only one of --path or --id", err=True)
        raise typer.Exit(code=2)

    fixture: dict[str, Any]
    case_id: str | None = None
    resolved_suite_id: str | None = None

    if path is not None:
        try:
            fixture = load_fixture_dict(path)
        except FixtureLoadError as exc:
            typer.echo(f"encode-fixture failed: {exc}", err=True)
            raise typer.Exit(code=1) from None
    else:
        root = default_fixture_root()
        sid = suite_id or "cm-eval-fixtures-core"
        try:
            suite = load_suite(sid, fixture_root=root)
            pairs = load_suite_fixtures(suite, fixture_root=root)
        except Exception as exc:
            typer.echo(f"encode-fixture --id failed to load suite {sid!r}: {exc}", err=True)
            raise typer.Exit(code=1) from None
        match = next(((cid, fx) for cid, fx in pairs if cid == fixture_id), None)
        if match is None:
            typer.echo(
                f"encode-fixture --id: case_id {fixture_id!r} not found in suite {sid!r}",
                err=True,
            )
            raise typer.Exit(code=1)
        case_id, fixture = match
        resolved_suite_id = sid

    try:
        encoded = encode_fixture(fixture, case_id=case_id, suite_id=resolved_suite_id)
    except Exception as exc:
        typer.echo(f"encode-fixture failed: {exc}", err=True)
        raise typer.Exit(code=1) from None

    typer.echo(f"bundle_hash {encoded['bundle_hash']}")
    typer.echo(f"case_hash {encoded['case_hash']}")
    typer.echo(f"bundle_ref {encoded['bundle_ref']}")
    raise typer.Exit(code=0)


# --------------------------------------------------------------------------
# S6 suite run / resume / recompute (Slice 3)
# --------------------------------------------------------------------------


def _emit_run_result(
    command: str,
    *,
    as_json: bool,
    result: Any | None = None,
    error: BaseException | None = None,
) -> None:
    """Shared stdout/stderr + exit mapping for run/resume/recompute."""
    from git_cg.eval.cli_output import emit_human_line, envelope_message
    from git_cg.eval.run_orchestrator import RunOrchestratorError, RunResult

    if error is not None:
        if isinstance(error, RunOrchestratorError):
            code = error.code
            message = str(error)
            hint = error.hint
            exit_code = int(error.exit_code)
            data = dict(error.data)
            data.setdefault("status", "failed" if exit_code == 1 else "blocked")
        else:
            code = "EVAL_SUITE_FAIL"
            message = str(error)
            hint = None
            exit_code = 1
            data = {"status": "failed"}
        if as_json:
            emit_json_envelope(
                build_envelope(
                    command,
                    ok=False,
                    data=data,
                    errors=[envelope_message(code, message, hint=hint)],
                )
            )
        else:
            line = f"{command}: {message}"
            if hint:
                line = f"{line} ({hint})"
            emit_human_line(line, err=True)
        raise typer.Exit(code=exit_code)

    assert isinstance(result, RunResult)
    data = result.to_data()
    ok = result.exit_code == 0
    if as_json:
        emit_json_envelope(build_envelope(command, ok=ok, data=data))
    else:
        emit_human_line(
            (
                f"{command}: status={result.status} mode={result.mode} "
                f"suite={result.suite_id} experiment={result.experiment_id} "
                f"all_pass={result.all_pass} completed={len(result.completed_case_ids)} "
                f"pending={len(result.pending_case_ids)}"
            ),
            err=False,
        )
        for case in result.case_results:
            failed = ",".join(case.failed_metric_ids) if case.failed_metric_ids else "-"
            emit_human_line(
                f"  case {case.case_id}: deterministic_pass={case.deterministic_pass} failed={failed}",
                err=True,
            )
        if result.checkpoint_id:
            emit_human_line(f"  checkpoint={result.checkpoint_id}", err=True)
        if result.compat_hash:
            emit_human_line(f"  compat_hash={result.compat_hash[:12]}…", err=True)
        if result.pruned_checkpoint_ids:
            emit_human_line(
                f"  pruned_checkpoints={len(result.pruned_checkpoint_ids)}",
                err=True,
            )
    raise typer.Exit(code=result.exit_code)


def _parse_case_ids(raw: str | None) -> tuple[str, ...] | None:
    """Parse a CLI/operator token into the engine-native shape (fail closed)."""
    if raw is None:
        return None
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return tuple(parts) if parts else None


@eval_app.command("run", rich_help_panel="Run")
def run_cmd(
    suite: str | None = typer.Option(
        "cm-eval-fixtures-core",
        "--suite",
        help="Suite id to run (default: cm-eval-fixtures-core).",
    ),
    fixture_root: Path | None = typer.Option(
        None,
        "--fixture-root",
        help="Optional fixture root override (tests/lab).",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    mode: str = typer.Option(
        "fresh_suite_run",
        "--mode",
        help=("Run mode: fresh_suite_run | resume_missing | recompute_scores | replay_generation | export_only."),
    ),
    keep_last: int = typer.Option(
        DEFAULT_KEEP_LAST,
        "--keep-last",
        help="Checkpoint retention bound per suite family (default 10).",
    ),
    keep_checkpoint: bool = typer.Option(
        False,
        "--keep-checkpoint",
        help="Retain this run's checkpoint even after success.",
    ),
    gold_mode: str = typer.Option("strict", "--gold-mode", help="Gold comparison mode."),
    case: str | None = typer.Option(
        None,
        "--case",
        help="Optional comma-separated case id filter (triage/lab only; not CI golden).",
    ),
    experiment: str | None = typer.Option(
        None,
        "--experiment",
        help="Required for export_only / optional parent for recompute via run --mode.",
    ),
    checkpoint: str | None = typer.Option(
        None,
        "--checkpoint",
        help="Checkpoint id when --mode resume_missing.",
    ),
    allow_replay_generation: bool = typer.Option(
        False,
        "--allow-replay-generation",
        help="Explicit gate for replay_generation (refused by default).",
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """Run an offline evaluation suite."""
    # Lazy import preserves Slice 2 import-isolation law (no scoring at import).
    from git_cg.eval.run_orchestrator import RunOrchestratorError, RunRequest, run_evaluation

    try:
        result = run_evaluation(
            RunRequest(
                mode=mode,  # type: ignore[arg-type]
                suite_id=suite or "cm-eval-fixtures-core",
                fixture_root=fixture_root,
                gold_mode=gold_mode,
                keep_last=keep_last,
                keep_checkpoint=keep_checkpoint,
                checkpoint_id=checkpoint,
                experiment_id=experiment,
                case_ids=_parse_case_ids(case),
                allow_replay_generation=allow_replay_generation,
                offline=True,
                enable_lane_c=False,
                enable_dogfood=False,
            )
        )
    except RunOrchestratorError as exc:
        _emit_run_result("eval run", as_json=as_json, error=exc)
    except Exception as exc:
        _emit_run_result("eval run", as_json=as_json, error=exc)
    else:
        _emit_run_result("eval run", as_json=as_json, result=result)


@eval_app.command("resume", rich_help_panel="Run")
def resume_cmd(
    checkpoint: str | None = typer.Option(
        None,
        "--checkpoint",
        help="Checkpoint id to resume (required).",
    ),
    fixture_root: Path | None = typer.Option(
        None,
        "--fixture-root",
        help="Optional fixture root override (tests/lab).",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    keep_last: int = typer.Option(
        DEFAULT_KEEP_LAST,
        "--keep-last",
        help="Checkpoint retention bound per suite family (default 10).",
    ),
    keep_checkpoint: bool = typer.Option(
        False,
        "--keep-checkpoint",
        help="Retain this run's checkpoint even after success.",
    ),
    gold_mode: str = typer.Option("strict", "--gold-mode", help="Gold comparison mode."),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """Resume a suite from a checkpoint."""
    from git_cg.eval.run_orchestrator import RunOrchestratorError, RunRequest, run_evaluation

    if not checkpoint:
        _emit_run_result(
            "eval resume",
            as_json=as_json,
            error=RunOrchestratorError(
                "resume requires --checkpoint",
                code="EVAL_USAGE",
                exit_code=2,
                hint="Pass --checkpoint <id> from a prior suite run.",
            ),
        )
        return

    try:
        result = run_evaluation(
            RunRequest(
                mode="resume_missing",
                fixture_root=fixture_root,
                gold_mode=gold_mode,
                keep_last=keep_last,
                keep_checkpoint=keep_checkpoint,
                checkpoint_id=checkpoint,
                offline=True,
            )
        )
    except RunOrchestratorError as exc:
        _emit_run_result("eval resume", as_json=as_json, error=exc)
    except Exception as exc:
        _emit_run_result("eval resume", as_json=as_json, error=exc)
    else:
        _emit_run_result("eval resume", as_json=as_json, result=result)


@eval_app.command("recompute-scores", rich_help_panel="Run")
def recompute_scores_cmd(
    experiment: str | None = typer.Option(
        None,
        "--experiment",
        help="Parent experiment id whose evidence is re-scored (required).",
    ),
    suite: str | None = typer.Option(
        "cm-eval-fixtures-core",
        "--suite",
        help="Suite id / metric pack context (default: cm-eval-fixtures-core).",
    ),
    fixture_root: Path | None = typer.Option(
        None,
        "--fixture-root",
        help="Optional fixture root override (tests/lab).",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    keep_last: int = typer.Option(
        DEFAULT_KEEP_LAST,
        "--keep-last",
        help="Checkpoint retention bound per suite family (default 10).",
    ),
    keep_checkpoint: bool = typer.Option(
        False,
        "--keep-checkpoint",
        help="Retain this recompute checkpoint even after success.",
    ),
    gold_mode: str = typer.Option("strict", "--gold-mode", help="Gold comparison mode."),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """Re-score evidence already written by a prior run."""
    from git_cg.eval.run_orchestrator import RunOrchestratorError, RunRequest, run_evaluation

    if not experiment:
        _emit_run_result(
            "eval recompute-scores",
            as_json=as_json,
            error=RunOrchestratorError(
                "recompute-scores requires --experiment",
                code="EVAL_USAGE",
                exit_code=2,
                hint="Pass the parent experiment id that retains evidence bundles.",
            ),
        )
        return

    try:
        result = run_evaluation(
            RunRequest(
                mode="recompute_scores",
                suite_id=suite or "cm-eval-fixtures-core",
                fixture_root=fixture_root,
                gold_mode=gold_mode,
                keep_last=keep_last,
                keep_checkpoint=keep_checkpoint,
                experiment_id=experiment,
                offline=True,
            )
        )
    except RunOrchestratorError as exc:
        _emit_run_result("eval recompute-scores", as_json=as_json, error=exc)
    except Exception as exc:
        _emit_run_result("eval recompute-scores", as_json=as_json, error=exc)
    else:
        _emit_run_result("eval recompute-scores", as_json=as_json, result=result)


# --------------------------------------------------------------------------
# S6 doctor / triage / review
# --------------------------------------------------------------------------


@eval_app.command("doctor", rich_help_panel="Inspect")
def doctor_cmd(
    suite: str = typer.Option(
        "cm-eval-fixtures-core",
        "--suite",
        help="Suite id to doctor (default: cm-eval-fixtures-core).",
    ),
    fixture_root: Path | None = typer.Option(
        None,
        "--fixture-root",
        help="Optional fixture root override (tests/lab).",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """Check local suite health (pins, metrics, fixtures).

    Offline, network-free. Fail-closed on floating ``latest`` pins and missing
    catalog/schema hashes. ``h.doctor_green`` aggregates block-severity checks
    only; warn-severity failures never flip green to red. Emits phantom-metric
    producers ``h.compat_hash_resume`` / ``h.doctor_green`` /
    ``h.export_config_resolved`` as ScoreResultV1 rows.
    """
    from git_cg.eval.cli_output import emit_human_line
    from git_cg.eval.doctor import run_local_doctor

    repo = _resolve_repo(None)
    report = run_local_doctor(repo_root=repo, suite_id=suite, fixture_root=fixture_root)
    if as_json:
        emit_json_envelope(build_envelope("eval doctor", ok=report.green, data=report.to_data()))
    else:
        emit_human_line(
            f"eval doctor: green={report.green} suite={report.suite_id} "
            f"checks={len(report.checks)} block_failures={len(report.to_data()['block_failures'])}",
            err=False,
        )
        for check in report.checks:
            if check.status == "pass":
                continue
            line = f"  [{check.severity}/{check.status}] {check.check_id}: {check.message}"
            if check.hint:
                line = f"{line} (hint: {check.hint})"
            emit_human_line(line, err=True)
    raise typer.Exit(code=report.exit_code)


@eval_app.command("amend-brief", rich_help_panel="Export & train")
def amend_brief_cmd(
    score_run_id: str = typer.Argument(..., help="Case score run id (rs_) to brief against."),
    session_thread_id: str | None = typer.Option(
        None, "--session-thread-id", help="Optional session twin (sess_) this brief belongs to."
    ),
    last_dogfood: int = typer.Option(3, "--last", min=0, help="Last-N dogfood/Lane C attachments."),
    doctor: bool = typer.Option(False, "--doctor", help="Include the doctor projection."),
    write: bool = typer.Option(True, "--write/--no-write", help="Persist under .eval/amend_briefs/."),
    root: Path | None = typer.Option(
        None,
        "--root",
        help="Repo root (defaults to discovery).",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """Build an amend brief from landed evaluation data.

    Advisory authority: summarizes score/failure/regime/family context and
    preference pairs; never auto-applies reruns, never accepts, never re-ranks.
    """
    from git_cg.eval.brief import AmendBriefError, amend_brief
    from git_cg.eval.cli_output import emit_human_line

    repo = _resolve_repo(root)
    try:
        data = amend_brief(
            repo,
            experiment_id=score_run_id,
            session_thread_id=session_thread_id,
            include_doctor=doctor,
            lane_c_last_n=last_dogfood,
            write=write,
        )
    except AmendBriefError as exc:
        _emit_slice5_error("eval amend-brief", exc, as_json=as_json)
        return
    if as_json:
        emit_json_envelope(build_envelope("eval amend-brief", ok=True, data=data))
    else:
        brief = data["brief"]
        emit_human_line(
            f"eval amend-brief: id={brief.get('id')} run={data.get('experiment_id') or score_run_id} "
            f"written={data.get('written')}",
            err=False,
        )
    raise typer.Exit(code=0)


@eval_app.command(
    "dogfood",
    hidden=True,  # dark-launch: callable, omitted from regular `git-cg eval --help`
    rich_help_panel="Advanced",
)
def dogfood_cmd(
    commit_message: str = typer.Option(..., "--commit-message", help="Candidate commit message."),
    mode: str = typer.Option("async", "--mode", help="off|sample|always|async."),
    profile: str = typer.Option("default_scrub", "--profile", help="Redaction profile."),
    population: list[str] | None = typer.Option(
        None, "--population", help="Deterministic sample population (repeatable)."
    ),
    seed: str | None = typer.Option(None, "--seed", help="Explicit sample seed."),
    sample_rate: float = typer.Option(0.10, "--sample-rate", min=0.0, max=1.0),
    capture_on: str = typer.Option("all", "--capture-on", help="pass|fail|all."),
    payload_path: Path | None = typer.Option(
        None, "--payload", help="Optional JSON payload for the Lane C judge (exists-check)."
    ),
    session_thread_id: str | None = typer.Option(None, "--session-thread-id"),
    trigger: str = typer.Option("cli", "--trigger", help="cli|pre_commit|post_commit|hook."),
    write: bool = typer.Option(True, "--write/--no-write"),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """Capture Lane C dogfood evidence for a candidate commit message.

    Dark-launched maintainer/operator surface: registered and callable as
    ``git-cg eval dogfood``, but hidden from regular ``git-cg eval --help`` so
    basic users do not see it in the default command menu.

    Lane C is advisory only: it never blocks the product commit path, never
    mutates intent/ranking, and async mode never awaits the judge outcome.
    """
    import hashlib

    from git_cg.eval.cli_output import emit_human_line
    from git_cg.eval.dogfood.capture import DOGFoodError, capture_dogfood

    if payload_path is not None and not payload_path.is_file():
        exc = DOGFoodError(
            f"payload file not found: {payload_path}",
            code="EVAL_USAGE",
            exit_code=2,
            hint="--payload must point at an existing JSON file for the Lane C judge.",
        )
        _emit_slice5_error("eval dogfood", exc, as_json=as_json)
        return
    repo = _resolve_repo(None)
    sha = hashlib.sha256(commit_message.encode("utf-8")).hexdigest()
    try:
        data = capture_dogfood(
            repo,
            message_sha256=sha,
            mode=mode,
            capture_on=capture_on,
            seed=seed,
            rate=sample_rate,
            population=population,
            session_thread_id=session_thread_id,
            notes=f"trigger={trigger} profile={profile}",
            write=write,
        )
    except DOGFoodError as exc:
        _emit_slice5_error("eval dogfood", exc, as_json=as_json)
        return
    if as_json:
        emit_json_envelope(build_envelope("eval dogfood", ok=True, data=data))
    else:
        att = data.get("attachment") or {}
        emit_human_line(
            f"eval dogfood: captured={data.get('captured')} mode={att.get('mode', mode)} "
            f"authority={att.get('authority', 'advisory')} written={bool(write)}",
            err=False,
        )
    raise typer.Exit(code=0)


@eval_app.command("train-export", rich_help_panel="Export & train")
def train_export_cmd(
    bundle_id: list[str] | None = typer.Option(
        None, "--bundle-id", help="Bundle id(s) to export; default exports all landed bundles."
    ),
    profile: str = typer.Option("train_rich", "--profile", help="Redaction profile (never raw_dev_unsafe)."),
    capture_on: str = typer.Option("all", "--capture-on", help="pass|fail|all corpus eligibility."),
    split_group_id: str | None = typer.Option(None, "--split-group-id"),
    notes: str | None = typer.Option(None, "--notes"),
    write: bool = typer.Option(True, "--write/--no-write"),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Validate + project export without writing (alias of --no-write).",
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """Export redacted training rows from landed bundles.

    Row scrub-failure policy: drop + report (scrub_report) + continue; never
    emit cleartext; no .eval/quarantine/. Antipattern/hard-negative rows never
    enter positive_gold (S6-G06). ``--dry-run`` is the NTH-03 alias of
    ``--no-write`` (validate + would-write summary; zero store mutation).
    """
    from git_cg.eval.cli_output import emit_human_line
    from git_cg.eval.train_export import TrainExportError, train_export

    repo = _resolve_repo(None)
    try:
        data = train_export(
            repo,
            bundle_ids=bundle_id,
            redaction_profile=profile,
            capture_on=capture_on,
            split_group_id=split_group_id,
            notes=notes,
            write=write,
            dry_run=dry_run if dry_run else None,
        )
    except TrainExportError as exc:
        _emit_slice5_error("eval train-export", exc, as_json=as_json)
        return
    if as_json:
        emit_json_envelope(build_envelope("eval train-export", ok=True, data=data))
    else:
        scrub = data["scrub_report"]
        emit_human_line(
            f"eval train-export: id={data['export_id']} rows={data['row_count']} "
            f"dropped={len(data['dropped_row_ids'])} scrub={scrub['status']} "
            f"written={data['written']} dry_run={data.get('dry_run', False)}",
            err=False,
        )
        if data.get("dry_run") and isinstance(data.get("would_write"), dict):
            ww = data["would_write"]
            emit_human_line(
                f"  would_write: export={ww.get('export_path')} rows_dir={ww.get('rows_dir')} "
                f"row_count={ww.get('row_count')}",
                err=False,
            )
    raise typer.Exit(code=0)


@eval_app.command("triage", rich_help_panel="Inspect")
def triage_cmd(
    suite: str = typer.Option(
        "cm-eval-fixtures-core",
        "--suite",
        help="Suite id for the doctor section (default: cm-eval-fixtures-core).",
    ),
    fixture_root: Path | None = typer.Option(
        None,
        "--fixture-root",
        help="Optional fixture root override for the doctor section.",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    experiment_id: str | None = typer.Option(
        None,
        "--experiment-id",
        help="Experiment id for failures/explain (defaults to latest local run).",
    ),
    case_id: str | None = typer.Option(
        None,
        "--case",
        help="Case id for explain (auto-selects when exactly one failing case).",
    ),
    skip_doctor: bool = typer.Option(False, "--skip-doctor", help="Skip the doctor section."),
    skip_failures: bool = typer.Option(False, "--skip-failures", help="Skip the failures section."),
    skip_explain: bool = typer.Option(False, "--skip-explain", help="Skip the explain section."),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """One-shot advisory view: doctor + failures + explain.

    Composes library engines only — never nests Typer presentation commands.
    Not score law: does not promote gold, rank intents, or revive Opik
    ``user_acceptance`` threshold triage. Emits one human report or one
    ``cli_output_envelope_v1`` with an ``eval_triage_v0`` data payload.
    """
    from git_cg.eval.cli_output import emit_human_line
    from git_cg.eval.explain import ExplainError
    from git_cg.eval.triage import TriageError, run_triage

    repo = _resolve_repo(None)
    try:
        report = run_triage(
            repo,
            suite_id=suite,
            fixture_root=fixture_root,
            experiment_id=experiment_id,
            case_id=case_id,
            skip_doctor=skip_doctor,
            skip_failures=skip_failures,
            skip_explain=skip_explain,
        )
    except (TriageError, ExplainError) as exc:
        _emit_slice5_error("eval triage", exc, as_json=as_json)
        return

    data = report.to_data()
    if as_json:
        emit_json_envelope(build_envelope("eval triage", ok=report.ok, data=data))
    else:
        doctor = data.get("doctor") or {}
        failures = data.get("failures") or {}
        explain = data.get("explain")
        emit_human_line(
            "eval triage: "
            f"authority={data.get('authority')} "
            f"sections_run={','.join(data.get('sections_run') or []) or '-'} "
            f"doctor_green={doctor.get('green') if doctor else 'skipped'} "
            f"failing_cases={failures.get('case_count') if failures else 'skipped'} "
            f"explain={'yes' if explain else 'no'}",
            err=False,
        )
        for note in data.get("notes") or []:
            emit_human_line(f"  note: {note}", err=False)
        if doctor:
            block = doctor.get("block_failures") or []
            if block:
                emit_human_line(
                    f"  doctor block_failures={','.join(block)}",
                    err=True,
                )
            for check in doctor.get("checks") or []:
                if check.get("status") == "pass":
                    continue
                line = (
                    f"  [doctor {check.get('severity')}/{check.get('status')}] "
                    f"{check.get('check_id')}: {check.get('message')}"
                )
                if check.get("hint"):
                    line = f"{line} (hint: {check['hint']})"
                emit_human_line(line, err=True)
        if failures:
            for case in failures.get("failing_cases") or []:
                emit_human_line(
                    f"  fail {case.get('case_id')}: "
                    f"metrics={','.join(case.get('metric_ids') or []) or '-'} "
                    f"failures={','.join(case.get('failure_ids') or []) or '-'}",
                    err=False,
                )
        if explain:
            for case in explain.get("cases") or []:
                emit_human_line(
                    f"  explain {case.get('case_id')}: blame={case.get('blame_span') or '-'} "
                    f"first_divergent={case.get('first_divergent_span') or '-'} "
                    f"artifact_class={case.get('artifact_class') or '-'}",
                    err=False,
                )
                emit_human_line(f"    replay: {case.get('replay_command')}", err=False)
        emit_human_line(
            "  replacements: " + ", ".join(data.get("replacements_for_legacy_script") or []),
            err=False,
        )
    raise typer.Exit(code=report.exit_code)


@eval_app.command("failures", rich_help_panel="Inspect")
def failures_cmd(
    experiment_id: str | None = typer.Option(
        None, "--experiment-id", help="Experiment id (defaults to latest local run)."
    ),
    regime: str | None = typer.Option(
        None, "--regime", help="Deterministic filter: regime label from fingerprint inputs (e.g. A|B)."
    ),
    family: str | None = typer.Option(None, "--family", help="Deterministic filter: score family (e.g. I|H|gate)."),
    failure_id: str | None = typer.Option(
        None, "--failure-id", help="Deterministic filter: require this failure_id on a failing score."
    ),
    severity: str | None = typer.Option(None, "--severity", help="Deterministic filter: block|warn|info."),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """List failing cases with metric and failure ids.

    Optional NTH-02 filters (``--regime``, ``--family``, ``--failure-id``,
    ``--severity``) are AND-combined and documented in the API map. The base
    unfiltered list remains the S6-D01 contract.
    """
    from git_cg.eval.cli_output import emit_human_line
    from git_cg.eval.explain import ExplainError, list_failures

    repo = _resolve_repo(None)
    try:
        data = list_failures(
            repo,
            experiment_id=experiment_id,
            regime=regime,
            family=family,
            failure_id=failure_id,
            severity=severity,
        )
    except ExplainError as exc:
        _emit_slice5_error("eval failures", exc, as_json=as_json)
        return
    if as_json:
        emit_json_envelope(build_envelope("eval failures", ok=True, data=data))
    else:
        filt = data.get("filters") if isinstance(data.get("filters"), dict) else {}
        active = {k: v for k, v in filt.items() if v is not None}
        emit_human_line(
            f"eval failures: experiment={data['experiment_id']} failing_cases={data['case_count']}"
            + (f" filters={active}" if active else ""),
            err=False,
        )
        for case in data["failing_cases"]:
            emit_human_line(
                f"  {case['case_id']}: metrics={','.join(case['metric_ids']) or '-'} "
                f"failures={','.join(case['failure_ids']) or '-'}",
                err=False,
            )
    raise typer.Exit(code=0)


@eval_app.command("explain", rich_help_panel="Inspect")
def explain_cmd(
    experiment_id: str | None = typer.Option(
        None, "--experiment-id", help="Experiment id (defaults to latest local run)."
    ),
    case_id: str | None = typer.Option(None, "--case", help="Case id within the experiment."),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """Show a deterministic explanation for a failing case."""
    from git_cg.eval.cli_output import emit_human_line
    from git_cg.eval.explain import ExplainError, explain

    repo = _resolve_repo(None)
    try:
        data = explain(repo, experiment_id=experiment_id, case_id=case_id)
    except ExplainError as exc:
        _emit_slice5_error("eval explain", exc, as_json=as_json)
        return
    if as_json:
        emit_json_envelope(build_envelope("eval explain", ok=True, data=data))
    else:
        for case in data["cases"]:
            emit_human_line(
                f"eval explain: {case['case_id']} blame={case['blame_span'] or '-'} "
                f"first_divergent={case['first_divergent_span'] or '-'} "
                f"artifact_class={case['artifact_class'] or '-'}",
                err=False,
            )
            emit_human_line(
                f"  failures={','.join(case['failure_ids']) or '-'} "
                f"prevention={','.join(case['prevention_ids']) or '-'}",
                err=False,
            )
            emit_human_line(f"  replay: {case['replay_command']}", err=False)
    raise typer.Exit(code=0)


@eval_app.command("compare", rich_help_panel="Inspect")
def compare_cmd(
    a_experiment_id: str = typer.Option(..., "--a-experiment-id", help="Left experiment id."),
    a_case_id: str = typer.Option(..., "--a-case", help="Left case id."),
    b_experiment_id: str = typer.Option(..., "--b-experiment-id", help="Right experiment id."),
    b_case_id: str = typer.Option(..., "--b-case", help="Right case id."),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """Diff two cases (structure and metrics)."""
    from git_cg.eval.cli_output import emit_human_line
    from git_cg.eval.explain import ExplainError, compare

    repo = _resolve_repo(None)
    try:
        data = compare(
            repo,
            a_experiment_id=a_experiment_id,
            a_case_id=a_case_id,
            b_experiment_id=b_experiment_id,
            b_case_id=b_case_id,
        )
    except ExplainError as exc:
        _emit_slice5_error("eval compare", exc, as_json=as_json)
        return
    if as_json:
        emit_json_envelope(build_envelope("eval compare", ok=True, data=data))
    else:
        emit_human_line(
            f"eval compare: source={data['compare_source']} "
            f"lineage_linked={data['lineage_linked']} "
            f"metric_changes={len(data['metric_delta'])}",
            err=False,
        )
        for row in data["metric_delta"]:
            emit_human_line(
                f"  {row['metric_id']}: a={row['a']['passed']} b={row['b']['passed']}",
                err=False,
            )
    raise typer.Exit(code=0)


@eval_app.command("replay", rich_help_panel="Advanced")
def replay_cmd(
    bundle: str | None = typer.Option(
        None,
        "--bundle",
        help="Source ape_bundle_v1 path or accept-path session_thread_id/stem.",
    ),
    experiment_id: str | None = typer.Option(
        None, "--experiment-id", help="Experiment id (with --case) for explain-linked replay."
    ),
    case_id: str | None = typer.Option(None, "--case", help="Case id within the experiment."),
    notes: str | None = typer.Option(None, "--notes", help="Optional notes on the compare record."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate and project without writing."),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """Replay generation into a new bundle (source unchanged)."""
    from git_cg.eval.cli_output import emit_human_line
    from git_cg.eval.replay import ReplayError, replay

    repo = _resolve_repo(None)
    try:
        result = replay(
            repo,
            bundle=bundle,
            experiment_id=experiment_id,
            case_id=case_id,
            notes=notes,
            dry_run=dry_run,
        )
    except ReplayError as exc:
        _emit_slice5_error("eval replay", exc, as_json=as_json)
        return
    compare = result["compare"]
    data = {
        "compare": compare,
        "source_path": result["source_path"],
        "compare_path": result["compare_path"],
        "replay_bundle_path": result["replay_bundle_path"],
        "source_bundle_hash": result["source_bundle_hash"],
        "replay_bundle_hash": result["replay_bundle_hash"],
        "source_mutated": result["source_mutated"],
        "dry_run": result["dry_run"],
    }
    if as_json:
        emit_json_envelope(build_envelope("eval replay", ok=True, data=data))
    else:
        emit_human_line(
            f"eval replay: replay_id={compare['replay_id']} "
            f"status={compare['regression_status']} lineage_ok={compare['lineage_ok']} "
            f"source_mutated={result['source_mutated']} dry_run={dry_run}",
            err=False,
        )
        emit_human_line(f"  compare: {result['compare_path']}", err=False)
        emit_human_line(f"  bundle:  {result['replay_bundle_path']}", err=False)
    raise typer.Exit(code=0)


@eval_app.command("promote", rich_help_panel="Advanced")
def promote_cmd(
    bundle: str = typer.Option(..., "--bundle", help="Source ape_bundle_v1 path/id (acceptpath or replay)."),
    destination: str = typer.Option(
        ...,
        "--destination",
        help=(
            "Terminal destination: fixture_lane_a|hard_negative|preference_pair|observability_fixture|quarantine|reject"
        ),
    ),
    owner: str = typer.Option(..., "--owner", help="Promotion owner (opaque local handle)."),
    label: str = typer.Option(..., "--label", help="Promotion label (not silent gold)."),
    provenance: str = typer.Option(..., "--provenance", help="Provenance token (not popularity/accept alone)."),
    redaction_profile: str = typer.Option(
        ...,
        "--redaction-profile",
        help="R14 redaction profile for the promoted artifact.",
    ),
    stage: str = typer.Option(
        "scrubbed_candidate",
        "--stage",
        help="Source stage: failure_or_capture|scrubbed_candidate (default scrubbed_candidate).",
    ),
    split_group_id: str | None = typer.Option(
        None, "--split-group-id", help="Contamination unit (defaults from bundle/session)."
    ),
    review_id: str | None = typer.Option(
        None, "--review-id", help="Optional adjudicated review_queue id (advisory only)."
    ),
    notes: str | None = typer.Option(None, "--notes", help="Free-text notes."),
    popularity_signal: bool = typer.Option(
        False,
        "--popularity-signal",
        help="Mark popularity/user_acceptance signal (cannot promote golden).",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate decision without writing."),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """Promote a scrubbed candidate with contamination checks."""
    from git_cg.eval.cli_output import emit_human_line
    from git_cg.eval.promote import PromoteError, promote

    repo = _resolve_repo(None)
    try:
        result = promote(
            repo,
            bundle=bundle,
            destination=destination,
            owner=owner,
            label=label,
            provenance=provenance,
            redaction_profile=redaction_profile,
            stage=stage,
            split_group_id=split_group_id,
            review_id=review_id,
            notes=notes,
            popularity_signal=popularity_signal,
            dry_run=dry_run,
        )
    except PromoteError as exc:
        # Surface denial_reason + retained candidate decision when present (S6-E09).
        if as_json:
            from git_cg.eval.cli_output import envelope_message

            err = envelope_message(getattr(exc, "code", "EVAL_USAGE"), str(exc), hint=getattr(exc, "hint", None))
            data: dict[str, object] = {
                "accepted": False,
                "denial_reason": getattr(exc, "denial_reason", None),
            }
            decision = getattr(exc, "decision", None)
            decision_path = getattr(exc, "decision_path", None)
            if isinstance(decision, dict):
                data["decision"] = decision
            if isinstance(decision_path, str) and decision_path:
                data["decision_path"] = decision_path
            emit_json_envelope(build_envelope("eval promote", ok=False, data=data, errors=[err]))
            raise typer.Exit(code=int(getattr(exc, "exit_code", 2))) from None
        _emit_slice5_error("eval promote", exc, as_json=False)
        denial = getattr(exc, "denial_reason", None)
        decision_path = getattr(exc, "decision_path", None)
        if denial:
            emit_human_line(f"  denial_reason: {denial}", err=True)
        if decision_path:
            emit_human_line(f"  denial_audit: {decision_path}", err=True)
        return
    data = {
        "decision": result["decision"],
        "decision_path": result["decision_path"],
        "artifact_path": result["artifact_path"],
        "accepted": result["accepted"],
        "denial_reason": result["denial_reason"],
        "dry_run": result["dry_run"],
    }
    if as_json:
        emit_json_envelope(build_envelope("eval promote", ok=True, data=data))
    else:
        decision = result["decision"]
        emit_human_line(
            f"eval promote: accepted={result['accepted']} id={decision.get('promotion_id')} "
            f"destination={decision.get('destination')} dry_run={dry_run}",
            err=False,
        )
        emit_human_line(f"  decision: {result['decision_path']}", err=False)
        if result.get("artifact_path"):
            emit_human_line(f"  artifact: {result['artifact_path']}", err=False)
    raise typer.Exit(code=0)


@eval_app.command("diagnose", rich_help_panel="Inspect")
def diagnose_cmd(
    experiment_id: str | None = typer.Option(
        None, "--experiment-id", help="Experiment id (defaults to latest local run)."
    ),
    case_id: str | None = typer.Option(None, "--case", help="Case id within the experiment."),
    code: str | None = typer.Option(None, "--code", help="Diagnostic code (defaults to first failure_id)."),
    title: str | None = typer.Option(None, "--title", help="Issue title."),
    product_impact: str = typer.Option(
        "unknown", "--product-impact", help="accept_path|golden|train|export|docs|unknown."
    ),
    owner: str | None = typer.Option(None, "--owner", help="Issue owner."),
    notes: str | None = typer.Option(None, "--notes", help="Free-text notes."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Validate + project issue without writing issues/diagnostics."
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """Create or update a diagnostic issue from a failure."""
    from git_cg.eval.cli_output import emit_human_line
    from git_cg.eval.diagnose import DiagnoseError, diagnose

    repo = _resolve_repo(None)
    try:
        result = diagnose(
            repo,
            experiment_id=experiment_id,
            case_id=case_id,
            code=code,
            title=title,
            product_impact=product_impact,
            owner=owner,
            notes=notes,
            dry_run=dry_run,
        )
    except DiagnoseError as exc:
        _emit_slice5_error("eval diagnose", exc, as_json=as_json)
        return
    issue = result["issue"]
    data = {
        "issue": issue,
        "upserted": result["upserted"],
        "dry_run": result.get("dry_run", False),
        "would_write": result.get("would_write"),
    }
    if as_json:
        emit_json_envelope(build_envelope("eval diagnose", ok=True, data=data))
    else:
        verb = "upserted" if result["upserted"] else "created"
        if dry_run:
            verb = f"dry-run-{verb}"
        emit_human_line(
            f"eval diagnose: {verb} {issue['issue_id']} status={issue['status']} "
            f"occurrences={issue['occurrence_count']} fingerprint={issue['fingerprint'][:12]} "
            f"dry_run={dry_run}",
            err=False,
        )
        ww = result.get("would_write") if isinstance(result.get("would_write"), dict) else None
        if dry_run and ww:
            emit_human_line(
                f"  would_write: issue={ww.get('issue_path')} diagnostics={ww.get('diagnostics_path')}",
                err=False,
            )
    raise typer.Exit(code=0)


# --------------------------------------------------------------------------
# Nested: review queue (HITL / human_review_v1)
# --------------------------------------------------------------------------


# review_app registered near module top for help-panel order.


@review_app.command("enqueue")
def review_enqueue_cmd(
    case_id: str | None = typer.Option(None, "--case", help="Case id under review."),
    bundle_id: str | None = typer.Option(None, "--bundle-id", help="Bundle id under review."),
    reviewer: str = typer.Option(..., "--reviewer", help="Opaque local reviewer handle (not email)."),
    redaction_profile: str = typer.Option(
        "meta_eval_scrub",
        "--redaction-profile",
        help="R14 redaction profile (default meta_eval_scrub).",
    ),
    craft_rating: float | None = typer.Option(None, "--craft-rating", help="human.craft_rating score."),
    gold_dispute: str | None = typer.Option(None, "--gold-dispute", help="human.gold_dispute: true|false."),
    regime_label: str | None = typer.Option(None, "--regime-label", help="human.regime_label: A|B|unknown."),
    notes: str | None = typer.Option(None, "--notes", help="Free-text notes."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate without writing."),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """Enqueue an advisory human-review item."""
    from git_cg.eval.cli_output import emit_human_line
    from git_cg.eval.review_queue import ReviewQueueError, enqueue

    repo = _resolve_repo(None)
    gd: bool | None = None
    if gold_dispute is not None:
        token = gold_dispute.strip().lower()
        if token in {"1", "true", "yes", "y"}:
            gd = True
        elif token in {"0", "false", "no", "n"}:
            gd = False
        else:
            from git_cg.eval.cli_output import emit_human_line, envelope_message

            err = envelope_message("EVAL_USAGE", f"invalid --gold-dispute: {gold_dispute!r}", hint="Use true|false")
            if as_json:
                emit_json_envelope(build_envelope("eval review enqueue", ok=False, errors=[err]))
            else:
                emit_human_line(f"eval review enqueue: {err['message']}", err=True)
            raise typer.Exit(code=2)
    try:
        result = enqueue(
            repo,
            case_id=case_id,
            bundle_id=bundle_id,
            reviewer=reviewer,
            redaction_profile=redaction_profile,
            craft_rating=craft_rating,
            gold_dispute=gd,
            regime_label=regime_label,
            notes=notes,
            dry_run=dry_run,
        )
    except ReviewQueueError as exc:
        _emit_slice5_error("eval review enqueue", exc, as_json=as_json)
        return
    item = result["item"]
    if as_json:
        emit_json_envelope(build_envelope("eval review enqueue", ok=True, data=result))
    else:
        emit_human_line(
            f"eval review enqueue: {item['review_id']} status={item['status']} dry_run={dry_run}",
            err=False,
        )
    raise typer.Exit(code=0)


@review_app.command("list")
def review_list_cmd(
    status: str | None = typer.Option(None, "--status", help="Filter: pending|in_review|adjudicated|dismissed."),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """List local review-queue items."""
    from git_cg.eval.cli_output import emit_human_line
    from git_cg.eval.review_queue import ReviewQueueError, list_reviews

    repo = _resolve_repo(None)
    try:
        data = list_reviews(repo, status=status)
    except ReviewQueueError as exc:
        _emit_slice5_error("eval review list", exc, as_json=as_json)
        return
    if as_json:
        emit_json_envelope(build_envelope("eval review list", ok=True, data=data))
    else:
        emit_human_line(f"eval review list: {data['review_count']} item(s)", err=False)
        for row in data["reviews"]:
            emit_human_line(
                f"  {row['review_id']}: [{row['status']}] case={row.get('case_id') or '-'} "
                f"reviewer={row.get('reviewer') or '-'}",
                err=False,
            )
    raise typer.Exit(code=0)


@review_app.command("rollup")
def review_rollup_cmd(
    case_id: str | None = typer.Option(None, "--case", help="Optional case_id filter."),
    bundle_id: str | None = typer.Option(None, "--bundle-id", help="Optional bundle_id filter."),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """Roll up multi-rater advisory scores for review items.

    Read-only dimension/outcome majority + craft spread. Authority stays
    advisory; never sole-promotes gold.
    """
    from git_cg.eval.cli_output import emit_human_line
    from git_cg.eval.review_queue import ReviewQueueError, rollup_reviews

    repo = _resolve_repo(None)
    try:
        data = rollup_reviews(repo, case_id=case_id, bundle_id=bundle_id)
    except ReviewQueueError as exc:
        _emit_slice5_error("eval review rollup", exc, as_json=as_json)
        return
    if as_json:
        emit_json_envelope(build_envelope("eval review rollup", ok=True, data=data))
    else:
        emit_human_line(
            f"eval review rollup: groups={data['rollup_count']} authority=advisory "
            f"can_sole_promote_gold={data['can_sole_promote_gold']}",
            err=False,
        )
        for row in data["rollups"]:
            craft = (row.get("dimensions") or {}).get("human.craft_rating") or {}
            dispute = (row.get("dimensions") or {}).get("human.gold_dispute") or {}
            regime = (row.get("dimensions") or {}).get("human.regime_label") or {}
            outcomes = row.get("outcomes") or {}
            emit_human_line(
                f"  {row['target_kind']}={row['target_id']}: reviewers={row['reviewer_count']} "
                f"reviews={row['review_count']} craft_mean={craft.get('mean')} "
                f"craft_disagreement={craft.get('disagreement')} "
                f"dispute={dispute.get('majority')} regime={regime.get('majority')} "
                f"outcome={outcomes.get('majority')}",
                err=False,
            )
    raise typer.Exit(code=0)


@review_app.command("show")
def review_show_cmd(
    review_id: str = typer.Argument(..., help="Review id."),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """Show one local review-queue item."""
    from git_cg.eval.cli_output import emit_human_line
    from git_cg.eval.review_queue import ReviewQueueError, show_review

    repo = _resolve_repo(None)
    try:
        data = show_review(repo, review_id=review_id)
    except ReviewQueueError as exc:
        _emit_slice5_error("eval review show", exc, as_json=as_json)
        return
    item = data["item"]
    if as_json:
        emit_json_envelope(build_envelope("eval review show", ok=True, data=data))
    else:
        review = item.get("review") or {}
        emit_human_line(
            f"eval review show: {item['review_id']} status={item['status']} "
            f"authority={review.get('authority', 'advisory')}",
            err=False,
        )
        if item.get("adjudication"):
            adj = item["adjudication"]
            emit_human_line(
                f"  outcome={adj.get('outcome')} ref={adj.get('outcome_ref')}",
                err=False,
            )
    raise typer.Exit(code=0)


@review_app.command("claim")
def review_claim_cmd(
    review_id: str = typer.Argument(..., help="Review id."),
    reviewer: str = typer.Option(..., "--reviewer", help="Opaque local reviewer handle."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate without writing."),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """Claim a pending review item (pending → in_review)."""
    from git_cg.eval.cli_output import emit_human_line
    from git_cg.eval.review_queue import ReviewQueueError, claim

    repo = _resolve_repo(None)
    try:
        result = claim(repo, review_id=review_id, reviewer=reviewer, dry_run=dry_run)
    except ReviewQueueError as exc:
        _emit_slice5_error("eval review claim", exc, as_json=as_json)
        return
    item = result["item"]
    if as_json:
        emit_json_envelope(build_envelope("eval review claim", ok=True, data=result))
    else:
        emit_human_line(
            f"eval review claim: {item['review_id']} status={item['status']} "
            f"claimed_by={item.get('claimed_by')} dry_run={dry_run}",
            err=False,
        )
    raise typer.Exit(code=0)


@review_app.command("adjudicate")
def review_adjudicate_cmd(
    review_id: str = typer.Argument(..., help="Review id."),
    outcome: str = typer.Option(
        ...,
        "--outcome",
        help="Typed outcome: approve_promote|reject|needs_work|dismiss.",
    ),
    adjudicator: str | None = typer.Option(None, "--adjudicator", help="Opaque adjudicator handle."),
    destination_hint: str | None = typer.Option(
        None, "--destination-hint", help="Optional promote destination hint (advisory)."
    ),
    notes: str | None = typer.Option(None, "--notes", help="Free-text notes."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate without writing."),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """Adjudicate an in_review item (emits typed outcome_ref; never writes gold)."""
    from git_cg.eval.cli_output import emit_human_line
    from git_cg.eval.review_queue import ReviewQueueError, adjudicate

    repo = _resolve_repo(None)
    try:
        result = adjudicate(
            repo,
            review_id=review_id,
            outcome=outcome,
            adjudicator=adjudicator,
            destination_hint=destination_hint,
            notes=notes,
            dry_run=dry_run,
        )
    except ReviewQueueError as exc:
        _emit_slice5_error("eval review adjudicate", exc, as_json=as_json)
        return
    item = result["item"]
    if as_json:
        emit_json_envelope(build_envelope("eval review adjudicate", ok=True, data=result))
    else:
        emit_human_line(
            f"eval review adjudicate: {item['review_id']} status={item['status']} "
            f"outcome_ref={result.get('outcome_ref')} dry_run={dry_run}",
            err=False,
        )
    raise typer.Exit(code=0)


@review_app.command("dismiss")
def review_dismiss_cmd(
    review_id: str = typer.Argument(..., help="Review id."),
    reason: str = typer.Option(..., "--reason", help="Required dismissal reason."),
    adjudicator: str | None = typer.Option(None, "--adjudicator", help="Opaque adjudicator handle."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate without writing."),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """Dismiss a pending/in_review item (terminal)."""
    from git_cg.eval.cli_output import emit_human_line
    from git_cg.eval.review_queue import ReviewQueueError, dismiss

    repo = _resolve_repo(None)
    try:
        result = dismiss(
            repo,
            review_id=review_id,
            reason=reason,
            adjudicator=adjudicator,
            dry_run=dry_run,
        )
    except ReviewQueueError as exc:
        _emit_slice5_error("eval review dismiss", exc, as_json=as_json)
        return
    item = result["item"]
    if as_json:
        emit_json_envelope(build_envelope("eval review dismiss", ok=True, data=result))
    else:
        emit_human_line(
            f"eval review dismiss: {item['review_id']} status={item['status']} dry_run={dry_run}",
            err=False,
        )
    raise typer.Exit(code=0)


# --------------------------------------------------------------------------
# Nested: session / thread
# --------------------------------------------------------------------------


# session_app registered near module top for help-panel order.


@session_app.command("show")
def session_show_cmd(
    session_id: str = typer.Option(..., "--id", help="Session id (sess_ or sessmeta_)."),
    root: Path | None = typer.Option(
        None,
        "--root",
        help="Repo root (defaults to discovery).",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """Show one local commit session.

    Read-only: no Opik reach, no chat timeline, no graph browser, no accept
    authority, no rerun, no ranking mutation.
    """
    from git_cg.eval.cli_output import emit_human_line
    from git_cg.eval.sessions import SessionsError, show_session

    repo = _resolve_repo(root)
    try:
        data = show_session(repo, session_id)
    except SessionsError as exc:
        _emit_slice5_error("eval session show", exc, as_json=as_json)
        return
    if as_json:
        emit_json_envelope(build_envelope("eval session show", ok=True, data=data))
    else:
        sess = data["session"]
        meta = sess.get("meta") or {}
        emit_human_line(
            f"eval session show: id={sess.get('id')} lifecycle={meta.get('lifecycle', '-')} "
            f"schema={sess.get('schema_version', '-')} network={data.get('network', False)}",
            err=False,
        )
    raise typer.Exit(code=0)


# thread_app registered near module top for help-panel order.


@thread_app.command("show")
def thread_show_cmd(
    thread_id: str = typer.Option(..., "--id", help="Thread/session id (sess_ or sessmeta_)."),
    root: Path | None = typer.Option(
        None,
        "--root",
        help="Repo root (defaults to discovery).",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """Show one local session thread.

    Read-only: no Opik reach, no chat timeline, no graph browser, no accept
    authority, no rerun, no ranking mutation.
    """
    from git_cg.eval.cli_output import emit_human_line
    from git_cg.eval.sessions import SessionsError, show_thread

    repo = _resolve_repo(root)
    try:
        data = show_thread(repo, thread_id)
    except SessionsError as exc:
        _emit_slice5_error("eval thread show", exc, as_json=as_json)
        return
    if as_json:
        emit_json_envelope(build_envelope("eval thread show", ok=True, data=data))
    else:
        thread = data["thread"]
        n = thread.get("message_version_count")
        if n is None:
            n = len(thread.get("message_versions") or [])
        emit_human_line(
            f"eval thread show: id={thread.get('id')} "
            f"message_versions={n} lifecycle={data.get('lifecycle', '-')} "
            f"network={data.get('network', False)}",
            err=False,
        )
    raise typer.Exit(code=0)


# --------------------------------------------------------------------------
# Nested: issue
# --------------------------------------------------------------------------


# issue_app registered near module top for help-panel order.


@issue_app.command("list")
def issue_list_cmd(
    status: str | None = typer.Option(
        None, "--status", help="Filter by status (open|acknowledged|resolved|suppressed|reopened)."
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """List local diagnostic issues (newest last_seen first)."""
    from git_cg.eval.cli_output import emit_human_line
    from git_cg.eval.diagnose import DiagnoseError, list_issues

    repo = _resolve_repo(None)
    try:
        data = list_issues(repo, status=status)
    except DiagnoseError as exc:
        _emit_slice5_error("eval issue list", exc, as_json=as_json)
        return
    if as_json:
        emit_json_envelope(build_envelope("eval issue list", ok=True, data=data))
    else:
        emit_human_line(f"eval issue list: {data['issue_count']} issue(s)", err=False)
        for issue in data["issues"]:
            emit_human_line(
                f"  {issue['issue_id']}: [{issue['status']}/{issue['severity']}] "
                f"{issue['code']} occurrences={issue['occurrence_count']}",
                err=False,
            )
    raise typer.Exit(code=0)


@issue_app.command("show")
def issue_show_cmd(
    issue_id: str = typer.Argument(..., help="Issue id."),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """Show one local diagnostic issue."""
    from git_cg.eval.cli_output import emit_human_line
    from git_cg.eval.diagnose import DiagnoseError, show_issue

    repo = _resolve_repo(None)
    try:
        data = show_issue(repo, issue_id=issue_id)
    except DiagnoseError as exc:
        _emit_slice5_error("eval issue show", exc, as_json=as_json)
        return
    issue = data["issue"]
    if as_json:
        emit_json_envelope(build_envelope("eval issue show", ok=True, data=data))
    else:
        emit_human_line(
            f"eval issue show: {issue['issue_id']} [{issue['status']}/{issue['severity']}] {issue['title']}",
            err=False,
        )
        emit_human_line(
            f"  fingerprint={issue['fingerprint']} occurrences={issue['occurrence_count']}",
            err=False,
        )
        emit_human_line(
            f"  failure_ids={','.join(issue['failure_ids']) or '-'} metric_ids={','.join(issue['metric_ids']) or '-'}",
            err=False,
        )
        if issue.get("suggested_surfaces"):
            emit_human_line(f"  surfaces={','.join(issue['suggested_surfaces'])}", err=False)
    raise typer.Exit(code=0)


@issue_app.command("resolve")
def issue_resolve_cmd(
    issue_id: str = typer.Argument(..., help="Issue id."),
    resolution_evidence: str = typer.Option(..., "--resolution-evidence", help="Required fix-verification evidence."),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """Mark a local diagnostic issue resolved (requires --resolution-evidence)."""
    _run_issue_transition(
        "eval issue resolve",
        issue_id=issue_id,
        target="resolved",
        resolution_evidence=resolution_evidence,
        reason=None,
        as_json=as_json,
    )


@issue_app.command("reopen")
def issue_reopen_cmd(
    issue_id: str = typer.Argument(..., help="Issue id."),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """Reopen a previously resolved/suppressed local diagnostic issue."""
    _run_issue_transition(
        "eval issue reopen",
        issue_id=issue_id,
        target="reopened",
        resolution_evidence=None,
        reason=None,
        as_json=as_json,
    )


@issue_app.command("suppress")
def issue_suppress_cmd(
    issue_id: str = typer.Argument(..., help="Issue id."),
    reason: str = typer.Option(..., "--reason", help="Required suppression reason."),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """Suppress a local diagnostic issue (requires --reason)."""
    _run_issue_transition(
        "eval issue suppress",
        issue_id=issue_id,
        target="suppressed",
        resolution_evidence=None,
        reason=reason,
        as_json=as_json,
    )


# --------------------------------------------------------------------------
# Nested: opik (canonical config + doctor)
# --------------------------------------------------------------------------


# opik_app / opik_config_app registered near module top for help-panel order.


def _config_show_impl(*, as_json: bool = False, deprecated_from: str | None = None) -> None:
    """Shared secret-safe config show implementation (canonical + alias)."""
    import json
    import os

    from git_cg.eval.mirror.config import (
        OpikConfigError,
        mask_secret,
        mode_fallback_token,
        operator_config_health,
        public_config_view,
        resolve_opik_config,
    )
    from git_cg.eval.mirror.health import ExportHealth
    from git_cg.eval.mirror.result import build_mirror_result

    warnings: list[dict[str, str]] = []
    if deprecated_from is not None:
        warning = deprecation_warning(
            deprecated=deprecated_from,
            canonical="git-cg eval opik config show",
            removal_target=REMOVAL_TARGET,
        )
        warnings.append(warning)
        if not as_json:
            emit_deprecation_human(
                deprecated=deprecated_from,
                canonical="git-cg eval opik config show",
                removal_target=REMOVAL_TARGET,
            )

    try:
        config = resolve_opik_config()
    except OpikConfigError as exc:
        result = build_mirror_result(
            mode="off",
            health=ExportHealth.CONFIG_ERROR,
            notes=(f"config_error: {exc}",),
        )
        payload = {
            "config": None,
            "secrets": {"api_key": None, "api_key_present": False},
            "health_hint": ExportHealth.CONFIG_ERROR.value,
            "mirror_result": result.to_dict(),
        }
        if as_json:
            emit_json_envelope(
                build_envelope(
                    "eval opik config show",
                    ok=False,
                    data=payload,
                    errors=[
                        {
                            "code": "EVAL_CONFIG_ERROR",
                            "message": f"invalid (fail-closed): {exc}",
                        }
                    ],
                    warnings=warnings,
                )
            )
        else:
            typer.echo(json.dumps(result.to_dict(), indent=2, sort_keys=True))
            typer.echo(f"config show: invalid (fail-closed): {exc}", err=True)
        raise typer.Exit(code=2) from None

    view = public_config_view(config)
    ambient_key = os.environ.get("OPIK_API_KEY") or os.environ.get("GIT_CG_OPIK_API_KEY")
    masked = {
        "api_key": mask_secret(ambient_key) if ambient_key else None,
        "api_key_present": bool(ambient_key),
    }
    health_hint = operator_config_health(config)
    payload = {
        "config": view,
        "secrets": masked,
        "health_hint": health_hint,
        "mirror_result": build_mirror_result(
            mode=str(view.get("mode") or "off"),
            health=ExportHealth(health_hint),
            notes=(
                (f"config_error: invalid mode token {mode_fallback_token(config)!r}",)
                if mode_fallback_token(config)
                else ()
            ),
        ).to_dict(),
    }

    exit_code = 2 if health_hint == ExportHealth.CONFIG_ERROR.value else 0
    if as_json:
        emit_json_envelope(
            build_envelope(
                "eval opik config show",
                ok=exit_code == 0,
                data=payload,
                warnings=warnings,
                errors=(
                    [
                        {
                            "code": "EVAL_CONFIG_ERROR",
                            "message": f"invalid mode token {mode_fallback_token(config)!r}",
                        }
                    ]
                    if exit_code == 2
                    else []
                ),
            )
        )
    else:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
    raise typer.Exit(code=exit_code)


@opik_config_app.command("show")
def opik_config_show_cmd(
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """Show resolved Opik/mirror config without secrets."""
    _config_show_impl(as_json=as_json, deprecated_from=None)


@opik_app.command("doctor")
def opik_doctor_cmd(
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """Check Opik/export health without exposing secrets.

    Inspects resolved config / export health / queue without transport or
    network. All secret-bearing output passes through ``mask_secret()``
    (``•••[len=N]``); raw token values and prefixes are never printed.
    """
    from git_cg.eval.cli_output import emit_human_line
    from git_cg.eval.doctor import run_opik_doctor

    repo = _resolve_repo(None)
    report = run_opik_doctor(repo_root=repo)
    if as_json:
        emit_json_envelope(build_envelope("eval opik doctor", ok=report.green, data=report.to_data()))
    else:
        emit_human_line(
            f"eval opik doctor: green={report.green} checks={len(report.checks)}",
            err=False,
        )
        for check in report.checks:
            line = f"  [{check.severity}/{check.status}] {check.check_id}: {check.message}"
            if check.hint:
                line = f"{line} (hint: {check.hint})"
            emit_human_line(line, err=True)
    raise typer.Exit(code=report.exit_code)


# --------------------------------------------------------------------------
# Temporary flat config alias (deprecated → eval opik config show)
# --------------------------------------------------------------------------


@eval_app.command("config", rich_help_panel="Deprecated", deprecated=True)
def config_cmd(
    action: str = typer.Argument(..., help="Subcommand: show"),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
) -> None:
    """Alias of eval opik config show.

    Removal target: first minor release after S6 GA.
    """
    if action != "show":
        typer.echo(f"config: unknown action {action!r} (supported: show)", err=True)
        raise typer.Exit(code=2)
    _config_show_impl(as_json=as_json, deprecated_from="git-cg eval config show")


# --------------------------------------------------------------------------
# Nested export (landed S4) + temporary dashed aliases
# --------------------------------------------------------------------------


# export_app registered near module top for help-panel order.


def _resolve_repo(root: Path | None) -> Path:
    """Resolve repo_root from an explicit path or Layer-A discovery."""
    from git_cg.eval.binding.paths import resolve_repo_root

    return root if root is not None else resolve_repo_root()


def _emit_slice5_error(command: str, exc: Exception, *, as_json: bool) -> None:
    """Emit a Slice-5 deterministic error and exit with the locked code.

    ``exc`` is an ExplainError/DiagnoseError carrying ``code``/``exit_code``/
    optional ``hint``. Human mode → one stderr line; JSON mode → one
    ``cli_output_envelope_v1`` with ``ok=false``. Never raises past the exit.
    """
    from git_cg.eval.cli_output import emit_human_line, envelope_message

    code = getattr(exc, "code", "EVAL_STORE_INTEGRITY")
    exit_code = int(getattr(exc, "exit_code", 4))
    hint = getattr(exc, "hint", None)
    err = envelope_message(code, str(exc), hint=hint)
    if as_json:
        emit_json_envelope(build_envelope(command, ok=False, errors=[err]))
    else:
        line = f"{command}: {err['message']}"
        if hint := err.get("hint"):
            line = f"{line} (hint: {hint})"
        emit_human_line(line, err=True)
    raise typer.Exit(code=exit_code)


def _run_issue_transition(
    command: str,
    *,
    issue_id: str,
    target: str,
    resolution_evidence: str | None,
    reason: str | None,
    as_json: bool,
) -> None:
    """Shared runner for the closed issue transition matrix verbs."""
    from git_cg.eval.cli_output import emit_human_line
    from git_cg.eval.diagnose import DiagnoseError, transition_issue

    repo = _resolve_repo(None)
    try:
        result = transition_issue(
            repo,
            issue_id=issue_id,
            target=target,
            resolution_evidence=resolution_evidence,
            reason=reason,
        )
    except DiagnoseError as exc:
        _emit_slice5_error(command, exc, as_json=as_json)
        return
    issue = result["issue"]
    if as_json:
        emit_json_envelope(build_envelope(command, ok=True, data=result))
    else:
        verb = "transitioned" if result["transitioned"] else "already"
        emit_human_line(
            f"{command}: {verb} {issue['issue_id']} {result['from']} -> {result['to']}",
            err=False,
        )
    raise typer.Exit(code=0)


def _queue_status_counts(repo: Path) -> dict[str, int]:
    """Count export-queue rows by status (read-only, offline).

    Unreadable JSON rows are bucketed as ``unreadable`` rather than
    raising so operator status stays fail-open for product accept.
    """
    from git_cg.eval.mirror.queue import export_queue_dir, load_queue_item

    qdir = export_queue_dir(repo)
    counts: dict[str, int] = {}
    if qdir.is_dir():
        for path in sorted(qdir.glob("*.json")):
            try:
                item = load_queue_item(path.stem, repo_root=repo)
            except Exception:
                counts["unreadable"] = counts.get("unreadable", 0) + 1
                continue
            status = str(item.get("status", "unknown"))
            counts[status] = counts.get(status, 0) + 1
    return counts


def _emit_status(repo: Path) -> None:
    """Print queue directory and per-status counts for ``export status``."""
    from git_cg.eval.mirror.queue import export_queue_dir

    qdir = export_queue_dir(repo)
    counts = _queue_status_counts(repo)
    typer.echo(f"queue_dir {qdir}")
    for status in ("pending", "sending", "sent", "failed", "dropped", "unreadable"):
        if status in counts:
            typer.echo(f"{status} {counts[status]}")
    if not counts:
        typer.echo("queue empty")


def _maybe_export_alias_deprecation(deprecated: str, *, as_json: bool) -> list[dict[str, str]]:
    """Emit dashed-export deprecation (stderr human / warnings[] JSON)."""
    leaf = deprecated.rsplit(" ", 1)[-1]  # export-status
    nested = leaf.replace("export-", "export ")
    canonical = f"git-cg eval {nested}"
    warning = deprecation_warning(
        deprecated=deprecated,
        canonical=canonical,
        removal_target=REMOVAL_TARGET,
    )
    if not as_json:
        emit_deprecation_human(
            deprecated=deprecated,
            canonical=canonical,
            removal_target=REMOVAL_TARGET,
        )
    return [warning]


@export_app.command("status")
def export_status_cmd(
    root: Path | None = typer.Option(
        None,
        "--root",
        help="Repo root (defaults to discovery).",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
    _deprecated_from: str | None = typer.Option(None, hidden=True),
) -> None:
    """Show export-queue status (read-only, offline).

    Never mutates the queue and never contacts Opik or the network.
    """
    from git_cg.eval.mirror.config import mode_fallback_token, operator_config_health, resolve_opik_config

    warnings: list[dict[str, str]] = []
    if _deprecated_from:
        warnings = _maybe_export_alias_deprecation(_deprecated_from, as_json=as_json)

    try:
        cfg = resolve_opik_config()
    except Exception:
        cfg = None
    health_hint = operator_config_health(cfg) if cfg is not None else None
    bad_mode = mode_fallback_token(cfg) if cfg is not None else None

    try:
        repo = _resolve_repo(root)
    except Exception as exc:
        if as_json:
            emit_json_envelope(
                build_envelope(
                    "eval export status",
                    ok=False,
                    data={},
                    errors=[{"code": "EVAL_REPO_UNRESOLVABLE", "message": str(exc)}],
                    warnings=warnings,
                )
            )
        else:
            typer.echo(f"export status: repo root unresolvable: {exc}", err=True)
        raise typer.Exit(code=1) from None

    counts = _queue_status_counts(repo)
    from git_cg.eval.mirror.queue import export_queue_dir

    qdir = export_queue_dir(repo)
    if as_json:
        emit_json_envelope(
            build_envelope(
                "eval export status",
                ok=bad_mode is None,
                data={
                    "queue_dir": str(qdir),
                    "counts": counts,
                    "health": health_hint,
                    "bad_mode": bad_mode,
                },
                errors=(
                    [
                        {
                            "code": "EVAL_CONFIG_ERROR",
                            "message": f"invalid mode token {bad_mode!r}",
                        }
                    ]
                    if bad_mode is not None
                    else []
                ),
                warnings=warnings,
            )
        )
    else:
        if health_hint is not None:
            typer.echo(f"health {health_hint}")
        if bad_mode is not None:
            typer.echo(f"config_error invalid mode token {bad_mode!r}", err=True)
        _emit_status(repo)
    if bad_mode is not None:
        raise typer.Exit(code=2)
    raise typer.Exit(code=0)


@export_app.command("retry")
def export_retry_cmd(
    root: Path | None = typer.Option(
        None,
        "--root",
        help="Repo root (defaults to discovery).",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    queue_id: str | None = typer.Option(
        None,
        "--id",
        help="Retry a single failed queue id (default: all failed rows).",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Also retry export_validation / export_auth / export_size failures.",
    ),
    max_items: int | None = typer.Option(
        None,
        "--max-items",
        help="Cap on failed rows re-queued this invocation.",
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
    _deprecated_from: str | None = typer.Option(None, hidden=True),
) -> None:
    """Re-queue failed export rows for another drain attempt.

    Default policy: reclaim rows whose last_error_class is retryable
    (``export_network`` / ``export_timeout`` / empty). Validation/auth/size
    failures require ``--force``. Transitions ``failed → pending`` so the next
    ``export drain`` can claim them. Never blocks product accept.
    """
    from git_cg.eval.mirror.queue import (
        ExportQueueError,
        export_queue_dir,
        load_queue_item,
        mark_queue_item,
    )

    warnings: list[dict[str, str]] = []
    if _deprecated_from:
        warnings = _maybe_export_alias_deprecation(_deprecated_from, as_json=as_json)

    try:
        repo = _resolve_repo(root)
    except Exception as exc:
        if as_json:
            emit_json_envelope(
                build_envelope(
                    "eval export retry",
                    ok=True,
                    data={"retried": 0, "skipped": 0, "unreadable": 0, "note": "fail_open"},
                    warnings=warnings,
                    errors=[{"code": "EVAL_REPO_UNRESOLVABLE", "message": str(exc)}],
                )
            )
        else:
            typer.echo(f"export retry: repo root unresolvable: {exc}", err=True)
        raise typer.Exit(code=0) from None

    retryable = {"export_network", "export_timeout", ""}
    qdir = export_queue_dir(repo)
    targets: list[str] = []
    if queue_id:
        targets = [queue_id]
    elif qdir.is_dir():
        for path in sorted(qdir.glob("*.json")):
            targets.append(path.stem)

    retried = 0
    skipped = 0
    unreadable = 0
    for qid in targets:
        if max_items is not None and retried >= max_items:
            break
        try:
            item = load_queue_item(qid, repo_root=repo)
        except ExportQueueError:
            unreadable += 1
            continue
        except Exception:
            unreadable += 1
            continue
        if item.get("status") != "failed":
            skipped += 1
            continue
        err = str(item.get("last_error_class") or "")
        if not force and err not in retryable:
            skipped += 1
            continue
        try:
            mark_queue_item(
                qid,
                "pending",
                repo_root=repo,
                clear_lease=True,
                notes="retry_requested",
                last_error_class=err or None,
            )
            retried += 1
        except ExportQueueError as exc:
            typer.echo(f"export retry: {qid}: {exc}", err=True)
            skipped += 1

    if as_json:
        emit_json_envelope(
            build_envelope(
                "eval export retry",
                ok=True,
                data={"retried": retried, "skipped": skipped, "unreadable": unreadable},
                warnings=warnings,
            )
        )
    else:
        typer.echo(f"retried {retried} skipped {skipped} unreadable {unreadable}")
    raise typer.Exit(code=0)


@export_app.command("drain")
def export_drain_cmd(
    root: Path | None = typer.Option(
        None,
        "--root",
        help="Repo root (defaults to discovery).",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    max_items: int | None = typer.Option(None, "--max-items", help="Cap on rows processed this drain."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Resolve config + list pending rows; no upload."),
    as_json: bool = typer.Option(False, "--json", help="Emit cli_output_envelope_v1 on stdout."),
    _deprecated_from: str | None = typer.Option(None, hidden=True),
) -> None:
    """Drain the export queue through the Opik transport.

    Always exits 0 unless the config is invalid (fail-closed). Transport and
    secret failures are classified and recorded on the queue rows; they never
    produce a non-zero exit that could block a hook.
    """
    import json

    from git_cg.eval.mirror.config import (
        OpikConfigError,
        mode_fallback_token,
        operator_config_health,
        resolve_opik_config,
    )
    from git_cg.eval.mirror.exporter import drain_queue, list_pending_items
    from git_cg.eval.mirror.health import ExportHealth
    from git_cg.eval.mirror.result import build_mirror_result, evaluation_job_result, export_result
    from git_cg.eval.mirror.transport import OpikSdkTransport

    warnings: list[dict[str, str]] = []
    if _deprecated_from:
        warnings = _maybe_export_alias_deprecation(_deprecated_from, as_json=as_json)

    try:
        config = resolve_opik_config()
    except OpikConfigError as exc:
        if as_json:
            emit_json_envelope(
                build_envelope(
                    "eval export drain",
                    ok=False,
                    data={},
                    errors=[{"code": "EVAL_CONFIG_ERROR", "message": str(exc)}],
                    warnings=warnings,
                )
            )
        else:
            typer.echo(f"export drain: config invalid (fail-closed): {exc}", err=True)
        raise typer.Exit(code=2) from None

    bad_mode = mode_fallback_token(config)
    if bad_mode is not None:
        result = build_mirror_result(
            mode=str(config.get("mode") or "off"),
            health=ExportHealth.CONFIG_ERROR,
            notes=(f"config_error: invalid mode token {bad_mode!r}",),
            error_classes=("export_validation",),
        )
        payload = {
            "mirror_result": result.to_dict(),
            "export_result": export_result(result),
            "evaluation_job_result": evaluation_job_result(result),
            "health_hint": operator_config_health(config),
        }
        if as_json:
            emit_json_envelope(
                build_envelope(
                    "eval export drain",
                    ok=False,
                    data=payload,
                    errors=[
                        {
                            "code": "EVAL_CONFIG_ERROR",
                            "message": f"invalid mode token {bad_mode!r}",
                        }
                    ],
                    warnings=warnings,
                )
            )
        else:
            typer.echo(
                f"export drain: config_error invalid mode token {bad_mode!r} (fail-closed to {config.get('mode')!r})",
                err=True,
            )
            typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        raise typer.Exit(code=2)

    if config.get("mode", "off") == "off":
        if as_json:
            emit_json_envelope(
                build_envelope(
                    "eval export drain",
                    ok=True,
                    data={"mode": "off", "note": "nothing_to_do"},
                    warnings=warnings,
                )
            )
        else:
            typer.echo("export drain: mode=off; nothing to do")
        raise typer.Exit(code=0)

    try:
        repo = _resolve_repo(root)
    except Exception as exc:
        if as_json:
            emit_json_envelope(
                build_envelope(
                    "eval export drain",
                    ok=True,
                    data={"note": "fail_open", "error": str(exc)},
                    warnings=warnings,
                )
            )
        else:
            typer.echo(f"export drain: repo root unresolvable: {exc}", err=True)
        raise typer.Exit(code=0) from None

    if dry_run:
        pending = list_pending_items(repo_root=repo)
        projects = config.get("projects") or {}
        project = (projects.get("eval") if isinstance(projects, dict) else None) or config.get("project_name", "")
        data = {
            "mode": config.get("mode"),
            "project": project,
            "pending": len(pending),
        }
        if as_json:
            emit_json_envelope(build_envelope("eval export drain", ok=True, data=data, warnings=warnings))
        else:
            typer.echo(f"mode {config.get('mode')}")
            typer.echo(f"project {project}")
            typer.echo(f"pending {len(pending)}")
        raise typer.Exit(code=0)

    from git_cg.eval.mirror.exporter import mirror_result_from_drain

    summary = drain_queue(
        config,
        transport=OpikSdkTransport(),
        repo_root=repo,
        max_items=max_items,
    )
    result = mirror_result_from_drain(config, summary)
    payload = {
        "mirror_result": result.to_dict(),
        "export_result": export_result(result),
        "evaluation_job_result": evaluation_job_result(result),
        "attempted": summary.attempted,
        "exported": summary.exported,
        "failed": summary.failed,
        "error_classes": list(summary.error_classes) if summary.error_classes else [],
    }
    if as_json:
        emit_json_envelope(build_envelope("eval export drain", ok=True, data=payload, warnings=warnings))
    else:
        typer.echo(f"attempted {summary.attempted} exported {summary.exported} failed {summary.failed}")
        if summary.error_classes:
            typer.echo(f"error_classes {','.join(summary.error_classes)}")
        typer.echo(
            json.dumps(
                {
                    "mirror_result": payload["mirror_result"],
                    "export_result": payload["export_result"],
                    "evaluation_job_result": payload["evaluation_job_result"],
                },
                indent=2,
                sort_keys=True,
            )
        )
    raise typer.Exit(code=0)


# Temporary dashed aliases (R2) — removal: first minor after S6 GA.
def _export_status_alias(
    root: Path | None = typer.Option(None, "--root", exists=False, file_okay=False, dir_okay=True, resolve_path=True),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Alias of eval export status."""
    export_status_cmd(root=root, as_json=as_json, _deprecated_from="git-cg eval export-status")


def _export_retry_alias(
    root: Path | None = typer.Option(None, "--root", exists=False, file_okay=False, dir_okay=True, resolve_path=True),
    queue_id: str | None = typer.Option(None, "--id"),
    force: bool = typer.Option(False, "--force"),
    max_items: int | None = typer.Option(None, "--max-items"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Alias of eval export retry."""
    export_retry_cmd(
        root=root,
        queue_id=queue_id,
        force=force,
        max_items=max_items,
        as_json=as_json,
        _deprecated_from="git-cg eval export-retry",
    )


def _export_drain_alias(
    root: Path | None = typer.Option(None, "--root", exists=False, file_okay=False, dir_okay=True, resolve_path=True),
    max_items: int | None = typer.Option(None, "--max-items"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Alias of eval export drain."""
    export_drain_cmd(
        root=root,
        max_items=max_items,
        dry_run=dry_run,
        as_json=as_json,
        _deprecated_from="git-cg eval export-drain",
    )


eval_app.command("export-status", rich_help_panel="Deprecated", deprecated=True)(_export_status_alias)
eval_app.command("export-retry", rich_help_panel="Deprecated", deprecated=True)(_export_retry_alias)
eval_app.command("export-drain", rich_help_panel="Deprecated", deprecated=True)(_export_drain_alias)
