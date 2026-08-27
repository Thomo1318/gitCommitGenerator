"""
Index and HEAD blob readers for semantic producers (ADR-0005 Phase 1-2).

Reads **index** and **HEAD** content only (not the dirty worktree).
Never mutates git state.
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

# Bound stalled git subprocesses on the semantic staged-read path.
DEFAULT_GIT_TIMEOUT_SECONDS = 30.0


@dataclass
class StagedReadResult:
    """Outcome of reading staged blobs for semantic parsing.

    ok means "usable payload available" (at least one file), not
    "error-free". Callers must still inspect errors / skipped.
    """

    files: dict[str, bytes] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)  # path:reason
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Return True if at least one usable file is available (errors may still exist)."""
        return bool(self.files)


@git_retry
def _run_git(
    args: list[str],
    *,
    cwd: str | None,
    check: bool = True,
    input_data: bytes | None = None,
    timeout: float | None = DEFAULT_GIT_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[bytes]:
    """Execute a git command with retry logic and timeout."""
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        input=input_data,
        capture_output=True,
        check=check,
        timeout=timeout,
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

    Uses git diff --cached --name-only --diff-filter=ACMR -z.
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

    raw = proc.stdout.split(bytes([0]))
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
    Read a single staged blob via git show :path (index stage 0).

    Raises:
        ValueError: when ``path`` fails the shared unsafe-path guards.
        subprocess.CalledProcessError: when git cannot resolve the path in the index.
    """
    if _is_unsafe_staged_path(path):
        raise ValueError(f"unsafe staged path: {path!r}")
    cwd = repo_root or "."
    proc = _run_git(["show", f":{path}"], cwd=cwd)
    return proc.stdout


def _encode_batch_requests(paths: list[str], *, prefix: str = ":") -> bytes:
    """
    Encode repository-relative paths as newline-delimited Git batch requests.

    Parameters:
        paths (list[str]): Repository-relative paths to encode.
        prefix (str): Object prefix, such as ":" for the index or "HEAD:" for the HEAD tree.

    Returns:
        bytes: UTF-8 encoded batch requests.
    """
    return b"".join((f"{prefix}{p}".encode("utf-8", errors="surrogateescape") + bytes([10])) for p in paths)


def _parse_batch_check_header(header: str) -> tuple[str, int] | None:
    """Parse a Git ``--batch-check`` header.

    Parameters:
        header (str): Header line produced by ``git cat-file --batch-check``.

    Returns:
        tuple[str, int] | None: The object identifier or ``"missing"`` marker and
            object size, or ``None`` for an unrecognised header.
    """
    if header.endswith(" missing"):
        return "missing", 0
    parts = header.rsplit(" ", 2)
    if len(parts) != 3:
        return None
    _oid, _kind, size_s = parts
    try:
        return _oid, int(size_s)
    except ValueError:
        return None


def _is_unsafe_staged_path(path: str) -> bool:
    """
    Determine whether a path contains forms that are unsafe for batch input.

    Parameters:
        path (str): Path to check.

    Returns:
        bool: `True` if the path is absolute, contains traversal segments, or includes a newline or carriage return; `False` otherwise.
    """
    return (
        path.startswith("/")
        or path.startswith(chr(92))
        or ".." in Path(path).parts
        or chr(10) in path
        or chr(13) in path
    )


def _read_blobs_batch(
    paths: list[str],
    *,
    repo_root: str | None,
    max_file_bytes: int,
    prefix: str = ":",
) -> StagedReadResult:
    """
    Read multiple index or HEAD blobs and record successful, skipped, and failed paths.

    Parameters:
        paths (list[str]): Paths whose blobs should be read.
        repo_root (str | None): Repository working directory, or the current directory when omitted.
        max_file_bytes (int): Maximum permitted size for an individual blob.
        prefix (str): Git object prefix used to resolve each path.

    Returns:
        StagedReadResult: Blob contents and per-path skip or error records.
    """
    result = StagedReadResult()
    if not paths:
        return result

    cwd = repo_root or "."
    # Filter unsafe paths first (same guards as the single-path loop).
    # Also reject newlines: batch input is newline-delimited ( + LF), so a
    # newline in the path would split one request into multiple cat-file lines.
    safe_paths: list[str] = []
    for path in paths:
        if _is_unsafe_staged_path(path):
            result.skipped.append(f"{path}:unsafe_path")
            continue
        safe_paths.append(path)

    if not safe_paths:
        return result

    request = _encode_batch_requests(safe_paths, prefix=prefix)
    try:
        check_proc = _run_git(
            ["cat-file", "--batch-check"],
            cwd=cwd,
            check=False,
            input_data=request,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        for path in safe_paths:
            result.errors.append(f"{path}:{type(exc).__name__}:{exc}")
        return result

    check_data = check_proc.stdout
    offset = 0
    eligible: list[str] = []
    newline = bytes([10])

    for idx, path in enumerate(safe_paths):
        nl = check_data.find(newline, offset)
        if nl < 0:
            result.errors.append(f"{path}:batch_parse_error:truncated_header")
            for missing_path in safe_paths[idx + 1 :]:
                result.errors.append(f"{missing_path}:batch_parse_error:no_record")
            return result

        header = check_data[offset:nl].decode("utf-8", errors="replace")
        offset = nl + 1
        parsed = _parse_batch_check_header(header)
        if parsed is None:
            result.errors.append(f"{path}:batch_parse_error:{header}")
            continue
        marker, size = parsed
        if marker == "missing":
            result.errors.append(f"{path}:missing")
            continue
        if size > max_file_bytes:
            result.skipped.append(f"{path}:oversize:{size}")
            continue
        eligible.append(path)

    if check_proc.returncode not in (0, None) and not eligible and not result.errors and not result.skipped:
        stderr = (check_proc.stderr or b"").decode("utf-8", errors="replace").strip()
        result.errors.append(f"batch_check:CalledProcessError:{stderr or check_proc.returncode}")
        return result

    if not eligible:
        return result

    try:
        proc = _run_git(
            ["cat-file", "--batch"],
            cwd=cwd,
            check=False,
            input_data=_encode_batch_requests(eligible, prefix=prefix),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        for path in eligible:
            result.errors.append(f"{path}:{type(exc).__name__}:{exc}")
        return result

    data = proc.stdout
    offset = 0
    path_idx = 0

    while path_idx < len(eligible) and offset < len(data):
        path = eligible[path_idx]
        path_idx += 1

        nl = data.find(newline, offset)
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

        # Defence in depth: never retain oversize content even if check raced.
        if size > max_file_bytes:
            result.skipped.append(f"{path}:oversize:{size}")
            offset += size
            if offset < len(data) and data[offset : offset + 1] == newline:
                offset += 1
            continue

        content = data[offset : offset + size]
        offset += size
        # cat-file --batch emits a trailing newline after content
        if offset < len(data) and data[offset : offset + 1] == newline:
            offset += 1

        if len(content) != size:
            result.errors.append(f"{path}:batch_parse_error:truncated_content")
            continue
        result.files[path] = content

    # Paths with no corresponding batch record (truncated stream / early exit).
    while path_idx < len(eligible):
        path = eligible[path_idx]
        path_idx += 1
        result.errors.append(f"{path}:batch_parse_error:no_record")

    if proc.returncode not in (0, None) and not result.files and not result.errors:
        stderr = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
        result.errors.append(f"batch:CalledProcessError:{stderr or proc.returncode}")

    return result


def _read_staged_blobs_batch(
    paths: list[str],
    *,
    repo_root: str | None,
    max_file_bytes: int,
) -> StagedReadResult:
    """Read index stage-0 blobs for ``paths``."""
    return _read_blobs_batch(paths, repo_root=repo_root, max_file_bytes=max_file_bytes, prefix=":")


def _read_head_blobs_batch(
    paths: list[str],
    *,
    repo_root: str | None,
    max_file_bytes: int,
) -> StagedReadResult:
    """Read HEAD-tree blobs for ``paths``."""
    return _read_blobs_batch(paths, repo_root=repo_root, max_file_bytes=max_file_bytes, prefix="HEAD:")


def read_staged_sources(
    repo_root: str | None = None,
    *,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    excludes: tuple[str, ...] = _DEFAULT_EXCLUDES,
    paths: list[str] | None = None,
) -> StagedReadResult:
    """
    Load staged file contents for semantic parsing.

    Parameters:
        max_file_bytes (int): Maximum content size in bytes for each file.
        excludes (tuple[str, ...]): Glob patterns for staged paths to skip when paths are not provided.
        paths (list[str] | None): Paths to read; when omitted, reads eligible staged paths from the index.

    Returns:
        StagedReadResult: Loaded file contents and records of skipped paths or read errors.
    """
    cwd = repo_root or "."
    staged_paths = paths if paths is not None else list_staged_paths(cwd, excludes=excludes)
    return _read_staged_blobs_batch(staged_paths, repo_root=cwd, max_file_bytes=max_file_bytes)


def read_head_blob(path: str, *, repo_root: str | None = None) -> bytes:
    """
    Read a single blob from HEAD via ``git show HEAD:path``.

    Raises:
        ValueError: when ``path`` fails the shared unsafe-path guards.
        subprocess.CalledProcessError: when git cannot resolve the path at HEAD.
    """
    if _is_unsafe_staged_path(path):
        raise ValueError(f"unsafe head path: {path!r}")
    cwd = repo_root or "."
    proc = _run_git(["show", f"HEAD:{path}"], cwd=cwd)
    return proc.stdout


def read_head_sources(
    repo_root: str | None = None,
    *,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    paths: list[str] | None = None,
) -> StagedReadResult:
    """
    Load HEAD-tree file contents for the specified paths.

    Parameters:
        paths (list[str] | None): Paths to read from HEAD. If omitted, no paths are read.
        max_file_bytes (int): Maximum content size for each file.

    Returns:
        StagedReadResult: Loaded path-to-content mappings, skipped paths, and read errors.
    """
    cwd = repo_root or "."
    head_paths = list(paths or [])
    return _read_head_blobs_batch(head_paths, repo_root=cwd, max_file_bytes=max_file_bytes)


def should_refresh_graph() -> bool:
    """
    Determines whether semantic graph refresh is enabled by configuration.

    Returns:
        bool: `True` when the configuration enables graph refresh, `False` otherwise.
    """
    raw = os.environ.get("GIT_CG_SEMANTIC_REFRESH_GRAPH", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}
