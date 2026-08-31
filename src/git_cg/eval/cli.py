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

import os
import sys
from pathlib import Path
from typing import Any

import click
import typer
from typer.core import TyperCommand, TyperGroup

from git_cg.eval.cli_output import (
    DEFAULT_KEEP_LAST,
    REMOVAL_TARGET,
    build_envelope,
    deprecation_warning,
    emit_deprecation_human,
    emit_json_envelope,
    emit_not_implemented,
)

# --------------------------------------------------------------------------
# Help depth pilot (selected eval commands) — variant C
# --------------------------------------------------------------------------
#
# Default ``--help`` shows the brief body (text before the detail marker).
# Detailed operator help is a help-depth flag shown in the Options panel:
#
#   git-cg eval --help
#   git-cg eval --detail
#   git-cg eval materialize-core-goldens --help
#   git-cg eval materialize-core-goldens --detail
#   git-cg eval materialize-core-goldens --help --detail
#   git-cg eval encode-fixture --detail
#   git-cg eval run --detail
#   git-cg eval resume --detail
#   git-cg eval recompute-scores --detail
#   git-cg eval doctor --detail
#   git-cg eval triage --detail
#   git-cg eval failures --detail
#   git-cg eval explain --detail
#   git-cg eval compare --detail
#   git-cg eval diagnose --detail
#   git-cg eval review --detail
#   git-cg eval review enqueue --detail
#   git-cg eval review list --detail
#   git-cg eval review rollup --detail
#   git-cg eval review show --detail
#   git-cg eval review claim --detail
#   git-cg eval review adjudicate --detail
#   git-cg eval review dismiss --detail
#   git-cg eval session --detail
#   git-cg eval session show --detail
#   git-cg eval thread --detail
#   git-cg eval thread show --detail
#   git-cg eval issue --detail
#   git-cg eval issue list --detail
#   git-cg eval issue show --detail
#   git-cg eval issue resolve --detail
#   git-cg eval issue reopen --detail
#   git-cg eval issue suppress --detail
#   git-cg eval session --detail
#   git-cg eval thread --detail
#   git-cg eval issue --detail
#   git-cg eval amend-brief --detail
#   git-cg eval train-export --detail
#   git-cg eval opik --detail
#   git-cg eval opik doctor --detail
#   git-cg eval opik config --detail
#   git-cg eval opik config show --detail
#   git-cg eval export --detail
#   git-cg eval export status --detail
#   git-cg eval export retry --detail
#   git-cg eval export drain --detail
#   git-cg eval replay --detail
#   git-cg eval promote --detail
#   git-cg eval dogfood --detail
#   git-cg eval config --detail
#   git-cg eval export-status --detail
#   git-cg eval export-retry --detail
#   git-cg eval export-drain --detail
#   GIT_CG_HELP=full git-cg eval materialize-core-goldens --help
#
# Implementation notes:
# * Docstring uses a project marker between brief and detail body (not Click
#   form-feed) so Ruff does not treat the splitter as trailing whitespace.
# * ``--detail`` is a declared eager Typer option so it appears under Options,
#   but it is help-only: the callback prints help and exits (never runs the command).
# * Prefer ``--detail`` over names that sound like runtime modes or log verbosity.
# * Compose once from ``_help_raw`` with a re-entry guard: Typer Rich reads
#   ``obj.help`` directly after we expand it.
# * Nested groups use ``BriefFullHelpGroup`` plus a callback-owned ``--detail``;
#   leaf commands use ``BriefFullHelpCommand``.
# * Scoped to selected eval surfaces so terminal UX can be judged before wider rollout.


_HELP_DETAIL_MARKER = "<<GIT_CG_HELP_DETAIL>>"
_FULL_HELP_ENV = "GIT_CG_HELP"
_FULL_HELP_ENV_VALUE = "full"
_DETAIL_HELP_FLAG = "--detail"


def _wants_detail_help(ctx: click.Context | None = None) -> bool:
    """Return True when the caller asked for the long help body."""
    env = (os.environ.get(_FULL_HELP_ENV) or "").strip().lower()
    if env == _FULL_HELP_ENV_VALUE:
        return True
    if ctx is not None and getattr(ctx, "meta", None) and ctx.meta.get("git_cg_detail_help"):
        return True
    # Defensive: ``--help --detail`` may render via Click's eager ``--help``
    # before our option callback runs; argv still carries ``--detail``.
    return _DETAIL_HELP_FLAG in sys.argv


def _split_brief_detail_help(help_text: str | None) -> tuple[str, str | None]:
    """Split docstring help on the detail marker into (brief, detail_or_none)."""
    if not help_text:
        return "", None
    brief, sep, detail = str(help_text).partition(_HELP_DETAIL_MARKER)
    brief = brief.strip()
    detail_body = detail.strip() if sep else None
    return brief, detail_body or None


def _compose_help_for_display(*, help_text: str | None, detail: bool) -> str:
    """Build the help string Click/Typer should render for this invocation.

    Always expands from the raw docstring (with optional detail marker). Brief
    mode is text before the marker only; detail mode joins brief + detail body.
    Discoverability for detail help lives in the Options panel (``--detail``).
    """
    brief, detail_body = _split_brief_detail_help(help_text)
    if detail and detail_body:
        return f"{brief}\n\n{detail_body}\n"
    return (brief + "\n") if brief else ""


def _detail_help_option_callback(
    ctx: typer.Context,
    param: click.Parameter,
    value: bool,
) -> bool:
    """Eager ``--detail``: mark detailed help, print help, exit (never run command)."""
    if ctx.resilient_parsing or not value:
        return value
    ctx.meta["git_cg_detail_help"] = True
    # ``get_help`` → ``format_help`` which composes from ``_help_raw``.
    click.echo(ctx.get_help(), color=ctx.color)
    raise typer.Exit()


def _detail_help_option() -> Any:
    """Shared Typer option factory for the brief/detail pilot."""
    return typer.Option(
        False,
        _DETAIL_HELP_FLAG,
        help="Show detailed help text and exit.",
        is_eager=True,
        callback=_detail_help_option_callback,
        # Visible on purpose: basic users should see this next to ``--help``.
        hidden=False,
    )


class BriefFullHelpCommand(TyperCommand):
    """Typer command: default brief ``--help``; ``--detail`` for long body.

    Pilot only: attach via ``cls=BriefFullHelpCommand`` on selected commands.
    Docstrings store brief text, a detail marker, then the long body.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Frozen source for composition. Never overwrite with composed text.
        self._help_raw = self.help
        self._git_cg_help_composing = False

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:  # type: ignore[override]
        if self._git_cg_help_composing:
            # Nested call (get_help → format_help): keep the already expanded help.
            return super().format_help(ctx, formatter)

        original = self.help
        self._git_cg_help_composing = True
        try:
            self.help = _compose_help_for_display(
                help_text=self._help_raw,
                detail=_wants_detail_help(ctx),
            )
            return super().format_help(ctx, formatter)
        finally:
            self.help = original
            self._git_cg_help_composing = False


class BriefFullHelpGroup(TyperGroup):
    """Typer group: default brief ``--help``; ``--detail`` for long body.

    Pilot only: attach via ``cls=BriefFullHelpGroup`` on selected nested apps.
    Group help lives on the Typer ``help=`` string (brief + marker + detail).
    Visible ``--detail`` is owned by the group callback via ``_detail_help_option()``.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._help_raw = self.help
        self._git_cg_help_composing = False

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:  # type: ignore[override]
        if self._git_cg_help_composing:
            return super().format_help(ctx, formatter)

        original = self.help
        self._git_cg_help_composing = True
        try:
            self.help = _compose_help_for_display(
                help_text=self._help_raw,
                detail=_wants_detail_help(ctx),
            )
            return super().format_help(ctx, formatter)
        finally:
            self.help = original
            self._git_cg_help_composing = False


