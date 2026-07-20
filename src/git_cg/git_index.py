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
        return not self.errors or bool(self.files)


@git_retry
def _run_git(
    args: list[str],
    *,
    cwd: str | None,
    check: bool = True,
    input_data: bytes | None = None,
    timeout: float | None = DEFAULT_GIT_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[bytes]:
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
        subprocess.CalledProcessError: when git cannot resolve the path in the index.
    """
    cwd = repo_root or "."
    proc = _run_git(["show", f":{path}"], cwd=cwd)
    return proc.stdout


def _encode_batch_requests(paths: list[str], *, prefix: str = ":") -> bytes:
    """Encode path requests for git cat-file --batch*.

    Args:
        paths: Repo-relative paths.
        prefix: Object prefix. ``":"`` = index stage 0; ``"HEAD:"`` = HEAD tree.
    """
    return b"".join((f"{prefix}{p}".encode("utf-8", errors="surrogateescape") + bytes([10])) for p in paths)


def _parse_batch_check_header(header: str) -> tuple[str, int] | None:
    """Parse a --batch-check header into (oid_or_marker, size)."""
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
    """Reject absolute, traversal, and newline-bearing paths for batch input."""
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
    Read many blobs via git cat-file batch protocols.

    1. --batch-check preflight obtains sizes without materialising content.
    2. Oversized / missing / unsafe paths are skipped or errored immediately.
    3. Eligible blobs are fetched with one --batch call so peak memory is
       bounded by max_file_bytes rather than the full path set.

    Input lines are ``{prefix}{path}`` (e.g. index stage 0 ``:path`` or
    ``HEAD:path``). Output records are:
    <oid> <type> <size> then newline (check), or the same header plus
    content and trailing newline (batch), or <requested> missing.
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
    Load staged file contents as path -> bytes for the semantic parser.

    Uses git cat-file --batch-check then --batch for the staged set.
    Skips oversize blobs and records typed skip/error reasons without raising.
    """
    cwd = repo_root or "."
    staged_paths = paths if paths is not None else list_staged_paths(cwd, excludes=excludes)
    return _read_staged_blobs_batch(staged_paths, repo_root=cwd, max_file_bytes=max_file_bytes)


def read_head_blob(path: str, *, repo_root: str | None = None) -> bytes:
    """
    Read a single blob from HEAD via ``git show HEAD:path``.

    Raises:
        subprocess.CalledProcessError: when git cannot resolve the path at HEAD.
    """
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
    Load HEAD-tree file contents as path -> bytes for fingerprint baselines.

    When ``paths`` is None, returns an empty result (callers should pass the
    staged path set they intend to pair). Missing HEAD paths are recorded as
    errors (typically add-only staged files).
    """
    cwd = repo_root or "."
    head_paths = list(paths or [])
    return _read_head_blobs_batch(head_paths, repo_root=cwd, max_file_bytes=max_file_bytes)


def should_refresh_graph() -> bool:
    """Opt-in graph rebuild on the semantic path (default off)."""
    raw = os.environ.get("GIT_CG_SEMANTIC_REFRESH_GRAPH", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}
