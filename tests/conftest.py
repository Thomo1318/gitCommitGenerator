"""
Shared pytest configuration and fixtures.

Stubs out sentry_sdk before any test modules import git_cg packages, since
sentry-sdk may not be installed in the test environment and telemetry.py
calls sentry_sdk.init() at import time.

Also hosts shared builders for Issue #204 Phase 7.30 corpus/unit tests (D24).
Do not refactor legacy per-module helpers in older test modules from here.
"""

from __future__ import annotations

import sys
import types
from typing import Any

# ---------------------------------------------------------------------------
# Stub sentry_sdk before any git_cg module is imported
# ---------------------------------------------------------------------------

if "sentry_sdk" not in sys.modules:
    _sentry_stub = types.ModuleType("sentry_sdk")
    _sentry_stub.init = lambda *args, **kwargs: None
    _sentry_stub.capture_exception = lambda *args, **kwargs: None
    _sentry_stub.capture_message = lambda *args, **kwargs: None
    _sentry_stub.flush = lambda *args, **kwargs: None
    _sentry_stub.add_breadcrumb = lambda *args, **kwargs: None
    _sentry_stub.new_scope = lambda *args, **kwargs: __import__("contextlib").nullcontext()
    sys.modules["sentry_sdk"] = _sentry_stub


# ---------------------------------------------------------------------------
# D24 shared factories (Issue #204 · Phase 7.30)
# ---------------------------------------------------------------------------


def make_diff_signals(**kwargs: Any):
    """Build a ``DiffSignals`` instance from keyword overrides."""
    from git_cg.intent import DiffSignals

    return DiffSignals(**kwargs)


def make_commit_intent(
    *,
    intent_id: str = "feature_addition",
    gitmoji: str = "✨",
    cc_type: str | Any = "feat",
    scope: str | None = "api",
    description: str = "add something",
    semver_impact: str | Any = "MINOR",
    changelog_group: str = "Added",
    construct: bool = False,
    **overrides: Any,
):
    """Build a ``CommitIntent``.

    Parameters:
        construct: When True, use ``model_construct`` for deliberately illegal
            negative fixtures that must bypass matrix validation.
    """
    from git_cg.models import CommitIntent, CommitType, SemVerImpact

    payload = {
        "intent_id": intent_id,
        "gitmoji": gitmoji,
        "cc_type": CommitType(cc_type) if not isinstance(cc_type, CommitType) else cc_type,
        "scope": scope,
        "description": description,
        "semver_impact": (
            SemVerImpact(semver_impact) if not isinstance(semver_impact, SemVerImpact) else semver_impact
        ),
        "changelog_group": changelog_group,
        **overrides,
    }
    if construct:
        return CommitIntent.model_construct(**payload)
    return CommitIntent(**payload)


def make_commit_plan(
    *,
    primary: Any | None = None,
    secondary_intents: list[Any] | None = None,
    split_recommended: bool = False,
    rationale: str = "test rationale",
    body_summary: str | None = "test body",
    breaking_change: bool = False,
    breaking_change_description: str | None = None,
    construct: bool = False,
    **primary_overrides: Any,
):
    """Build a ``CommitPlan`` with optional primary overrides or a ready primary."""
    from git_cg.models import CommitPlan

    primary_intent = primary if primary is not None else make_commit_intent(**primary_overrides)
    payload = {
        "primary_intent": primary_intent,
        "secondary_intents": list(secondary_intents or []),
        "split_recommended": split_recommended,
        "rationale": rationale,
        "body_summary": body_summary,
        "breaking_change": breaking_change,
        "breaking_change_description": breaking_change_description,
    }
    if construct:
        return CommitPlan.model_construct(**payload)
    return CommitPlan(**payload)


def make_ranked_intent(
    *,
    intent_id: str = "feature_addition",
    emoji: str = "✨",
    code: str = ":sparkles:",
    cc_type: str = "feat",
    description: str = "feature addition",
    semver_impact: str = "MINOR",
    changelog_group: str = "Added",
    intent_group: str = "feature",
    score: float = 10.0,
    priority: int = 100,
    specificity: int = 100,
    split_weight: int = 100,
    selection_rule: str | None = None,
    evidence: list[str] | None = None,
    penalties: list[str] | None = None,
    construct: bool = False,
    **overrides: Any,
):
    """Build a ``RankedIntent`` for pure presentation / ranking-adjacent tests."""
    from git_cg.intent import RankedIntent

    payload = {
        "intent_id": intent_id,
        "emoji": emoji,
        "code": code,
        "cc_type": cc_type,
        "description": description,
        "semver_impact": semver_impact,
        "changelog_group": changelog_group,
        "intent_group": intent_group,
        "score": score,
        "priority": priority,
        "specificity": specificity,
        "split_weight": split_weight,
        "selection_rule": selection_rule,
        "evidence": list(evidence or []),
        "penalties": list(penalties or []),
        **overrides,
    }
    if construct:
        return RankedIntent.model_construct(**payload)
    return RankedIntent(**payload)


def make_trailer_priors(
    *,
    cc_type: str | Any = "chore",
    semver_impact: str | Any = "NONE",
    changelog_group: str = "Miscellaneous",
    scope_hint: str | None = None,
    role: str = "mixed",
    construct: bool = False,
    **overrides: Any,
):
    """Build frozen ``TrailerPriors``.

    Parameters:
        construct: When True, bypass role validation for negative fixtures.
    """
    from git_cg.models import CommitType, SemVerImpact, TrailerPriors

    payload = {
        "cc_type": CommitType(cc_type) if not isinstance(cc_type, CommitType) else cc_type,
        "semver_impact": (
            SemVerImpact(semver_impact) if not isinstance(semver_impact, SemVerImpact) else semver_impact
        ),
        "changelog_group": changelog_group,
        "scope_hint": scope_hint,
        "role": role,
        **overrides,
    }
    if construct:
        return TrailerPriors.model_construct(**payload)
    return TrailerPriors(**payload)


# ---------------------------------------------------------------------------
# Opik four-lane project-pin env scrubbing (S7-1a)
# ---------------------------------------------------------------------------

#: The canonical four-lane Opik project pins plus the legacy fallback. Scrubbed
#: together so lane-provenance / doctor tests are hermetic regardless of the
#: developer's ambient shell environment.
OPIK_PROJECT_LANE_ENV_VARS: tuple[str, ...] = (
    "GIT_CG_OPIK_PROJECT_LIVE",
    "GIT_CG_OPIK_PROJECT_EVAL",
    "GIT_CG_OPIK_PROJECT_CI",
    "GIT_CG_OPIK_PROJECT_IMPORT",
    "OPIK_PROJECT_NAME",
)


def scrub_opik_project_lanes(monkeypatch: Any) -> None:
    """Delete every Opik project-lane pin and the legacy fallback from the env.

    Shared by S7-1a lane tests in ``test_config.py`` / ``test_eval_opik_doctor.py``
    so both scrub the identical var set. Deliberately narrow: it does not touch
    the broader Opik config/secret vars those files manage per-test.
    """
    for var in OPIK_PROJECT_LANE_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
