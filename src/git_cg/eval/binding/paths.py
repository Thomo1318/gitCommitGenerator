"""S3 local Layer-A filesystem law (Issue #231, S3-contract-v1.4 / D2, D13, N19.3, N20.5).

Locked on-disk tree (repo-local, gitignored in normal use)::

    .eval/
      bundles/acceptpath/<session_thread_id>.json   # final_accept ape_bundle_v1
      sessions/<session_thread_id>.json             # commit_session_thread_v1 twin
      trajectories/<trajectory_id>.json             # optional split twin (inline preferred)

Write law:

* **Atomic persist (N19.3):** temp file in the target directory + ``os.replace``;
  restrictive modes (files ``0600``, dirs ``0700``) for runtime ``.eval/**`` trees.
* **Containment:** refuse any write that would escape the resolved repo-root
  ``.eval/`` tree (symlink / path-escape defense).
* **Authority:** validated bundle/session JSON files are authoritative; an
  optional ``index.json`` is cache-only and rebuildable — never sole authority.
* **Repo root (D13/N20.5):** resolve via ``git rev-parse --show-toplevel`` from
  the hook environment; fall back to ``git rev-parse --git-dir`` layouts; if
  unresolvable, surface ``repo_root_unresolved`` (no writes, no product fail).

No network. No Opik. Nothing here mutates product accept behaviour.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

__all__ = [
    "ACCEPTPATH_BUNDLES_DIRNAME",
    "EVAL_DIRNAME",
    "SESSIONS_DIRNAME",
    "TRAJECTORIES_DIRNAME",
    "LayerAPathError",
    "RepoRootUnresolvedError",
    "acceptpath_bundles_dir",
    "atomic_write_json",
    "eval_tree_root",
    "resolve_repo_root",
    "sessions_dir",
    "trajectories_dir",
]

#: Runtime tree root name (repo-local; gitignored via ``/.eval/``).
EVAL_DIRNAME = ".eval"

#: Locked sub-paths under ``.eval/`` (D2).
ACCEPTPATH_BUNDLES_DIRNAME = ("bundles", "acceptpath")
SESSIONS_DIRNAME = ("sessions",)
TRAJECTORIES_DIRNAME = ("trajectories",)

#: Restrictive modes for runtime trees (N19.3).
_FILE_MODE = 0o600
_DIR_MODE = 0o700


class LayerAPathError(ValueError):
    """Layer-A path containment / persistence failure (fail-closed)."""


class RepoRootUnresolvedError(LayerAPathError):
    """Repo root could not be resolved; no Layer-A writes permitted (N20.5)."""


def _run_git(args: list[str], cwd: Path) -> str | None:
    """Best-effort ``git`` stdout, or ``None`` on any failure (never raises)."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except OSError, subprocess.SubprocessError:
        return None
    if proc.returncode != 0:
        return None
    out = proc.stdout.strip()
    return out or None


def resolve_repo_root(start: Path | None = None) -> Path:
    """Resolve the repo root for Layer-A writes (D13 primary, N20.5 fallback).

    Order:
        1. ``git rev-parse --show-toplevel`` (primary).
        2. ``git rev-parse --git-dir`` fallback: when git-dir is ``$REPO/.git``
           use its parent; otherwise use the git-dir itself (bare/odd layout).
        3. Unresolvable ⇒ raise :class:`RepoRootUnresolvedError`.

    The returned path is resolved (symlinks collapsed) and must be a directory.
    """
    cwd = Path(start) if start is not None else Path.cwd()
    try:
        cwd = cwd.resolve()
    except OSError as exc:
        raise RepoRootUnresolvedError(f"cannot resolve start path: {exc}") from exc

    top = _run_git(["rev-parse", "--show-toplevel"], cwd)
    if top:
        root = Path(top)
        try:
            root = root.resolve()
        except OSError:
            root = root.absolute()
        if root.is_dir():
            return root

    git_dir_raw = _run_git(["rev-parse", "--git-dir"], cwd)
    if git_dir_raw:
        git_dir = Path(git_dir_raw)
        if not git_dir.is_absolute():
            git_dir = cwd / git_dir
        try:
            git_dir = git_dir.resolve()
        except OSError:
            git_dir = git_dir.absolute()
        if git_dir.name == ".git":
            parent = git_dir.parent
            if parent.is_dir():
                return parent
        if git_dir.is_dir():
            # Bare repo / unusual layout: git-dir-local fallback root.
            return git_dir

    raise RepoRootUnresolvedError("repo_root_unresolved")


