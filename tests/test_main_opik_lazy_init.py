"""Product-path Opik stays lazy under GIT_CG_OPIK_MODE=off (FIND-068)."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN_PATH = REPO_ROOT / "src" / "git_cg" / "main.py"


def test_main_has_no_module_level_opik_import() -> None:
    tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"), filename=str(MAIN_PATH))
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "opik" or alias.name.startswith("opik."):
                    pytest.fail(f"module-level import opik at main.py:{node.lineno}")
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "opik" or mod.startswith("opik."):
                pytest.fail(f"module-level from opik import at main.py:{node.lineno}")


def _scrub_opik_env(env: dict[str, str]) -> dict[str, str]:
    cleaned = {
        key: value for key, value in env.items() if not key.startswith("OPIK") and not key.startswith("GIT_CG_OPIK")
    }
    cleaned["GIT_CG_OPIK_MODE"] = "off"
    cleaned["GIT_CG_DISABLE_SENTRY"] = "1"
    cleaned["PYTHONPATH"] = str(REPO_ROOT / "src")
    cleaned.setdefault("PATH", os.environ.get("PATH", ""))
    return cleaned


def test_mode_off_import_does_not_load_opik_or_emit_startup_stderr() -> None:
    """Fresh process: mode=off must not import Opik or print OPIK startup lines."""
    probe = textwrap.dedent(
        """
        import sys
        import git_cg.main as main

        opik_mods = sorted(
            name for name in sys.modules if name == "opik" or name.startswith("opik.")
        )
        print("OPIK_MODS=" + ",".join(opik_mods))

        @main.opik.track(project_name="should-not-init")
        def _sample():
            return 7

        assert _sample() == 7
        main.opik_context.update_current_trace(metadata={"x": 1})
        main.opik.flush_tracker()
        bare = object()
        assert main.track_openai(bare) is bare
        """
    )
    env = _scrub_opik_env(dict(os.environ))
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, (
        f"probe failed rc={completed.returncode}\nstdout={completed.stdout}\nstderr={completed.stderr}"
    )
    opik_mods_line = next(line for line in completed.stdout.splitlines() if line.startswith("OPIK_MODS="))
    assert opik_mods_line == "OPIK_MODS=", f"Opik modules leaked: {opik_mods_line}"
    assert "Started logging traces" not in completed.stderr
    assert "OPIK:" not in completed.stderr


def test_mode_off_cli_help_has_clean_stderr() -> None:
    """CLI smoke: git-cg --help under mode=off must not emit Opik startup noise."""
    env = _scrub_opik_env(dict(os.environ))
    completed = subprocess.run(
        [sys.executable, "-m", "git_cg.main", "--help"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Started logging traces" not in completed.stderr
    assert "OPIK:" not in completed.stderr


def test_track_openai_returns_bare_client_when_mode_off(monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.main as main

    monkeypatch.setenv("GIT_CG_OPIK_MODE", "off")
    monkeypatch.setattr(main, "_opik_module", None)
    monkeypatch.setattr(main, "_opik_context_module", None)
    monkeypatch.setattr(main, "_track_openai_function", None)
    monkeypatch.setattr(main, "_opik_init_attempted", False)

    sentinel = object()
    assert main.track_openai(sentinel) is sentinel
    assert main._ensure_opik() is False
