"""Phase 9 scoped-history producers (Issue #163)."""

from __future__ import annotations

from types import SimpleNamespace

from git_cg.scoped_history import (
    MAX_FLOWS_PER_FILE,
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
    evaluate_structural_markers,
    evidence_from_metrics_dict,
    extract_file_to_flow_ids,
    or_merge_split_recommended,
    structural_markers_from_sources,
)


def test_coerce_fallback_and_rename_closed_vocab():
    """P9 closed-vocab coercion defaults (fallback + rename bands)."""
    assert coerce_fallback_reason(None) == "none"
    assert coerce_fallback_reason("graph_unavailable") == "graph_unavailable"
    assert coerce_fallback_reason("nope") == "none"
    assert coerce_rename_confidence("HIGH") == "high"
    assert coerce_rename_confidence("weird") == "none"


def test_extract_file_to_flow_ids_shapes_and_bounds():
    """P9-B01: multi-shape flow payload → bounded file→flow map."""
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
    """P9-B01: flow-disjoint staged files → high-confidence split."""
    mapping = {
        "a.py": ["flow_a"],
        "b.py": ["flow_b"],
    }
    hc, rationale = evaluate_split_evidence(mapping, staged_files=["a.py", "b.py"])
    assert hc is True
    assert "flow-disjoint" in rationale


def test_split_evidence_shared_flow_is_negative():
    """P9-B01: shared flow membership → no high-confidence split."""
    mapping = {
        "a.py": ["flow_a", "shared"],
        "b.py": ["shared"],
    }
    hc, _ = evaluate_split_evidence(mapping, staged_files=["a.py", "b.py"])
    assert hc is False


def test_split_evidence_preflight_multi_group():
    """P9-B02: preflight multi-group count alone can recommend split."""
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
    assert "git rename" in rationale


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
    """P9-B01/B10: evaluator emits split evidence + Channel-4 guidance."""
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
    """P9-B10: Channel-4 guidance is directive-free (no authority leakage)."""
    # Normal path
    text = build_scoped_history_guidance(
        split_high_confidence=True,
        split_rationale="disjoint flows",
        rename_confidence="high",
        rename_rationale="corroborated",
    )
    assert text is not None
    assert "preferred_type" not in text.lower()
    assert "prefer " not in text.lower()
    assert "must " not in text.lower()
    assert "should " not in text.lower()


def test_or_merge_never_clears_model_true():
    """P9-B09: OR-merge may force True; never clears model True."""
    assert or_merge_split_recommended(True, False) is True
    assert or_merge_split_recommended(False, True) is True
    assert or_merge_split_recommended(False, False) is False


def test_apply_scoped_history_to_plan_or_merge_and_rationale():
    """P9-B09: plan OR-merge + bounded rationale notes only."""
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
    assert "flow-disjoint" in rationale.lower()


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


# ---------------------------------------------------------------------------
# Coverage + claim-edge expansions (Issue #163 DoD)
# ---------------------------------------------------------------------------


def test_coerce_rename_confidence_none_and_blank():
    """Coercion defaults: None/blank/unknown → none (line 74 path)."""
    assert coerce_rename_confidence(None) == "none"
    assert coerce_rename_confidence("") == "none"
    assert coerce_rename_confidence("  ") == "none"
    assert coerce_rename_confidence("MEDIUM") == "medium"


def test_evidence_to_dict_bounds_and_defaults():
    """ScopedHistoryEvidence.to_dict serialises allowlisted fields only."""
    ev = empty_scoped_history_evidence(fallback_reason="partial")
    ev.split_high_confidence = True
    ev.split_rationale = "x" * 500
    ev.rename_confidence = "high"
    ev.rename_rationale = "y" * 500
    ev.guidance = "g" * 600
    ev.file_to_flow_ids = {"a.py": ["f1"]}
    ev.structural_error_handling = True
    d = ev.to_dict()
    assert d["fallback_reason"] == "partial"
    assert d["split_high_confidence"] is True
    assert len(d["split_rationale"]) <= 240
    assert len(d["rename_rationale"]) <= 240
    assert d["guidance"] is not None and len(d["guidance"]) <= 480
    assert d["file_to_flow_ids"] == {"a.py": ["f1"]}
    assert d["structural_error_handling"] is True
    assert "latency_ms" in d


