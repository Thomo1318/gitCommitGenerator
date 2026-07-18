import os
import subprocess
import tempfile
import unittest.mock as mock

import pytest

from git_cg.shadow_workspace import ShadowWorkspace, shadow_workspace


@pytest.fixture
def mock_repo():
    """Creates a temporary git repository with initial commits, staged, and unstaged changes."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Initialize
        subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=temp_dir, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=temp_dir, check=True)

        # Initial commit
        file1 = os.path.join(temp_dir, "file1.txt")
        file2 = os.path.join(temp_dir, "file2.txt")

        with open(file1, "w") as f:
            f.write("Initial file 1\n")
        with open(file2, "w") as f:
            f.write("Initial file 2\n")

        subprocess.run(["git", "add", "."], cwd=temp_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=temp_dir, check=True)

        # Create a staged change
        with open(file1, "a") as f:
            f.write("Staged change\n")
        subprocess.run(["git", "add", "file1.txt"], cwd=temp_dir, check=True)

        # Create an unstaged change
        with open(file2, "a") as f:
            f.write("Unstaged change\n")

        yield temp_dir


def test_shadow_workspace_isolation(mock_repo):
    """Verifies that commits made in the shadow workspace do not affect the original repo."""
    original_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=mock_repo, capture_output=True, text=True, check=True
    ).stdout.strip()

    with shadow_workspace(mock_repo) as workspace:
        # Make a commit inside the shadow workspace
        workspace.run(["git", "config", "user.name", "Test User"], check=True)
        workspace.run(["git", "config", "user.email", "test@example.com"], check=True)
        workspace.run(["git", "commit", "-m", "Shadow commit"], check=True)
        shadow_head = workspace.run(["git", "rev-parse", "HEAD"], capture_output=True, check=True).stdout.strip()

        assert shadow_head != original_head

        # Verify the commit exists in shadow
        log_output = workspace.run(["git", "log", "--oneline"], capture_output=True).stdout
        assert "Shadow commit" in log_output

    # Outside the context manager, verify original repo is untouched
    current_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=mock_repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert current_head == original_head

    log_output = subprocess.run(["git", "log", "--oneline"], cwd=mock_repo, capture_output=True, text=True).stdout
    assert "Shadow commit" not in log_output


def test_shadow_workspace_sync_state(mock_repo):
    """Verifies that staged and unstaged changes are correctly synced to the shadow workspace."""
    with shadow_workspace(mock_repo) as workspace:
        # Check staged changes
        staged_diff = workspace.run(["git", "diff", "--cached"], capture_output=True).stdout
        assert "Staged change" in staged_diff

        # Check unstaged changes
        unstaged_diff = workspace.run(["git", "diff"], capture_output=True).stdout
        assert "Unstaged change" in unstaged_diff


def test_shadow_workspace_cleanup(mock_repo):
    """Verifies that the temporary directory is cleaned up even if an exception occurs."""
    path = None
    try:
        with shadow_workspace(mock_repo) as workspace:
            path = workspace.path
            assert os.path.exists(path)
            raise ValueError("Test Exception")
    except ValueError:
        pass

    assert path is not None
    assert not os.path.exists(path)


def test_shadow_workspace_git_commands_succeed(mock_repo):
    """Verifies that standard git commands run cleanly in the shadow workspace."""
    with shadow_workspace(mock_repo) as workspace:
        status = workspace.run(["git", "status"], capture_output=True).stdout
        assert "Changes to be committed:" in status
        assert "Changes not staged for commit:" in status


@pytest.fixture
def clean_repo():
    """Creates a temporary git repository with a committed history and no pending changes."""
    with tempfile.TemporaryDirectory() as temp_dir:
        subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=temp_dir, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=temp_dir, check=True)

        file1 = os.path.join(temp_dir, "file1.txt")
        with open(file1, "w") as f:
            f.write("Initial file 1\n")

        subprocess.run(["git", "add", "."], cwd=temp_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=temp_dir, check=True)

        yield temp_dir


# ---------------------------------------------------------------------------
# Path construction / source_dir resolution
# ---------------------------------------------------------------------------


def test_shadow_workspace_path_is_absolute_and_named_repo(mock_repo):
    """The shadow workspace path must be an absolute path pointing to an existing 'repo' directory."""
    with shadow_workspace(mock_repo) as workspace:
        assert os.path.isabs(workspace.path)
        assert os.path.basename(workspace.path) == "repo"
        assert os.path.isdir(workspace.path)


def test_shadow_workspace_source_dir_is_resolved_to_abspath(mock_repo, monkeypatch):
    """source_dir must be normalized to an absolute path even when a relative path is supplied."""
    monkeypatch.chdir(os.path.dirname(mock_repo))
    relative_source = os.path.basename(mock_repo)

    with shadow_workspace(relative_source) as workspace:
        assert workspace.source_dir == os.path.realpath(mock_repo)


def test_shadow_workspace_default_source_dir_uses_cwd(mock_repo, monkeypatch):
    """Calling shadow_workspace() with no arguments must default to the current working directory."""
    monkeypatch.chdir(mock_repo)

    with shadow_workspace() as workspace:
        assert workspace.source_dir == os.path.realpath(mock_repo)
        staged_diff = workspace.run(["git", "diff", "--cached"], capture_output=True).stdout
        assert "Staged change" in staged_diff


def test_multiple_shadow_workspaces_have_unique_temp_dirs(mock_repo):
    """Each ShadowWorkspace instance must get its own isolated temp directory."""
    with shadow_workspace(mock_repo) as ws1, shadow_workspace(mock_repo) as ws2:
        assert ws1.path != ws2.path
        assert os.path.isdir(ws1.path)
        assert os.path.isdir(ws2.path)


def test_shadow_workspace_class_used_directly_as_context_manager(mock_repo):
    """ShadowWorkspace itself must work as a context manager, independent of the shadow_workspace() wrapper."""
    with ShadowWorkspace(mock_repo) as workspace:
        assert isinstance(workspace, ShadowWorkspace)
        assert os.path.isdir(workspace.path)
        result = workspace.run(["git", "rev-parse", "--is-inside-work-tree"], capture_output=True)
        assert result.stdout.strip() == "true"

    assert not os.path.exists(workspace.path)


# ---------------------------------------------------------------------------
# Sync edge cases: no changes, staged-only, unstaged-only, untracked, deletions, binary
# ---------------------------------------------------------------------------


def test_shadow_workspace_no_pending_changes(clean_repo):
    """When there are no staged or unstaged changes, the shadow workspace must be perfectly clean."""
    with shadow_workspace(clean_repo) as workspace:
        status = workspace.run(["git", "status", "--porcelain"], capture_output=True).stdout
        assert status == ""


def test_shadow_workspace_only_staged_changes_synced(clean_repo):
    """Only staged changes (no unstaged) must be synced, leaving the working tree diff empty."""
    file1 = os.path.join(clean_repo, "file1.txt")
    with open(file1, "a") as f:
        f.write("Only staged\n")
    subprocess.run(["git", "add", "file1.txt"], cwd=clean_repo, check=True)

    with shadow_workspace(clean_repo) as workspace:
        staged_diff = workspace.run(["git", "diff", "--cached"], capture_output=True).stdout
        assert "Only staged" in staged_diff

        unstaged_diff = workspace.run(["git", "diff"], capture_output=True).stdout
        assert unstaged_diff == ""


def test_shadow_workspace_only_unstaged_changes_synced(clean_repo):
    """Only unstaged changes (no staged) must be synced, leaving the index diff empty."""
    file1 = os.path.join(clean_repo, "file1.txt")
    with open(file1, "a") as f:
        f.write("Only unstaged\n")

    with shadow_workspace(clean_repo) as workspace:
        staged_diff = workspace.run(["git", "diff", "--cached"], capture_output=True).stdout
        assert staged_diff == ""

        unstaged_diff = workspace.run(["git", "diff"], capture_output=True).stdout
        assert "Only unstaged" in unstaged_diff


def test_shadow_workspace_untracked_files_are_not_synced(clean_repo):
    """Untracked files must not appear in the shadow workspace, since 'git diff' excludes them."""
    untracked = os.path.join(clean_repo, "untracked.txt")
    with open(untracked, "w") as f:
        f.write("This file was never added to git\n")

    with shadow_workspace(clean_repo) as workspace:
        assert not os.path.exists(os.path.join(workspace.path, "untracked.txt"))


def test_shadow_workspace_syncs_staged_file_deletion(clean_repo):
    """A staged file deletion in the source repo must be reflected in the shadow workspace."""
    subprocess.run(["git", "rm", "file1.txt"], cwd=clean_repo, check=True, capture_output=True)

    with shadow_workspace(clean_repo) as workspace:
        assert not os.path.exists(os.path.join(workspace.path, "file1.txt"))
        staged_diff = workspace.run(["git", "diff", "--cached", "--name-status"], capture_output=True).stdout
        assert "D\tfile1.txt" in staged_diff


def test_shadow_workspace_syncs_staged_binary_file(clean_repo):
    """A newly staged binary file must be synced with identical byte content (exercises --binary diffs)."""
    binary_path = os.path.join(clean_repo, "image.bin")
    binary_content = bytes([0, 1, 2, 3, 255, 254, 0, 10, 13])
    with open(binary_path, "wb") as f:
        f.write(binary_content)
    subprocess.run(["git", "add", "image.bin"], cwd=clean_repo, check=True)

    with shadow_workspace(clean_repo) as workspace:
        shadow_binary_path = os.path.join(workspace.path, "image.bin")
        assert os.path.exists(shadow_binary_path)
        with open(shadow_binary_path, "rb") as f:
            assert f.read() == binary_content


# ---------------------------------------------------------------------------
# Error handling / cleanup on invalid input
# ---------------------------------------------------------------------------


def test_shadow_workspace_invalid_source_dir_raises_and_cleans_up(tmp_path):
    """If source_dir is not a git repository, __enter__ must propagate the error and clean up the temp dir."""
    non_git_dir = tmp_path / "not_a_repo"
    non_git_dir.mkdir()

    workspace = ShadowWorkspace(str(non_git_dir))
    temp_root = workspace.temp_dir_obj.name

    with pytest.raises(subprocess.CalledProcessError):
        workspace.__enter__()

    assert not os.path.exists(temp_root)


# ---------------------------------------------------------------------------
# ShadowWorkspace.run - default and overridden subprocess kwargs
# ---------------------------------------------------------------------------


def test_run_applies_default_kwargs(monkeypatch):
    """run() must default cwd to self.path, text=True, and check=True when not explicitly provided."""
    workspace = ShadowWorkspace.__new__(ShadowWorkspace)
    workspace.path = "/fake/shadow/repo"

    captured = {}
    sentinel = mock.MagicMock()

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return sentinel

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = workspace.run(["git", "status"])

    assert result is sentinel
    assert captured["cmd"] == ["git", "status"]
    assert captured["kwargs"]["cwd"] == "/fake/shadow/repo"
    assert captured["kwargs"]["text"] is True
    assert captured["kwargs"]["check"] is True


def test_run_allows_overriding_default_kwargs(monkeypatch):
    """Explicitly passed kwargs (cwd, text, check) must take precedence over the defaults."""
    workspace = ShadowWorkspace.__new__(ShadowWorkspace)
    workspace.path = "/fake/shadow/repo"

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["kwargs"] = kwargs
        return mock.MagicMock()

    monkeypatch.setattr(subprocess, "run", fake_run)

    workspace.run(["git", "status"], cwd="/other/dir", text=False, check=False)

    assert captured["kwargs"]["cwd"] == "/other/dir"
    assert captured["kwargs"]["text"] is False
    assert captured["kwargs"]["check"] is False


def test_shadow_workspace_run_raises_on_failing_command_by_default(mock_repo):
    """run() must raise CalledProcessError for a failing command since check=True by default."""
    with shadow_workspace(mock_repo) as workspace, pytest.raises(subprocess.CalledProcessError):
        workspace.run(["git", "this-is-not-a-git-command"], capture_output=True)


def test_shadow_workspace_run_does_not_raise_when_check_disabled(mock_repo):
    """Passing check=False to run() must suppress the exception for a failing command."""
    with shadow_workspace(mock_repo) as workspace:
        result = workspace.run(["git", "this-is-not-a-git-command"], capture_output=True, check=False)
        assert result.returncode != 0


def test_shadow_workspace_run_failure_still_cleans_up_temp_dir(mock_repo):
    """Even when a failing command raises inside the combined `with ..., pytest.raises(...)`
    form, the temp directory must still be removed on context exit."""
    workspace_path = None
    with shadow_workspace(mock_repo) as workspace, pytest.raises(subprocess.CalledProcessError):
        workspace_path = workspace.path
        workspace.run(["git", "this-is-not-a-git-command"], capture_output=True)

    assert workspace_path is not None
    assert not os.path.exists(workspace_path)


# ---------------------------------------------------------------------------
# ShadowWorkspace._clone_and_sync - patch application is conditional on diff content
# ---------------------------------------------------------------------------


def test_clone_and_sync_skips_patch_application_when_diffs_are_empty(monkeypatch, tmp_path):
    """When both diffs are empty, git apply must never be invoked."""
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:2] == ["git", "diff"]:
            return mock.MagicMock(stdout=b"")
        return mock.MagicMock(stdout=b"", returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    workspace = ShadowWorkspace(str(tmp_path / "source"))
    try:
        workspace._clone_and_sync()
        apply_calls = [c for c in calls if c[:2] == ["git", "apply"]]
        assert apply_calls == []
    finally:
        workspace.temp_dir_obj.cleanup()


def test_clone_and_sync_skips_apply_when_diff_is_whitespace_only(monkeypatch, tmp_path):
    """A diff consisting solely of whitespace must be treated as empty (uses .strip()) and not applied."""
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:2] == ["git", "diff"]:
            return mock.MagicMock(stdout=b"   \n\t  ")
        return mock.MagicMock(stdout=b"", returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    workspace = ShadowWorkspace(str(tmp_path / "source"))
    try:
        workspace._clone_and_sync()
        apply_calls = [c for c in calls if c[:2] == ["git", "apply"]]
        assert apply_calls == []
    finally:
        workspace.temp_dir_obj.cleanup()


def test_clone_and_sync_applies_patches_when_diffs_are_non_empty(monkeypatch, tmp_path):
    """When staged/unstaged diffs are non-empty, both 'git apply --index' and 'git apply' must run."""
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd == ["git", "diff", "--cached", "--binary"]:
            return mock.MagicMock(stdout=b"staged patch data")
        if cmd == ["git", "diff", "--binary"]:
            return mock.MagicMock(stdout=b"unstaged patch data")
        return mock.MagicMock(stdout=b"", returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    workspace = ShadowWorkspace(str(tmp_path / "source"))
    try:
        workspace._clone_and_sync()
        assert ["git", "apply", "--index"] in calls
        assert ["git", "apply"] in calls
        assert ["git", "clone", "--local", workspace.source_dir, workspace.path] in calls
    finally:
        workspace.temp_dir_obj.cleanup()
