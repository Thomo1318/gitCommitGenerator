"""Tests for the new Bun lockfile (bun.lock) shipped alongside package.json.

bun.lock is JSONC (it permits trailing commas), so the stdlib ``json`` module
cannot parse it verbatim. These tests strip trailing commas before parsing and
cross-check the resulting structure against the pre-existing package.json,
which is the authoritative source for declared dependency ranges.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
BUN_LOCK = REPO_ROOT / "bun.lock"
PACKAGE_JSON = REPO_ROOT / "package.json"

_TRAILING_COMMA = re.compile(r",(\s*[}\]])")


def _parse_bun_lock() -> dict:
    """Parse bun.lock's JSONC content into a plain dict.

    Returns:
        dict: The parsed lockfile document.
    """
    text = BUN_LOCK.read_text(encoding="utf-8")
    stripped = _TRAILING_COMMA.sub(r"\1", text)
    return json.loads(stripped)


def _package_json() -> dict:
    return json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))


def test_bun_lock_file_exists():
    assert BUN_LOCK.is_file()


def test_bun_lock_is_parseable_jsonc():
    data = _parse_bun_lock()
    assert isinstance(data, dict)
    assert "workspaces" in data
    assert "packages" in data


def test_bun_lock_declares_lockfile_version_1():
    data = _parse_bun_lock()
    assert data["lockfileVersion"] == 1


def test_bun_lock_workspace_name_matches_package_json():
    data = _parse_bun_lock()
    pkg = _package_json()
    assert data["workspaces"][""]["name"] == pkg["name"] == "git-commit-generator"


def test_bun_lock_dependencies_match_package_json():
    data = _parse_bun_lock()
    pkg = _package_json()
    workspace = data["workspaces"][""]
    assert workspace["dependencies"] == pkg["dependencies"]
    assert workspace["devDependencies"] == pkg["devDependencies"]


def test_bun_lock_declared_dependencies_are_resolved_in_packages():
    data = _parse_bun_lock()
    packages = data["packages"]
    assert "zx" in packages
    assert "doctoc" in packages
    assert packages["zx"][0].startswith("zx@")
    assert packages["doctoc"][0].startswith("doctoc@")


def test_bun_lock_doctoc_resolved_version_satisfies_caret_range():
    """package.json pins doctoc to ^2.5.0; the resolved lock entry must be a 2.x >= 2.5.0."""
    data = _parse_bun_lock()
    resolved = data["packages"]["doctoc"][0]
    version = resolved.split("@")[-1]
    major, minor, patch = (int(part) for part in version.split("."))
    assert major == 2
    assert (minor, patch) >= (5, 0)


def test_bun_lock_zx_resolved_version_satisfies_caret_range():
    """package.json pins zx to ^8.1.0; the resolved lock entry must be an 8.x >= 8.1.0."""
    data = _parse_bun_lock()
    resolved = data["packages"]["zx"][0]
    version = resolved.split("@")[-1]
    major, minor, patch = (int(part) for part in version.split("."))
    assert major == 8
    assert (minor, patch) >= (1, 0)


def test_bun_lock_has_no_duplicate_top_level_package_keys():
    """Regression guard: duplicate JSON object keys silently collapse on parse."""
    text = BUN_LOCK.read_text(encoding="utf-8")
    keys = re.findall(r'^ {4}"([^"]+)": \[', text, flags=re.MULTILINE)
    data = _parse_bun_lock()
    assert len(keys) == len(set(keys)), "duplicate package keys found in bun.lock"
    assert len(keys) == len(data["packages"])


def test_bun_lock_every_package_entry_has_resolved_spec_and_sha512_integrity():
    """Every resolved package tuple must carry a name@version and an integrity hash."""
    data = _parse_bun_lock()
    for name, entry in data["packages"].items():
        assert isinstance(entry, list) and len(entry) >= 4, f"{name}: malformed package entry"
        resolved_spec = entry[0]
        assert "@" in resolved_spec, f"{name}: missing resolved version spec"
        integrity = entry[-1]
        assert integrity.startswith("sha512-"), f"{name}: missing sha512 integrity hash"