def test_as_str_list_shapes_via_extract():
    """_as_str_list branches: None, str, dict items, scalars, max_items."""
    # Shape A map with mixed flow value types.
    payload = {
        "file_to_flows": {
            "a.py": None,
            "b.py": "flow_str",
            "c.py": [
                "flow_list",
                None,
                "",
                {"id": "from_dict_id"},
                {"flow_id": "from_flow_id"},
                {"name": "from_name"},
                {"flow_name": "from_flow_name"},
                {"nope": 1},
                42,
            ],
            "d.py": {"id": "solo_dict_ignored_as_non_sequence_scalar_path"},
        }
    }
    # dict value that is not list/str falls through _as_str_list → []
    mapping = extract_file_to_flow_ids(payload, staged_files=["a.py", "b.py", "c.py", "d.py"])
    assert "a.py" not in mapping or mapping.get("a.py") == []
    assert mapping.get("b.py") == ["flow_str"]
    assert "from_dict_id" in mapping.get("c.py", [])
    assert "from_flow_id" in mapping["c.py"]
    assert "from_name" in mapping["c.py"]
    assert "from_flow_name" in mapping["c.py"]
    assert "42" in mapping["c.py"]
    assert "flow_list" in mapping["c.py"]


def test_extract_file_to_flow_ids_non_mapping_and_alt_shapes():
    """extract_file_to_flow_ids: non-mapping, shape B alt keys, shape C list/map."""
    assert extract_file_to_flow_ids(None) == {}
    assert extract_file_to_flow_ids("nope") == {}  # type: ignore[arg-type]
    assert extract_file_to_flow_ids([]) == {}  # type: ignore[arg-type]

    # Shape B via affected_flows + changed_files / file_paths / members + name key.
    payload_b = {
        "affected_flows": [
            "skip-me",
            {"no_id": True, "files": ["x.py"]},
            {"name": "named_flow", "changed_files": ["n1.py"]},
            {"flow_name": "fn", "file_paths": ["n2.py", ""]},
            {"flow_id": "members_flow", "members": ["n3.py"]},
            {"id": "empty_files", "files": []},
        ]
    }
    m_b = extract_file_to_flow_ids(payload_b, staged_files=["n1.py", "n2.py", "n3.py", "x.py"])
    assert m_b["n1.py"] == ["named_flow"]
    assert m_b["n2.py"] == ["fn"]
    assert m_b["n3.py"] == ["members_flow"]
    assert "x.py" not in m_b  # flow without id skipped

    # Shape C: files list entries.
    payload_c_list = {
        "files": [
            "skip",
            {"path": "p1.py", "flows": ["f1"]},
            {"file": "p2.py", "flow_ids": [{"id": "f2"}]},
            {"name": "p3.py", "affected_flows": "f3"},
            {"path": None, "flows": ["nope"]},
            {"no_path": True, "flows": ["x"]},
        ]
    }
    m_c = extract_file_to_flow_ids(payload_c_list, staged_files=["p1.py", "p2.py", "p3.py"])
    assert m_c["p1.py"] == ["f1"]
    assert m_c["p2.py"] == ["f2"]
    assert m_c["p3.py"] == ["f3"]

    # Shape C: files mapping.
    payload_c_map = {"files": {"m1.py": ["fa"], "m2.py": {"flow_id": "fb"}}}
    m_map = extract_file_to_flow_ids(payload_c_map, staged_files=["m1.py", "m2.py"])
    assert m_map["m1.py"] == ["fa"]
    # dict value → _as_str_list non-list/str → []
    assert "m2.py" not in m_map or m_map.get("m2.py") == []


