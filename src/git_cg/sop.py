"""Centralised, install-relative resolution and loading of the GitOps SOP.

Works in both supported modes:
  * Standalone CLI inside git-cg's own checkout (repo-root ``config/``).
  * Global git hook running inside an arbitrary repo (packaged wheel data).
"""

from __future__ import annotations

import json
import os
import subprocess
from contextlib import suppress
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


def _deep_merge(target: dict[str, Any], source: dict[str, Any]) -> None:
    """Recursively deep-merge a source dictionary into a target dictionary."""
    for key, value in source.items():
        if isinstance(value, dict) and key in target and isinstance(target[key], dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value


@lru_cache(maxsize=1)
def load_sop() -> dict[str, Any]:
    """Load and cache the SOP document. Returns ``{}`` if it cannot be found."""
    sop_data = {}

    # 1. Base Packaged wheel data (works in any repo when installed as a tool).
    with suppress(*_PACKAGE_ERRORS):
        text = resources.files(_PACKAGE).joinpath("data", _SOP_FILENAME).read_text(encoding="utf-8")
        sop_data = json.loads(text)

    repo_root = _git_repo_root()
    if repo_root:
        # 2. Local legacy config (used during development in git-cg's own repo)
        legacy = repo_root / "config" / _SOP_FILENAME
        if legacy.is_file():
            with suppress(OSError):
                _deep_merge(sop_data, json.loads(legacy.read_text(encoding="utf-8")))

        # 3. Per-repo override config
        override = repo_root / ".git-cg" / "sop.json"
        if override.is_file():
            with suppress(OSError):
                _deep_merge(sop_data, json.loads(override.read_text(encoding="utf-8")))

    # 4. Explicit environment override
    env_path = os.environ.get("GIT_CG_SOP_PATH")
    if env_path:
        candidate = Path(env_path).expanduser()
        if candidate.is_file():
            with suppress(OSError):
                _deep_merge(sop_data, json.loads(candidate.read_text(encoding="utf-8")))

    return sop_data


def get_gitmoji_matrix() -> list[dict[str, Any]]:
    """Convenience accessor for the gitmoji reference matrix."""
    return load_sop().get("gitmoji_reference_matrix", [])