class EvalHelpGroup(BriefFullHelpGroup):
    """Root ``git-cg eval`` group: workflow panel order + brief/detail help.

    Typer registers leaf commands before nested groups, so plain registration
    order always pushes Review/session groups to the bottom. This group keeps
    command resolution unchanged while listing commands in panel-priority order
    for Rich help rendering, and reuses ``BriefFullHelpGroup`` so root
    ``--help`` / ``--detail`` match nested surfaces.
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
        "product commit ranking.\n"
        "\n"
        "<<GIT_CG_HELP_DETAIL>>\n"
        "\n"
        "Top-level workflow groups match the panels below:\n"
        "\n"
        "- Corpus: rebuild checked-in reference fixtures and identity hashes\n"
        "- Run: offline suite run, resume from checkpoint, re-score prior evidence\n"
        "- Inspect: doctor, triage, failures, explain, compare, diagnose, checkpoint list\n"
        "- Review & sessions: advisory human review, local sessions/threads, diagnostic issues\n"
        "- Export & train: amend briefs, train export, Opik health/config, export queue\n"
        "- Advanced: replay generation and governed promote\n"
        "- Deprecated: temporary aliases for nested Opik config and export paths\n"
        "\n"
        "Guarantees:\n"
        "- local inspect/run surfaces stay offline-first by default\n"
        "- never changes product commit ranking or SOP intent authority\n"
        "- gold stays governed (no silent mint from accept or popularity)\n"
        "- dark-launched maintainer surfaces stay hidden from this menu\n"
        "\n"
        "Use git-cg eval <command> --help for brief leaf help, or --detail on any "
        "surface for the long operator body. GIT_CG_HELP=full also expands detail."
    ),
    short_help=("Run and inspect local evaluation suites without changing product ranking."),
    no_args_is_help=True,
)


# Group-level brief/detail help (root surface). Help-only; no eval I/O.
@eval_app.callback()
def eval_group_callback(
    detail: bool = _detail_help_option(),
) -> None:
    """Own the group ``--detail`` option; Typer group callback body is a no-op."""
    return


# Nested groups declared early so top-level help panels order by workflow:
# Corpus → Run → Inspect → Review & sessions → Export & train → Advanced → Deprecated.
review_app = typer.Typer(
    cls=BriefFullHelpGroup,
    add_completion=False,
    help=(
        "Local human review queue (advisory only).\n"
        "\n"
        "Manage advisory human-review items for eval cases. Never writes gold "
        "or changes product commit ranking.\n"
        "\n"
        "<<GIT_CG_HELP_DETAIL>>\n"
        "\n"
        "Local queue under .eval/review_queue/. Typical flow:\n"
        "\n"
        "  enqueue → claim → adjudicate | dismiss\n"
        "  list / show for inspection\n"
        "  rollup for multi-rater majority and craft spread (read-only)\n"
        "\n"
        "Guarantees:\n"
        "- authority stays advisory\n"
        "- adjudicate emits a typed outcome_ref and never writes gold\n"
        "- claim moves pending → in_review\n"
        "- dismiss is terminal for pending/in_review\n"
        "- rollup never sole-promotes gold\n"
        "\n"
        "Subcommands:\n"
        "- enqueue: create an advisory item for a case or bundle\n"
        "- list / show: inspect queue items\n"
        "- claim: take a pending item\n"
        "- adjudicate: resolve with a typed outcome\n"
        "- dismiss: close without promotion\n"
        "- rollup: multi-rater advisory score summary"
    ),
    short_help="Local human review queue (advisory only).",
    no_args_is_help=True,
)
session_app = typer.Typer(
    cls=BriefFullHelpGroup,
    add_completion=False,
    help=(
        "Inspect local commit sessions.\n"
        "\n"
        "Read-only lookup of a local commit-session record. Does not change "
        "commit ranking or gold.\n"
        "\n"
        "<<GIT_CG_HELP_DETAIL>>\n"
        "\n"
        "Reads a local commit_session_thread_v1 twin under the eval session "
        "store and prints a map-only projection.\n"
        "\n"
        "Guarantees (this surface):\n"
        "- local only (no Opik / network reach)\n"
        "- no chat timeline or graph browser\n"
        "- no accept authority, rerun, or ranking mutation\n"
        "\n"
        "Subcommands:\n"
        "- show: inspect one session by id (sess_ or sessmeta_)"
    ),
    short_help="Inspect local commit sessions.",
    no_args_is_help=True,
)
thread_app = typer.Typer(
    cls=BriefFullHelpGroup,
    add_completion=False,
    help=(
        "Inspect local session threads.\n"
        "\n"
        "Read-only lookup of a local session-thread record. Does not change "
        "commit ranking or gold.\n"
        "\n"
        "<<GIT_CG_HELP_DETAIL>>\n"
        "\n"
        "Reads the same local commit_session_thread_v1 capture episode and "
        "projects thread-oriented fields (message versions, preference pairs, "
        "attempt ids) as a map-only view.\n"
        "\n"
        "Guarantees (this surface):\n"
        "- local only (no Opik / network reach)\n"
        "- no chat timeline or graph browser\n"
        "- no accept authority, rerun, or ranking mutation\n"
        "\n"
        "Subcommands:\n"
        "- show: inspect one thread by id (sess_ or sessmeta_)"
    ),
    short_help="Inspect local session threads.",
    no_args_is_help=True,
)
issue_app = typer.Typer(
    cls=BriefFullHelpGroup,
    add_completion=False,
    help=(
        "Manage local diagnostic issues.\n"
        "\n"
        "List, inspect, and transition local diagnostic issues created from "
        "eval failures. Does not change commit ranking or gold.\n"
        "\n"
        "<<GIT_CG_HELP_DETAIL>>\n"
        "\n"
        "Local store under issues/diagnostics (via eval diagnose / issue "
        "commands). Operators can list and show issues, then resolve, reopen, "
        "or suppress them.\n"
        "\n"
        "Status filter values: open | acknowledged | resolved | suppressed | "
        "reopened.\n"
        "\n"
        "Guarantees / requirements:\n"
        "- resolve requires --resolution-evidence\n"
        "- suppress requires --reason\n"
        "- reopen works from resolved/suppressed\n"
        "- no product ranking mutation\n"
        "\n"
        "Subcommands:\n"
        "- list: newest last_seen first (optional --status)\n"
        "- show: one issue by id\n"
        "- resolve: mark resolved with evidence\n"
        "- reopen: reopen resolved/suppressed\n"
        "- suppress: suppress with reason"
    ),
    short_help="Manage local diagnostic issues.",
    no_args_is_help=True,
)
opik_app = typer.Typer(
    cls=BriefFullHelpGroup,
    add_completion=False,
    help=(
        "Opik health checks and secret-safe config.\n"
        "\n"
        "Inspect Opik/export health and resolved config offline. Never prints "
        "raw secrets or reaches the network.\n"
        "\n"
        "<<GIT_CG_HELP_DETAIL>>\n"
        "\n"
        "Offline operator surfaces for Opik/mirror integration. No transport, "
        "no network, and no raw token values or prefixes — secret-bearing "
        "output uses mask_secret() only (redacted length form) plus a presence boolean.\n"
        "\n"
        "Guarantees:\n"
        "- observability only (no accept, ranking, gold, or queue drain)\n"
        "- fail-closed config errors stay non-zero / non-green\n"
        "- active modes require pinned projects; invalid mode tokens surface "
        "as config_error\n"
        "\n"
        "Subcommands:\n"
        "- doctor: Opik/export/queue health checks (local only)\n"
        "- config: nested secret-safe config inspection (show)"
    ),
    short_help="Opik health checks and secret-safe config.",
    no_args_is_help=True,
)
opik_config_app = typer.Typer(
    cls=BriefFullHelpGroup,
    add_completion=False,
    help=(
        "Inspect Opik/mirror config without exposing secrets.\n"
        "\n"
        "Show the resolved public Opik/mirror view. Never prints raw API keys.\n"
        "\n"
        "<<GIT_CG_HELP_DETAIL>>\n"
        "\n"
        "Canonical path: git-cg eval opik config show. Prints public_config_view "
        "plus a masked secrets block (api_key via mask_secret, api_key_present).\n"
        "\n"
        "Health hint values include skipped_off / deferred / pending / "
        "config_error. Invalid mode tokens fail closed.\n"
        "\n"
        "Guarantees:\n"
        "- no network / transport\n"
        "- no cleartext secrets\n"
        "- temporary flat alias remains: git-cg eval config show\n"
        "\n"
        "Subcommands:\n"
        "- show: emit secret-safe resolved config (plain summary or --json envelope)"
    ),
    short_help="Inspect Opik/mirror config without exposing secrets.",
    no_args_is_help=True,
)
checkpoint_app = typer.Typer(
    cls=BriefFullHelpGroup,
    add_completion=False,
    help=(
        "Local evaluation checkpoint inventory (read-only).\n"
        "\n"
        "Inspect stored evaluation checkpoints under .eval/checkpoints/.\n"
        "\n"
        "<<GIT_CG_HELP_DETAIL>>\n"
        "\n"
        "Offline inventory for resume/GC planning. Does not mutate checkpoint\n"
        "files, contact Opik, or change product ranking.\n"
        "\n"
        "Guarantees:\n"
        "- list is offline and non-mutating\n"
        "- unreadable/corrupt checkpoints are skipped\n"
        "- live_match compares stored compat_hash to the live preimage\n"
        "\n"
        "Subcommands:\n"
        "- list: inventory id/mtime/suite/compat/pin/live_match/counts"
    ),
    short_help="Local evaluation checkpoint inventory (read-only).",
    no_args_is_help=True,
)

export_app = typer.Typer(
    cls=BriefFullHelpGroup,
    add_completion=False,
    help=(
        "Export-queue status, retry, and drain.\n"
        "\n"
        "Operate the local Opik export queue. Status is offline; drain may "
        "upload. Never blocks product accept.\n"
        "\n"
        "<<GIT_CG_HELP_DETAIL>>\n"
        "\n"
        "Local export queue under the eval mirror store. Operators inspect "
        "counts, re-queue failed rows, and drain pending items through the "
        "Opik transport.\n"
        "\n"
        "Typical flow:\n"
        "\n"
        "  status → (optional retry) → drain\n"
        "\n"
        "Guarantees:\n"
        "- status is read-only and offline (no Opik / network)\n"
        "- retry moves failed → pending; default only reclaim network/timeout/"
        "empty errors (validation/auth/size need --force)\n"
        "- drain exits 0 unless config is invalid (fail-closed); transport/"
        "secret failures are classified on rows and never block hooks\n"
        "- temporary flat aliases remain: export-status / export-retry / "
        "export-drain\n"
        "\n"
        "Subcommands:\n"
        "- status: queue directory + per-status counts\n"
        "- retry: re-queue failed rows for another drain\n"
        "- drain: upload pending rows (supports --dry-run)"
    ),
    short_help="Export-queue status, retry, and drain.",
    no_args_is_help=True,
)

# Register groups before leaf Export/Advanced commands so panel order matches workflow.
eval_app.add_typer(review_app, name="review", rich_help_panel="Review & sessions")
eval_app.add_typer(session_app, name="session", rich_help_panel="Review & sessions")
eval_app.add_typer(thread_app, name="thread", rich_help_panel="Review & sessions")
eval_app.add_typer(issue_app, name="issue", rich_help_panel="Review & sessions")
eval_app.add_typer(checkpoint_app, name="checkpoint", rich_help_panel="Inspect")
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


@eval_app.command(
    "materialize-core-goldens",
    cls=BriefFullHelpCommand,
    rich_help_panel="Corpus",
    short_help="Rebuild checked-in evaluation reference files used by tests.",
)
def materialize_core_goldens_cmd(
    root: Path | None = typer.Option(
        None,
        "--root",
        help="Directory to write into (default: tests/fixtures/eval).",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Rebuild the checked-in evaluation reference files used by tests.

    Local disk only. Does not run evaluations or change commit ranking.

    <<GIT_CG_HELP_DETAIL>>

    Writes the main reference bundles and snapshot into the fixture directory
    (default: tests/fixtures/eval). If optional archive fixtures exist there,
    those are rebuilt too.

    Use after you change eval fixtures and need the checked-in reference outputs
    refreshed. Prints the paths written and how many bundles were produced.
    """
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