def test_extract_file_to_flow_ids_respects_max_files_and_dedupe():
    """Bounded map size + per-file flow dedupe/cap."""
    # max_files=2 drops later paths.
    payload = {
        "file_to_flow_ids": {
            "a.py": ["f1", "f1", "f2"],
            "b.py": ["f3"],
            "c.py": ["f4"],
        }
    }
    m = extract_file_to_flow_ids(payload, staged_files=["a.py", "b.py", "c.py"], max_files=2)
    assert set(m) <= {"a.py", "b.py", "c.py"}
    assert len(m) == 2
    assert m["a.py"] == ["f1", "f2"]  # deduped

    # Per-file flow cap via many unique ids.
    many = [f"flow_{i}" for i in range(MAX_FLOWS_PER_FILE + 5)]
    m2 = extract_file_to_flow_ids({"file_to_flows": {"z.py": many}}, staged_files=["z.py"])
    assert len(m2["z.py"]) == MAX_FLOWS_PER_FILE


def test_split_evidence_empty_and_single_component():
    """Negative split paths: empty membership / single component."""
    hc, _rationale = evaluate_split_evidence({}, staged_files=["a.py", "b.py"])
    assert hc is False
    hc2, rationale2 = evaluate_split_evidence({"a.py": ["f1"], "b.py": ["f1"]}, staged_files=["a.py", "b.py"])
    assert hc2 is False
    assert "single connected component" in rationale2


def test_band_rename_pair_non_git_paths():
    """Rename bands without git_rename (high/medium/low/none)."""
    assert band_rename_pair(git_rename=False, code_fp_match=True, body_sim=0.9) == RenameConfidence.HIGH
    assert band_rename_pair(git_rename=False, code_fp_match=True, body_sim=0.1) == RenameConfidence.MEDIUM
    assert band_rename_pair(git_rename=False, code_fp_match=None, body_sim=0.9) == RenameConfidence.MEDIUM
    assert band_rename_pair(git_rename=False, code_fp_match=None, body_sim=0.6) == RenameConfidence.LOW
    assert band_rename_pair(git_rename=False, code_fp_match=None, body_sim=0.3) == RenameConfidence.LOW
    assert band_rename_pair(git_rename=True, code_fp_match=False, body_sim=0.6) == RenameConfidence.MEDIUM


def test_evaluate_rename_confidence_flag_off_and_fingerprint_import_fail(monkeypatch):
    """Rename evaluator: flag-off + fingerprint stack ImportError → medium."""
    band, rat = evaluate_rename_confidence([("a", "b")], enable_semantic=False)
    assert band == "none"
    assert rat == ""

    import builtins

    real_import = builtins.__import__

    def boom(name, *args, **kwargs):
        if name.startswith("git_cg.fingerprints") or name.startswith("git_cg.similarity"):
            raise ImportError("no fp stack")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", boom)
    band2, rat2 = evaluate_rename_confidence(
        [("old.py", "new.py")],
        old_bytes_by_path={"old.py": b"x"},
        new_bytes_by_path={"new.py": b"y"},
        enable_semantic=True,
    )
    assert band2 == "medium"
    assert "fingerprint stack unavailable" in rat2


