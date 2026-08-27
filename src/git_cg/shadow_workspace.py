"""Temporary isolated Git repository clones for safe speculative operations.

Provides ShadowWorkspace and context managers for creating sandboxed Git
repository clones that mirror staged and optionally unstaged changes without
risking the user's working directory.
"""

import os
import subprocess
import tempfile
import time
from contextlib import contextmanager


class ShadowWorkspace:
    """
    A temporary, isolated clone of a Git repository.

    This provides a safe sandbox for speculative Git operations (like generating and applying
    commits) without risking the user's actual working directory.
    """

    def __init__(self, source_dir: str, include_unstaged: bool = True):
        self.source_dir = os.path.abspath(source_dir)
        self.include_unstaged = include_unstaged
        self.temp_dir_obj = tempfile.TemporaryDirectory(prefix="git-cg-shadow-")
        self.path = os.path.join(self.temp_dir_obj.name, "repo")
        # Elapsed clone+sync time in ms (Phase 7.5 #180 nice-to-have). 0.0 until enter succeeds.
        self.clone_sync_latency_ms: float = 0.0

    def __enter__(self):
        try:
            self._clone_and_sync()
        except Exception:
            self.temp_dir_obj.cleanup()
            raise
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.temp_dir_obj.cleanup()

    def _clone_and_sync(self):
        """
        Clones the repository and synchronizes the index (staged changes) and working tree (unstaged changes)
        using git patch applications.
        """
        started = time.perf_counter()
        try:
            # 1. Fast local clone (uses hardlinks on POSIX, checks out HEAD)
            subprocess.run(
                ["git", "clone", "--local", self.source_dir, self.path],
                check=True,
                capture_output=True,
            )

            # 2. Sync staged changes
            staged_patch = self._get_patch(self.source_dir, ["git", "diff", "--cached", "--binary"])
            if staged_patch.strip():
                self._apply_patch(staged_patch, ["git", "apply", "--index"])

            # 3. Sync unstaged changes (skipped in index-only mode, Phase 7.5 #180)
            if self.include_unstaged:
                unstaged_patch = self._get_patch(self.source_dir, ["git", "diff", "--binary"])
                if unstaged_patch.strip():
                    self._apply_patch(unstaged_patch, ["git", "apply"])
        finally:
            # Record even on failure so callers can fold partial cost into graph_build_latency_ms.
            self.clone_sync_latency_ms = round((time.perf_counter() - started) * 1000.0, 3)

    def _get_patch(self, cwd: str, cmd: list[str]) -> bytes:
        """Runs a diff command and returns the patch bytes."""
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, check=True)
        return result.stdout

    def _apply_patch(self, patch_data: bytes, cmd: list[str]):
        """Applies a patch in the shadow workspace."""
        # Using subprocess.run with input=patch_data allows us to pipe the patch securely
        subprocess.run(cmd, cwd=self.path, input=patch_data, check=True, capture_output=True)

    def run(self, cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        """
        Runs a command (e.g., 'git') inside the shadow workspace.

        Args:
            cmd: The command list to run.
            **kwargs: Extra arguments for subprocess.run.

        Returns:
            subprocess.CompletedProcess
        """
        kwargs.setdefault("cwd", self.path)
        kwargs.setdefault("text", True)
        kwargs.setdefault("check", True)
        return subprocess.run(cmd, **kwargs)


@contextmanager
def shadow_workspace(source_dir: str = ".", include_unstaged: bool = True):
    """
    Context manager that duplicates the current git repository into a temporary directory.

    Args:
        source_dir: Path to the source git repository.
        include_unstaged: When False, only staged (index) changes are synced into the
            shadow — the dirty worktree is excluded (index-only mode, Phase 7.5 #180).

    Yields:
        ShadowWorkspace: The isolated workspace object.
    """
    with ShadowWorkspace(source_dir, include_unstaged=include_unstaged) as workspace:
        yield workspace


@contextmanager
def shadow_workspace_index_only(source_dir: str = "."):
    """
    Index-only shadow workspace (Phase 7.5 #180).

    Sugar for ``shadow_workspace(source_dir, include_unstaged=False)`` — only staged
    (index) content is synced; unstaged worktree edits are excluded.
    """
    with shadow_workspace(source_dir, include_unstaged=False) as workspace:
        yield workspace
