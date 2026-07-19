"""Tests for semantic dark-launch flag resolution."""

from git_cg.semantic_flags import is_semantic_enabled


def test_semantic_flag_default_false(monkeypatch):
    monkeypatch.delenv("GIT_CG_ENABLE_SEMANTIC", raising=False)
    assert is_semantic_enabled() is False


def test_semantic_flag_env_true(monkeypatch):
    monkeypatch.setenv("GIT_CG_ENABLE_SEMANTIC", "true")
    assert is_semantic_enabled() is True
    monkeypatch.setenv("GIT_CG_ENABLE_SEMANTIC", "1")
    assert is_semantic_enabled() is True
    monkeypatch.setenv("GIT_CG_ENABLE_SEMANTIC", "YES")
    assert is_semantic_enabled() is True


def test_semantic_flag_env_falsey(monkeypatch):
    monkeypatch.setenv("GIT_CG_ENABLE_SEMANTIC", "0")
    assert is_semantic_enabled() is False
    monkeypatch.setenv("GIT_CG_ENABLE_SEMANTIC", "false")
    assert is_semantic_enabled() is False


def test_semantic_flag_explicit_overrides_env(monkeypatch):
    monkeypatch.setenv("GIT_CG_ENABLE_SEMANTIC", "1")
    assert is_semantic_enabled(False) is False
    monkeypatch.setenv("GIT_CG_ENABLE_SEMANTIC", "0")
    assert is_semantic_enabled(True) is True
