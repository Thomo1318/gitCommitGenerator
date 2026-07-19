"""Tests for staged-index blob readers (Phase 1)."""

import os
import subprocess
import tempfile

import pytest

from git_cg.git_index import (
    list_staged_paths,
    read_staged_blob,
    read_staged_sources,
    should_refresh_graph,
)


@pytest.fixture
def staged_repo():
    with tempfile.TemporaryDirectory() as temp_dir:
        subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=temp_dir, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=temp_dir, check=True)

        tracked = os.path.join(temp_dir, "tracked.py")
        with open(tracked, "w", encoding="utf-8") as f:
            f.write("def old():\n    return 0\n")
        subprocess.run(["git", "add", "tracked.py"], cwd=temp_dir, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=temp_dir, check=True)

        # Staged modification + new staged file + lockfile noise + unstaged-only file
        with open(tracked, "w", encoding="utf-8") as f:
            f.write("def new():\n    return 1\n")
        subprocess.run(["git", "add", "tracked.py"], cwd=temp_dir, check=True)

        new_py = os.path.join(temp_dir, "fresh.py")
        with open(new_py, "w", encoding="utf-8") as f:
            f.write("def fresh():\n    return 2\n")
        subprocess.run(["git", "add", "fresh.py"], cwd=temp_dir, check=True)

        lock = os.path.join(temp_dir, "uv.lock")
        with open(lock, "w", encoding="utf-8") as f:
            f.write("lock\n")
        subprocess.run(["git", "add", "uv.lock"], cwd=temp_dir, check=True)

        unstaged = os.path.join(temp_dir, "unstaged_only.py")
        with open(unstaged, "w", encoding="utf-8") as f:
            f.write("def no():\n    return 3\n")

        yield temp_dir


def test_list_staged_paths_excludes_lock_and_unstaged(staged_repo):
    paths = set(list_staged_paths(staged_repo))
    assert "tracked.py" in paths
    assert "fresh.py" in paths
    assert "uv.lock" not in paths
    assert "unstaged_only.py" not in paths


def test_read_staged_blob_returns_index_content(staged_repo):
    data = read_staged_blob("tracked.py", repo_root=staged_repo)
    assert b"def new()" in data
    assert b"def old()" not in data


def test_read_staged_sources_batch(staged_repo):
    result = read_staged_sources(staged_repo)
    assert result.ok
    assert "tracked.py" in result.files
    assert "fresh.py" in result.files
    assert b"def fresh()" in result.files["fresh.py"]
    assert "uv.lock" not in result.files


def test_read_staged_sources_oversize_skip(staged_repo):
    result = read_staged_sources(staged_repo, max_file_bytes=5)
    assert result.files == {}
    assert any("oversize" in s for s in result.skipped)


def test_should_refresh_graph_env(monkeypatch):
    monkeypatch.delenv("GIT_CG_SEMANTIC_REFRESH_GRAPH", raising=False)
    assert should_refresh_graph() is False
    monkeypatch.setenv("GIT_CG_SEMANTIC_REFRESH_GRAPH", "1")
    assert should_refresh_graph() is True
