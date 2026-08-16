"""Thin ``git-cg eval`` corpus-helper CLI (Issue #231, D11 / B1-b).

This is a **delegation-only** Typer sub-app. It exposes corpus helpers
(``materialize-core-goldens`` and ``encode-fixture``) and nothing else:

* No binder invocation (``git_cg.eval.binding`` is never imported here).
* No accept-path writes under ``.eval/bundles/acceptpath/**``.
* No network, no capture enablement side effects, no Opik.
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
