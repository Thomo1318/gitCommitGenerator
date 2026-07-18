import os
import subprocess
import tempfile

import pytest

from git_cg.shadow_workspace import shadow_workspace


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
        workspace.run(["git", "commit", "-m", "Shadow commit"])
        shadow_head = workspace.run(["git", "rev-parse", "HEAD"], capture_output=True).stdout.strip()

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