def eval_tree_root(repo_root: Path) -> Path:
    """Return the resolved ``.eval/`` root under ``repo_root`` (no creation)."""
    return Path(repo_root).resolve() / EVAL_DIRNAME


def _contained(repo_root: Path, target: Path) -> Path:
    """Resolve ``target`` and refuse escape outside the ``.eval/`` tree.

    Containment is enforced against the resolved repo-root ``.eval/`` tree so
    symlink or ``..`` escapes fail closed (N19.3). Symlinks on existing path
    ancestors are resolved before the comparison; non-existent trailing
    components are re-appended so creation targets remain valid.
    """
    root = Path(repo_root).resolve()
    tree = root / EVAL_DIRNAME
    resolved = Path(target)
    if not resolved.is_absolute():
        resolved = tree / resolved
    # Collapse ``..`` lexically, then resolve symlinks on the deepest existing
    # ancestor and re-append the not-yet-created tail (N19.3).
    resolved = Path(os.path.normpath(str(resolved)))
    existing = resolved
    tail: list[str] = []
    while not existing.exists() and existing != existing.parent:
        tail.append(existing.name)
        existing = existing.parent
    try:
        resolved = existing.resolve().joinpath(*reversed(tail))
    except OSError as exc:
        raise LayerAPathError(f"cannot resolve containment path: {exc}") from exc
    try:
        # Resolve via an existing parent so a missing .eval leaf still compares
        # against the real repo-root path; resolve fully when .eval already exists.
        tree_norm = tree.parent.resolve() / tree.name if tree.parent.exists() else Path(os.path.normpath(str(tree)))
        if tree_norm.exists():
            tree_norm = tree_norm.resolve()
    except OSError as exc:
        raise LayerAPathError(f"cannot resolve .eval containment root: {exc}") from exc
    if tree_norm != resolved and tree_norm not in resolved.parents:
        raise LayerAPathError(f"path escapes .eval containment root: {resolved}")
    return resolved


def acceptpath_bundles_dir(repo_root: Path) -> Path:
    """Return ``.eval/bundles/acceptpath/`` (contained; not created here)."""
    return _contained(repo_root, Path(*ACCEPTPATH_BUNDLES_DIRNAME))


def sessions_dir(repo_root: Path) -> Path:
    """Return ``.eval/sessions/`` (contained; not created here)."""
    return _contained(repo_root, Path(*SESSIONS_DIRNAME))


def trajectories_dir(repo_root: Path) -> Path:
    """Return ``.eval/trajectories/`` (contained; not created here)."""
    return _contained(repo_root, Path(*TRAJECTORIES_DIRNAME))


def _ensure_dir(path: Path) -> None:
    """Create ``path`` (and parents) with restrictive dir mode, best-effort."""
    path.mkdir(parents=True, exist_ok=True, mode=_DIR_MODE)
    # mkdir mode is subject to umask; tighten the leaf explicitly, best-effort.
    with contextlib.suppress(OSError):
        os.chmod(path, _DIR_MODE)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> Path:
    """Atomically write ``payload`` as UTF-8 JSON to ``path`` (N19.3).

    Writes a temp file in the *target directory*, fsyncs, then ``os.replace``
    onto the final path so an interrupted write never leaves a partially-valid
    authoritative bundle under the final name. Final file mode is ``0600``.

    The final ``path`` must already be containment-checked by the caller; this
    helper re-verifies containment defensively when the path is under a
    recognisable ``.eval/`` tree.

    Returns the final path written.
    """
    final = Path(path)
    _ensure_dir(final.parent)

    fd, tmp_name = tempfile.mkstemp(prefix=f".{final.name}.", suffix=".tmp", dir=str(final.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_path, _FILE_MODE)
        os.replace(tmp_path, final)
    except BaseException:
        # Never leave a partially-valid authoritative bundle behind.
        with contextlib.suppress(OSError):
            tmp_path.unlink(missing_ok=True)
        raise
    # Durably record the rename in the parent directory (N19.3). Best-effort:
    # some platforms/filesystems do not support directory fsync.
    with contextlib.suppress(OSError):
        dir_fd = os.open(str(final.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    return final
