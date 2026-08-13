"""Committed fixture discovery and loading (Lane A SoT)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from git_cg.eval.paths import REPO_ROOT

DEFAULT_FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "eval"


class FixtureLoadError(ValueError):
    """Fixture path / JSON / shape failure."""


def default_fixture_root() -> Path:
    return DEFAULT_FIXTURE_ROOT


def load_fixture_dict(path: Path | str) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        raise FixtureLoadError(f"missing fixture: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FixtureLoadError(f"invalid fixture JSON: {p}: {exc}") from exc
    if not isinstance(data, dict):
        raise FixtureLoadError(f"fixture root must be an object: {p}")
    return data


def _resolve_case_path(fixture_root: Path, rel: str) -> Path:
    candidate = (fixture_root / rel).resolve()
    root = fixture_root.resolve()
    if not str(candidate).startswith(str(root)):
        raise FixtureLoadError(f"case path escapes fixture root: {rel}")
    if not candidate.is_file():
        # allow bare case_id lookup under cases/
        alt = fixture_root / "cases" / f"{rel}.json"
        if alt.is_file():
            return alt
        # allow path without extension
        alt2 = fixture_root / f"{rel}.json"
        if alt2.is_file():
            return alt2
        raise FixtureLoadError(f"missing case fixture: {rel}")
    return candidate


def load_suite_fixtures(
    suite: dict[str, Any],
    *,
    fixture_root: Path | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    """Load ordered (case_id, fixture_dict) pairs for a suite definition."""
    root = fixture_root or default_fixture_root()
    case_ids = suite.get("case_ids")
    if not isinstance(case_ids, list) or not case_ids:
        raise FixtureLoadError("suite.case_ids must be a non-empty list")
    case_paths = suite.get("case_paths")
    if case_paths is not None and (
        not isinstance(case_paths, dict) or any(not isinstance(v, str) for v in case_paths.values())
    ):
        raise FixtureLoadError("suite.case_paths must be an object of case_id -> relative path")

    out: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    for case_id in case_ids:
        if not isinstance(case_id, str) or not case_id:
            raise FixtureLoadError(f"invalid case_id in suite: {case_id!r}")
        if case_id in seen:
            raise FixtureLoadError(f"duplicate case_id in suite: {case_id}")
        seen.add(case_id)
        if case_paths and case_id in case_paths:
            rel = case_paths[case_id]
        else:
            # default layout convention
            rel = f"cases/valid/{case_id}.json"
            # session-12 seeds often live under session-12/
            session_rel = f"cases/session-12/{case_id}.json"
            archive_rel = f"cases/204-archive/{case_id}.json"
            if (root / session_rel).is_file():
                rel = session_rel
            elif (root / archive_rel).is_file():
                rel = archive_rel
            elif not (root / rel).is_file():
                # last resort: search known trees by filename
                matches = list(root.joinpath("cases").rglob(f"{case_id}.json"))
                if len(matches) == 1:
                    rel = str(matches[0].relative_to(root))
                elif len(matches) > 1:
                    raise FixtureLoadError(f"ambiguous case fixture for {case_id}: {matches}")
        path = _resolve_case_path(root, rel)
        fixture = load_fixture_dict(path)
        # enforce case_id consistency when the fixture declares case_id
        declared = fixture.get("case_id")
        if declared is not None and declared != case_id:
            raise FixtureLoadError(f"fixture case_id {declared!r} != suite {case_id!r}")
        out.append((case_id, fixture))
    return out
