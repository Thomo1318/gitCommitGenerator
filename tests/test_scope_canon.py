"""Slice 1 (#204) — pure scope normalisation characterisation.

Producer-side only. No #201 ontology allowlist, no gold steers, no rank mutation.
"""

from __future__ import annotations

import pytest

from git_cg.models import CommitIntent, CommitPlan, CommitType, SemVerImpact
from git_cg.regeneration import ResolvedCommitContract, enforce_semantic_contract
from git_cg.scope_canon import (
    CANONICAL_SCOPE_ALIASES,
    canonical_scope_values,
    coerce_scope_normalised_from,
    export_scope_canon,
    is_canonical_scope,
    iter_canonical_scope_aliases,
    normalize_scope,
    resolve_scope_normalisation,
)

# ---------------------------------------------------------------------------
# normalize_scope pure behaviour
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("scoped_history", "scoped-history"),
        ("scoped-hist", "scoped-history"),
        ("scoped_hist", "scoped-history"),
        ("scoped-history", "scoped-history"),
        ("main", "main"),
        ("main.py", "main"),
        ("git_cg.main", "main"),
        ("intent", "intent"),
        ("intent.py", "intent"),
        ("telemetry", "telemetry"),
        ("telemetry.py", "telemetry"),
        ("sentry", "sentry"),
        ("sentry_config", "sentry"),
        ("adr", "adr"),
        ("ADRs", "adr"),
        ("docs", "docs"),
        ("test", "test"),
        ("tests", "test"),
        ("fixtures", "fixtures"),
        ("usage", "usage"),
        ("phase9", "phase9"),
        # Defense in depth with F5-light: strip accidental path/filename forms.
        ("src/git_cg/main.py", "main"),
        ("docs/ADRs/0163.md", "adr"),
        ("docs/usage.md", "usage"),
        ("SCOPED_HISTORY", "scoped-history"),
        ("Scoped-History", "scoped-history"),
    ],
)
def test_normalize_scope_aliases(raw: str | None, expected: str | None) -> None:
    assert normalize_scope(raw) == expected


def test_normalize_scope_never_emits_filename_or_snake_when_canon_exists() -> None:
    """TIP-G9 / F1: never leave snake or basename forms when a canon entry exists."""
    forbidden_final = {
        "scoped_history",
        "scoped_hist",
        "scoped-hist",
        "main.py",
        "intent.py",
        "telemetry.py",
        "sentry_config",
    }
    for raw in list(CANONICAL_SCOPE_ALIASES) + list(forbidden_final):
        out = normalize_scope(raw)
        assert out is None or out not in forbidden_final
        if out is not None:
            assert ".py" not in out
            assert "/" not in out
            assert "\\" not in out


def test_canonical_scope_aliases_is_nonempty_mapping() -> None:
    assert isinstance(CANONICAL_SCOPE_ALIASES, dict)
    assert CANONICAL_SCOPE_ALIASES
    # Every value must itself normalise to the same canonical slug.
    for alias, canonical in CANONICAL_SCOPE_ALIASES.items():
        assert normalize_scope(alias) == canonical
        assert normalize_scope(canonical) == canonical


# ---------------------------------------------------------------------------
# I-12 choke-points: preferred_scope must pass through normalize_scope
# ---------------------------------------------------------------------------


def _plan(scope: str = "ui") -> CommitPlan:
    return CommitPlan(
        primary_intent=CommitIntent(
            intent_id="bug",
            gitmoji="🐛",
            cc_type=CommitType.FIX,
            scope=scope,
            description="Fix a bug",
            semver_impact=SemVerImpact.PATCH,
            changelog_group="Bug Fixes",
        ),
        secondary_intents=[],
        split_recommended=False,
        rationale="Fix.",
        body_summary=None,
        breaking_change=False,
        breaking_change_description=None,
    )


def _contract() -> ResolvedCommitContract:
    return ResolvedCommitContract(
        primary_intent_id="bug",
        gitmoji="🐛",
        cc_type="fix",
        semver_impact="PATCH",
        changelog_group="Bug Fixes",
        secondary_intent_ids=[],
    )