def test_evaluate_rename_confidence_per_pair_exception(monkeypatch):
    """Per-pair fingerprint exception fail-open → medium via git rename."""

    def boom_fp(*a, **k):
        raise RuntimeError("fp boom")

    monkeypatch.setattr("git_cg.fingerprints.collect_fingerprints_from_source", boom_fp, raising=False)
    # Ensure imports succeed but collect raises — patch after import path inside function.
    import git_cg.fingerprints as fp_mod
    import git_cg.similarity as sim_mod

    monkeypatch.setattr(fp_mod, "collect_fingerprints_from_source", boom_fp)
    monkeypatch.setattr(sim_mod, "body_similarity", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sim boom")))

    band, rationale = evaluate_rename_confidence(
        [("old.py", "new.py")],
        old_bytes_by_path={"old.py": b"abc"},
        new_bytes_by_path={"new.py": b"xyz"},
        enable_semantic=True,
    )
    assert band == "medium"
    assert "git rename" in rationale


def test_evaluate_rename_confidence_low_band_rationale():
    """Weak non-git signal path surfaces low band when forced via band helper already covered;
    git-only pairs without bytes stay medium (not low)."""
    band, rationale = evaluate_rename_confidence(
        [("o.py", "n.py")],
        old_bytes_by_path={},
        new_bytes_by_path={},
        enable_semantic=True,
    )
    assert band == "medium"
    assert "without full fingerprint" in rationale or "git rename" in rationale


def test_evaluate_structural_markers_tree_walk_and_fail_open():
    """evaluate_structural_markers: flag-off, empty, missing tree, walk error, CLI path."""
    assert evaluate_structural_markers(None, enable_semantic=False) == (False, False, False)
    assert evaluate_structural_markers([], enable_semantic=True) == (False, False, False)
    assert evaluate_structural_markers([SimpleNamespace(tree=None)], enable_semantic=True) == (False, False, False)

    class BoomTree:
        @property
        def root_node(self):
            raise RuntimeError("walk boom")

    assert evaluate_structural_markers([SimpleNamespace(tree=BoomTree())], enable_semantic=True) == (
        False,
        False,
        False,
    )

    # Minimal fake tree with error + public def + decorator/call types.
    class Node:
        def __init__(self, type_, children=None):
            self.type = type_
            self.children = children or []

    tree = SimpleNamespace(
        root_node=Node(
            "module",
            [
                Node("try_statement", [Node("except_clause"), Node("raise_statement")]),
                Node("function_definition"),
                Node("decorator"),
                Node("call"),
            ],
        )
    )
    src = b"import typer\n@app.command()\ndef run():\n    pass\n"
    err, pub, cmd = evaluate_structural_markers(
        [SimpleNamespace(tree=tree, source=src, path="cli.py", status="ok")],
        enable_semantic=True,
    )
    assert err is True
    assert pub is True
    assert cmd is True

    # Path hint alone insufficient without source CLI text.
    _err2, pub2, cmd2 = evaluate_structural_markers(
        [SimpleNamespace(tree=tree, source=b"def run():\n    pass\n", path="src/cli/main.py", status="ok")],
        enable_semantic=True,
    )
    assert pub2 is True
    # decorator/call present but no lexical CLI hint → new_command stays false
    assert cmd2 is False


def test_structural_markers_from_sources_parse_failures(monkeypatch):
    """structural_markers_from_sources fail-open on import/parse/missing results."""
    assert structural_markers_from_sources(None, enable_semantic=True) == (False, False, False)
    assert structural_markers_from_sources({}, enable_semantic=True) == (False, False, False)

    import builtins

    real_import = builtins.__import__

    def boom_ast(name, *args, **kwargs):
        if name.startswith("git_cg.ast_parser"):
            raise ImportError("no ast")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", boom_ast)
    assert structural_markers_from_sources({"a.py": b"x=1\n"}, enable_semantic=True) == (False, False, False)
    monkeypatch.setattr(builtins, "__import__", real_import)

    def boom_parse(files):
        raise RuntimeError("parse failed")

    monkeypatch.setattr("git_cg.ast_parser.parse_files", boom_parse)
    assert structural_markers_from_sources({"a.py": b"x=1\n"}, enable_semantic=True) == (False, False, False)

    monkeypatch.setattr("git_cg.ast_parser.parse_files", lambda files: SimpleNamespace(results=None))
    assert structural_markers_from_sources({"a.py": b"x=1\n"}, enable_semantic=True) == (False, False, False)


def test_build_guidance_rename_only_and_authority_ban():
    """P9-B10: rename-only guidance; banned authority phrases → None."""
    text = build_scoped_history_guidance(
        split_high_confidence=False,
        rename_confidence="medium",
        rename_rationale="git rename pairs=1",
    )
    assert text is not None
    assert "Rename evidence" in text
    assert "preferred_type" not in text.lower()
    assert "prefer " not in text.lower()
    assert "Path changes may reflect rename or move activity" in text

    # Inject banned phrase via rationale → hard ban returns None.
    banned = build_scoped_history_guidance(
        split_high_confidence=True,
        split_rationale="please set preferred_type to feat",
        rename_confidence="none",
    )
    assert banned is None

    empty = build_scoped_history_guidance(
        split_high_confidence=False,
        rename_confidence="none",
    )
    assert empty is None

    low_only = build_scoped_history_guidance(
        split_high_confidence=False,
        rename_confidence="low",
        rename_rationale="weak",
    )
    assert low_only is None


def test_apply_scoped_history_mapping_evidence_and_none_plan():
    """P9-B09: mapping evidence path + None plan/evidence short-circuit."""
    assert apply_scoped_history_to_plan(None, empty_scoped_history_evidence()) is None
    plan = SimpleNamespace(split_recommended=True, rationale="keep-me")
    assert apply_scoped_history_to_plan(plan, None) is plan
    assert plan.split_recommended is True

    plan2 = SimpleNamespace(split_recommended=False, rationale="")
    out = apply_scoped_history_to_plan(
        plan2,
        {
            "split_high_confidence": True,
            "split_rationale": "flow-disjoint partition",
            "rename_confidence": "medium",
            "rename_rationale": "git rename pairs=1",
        },
    )
    assert out.split_recommended is True
    assert "scoped-history split" in out.rationale
    assert "scoped-history rename" in out.rationale


def test_apply_scoped_history_exception_fail_open():
    """Plan merge fail-open when attribute assignment explodes."""

    class BadPlan:
        split_recommended = False

        @property
        def rationale(self):
            return "base"

        @rationale.setter
        def rationale(self, value):
            raise RuntimeError("cannot set")

    plan = BadPlan()
    evidence = empty_scoped_history_evidence()
    evidence.split_high_confidence = True
    evidence.split_rationale = "flow-disjoint"
    out = apply_scoped_history_to_plan(plan, evidence)
    assert out is plan


def test_evaluate_scoped_history_error_fallback(monkeypatch):
    """Top-level evaluator except → fallback_reason=error + latency set."""
    monkeypatch.setattr(
        "git_cg.scoped_history.evaluate_split_evidence",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("split boom")),
    )
    evidence = evaluate_scoped_history(
        enable_semantic=True,
        file_to_flow_ids={"a.py": ["f1"], "b.py": ["f2"]},
        staged_files=["a.py", "b.py"],
    )
    assert evidence.fallback_reason == "error"
    assert evidence.latency_ms >= 0.0


