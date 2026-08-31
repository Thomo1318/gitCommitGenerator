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


# S4 / P1-4 export CLI surface (nested + dashed aliases)


def test_export_nested_and_dashed_help_registered() -> None:
    result = runner.invoke(app, ["eval", "--help"])
    assert result.exit_code == 0
    assert "export" in result.output
    nested = runner.invoke(app, ["eval", "export", "--help"])
    assert nested.exit_code == 0
    assert "status" in nested.output
    assert "retry" in nested.output
    assert "drain" in nested.output


def test_export_status_empty_queue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    result = runner.invoke(app, ["eval", "export", "status", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "queue empty" in result.output or "queue_dir" in result.output


def test_export_status_dashed_alias(tmp_path: Path) -> None:
    result = runner.invoke(app, ["eval", "export-status", "--root", str(tmp_path)])
    # root may be unresolvable without .git — either empty/status or fail code 1
    assert result.exit_code in {0, 1}


def test_export_status_empty_queue_zeroed_counts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty/absent queue emits a stable zeroed counts object (JSON)."""
    import json

    monkeypatch.setenv("GIT_CG_OPIK_MODE", "off")
    _clear_project_envs(monkeypatch)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    result = runner.invoke(app, ["eval", "export", "status", "--root", str(tmp_path), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    counts = payload["data"]["counts"]
    assert counts == {
        "pending": 0,
        "sending": 0,
        "sent": 0,
        "failed": 0,
        "dropped": 0,
        "unreadable": 0,
    }
    # no queue dir invented by status
    assert not (tmp_path / ".eval" / "export_queue").exists()


def test_export_retry_missing_id_reports_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`export retry --id <missing>` prints a plain id-not-found line."""
    monkeypatch.setenv("GIT_CG_OPIK_MODE", "off")
    _clear_project_envs(monkeypatch)
    (tmp_path / ".git").mkdir()
    result = runner.invoke(app, ["eval", "export", "retry", "--root", str(tmp_path), "--id", "q_missing"])
    assert result.exit_code == 0, result.output
    assert "id not found: q_missing" in result.output
    assert "unreadable 0" in result.output


def test_export_retry_missing_id_json_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """JSON mode surfaces a not-found warning code + not_found list."""
    import json

    monkeypatch.setenv("GIT_CG_OPIK_MODE", "off")
    _clear_project_envs(monkeypatch)
    (tmp_path / ".git").mkdir()
    result = runner.invoke(app, ["eval", "export", "retry", "--root", str(tmp_path), "--id", "q_missing", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["data"]["not_found"] == ["q_missing"]
    assert payload["data"]["unreadable"] == 0
    codes = {w.get("code") for w in payload.get("warnings", [])}
    assert "EVAL_EXPORT_ID_NOT_FOUND" in codes


def test_export_retry_corrupt_id_is_unreadable_not_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Existing corrupt queue rows must not be reported as not_found."""
    import json

    from git_cg.eval.mirror.queue import export_queue_dir

    monkeypatch.setenv("GIT_CG_OPIK_MODE", "off")
    _clear_project_envs(monkeypatch)
    (tmp_path / ".git").mkdir()
    qdir = export_queue_dir(tmp_path)
    qdir.mkdir(parents=True, exist_ok=True)
    (qdir / "q_corrupt.json").write_text("{", encoding="utf-8")

    result = runner.invoke(
        app,
        ["eval", "export", "retry", "--root", str(tmp_path), "--id", "q_corrupt", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["data"].get("not_found") in (None, [])
    assert payload["data"]["unreadable"] == 1


def test_export_retry_failed_rows(tmp_path: Path) -> None:
    from git_cg.eval.mirror.batch import build_export_batches
    from git_cg.eval.mirror.queue import enqueue_export_batch, load_queue_item, mark_queue_item

    batches = build_export_batches(
        [("cli_retry_item", {"trace": {"ok": True}, "gate": {"deterministic_pass": True}})],
        "default_scrub",
        project="eval-project",
        experiment_id="exp_cli_retry",
    )
    path = enqueue_export_batch(batches[0], repo_root=tmp_path)
    qid = path.stem
    mark_queue_item(qid, "sending", repo_root=tmp_path, claimed_by="t")
    mark_queue_item(qid, "failed", repo_root=tmp_path, last_error_class="export_network", clear_lease=True)
    assert load_queue_item(qid, repo_root=tmp_path)["status"] == "failed"

    result = runner.invoke(app, ["eval", "export", "retry", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "retried 1" in result.output
    assert load_queue_item(qid, repo_root=tmp_path)["status"] == "pending"


def test_export_retry_skips_validation_without_force(tmp_path: Path) -> None:
    from git_cg.eval.mirror.batch import build_export_batches
    from git_cg.eval.mirror.queue import enqueue_export_batch, load_queue_item, mark_queue_item

    batches = build_export_batches(
        [("cli_retry_val", {"trace": {"ok": True}})],
        "default_scrub",
        project="eval-project",
        experiment_id="exp_cli_val",
    )
    path = enqueue_export_batch(batches[0], repo_root=tmp_path)
    qid = path.stem
    mark_queue_item(qid, "sending", repo_root=tmp_path, claimed_by="t")
    mark_queue_item(qid, "failed", repo_root=tmp_path, last_error_class="export_validation", clear_lease=True)

    result = runner.invoke(app, ["eval", "export", "retry", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "retried 0" in result.output
    assert load_queue_item(qid, repo_root=tmp_path)["status"] == "failed"

    forced = runner.invoke(app, ["eval", "export", "retry", "--root", str(tmp_path), "--force"])
    assert forced.exit_code == 0, forced.output
    assert "retried 1" in forced.output
    assert load_queue_item(qid, repo_root=tmp_path)["status"] == "pending"


def test_export_drain_mode_off(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GIT_CG_OPIK_MODE", "off")
    # Ensure no leftover project envs force config_error.
    for key in (
        "GIT_CG_OPIK_PROJECT_LIVE",
        "GIT_CG_OPIK_PROJECT_EVAL",
        "GIT_CG_OPIK_PROJECT_CI",
        "GIT_CG_OPIK_PROJECT_IMPORT",
        "OPIK_PROJECT_NAME",
    ):
        monkeypatch.delenv(key, raising=False)
    result = runner.invoke(app, ["eval", "export", "drain", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "mode=off" in result.output


def test_export_drain_dashed_alias_mode_off(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GIT_CG_OPIK_MODE", "off")
    for key in (
        "GIT_CG_OPIK_PROJECT_LIVE",
        "GIT_CG_OPIK_PROJECT_EVAL",
        "GIT_CG_OPIK_PROJECT_CI",
        "GIT_CG_OPIK_PROJECT_IMPORT",
        "OPIK_PROJECT_NAME",
    ):
        monkeypatch.delenv(key, raising=False)
    result = runner.invoke(app, ["eval", "export-drain", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "mode=off" in result.output


def _clear_project_envs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear project-related env vars for CLI isolation."""
    for key in (
        "GIT_CG_OPIK_PROJECT_LIVE",
        "GIT_CG_OPIK_PROJECT_EVAL",
        "GIT_CG_OPIK_PROJECT_CI",
        "GIT_CG_OPIK_PROJECT_IMPORT",
        "OPIK_PROJECT_NAME",
    ):
        monkeypatch.delenv(key, raising=False)


def test_export_drain_invalid_mode_is_config_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """E12: bogus mode on drain surfaces config_error (not silent mode=off)."""
    monkeypatch.setenv("GIT_CG_OPIK_MODE", "bogus")
    _clear_project_envs(monkeypatch)
    result = runner.invoke(app, ["eval", "export", "drain", "--root", str(tmp_path)])
    assert result.exit_code == 2, result.output
    assert "config_error" in result.output
    assert "bogus" not in result.output
    assert "<redacted-mode-token>" in result.output
    assert '"health": "config_error"' in result.output or '"health":"config_error"' in result.output.replace(" ", "")


def test_export_status_invalid_mode_is_config_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GIT_CG_OPIK_MODE", "bogus")
    _clear_project_envs(monkeypatch)
    result = runner.invoke(app, ["eval", "export", "status", "--root", str(tmp_path)])
    assert result.exit_code == 2, result.output
    assert "health config_error" in result.output
    assert "bogus" not in result.output
    assert "<redacted-mode-token>" in result.output


def test_config_show_invalid_mode_is_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CG_OPIK_MODE", "bogus")
    _clear_project_envs(monkeypatch)
    # Support both naming variants if present.
    result = runner.invoke(app, ["eval", "config", "show"])
    if result.exit_code == 2 and "unknown" in (result.output or "").lower() and "config_error" not in result.output:
        result = runner.invoke(app, ["eval", "opik-config-show"])
    assert result.exit_code == 2, result.output
    assert "config_error" in result.output
    assert "bogus" not in result.output
    assert "<redacted-mode-token>" in result.output


def test_config_unknown_action_exits_2() -> None:
    result = runner.invoke(app, ["eval", "config", "wat"])
    assert result.exit_code == 2
    assert "unknown action" in result.output


def test_config_show_ok_exit_0(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CG_OPIK_MODE", "off")
    _clear_project_envs(monkeypatch)
    for key in ("OPIK_API_KEY", "GIT_CG_OPIK_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    result = runner.invoke(app, ["eval", "config", "show"])
    assert result.exit_code == 0, result.output
    out = result.output
    assert "mode=off" in out
    assert "health=" in out
    assert "api_key_present=false" in out
    assert "product_accept_blocked=false" in out


def test_config_show_opik_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    # Real fail-closed path: active mode without pinned projects raises OpikConfigError.
    monkeypatch.setenv("GIT_CG_OPIK_MODE", "mirror")
    for key in (
        "GIT_CG_OPIK_PROJECT_EVAL",
        "GIT_CG_OPIK_PROJECT_LIVE",
        "GIT_CG_OPIK_PROJECT_CI",
        "GIT_CG_OPIK_PROJECT_IMPORT",
        "OPIK_PROJECT_NAME",
    ):
        monkeypatch.delenv(key, raising=False)
    result = runner.invoke(app, ["eval", "config", "show"])
    assert result.exit_code == 2, result.output
    assert "config_error" in result.output or "invalid" in result.output or "pinned projects" in result.output


def test_export_status_counts_unreadable_and_statuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from git_cg.eval.mirror.batch import build_export_batches
    from git_cg.eval.mirror.queue import enqueue_export_batch, export_queue_dir, mark_queue_item

    monkeypatch.setenv("GIT_CG_OPIK_MODE", "off")
    _clear_project_envs(monkeypatch)
    (tmp_path / ".git").mkdir()
    batches = build_export_batches(
        [("status_item", {"trace": {"ok": True}})],
        "default_scrub",
        project="eval-project",
        experiment_id="exp_status",
    )
    path = enqueue_export_batch(batches[0], repo_root=tmp_path)
    qid = path.stem
    mark_queue_item(qid, "sending", repo_root=tmp_path, claimed_by="t")
    mark_queue_item(qid, "failed", repo_root=tmp_path, last_error_class="export_network", clear_lease=True)

    # unreadable row
    bad = export_queue_dir(tmp_path) / "broken.json"
    bad.write_text("{", encoding="utf-8")

    result = runner.invoke(app, ["eval", "export", "status", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "failed" in result.output
    assert "unreadable" in result.output


def test_export_status_repo_unresolvable(monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.eval.cli as cli_mod

    def boom(_root=None):
        raise RuntimeError("no repo")

    monkeypatch.setattr(cli_mod, "_resolve_repo", boom)
    monkeypatch.setenv("GIT_CG_OPIK_MODE", "off")
    _clear_project_envs(monkeypatch)
    result = runner.invoke(cli_mod.eval_app, ["export", "status"])
    assert result.exit_code == 1, result.output
    assert "unresolvable" in result.output


def test_export_retry_repo_unresolvable_fail_open(monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.eval.cli as cli_mod

    def boom(_root=None):
        raise RuntimeError("no repo")

    monkeypatch.setattr(cli_mod, "_resolve_repo", boom)
    result = runner.invoke(cli_mod.eval_app, ["export", "retry"])
    assert result.exit_code == 0, result.output
    assert "unresolvable" in result.output


def test_export_retry_by_id_max_items_and_unreadable(tmp_path: Path) -> None:
    from git_cg.eval.mirror.batch import build_export_batches
    from git_cg.eval.mirror.queue import enqueue_export_batch, export_queue_dir, load_queue_item, mark_queue_item

    batches = build_export_batches(
        [("retry_id", {"trace": {"ok": True}})],
        "default_scrub",
        project="eval-project",
        experiment_id="exp_retry_id",
    )
    path = enqueue_export_batch(batches[0], repo_root=tmp_path)
    qid = path.stem
    mark_queue_item(qid, "sending", repo_root=tmp_path, claimed_by="t")
    mark_queue_item(qid, "failed", repo_root=tmp_path, last_error_class="export_network", clear_lease=True)

    # unreadable + pending (skipped)
    (export_queue_dir(tmp_path) / "junk.json").write_text("{", encoding="utf-8")
    batches2 = build_export_batches(
        [("pending_skip", {"trace": {"ok": True}})],
        "default_scrub",
        project="eval-project",
        experiment_id="exp_pending",
    )
    enqueue_export_batch(batches2[0], repo_root=tmp_path)

    result = runner.invoke(
        app,
        ["eval", "export", "retry", "--root", str(tmp_path), "--id", qid, "--max-items", "1"],
    )
    assert result.exit_code == 0, result.output
    assert "retried 1" in result.output
    assert load_queue_item(qid, repo_root=tmp_path)["status"] == "pending"


def test_export_retry_mark_failure_is_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from git_cg.eval.mirror.batch import build_export_batches
    from git_cg.eval.mirror.queue import ExportQueueError, enqueue_export_batch, mark_queue_item

    batches = build_export_batches(
        [("retry_mark_fail", {"trace": {"ok": True}})],
        "default_scrub",
        project="eval-project",
        experiment_id="exp_retry_mark",
    )
    path = enqueue_export_batch(batches[0], repo_root=tmp_path)
    qid = path.stem
    mark_queue_item(qid, "sending", repo_root=tmp_path, claimed_by="t")
    mark_queue_item(qid, "failed", repo_root=tmp_path, last_error_class="export_network", clear_lease=True)

    def boom(*_a, **_k):
        raise ExportQueueError("cannot mark")

    monkeypatch.setattr("git_cg.eval.mirror.queue.mark_queue_item", boom)
    result = runner.invoke(app, ["eval", "export", "retry", "--root", str(tmp_path), "--id", qid])
    assert result.exit_code == 0
    assert "skipped" in result.output


def test_export_drain_config_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Real fail-closed path: active mode without pinned projects.
    monkeypatch.setenv("GIT_CG_OPIK_MODE", "mirror")
    for key in (
        "GIT_CG_OPIK_PROJECT_EVAL",
        "GIT_CG_OPIK_PROJECT_LIVE",
        "GIT_CG_OPIK_PROJECT_CI",
        "GIT_CG_OPIK_PROJECT_IMPORT",
        "OPIK_PROJECT_NAME",
    ):
        monkeypatch.delenv(key, raising=False)
    result = runner.invoke(app, ["eval", "export", "drain", "--root", str(tmp_path)])
    assert result.exit_code == 2, result.output
    assert "config invalid" in result.output or "invalid" in result.output or "pinned projects" in result.output


def test_export_drain_dry_run_and_full_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from git_cg.eval.mirror.batch import build_export_batches
    from git_cg.eval.mirror.queue import enqueue_export_batch
    from git_cg.eval.mirror.transport import MockTransport

    monkeypatch.setenv("GIT_CG_OPIK_MODE", "mirror")
    monkeypatch.setenv("GIT_CG_OPIK_PROJECT_EVAL", "eval-project")
    monkeypatch.setenv("GIT_CG_OPIK_PROJECT_LIVE", "eval-project")
    monkeypatch.setenv("GIT_CG_OPIK_PROJECT_CI", "eval-project")
    monkeypatch.setenv("GIT_CG_OPIK_PROJECT_IMPORT", "eval-project")
    monkeypatch.setenv("GIT_CG_OPIK_API_KEY", "test-key")

    batches = build_export_batches(
        [("drain_item", {"trace": {"ok": True}})],
        "default_scrub",
        project="eval-project",
        experiment_id="exp_drain",
    )
    enqueue_export_batch(batches[0], repo_root=tmp_path)

    dry = runner.invoke(app, ["eval", "export", "drain", "--root", str(tmp_path), "--dry-run"])
    assert dry.exit_code == 0, dry.output
    assert "pending" in dry.output
    assert "mode" in dry.output

    # Patch real transport to mock so drain path executes without Opik.
    monkeypatch.setattr("git_cg.eval.mirror.transport.OpikSdkTransport", MockTransport)

    monkeypatch.setattr(
        "git_cg.eval.mirror.exporter.drain_queue",
        lambda *a, **k: __import__("git_cg.eval.mirror.exporter", fromlist=["DrainSummary"]).DrainSummary(
            attempted=1, exported=1
        ),
    )
    full = runner.invoke(app, ["eval", "export", "drain", "--root", str(tmp_path)])
    assert full.exit_code == 0, full.output
    assert "attempted" in full.output
    assert "mirror_result" in full.output


def test_export_drain_repo_unresolvable_fail_open(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import git_cg.eval.cli as cli_mod

    monkeypatch.setenv("GIT_CG_OPIK_MODE", "mirror")
    monkeypatch.setenv("GIT_CG_OPIK_PROJECT_EVAL", "eval-project")
    monkeypatch.setenv("GIT_CG_OPIK_PROJECT_LIVE", "eval-project")
    monkeypatch.setenv("GIT_CG_OPIK_PROJECT_CI", "eval-project")
    monkeypatch.setenv("GIT_CG_OPIK_PROJECT_IMPORT", "eval-project")

    def boom(_root=None):
        raise RuntimeError("no repo")

    monkeypatch.setattr(cli_mod, "_resolve_repo", boom)
    # Pass --root so config path succeeds; boom still intercepts _resolve_repo.
    result = runner.invoke(cli_mod.eval_app, ["export", "drain", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "unresolvable" in result.output
