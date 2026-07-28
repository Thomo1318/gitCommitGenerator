"""Tests for the new Bun lockfile (bun.lock) shipped alongside package.json.

bun.lock is JSONC (comments + trailing commas). These tests parse it with a
JSONC-aware helper and cross-check structure against package.json, which is
the authoritative source for declared dependency ranges.
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
BUN_LOCK = REPO_ROOT / "bun.lock"
PACKAGE_JSON = REPO_ROOT / "package.json"

_LINE_COMMENT = re.compile(r"(^|[^:])//.*?$", re.MULTILINE)
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")


def _strip_jsonc(text: str) -> str:
    """Remove JSONC comments and trailing commas without touching string values.

    Uses a simple state machine so // and /* */ inside quoted strings are kept.
    """
    out: list[str] = []
    i = 0
    n = len(text)
    in_string = False
    escape = False
    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        # not in string
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n:
            nxt = text[i + 1]
            if nxt == "/":
                i += 2
                while i < n and text[i] not in "\n\r":
                    i += 1
                continue
            if nxt == "*":
                i += 2
                while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                    i += 1
                i = min(i + 2, n)
                continue
        out.append(ch)
        i += 1
    stripped = "".join(out)
    # Drop trailing commas before } or ]
    prev = None
    while prev != stripped:
        prev = stripped
        stripped = _TRAILING_COMMA.sub(r"\1", stripped)
    return stripped


class _DuplicateKeyError(ValueError):
    """Raised when a JSON object contains repeated keys."""


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    """object_pairs_hook that fails closed on duplicate keys."""
    seen: set[str] = set()
    result: dict = {}
    for key, value in pairs:
        if key in seen:
            raise _DuplicateKeyError(f"duplicate JSON key: {key!r}")
        seen.add(key)
        result[key] = value
    return result


def _parse_bun_lock(*, reject_duplicates: bool = False) -> dict:
    """Parse bun.lock JSONC into a plain dict.

    Args:
        reject_duplicates: When True, raise if any object has repeated keys.

    Returns:
        dict: The parsed lockfile document.
    """
    text = BUN_LOCK.read_text(encoding="utf-8")
    cleaned = _strip_jsonc(text)
    hook = _reject_duplicate_keys if reject_duplicates else None
    return json.loads(cleaned, object_pairs_hook=hook)


def _package_json() -> dict:
    return json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))


def _declared_dependencies(pkg: dict) -> dict[str, str]:
    """Merge dependencies + devDependencies from package.json."""
    declared: dict[str, str] = {}
    for section in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        block = pkg.get(section) or {}
        if isinstance(block, dict):
            declared.update({str(k): str(v) for k, v in block.items()})
    return declared


def _version_from_resolved_spec(package_key: str, resolved_spec: str) -> str:
    """Extract version from a bun lock resolved spec relative to package key."""
    # Scoped: @scope/name@version  Unscoped: name@version
    if resolved_spec.startswith(package_key + "@"):
        return resolved_spec[len(package_key) + 1 :]
    # Fallback: last @ segment (unscoped only)
    if package_key.startswith("@"):
        raise AssertionError(f"{package_key}: resolved_spec {resolved_spec!r} missing key prefix")
    return resolved_spec.rsplit("@", 1)[-1]


def _parse_semver(version: str) -> tuple[int, int, int]:
    core = version.split("-", 1)[0].split("+", 1)[0]
    parts = core.split(".")
    major = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
    minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    patch = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    return major, minor, patch


def _satisfies_caret(version: str, range_spec: str) -> bool:
    """Minimal caret (^x.y.z) checker used by package.json ranges in this repo."""
    assert range_spec.startswith("^"), f"unsupported range (expected caret): {range_spec}"
    base = range_spec[1:]
    v = _parse_semver(version)
    b = _parse_semver(base)
    if b[0] > 0:
        return v[0] == b[0] and v >= b
    if b[1] > 0:
        return v[0] == 0 and v[1] == b[1] and v >= b
    return v[0] == 0 and v[1] == 0 and v[2] == b[2] and v >= b


def _is_valid_sha512_integrity(value: str) -> bool:
    if not isinstance(value, str) or not value.startswith("sha512-"):
        return False
    digest = value[len("sha512-") :]
    if not digest:
        return False
    try:
        # URL-safe Base64 (Bun may omit padding)
        padded = digest + "=" * (-len(digest) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        return len(raw) == 64  # sha512 digest length
    except Exception:
        return False


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
    """Every package.json dependency must resolve in bun.lock packages with a matching range."""
    data = _parse_bun_lock()
    packages = data["packages"]
    declared = _declared_dependencies(_package_json())
    assert declared, "package.json must declare at least one dependency"
    for name, range_spec in declared.items():
        assert name in packages, f"{name}: missing from bun.lock packages"
        entry = packages[name]
        assert isinstance(entry, list) and entry, f"{name}: empty package entry"
        resolved_spec = entry[0]
        assert resolved_spec.startswith(name + "@"), (
            f"{name}: resolved_spec {resolved_spec!r} must start with package key"
        )
        version = _version_from_resolved_spec(name, resolved_spec)
        if range_spec.startswith("^"):
            assert _satisfies_caret(version, range_spec), f"{name}: version {version} does not satisfy {range_spec}"
        else:
            # Exact pin or other range: at least ensure non-empty version token
            assert version, f"{name}: empty resolved version"


def test_bun_lock_has_no_duplicate_top_level_package_keys():
    """Regression guard: duplicate JSON object keys silently collapse on parse."""
    # Full-document parse with duplicate-aware hook (indentation-independent).
    data = _parse_bun_lock(reject_duplicates=True)
    # Also ensure packages mapping itself has unique keys (dict invariant).
    assert len(data["packages"]) == len(set(data["packages"]))


def _resolved_spec_matches_package_key(package_key: str, resolved_spec: str) -> bool:
    """True if resolved_spec is package@version for the lock key (incl. scoped/nested)."""
    if not isinstance(resolved_spec, str) or "@" not in resolved_spec:
        return False
    if package_key.startswith("@"):
        # Scoped top-level: @scope/name@version
        return resolved_spec.startswith(package_key + "@")
    if "/" in package_key:
        # Nested bun keys (e.g. dom-serializer/entities) resolve as leaf name@version
        leaf = package_key.rsplit("/", 1)[-1]
        return resolved_spec.startswith(leaf + "@")
    return resolved_spec.startswith(package_key + "@")


def test_bun_lock_every_package_entry_has_resolved_spec_and_sha512_integrity():
    """Every resolved package tuple must carry a key@version and a valid sha512 integrity."""
    data = _parse_bun_lock()
    for name, entry in data["packages"].items():
        assert isinstance(entry, list) and len(entry) >= 4, f"{name}: malformed package entry"
        resolved_spec = entry[0]
        assert _resolved_spec_matches_package_key(name, resolved_spec), (
            f"{name}: resolved_spec {resolved_spec!r} must be package@version for key"
        )
        integrity = entry[-1]
        assert _is_valid_sha512_integrity(integrity), f"{name}: invalid sha512 integrity {integrity!r}"