def test_evidence_from_metrics_dict_shapes():
    """Rehydrate evidence from nested carrier, flat metrics, or passthrough object."""
    assert evidence_from_metrics_dict(None).fallback_reason == "none"
    assert evidence_from_metrics_dict("x").fallback_reason == "none"  # type: ignore[arg-type]

    live = empty_scoped_history_evidence(fallback_reason="partial")
    live.split_high_confidence = True
    assert evidence_from_metrics_dict({"scoped_history_evidence": live}) is live

    nested = evidence_from_metrics_dict(
        {
            "scoped_history_evidence": {
                "fallback_reason": "graph_unavailable",
                "split_high_confidence": True,
                "split_rationale": "disjoint",
                "rename_confidence": "HIGH",
                "rename_rationale": "pairs",
                "guidance": "Split evidence: disjoint.",
                "file_to_flow_ids": {"a.py": ["f1", 2]},
                "structural_error_handling": True,
                "structural_public_api": False,
                "structural_new_command": True,
                "latency_ms": 3.5,
            }
        }
    )
    assert nested.fallback_reason == "graph_unavailable"
    assert nested.split_high_confidence is True
    assert nested.rename_confidence == "high"
    assert nested.guidance == "Split evidence: disjoint."
    assert nested.file_to_flow_ids == {"a.py": ["f1", "2"]}
    assert nested.structural_error_handling is True
    assert nested.structural_new_command is True
    assert nested.latency_ms == 3.5

    flat = evidence_from_metrics_dict(
        {
            "scoped_history_fallback_reason": "shadow_unavailable",
            "split_high_confidence": False,
            "rename_confidence": "low",
            "scoped_history_guidance": "Rename evidence: weak.",
            "scoped_history_latency_ms": 1.25,
            "structural_public_api": True,
        }
    )
    assert flat.fallback_reason == "shadow_unavailable"
    assert flat.rename_confidence == "low"
    assert flat.guidance == "Rename evidence: weak."
    assert flat.latency_ms == 1.25
    assert flat.structural_public_api is True


