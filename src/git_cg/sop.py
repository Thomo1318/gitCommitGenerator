"""Centralised, install-relative resolution and loading of the GitOps SOP.

Works in both supported modes:
  * Standalone CLI inside git-cg's own checkout (repo-root ``config/``).
  * Global git hook running inside an arbitrary repo (packaged wheel data).
"""

from __future__ import annotations

import json
import os
import subprocess
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

_PACKAGE = "git_cg"
_SOP_FILENAME = "gitops_agent_sop.json"

_GIT_ERRORS = (subprocess.CalledProcessError, FileNotFoundError)
_READ_ERRORS = (OSError, json.JSONDecodeError)
_PACKAGE_ERRORS = (FileNotFoundError, ModuleNotFoundError, json.JSONDecodeError)


def _git_repo_root() -> Path | None:
    """Return the top level of the current git repo, or None if unavailable."""
    try:
        root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return Path(root) if root else None
    except _GIT_ERRORS:
        return None


def resolve_sop_path() -> Path | None:
    """Locate the SOP file using a portable precedence chain (highest first).

    1. ``GIT_CG_SOP_PATH`` explicit override.
    2. ``<repo_root>/.git-cg/sop.json`` per-repo override.
    3. ``<repo_root>/config/gitops_agent_sop.json`` (git-cg's own checkout).

    Packaged wheel data is handled separately in :func:`load_sop` so it works
    for both zip-safe and filesystem installs.
    """
    env_path = os.environ.get("GIT_CG_SOP_PATH")
    if env_path:
        candidate = Path(env_path).expanduser()
        if candidate.is_file():
            return candidate

    repo_root = _git_repo_root()
    if repo_root:
        override = repo_root / ".git-cg" / "sop.json"
        if override.is_file():
            return override
        legacy = repo_root / "config" / _SOP_FILENAME
        if legacy.is_file():
            return legacy

    return None


@lru_cache(maxsize=1)
def load_sop() -> dict[str, Any]:
    """Load and cache the SOP document. Returns ``{}`` if it cannot be found."""
    path = resolve_sop_path()
    if path is not None:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except _READ_ERRORS:
            pass

    # Packaged wheel data (works in any repo when installed as a tool).
    try:
        text = resources.files(_PACKAGE).joinpath("data", _SOP_FILENAME).read_text(encoding="utf-8")
        return json.loads(text)
    except _PACKAGE_ERRORS:
        return {}


def get_gitmoji_matrix() -> list[dict[str, Any]]:
    """Convenience accessor for the gitmoji reference matrix."""
    return load_sop().get("gitmoji_reference_matrix", [])
