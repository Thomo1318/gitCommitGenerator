"""Tests for three-fingerprint algebra (Issue #160)."""

from git_cg.fingerprints import (
    FingerprintClass,
    classify_fingerprint_equality,
    collect_fingerprints_from_source,
    compare_file_fingerprints,
    compare_fingerprint_sets,
    empty_fingerprint_metrics,
)


def _py(src: str) -> bytes:
    """Encode Python source text as UTF-8 bytes.
    
    Parameters:
    	src (str): Python source text to encode.
    
    Returns:
    	bytes: The UTF-8 encoded source text.
    """
    return src.encode("utf-8")


def test_collect_fingerprints_idempotent():
    src = _py("def foo(x):\n    return x + 1\n")
    a, lang_a, err_a = collect_fingerprints_from_source("m.py", src)
    b, _lang_b, err_b = collect_fingerprints_from_source("m.py", src)
    assert err_a is None and err_b is None
    assert lang_a == "python"
    assert a is not None and b is not None
    assert a == b


def test_comment_only_preserves_code_fp():
    base = _py("def foo(x):\n    return x + 1\n")
    staged = _py("def foo(x):\n    # note\n    return x + 1\n")
    result = compare_file_fingerprints("m.py", baseline_source=base, staged_source=staged)
    assert result.classification == FingerprintClass.COMMENTS_ONLY
    assert "comments_only" in result.markers
    assert result.baseline_fps is not None and result.staged_fps is not None
    assert result.baseline_fps.shape_fp == result.staged_fps.shape_fp
    assert result.baseline_fps.code_fp == result.staged_fps.code_fp
    assert result.baseline_fps.text_fp != result.staged_fps.text_fp


def test_identifier_rename_preserves_shape_changes_code():
    base = _py("def foo(x):\n    return x + 1\n")
    staged = _py("def bar(x):\n    return x + 1\n")
    result = compare_file_fingerprints("m.py", baseline_source=base, staged_source=staged)
    assert result.classification in {
        FingerprintClass.IDENTIFIER_OR_LITERAL_ONLY,
        FingerprintClass.FORMATTING_ONLY,
    }
    assert result.baseline_fps is not None and result.staged_fps is not None
    assert result.baseline_fps.shape_fp == result.staged_fps.shape_fp
    assert result.baseline_fps.code_fp != result.staged_fps.code_fp


def test_structural_change_differs_shape():
    base = _py("def foo(x):\n    return x + 1\n")
    staged = _py("def foo(x):\n    if x:\n        return x + 1\n    return 0\n")
    result = compare_file_fingerprints("m.py", baseline_source=base, staged_source=staged)
    assert result.classification == FingerprintClass.STRUCTURAL
    assert result.baseline_fps is not None and result.staged_fps is not None
    assert result.baseline_fps.shape_fp != result.staged_fps.shape_fp


def test_noop_equal_sources():
    src = _py("def foo(x):\n    return x + 1\n")
    result = compare_file_fingerprints("m.py", baseline_source=src, staged_source=src)
    assert result.classification == FingerprintClass.NOOP
    assert result.markers == ()


def test_add_only_and_delete_only():
    src = _py("def foo():\n    return 1\n")
    add = compare_file_fingerprints("new.py", baseline_source=None, staged_source=src)
    delete = compare_file_fingerprints("old.py", baseline_source=src, staged_source=None)
    assert add.classification == FingerprintClass.ADD_ONLY
    assert "files_added" in add.markers
    assert delete.classification == FingerprintClass.DELETE_ONLY
    assert "files_deleted" in delete.markers


def test_unparsed_unsupported_extension():
    result = compare_file_fingerprints(
        "notes.notalang",
        baseline_source=b"hello\n",
        staged_source=b"hello world\n",
    )
    assert result.classification == FingerprintClass.UNPARSED


def test_truth_table_anomaly_shape_eq_code_ne_text_eq():
    classification, markers = classify_fingerprint_equality(shape_eq=True, code_eq=False, text_eq=True, similarity=0.5)
    assert classification == FingerprintClass.INCONSISTENT
    assert "fingerprint_inconsistent" in markers


def test_truth_table_formatting_gate():
    classification, markers = classify_fingerprint_equality(
        shape_eq=True, code_eq=False, text_eq=False, similarity=0.95
    )
    assert classification == FingerprintClass.FORMATTING_ONLY
    assert "formatting_only" in markers


def test_compare_fingerprint_sets_metrics():
    base = {
        "a.py": _py("def a():\n    return 1\n"),
        "gone.py": _py("def g():\n    return 0\n"),
    }
    staged = {
        "a.py": _py("def a():\n    # c\n    return 1\n"),
        "new.py": _py("def n():\n    return 2\n"),
    }
    batch = compare_fingerprint_sets(baseline_files=base, staged_files=staged)
    metrics = batch.metrics.to_dict()
    assert metrics["fingerprint_files_compared"] >= 1
    assert metrics["fingerprint_latency_ms"] >= 0.0
    assert metrics["grammar_version"]
    assert "comments_only" in metrics["class_counts"] or any(
        r.classification == FingerprintClass.COMMENTS_ONLY for r in batch.results
    )
    assert any(r.classification == FingerprintClass.ADD_ONLY for r in batch.results)
    assert any(r.classification == FingerprintClass.DELETE_ONLY for r in batch.results)
    # body similarity present for non-noop paired compares
    assert metrics["body_similarity_min"] is not None
    assert metrics["body_similarity_avg"] is not None


def test_empty_fingerprint_metrics():
    metrics = empty_fingerprint_metrics()
    assert metrics["fingerprint_files_compared"] == 0
    assert metrics["body_similarity_min"] is None
    assert metrics["grammar_version"]


def test_node_overflow_skips_hash_equality():
    """Oversized trees must not classify via content-independent overflow hashes."""
    src_a = _py("def a():\n    return 1\n")
    src_b = _py("def b():\n    return 2\n")
    # Force overflow on both sides with a tiny node budget.
    result = compare_file_fingerprints(
        "m.py",
        baseline_source=src_a,
        staged_source=src_b,
        max_nodes=1,
    )
    assert result.classification == FingerprintClass.SKIPPED
    assert result.reason == "node_overflow"
    assert result.baseline_fps is not None and result.staged_fps is not None
    assert result.baseline_fps.overflowed is True
    assert result.staged_fps.overflowed is True
