"""Shared eval-suite fixtures for doctor/triage tests (Issue #256).

Provides the green-doctor double factory and Layer-A repo-root isolation.
No production behaviour lives here.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from git_cg.eval.binding import paths as binding_paths


def _make_doctor_double(
    *,
    green: bool = True,
    exit_code: int = 0,
    suite_id: str | None = "s",
    block_failures: list[str] | None = None,
    warn_failures: list[str] | None = None,
    checks: list[Any] | None = None,
    scores: list[Any] | None = None,
) -> SimpleNamespace:
    """Build a DoctorReport-shaped double for triage/doctor tests.

    Surface: ``green``, ``exit_code``, and ``to_data()`` with
    ``block_failures`` / ``warn_failures``.
    """
    block = list(block_failures or [])
    warn = list(warn_failures or [])
    check_rows = list(checks or [])
    score_rows = list(scores or [])

    def to_data() -> dict[str, Any]:
        return {
            "green": green,
            "exit_code": exit_code,
            "suite_id": suite_id,
            "checks": check_rows,
            "scores": score_rows,
            "block_failures": block,
            "warn_failures": warn,
        }

    return SimpleNamespace(
        green=green,
        exit_code=exit_code,
        suite_id=suite_id,
        checks=tuple(check_rows),
        scores=tuple(score_rows),
        block_failures=block,
        warn_failures=warn,
        to_data=to_data,
    )


@pytest.fixture
def make_doctor_double() -> Callable[..., SimpleNamespace]:
    """Factory fixture for doctor doubles."""
    return _make_doctor_double


@pytest.fixture()
def isolated_eval_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect ``resolve_repo_root`` to an isolated git root.

    Prevents checkpoint/queue scans from reading the developer's real
    ``.eval/`` workspace during doctor/triage CLI tests.

    Doctor CLI tests keep the domain alias ``clean_doctor_repo``.
    """
    (tmp_path / ".git").mkdir(exist_ok=True)
    monkeypatch.setattr(binding_paths, "resolve_repo_root", lambda start=None: tmp_path)
    return tmp_path
