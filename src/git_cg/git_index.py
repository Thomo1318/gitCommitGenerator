"""
Staged-index blob readers for semantic producers (ADR-0005 Phase 1).

Reads **index** content only (not the dirty worktree). Never mutates git state.
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from git_cg.retries import git_retry

log = logging.getLogger(__name__)

# Skip lockfiles / generated noise consistent with extract_git_diff excludes.
_DEFAULT_EXCLUDES: tuple[str, ...] = (
    "*.lock",
    "*-lock.json",
    "*-lock.yaml",
    "*.lockb",
    "*zensical*",
    "*auxly*",
)

# Per-file cap so huge staged blobs cannot blow memory on the commit path.
DEFAULT_MAX_FILE_BYTES = 2 * 1024 * 1024


@dataclass
class StagedReadResult:
    """Outcome of reading staged blobs for semantic parsing."""

    files: dict[str, bytes] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)  # path:reason
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors or bool(self.files)


@git_retry
def _run_git(args: list[str], *, cwd: str | None, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        check=check,
    )


def _path_excluded(path: str, excludes: tuple[str, ...]) -> bool:
    name = Path(path).name
    full = path
    for pattern in excludes:
        # Minimal fnmatch-like handling for our fixed patterns.
        if pattern.startswith("*") and pattern.endswith("*"):
            token = pattern.strip("*")
            if token and (token in name or token in full):
                return True
        elif pattern.startswith("*"):
            if name.endswith(pattern[1:]) or full.endswith(pattern[1:]):
                return True
        elif pattern.endswith("*"):
            if name.startswith(pattern[:-1]) or full.startswith(pattern[:-1]):
                return True
        elif name == pattern or full == pattern:
            return True
    return False


def list_staged_paths(
    repo_root: str | None = None,
    *,
    excludes: tuple[str, ...] = _DEFAULT_EXCLUDES,
) -> list[str]:
    """
    Return repo-relative paths of staged files (ACMR), excluding deletes and noise.

    Uses ``git diff --cached --name-only --diff-filter=ACMR -z``.
    """
    cwd = repo_root or "."
    try:
        proc = _run_git(
            ["diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z", "--", "."],
            cwd=cwd,
        )
    except subprocess.CalledProcessError as exc:
        log.debug("list_staged_paths failed: %s", exc)
        return []

    raw = proc.stdout.split(b"\x00")
    paths: list[str] = []
    for chunk in raw:
        if not chunk:
            continue
        try:
            path = chunk.decode("utf-8")
        except UnicodeDecodeError:
            path = chunk.decode("utf-8", errors="replace")
        if _path_excluded(path, excludes):
            continue
        paths.append(path)
    return paths


def read_staged_blob(path: str, *, repo_root: str | None = None) -> bytes:
    """
    Read a single staged blob via ``git show :path`` (index stage 0).

    Raises:
        subprocess.CalledProcessError: when git cannot resolve the path in the index.
    """
    cwd = repo_root or "."
    # Prefer literal pathspec after -- to avoid option injection.
    proc = _run_git(["show", f":{path}"], cwd=cwd)
    return proc.stdout


def read_staged_sources(
    repo_root: str | None = None,
    *,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    excludes: tuple[str, ...] = _DEFAULT_EXCLUDES,
    paths: list[str] | None = None,
) -> StagedReadResult:
    """
    Load staged file contents as ``path -> bytes`` for the semantic parser.

    Skips oversize blobs and records typed skip/error reasons without raising.
    """
    result = StagedReadResult()
    cwd = repo_root or "."
    staged_paths = paths if paths is not None else list_staged_paths(cwd, excludes=excludes)

    for path in staged_paths:
        try:
            # Guard against absolute / escape paths.
            if path.startswith("/") or path.startswith("\\") or ".." in Path(path).parts:
                result.skipped.append(f"{path}:unsafe_path")
                continue

            data = read_staged_blob(path, repo_root=cwd)
            if len(data) > max_file_bytes:
                result.skipped.append(f"{path}:oversize:{len(data)}")
                continue
            result.files[path] = data
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or b"").decode("utf-8", errors="replace").strip()
            result.errors.append(f"{path}:CalledProcessError:{stderr or exc.returncode}")
        except OSError as exc:
            result.errors.append(f"{path}:{type(exc).__name__}:{exc}")

    return result


def should_refresh_graph() -> bool:
    """Opt-in graph rebuild on the semantic path (default off)."""
    raw = os.environ.get("GIT_CG_SEMANTIC_REFRESH_GRAPH", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}