def test_coerce_fallback_reason_lowercases():
    """Closed fallback coercion is case-insensitive (parity with rename bands)."""
    from git_cg.scoped_history import coerce_fallback_reason

    assert coerce_fallback_reason("GRAPH_UNAVAILABLE") == "graph_unavailable"
    assert coerce_fallback_reason("Error") == "error"
    assert coerce_fallback_reason("not-a-reason") == "none"


def test_source_cli_hint_rejects_client_substring():
    """Boundary-anchored CLI hints must not match client/commandeer/prose substrings."""
    from git_cg.scoped_history import _source_has_cli_hint

    assert _source_has_cli_hint(b"from myclient import Client\n") is False
    assert _source_has_cli_hint(b"def commandeer():\n    pass\n") is False
    assert _source_has_cli_hint(b"cli_unrelated = 1\n") is False
    assert _source_has_cli_hint(b"# run the command\nfoo()\n") is False
    assert _source_has_cli_hint(b"command = 'build'\n") is False
    assert _source_has_cli_hint(b"import typer\n@app.command()\ndef run():\n    pass\n") is True
    assert _source_has_cli_hint(b"parser.add_argument('--x')\n") is True
    assert _source_has_cli_hint(b"import click\n@click.command()\ndef run():\n    pass\n") is True


def test_structural_public_api_skips_private_only_defs():
    """Private-only helpers must not set structural_public_api when names recover."""
    from types import SimpleNamespace

    from git_cg.scoped_history import evaluate_structural_markers

    class _Name:
        def __init__(self, text: bytes):
            self.text = text

    class _Node:
        def __init__(self, type_: str, name: bytes | None = None, children=None):
            self.type = type_
            self._name = name
            self.children = children or []

        def child_by_field_name(self, field: str):
            if field == "name" and self._name is not None:
                return _Name(self._name)
            return None

    private_tree = SimpleNamespace(root_node=_Node("function_definition", name=b"_load", children=[]))
    public_tree = SimpleNamespace(root_node=_Node("function_definition", name=b"load", children=[]))

    _err, pub, _cmd = evaluate_structural_markers(
        [SimpleNamespace(tree=private_tree, status="ok", path="priv.py", source=b"def _load():\n    pass\n")],
        enable_semantic=True,
    )
    assert pub is False

    _err, pub, _cmd = evaluate_structural_markers(
        [SimpleNamespace(tree=public_tree, status="ok", path="pub.py", source=b"def load():\n    pass\n")],
        enable_semantic=True,
    )
    assert pub is True

    # Grammar without a "name" field: fall back to the identifier child.
    class _PlainNode:
        def __init__(self, type_: str, children=None):
            self.type = type_
            self.children = children or []

    ident = _PlainNode("identifier")
    ident.text = b"_helper"
    no_field_tree = SimpleNamespace(root_node=_PlainNode("function_definition", children=[ident]))

    _err, pub, _cmd = evaluate_structural_markers(
        [SimpleNamespace(tree=no_field_tree, status="ok", path="nf.py", source=b"")],
        enable_semantic=True,
    )
    assert pub is False

    pub_ident = _PlainNode("identifier")
    pub_ident.text = b"load"
    no_field_public = SimpleNamespace(root_node=_PlainNode("function_definition", children=[pub_ident]))
    _err, pub, _cmd = evaluate_structural_markers(
        [SimpleNamespace(tree=no_field_public, status="ok", path="nf_pub.py", source=b"")],
        enable_semantic=True,
    )
    assert pub is True
