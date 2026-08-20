"""Freeze contract for scripts/eval_commit_message.py (S5 D24 / #233).

The live Opik evaluate harness is retired. This module must fail closed and
point at canonical offline scoring / Lane C surfaces. Live generation,
caching, and tier-gating behaviour are intentionally gone.
"""

from __future__ import annotations

import ast
import io
import os
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, os.fspath(SCRIPTS))

import eval_commit_message as ecm  # noqa: E402


def test_module_exports_freeze_surface() -> None:
    assert ecm.LEGACY_EVAL_COMMIT_MESSAGE_RETIRED is True
    assert "src/git_cg/eval/scoring/" in ecm.CANONICAL_EVAL_HOMES
    assert "src/git_cg/eval/lane_c/" in ecm.CANONICAL_EVAL_HOMES
    assert "tests/eval/" in ecm.CANONICAL_EVAL_HOMES
    assert "refuse_legacy_eval_commit_message" in ecm.__all__
    assert "evaluation_task" in ecm.__all__
    assert "main" in ecm.__all__


def test_no_live_generation_cache_surface() -> None:
    assert not hasattr(ecm, "_generation_cache")
    assert not hasattr(ecm, "generate_commit_message")
    assert not hasattr(ecm, "get_ai_client")


def test_source_has_no_hard_sdk_imports() -> None:
    path = SCRIPTS / "eval_commit_message.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    banned = {"opik", "requests", "httpx", "openai", "anthropic"}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".", 1)[0] not in banned
        if isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            assert root not in banned


def test_refuse_prints_pointer_and_returns_2() -> None:
    buf = io.StringIO()
    code = ecm.refuse_legacy_eval_commit_message(stream=buf)
    assert code == 2
    msg = buf.getvalue().lower()
    assert "frozen" in msg or "retired" in msg or "demotion" in msg
    assert "scoring" in msg
    assert "lane_c" in msg or "lane c" in msg


def test_main_refuses() -> None:
    assert ecm.main([]) == 2


def test_evaluation_task_refuses_dict_item() -> None:
    with pytest.raises(SystemExit) as ei:
        ecm.evaluation_task({"diff_output": "x", "expected_output": "y"})
    assert ei.value.code == 2


def test_evaluation_task_refuses_object_item() -> None:
    class _Item:
        diff_output = "x"
        expected_output = "y"

    with pytest.raises(SystemExit) as ei:
        ecm.evaluation_task(_Item())
    assert ei.value.code == 2


def test_evaluation_task_refuses_without_item() -> None:
    with pytest.raises(SystemExit) as ei:
        ecm.evaluation_task()
    assert ei.value.code == 2
