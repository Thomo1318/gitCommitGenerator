"""
Staged-index blob readers for semantic producers (ADR-0005 Phase 1).

Reads **index** content only (not the dirty worktree). Never mutates git state.
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
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
    """Outcome of reading staged blobs for semantic parsing.

    ``ok`` means "usable payload available" (at least one file), not
    "error-free". Callers must still inspect ``errors`` / ``skipped``.
    """

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
    """Return True when path or basename matches any exclude glob."""
    name = Path(path).name
    return any(fnmatchcase(name, pattern) or fnmatchcase(path, pattern) for pattern in excludes)


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
    proc = _run_git(["show", f":{path}"], cwd=cwd)
    return proc.stdout


def _read_staged_blobs_batch(
    paths: list[str],
    *,
    repo_root: str | None,
    max_file_bytes: int,
) -> StagedReadResult:
    """
    Read many staged blobs via one ``git cat-file --batch`` process.

    Input lines are ``:<path>`` (index stage 0). Output records are:
    ``<oid> <type> <size>\\n<content>\\n`` or ``<requested> missing\\n``.
    """
    result = StagedReadResult()
    if not paths:
        return result

    cwd = repo_root or "."
    # Filter unsafe paths first (same guards as the single-path loop).
    safe_paths: list[str] = []
    for path in paths:
        if path.startswith("/") or path.startswith("\\") or ".." in Path(path).parts:
            result.skipped.append(f"{path}:unsafe_path")
            continue
        safe_paths.append(path)

    if not safe_paths:
        return result

    try:
        proc = subprocess.run(
            ["git", "cat-file", "--batch"],
            cwd=cwd,
            input=b"".join(f":{p}\n".encode("utf-8", errors="surrogateescape") for p in safe_paths),
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        for path in safe_paths:
            result.errors.append(f"{path}:{type(exc).__name__}:{exc}")
        return result

    data = proc.stdout
    offset = 0
    path_idx = 0

    while path_idx < len(safe_paths) and offset < len(data):
        path = safe_paths[path_idx]
        path_idx += 1

        nl = data.find(b"\n", offset)
        if nl < 0:
            result.errors.append(f"{path}:batch_parse_error:truncated_header")
            break
        header = data[offset:nl].decode("utf-8", errors="replace")
        offset = nl + 1

        if header.endswith(" missing"):
            result.errors.append(f"{path}:missing")
            continue

        parts = header.rsplit(" ", 2)
        if len(parts) != 3:
            result.errors.append(f"{path}:batch_parse_error:{header}")
            continue
        _oid, _kind, size_s = parts
        try:
            size = int(size_s)
        except ValueError:
            result.errors.append(f"{path}:batch_parse_error:bad_size:{size_s}")
            continue

        content = data[offset : offset + size]
        offset += size
        # cat-file --batch emits a trailing newline after content
        if offset < len(data) and data[offset : offset + 1] == b"\n":
            offset += 1

        if len(content) != size:
            result.errors.append(f"{path}:batch_parse_error:truncated_content")
            continue
        if size > max_file_bytes:
            result.skipped.append(f"{path}:oversize:{size}")
            continue
        result.files[path] = content

    # Paths with no corresponding batch record (truncated stream / early exit).
    while path_idx < len(safe_paths):
        path = safe_paths[path_idx]
        path_idx += 1
        result.errors.append(f"{path}:batch_parse_error:no_record")

    if proc.returncode not in (0, None) and not result.files and not result.errors:
        stderr = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
        result.errors.append(f"batch:CalledProcessError:{stderr or proc.returncode}")

    return result


def read_staged_sources(
    repo_root: str | None = None,
    *,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    excludes: tuple[str, ...] = _DEFAULT_EXCLUDES,
    paths: list[str] | None = None,
) -> StagedReadResult:
    """
    Load staged file contents as ``path -> bytes`` for the semantic parser.

    Uses a single ``git cat-file --batch`` process for the staged set.
    Skips oversize blobs and records typed skip/error reasons without raising.
    """
    cwd = repo_root or "."
    staged_paths = paths if paths is not None else list_staged_paths(cwd, excludes=excludes)
    return _read_staged_blobs_batch(staged_paths, repo_root=cwd, max_file_bytes=max_file_bytes)


def should_refresh_graph() -> bool:
    """Opt-in graph rebuild on the semantic path (default off)."""
    raw = os.environ.get("GIT_CG_SEMANTIC_REFRESH_GRAPH", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}