@eval_app.command(
    "encode-fixture",
    cls=BriefFullHelpCommand,
    rich_help_panel="Corpus",
    short_help="Print stable identity hashes for one evaluation fixture.",
)
def encode_fixture_cmd(
    path: Path | None = typer.Option(
        None,
        "--path",
        help="Path to one fixture JSON file.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
    fixture_id: str | None = typer.Option(
        None,
        "--id",
        help="Fixture case id to load from a suite (use instead of --path).",
    ),
    suite_id: str | None = typer.Option(
        None,
        "--suite",
        help="Suite to search when using --id (default: cm-eval-fixtures-core).",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Print stable identity hashes for one evaluation fixture.

    Local disk only. Does not run evaluations or change commit ranking.

    <<GIT_CG_HELP_DETAIL>>

    Load exactly one fixture with --path FILE or --id CASE_ID (not both).
    With --id, --suite selects which suite to search (default:
    cm-eval-fixtures-core).

    Prints bundle_hash, case_hash, and bundle_ref so you can confirm the
    fixture encodes cleanly and compare identities across tooling. Exits
    non-zero on bad options, missing fixtures, or encode failures.
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

    if not isinstance(result, RunResult):
        raise TypeError(f"{command}: expected RunResult, got {type(result)!r}")
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
    """Parse comma-separated case IDs into a tuple, or return None if raw is None."""
    if raw is None:
        return None
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return tuple(parts) if parts else None


@eval_app.command(
    "run",
    cls=BriefFullHelpCommand,
    rich_help_panel="Run",
    short_help="Run a local offline evaluation suite.",
)
def run_cmd(
    suite: str | None = typer.Option(
        "cm-eval-fixtures-core",
        "--suite",
        help="Which fixture suite to run (default: cm-eval-fixtures-core).",
    ),
    fixture_root: Path | None = typer.Option(
        None,
        "--fixture-root",
        help="Optional alternate fixture directory (for tests/lab layouts).",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    mode: str = typer.Option(
        "fresh_suite_run",
        "--mode",
        help=(
            "How to run: fresh_suite_run (default), resume_missing, "
            "recompute_scores, replay_generation, or export_only."
        ),
    ),
    keep_last: int = typer.Option(
        DEFAULT_KEEP_LAST,
        "--keep-last",
        help="How many recent checkpoints to keep per suite family (default: 10).",
    ),
    keep_checkpoint: bool = typer.Option(
        False,
        "--keep-checkpoint",
        help="Keep this run's checkpoint even when the run succeeds.",
    ),
    gold_mode: str = typer.Option(
        "strict",
        "--gold-mode",
        help="How tightly to compare against reference answers (default: strict).",
    ),
    case: str | None = typer.Option(
        None,
        "--case",
        help="Limit to specific case ids (comma-separated). Lab/triage only, not CI golden.",
    ),
    experiment: str | None = typer.Option(
        None,
        "--experiment",
        help="Existing experiment id (required for export_only; optional parent for recompute_scores).",
    ),
    checkpoint: str | None = typer.Option(
        None,
        "--checkpoint",
        help="Checkpoint id to continue (used with --mode resume_missing).",
    ),
    allow_replay_generation: bool = typer.Option(
        False,
        "--allow-replay-generation",
        help="Allow replay_generation mode (blocked unless you set this).",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Run a local offline evaluation suite.

    Does not change how commits are ranked. Default mode starts a fresh suite run.

    <<GIT_CG_HELP_DETAIL>>

    Modes:
    - fresh_suite_run: score the suite from scratch (default)
    - resume_missing: continue unfinished cases from --checkpoint
    - recompute_scores: re-score evidence for an existing --experiment
    - replay_generation: regenerate commit text (requires --allow-replay-generation)
    - export_only: project local results for --experiment; no scoring or checkpoint

    Common flags:
    - --suite / --fixture-root choose fixtures
    - --case limits work to listed case ids (lab/triage only)
    - --keep-last / --keep-checkpoint control checkpoint retention
    - --gold-mode controls reference comparison strictness
    - --json emits the standard CLI JSON envelope

    Prefer the dedicated resume / recompute-scores commands when you already
    know that workflow. Default path stays offline and local-disk first.
    """
    # Lazy import preserves Slice 2 import-isolation law (no scoring at import).
    from git_cg.eval.run_orchestrator import RunRequest, run_evaluation

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
    except Exception as exc:
        # RunOrchestratorError and unexpected failures share the same emitter.
        _emit_run_result("eval run", as_json=as_json, error=exc)
    else:
        _emit_run_result("eval run", as_json=as_json, result=result)


@eval_app.command(
    "resume",
    cls=BriefFullHelpCommand,
    rich_help_panel="Run",
    short_help="Continue an unfinished evaluation from a checkpoint.",
)
def resume_cmd(
    checkpoint: str | None = typer.Option(
        None,
        "--checkpoint",
        help="Checkpoint id from a prior suite run (required).",
    ),
    fixture_root: Path | None = typer.Option(
        None,
        "--fixture-root",
        help="Optional alternate fixture directory (for tests/lab layouts).",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    keep_last: int = typer.Option(
        DEFAULT_KEEP_LAST,
        "--keep-last",
        help="How many recent checkpoints to keep per suite family (default: 10).",
    ),
    keep_checkpoint: bool = typer.Option(
        False,
        "--keep-checkpoint",
        help="Keep this run's checkpoint even when the run succeeds.",
    ),
    gold_mode: str = typer.Option(
        "strict",
        "--gold-mode",
        help="How tightly to compare against reference answers (default: strict).",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Continue an unfinished evaluation from a checkpoint.

    Does not change how commits are ranked. Requires --checkpoint from a prior run.

    <<GIT_CG_HELP_DETAIL>>

    This is the dedicated form of `git-cg eval run --mode resume_missing`.
    Pass --checkpoint <id> from a previous suite run; only missing/unfinished
    cases are continued.

    Retention and comparison flags match eval run:
    - --keep-last / --keep-checkpoint control checkpoint retention
    - --gold-mode controls reference comparison strictness
    - --fixture-root overrides the fixture directory when needed
    - --json emits the standard CLI JSON envelope

    Local offline path by default. Does not start a brand-new suite run.
    """
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


@eval_app.command(
    "recompute-scores",
    cls=BriefFullHelpCommand,
    rich_help_panel="Run",
    short_help="Re-score evidence already written by a prior run.",
)
def recompute_scores_cmd(
    experiment: str | None = typer.Option(
        None,
        "--experiment",
        help="Parent experiment id whose evidence is re-scored (required).",
    ),
    suite: str | None = typer.Option(
        "cm-eval-fixtures-core",
        "--suite",
        help="Suite id / metric pack to use (default: cm-eval-fixtures-core).",
    ),
    fixture_root: Path | None = typer.Option(
        None,
        "--fixture-root",
        help="Optional alternate fixture directory (for tests/lab layouts).",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    keep_last: int = typer.Option(
        DEFAULT_KEEP_LAST,
        "--keep-last",
        help="How many recent checkpoints to keep per suite family (default: 10).",
    ),
    keep_checkpoint: bool = typer.Option(
        False,
        "--keep-checkpoint",
        help="Keep this recompute checkpoint even when the run succeeds.",
    ),
    gold_mode: str = typer.Option(
        "strict",
        "--gold-mode",
        help="How tightly to compare against reference answers (default: strict).",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Re-score evidence already written by a prior run.

    Does not re-generate cases and does not change how commits are ranked.

    <<GIT_CG_HELP_DETAIL>>

    This is the dedicated form of `git-cg eval run --mode recompute_scores`.
    Pass --experiment <id> from a prior suite run that still has evidence
    bundles on disk. Scores are recomputed against that evidence using the
    chosen suite/metric pack.

    Flags:
    - --suite selects the metric pack context (default: cm-eval-fixtures-core)
    - --fixture-root overrides the fixture directory when needed
    - --keep-last / --keep-checkpoint control checkpoint retention
    - --gold-mode controls reference comparison strictness
    - --json emits the standard CLI JSON envelope

    Local offline path by default. Requires an existing experiment id.
    """
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


@eval_app.command(
    "doctor",
    cls=BriefFullHelpCommand,
    rich_help_panel="Inspect",
    short_help="Check local suite health (pins, metrics, fixtures).",
)
def doctor_cmd(
    suite: str = typer.Option(
        "cm-eval-fixtures-core",
        "--suite",
        help="Suite id to check (default: cm-eval-fixtures-core).",
    ),
    fixture_root: Path | None = typer.Option(
        None,
        "--fixture-root",
        help="Optional alternate fixture directory (for tests/lab layouts).",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Check local suite health (pins, metrics, fixtures).

    Offline and network-free. Does not run evaluations or change commit ranking.

    <<GIT_CG_HELP_DETAIL>>

    Reviews local pins, metric catalog wiring, fixture presence, and related
    integrity checks for one suite. Fails closed on floating ``latest`` pins
    and missing catalog/schema hashes.

    Severity policy:
    - block-severity failures flip the report red
    - warn-severity findings stay advisory and never flip green to red

    ``h.doctor_green`` aggregates block-severity checks only. Doctor also emits
    phantom-metric producer rows (ScoreResultV1) for:
    - ``h.compat_hash_resume``
    - ``h.doctor_green``
    - ``h.export_config_resolved``

    Plain-text mode prints a green summary plus non-pass checks.
    --json emits the standard CLI envelope with the full report payload.
    Exit code follows the doctor report.
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


@eval_app.command(
    "amend-brief",
    cls=BriefFullHelpCommand,
    rich_help_panel="Export & train",
    short_help="Build an amend brief from landed evaluation data.",
)
def amend_brief_cmd(
    score_run_id: str = typer.Argument(
        ...,
        help="Score-run id (rs_) to build the brief from.",
    ),
    session_thread_id: str | None = typer.Option(
        None,
        "--session-thread-id",
        help="Optional session id (sess_) to attach to the brief.",
    ),
    last_dogfood: int = typer.Option(
        3,
        "--last",
        min=0,
        help="How many recent dogfood/Lane C attachments to include (default 3).",
    ),
    doctor: bool = typer.Option(
        False,
        "--doctor",
        help="Include a doctor summary section in the brief.",
    ),
    write: bool = typer.Option(
        True,
        "--write/--no-write",
        help="Write the brief under .eval/amend_briefs/ (default: write).",
    ),
    root: Path | None = typer.Option(
        None,
        "--root",
        help="Repo root (defaults to discovery).",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Build an amend brief from landed evaluation data.

    Advisory summary of score/failure context. Never reruns, accepts, or re-ranks.

    <<GIT_CG_HELP_DETAIL>>

    Builds a local amend_brief_v1 from landed evaluation evidence for one
    score-run id (rs_). The brief is advisory only: it summarizes regime,
    family rollups, failure ids, path class, gold counters, blocking state,
    and optional preference pairs from a session twin.

    Options:
    - --session-thread-id attaches a sess_ twin when available
    - --last N includes the newest N dogfood/Lane C attachments (default 3)
    - --doctor adds a doctor projection section
    - --write/--no-write controls persistence under .eval/amend_briefs/
      (default writes)

    Guarantees:
    - authority stays advisory
    - never auto-applies reruns
    - never accepts or promotes gold
    - never mutates product ranking

    Plain text prints a short id/run/written summary.
    --json emits the standard CLI envelope with the brief payload.
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
    cls=BriefFullHelpCommand,
    hidden=True,  # dark-launch: callable, omitted from regular `git-cg eval --help`
    rich_help_panel="Advanced",
    short_help="Capture Lane C dogfood evidence for a candidate commit message.",
)
def dogfood_cmd(
    commit_message: str = typer.Option(
        ...,
        "--commit-message",
        help="Candidate commit message to capture evidence for.",
    ),
    mode: str = typer.Option(
        "async",
        "--mode",
        help="Capture mode: off | sample | always | async (default async).",
    ),
    profile: str = typer.Option(
        "default_scrub",
        "--profile",
        help="Redaction profile (default default_scrub).",
    ),
    population: list[str] | None = typer.Option(
        None,
        "--population",
        help="Deterministic sample population id(s) (repeatable; for mode=sample).",
    ),
    seed: str | None = typer.Option(
        None,
        "--seed",
        help="Explicit sample seed (for mode=sample).",
    ),
    sample_rate: float = typer.Option(
        0.10,
        "--sample-rate",
        min=0.0,
        max=1.0,
        help="Sample rate 0.0-1.0 (default 0.1; for mode=sample).",
    ),
    capture_on: str = typer.Option(
        "all",
        "--capture-on",
        help="Which rows are eligible: pass | fail | all (default all).",
    ),
    payload_path: Path | None = typer.Option(
        None,
        "--payload",
        help="Optional existing JSON payload path for the Lane C judge.",
    ),
    session_thread_id: str | None = typer.Option(
        None,
        "--session-thread-id",
        help="Optional local session-thread id to attach evidence to.",
    ),
    trigger: str = typer.Option(
        "cli",
        "--trigger",
        help="How this capture was started: cli | pre_commit | post_commit | hook.",
    ),
    write: bool = typer.Option(
        True,
        "--write/--no-write",
        help="Write dogfood attachment files (default: write).",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Capture Lane C dogfood evidence for a candidate commit message.

    Dark-launched maintainer surface. Callable, but hidden from regular eval --help.

    <<GIT_CG_HELP_DETAIL>>

    Registered and callable as ``git-cg eval dogfood``, but omitted from the
    default ``git-cg eval --help`` menu so basic users do not see it.

    Lane C is advisory only:
    - never blocks the product commit path
    - never mutates intent / ranking / accept
    - authority is always advisory on dogfood_attachment_v1
    - async mode records capture intent and never awaits the judge outcome

    Mode law (closed):
    - off: capture nothing
    - sample: deterministic membership from seed + rate + population
    - always: capture every eligible row
    - async: non-blocking capture intent (default; S6-G02a)

    capture_on (pass | fail | all) is corpus eligibility separate from product
    accept. fail retains hard-negative candidates on failing rows without
    failing the product path.

    Env knobs (maintainer/lab only): GIT_CG_EVAL_DOGFOOD_MODE / _SEED / _RATE.

    Plain text prints captured, mode, authority, and written.
    --json emits the standard CLI envelope with the capture payload.
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


@eval_app.command(
    "train-export",
    cls=BriefFullHelpCommand,
    rich_help_panel="Export & train",
    short_help="Export redacted training rows from landed bundles.",
)
def train_export_cmd(
    bundle_id: list[str] | None = typer.Option(
        None,
        "--bundle-id",
        help="Bundle id(s) to export (repeatable). Default: all landed bundles.",
    ),
    profile: str = typer.Option(
        "train_rich",
        "--profile",
        help="Redaction profile (default train_rich). Unsafe raw profiles are rejected.",
    ),
    capture_on: str = typer.Option(
        "all",
        "--capture-on",
        help="Which rows to include: pass | fail | all (default all).",
    ),
    split_group_id: str | None = typer.Option(
        None,
        "--split-group-id",
        help="Optional split-group label for the export batch.",
    ),
    notes: str | None = typer.Option(
        None,
        "--notes",
        help="Optional free-text notes for the export record.",
    ),
    write: bool = typer.Option(
        True,
        "--write/--no-write",
        help="Write export files under .eval/train_export/ (default: write).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Validate and preview paths without writing (same as --no-write).",
    ),
    root: Path | None = typer.Option(
        None,
        "--root",
        help="Repo root (defaults to discovery).",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Export redacted training rows from landed bundles.

    Builds a local redacted training export. Never emits secrets cleartext.

    <<GIT_CG_HELP_DETAIL>>

    Consumes landed evaluation bundles and writes a train_export_v1 document
    plus per-row train_row_v1 files under .eval/train_export/ (unless
    --no-write / --dry-run).

    Defaults:
    - --profile train_rich
    - --capture-on all
    - all landed bundles when --bundle-id is omitted
    - write enabled

    Optional ``--root`` overrides repo discovery (test isolation / multi-worktree).

    Scrub-failure policy (locked):
    - row that cannot be made secret-safe is dropped
    - failure is recorded in scrub_report
    - export continues with remaining rows
    - never emit cleartext
    - no .eval/quarantine/ store

    Dual-axis law (S6-G06):
    - antipattern / hard-negative rows never enter positive_gold

    --dry-run is an alias of --no-write: validate, project would-write paths,
    and leave the store untouched.

    Plain text prints export id, row counts, scrub status, and write/dry-run.
    --json emits the standard CLI envelope with the export payload.
    """
    from git_cg.eval.cli_output import emit_human_line
    from git_cg.eval.train_export import TrainExportError, train_export

    repo = _resolve_repo(root)
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


@eval_app.command(
    "triage",
    cls=BriefFullHelpCommand,
    rich_help_panel="Inspect",
    short_help="One-shot advisory view: doctor + failures + explain.",
)
def triage_cmd(
    suite: str = typer.Option(
        "cm-eval-fixtures-core",
        "--suite",
        help="Suite id for the doctor section (default: cm-eval-fixtures-core).",
    ),
    fixture_root: Path | None = typer.Option(
        None,
        "--fixture-root",
        help="Optional alternate fixture directory for the doctor section.",
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
        help="Case id for explain (auto-picks when exactly one failing case).",
    ),
    skip_doctor: bool = typer.Option(
        False,
        "--skip-doctor",
        help="Skip the doctor health section.",
    ),
    skip_failures: bool = typer.Option(
        False,
        "--skip-failures",
        help="Skip the failing-cases section.",
    ),
    skip_explain: bool = typer.Option(
        False,
        "--skip-explain",
        help="Skip the explain/blame section.",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """One-shot advisory view: doctor + failures + explain.

    Advisory only. Does not promote gold, rank intents, or change score law.

    <<GIT_CG_HELP_DETAIL>>

    Composes local library engines into one report (doctor health, failing
    cases, and explain/blame). Never nests other Typer presentation commands.

    Not score law and not an Opik ``user_acceptance`` threshold revival path.
    Use --skip-doctor / --skip-failures / --skip-explain to omit sections.

    Defaults:
    - doctor uses --suite (and optional --fixture-root)
    - failures/explain use --experiment-id, or the latest local run
    - explain uses --case, or auto-selects when exactly one failing case

    Plain text prints one combined human report.
    --json emits one ``cli_output_envelope_v1`` with an ``eval_triage_v0``
    data payload. Exit code follows the triage report.
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


@eval_app.command(
    "failures",
    cls=BriefFullHelpCommand,
    rich_help_panel="Inspect",
    short_help="List failing cases with metric and failure ids.",
)
def failures_cmd(
    experiment_id: str | None = typer.Option(
        None,
        "--experiment-id",
        help="Experiment id (defaults to latest local run).",
    ),
    regime: str | None = typer.Option(
        None,
        "--regime",
        help="Keep cases matching this regime label (e.g. A|B).",
    ),
    family: str | None = typer.Option(
        None,
        "--family",
        help="Keep cases matching this score family (e.g. I|H|gate).",
    ),
    failure_id: str | None = typer.Option(
        None,
        "--failure-id",
        help="Keep cases that include this failure id.",
    ),
    severity: str | None = typer.Option(
        None,
        "--severity",
        help="Keep cases matching this severity (block|warn|info).",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """List failing cases with metric and failure ids.

    Local read-only. Does not re-score, promote gold, or change commit ranking.

    <<GIT_CG_HELP_DETAIL>>

    Reads an experiment's landed score results and lists failing cases with
    their metric ids and failure ids. With no experiment id, uses the latest
    local run.

    Optional filters (``--regime``, ``--family``, ``--failure-id``,
    ``--severity``) are deterministic and AND-combined. They are documented
    as NTH-02 in the operator API map. The unfiltered list remains the base
    S6-D01 contract.

    Plain text prints a summary line plus one line per failing case.
    --json emits the standard CLI envelope with the failures payload.
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


@eval_app.command(
    "explain",
    cls=BriefFullHelpCommand,
    rich_help_panel="Inspect",
    short_help="Show a deterministic explanation for a failing case.",
)
def explain_cmd(
    experiment_id: str | None = typer.Option(
        None,
        "--experiment-id",
        help="Experiment id (defaults to latest local run).",
    ),
    case_id: str | None = typer.Option(
        None,
        "--case",
        help="Case id within the experiment (required when multiple fail).",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Show a deterministic explanation for a failing case.

    Local read-only. Does not re-score, promote gold, or change commit ranking.

    <<GIT_CG_HELP_DETAIL>>

    Reads landed score/evidence for one experiment case and prints a
    deterministic explanation: blame span, first divergent span, artifact
    class, failure/prevention ids, suggested surfaces, and a replay command.

    Defaults:
    - --experiment-id falls back to the latest local run
    - --case selects the target case; when omitted, selection follows the
      explain engine's local rules (including single-failure convenience)

    Plain text prints one short multi-line report per selected case.
    --json emits the standard CLI envelope with the explain payload.
    """
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


@eval_app.command(
    "compare",
    cls=BriefFullHelpCommand,
    rich_help_panel="Inspect",
    short_help="Diff two cases (structure and metrics).",
)
def compare_cmd(
    a_experiment_id: str = typer.Option(
        ...,
        "--a-experiment-id",
        help="Left experiment id (required).",
    ),
    a_case_id: str = typer.Option(
        ...,
        "--a-case",
        help="Left case id (required).",
    ),
    b_experiment_id: str = typer.Option(
        ...,
        "--b-experiment-id",
        help="Right experiment id (required).",
    ),
    b_case_id: str = typer.Option(
        ...,
        "--b-case",
        help="Right case id (required).",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Diff two cases (structure and metrics).

    Local read-only. Does not replay, re-score, or change commit ranking.

    <<GIT_CG_HELP_DETAIL>>

    Compares two landed case results side by side:
    - metric pass/value deltas
    - structural fields such as deterministic_pass and failed_metric_ids
    - lineage link detection when one experiment is a recompute child of the other

    All four selectors are required:
    --a-experiment-id / --a-case and --b-experiment-id / --b-case.

    When the experiments are lineage-linked, compare_source is
    ``replay_compare_v1``; otherwise it is ``case_result_delta``.
    The delta itself is always derived deterministically from the two case
    rows. Compare only reads; it never writes replay artifacts.

    Plain text prints a short summary plus changed metrics.
    --json emits the standard CLI envelope with the full compare payload.
    """
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


@eval_app.command(
    "replay",
    cls=BriefFullHelpCommand,
    rich_help_panel="Advanced",
    short_help="Replay generation into a new bundle (source unchanged).",
)
def replay_cmd(
    bundle: str | None = typer.Option(
        None,
        "--bundle",
        help="Source bundle path or accept-path id/stem.",
    ),
    experiment_id: str | None = typer.Option(
        None,
        "--experiment-id",
        help="Experiment id (use with --case for explain-linked replay).",
    ),
    case_id: str | None = typer.Option(
        None,
        "--case",
        help="Case id within the experiment.",
    ),
    notes: str | None = typer.Option(
        None,
        "--notes",
        help="Optional notes stored on the compare record.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Validate and project paths without writing files.",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Replay generation into a new bundle (source unchanged).

    Offline structural replay. Writes a new bundle + compare; never mutates the source.

    <<GIT_CG_HELP_DETAIL>>

    Reads an existing ape_bundle_v1 (explicit path/id via --bundle, or
    explain-linked via --experiment-id + --case) and writes:

    - a new replay bundle under the local replays store
    - a schema-valid replay_compare_v1 record

    Guarantees:
    - source bundle bytes are never mutated (immutability law)
    - session_thread_id is preserved; new replay identity / trace / hashes
    - harness, metric catalog, and schema pack pins are recorded on compare
    - offline-first structural lineage replay only
      (live replay_generation is a separate run-orchestrator mode)

    --dry-run validates and projects would-write paths without writing.

    Plain text prints replay id, regression status, lineage_ok, source_mutated,
    and paths. --json emits the standard CLI envelope with the replay payload.
    """
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


@eval_app.command(
    "promote",
    cls=BriefFullHelpCommand,
    rich_help_panel="Advanced",
    short_help="Promote a scrubbed candidate with contamination checks.",
)
def promote_cmd(
    bundle: str = typer.Option(
        ...,
        "--bundle",
        help="Source bundle path or id (accept-path or replay).",
    ),
    destination: str = typer.Option(
        ...,
        "--destination",
        help=(
            "Where to send it: fixture_lane_a | hard_negative | preference_pair | "
            "observability_fixture | quarantine | reject."
        ),
    ),
    owner: str = typer.Option(
        ...,
        "--owner",
        help="Who owns this promotion (local handle).",
    ),
    label: str = typer.Option(
        ...,
        "--label",
        help="Promotion label (not silent gold).",
    ),
    provenance: str = typer.Option(
        ...,
        "--provenance",
        help="Why this is allowed (not popularity/accept alone).",
    ),
    redaction_profile: str = typer.Option(
        ...,
        "--redaction-profile",
        help="Redaction profile applied to the promoted artifact.",
    ),
    stage: str = typer.Option(
        "scrubbed_candidate",
        "--stage",
        help="Source stage: failure_or_capture | scrubbed_candidate (default scrubbed_candidate).",
    ),
    split_group_id: str | None = typer.Option(
        None,
        "--split-group-id",
        help="Contamination unit (defaults from bundle/session).",
    ),
    review_id: str | None = typer.Option(
        None,
        "--review-id",
        help="Optional reviewed item id (advisory only; never sole gold authority).",
    ),
    notes: str | None = typer.Option(
        None,
        "--notes",
        help="Optional free-text notes for the decision record.",
    ),
    popularity_signal: bool = typer.Option(
        False,
        "--popularity-signal",
        help="Mark popularity/acceptance signal (cannot promote golden).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Validate the decision without writing files.",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Promote a scrubbed candidate with contamination checks.

    Governed promote path. Writes a decision audit; never silent-mints gold from accept or popularity.

    <<GIT_CG_HELP_DETAIL>>

    Closed state machine:

      failure_or_capture → scrubbed_candidate → terminal destination

    Terminal destinations:
    - fixture_lane_a
    - hard_negative
    - preference_pair
    - observability_fixture
    - quarantine
    - reject

    Required: --bundle, --destination, --owner, --label, --provenance,
    --redaction-profile. split_group_id is required for contamination control
    (explicit or derived from the source bundle/session).

    Forbidden (named denials, never silent):
    - silent gold mint from production accept / popularity
    - human-review-alone golden promotion
    - Expand-with-AI synthetic rows without quarantine
    - antipattern rows into positive_train destinations
    - unresolved HITL dispute / open review on non-park destinations

    Denial law (S6-E09): every rejection has a named denial_reason. After the
    source candidate is resolved, denials persist a candidate-class audit row
    under .eval/index/promotions/ (accepted=false) and never write fixture/gold
    destination artifacts.

    --dry-run validates and previews accept/deny without writing.

    Plain text prints accepted, promotion id, destination, and paths.
    --json emits the standard CLI envelope (denials include denial_reason +
    retained decision when present).
    """
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
        # Print S6-E09 denial context before exiting (_emit_slice5_error raises Exit).
        from git_cg.eval.cli_output import emit_human_line, envelope_message

        code = getattr(exc, "code", "EVAL_USAGE")
        exit_code = int(getattr(exc, "exit_code", 2))
        hint = getattr(exc, "hint", None)
        err = envelope_message(code, str(exc), hint=hint)
        line = f"eval promote: {err['message']}"
        if hint := err.get("hint"):
            line = f"{line} (hint: {hint})"
        emit_human_line(line, err=True)
        denial = getattr(exc, "denial_reason", None)
        decision_path = getattr(exc, "decision_path", None)
        if denial:
            emit_human_line(f"  denial_reason: {denial}", err=True)
        if decision_path:
            emit_human_line(f"  denial_audit: {decision_path}", err=True)
        raise typer.Exit(code=exit_code) from None
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


@eval_app.command(
    "diagnose",
    cls=BriefFullHelpCommand,
    rich_help_panel="Inspect",
    short_help="Create or update a diagnostic issue from a failure.",
)
def diagnose_cmd(
    experiment_id: str | None = typer.Option(
        None,
        "--experiment-id",
        help="Experiment id (defaults to latest local run).",
    ),
    case_id: str | None = typer.Option(
        None,
        "--case",
        help="Case id within the experiment.",
    ),
    code: str | None = typer.Option(
        None,
        "--code",
        help="Diagnostic code (defaults to the first failure id).",
    ),
    title: str | None = typer.Option(
        None,
        "--title",
        help="Optional issue title override.",
    ),
    product_impact: str = typer.Option(
        "unknown",
        "--product-impact",
        help="Impact area: accept_path|golden|train|export|docs|unknown.",
    ),
    owner: str | None = typer.Option(
        None,
        "--owner",
        help="Optional issue owner handle.",
    ),
    notes: str | None = typer.Option(
        None,
        "--notes",
        help="Optional free-text notes for the issue.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Validate and project the issue without writing files.",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Create or update a diagnostic issue from a failure.

    Builds a local diagnostic issue record. Does not change commit ranking.

    <<GIT_CG_HELP_DETAIL>>

    Reads one failing case (or the selected case) from an experiment and
    creates/updates a diagnostic issue under the local issues/diagnostics
    store. With no experiment id, uses the latest local run.

    Defaults:
    - --code falls back to the first failure id on the case
    - --product-impact defaults to unknown
    - --title / --owner / --notes are optional annotations

    --dry-run fully builds and schema-validates the issue, then reports the
    paths that would be written without touching disk.
    Plain text prints create/upsert summary (and would_write paths on dry-run).
    --json emits the standard CLI envelope with the diagnose payload.
    """
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


# Group-level brief/detail help (parent surface). Help-only; no queue I/O.
@review_app.callback()
def review_group_callback(
    detail: bool = _detail_help_option(),
) -> None:
    """Own the group ``--detail`` option; Typer group callback body is a no-op."""
    return


@review_app.command(
    "enqueue",
    cls=BriefFullHelpCommand,
    short_help="Enqueue an advisory human-review item.",
)
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
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Enqueue an advisory human-review item.

    Creates a local queue entry for a case or bundle. Never writes gold or
    changes product commit ranking.

    <<GIT_CG_HELP_DETAIL>>

    Writes under ``.eval/review_queue/`` unless ``--dry-run`` validates only.
    Requires ``--reviewer`` (opaque local handle, not email). Target one of
    ``--case`` or ``--bundle-id``.

    Optional human dimensions: ``--craft-rating``, ``--gold-dispute``
    (true|false), ``--regime-label`` (A|B|unknown), plus free-text ``--notes``.
    Default redaction profile is ``meta_eval_scrub``.

    Authority stays advisory. ``--json`` emits the standard CLI envelope with
    the created item payload.
    """
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


@review_app.command(
    "list",
    cls=BriefFullHelpCommand,
    short_help="List local review-queue items.",
)
def review_list_cmd(
    status: str | None = typer.Option(None, "--status", help="Filter: pending|in_review|adjudicated|dismissed."),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """List local review-queue items.

    Read-only inspection of the advisory queue. Never writes gold or changes
    product commit ranking.

    <<GIT_CG_HELP_DETAIL>>

    Optional ``--status`` filter: pending | in_review | adjudicated | dismissed.
    Plain text prints a count plus one line per item (id, status, case,
    reviewer). ``--json`` emits the standard CLI envelope with the full list
    payload.
    """
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


@review_app.command(
    "rollup",
    cls=BriefFullHelpCommand,
    short_help="Roll up multi-rater advisory scores for review items.",
)
def review_rollup_cmd(
    case_id: str | None = typer.Option(None, "--case", help="Optional case_id filter."),
    bundle_id: str | None = typer.Option(None, "--bundle-id", help="Optional bundle_id filter."),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Roll up multi-rater advisory scores for review items.

    Read-only. Authority stays advisory and never sole-promotes gold.

    <<GIT_CG_HELP_DETAIL>>

    Aggregates multi-rater dimension/outcome majority and craft spread for
    matching review items. Optional filters: ``--case``, ``--bundle-id``.

    Plain text prints group count plus per-target summaries (reviewer_count,
    craft mean/disagreement, dispute/regime majority, outcome majority).
    ``--json`` emits the standard CLI envelope with the full rollup payload.
    ``can_sole_promote_gold`` remains false by contract.
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


@review_app.command(
    "show",
    cls=BriefFullHelpCommand,
    short_help="Show one local review-queue item.",
)
def review_show_cmd(
    review_id: str = typer.Argument(..., help="Review id."),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Show one local review-queue item.

    Read-only inspection of a single advisory review. Never writes gold.

    <<GIT_CG_HELP_DETAIL>>

    Requires a review id argument. Plain text prints status and authority
    (always advisory) and, when present, adjudication outcome + outcome_ref.
    ``--json`` emits the standard CLI envelope with the full item payload.
    """
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


@review_app.command(
    "claim",
    cls=BriefFullHelpCommand,
    short_help="Claim a pending review item (pending → in_review).",
)
def review_claim_cmd(
    review_id: str = typer.Argument(..., help="Review id."),
    reviewer: str = typer.Option(..., "--reviewer", help="Opaque local reviewer handle."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate without writing."),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Claim a pending review item (pending → in_review).

    Local queue state only. Never writes gold or changes product commit ranking.

    <<GIT_CG_HELP_DETAIL>>

    Requires a review id and ``--reviewer`` (opaque local handle). Moves a
    pending item to in_review and records claimed_by. ``--dry-run`` validates
    without writing.

    ``--json`` emits the standard CLI envelope with the updated item payload.
    """
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


@review_app.command(
    "adjudicate",
    cls=BriefFullHelpCommand,
    short_help="Adjudicate an in_review item (emits typed outcome_ref; never writes gold).",
)
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
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Adjudicate an in_review item (emits typed outcome_ref; never writes gold).

    Authority stays advisory. Never writes gold or changes product commit ranking.

    <<GIT_CG_HELP_DETAIL>>

    Requires a review id and typed ``--outcome``:
    approve_promote | reject | needs_work | dismiss.

    Emits a typed outcome_ref on success. Optional ``--adjudicator``,
    ``--destination-hint`` (advisory promote hint only), and ``--notes``.
    ``--dry-run`` validates without writing.

    ``--json`` emits the standard CLI envelope with the item + outcome_ref
    payload.
    """
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


@review_app.command(
    "dismiss",
    cls=BriefFullHelpCommand,
    short_help="Dismiss a pending/in_review item (terminal).",
)
def review_dismiss_cmd(
    review_id: str = typer.Argument(..., help="Review id."),
    reason: str = typer.Option(..., "--reason", help="Required dismissal reason."),
    adjudicator: str | None = typer.Option(None, "--adjudicator", help="Opaque adjudicator handle."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate without writing."),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Dismiss a pending/in_review item (terminal).

    Closes without promotion. Never writes gold or changes product commit ranking.

    <<GIT_CG_HELP_DETAIL>>

    Requires a review id and ``--reason``. Optional ``--adjudicator``. Terminal
    for pending/in_review items. ``--dry-run`` validates without writing.

    ``--json`` emits the standard CLI envelope with the updated item payload.
    """
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


# Group-level brief/detail help (parent surface). Help-only; no session I/O.
@session_app.callback()
def session_group_callback(
    detail: bool = _detail_help_option(),
) -> None:
    """Own the group ``--detail`` option; Typer group callback body is a no-op."""
    return


@session_app.command(
    "show",
    cls=BriefFullHelpCommand,
    short_help="Show one local commit session.",
)
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
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Show one local commit session.

    Read-only lookup of one local commit-session twin. Does not change commit
    ranking or gold.

    <<GIT_CG_HELP_DETAIL>>

    Requires ``--id`` as ``sess_<uuid>`` (``sessmeta_`` alias accepted). Optional
    ``--root`` overrides repo discovery.

    Reads a local ``commit_session_thread_v1`` twin under ``.eval/sessions/`` and
    prints a map-only projection (id, lifecycle, schema, network=false). Missing
    twin / bad id shape fails closed. Never opens Opik/network, never builds a
    chat timeline or graph browser, and never grants accept authority or ranking
    mutation.

    ``--json`` emits the standard CLI envelope with the full session payload.
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


# Group-level brief/detail help (parent surface). Help-only; no thread I/O.
@thread_app.callback()
def thread_group_callback(
    detail: bool = _detail_help_option(),
) -> None:
    """Own the group ``--detail`` option; Typer group callback body is a no-op."""
    return


@thread_app.command(
    "show",
    cls=BriefFullHelpCommand,
    short_help="Show one local session thread.",
)
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
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Show one local session thread.

    Read-only lookup of one local session-thread record. Does not change commit
    ranking or gold.

    <<GIT_CG_HELP_DETAIL>>

    Requires ``--id`` as ``sess_<uuid>`` (``sessmeta_`` alias accepted). Optional
    ``--root`` overrides repo discovery.

    Projects the same local ``commit_session_thread_v1`` capture episode as a
    thread-oriented map (message version count, lifecycle, optional preference
    pairs / attempt ids). Store fields only — not a chat timeline or graph
    browser. Local-only; never opens Opik/network and never mutates ranking.

    ``--json`` emits the standard CLI envelope with the full thread payload.
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


# Group-level brief/detail help (parent surface). Help-only; no issue I/O.
@issue_app.callback()
def issue_group_callback(
    detail: bool = _detail_help_option(),
) -> None:
    """Own the group ``--detail`` option; Typer group callback body is a no-op."""
    return


@issue_app.command(
    "list",
    cls=BriefFullHelpCommand,
    short_help="List local diagnostic issues.",
)
def issue_list_cmd(
    status: str | None = typer.Option(
        None, "--status", help="Filter by status (open|acknowledged|resolved|suppressed|reopened)."
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """List local diagnostic issues.

    Read-only inspection of local diagnostic issues created from eval failures.
    Newest ``last_seen`` first. Does not change commit ranking or gold.

    <<GIT_CG_HELP_DETAIL>>

    Optional ``--status`` filter: open | acknowledged | resolved | suppressed |
    reopened. Plain text prints a count plus one line per issue (id, status,
    severity, code, occurrences). ``--json`` emits the standard CLI envelope with
    the full list payload.
    """
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


@issue_app.command(
    "show",
    cls=BriefFullHelpCommand,
    short_help="Show one local diagnostic issue.",
)
def issue_show_cmd(
    issue_id: str = typer.Argument(..., help="Issue id."),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Show one local diagnostic issue.

    Read-only inspection of a single diagnostic issue. Does not change commit
    ranking or gold.

    <<GIT_CG_HELP_DETAIL>>

    Requires an issue id argument. Plain text prints status/severity/title plus
    fingerprint, occurrence count, linked failure/metric ids, and any suggested
    surfaces. ``--json`` emits the standard CLI envelope with the full issue
    payload.
    """
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


@issue_app.command(
    "resolve",
    cls=BriefFullHelpCommand,
    short_help="Mark a local diagnostic issue resolved.",
)
def issue_resolve_cmd(
    issue_id: str = typer.Argument(..., help="Issue id."),
    resolution_evidence: str = typer.Option(..., "--resolution-evidence", help="Required fix-verification evidence."),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Mark a local diagnostic issue resolved.

    Local issue lifecycle only. Requires fix-verification evidence. Does not
    change commit ranking or gold.

    <<GIT_CG_HELP_DETAIL>>

    Requires an issue id and ``--resolution-evidence``. Legal from open,
    acknowledged, or reopened (closed transition matrix). Re-applying resolved
    is an idempotent no-op that still requires evidence. Free text is secret-
    projected before persist.

    ``--json`` emits the standard CLI envelope with the transition payload.
    """
    _run_issue_transition(
        "eval issue resolve",
        issue_id=issue_id,
        target="resolved",
        resolution_evidence=resolution_evidence,
        reason=None,
        as_json=as_json,
    )


@issue_app.command(
    "reopen",
    cls=BriefFullHelpCommand,
    short_help="Reopen a local diagnostic issue.",
)
def issue_reopen_cmd(
    issue_id: str = typer.Argument(..., help="Issue id."),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Reopen a local diagnostic issue.

    Local issue lifecycle only. Typically used after resolved/suppressed.
    Does not change commit ranking or gold.

    <<GIT_CG_HELP_DETAIL>>

    Requires an issue id. Legal from acknowledged, resolved, or suppressed
    (closed transition matrix). Re-applying reopened is an idempotent no-op.
    From reopened, operators can acknowledge, resolve, or suppress again.

    ``--json`` emits the standard CLI envelope with the transition payload.
    """
    _run_issue_transition(
        "eval issue reopen",
        issue_id=issue_id,
        target="reopened",
        resolution_evidence=None,
        reason=None,
        as_json=as_json,
    )


@issue_app.command(
    "suppress",
    cls=BriefFullHelpCommand,
    short_help="Suppress a local diagnostic issue.",
)
def issue_suppress_cmd(
    issue_id: str = typer.Argument(..., help="Issue id."),
    reason: str = typer.Option(..., "--reason", help="Required suppression reason."),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Suppress a local diagnostic issue.

    Local issue lifecycle only. Requires a suppression reason. Does not change
    commit ranking or gold.

    <<GIT_CG_HELP_DETAIL>>

    Requires an issue id and ``--reason``. Legal from open, acknowledged, or
    reopened (closed transition matrix). Re-applying suppressed is an
    idempotent no-op that still requires a reason. Reason text is secret-
    projected and recorded in notes.

    ``--json`` emits the standard CLI envelope with the transition payload.
    """
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


# Group-level brief/detail help (parent surface). Help-only; no Opik I/O.
@opik_app.callback()
def opik_group_callback(
    detail: bool = _detail_help_option(),
) -> None:
    """Own the group ``--detail`` option; Typer group callback body is a no-op."""
    return


# Nested config group brief/detail help. Help-only; no config I/O.
@opik_config_app.callback()
def opik_config_group_callback(
    detail: bool = _detail_help_option(),
) -> None:
    """Own the group ``--detail`` option; Typer group callback body is a no-op."""
    return


def _config_show_impl(*, as_json: bool = False, deprecated_from: str | None = None) -> None:
    """Shared secret-safe config show implementation (canonical + alias)."""
    import os

    from git_cg.eval.cli_output import emit_human_line
    from git_cg.eval.mirror.config import (
        PROJECT_LANES,
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
            emit_human_line("eval opik config show: invalid (fail-closed)", err=True)
            emit_human_line(f"  health={ExportHealth.CONFIG_ERROR.value}", err=True)
            emit_human_line(f"  error={exc}", err=True)
            emit_human_line("  api_key_present=false", err=True)
            emit_human_line("  product_accept_blocked=false", err=True)
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
        mode = str(view.get("mode") or "off")
        workspace = view.get("workspace")
        redaction = view.get("redaction_profile")
        projects = view.get("projects") if isinstance(view.get("projects"), dict) else {}
        emit_human_line("eval opik config show:")
        emit_human_line(f"  mode={mode}")
        emit_human_line(f"  health={health_hint}")
        emit_human_line(f"  workspace={workspace if workspace not in (None, '') else '-'}")
        if projects:
            for lane in PROJECT_LANES:
                pin = projects.get(lane)
                emit_human_line(f"  project.{lane}={pin if pin not in (None, '') else '-'}")
        else:
            emit_human_line("  projects=-")
        emit_human_line(f"  api_key_present={str(bool(masked.get('api_key_present'))).lower()}")
        if masked.get("api_key"):
            emit_human_line(f"  api_key={masked['api_key']}")
        emit_human_line(f"  redaction_profile={redaction if redaction not in (None, '') else '-'}")
        emit_human_line("  product_accept_blocked=false")
        fallback = mode_fallback_token(config)
        if fallback:
            emit_human_line(f"  mode_fallback={fallback}")
    raise typer.Exit(code=exit_code)


@opik_config_app.command(
    "show",
    cls=BriefFullHelpCommand,
    short_help="Show resolved Opik/mirror config without secrets.",
)
def opik_config_show_cmd(
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Show resolved Opik/mirror config without secrets.

    Offline and secret-safe. Never prints raw API keys or reaches the network.

    <<GIT_CG_HELP_DETAIL>>

    Prints ``public_config_view`` plus a masked secrets block
    (``api_key`` via ``mask_secret()`` redacted length form, ``api_key_present``)
    and an operator health hint.

    Health hint values include skipped_off / deferred / pending / config_error.
    Invalid mode tokens fail closed (exit 2). Successful show exits 0.

    Plain text is a multi-line summary (mode, health, workspace, four-lane
    project pins, ``api_key_present``, redaction profile,
    ``product_accept_blocked``). ``--json`` wraps the full secret-safe payload in
    the standard CLI envelope (deprecation warnings apply on the temporary flat
    alias ``git-cg eval config show``).

    No transport, no queue drain, and no accept/ranking side effects.
    """
    _config_show_impl(as_json=as_json, deprecated_from=None)


@opik_app.command(
    "doctor",
    cls=BriefFullHelpCommand,
    short_help="Check Opik/export health without exposing secrets.",
)
def opik_doctor_cmd(
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Check Opik/export health without exposing secrets.

    Local only: no transport and no network. Raw API keys are never printed.

    <<GIT_CG_HELP_DETAIL>>

    Inspects resolved Opik/mirror config, export health, and local export-queue
    counts without contacting Opik. Secret-bearing output always passes through
    ``mask_secret()`` (redacted length form) plus a presence boolean — raw token
    values and prefixes are never printed.

    Typical checks include:
    - ``opik.config_resolved`` (block): config health / invalid mode tokens
    - ``opik.mode``: mode + health observability
    - ``opik.api_key_present``: ambient key presence (warn when active mode
      lacks a key)
    - ``opik.queue_readable`` / ``opik.queue_failed_drainable``: local queue
      readability and failed-row backlog

    ``h.doctor_green`` follows block-severity only (config must resolve cleanly).
    Exit code is 0 when config is healthy, otherwise 2 (fail-closed). Plain text
    prints a green summary plus non-pass checks; ``--json`` emits the standard
    CLI envelope with the full report payload.
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


@eval_app.command(
    "config",
    cls=BriefFullHelpCommand,
    rich_help_panel="Deprecated",
    deprecated=True,
    short_help="Alias of eval opik config show.",
)
def config_cmd(
    action: str = typer.Argument(
        ...,
        help="Only 'show' is supported on this temporary alias.",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Alias of eval opik config show.

    Temporary compatibility shim. Prefer the nested canonical path.

    <<GIT_CG_HELP_DETAIL>>

    Canonical: git-cg eval opik config show

    This flat alias still runs the secret-safe config show path and emits a
    deprecation warning (stderr human / envelope warnings[] JSON).

    Removal target: first minor release after S6 GA.

    Supported action: show only.
    """
    if action != "show":
        typer.echo(f"config: unknown action {action!r} (supported: show)", err=True)
        raise typer.Exit(code=2)
    _config_show_impl(as_json=as_json, deprecated_from="git-cg eval config show")


# --------------------------------------------------------------------------
# Nested export (landed S4) + temporary dashed aliases
# --------------------------------------------------------------------------


# export_app registered near module top for help-panel order.


@checkpoint_app.command(
    "list",
    cls=BriefFullHelpCommand,
    short_help="List local evaluation checkpoints (read-only).",
)
def checkpoint_list_cmd(
    suite_id: str | None = typer.Option(
        None,
        "--suite",
        help="Optional suite_id filter.",
    ),
    root: Path | None = typer.Option(
        None,
        "--root",
        help="Repo root (defaults to discovery).",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """List local evaluation checkpoints (read-only).

    Offline inventory of ``.eval/checkpoints`` for resume/GC planning. Does not
    mutate checkpoint files, contact Opik, or change product ranking.

    <<GIT_CG_HELP_DETAIL>>

    Each row includes id, mtime, suite, short compat hash, short pin, live_match
    against the live compat preimage, and pending/completed counts. Unreadable
    or schema-invalid checkpoints are skipped. Optional ``--suite`` filters by
    suite_id. ``--json`` emits the standard CLI envelope.
    """
    from git_cg.eval.checkpoint_store import list_checkpoint_inventory
    from git_cg.eval.cli_output import emit_human_line

    try:
        repo = _resolve_repo(root)
    except Exception as exc:
        if as_json:
            emit_json_envelope(
                build_envelope(
                    "eval checkpoint list",
                    ok=False,
                    data={},
                    errors=[{"code": "EVAL_REPO_UNRESOLVABLE", "message": str(exc)}],
                )
            )
        else:
            emit_human_line(f"eval checkpoint list: repo root unresolvable: {exc}", err=True)
        raise typer.Exit(code=1) from None

    rows = list_checkpoint_inventory(repo, suite_id=suite_id)
    payload = {
        "checkpoints": [row.to_dict() for row in rows],
        "checkpoint_count": len(rows),
        "suite_id": suite_id,
    }
    if as_json:
        emit_json_envelope(build_envelope("eval checkpoint list", ok=True, data=payload))
    else:
        emit_human_line(f"eval checkpoint list: {payload['checkpoint_count']} checkpoint(s)")
        for row in rows:
            emit_human_line(
                f"  {row.checkpoint_id}: suite={row.suite_id or '-'} "
                f"mtime={row.mtime or '-'} "
                f"compat={row.compat_hash_short or '-'} "
                f"pin={row.pin_short or '-'} "
                f"live_match={str(row.live_match).lower()} "
                f"completed={row.completed_count} pending={row.pending_count}"
            )
    raise typer.Exit(code=0)


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
    # Always emit a stable zeroed shape so machine consumers see a consistent
    # key set on an empty/absent queue (healthy, not a defect).
    counts: dict[str, int] = {
        "pending": 0,
        "sending": 0,
        "sent": 0,
        "failed": 0,
        "dropped": 0,
        "unreadable": 0,
    }
    if qdir.is_dir():
        for path in sorted(qdir.glob("*.json")):
            try:
                item = load_queue_item(path.stem, repo_root=repo)
            except Exception:
                counts["unreadable"] += 1
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
    if not any(counts.values()):
        # Empty/absent queue is healthy; report it without inventing rows.
        typer.echo("queue empty")
        return
    for status in ("pending", "sending", "sent", "failed", "dropped", "unreadable"):
        if counts.get(status):
            typer.echo(f"{status} {counts[status]}")


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


# Group-level brief/detail help (parent surface). Help-only; no queue I/O.
@export_app.callback()
def export_group_callback(
    detail: bool = _detail_help_option(),
) -> None:
    """Own the group ``--detail`` option; Typer group callback body is a no-op."""
    return


@export_app.command(
    "status",
    cls=BriefFullHelpCommand,
    short_help="Show export-queue status (read-only, offline).",
)
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
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
    _deprecated_from: str | None = typer.Option(None, hidden=True),
) -> None:
    """Show export-queue status (read-only, offline).

    Never mutates the queue and never contacts Opik or the network.

    <<GIT_CG_HELP_DETAIL>>

    Prints the export queue directory and per-status counts (pending, sending,
    sent, failed, dropped, unreadable). May also surface a config health hint
    and fail closed on an invalid mode token.

    ``--json`` emits the standard CLI envelope with queue_dir, counts, health,
    and bad_mode fields. Exit codes: 0 when healthy, 1 if the repo root cannot
    be resolved, 2 on invalid mode configuration.
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


@export_app.command(
    "retry",
    cls=BriefFullHelpCommand,
    short_help="Re-queue failed export rows for another drain attempt.",
)
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
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
    _deprecated_from: str | None = typer.Option(None, hidden=True),
) -> None:
    """Re-queue failed export rows for another drain attempt.

    Moves ``failed → pending`` so the next ``export drain`` can claim them.
    Never blocks product accept.

    <<GIT_CG_HELP_DETAIL>>

    Default policy: reclaim rows whose last_error_class is retryable
    (``export_network`` / ``export_timeout`` / empty). Validation/auth/size
    failures require ``--force``.

    Optional ``--id`` limits retry to one queue row; ``--max-items`` caps how
    many failed rows are re-queued this invocation.

    ``--json`` emits the standard CLI envelope with retried/skipped/unreadable
    counts. Exit code is 0 (including fail-open paths such as an unresolvable
    repo root).
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
    not_found: list[str] = []
    for qid in targets:
        if max_items is not None and retried >= max_items:
            break
        try:
            item = load_queue_item(qid, repo_root=repo)
        except ExportQueueError:
            unreadable += 1
            # Explicit --id miss is not-found, not silent corruption.
            if queue_id and qid == queue_id:
                not_found.append(qid)
            continue
        except Exception:
            unreadable += 1
            if queue_id and qid == queue_id:
                not_found.append(qid)
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
        data: dict[str, object] = {"retried": retried, "skipped": skipped, "unreadable": unreadable}
        if not_found:
            # Surface not-found ids alongside the counts for machine consumers.
            data["not_found"] = not_found
            warnings = [
                *warnings,
                {
                    "code": "EVAL_EXPORT_ID_NOT_FOUND",
                    "message": f"queue id not found: {', '.join(not_found)}",
                },
            ]
        emit_json_envelope(
            build_envelope(
                "eval export retry",
                ok=True,
                data=data,
                warnings=warnings,
            )
        )
    else:
        for qid in not_found:
            typer.echo(f"id not found: {qid}")
        typer.echo(f"retried {retried} skipped {skipped} unreadable {unreadable}")
    raise typer.Exit(code=0)


@export_app.command(
    "drain",
    cls=BriefFullHelpCommand,
    short_help="Drain the export queue through the Opik transport.",
)
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
    max_items: int | None = typer.Option(
        None,
        "--max-items",
        help="Cap on rows processed this drain.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Resolve config + list pending rows; no upload.",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
    _deprecated_from: str | None = typer.Option(None, hidden=True),
) -> None:
    """Drain the export queue through the Opik transport.

    Always exits 0 unless the config is invalid (fail-closed). Transport and
    secret failures are classified on queue rows and never block hooks.

    <<GIT_CG_HELP_DETAIL>>

    Uploads pending rows through the Opik transport (unless ``mode=off`` or
    ``--dry-run``). ``--dry-run`` resolves config and lists pending rows without
    uploading. ``--max-items`` caps how many rows are processed this drain.

    Fail-closed on invalid config / mode tokens (non-zero exit). Transport and
    secret failures are recorded on the affected queue rows and do not produce a
    hook-blocking exit.

    ``--json`` emits the standard CLI envelope with mirror/export result
    payloads and any deprecation warnings when invoked via a dashed alias.
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
    root: Path | None = typer.Option(
        None,
        "--root",
        help="Repo root (defaults to discovery).",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Alias of eval export status.

    Temporary dashed alias. Prefer the nested canonical path.

    <<GIT_CG_HELP_DETAIL>>

    Canonical: git-cg eval export status

    Still runs the read-only offline queue-status path and emits a deprecation
    warning (stderr human / envelope warnings[] JSON).

    Removal target: first minor release after S6 GA.
    """
    export_status_cmd(root=root, as_json=as_json, _deprecated_from="git-cg eval export-status")


def _export_retry_alias(
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
        help="Also retry validation/auth/size failures.",
    ),
    max_items: int | None = typer.Option(
        None,
        "--max-items",
        help="Cap on failed rows re-queued this invocation.",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Alias of eval export retry.

    Temporary dashed alias. Prefer the nested canonical path.

    <<GIT_CG_HELP_DETAIL>>

    Canonical: git-cg eval export retry

    Still re-queues failed rows (failed → pending) under the same policy as the
    nested command and emits a deprecation warning.

    Removal target: first minor release after S6 GA.
    """
    export_retry_cmd(
        root=root,
        queue_id=queue_id,
        force=force,
        max_items=max_items,
        as_json=as_json,
        _deprecated_from="git-cg eval export-retry",
    )


def _export_drain_alias(
    root: Path | None = typer.Option(
        None,
        "--root",
        help="Repo root (defaults to discovery).",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    max_items: int | None = typer.Option(
        None,
        "--max-items",
        help="Cap on rows processed this drain.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Resolve config + list pending rows; no upload.",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON instead of plain text.",
    ),
    detail: bool = _detail_help_option(),
) -> None:
    """Alias of eval export drain.

    Temporary dashed alias. Prefer the nested canonical path.

    <<GIT_CG_HELP_DETAIL>>

    Canonical: git-cg eval export drain

    Still drains pending queue rows through the Opik transport under the same
    fail-closed/config and hook-safe exit policy, and emits a deprecation
    warning.

    Removal target: first minor release after S6 GA.
    """
    export_drain_cmd(
        root=root,
        max_items=max_items,
        dry_run=dry_run,
        as_json=as_json,
        _deprecated_from="git-cg eval export-drain",
    )


eval_app.command(
    "export-status",
    cls=BriefFullHelpCommand,
    rich_help_panel="Deprecated",
    deprecated=True,
    short_help="Alias of eval export status.",
)(_export_status_alias)
eval_app.command(
    "export-retry",
    cls=BriefFullHelpCommand,
    rich_help_panel="Deprecated",
    deprecated=True,
    short_help="Alias of eval export retry.",
)(_export_retry_alias)
eval_app.command(
    "export-drain",
    cls=BriefFullHelpCommand,
    rich_help_panel="Deprecated",
    deprecated=True,
    short_help="Alias of eval export drain.",
)(_export_drain_alias)
