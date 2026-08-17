"""Thin ``git-cg eval`` corpus-helper CLI (Issue #231, D11 / B1-b).

This is a **delegation-only** Typer sub-app. It exposes corpus helpers
(``materialize-core-goldens`` and ``encode-fixture``) plus the thin S4
mirror surface (``config show``, nested ``export status|retry|drain``):

* No binder invocation at import time (``git_cg.eval.binding`` is never
  imported by the module body; export commands may resolve repo paths).
* No accept-path writes under ``.eval/bundles/acceptpath/**``.
* Opik SDK is imported only lazily inside drain transport construction.
* Not the S6 doctor / review / amend-brief UX.

``materialize-core-goldens`` may write corpus golden files under
``tests/fixtures/eval/**`` — that is a corpus write, not an accept-path write.
"""

from __future__ import annotations

from pathlib import Path

import typer

eval_app = typer.Typer(
    add_completion=False,
    help="Corpus helpers: materialize core goldens and encode fixtures (no binder, no .eval writes).",
    no_args_is_help=True,
)


@eval_app.command("materialize-core-goldens")
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
    """Materialize checked-in core golden bundles + snapshot (corpus write only)."""
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


@eval_app.command("encode-fixture")
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
    """Encode a fixture into an ape_bundle_v1 and print its identity summary."""
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

    fixture: dict
    case_id: str | None = None
    resolved_suite_id: str | None = None

    if path is not None:
        try:
            fixture = load_fixture_dict(path)
        except FixtureLoadError as exc:
            typer.echo(f"encode-fixture failed: {exc}", err=True)
            raise typer.Exit(code=1) from None
    else:
        # --id resolution: resolve case_id against the suite's known fixtures.
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
# S4 config inspection (secret-safe; offline).
# --------------------------------------------------------------------------


@eval_app.command("config")
def config_cmd(
    action: str = typer.Argument(..., help="Subcommand: show"),
) -> None:
    """Inspect resolved Opik/mirror config (secret-safe).

    Currently supports ``show`` only (E2 / §10.6 law 5). Never prints secret
    values — only masked ``•••[len=N]`` forms when a key is present in the
    ambient environment (never loaded into the config record itself).
    """
    if action != "show":
        typer.echo(f"config: unknown action {action!r} (supported: show)", err=True)
        raise typer.Exit(code=2)

    import json
    import os

    from git_cg.eval.mirror.config import (
        OpikConfigError,
        mask_secret,
        public_config_view,
        resolve_opik_config,
    )
    from git_cg.eval.mirror.health import ExportHealth
    from git_cg.eval.mirror.result import build_mirror_result

    try:
        config = resolve_opik_config()
    except OpikConfigError as exc:
        # Surface config_error via MirrorResult; still print diagnostics.
        result = build_mirror_result(
            mode="off",
            health=ExportHealth.CONFIG_ERROR,
            notes=(f"config_error: {exc}",),
        )
        typer.echo(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        typer.echo(f"config show: invalid (fail-closed): {exc}", err=True)
        raise typer.Exit(code=2) from None

    view = public_config_view(config)
    # Ambient secret presence only (never values from config — none stored).
    ambient_key = os.environ.get("OPIK_API_KEY") or os.environ.get("GIT_CG_OPIK_API_KEY")
    masked = {
        "api_key": mask_secret(ambient_key) if ambient_key else None,
        "api_key_present": bool(ambient_key),
    }
    payload = {
        "config": view,
        "secrets": masked,
        "health_hint": (
            ExportHealth.SKIPPED_OFF.value
            if view.get("mode") == "off"
            else (
                ExportHealth.CONFIG_ERROR.value
                if "mode_fallback" in (view.get("meta") or {})
                else ExportHealth.PENDING.value
            )
        ),
    }
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))
    raise typer.Exit(code=0)


# --------------------------------------------------------------------------
# S4 export commands (P1-4 nested surface + temporary dashed aliases).
# Canonical: git-cg eval export {status,retry,drain}
# Aliases:   git-cg eval export-status / export-retry / export-drain (R2)
# --------------------------------------------------------------------------


