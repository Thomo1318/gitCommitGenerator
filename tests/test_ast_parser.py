"""Tests for Phase 1 tree-sitter registry and parse pipeline."""

from git_cg.ast_parser import (
    empty_parser_metrics,
    get_parser_for,
    is_probably_binary,
    language_for_path,
    parse_files,
    parse_source,
)


def test_language_for_path_known_and_unknown():
    assert language_for_path("src/foo.py") == "python"
    assert language_for_path("app.ts") == "typescript"
    assert language_for_path("README.unknownext") is None


def test_get_parser_for_python_cached():
    p1 = get_parser_for("python")
    p2 = get_parser_for("python")
    assert p1 is p2


def test_parse_source_success_python():
    src = b"def foo(x):\n    return x + 1\n"
    result = parse_source("pkg/mod.py", src)
    assert result.status == "success"
    assert result.language == "python"
    assert result.root_type == "module"
    assert result.error is None
    assert result.latency_ms >= 0.0
    assert result.source_sha16


def test_parse_source_unsupported_extension():
    result = parse_source("notes.notalang", b"hello world\n")
    assert result.status == "unsupported"
    assert result.language is None
    assert result.error


def test_parse_source_binary_nul_bytes():
    result = parse_source("blob.bin", b"\x00\x01\x02\x03" + b"abc")
    assert result.status == "binary"


def test_is_probably_binary_image_mime():
    assert is_probably_binary("photo.png") is True
    assert is_probably_binary("main.py", b"print(1)\n") is False


def test_parse_files_metrics_aggregate():
    files = {
        "a.py": b"def a():\n    return 1\n",
        "b.unknown": b"???",
        "c.bin": b"\x00\x00\x00",
    }
    batch = parse_files(files)
    metrics = batch.metrics.to_dict()

    assert metrics["semantic_parser_enabled"] is True
    assert metrics["semantic_files_total"] == 3
    assert metrics["semantic_files_parsed"] == 1
    assert metrics["semantic_files_unsupported"] == 1
    assert metrics["semantic_files_binary"] == 1
    assert metrics["semantic_files_failed"] == 0
    assert "python" in metrics["semantic_languages_requested"]
    assert "python" in metrics["semantic_languages_parsed"]
    assert metrics["parser_latency_ms"] >= 0.0
    assert metrics["semantic_summary_hash"]
    assert metrics["semantic_summary_chars"] > 0
    assert any(r.startswith("unsupported:") for r in metrics["semantic_fallback_reasons"])
    assert any(r.startswith("binary:") for r in metrics["semantic_fallback_reasons"])


def test_parse_files_never_raises_on_bad_language(monkeypatch):
    from git_cg import ast_parser

    def boom(_language: str):
        raise RuntimeError("grammar missing")

    monkeypatch.setattr(ast_parser, "get_parser_for", boom)
    batch = parse_files({"x.py": b"def x():\n    pass\n"})
    assert batch.results[0].status == "failed"
    assert batch.metrics.semantic_files_failed == 1
    assert batch.metrics.semantic_files_parsed == 0


def test_empty_parser_metrics_disabled():
    metrics = empty_parser_metrics(enabled=False)
    assert metrics["semantic_parser_enabled"] is False
    assert metrics["semantic_parser_mode"] == "disabled"
    assert metrics["semantic_files_total"] == 0
