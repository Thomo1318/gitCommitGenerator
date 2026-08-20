"""S5 D24 / S5-G05 — freeze scripts/setup_opik_*.py as non-authority.

Contract:
* No hard top-level ``import opik`` / ``import requests`` network clients.
* Live setup paths refuse with pointer to gated Lane C / offline tests.
* Scripts are never alternate accept-path / CI / golden authority.
"""

from __future__ import annotations

import ast
import importlib.util
import io
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / "scripts"

SETUP_RULE = SCRIPTS / "setup_opik_eval_rule.py"
SETUP_SUITES = SCRIPTS / "setup_opik_test_suites.py"
EVAL_COMMIT = SCRIPTS / "eval_commit_message.py"
OPIK_METRICS = SCRIPTS / "opik_metrics.py"


def _install_banned_module_sentinels(monkeypatch, banned_roots=None):
    """Remove loaded banned modules and block fresh imports (process-global isolation)."""
    import types

    roots = tuple(banned_roots or ("opik", "requests", "httpx", "openai", "anthropic"))
    # Drop already-loaded roots and submodules.
    for name in list(sys.modules):
        if name in roots or any(name.startswith(r + ".") for r in roots):
            monkeypatch.delitem(sys.modules, name, raising=False)

    class _BannedModule(types.ModuleType):
        def __getattr__(self, item):  # pragma: no cover - defensive
            """Block attribute access on a banned module sentinel."""
            raise ImportError(f"banned module access: {self.__name__}.{item}")

    for root in roots:
        sentinel = _BannedModule(root)
        monkeypatch.setitem(sys.modules, root, sentinel)
    return roots


def _load(path: Path, *, monkeypatch: pytest.MonkeyPatch, module_name: str):
    """Load a legacy script module with banned roots masked (process isolation)."""
    scripts_dir = str(path.parent)
    monkeypatch.syspath_prepend(scripts_dir)
    # Mask network/SDK modules so freezes cannot accidentally depend on them.
    _install_banned_module_sentinels(
        monkeypatch,
        banned_roots=("opik", "requests", "httpx", "openai", "anthropic"),
    )

    sys.modules.pop(module_name, None)
    sys.modules.pop(f"{module_name}_frozen", None)

    try:
        return __import__(module_name)
    except Exception:
        spec = importlib.util.spec_from_file_location(f"{module_name}_frozen", path)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


def _assert_no_banned_imports(path: Path, banned_roots: set[str]) -> None:
    """Assert script source has no top-level imports under banned roots."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                assert root not in banned_roots, f"{path.name}: import {alias.name} line {node.lineno}"
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            root = mod.split(".", 1)[0] if mod else ""
            assert root not in banned_roots, f"{path.name}: from {mod} import … line {node.lineno}"


@pytest.mark.parametrize(
    ("path", "module_name", "flag_name", "refuse_name", "needle"),
    [
        (SETUP_RULE, "setup_opik_eval_rule", "LEGACY_RULE_SETUP_RETIRED", "refuse_legacy_rule_setup", "lane_c"),
        (
            SETUP_SUITES,
            "setup_opik_test_suites",
            "LEGACY_TEST_SUITE_SETUP_RETIRED",
            "refuse_legacy_test_suite_setup",
            "tests/eval",
        ),
        (
            EVAL_COMMIT,
            "eval_commit_message",
            "LEGACY_EVAL_COMMIT_MESSAGE_RETIRED",
            "refuse_legacy_eval_commit_message",
            "scoring",
        ),
        (
            OPIK_METRICS,
            "opik_metrics",
            "LEGACY_OPIK_METRICS_RETIRED",
            "refuse_legacy_opik_metrics",
            "scoring",
        ),
    ],
)
class TestLegacyScriptFreeze:
    def test_no_hard_sdk_imports(
        self, path: Path, module_name: str, flag_name: str, refuse_name: str, needle: str
    ) -> None:
        del module_name, flag_name, refuse_name, needle
        _assert_no_banned_imports(path, {"opik", "requests", "httpx", "openai", "anthropic"})

    def test_flag_and_refuse(
        self,
        path: Path,
        module_name: str,
        flag_name: str,
        refuse_name: str,
        needle: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mod = _load(path, monkeypatch=monkeypatch, module_name=module_name)
        assert getattr(mod, flag_name) is True
        buf = io.StringIO()
        code = getattr(mod, refuse_name)(stream=buf)
        assert code == 2
        msg = buf.getvalue().lower()
        assert "frozen" in msg or "retired" in msg or "demotion" in msg
        assert needle.lower() in msg

    def test_main_refuses(
        self,
        path: Path,
        module_name: str,
        flag_name: str,
        refuse_name: str,
        needle: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        del flag_name, refuse_name, needle
        mod = _load(path, monkeypatch=monkeypatch, module_name=module_name)
        assert mod.main([]) == 2


class TestSetupRuleHelpersRefuse:
    def test_create_geval_rule_refuses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = _load(SETUP_RULE, monkeypatch=monkeypatch, module_name="setup_opik_eval_rule")
        with pytest.raises(SystemExit) as ei:
            mod.create_geval_rule("pid", "n", "p", {}, "http://example.invalid")
        assert ei.value.code == 2


class TestSetupSuitesHelpersRefuse:
    def test_run_test_suite_refuses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = _load(SETUP_SUITES, monkeypatch=monkeypatch, module_name="setup_opik_test_suites")
        with pytest.raises(SystemExit) as ei:
            mod.run_test_suite("ds", "metric")
        assert ei.value.code == 2


class TestEvalCommitMessageTaskRefuses:
    def test_evaluation_task_refuses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = _load(EVAL_COMMIT, monkeypatch=monkeypatch, module_name="eval_commit_message")
        with pytest.raises(SystemExit) as ei:
            mod.evaluation_task({"diff_output": "x", "expected_output": "y"})
        assert ei.value.code == 2


class TestOpikMetricsFormatMetricRefuses:
    def test_score_refuses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = _load(OPIK_METRICS, monkeypatch=monkeypatch, module_name="opik_metrics")
        metric = mod.FormatMetric()
        with pytest.raises(SystemExit) as ei:
            metric.score("✨ feat(test): x")
        assert ei.value.code == 2
