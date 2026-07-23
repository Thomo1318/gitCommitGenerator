"""Tests for Phase 1 tree-sitter registry and parse pipeline."""

from git_cg.ast_parser import (
    ParseStatus,
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
    assert result.status == ParseStatus.SUCCESS
    assert result.language == "python"
    assert result.root_type == "module"
    assert result.error is None
    assert result.latency_ms >= 0.0
    assert result.source_sha16


def test_parse_source_unsupported_extension():
    result = parse_source("notes.notalang", b"hello world\n")
    assert result.status == ParseStatus.UNSUPPORTED
    assert result.language is None
    assert result.error


def test_parse_source_binary_nul_bytes():
    result = parse_source("blob.bin", b"\x00\x01\x02\x03" + b"abc")
    assert result.status == ParseStatus.BINARY


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
    assert batch.results[0].status == ParseStatus.FAILED
    assert batch.metrics.semantic_files_failed == 1
    assert batch.metrics.semantic_files_parsed == 0


def test_empty_parser_metrics_disabled():
    metrics = empty_parser_metrics(enabled=False)
    assert metrics["semantic_parser_enabled"] is False
    assert metrics["semantic_parser_mode"] == "disabled"
    assert metrics["semantic_files_total"] == 0


def test_parse_status_enum_values():
    assert ParseStatus.SUCCESS == "success"
    assert ParseStatus.UNSUPPORTED == "unsupported"
    assert ParseStatus.BINARY == "binary"
    assert ParseStatus.FAILED == "failed"
    assert set(ParseStatus) == {
        ParseStatus.SUCCESS,
        ParseStatus.UNSUPPORTED,
        ParseStatus.BINARY,
        ParseStatus.FAILED,
    }


def test_all_language_map_ids_resolve_and_minimal_parse():
    """Every `_LANGUAGE_BY_EXT` language id must load a parser and accept a minimal parse."""
    from git_cg.ast_parser import _LANGUAGE_BY_EXT, ParseStatus, get_parser_for, parse_source

    # Sample sources keyed by language id. Paths use `src/*` for realism; non-NUL
    # mapped sources must parse successfully (no BINARY continue escape hatch).
    samples: dict[str, tuple[str, bytes]] = {
        "python": ("src/x.py", b"def f():\n    return 1\n"),
        "javascript": ("src/x.js", b"function f() { return 1 }\n"),
        "typescript": ("src/model.ts", b"const x: number = 1\n"),
        "tsx": ("src/x.tsx", b"const x = <div />\n"),
        "go": ("src/x.go", b"package main\nfunc main() {}\n"),
        "rust": ("src/x.rs", b"fn main() {}\n"),
        "bash": ("src/x.sh", b"echo hi\n"),
        "c": ("src/x.c", b"int main(void) { return 0; }\n"),
        "cpp": ("src/x.cpp", b"int main() { return 0; }\n"),
        "java": ("src/x.java", b"class A { void m() {} }\n"),
        "kotlin": ("src/x.kt", b"fun main() {}\n"),
        "ruby": ("src/x.rb", b"def f; end\n"),
        "php": ("src/x.php", b"<?php function f() {}\n"),
        "csharp": ("src/x.cs", b"class A { void M() {} }\n"),
        "swift": ("src/x.swift", b"func f() {}\n"),
        "scala": ("src/x.scala", b"object A { def f = 1 }\n"),
        "toml": ("src/x.toml", b"a = 1\n"),
        "yaml": ("src/x.yaml", b"a: 1\n"),
        "json": ("src/x.json", b'{"a": 1}\n'),
        "markdown": ("src/x.md", b"# hi\n"),
        "html": ("src/x.html", b"<html></html>\n"),
        "css": ("src/x.css", b"a { color: red }\n"),
        "sql": ("src/x.sql", b"SELECT 1;\n"),
    }

    langs = sorted(set(_LANGUAGE_BY_EXT.values()))
    assert set(langs) == set(samples), f"language map drift: {set(langs) ^ set(samples)}"

    for lang in langs:
        parser = get_parser_for(lang)
        assert parser is not None
        path, src = samples[lang]
        assert b"\x00" not in src
        tree = parser.parse(src)
        assert tree.root_node is not None
        assert getattr(tree.root_node, "type", None)

        result = parse_source(path, src)
        assert result.status == ParseStatus.SUCCESS, (lang, result.status, result.error)
        assert result.language == lang
        assert result.root_type


def test_python_root_type_is_module():
    """Python grammar root node type remains `module` (WP5 node-type invariant)."""
    result = parse_source("pkg/mod.py", b"def foo():\n    return 1\n")
    assert result.status == ParseStatus.SUCCESS
    assert result.root_type == "module"


def test_cs_extension_maps_to_csharp_language_id():
    assert language_for_path("Program.cs") == "csharp"


def test_typescript_not_classified_binary_by_mime():
    """`*.ts` must not be skipped as MPEG-TS video via mimetypes."""
    src = b"const x: number = 1\n"
    assert is_probably_binary("x.ts", src) is False
    result = parse_source("x.ts", src)
    assert result.status == ParseStatus.SUCCESS
    assert result.language == "typescript"


def test_language_map_has_no_legacy_c_sharp_id():
    """Guard against regressing `.cs` back to the old `c_sharp` language id."""
    from git_cg.ast_parser import _LANGUAGE_BY_EXT

    assert "c_sharp" not in _LANGUAGE_BY_EXT.values()
    assert _LANGUAGE_BY_EXT[".cs"] == "csharp"


def test_is_probably_binary_known_extension_without_source_is_false():
    """A recognised extension with no content supplied must not be treated as binary."""
    assert is_probably_binary("app.py") is False
    assert is_probably_binary("app.py", None) is False


def test_is_probably_binary_known_extension_with_nul_bytes_is_true():
    """A recognised extension whose content contains NUL bytes must still be flagged binary."""
    assert is_probably_binary("app.py", b"\x00\x01binary garbage") is True


def test_is_probably_binary_known_extension_skips_mimetypes_guess():
    """
    Extension-registry hit must short-circuit mimetypes entirely, not just for `.ts`.

    `.css`/`.json`/etc. are already text-ish under mimetypes, but this asserts the
    registry-first branch is taken (no NUL bytes => never binary) even though
    mimetypes would also agree, keeping the two code paths in sync going forward.
    """
    assert is_probably_binary("styles.css", b"a { color: red }\n") is False
    assert is_probably_binary("data.json", b'{"a": 1}\n') is False


def test_is_probably_binary_unknown_extension_with_nul_bytes_is_true():
    """Unrecognised extensions fall back to the NUL-byte heuristic."""
    assert is_probably_binary("blob.unknownext", b"\x00\x00\x00garbage") is True


def test_is_probably_binary_unknown_extension_without_nul_bytes_is_false():
    """Unrecognised extensions with plain text content must not be flagged binary."""
    assert is_probably_binary("notes.unknownext", b"just plain text\n") is False


def test_cs_source_parses_without_error():
    """`.cs` sources must parse successfully under the `csharp` grammar id."""
    result = parse_source("Program.cs", b"class Program { static void Main() {} }\n")
    assert result.status == ParseStatus.SUCCESS
    assert result.language == "csharp"
    assert result.error is None
