"""Freeze contract for scripts/opik_metrics.py (S2b demotion / S5 D24 / #233).

FormatMetric is retired advisory surface only. It must not act as scoring law,
must not import the Opik SDK, and must fail closed on score/main.
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

import opik_metrics as om  # noqa: E402
from opik_metrics import (  # noqa: E402
    CANONICAL_SCORING_HOME,
    LEGACY_OPIK_METRICS_RETIRED,
    FormatMetric,
    main,
    refuse_legacy_opik_metrics,
)


def test_module_exports_freeze_surface() -> None:
    assert LEGACY_OPIK_METRICS_RETIRED is True
    assert CANONICAL_SCORING_HOME == "src/git_cg/eval/scoring/"
    assert "FormatMetric" in om.__all__
    assert "refuse_legacy_opik_metrics" in om.__all__
    assert "main" in om.__all__


def test_source_has_no_hard_sdk_imports() -> None:
    path = SCRIPTS / "opik_metrics.py"
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
    code = refuse_legacy_opik_metrics(stream=buf)
    assert code == 2
    msg = buf.getvalue().lower()
    assert "frozen" in msg or "retired" in msg or "demotion" in msg or "legacy" in msg
    assert "scoring" in msg


def test_main_refuses() -> None:
    assert main([]) == 2


def test_format_metric_keeps_name_only() -> None:
    metric = FormatMetric()
    assert metric.name == "CommitFormatQuality"
    custom = FormatMetric(name="MyCustomMetric")
    assert custom.name == "MyCustomMetric"


@pytest.mark.parametrize(
    "output",
    [
        "feat(eval): integrate atomic metrics",
        "",
        None,
        42,
        ["feat: x"],
    ],
)
def test_format_metric_score_refuses(output: object) -> None:
    metric = FormatMetric()
    with pytest.raises(SystemExit) as ei:
        metric.score(output)  # type: ignore[arg-type]
    assert ei.value.code == 2
