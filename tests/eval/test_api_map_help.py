"""S6 Slice 2 — operator API map + help alignment (Issue #246 / S6-A).

Locks:
* Live Typer tree matches generated ``docs/eval/operator_api_map.md``.
* ``git-cg eval --help`` exposes the supported S6 command surface.
* Nested group help lists canonical children.
* Basic ``git-cg --help`` does not require Opik / dump eval-only noise.
* ``git_cg.eval.cli`` import stays binder/Opik free.
* Deprecated aliases emit stderr warnings (human) / envelope warnings (JSON).
* JSON stubs emit exactly one ``cli_output_envelope_v1`` document.
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import sys
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from git_cg.eval.api_map import (
    CANONICAL_COMMANDS,
    DEFAULT_MAP_PATH,
    check_map,
    render_operator_api_map,
    walk_eval_tree,
)
from git_cg.eval.cli_output import (
    DEFAULT_KEEP_LAST,
    REMOVAL_TARGET,
    SCHEMA_VERSION,
)
from git_cg.main import app

runner = CliRunner()
REPO_ROOT = Path(__file__).resolve().parents[2]


CANONICAL_HELP_NAMES = sorted(
    {
        # top-level leaves (help text on eval --help)
        "run",
        "resume",
        "recompute-scores",
        "doctor",
        "amend-brief",
        "dogfood",
        "train-export",
        "failures",
        "explain",
        "compare",
        "replay",
        "promote",
        "diagnose",
        # groups
        "session",
        "thread",
        "issue",
        "opik",
        "export",
        # corpus
        "materialize-core-goldens",
        "encode-fixture",
        # temporary aliases still registered
        "config",
        "export-status",
        "export-retry",
        "export-drain",
    }
)


def test_operator_api_map_matches_live_tree() -> None:
    ok, msg = check_map(REPO_ROOT / DEFAULT_MAP_PATH)
    assert ok, msg


def test_render_is_deterministic() -> None:
    a = render_operator_api_map()
    b = render_operator_api_map()
    assert a == b
    assert "Stability tiers" in a
    assert "Supported Python entrypoints" in a
    assert str(DEFAULT_KEEP_LAST) in a
    assert REMOVAL_TARGET in a


def test_walk_eval_tree_includes_canonical_commands() -> None:
    paths = {n.path for n in walk_eval_tree()}
    missing = sorted(cmd for cmd in CANONICAL_COMMANDS if cmd not in paths)
    assert not missing, f"canonical commands missing from Typer tree: {missing}"


def test_eval_help_lists_supported_surface() -> None:
    result = runner.invoke(app, ["eval", "--help"])
    assert result.exit_code == 0, result.output
    for name in CANONICAL_HELP_NAMES:
        assert name in result.output, f"missing from eval --help: {name}"


@pytest.mark.parametrize(
    ("args", "needles"),
    [
        (["eval", "export", "--help"], ["status", "retry", "drain"]),
        (["eval", "issue", "--help"], ["list", "show", "resolve", "reopen", "suppress"]),
        (["eval", "opik", "--help"], ["doctor", "config"]),
        (["eval", "opik", "config", "--help"], ["show"]),
        (["eval", "session", "--help"], ["show"]),
        (["eval", "thread", "--help"], ["show"]),
    ],
)
def test_nested_group_help(args: list[str], needles: list[str]) -> None:
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    for needle in needles:
        assert needle in result.output, f"{args}: missing {needle}"


def test_basic_git_cg_help_no_opik_requirement_or_eval_noise() -> None:
    """S6-A02: basic help must not require Opik or dump eval-only internals."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    # eval group is registered (name only) — fine
    assert "eval" in result.output
    # Must not require Opik setup to render help
    assert "OPIK_API_KEY" not in result.output
    assert "opik.com" not in result.output.lower()
    # Must not dump eval-only internal module paths / schema pack noise
    assert "git_cg.eval.binding" not in result.output
    assert "schema_pack_v0@" not in result.output
    assert "cli_output_envelope_v1" not in result.output


def test_eval_cli_module_import_stays_light() -> None:
    for mod in ("git_cg.eval.binding", "opik", "git_cg.eval.cli"):
        sys.modules.pop(mod, None)
    import git_cg.eval.cli  # noqa: F401

    assert "git_cg.eval.binding" not in sys.modules
    assert "opik" not in sys.modules


