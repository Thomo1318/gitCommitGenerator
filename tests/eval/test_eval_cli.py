"""D11 thin ``git-cg eval`` CLI contract tests (Issue #231, B1-b / NTH-A7).

Locks the corpus-helper sub-app boundary:

* ``materialize-core-goldens`` and ``encode-fixture`` delegate to corpus helpers.
* The sub-app is **distinct** from the existing ``evals`` benchmark command.
* The CLI **never** imports the binder and **never** writes under
  ``.eval/bundles/acceptpath/**`` (materialize is a corpus write only).
* Exit codes: 0 on success, non-zero on unresolved ``--id`` / bad args.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from git_cg.main import app

runner = CliRunner()

FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "fixtures" / "eval"
VALID_CASE = FIXTURE_ROOT / "cases" / "valid" / "seed-v1-valid-fixture.json"
CORE_CASE_ID = "seed-v1-valid-fixture"


def test_eval_app_registered_and_distinct_from_evals() -> None:
    """The `eval` group exists and is not the `evals` benchmark command."""
    result = runner.invoke(app, ["eval", "--help"])
    assert result.exit_code == 0
    assert "materialize-core-goldens" in result.output
    assert "encode-fixture" in result.output
    # `evals` remains a separate top-level command.
    evals_result = runner.invoke(app, ["evals", "--help"])
    assert evals_result.exit_code == 0


def test_eval_cli_module_does_not_import_binder_or_opik() -> None:
    """The ``git_cg.eval.cli`` module itself must not pull in binder or Opik.

    Note: ``git_cg.main`` legitimately imports Opik for product telemetry, so
    the isolation contract is scoped to the CLI module's own import graph.
    """
    for mod in ("git_cg.eval.binding", "opik"):
        sys.modules.pop(mod, None)
    # Re-import the CLI module fresh and check its own import graph.
    sys.modules.pop("git_cg.eval.cli", None)
    import git_cg.eval.cli  # noqa: F401

    assert "git_cg.eval.binding" not in sys.modules
    assert "opik" not in sys.modules


def test_eval_cli_invocation_does_not_import_binder() -> None:
    """Invoking encode-fixture must not load the binder package."""
    sys.modules.pop("git_cg.eval.binding", None)
    result = runner.invoke(app, ["eval", "encode-fixture", "--path", str(VALID_CASE)])
    assert result.exit_code == 0, result.output
    assert "git_cg.eval.binding" not in sys.modules


def test_encode_fixture_path_prints_identity() -> None:
    result = runner.invoke(app, ["eval", "encode-fixture", "--path", str(VALID_CASE)])
    assert result.exit_code == 0, result.output
    assert "bundle_hash " in result.output
    assert "case_hash " in result.output
    assert "bundle_ref bundle:seed-v1-valid-fixture@" in result.output


def test_encode_fixture_id_resolves_core_case() -> None:
    result = runner.invoke(app, ["eval", "encode-fixture", "--id", CORE_CASE_ID])
    assert result.exit_code == 0, result.output
    assert "bundle_hash " in result.output
    assert f"bundle_ref bundle:{CORE_CASE_ID}@" in result.output


def test_encode_fixture_id_unresolved_fails_nonzero() -> None:
    result = runner.invoke(app, ["eval", "encode-fixture", "--id", "does-not-exist"])
    assert result.exit_code == 1
    assert "not found in suite" in result.output


def test_encode_fixture_requires_path_or_id() -> None:
    result = runner.invoke(app, ["eval", "encode-fixture"])
    assert result.exit_code == 2
    assert "requires --path" in result.output or "requires" in result.output


def test_encode_fixture_rejects_both_path_and_id() -> None:
    result = runner.invoke(
        app,
        ["eval", "encode-fixture", "--path", str(VALID_CASE), "--id", CORE_CASE_ID],
    )
    assert result.exit_code == 2
    assert "only one of" in result.output


def test_encode_fixture_missing_path_fails() -> None:
    result = runner.invoke(app, ["eval", "encode-fixture", "--path", "/nonexistent.json"])
    assert result.exit_code != 0


@pytest.mark.parametrize("extra", [[], ["--id", CORE_CASE_ID]])
def test_encode_fixture_never_writes_acceptpath(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    extra: list[str],
) -> None:
    """encode-fixture must not create .eval/bundles/acceptpath/** anywhere."""
    monkeypatch.chdir(tmp_path)
    args = (
        ["eval", "encode-fixture", "--path", str(VALID_CASE)]
        if not extra
        else [
            "eval",
            "encode-fixture",
            *extra,
        ]
    )
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    assert not (tmp_path / ".eval").exists()


def test_materialize_core_goldens_writes_corpus_not_acceptpath(tmp_path: Path) -> None:
    """materialize-core-goldens is a corpus write; no .eval/acceptpath tree."""
    root = tmp_path / "eval"
    shutil.copytree(FIXTURE_ROOT, root)
    result = runner.invoke(app, ["eval", "materialize-core-goldens", "--root", str(root)])
    assert result.exit_code == 0, result.output
    assert "core_snapshot" in result.output
    assert "core_bundles" in result.output
    # Corpus goldens materialized under the fixture root.
    assert (root / "bundles").is_dir()
    assert (root / "snapshots").is_dir()
    # No accept-path binder tree anywhere under the temp root.
    assert not (root / ".eval").exists()
    assert not list(root.rglob("acceptpath"))


def test_materialize_core_goldens_failure_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_a, **_k):
        raise ValueError("materialize exploded")

    monkeypatch.setattr("git_cg.eval.corpus.materialize.materialize_core_goldens", _boom)
    result = runner.invoke(app, ["eval", "materialize-core-goldens"])
    assert result.exit_code == 1
    assert "materialize-core-goldens failed" in result.output


def test_encode_fixture_path_load_error(tmp_path: Path) -> None:
    bad = tmp_path / "not-json.json"
    bad.write_text("{nope", encoding="utf-8")
    result = runner.invoke(app, ["eval", "encode-fixture", "--path", str(bad)])
    assert result.exit_code == 1
    assert "encode-fixture failed" in result.output


def test_encode_fixture_id_suite_load_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_a, **_k):
        raise RuntimeError("suite missing")

    monkeypatch.setattr("git_cg.eval.corpus.suites.load_suite", _boom)
    result = runner.invoke(app, ["eval", "encode-fixture", "--id", CORE_CASE_ID])
    assert result.exit_code == 1
    assert "failed to load suite" in result.output


def test_encode_fixture_encode_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_a, **_k):
        raise ValueError("encode exploded")

    monkeypatch.setattr("git_cg.eval.corpus.encoder.encode_fixture", _boom)
    result = runner.invoke(app, ["eval", "encode-fixture", "--path", str(VALID_CASE)])
    assert result.exit_code == 1
    assert "encode-fixture failed" in result.output


def test_materialize_prints_archive_snapshot_when_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover archive_snapshot truthy branch in materialize-core-goldens output."""

    def _fake(*_a, **_k):
        return {
            "core_snapshot": "core@abc",
            "archive_snapshot": "archive@def",
            "core_bundles": ["a", "b"],
            "archive_bundles": ["c"],
        }

    monkeypatch.setattr("git_cg.eval.corpus.materialize.materialize_core_goldens", _fake)
    result = runner.invoke(app, ["eval", "materialize-core-goldens"])
    assert result.exit_code == 0
    assert "core_snapshot core@abc" in result.output
    assert "archive_snapshot archive@def" in result.output
    assert "core_bundles 2" in result.output
    assert "archive_bundles 1" in result.output


def test_materialize_skips_archive_snapshot_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover archive_snapshot falsy branch (no archive line printed)."""

    def _fake(*_a, **_k):
        return {
            "core_snapshot": "core@abc",
            "archive_snapshot": None,
            "core_bundles": ["a"],
            "archive_bundles": [],
        }

    monkeypatch.setattr("git_cg.eval.corpus.materialize.materialize_core_goldens", _fake)
    result = runner.invoke(app, ["eval", "materialize-core-goldens"])
    assert result.exit_code == 0
    assert "core_snapshot core@abc" in result.output
    assert "archive_snapshot" not in result.output
    assert "core_bundles 1" in result.output
    assert "archive_bundles 0" in result.output
