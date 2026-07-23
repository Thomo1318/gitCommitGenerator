"""Tests for three-fingerprint algebra (Issue #160)."""

import pytest

from git_cg.fingerprints import (
    FingerprintClass,
    classify_fingerprint_equality,
    collect_fingerprints_from_source,
    compare_file_fingerprints,
    compare_fingerprint_sets,
    empty_fingerprint_metrics,
    grammar_version,
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


def test_file_fingerprint_result_to_dict_includes_nested_fps():
    src = _py("def foo():\n    return 1\n")
    result = compare_file_fingerprints("m.py", baseline_source=src, staged_source=src)
    payload = result.to_dict()
    assert payload["classification"] == "noop"
    assert payload["baseline_fps"] is not None
    assert "shape_fp" in payload["baseline_fps"]
    assert payload["baseline_fps"].get("overflowed") is False


def test_batch_to_dict_and_empty_metrics():
    batch = compare_fingerprint_sets(baseline_files={}, staged_files={})
    payload = batch.to_dict()
    assert "results" in payload and "metrics" in payload
    empty = empty_fingerprint_metrics()
    assert empty["fingerprint_files_compared"] == 0
    assert empty["body_similarity_min"] is None


def test_both_missing_skipped():
    result = compare_file_fingerprints("x.py", baseline_source=None, staged_source=None)
    assert result.classification == FingerprintClass.SKIPPED
    assert result.reason == "both_missing"


def test_identifier_only_without_similarity_metric():
    classification, markers = classify_fingerprint_equality(
        shape_eq=True, code_eq=False, text_eq=False, similarity=None
    )
    assert classification == FingerprintClass.IDENTIFIER_OR_LITERAL_ONLY
    assert "identifier_or_literal_only" in markers


def test_inconsistent_shape_ne_code_eq():
    classification, markers = classify_fingerprint_equality(shape_eq=False, code_eq=True, text_eq=False, similarity=0.1)
    assert classification == FingerprintClass.INCONSISTENT
    assert "fingerprint_inconsistent" in markers


def test_collect_fingerprints_from_source_tree_unavailable(monkeypatch):
    from git_cg import fingerprints as fp_mod
    from git_cg.ast_parser import ParseResult, ParseStatus

    def fake_parse(path, source, language=None):
        return ParseResult(
            path=path,
            language="python",
            status=ParseStatus.SUCCESS,
            root_type="module",
            tree=None,
        )

    monkeypatch.setattr(fp_mod, "parse_source", fake_parse)
    triple, lang, err = fp_mod.collect_fingerprints_from_source("m.py", b"def x():\n    return 1\n")
    assert triple is None
    assert lang == "python"
    assert err == "parse tree unavailable"


def test_grammar_version_uses_package_metadata(monkeypatch: pytest.MonkeyPatch):
    """grammar_version must use package metadata when module attrs are absent."""
    import importlib.metadata as md

    import tree_sitter_language_pack as tslp

    # Disable module-level version attributes so metadata path is exercised.
    monkeypatch.setattr(tslp, "__version__", None, raising=False)
    if hasattr(tslp, "VERSION"):
        monkeypatch.setattr(tslp, "VERSION", None, raising=False)

    expected = "9.9.9-test"

    def _fake_version(name: str) -> str:
        assert name == "tree-sitter-language-pack"
        return expected

    monkeypatch.setattr(md, "version", _fake_version)

    value = grammar_version()
    assert value == f"tree-sitter-language-pack=={expected}", value
    assert "@" not in value


def test_fingerprint_relational_invariants_multi_language():
    """Relational fingerprint invariants hold across a small multi-language set."""
    cases = {
        "a.py": (
            b"def foo(x):\n    return x + 1\n",
            b"def foo(x):\n    # note\n    return x + 1\n",
            FingerprintClass.COMMENTS_ONLY,
        ),
        "a.js": (
            b"function foo(x) { return x + 1 }\n",
            b"function foo(x) { /* note */ return x + 1 }\n",
            None,
        ),
        "a.go": (
            b"package main\nfunc foo(x int) int { return x + 1 }\n",
            b"package main\n// note\nfunc foo(x int) int { return x + 1 }\n",
            None,
        ),
    }
    for path, (base, staged, expected) in cases.items():
        result = compare_file_fingerprints(path, baseline_source=base, staged_source=staged)
        assert result.baseline_fps is not None and result.staged_fps is not None
        base_fp = result.baseline_fps
        staged_fp = result.staged_fps
        assert base_fp.shape_fp and staged_fp.shape_fp
        assert base_fp.code_fp and staged_fp.code_fp
        assert base_fp.text_fp and staged_fp.text_fp
        assert result.classification in set(FingerprintClass)

        if expected is not None:
            assert result.classification == expected
            assert base_fp.shape_fp == staged_fp.shape_fp
            assert base_fp.code_fp == staged_fp.code_fp
            assert base_fp.text_fp != staged_fp.text_fp
            continue

        # JS/Go comment edits: allow grammar-dependent classification, but require
        # a coherent relationship among the three fingerprints.
        if base_fp.text_fp == staged_fp.text_fp:
            # Byte-identical after normalisation — all three should match.
            assert base_fp.shape_fp == staged_fp.shape_fp
            assert base_fp.code_fp == staged_fp.code_fp
            assert result.classification == FingerprintClass.NOOP
        else:
            # Text changed. Prefer comments/formatting-only when shape holds;
            # otherwise accept structural/inconsistent only if code or shape moved.
            if base_fp.shape_fp == staged_fp.shape_fp:
                assert result.classification in {
                    FingerprintClass.COMMENTS_ONLY,
                    FingerprintClass.FORMATTING_ONLY,
                    FingerprintClass.IDENTIFIER_OR_LITERAL_ONLY,
                    FingerprintClass.NOOP,
                }
                if result.classification == FingerprintClass.COMMENTS_ONLY:
                    assert base_fp.code_fp == staged_fp.code_fp
                if result.classification == FingerprintClass.IDENTIFIER_OR_LITERAL_ONLY:
                    assert base_fp.code_fp != staged_fp.code_fp
            else:
                assert result.classification in {
                    FingerprintClass.STRUCTURAL,
                    FingerprintClass.INCONSISTENT,
                }
                assert base_fp.shape_fp != staged_fp.shape_fp or base_fp.code_fp != staged_fp.code_fp


def test_grammar_version_prefers_dunder_version_attribute(monkeypatch):
    """When `__version__` is set, it must be used directly without touching importlib.metadata."""
    from git_cg import fingerprints as fp_mod

    monkeypatch.setattr(fp_mod.tslp, "__version__", "9.9.9", raising=False)

    def boom(_name: str) -> str:
        raise AssertionError("importlib.metadata.version must not be called when __version__ is set")

    monkeypatch.setattr("importlib.metadata.version", boom)

    assert fp_mod.grammar_version() == "tree-sitter-language-pack==9.9.9"


def test_grammar_version_falls_back_to_importlib_metadata(monkeypatch):
    """Without `__version__`/`VERSION`, the package metadata version must be used."""
    from git_cg import fingerprints as fp_mod

    monkeypatch.setattr(fp_mod.tslp, "__version__", None, raising=False)
    monkeypatch.setattr(fp_mod.tslp, "VERSION", None, raising=False)
    monkeypatch.setattr("importlib.metadata.version", lambda name: "0.13.5")

    assert fp_mod.grammar_version() == "tree-sitter-language-pack==0.13.5"


def test_grammar_version_falls_back_to_file_path_when_metadata_missing(monkeypatch):
    """If package metadata is unavailable, fall back to the module `__file__` identity."""
    from importlib.metadata import PackageNotFoundError

    from git_cg import fingerprints as fp_mod

    monkeypatch.setattr(fp_mod.tslp, "__version__", None, raising=False)
    monkeypatch.setattr(fp_mod.tslp, "VERSION", None, raising=False)
    monkeypatch.setattr(fp_mod.tslp, "__file__", "/fake/path/tslp/__init__.py", raising=False)

    def not_found(_name: str) -> str:
        raise PackageNotFoundError("tree-sitter-language-pack")

    monkeypatch.setattr("importlib.metadata.version", not_found)

    assert fp_mod.grammar_version() == "tree-sitter-language-pack@/fake/path/tslp/__init__.py"


def test_grammar_version_falls_back_to_file_path_on_unexpected_metadata_error(monkeypatch):
    """Any other importlib.metadata error must also degrade to the file-path fallback, not raise."""
    from git_cg import fingerprints as fp_mod

    monkeypatch.setattr(fp_mod.tslp, "__version__", None, raising=False)
    monkeypatch.setattr(fp_mod.tslp, "VERSION", None, raising=False)
    monkeypatch.setattr(fp_mod.tslp, "__file__", "/fake/path/tslp/__init__.py", raising=False)

    def boom(_name: str) -> str:
        raise RuntimeError("unexpected metadata backend failure")

    monkeypatch.setattr("importlib.metadata.version", boom)

    assert fp_mod.grammar_version() == "tree-sitter-language-pack@/fake/path/tslp/__init__.py"