export_app = typer.Typer(
    add_completion=False,
    help="Layer-A export queue ops: status / retry / drain (F4 fail-open).",
    no_args_is_help=True,
)
eval_app.add_typer(export_app, name="export")


def _resolve_repo(root: Path | None) -> Path:
    from git_cg.eval.binding.paths import resolve_repo_root

    return root if root is not None else resolve_repo_root()


def _queue_status_counts(repo: Path) -> dict[str, int]:
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
    from git_cg.eval.mirror.queue import export_queue_dir

    qdir = export_queue_dir(repo)
    counts = _queue_status_counts(repo)
    typer.echo(f"queue_dir {qdir}")
    for status in ("pending", "sending", "sent", "failed", "dropped", "unreadable"):
        if status in counts:
            typer.echo(f"{status} {counts[status]}")
    if not counts:
        typer.echo("queue empty")


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
) -> None:
    """Show the Layer-A export queue status (read-only, offline)."""
    try:
        repo = _resolve_repo(root)
    except Exception as exc:
        typer.echo(f"export status: repo root unresolvable: {exc}", err=True)
        raise typer.Exit(code=1) from None
    _emit_status(repo)
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
) -> None:
    """Re-queue failed export rows for another drain attempt (P1-4 / P1-11).

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

    try:
        repo = _resolve_repo(root)
    except Exception as exc:
        typer.echo(f"export retry: repo root unresolvable: {exc}", err=True)
        # Fail-open for product/hooks.
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
) -> None:
    """Drain the export queue through the Opik transport (F4 fail-open).

    Always exits 0 unless the config is invalid (fail-closed). Transport and
    secret failures are classified and recorded on the queue rows; they never
    produce a non-zero exit that could block a hook.
    """
    from git_cg.eval.mirror.config import OpikConfigError, resolve_opik_config
    from git_cg.eval.mirror.exporter import drain_queue, list_pending_items
    from git_cg.eval.mirror.transport import OpikSdkTransport

    try:
        config = resolve_opik_config()
    except OpikConfigError as exc:
        typer.echo(f"export drain: config invalid (fail-closed): {exc}", err=True)
        raise typer.Exit(code=2) from None

    if config.get("mode", "off") == "off":
        typer.echo("export drain: mode=off; nothing to do")
        raise typer.Exit(code=0)

    try:
        repo = _resolve_repo(root)
    except Exception as exc:
        typer.echo(f"export drain: repo root unresolvable: {exc}", err=True)
        raise typer.Exit(code=0) from None  # fail-open

    if dry_run:
        pending = list_pending_items(repo_root=repo)
        typer.echo(f"mode {config.get('mode')}")
        projects = config.get("projects") or {}
        project = (projects.get("eval") if isinstance(projects, dict) else None) or config.get("project_name", "")
        typer.echo(f"project {project}")
        typer.echo(f"pending {len(pending)}")
        raise typer.Exit(code=0)

    import json

    from git_cg.eval.mirror.exporter import mirror_result_from_drain
    from git_cg.eval.mirror.result import evaluation_job_result, export_result

    summary = drain_queue(
        config,
        transport=OpikSdkTransport(),
        repo_root=repo,
        max_items=max_items,
    )
    result = mirror_result_from_drain(config, summary)
    # Human one-liner + machine-readable MirrorResult (P0-7).
    typer.echo(f"attempted {summary.attempted} exported {summary.exported} failed {summary.failed}")
    if summary.error_classes:
        typer.echo(f"error_classes {','.join(summary.error_classes)}")
    typer.echo(
        json.dumps(
            {
                "mirror_result": result.to_dict(),
                "export_result": export_result(result),
                "evaluation_job_result": evaluation_job_result(result),
            },
            indent=2,
            sort_keys=True,
        )
    )
    # Fail-open for product/hooks: export failures never produce a blocking
    # non-zero exit here. Eval wrappers may inspect evaluation_job_result.
    raise typer.Exit(code=0)


# Temporary dashed aliases (R2) — one minor cycle; nested form is canonical.
eval_app.command("export-status")(export_status_cmd)
eval_app.command("export-retry")(export_retry_cmd)
eval_app.command("export-drain")(export_drain_cmd)
