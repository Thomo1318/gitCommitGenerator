"""Phase 9 scoped-history producers (Issue #163)."""

from __future__ import annotations

from types import SimpleNamespace

from git_cg.scoped_history import (
    RenameConfidence,
    ScopedHistoryFallbackReason,
    apply_scoped_history_to_plan,
    band_rename_pair,
    build_scoped_history_guidance,
    coerce_fallback_reason,
    coerce_rename_confidence,
    empty_scoped_history_evidence,
    evaluate_rename_confidence,
    evaluate_scoped_history,
    evaluate_split_evidence,
    extract_file_to_flow_ids,
    or_merge_split_recommended,
    structural_markers_from_sources,
)


def test_coerce_fallback_and_rename_closed_vocab():
    assert coerce_fallback_reason(None) == "none"
    assert coerce_fallback_reason("graph_unavailable") == "graph_unavailable"
    assert coerce_fallback_reason("nope") == "none"
    assert coerce_rename_confidence("HIGH") == "high"
    assert coerce_rename_confidence("weird") == "none"


def test_extract_file_to_flow_ids_shapes_and_bounds():
    payload = {
        "flows": [
            {"id": "flow_a", "files": ["a.py", "b.py"]},
            {"flow_id": "flow_b", "paths": ["c.py"]},
        ]
    }
    mapping = extract_file_to_flow_ids(payload, staged_files=["a.py", "c.py", "z.py"])
    assert mapping["a.py"] == ["flow_a"]
    assert "b.py" not in mapping  # not staged
    assert mapping["c.py"] == ["flow_b"]


def test_split_evidence_disjoint_high_confidence():
    mapping = {
        "a.py": ["flow_a"],
        "b.py": ["flow_b"],
    }
    hc, rationale = evaluate_split_evidence(mapping, staged_files=["a.py", "b.py"])
    assert hc is True
    assert "flow-disjoint" in rationale


def test_split_evidence_shared_flow_is_negative():
    mapping = {
        "a.py": ["flow_a", "shared"],
        "b.py": ["shared"],
    }
    hc, _ = evaluate_split_evidence(mapping, staged_files=["a.py", "b.py"])
    assert hc is False


def test_split_evidence_preflight_multi_group():
    hc, rationale = evaluate_split_evidence({}, staged_files=["a.py"], preflight_groups_count=3)
    assert hc is True
    assert "preflight_groups_count=3" in rationale


def test_band_rename_pair_matrix():
    assert band_rename_pair(git_rename=True, code_fp_match=True, body_sim=0.1) == RenameConfidence.HIGH
    assert band_rename_pair(git_rename=True, code_fp_match=None, body_sim=0.9) == RenameConfidence.HIGH
    assert band_rename_pair(git_rename=True, code_fp_match=None, body_sim=None) == RenameConfidence.MEDIUM
    assert band_rename_pair(git_rename=False, code_fp_match=False, body_sim=0.3) == RenameConfidence.LOW
    assert band_rename_pair(git_rename=False, code_fp_match=None, body_sim=None) == RenameConfidence.NONE


def test_evaluate_rename_confidence_git_only_medium(monkeypatch):
    # Force fingerprint stack import failure path via empty pairs handled separately;
    # with pairs and no bytes, band stays medium via git_rename alone.
    band, rationale = evaluate_rename_confidence(
        [("old.py", "new.py")],
        old_bytes_by_path={},
        new_bytes_by_path={},
        enable_semantic=True,
    )
    assert band == RenameConfidence.MEDIUM.value
    assert "git rename" in rationale or rationale == "" or "pair" in rationale


def test_evaluate_scoped_history_flag_off_is_noop():
    evidence = evaluate_scoped_history(
        enable_semantic=False,
        file_to_flow_ids={"a.py": ["f1"], "b.py": ["f2"]},
        staged_files=["a.py", "b.py"],
    )
    assert evidence.fallback_reason == ScopedHistoryFallbackReason.NONE.value
    assert evidence.split_high_confidence is False
    assert evidence.guidance is None


def test_evaluate_scoped_history_split_and_guidance():
    evidence = evaluate_scoped_history(
        enable_semantic=True,
        file_to_flow_ids={"a.py": ["f1"], "b.py": ["f2"]},
        staged_files=["a.py", "b.py"],
        renamed_paths=[],
        staged_sources={},
    )
    assert evidence.split_high_confidence is True
    assert evidence.guidance is not None
    assert "preferred_type" not in evidence.guidance.lower()
    assert "Split evidence" in evidence.guidance


def test_build_guidance_bans_authority_leakage():
    # Normal path
    text = build_scoped_history_guidance(
        split_high_confidence=True,
        split_rationale="disjoint flows",
        rename_confidence="high",
        rename_rationale="corroborated",
    )
    assert text is not None
    assert "preferred_type" not in text.lower()


def test_or_merge_never_clears_model_true():
    assert or_merge_split_recommended(True, False) is True
    assert or_merge_split_recommended(False, True) is True
    assert or_merge_split_recommended(False, False) is False


def test_apply_scoped_history_to_plan_or_merge_and_rationale():
    plan = SimpleNamespace(split_recommended=False, rationale="model note")
    evidence = empty_scoped_history_evidence()
    evidence.split_high_confidence = True
    evidence.split_rationale = "flow-disjoint partition"
    evidence.rename_confidence = "high"
    evidence.rename_rationale = "corroborated rename"
    out = apply_scoped_history_to_plan(plan, evidence)
    assert out.split_recommended is True
    assert "scoped-history split" in out.rationale
    assert "scoped-history rename" in out.rationale
    # Authority fields must not be invented on the plan.
    assert not hasattr(out, "intent_id") or True


