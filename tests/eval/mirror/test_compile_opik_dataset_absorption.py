"""S4 P2-3 / E6 — absorb/retire scripts/compile_opik_dataset.py upload path.

Contract:
* No hard top-level ``import opik`` in the legacy script (I4 / D20).
* Live upload path refuses with pointer to ``git-cg eval export drain``.
* Selection predicate never treats ``user_acceptance`` as correctness (E6).
* Layer-A train labels remain SoT via ``git_cg.eval.mirror.train``.
"""

from __future__ import annotations

import ast
import importlib.util
import io
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "compile_opik_dataset.py"


def _load_script_module(*, mask_opik: bool = False, monkeypatch: pytest.MonkeyPatch | None = None):
    """Load the retired compile script as a standalone module (not on package path)."""
    if mask_opik:
        assert monkeypatch is not None
        # Ensure script body never requires a real opik install.
        # Delete stale entries first, then install the None mask so the mask
        # is not immediately removed by the cleanup loop.
        for key in list(sys.modules):
            if key == "opik" or key.startswith("opik."):
                monkeypatch.delitem(sys.modules, key, raising=False)
        monkeypatch.setitem(sys.modules, "opik", None)  # type: ignore[arg-type]

    spec = importlib.util.spec_from_file_location(
        "compile_opik_dataset_retired",
        SCRIPT_PATH,
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules.pop("compile_opik_dataset_retired", None)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def script_mod():
    return _load_script_module()


class TestP23NoHardOpikImport:
    def test_no_module_level_opik_import(self) -> None:
        tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"), filename=str(SCRIPT_PATH))
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "opik" and not alias.name.startswith("opik."), (
                        f"module-level import opik forbidden at line {node.lineno}"
                    )
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert mod != "opik" and not mod.startswith("opik."), (
                    f"module-level from opik import forbidden at line {node.lineno}"
                )

    def test_script_imports_with_opik_masked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = _load_script_module(mask_opik=True, monkeypatch=monkeypatch)
        assert mod.LEGACY_UPLOAD_RETIRED is True
        assert callable(mod.compile_dataset)
        assert callable(mod.selection_predicate)


class TestP23RefuseUploadPath:
    def test_compile_dataset_refuses(self, script_mod) -> None:
        with pytest.raises(SystemExit) as ei:
            script_mod.compile_dataset("proj", "ds", 0.9)
        assert ei.value.code == 2

    def test_main_refuses_and_points_to_export_drain(self, script_mod) -> None:
        code = script_mod.main([])
        assert code == 2
        buf = io.StringIO()
        code2 = script_mod.refuse_legacy_upload(stream=buf)
        assert code2 == 2
        msg = buf.getvalue()
        assert "retired" in msg.lower()
        assert "git-cg eval export drain" in msg
        assert "user_acceptance" in msg
        assert "src/git_cg/eval/mirror" in msg

    def test_canonical_commands_documented(self, script_mod) -> None:
        joined = "\n".join(script_mod.CANONICAL_EXPORT_COMMANDS)
        assert "export status" in joined
        assert "export retry" in joined
        assert "export drain" in joined


class TestE6SelectionPredicateNoUserAcceptance:
    """E6: selection predicate never treats user_acceptance as correctness."""

    def test_forbidden_signal_constant(self, script_mod) -> None:
        assert "user_acceptance" in script_mod.FORBIDDEN_CORRECTNESS_SIGNALS

    def test_source_has_no_live_upload_surfaces(self) -> None:
        src = SCRIPT_PATH.read_text(encoding="utf-8")
        # Mentions of the ban are allowed in docs; live SDK call sites are not.
        for banned in (
            "search_traces",
            "get_or_create_dataset",
            "dataset.insert",
            "client.insert",
            "Opik()",
            "feedback_scores.user_acceptance",
        ):
            assert banned not in src, banned

        # Hard import absence is enforced by AST (see test_no_module_level_opik_import).
        tree = ast.parse(src, filename=str(SCRIPT_PATH))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "opik" and not alias.name.startswith("opik.")
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert mod != "opik" and not mod.startswith("opik.")
            if isinstance(node, ast.Call):
                # No Opik() constructor or client.search_traces-style calls.
                func = node.func
                if isinstance(func, ast.Name):
                    assert func.id != "Opik"
                if isinstance(func, ast.Attribute):
                    assert func.attr not in {
                        "search_traces",
                        "get_or_create_dataset",
                        "insert",
                    }

    def test_predicate_accepts_layer_a_positive_label(self, script_mod) -> None:
        assert script_mod.selection_predicate({"train_label": "positive", "bundle_id": "b1"}) is True
        assert script_mod.selection_predicate({"label": "preference_chosen"}) is True

    def test_predicate_rejects_unlabeled_and_negatives(self, script_mod) -> None:
        assert script_mod.selection_predicate({}) is False
        assert script_mod.selection_predicate({"label": "unlabeled"}) is False
        assert script_mod.selection_predicate({"label": "negative"}) is False

    def test_predicate_rejects_user_acceptance_keys(self, script_mod) -> None:
        # Popularity-shaped rows must never pass even if a positive label is present.
        assert (
            script_mod.selection_predicate(
                {
                    "user_acceptance": 1.0,
                    "train_label": "positive",
                }
            )
            is False
        )
        assert (
            script_mod.selection_predicate(
                {
                    "feedback_scores.user_acceptance": 0.95,
                    "label": "positive",
                }
            )
            is False
        )
        assert (
            script_mod.selection_predicate(
                {
                    "meta_user_acceptance_score": 1.0,
                    "label": "positive",
                }
            )
            is False
        )

    def test_predicate_source_ast_never_uses_threshold_filter(self) -> None:
        """Static AST: selection_predicate body must not reintroduce score thresholds."""
        tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"), filename=str(SCRIPT_PATH))
        fn = next(
            (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "selection_predicate"),
            None,
        )
        assert fn is not None, "selection_predicate missing"

        loaded_strings = [
            node.value for node in ast.walk(fn) if isinstance(node, ast.Constant) and isinstance(node.value, str)
        ]
        joined = " | ".join(loaded_strings)
        assert "feedback_scores.user_acceptance" not in joined
        assert "threshold" not in joined.lower()

    def test_library_train_path_remains_sot(self) -> None:
        """Layer-A Q18 train helpers remain the real projection SoT."""
        from git_cg.eval.mirror.train import (
            build_train_projection,
            filter_positive_gold,
            normalize_train_label,
        )

        # Popularity token is not a train label.
        assert normalize_train_label("user_acceptance") is None

        gold = filter_positive_gold(
            [
                {"label": "positive", "bundle_id": "p"},
                {"label": "negative", "bundle_id": "n"},
                {"user_acceptance": 1.0, "bundle_id": "pop"},  # popularity only
            ]
        )
        assert [g["bundle_id"] for g in gold] == ["p"]

        proj = build_train_projection(
            [
                {
                    "id": "p1",
                    "meta": {"train_label": "positive", "redaction_profile": "train_rich"},
                    "gate": {},
                    "score_card": {},
                },
                {
                    "id": "u1",
                    "meta": {"user_acceptance": 1.0, "redaction_profile": "train_rich"},
                    "gate": {},
                    "score_card": {},
                },
            ]
        )
        assert proj["excluded_unlabeled"] == 1
        assert {r["bundle_id"] for r in proj["positive_gold"]} == {"p1"}