def test_stub_json_emits_envelope() -> None:
    # All S6 commands are landed as of Slice 7; the not-implemented JSON
    # contract is exercised directly against the emitter instead of a live stub.
    from git_cg.eval.cli_output import emit_not_implemented

    buf = io.StringIO()
    with pytest.raises(typer.Exit) as ei, contextlib.redirect_stdout(buf):
        emit_not_implemented("eval hypothetical", slice_hint="Slice 9", as_json=True)
    assert ei.value.exit_code == 2
    payload = json.loads(buf.getvalue())
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["command"] == "eval hypothetical"
    assert payload["ok"] is False
    assert payload["errors"]
    assert payload["errors"][0]["code"] == "EVAL_CLI_NOT_IMPLEMENTED"


def test_config_show_deprecation_human(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CG_OPIK_MODE", "off")
    for key in (
        "GIT_CG_OPIK_PROJECT_LIVE",
        "GIT_CG_OPIK_PROJECT_EVAL",
        "GIT_CG_OPIK_PROJECT_CI",
        "GIT_CG_OPIK_PROJECT_IMPORT",
        "OPIK_PROJECT_NAME",
        "OPIK_API_KEY",
        "GIT_CG_OPIK_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    result = runner.invoke(app, ["eval", "config", "show"])
    assert result.exit_code == 0, result.output
    combined = (result.stdout or "") + (result.stderr or "")
    assert "temporary compatibility alias" in combined or "deprecated" in combined.lower()
    assert "opik config show" in combined


def test_config_show_deprecation_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CG_OPIK_MODE", "off")
    for key in (
        "GIT_CG_OPIK_PROJECT_LIVE",
        "GIT_CG_OPIK_PROJECT_EVAL",
        "GIT_CG_OPIK_PROJECT_CI",
        "GIT_CG_OPIK_PROJECT_IMPORT",
        "OPIK_PROJECT_NAME",
        "OPIK_API_KEY",
        "GIT_CG_OPIK_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    result = runner.invoke(app, ["eval", "config", "show", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["ok"] is True
    assert payload["warnings"]
    assert any(w.get("code") == "EVAL_CLI_DEPRECATED" for w in payload["warnings"])


def test_opik_config_show_canonical_no_deprecation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CG_OPIK_MODE", "off")
    for key in (
        "GIT_CG_OPIK_PROJECT_LIVE",
        "GIT_CG_OPIK_PROJECT_EVAL",
        "GIT_CG_OPIK_PROJECT_CI",
        "GIT_CG_OPIK_PROJECT_IMPORT",
        "OPIK_PROJECT_NAME",
        "OPIK_API_KEY",
        "GIT_CG_OPIK_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    result = runner.invoke(app, ["eval", "opik", "config", "show"])
    assert result.exit_code == 0, result.output
    combined = (result.stdout or "") + (result.stderr or "")
    assert "EVAL_CLI_DEPRECATED" not in combined
    assert "temporary compatibility alias" not in combined


def test_export_status_dashed_alias_deprecation(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    result = runner.invoke(app, ["eval", "export-status", "--root", str(tmp_path)])
    assert result.exit_code in {0, 1, 2}
    combined = (result.stdout or "") + (result.stderr or "")
    assert "export status" in combined or "temporary compatibility alias" in combined


def test_api_map_check_cli_ok() -> None:
    from git_cg.eval.api_map import main

    assert main(["--check", "--path", str(REPO_ROOT / DEFAULT_MAP_PATH)]) == 0


def test_api_map_check_detects_drift(tmp_path: Path) -> None:
    from git_cg.eval.api_map import main

    bogus = tmp_path / "operator_api_map.md"
    bogus.write_text("# drift\n", encoding="utf-8")
    assert main(["--check", "--path", str(bogus)]) == 1


def test_keep_last_default_on_run_help() -> None:
    result = runner.invoke(app, ["eval", "run", "--help"])
    assert result.exit_code == 0, result.output
    assert re.search(r"keep-last", result.output)
    assert str(DEFAULT_KEEP_LAST) in result.output
