"""S2 must wrap product authorities — no eval-only Hybrid/gold policy forks."""

from __future__ import annotations

import ast
from pathlib import Path

import git_cg.eval.scoring.product_bridges as bridges
from git_cg.commit_gold import STRICT_FAIL_CODES, check_commit_gold
from git_cg.telemetry import reverse_parse_commit_message, run_deterministic_checks

SCORING_ROOT = Path(__file__).resolve().parents[2] / "src" / "git_cg" / "eval" / "scoring"


def test_product_symbols_are_the_authorities() -> None:
    assert bridges.check_commit_gold is check_commit_gold
    assert bridges.reverse_parse_commit_message is reverse_parse_commit_message
    assert bridges.run_deterministic_checks is run_deterministic_checks
    assert bridges.STRICT_FAIL_CODES is STRICT_FAIL_CODES


def test_family_modules_import_product_bridges_not_local_sop_tables() -> None:
    """Scan scoring package AST for forbidden local SOP matrix reinvention."""
    forbidden_names = {
        "SOP_EMOJI_MAP",
        "GITMOJI_MATRIX",
        "CHANGELOG_GROUP_TABLE",
        "eval_only_gold",
    }
    hits: list[str] = []
    for path in SCORING_ROOT.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in forbidden_names:
                hits.append(f"{path.name}:{node.id}")
            if isinstance(node, ast.Attribute) and node.attr in forbidden_names:
                hits.append(f"{path.name}:{node.attr}")
    assert hits == []


def test_gold_code_map_covers_strict_fail_codes() -> None:
    """
    Verify that every strict-failure code maps to a metric present in the scoring catalogue.
    """
    from git_cg.eval.scoring.product_bridges import GOLD_CODE_TO_D_METRIC
    from git_cg.eval.scoring.result_builder import metric_row

    for code in STRICT_FAIL_CODES:
        assert code in GOLD_CODE_TO_D_METRIC, f"missing map for {code}"
        mid = GOLD_CODE_TO_D_METRIC[code]
        assert metric_row(mid) is not None, f"catalog missing {mid} for {code}"


def test_scoring_not_imported_by_main_commit_path() -> None:
    """Normal git-cg commit path must not hard-require eval.scoring."""
    main_path = Path(__file__).resolve().parents[2] / "src" / "git_cg" / "main.py"
    text = main_path.read_text(encoding="utf-8")
    assert "git_cg.eval.scoring" not in text
    assert "eval.scoring" not in text


def test_legacy_opik_metrics_not_s2_law() -> None:
    """scripts/opik_metrics.py remains legacy/advisory and is not imported by S2."""
    hits = []
    for path in SCORING_ROOT.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "opik_metrics" in text or "scripts.opik_metrics" in text:
            hits.append(path.name)
    assert hits == []