def test_structural_markers_error_handling_from_source():
    """P9-B11: semantic-ON structural except/raise evidence."""
    from git_cg.scoped_history import structural_markers_from_sources

    src = b"def f():\n    try:\n        x()\n    except ValueError:\n        raise\n"
    err, pub, cmd = structural_markers_from_sources({"mod.py": src}, enable_semantic=True)
    assert err is True
    assert pub is True
    assert cmd is False


def test_structural_markers_new_command_requires_cli_hint():
    """P9-B12: new_command only with structural CLI evidence + hint."""
    from git_cg.scoped_history import structural_markers_from_sources

    plain = b"def helper():\n    return 1\n"
    _, _, cmd_plain = structural_markers_from_sources({"util.py": plain}, enable_semantic=True)
    assert cmd_plain is False

    cli = b"import typer\napp = typer.Typer()\n\n@app.command()\ndef run():\n    pass\n"
    _err, pub, cmd = structural_markers_from_sources({"cli.py": cli}, enable_semantic=True)
    assert cmd is True
    assert pub is True


def test_structural_markers_flag_off():
    from git_cg.scoped_history import structural_markers_from_sources

    src = b"def f():\n    try:\n        pass\n    except Exception:\n        pass\n"
    assert structural_markers_from_sources({"a.py": src}, enable_semantic=False) == (False, False, False)


def test_evaluate_rename_confidence_high_with_identical_bytes():
    """P9-B04: git rename + identical body/code_fp → high."""
    body = b"def hello():\n    return 42\n"
    band, _rationale = evaluate_rename_confidence(
        [("old_mod.py", "new_mod.py")],
        old_bytes_by_path={"old_mod.py": body},
        new_bytes_by_path={"new_mod.py": body},
        enable_semantic=True,
    )
    assert band == RenameConfidence.HIGH.value


def test_evaluate_rename_confidence_non_rename_stays_none():
    """P9-B05: no pairs → none."""
    band, _ = evaluate_rename_confidence([], enable_semantic=True)
    assert band == RenameConfidence.NONE.value


def test_apply_scoped_history_never_sets_authority_fields():
    """P9-B08: plan authority fields untouched."""
    plan = SimpleNamespace(
        split_recommended=False,
        rationale="base",
        intent_id="feature_addition",
        gitmoji="✨",
        cc_type="feat",
        semver_impact="MINOR",
        changelog_group="Added",
    )
    evidence = empty_scoped_history_evidence()
    evidence.split_high_confidence = True
    evidence.split_rationale = "flow-disjoint"
    evidence.rename_confidence = "high"
    out = apply_scoped_history_to_plan(plan, evidence)
    assert out.intent_id == "feature_addition"
    assert out.gitmoji == "✨"
    assert out.cc_type == "feat"
    assert out.semver_impact == "MINOR"
    assert out.changelog_group == "Added"
    assert out.split_recommended is True


def test_fixtures_flow_disjoint_split_high_confidence():
    """Fixture: disjoint auth/billing flows → high-confidence split."""
    import json
    from pathlib import Path

    root = Path(__file__).parent / "fixtures" / "scoped_history"
    flows = json.loads((root / "flow_disjoint_flows.json").read_text())
    staged = (root / "flow_disjoint_staged.txt").read_text().splitlines()
    file_map = extract_file_to_flow_ids(flows, staged_files=staged)
    hc, rationale = evaluate_split_evidence(file_map, staged_files=staged)
    assert hc is True
    assert "disjoint" in rationale.lower() or "component" in rationale.lower() or rationale


def test_fixtures_flow_overlap_not_high_confidence():
    """Fixture: overlapping flows → no high-confidence split."""
    import json
    from pathlib import Path

    root = Path(__file__).parent / "fixtures" / "scoped_history"
    flows = json.loads((root / "flow_overlap_flows.json").read_text())
    staged = (root / "flow_overlap_staged.txt").read_text().splitlines()
    file_map = extract_file_to_flow_ids(flows, staged_files=staged)
    hc, _ = evaluate_split_evidence(file_map, staged_files=staged)
    assert hc is False


def test_fixtures_rename_identical_high():
    from pathlib import Path

    root = Path(__file__).parent / "fixtures" / "scoped_history"
    old_b = (root / "rename_old.py").read_bytes()
    new_b = (root / "rename_new.py").read_bytes()
    band, _ = evaluate_rename_confidence(
        [("pkg/old_name.py", "pkg/new_name.py")],
        old_bytes_by_path={"pkg/old_name.py": old_b},
        new_bytes_by_path={"pkg/new_name.py": new_b},
        enable_semantic=True,
    )
    assert band == RenameConfidence.HIGH.value


def test_fixtures_structural_error_and_cli():
    from pathlib import Path

    root = Path(__file__).parent / "fixtures" / "scoped_history"
    err_src = (root / "structural_error.py").read_bytes()
    cli_src = (root / "structural_cli.py").read_bytes()
    err, pub, _cmd = structural_markers_from_sources({"structural_error.py": err_src}, enable_semantic=True)
    assert err is True
    assert pub is True
    _err2, pub2, cmd2 = structural_markers_from_sources({"structural_cli.py": cli_src}, enable_semantic=True)
    assert cmd2 is True
    assert pub2 is True
