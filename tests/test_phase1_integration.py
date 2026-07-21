"""Integration tests for Phase 1 semantic producers on staged content."""

import os
import subprocess
import tempfile

import pytest

from git_cg.ast_parser import parse_files
from git_cg.fingerprints import compare_fingerprint_sets
from git_cg.git_index import read_head_sources, read_staged_sources
from git_cg.semantic_flags import is_semantic_enabled


@pytest.fixture
def staged_python_repo():
    with tempfile.TemporaryDirectory() as temp_dir:
        subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=temp_dir, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=temp_dir, check=True)

        path = os.path.join(temp_dir, "sample.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write("def sample(x):\n    return x + 1\n")
        subprocess.run(["git", "add", "sample.py"], cwd=temp_dir, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=temp_dir, check=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write("def sample(x):\n    return x + 2\n")
        subprocess.run(["git", "add", "sample.py"], cwd=temp_dir, check=True)
        yield temp_dir


def test_staged_parse_pipeline_produces_parser_metrics(staged_python_repo):
    staged = read_staged_sources(staged_python_repo)
    assert "sample.py" in staged.files
    batch = parse_files(staged.files)
    metrics = batch.metrics.to_dict()
    assert metrics["semantic_files_parsed"] >= 1
    assert metrics["parser_latency_ms"] >= 0.0
    assert "python" in metrics["semantic_languages_parsed"]
    assert metrics["semantic_summary_hash"]


def test_write_telemetry_state_safe_records_phase1_metrics(tmp_path, monkeypatch, staged_python_repo):
    """Exercise _write_telemetry_state_safe with Phase 1 fields populated."""
    import git_cg.main as main_mod
    import git_cg.telemetry as telemetry_mod
    from git_cg.ast_parser import parse_files
    from git_cg.git_index import read_staged_sources
    from git_cg.models import CommitIntent, CommitPlan, CommitType, SemVerImpact
    from git_cg.telemetry import read_telemetry_state

    monkeypatch.setattr(telemetry_mod, "redact_payload", lambda payload: payload)
    monkeypatch.chdir(staged_python_repo)

    staged = read_staged_sources(staged_python_repo)
    batch = parse_files(staged.files)
    metrics = batch.metrics.to_dict()

    plan = CommitPlan(
        primary_intent=CommitIntent(
            intent_id="feature_addition",
            gitmoji="✨",
            cc_type=CommitType.FEAT,
            scope="core",
            description="phase1 metrics",
            semver_impact=SemVerImpact.MINOR,
            changelog_group="Added",
        ),
        rationale="test",
        body_summary="test body",
    )
    review_state = main_mod.ReviewState(commit_plan=plan)

    # Avoid real git-dir discovery surprises: point write at tmp via monkeypatch of check_output
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    monkeypatch.setattr(
        main_mod.subprocess,
        "check_output",
        lambda *a, **k: str(git_dir).encode() if isinstance(a[0], list) and "git-dir" in a[0] else b".",
    )

    # Actually check_output is used with text=True in function - handle both
    def fake_check_output(cmd, *args, **kwargs):
        if isinstance(cmd, list) and "--git-dir" in cmd:
            return str(git_dir) if kwargs.get("text") else str(git_dir).encode()
        return "." if kwargs.get("text") else b"."

    monkeypatch.setattr(main_mod.subprocess, "check_output", fake_check_output)
    main_mod.LAST_OPIK_TRACE_ID = "trace-phase1"

    main_mod._write_telemetry_state_safe(
        review_state=review_state,
        diff_output="diff --git a/sample.py b/sample.py\n",
        engine="mtplx",
        model_name="test-model",
        system_prompt="sys",
        repo_name="repo",
        thread_id="thread-1",
        verbose=False,
        graph_schema_version="unknown",
        semantic_enabled=True,
        parser_latency_ms=float(metrics["parser_latency_ms"]),
        graph_build_latency_ms=0.0,
        graph_query_latency_ms=1.5,
        semantic_parser_metrics=metrics,
    )

    loaded = read_telemetry_state(str(git_dir))
    assert loaded is not None
    assert loaded.semantic_enabled is True
    assert loaded.parser_latency_ms == float(metrics["parser_latency_ms"])
    assert loaded.graph_query_latency_ms == 1.5
    assert loaded.semantic_parser_metrics is not None
    assert loaded.semantic_parser_metrics["semantic_files_parsed"] >= 1


def test_flag_off_default(monkeypatch):
    monkeypatch.delenv("GIT_CG_ENABLE_SEMANTIC", raising=False)
    assert is_semantic_enabled() is False


def test_semantic_producers_not_invoked_when_flag_off(monkeypatch):
    """Dark-launch contract: flag off must not call staged parse / graph producers."""
    from git_cg.semantic_flags import is_semantic_enabled

    monkeypatch.delenv("GIT_CG_ENABLE_SEMANTIC", raising=False)
    assert is_semantic_enabled(None) is False
    assert is_semantic_enabled(False) is False

    calls: list[str] = []

    def track(name):
        def _fn(*args, **kwargs):
            calls.append(name)
            raise AssertionError(f"{name} should not be called when semantic is disabled")

        return _fn

    monkeypatch.setattr("git_cg.git_index.read_staged_sources", track("read_staged_sources"))
    monkeypatch.setattr("git_cg.ast_parser.parse_files", track("parse_files"))
    monkeypatch.setattr("git_cg.graph_context.graph_stats", track("graph_stats"))
    monkeypatch.setattr("git_cg.graph_context.refresh_graph", track("refresh_graph"))

    # Reproduce the flag-gated producer block from _run_commit_generation without full CLI.
    enable_semantic = False
    semantic_enabled = is_semantic_enabled(enable_semantic)
    if semantic_enabled:
        from git_cg.ast_parser import parse_files
        from git_cg.git_index import read_staged_sources
        from git_cg.graph_context import graph_stats, refresh_graph

        read_staged_sources(".")
        parse_files({})
        graph_stats(repo_root=".")
        refresh_graph(repo_root=".")

    assert calls == []


def test_head_index_fingerprint_pipeline_on_staged_repo(staged_python_repo):
    """Phase 2: staged vs HEAD compare yields fingerprint metrics."""
    staged = read_staged_sources(staged_python_repo)
    head = read_head_sources(staged_python_repo, paths=list(staged.files.keys()))
    assert "sample.py" in staged.files
    assert "sample.py" in head.files
    batch = compare_fingerprint_sets(baseline_files=head.files, staged_files=staged.files)
    metrics = batch.metrics.to_dict()
    assert metrics["fingerprint_files_compared"] >= 1
    assert metrics["fingerprint_latency_ms"] >= 0.0
    assert metrics["grammar_version"]
    # sample.py body changed (return x+1 -> x+2) so similarity should be present
    assert metrics["body_similarity_min"] is not None
    assert metrics["body_similarity_avg"] is not None
    assert any(r.path == "sample.py" for r in batch.results)


def test_collect_semantic_producer_metrics_flag_off_skips_io(monkeypatch, staged_python_repo):
    import git_cg.main as main_mod

    monkeypatch.delenv("GIT_CG_ENABLE_SEMANTIC", raising=False)
    calls: list[str] = []

    def track(name):
        def _fn(*args, **kwargs):
            calls.append(name)
            raise AssertionError(f"{name} should not run when semantic disabled")

        return _fn

    monkeypatch.setattr("git_cg.git_index.read_staged_sources", track("read_staged_sources"))
    monkeypatch.setattr("git_cg.git_index.read_head_sources", track("read_head_sources"))
    monkeypatch.setattr("git_cg.ast_parser.parse_files", track("parse_files"))
    monkeypatch.setattr("git_cg.fingerprints.compare_fingerprint_sets", track("compare_fingerprint_sets"))
    monkeypatch.setattr("git_cg.graph_context.graph_stats", track("graph_stats"))

    out = main_mod._collect_semantic_producer_metrics(staged_python_repo, enable_semantic=False)
    assert out["semantic_enabled"] is False
    assert out["fingerprint_files_compared"] == 0
    assert out["body_similarity_min"] is None
    assert calls == []


def test_collect_semantic_producer_metrics_flag_on_records_fingerprints(monkeypatch, staged_python_repo):
    import git_cg.main as main_mod

    # Avoid optional graph refresh side effects; keep graph_stats lightweight via real call or mock.
    monkeypatch.setenv("GIT_CG_ENABLE_SEMANTIC", "1")
    monkeypatch.delenv("GIT_CG_SEMANTIC_REFRESH_GRAPH", raising=False)

    # Mock graph boundary so test stays offline/deterministic.
    from git_cg.graph_context import GraphOperationResult, GraphOutcome

    def fake_stats(*, repo_root=None, **kwargs):
        return GraphOperationResult(
            ok=True,
            operation="stats",
            outcome=GraphOutcome.OK,
            data={"schema_version": "test-schema"},
            latency_ms=1.0,
        )

    monkeypatch.setattr("git_cg.graph_context.graph_stats", fake_stats)
    monkeypatch.setattr(
        "git_cg.graph_context.collect_graph_telemetry",
        lambda **kwargs: {"graph_build_latency_ms": 0.0, "graph_query_latency_ms": 1.0},
    )

    out = main_mod._collect_semantic_producer_metrics(staged_python_repo, enable_semantic=True)
    assert out["semantic_enabled"] is True
    assert out["fingerprint_files_compared"] >= 1
    assert out["body_similarity_min"] is not None
    assert out["body_similarity_avg"] is not None
    assert isinstance(out["fingerprint_class_counts"], dict)
    assert out["fingerprint_grammar_version"] not in ("", None)
    assert out["semantic_parser_metrics"] is not None
    assert out["semantic_parser_metrics"].get("semantic_files_parsed", 0) >= 1
    assert out["crg_schema_version"] == "test-schema"


def test_write_telemetry_state_safe_records_phase2_fingerprint_fields(tmp_path, monkeypatch, staged_python_repo):
    import git_cg.main as main_mod
    import git_cg.telemetry as telemetry_mod
    from git_cg.models import CommitIntent, CommitPlan, CommitType, SemVerImpact
    from git_cg.telemetry import read_telemetry_state

    monkeypatch.setattr(telemetry_mod, "redact_payload", lambda payload: payload)
    monkeypatch.chdir(staged_python_repo)

    plan = CommitPlan(
        primary_intent=CommitIntent(
            intent_id="feature_addition",
            gitmoji="✨",
            cc_type=CommitType.FEAT,
            scope="core",
            description="phase2 metrics",
            semver_impact=SemVerImpact.MINOR,
            changelog_group="Added",
        ),
        rationale="test",
        body_summary="test body",
    )
    review_state = main_mod.ReviewState(commit_plan=plan)
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    def fake_check_output(cmd, *args, **kwargs):
        if isinstance(cmd, list) and "--git-dir" in cmd:
            return str(git_dir) if kwargs.get("text") else str(git_dir).encode()
        return "." if kwargs.get("text") else b"."

    monkeypatch.setattr(main_mod.subprocess, "check_output", fake_check_output)
    main_mod.LAST_OPIK_TRACE_ID = "trace-phase2"

    main_mod._write_telemetry_state_safe(
        review_state=review_state,
        diff_output="diff --git a/sample.py b/sample.py\n",
        engine="mtplx",
        model_name="test-model",
        system_prompt="sys",
        repo_name="repo",
        thread_id="thread-1",
        verbose=False,
        graph_schema_version="unknown",
        semantic_enabled=True,
        parser_latency_ms=1.0,
        graph_build_latency_ms=0.0,
        graph_query_latency_ms=1.5,
        semantic_parser_metrics={"semantic_parser_mode": "tree-sitter", "semantic_files_parsed": 1},
        body_similarity_min=0.8,
        body_similarity_avg=0.85,
        fingerprint_files_compared=2,
        fingerprint_latency_ms=3.25,
        fingerprint_class_counts={"structural": 1, "comments_only": 1},
        fingerprint_grammar_version="tree-sitter-language-pack==test",
        fingerprint_markers=["runtime_logic_changed"],
    )

    loaded = read_telemetry_state(str(git_dir))
    assert loaded is not None
    assert loaded.body_similarity_min == 0.8
    assert loaded.body_similarity_avg == 0.85
    assert loaded.fingerprint_files_compared == 2
    assert loaded.fingerprint_latency_ms == 3.25
    assert loaded.fingerprint_class_counts == {"structural": 1, "comments_only": 1}
    assert loaded.fingerprint_grammar_version == "tree-sitter-language-pack==test"
    assert loaded.fingerprint_markers == ["runtime_logic_changed"]
