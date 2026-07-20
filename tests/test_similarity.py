"""Tests for minimal body-similarity helper (Issue #160)."""

from git_cg.similarity import FORMATTING_BODY_SIMILARITY_THRESHOLD, body_similarity


def test_body_similarity_identical_is_one():
    src = b"def foo(x):\n    return x + 1\n"
    assert body_similarity(src, src) == 1.0


def test_body_similarity_accepts_str_and_bytes():
    assert body_similarity("hello world", b"hello world") == 1.0


def test_body_similarity_divergent_is_lower():
    a = b"def foo(x):\n    return x + 1\n"
    b = b"class Bar:\n    def run(self):\n        print('nope')\n"
    assert body_similarity(a, b) < 0.9


def test_formatting_threshold_constant():
    assert FORMATTING_BODY_SIMILARITY_THRESHOLD == 0.9