def test_enforce_semantic_contract_normalises_preferred_scope_snake() -> None:
    """I-12: regeneration.py:256 path — preferred_scope=scoped_history → scoped-history."""
    out = enforce_semantic_contract(
        _plan(),
        _contract(),
        active_directives={"preferred_scope": "scoped_history"},
    )
    assert out.primary_intent.scope == "scoped-history"


def test_enforce_semantic_contract_normalises_preferred_scope_filename() -> None:
    out = enforce_semantic_contract(
        _plan(),
        _contract(),
        active_directives={"preferred_scope": "main.py"},
    )
    assert out.primary_intent.scope == "main"


def test_enforce_semantic_contract_preserves_already_canonical_scope() -> None:
    out = enforce_semantic_contract(
        _plan(),
        _contract(),
        active_directives={"preferred_scope": "api"},
    )
    assert out.primary_intent.scope == "api"


# ---------------------------------------------------------------------------
# Issue #204 Slice 10 — resolve_scope_normalisation / coerce_scope_normalised_from
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected_canon", "expected_from"),
    [
        # Actual transformations retain the alias key that fired.
        ("scoped_history", "scoped-history", "scoped_history"),
        ("scoped-hist", "scoped-history", "scoped-hist"),
        ("scoped_hist", "scoped-history", "scoped_hist"),
        ("main.py", "main", "main.py"),
        ("git_cg.main", "main", "git_cg.main"),
        ("docs/usage.md", "usage", "usage"),
        ("docs/ADRs/foo.md", "adr", "adr"),
        ("src/git_cg/main.py", "main", "main"),  # basename alias reduces to canon token "main"
        ("sentry_config.py", "sentry", "sentry_config.py"),
        # Identity canonical inputs: no transformation → source "none".
        ("main", "main", "none"),
        ("scoped-history", "scoped-history", "none"),
        ("telemetry", "telemetry", "none"),
        ("intent", "intent", "none"),
        ("adr", "adr", "none"),
        ("usage", "usage", "none"),
        ("fixtures", "fixtures", "none"),
        ("phase9", "phase9", "none"),
        # Unknown / empty.
        ("unknown-token", "unknown-token", "none"),
        (None, None, "none"),
        ("", None, "none"),
        ("   ", None, "none"),
    ],
)
def test_resolve_scope_normalisation(raw, expected_canon, expected_from) -> None:
    canon, source = resolve_scope_normalisation(raw)
    assert canon == expected_canon
    assert source == expected_from


def test_resolve_scope_normalisation_identity_vs_transform() -> None:
    """RF-1 polish: identity canonical aliases report none; transforms keep keys."""
    assert resolve_scope_normalisation("main") == ("main", "none")
    assert resolve_scope_normalisation("main.py") == ("main", "main.py")
    assert resolve_scope_normalisation("scoped-history") == ("scoped-history", "none")
    assert resolve_scope_normalisation("scoped_history") == ("scoped-history", "scoped_history")
    assert resolve_scope_normalisation("usage") == ("usage", "none")
    assert resolve_scope_normalisation("docs/usage.md") == ("usage", "usage")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("scoped_history", "scoped_history"),
        ("main.py", "main.py"),
        ("none", "none"),
        ("", "none"),
        (None, "none"),
        ("/tmp/secret/path", "none"),
        ("not-an-alias", "none"),
        ("SCOPED_HISTORY", "scoped_history"),
    ],
)
def test_coerce_scope_normalised_from(value, expected) -> None:
    assert coerce_scope_normalised_from(value) == expected


def test_shared_canon_export_surface() -> None:
    """Stable #201-facing export helpers stay leaf-adjacent and closed."""
    aliases = iter_canonical_scope_aliases()
    assert aliases
    assert all(isinstance(a, tuple) and len(a) == 2 for a in aliases)
    values = canonical_scope_values()
    assert "scoped-history" in values
    assert "main" in values
    assert is_canonical_scope("scoped_history")
    assert is_canonical_scope("main.py")
    assert not is_canonical_scope("not-a-real-scope-token-xyz")
    snap = export_scope_canon()
    assert set(snap) == {"aliases", "canonical_values"}
    assert snap["aliases"]["scoped_history"] == "scoped-history"
    assert "telemetry" in snap["canonical_values"]
