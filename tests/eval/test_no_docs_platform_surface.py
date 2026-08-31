"""Guard: eval interaction work must not ship docs-platform / autodoc / REST surfaces.

Thin operator notes may live under ``docs/eval/**`` and generated ``docs/cli/**``.
Inspects the current branch diff against ``origin/main`` / ``main`` / ``master``
so pre-existing product docs outside this workstream are not false positives.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_FORBIDDEN_NAMES = {
    "mkdocs.yml",
    "mkdocs.yaml",
    "zensical.toml",
    "zensical.yml",
    "openapi.yaml",
    "openapi.yml",
    "openapi.json",
    "swagger.yaml",
    "swagger.yml",
    "swagger.json",
}
_FORBIDDEN_PATH_PREFIXES = (
    "docs/api/",
    "docs/rest/",
    "docs/openapi/",
    "docs/swagger/",
    "docs/autodoc/",
    "docs/mkdocstrings/",
    "docs/site/",
)
_FORBIDDEN_NAME_TOKENS = (
    "mkdocs",
    "zensical",
    "mkdocstrings",
    "autodoc",
    "openapi",
    "swagger",
)


def _git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return ""
    return completed.stdout


def _resolve_base_ref() -> str | None:
    for candidate in ("origin/main", "main", "origin/master", "master"):
        probe = subprocess.run(
            ["git", "rev-parse", "--verify", candidate],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if probe.returncode == 0:
            return candidate
    return None


def _changed_paths(base_ref: str) -> list[str]:
    merge_base = _git_output("merge-base", "HEAD", base_ref).strip() or base_ref
    committed = _git_output("diff", "--name-only", "--diff-filter=ACMR", f"{merge_base}...HEAD")
    unstaged = _git_output("diff", "--name-only", "--diff-filter=ACMR", "HEAD")
    staged = _git_output("diff", "--name-only", "--diff-filter=ACMR", "--cached")
    paths = {
        line.strip().replace("\\", "/")
        for blob in (committed, unstaged, staged)
        for line in blob.splitlines()
        if line.strip()
    }
    return sorted(paths)


def _is_forbidden(path: str) -> bool:
    normalized = path.replace("\\", "/")
    name = Path(normalized).name.lower()
    if name in _FORBIDDEN_NAMES:
        return True
    if any(normalized.startswith(prefix) or normalized == prefix.rstrip("/") for prefix in _FORBIDDEN_PATH_PREFIXES):
        return True
    # Historical ADR filenames may mention deferred platforms; ignore those.
    if normalized.startswith("docs/ADRs/"):
        return False
    if any(tok in name for tok in _FORBIDDEN_NAME_TOKENS):
        return True
    return normalized.startswith("src/") and any(tok in normalized.lower() for tok in _FORBIDDEN_NAME_TOKENS)


def test_branch_diff_excludes_docs_platform_surface() -> None:
    base_ref = _resolve_base_ref()
    if base_ref is None:
        return

    hits = [path for path in _changed_paths(base_ref) if _is_forbidden(path)]
    assert not hits, f"docs-platform / autodoc / REST surface present in branch diff: {hits}"
