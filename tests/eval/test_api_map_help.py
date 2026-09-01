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

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    """Strip ANSI SGR codes so help assertions survive FORCE_COLOR/CI."""
    return _ANSI_ESCAPE_RE.sub("", text)


REPO_ROOT = Path(__file__).resolve().parents[2]


# Visible in regular `git-cg eval --help` (excludes dark-launched hidden commands).
CANONICAL_HELP_NAMES = sorted(
    {
        # top-level leaves (help text on eval --help)
        "run",
        "resume",
        "recompute-scores",
        "doctor",
        "triage",
        "amend-brief",
        # "dogfood" is dark-launched (hidden=True) — still canonical/callable
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
        "checkpoint",
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
    # Dark-launched maintainer surface: callable, but omitted from regular help.
    assert "dogfood" not in result.output


def test_eval_dogfood_dark_launched_hidden_but_callable() -> None:
    """``eval dogfood`` stays registered for maintainers while hidden from help."""
    help_result = runner.invoke(app, ["eval", "--help"])
    assert help_result.exit_code == 0, help_result.output
    assert "dogfood" not in help_result.output

    # Still registered: ``eval dogfood --help`` works (direct invocation path).
    cmd_help = runner.invoke(app, ["eval", "dogfood", "--help"], terminal_width=120)
    assert cmd_help.exit_code == 0, cmd_help.output
    help_text = _strip_ansi(cmd_help.output)
    assert "--commit-message" in help_text
    assert "dark" in help_text.lower() or "Lane C" in help_text

    rendered = render_operator_api_map()
    assert "eval dogfood" in rendered
    assert "dark-launch" in rendered.lower()


@pytest.mark.parametrize(
    ("args", "needles"),
    [
        (["eval", "export", "--help"], ["status", "retry", "drain"]),
        (["eval", "issue", "--help"], ["list", "show", "resolve", "reopen", "suppress"]),
        (["eval", "checkpoint", "--help"], ["list"]),
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


def test_api_map_documents_single_writer_law() -> None:
    """Operator API map must state single-writer ownership (doc law only)."""
    rendered = render_operator_api_map()
    assert "## Single-writer / operator-writer law" in rendered
    # Ownership boundary + non-implementation posture.
    assert "single-operator-writer" in rendered
    assert "must not concurrently mutate" in rendered
    assert "atomic-write" in rendered or "atomic write" in rendered.lower()
    # Point at export-queue-grade coordination as the multi-writer gate.
    assert "export-queue-grade" in rendered or "claim/lease" in rendered
    assert "does **not** introduce locking" in rendered or "does not introduce locking" in rendered.lower()
    # Key store paths remain named so operators know the boundary.
    for needle in (".eval/issues/", ".eval/review_queue/", ".eval/index/promotions/", ".eval/export_queue/"):
        assert needle in rendered


# ---------------------------------------------------------------------------
# S6-A08 — per-command envelope data sketches + fail-closed --check gate
# ---------------------------------------------------------------------------


def test_minimum_envelope_sketches_registered() -> None:
    """Every Issue #246 minimum JSON command must have a closed data sketch."""
    from git_cg.eval.envelope_sketches import (
        ENVELOPE_DATA_SKETCHES,
        MINIMUM_SKETCH_COMMANDS,
        validate_sketch_registry,
    )

    ok, msg = validate_sketch_registry()
    assert ok, msg
    missing = sorted(cmd for cmd in MINIMUM_SKETCH_COMMANDS if cmd not in ENVELOPE_DATA_SKETCHES)
    assert not missing, f"minimum commands lacking sketches: {missing}"
    # Hygiene: sketch.command must equal registry key; required keys closed set.
    for cmd, sketch in ENVELOPE_DATA_SKETCHES.items():
        assert sketch.command == cmd
        assert sketch.required_keys == tuple(sorted(sketch.required_keys))
        assert sketch.optional_keys == tuple(sorted(sketch.optional_keys))
        # Closed top-level universe is non-overlapping.
        assert not (set(sketch.required_keys) & set(sketch.optional_keys))


def test_rendered_api_map_contains_all_envelope_sketches() -> None:
    """Generated operator API map must document every registered sketch."""
    from git_cg.eval.envelope_sketches import ENVELOPE_DATA_SKETCHES, MINIMUM_SKETCH_COMMANDS

    rendered = render_operator_api_map()
    assert "## Per-command envelope `data` sketches (S6-A08)" in rendered
    for cmd in sorted(MINIMUM_SKETCH_COMMANDS):
        assert f"`{cmd}`" in rendered, f"minimum command missing from map: {cmd}"
        assert f"#### `{cmd}`" in rendered, f"sketch heading missing: {cmd}"
    for _cmd, sketch in ENVELOPE_DATA_SKETCHES.items():
        for key in sketch.required_keys:
            # Required keys appear in the command's sketch block.
            assert f"`{key}`" in rendered
        for field, values in sketch.enums.items():
            assert f"`{field}`" in rendered
            for value in values:
                assert f"`{value}`" in rendered


def test_missing_envelope_sketch_fails_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """validate_sketch_registry / check_map fail closed when a minimum sketch is absent."""
    from git_cg.eval import api_map as api_map_mod, envelope_sketches as sketches_mod
    from git_cg.eval.envelope_sketches import (
        ENVELOPE_DATA_SKETCHES,
        MINIMUM_SKETCH_COMMANDS,
        missing_minimum_sketches,
        validate_sketch_registry,
    )

    # Synthetic incomplete registry: drop one minimum command.
    victim = sorted(MINIMUM_SKETCH_COMMANDS)[0]
    incomplete = {k: v for k, v in ENVELOPE_DATA_SKETCHES.items() if k != victim}
    assert victim not in incomplete
    assert victim in missing_minimum_sketches(incomplete)

    ok, msg = validate_sketch_registry(incomplete)
    assert ok is False
    assert victim in msg

    # check_map must fail even when on-disk map content would otherwise match
    # because the sketch registry is incomplete (monkeypatched live registry).
    monkeypatch.setattr(sketches_mod, "ENVELOPE_DATA_SKETCHES", incomplete)
    monkeypatch.setattr(api_map_mod, "validate_sketch_registry", lambda: validate_sketch_registry(incomplete))

    # Write a fresh map under the incomplete registry so drift is not the signal.
    map_path = tmp_path / "operator_api_map.md"
    # Force render under incomplete sketches via monkeypatched render helper.
    from git_cg.eval.envelope_sketches import render_sketches_markdown

    monkeypatch.setattr(
        api_map_mod,
        "render_sketches_markdown",
        lambda: render_sketches_markdown(incomplete),
    )
    map_path.write_text(api_map_mod.render_operator_api_map(), encoding="utf-8")

    ok2, msg2 = api_map_mod.check_map(map_path)
    assert ok2 is False, "check_map must fail when a minimum sketch is missing"
    assert "sketch" in msg2.lower() or victim in msg2


def test_api_map_check_still_detects_doc_drift(tmp_path: Path) -> None:
    """Doc drift detection remains intact after A08 sketch gate."""
    from git_cg.eval.api_map import main

    bogus = tmp_path / "operator_api_map.md"
    bogus.write_text("# drift\n", encoding="utf-8")
    assert main(["--check", "--path", str(bogus)]) == 1


def test_keep_last_default_on_run_help() -> None:
    result = runner.invoke(app, ["eval", "run", "--help"], terminal_width=120)
    assert result.exit_code == 0, result.output
    help_text = _strip_ansi(result.output)
    assert re.search(r"keep-last", help_text)
    assert str(DEFAULT_KEEP_LAST) in help_text


def test_eval_help_workflow_panels_and_plain_language() -> None:
    """Top-level eval help is workflow-grouped and free of internal jargon."""
    runner = CliRunner()
    result = runner.invoke(app, ["eval", "--help"])
    assert result.exit_code == 0
    out = _strip_ansi(result.output)

    # Workflow panel order (Rich titles). Match panel headers, not prose.
    panels = [
        "Corpus",
        "Run",
        "Inspect",
        "Review & sessions",
        "Export & train",
        "Advanced",
        "Deprecated",
    ]
    positions = []
    for name in panels:
        # Rich renders "╭─ <title> ─..."; fall back to plain title if box-drawing is stripped.
        header = f"─ {name} "
        if header in out:
            positions.append(out.index(header))
        else:
            positions.append(out.index(name))
    assert positions == sorted(positions), positions

    # Dark-launch stays hidden.
    assert "dogfood" not in out

    # No leaked ReST/backtick markup or internal-spec breadcrumbs in top help.
    banned = [
        "``",
        "ape_bundle_v1",
        "diag_issue_v1",
        "replay_compare_v1",
        "operator surface",
        "no product ranking",
        "§",
        "R11",
        "R14",
        "Slice 8",
        "D27",
        "F4",
        "Layer-A",
        "fingerprint law",
        "split_group_id",
    ]
    for token in banned:
        assert token not in out, token

    # Plain-language top description remains user-facing.
    # Rich may wrap the sentence across terminal columns.
    collapsed = re.sub(r"\s+", " ", out)
    assert "Does not change product commit ranking." in collapsed
