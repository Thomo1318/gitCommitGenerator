import pytest

from git_cg.intent import DiffSignals, derive_intent_selection_constraints, matrix_row_intent_id, rank_commit_intents
from git_cg.sop import load_sop


@pytest.fixture
def sop_matrix():
    # Load the actual SOP matrix used in production
    data = load_sop()
    return data.get("gitmoji_reference_matrix", [])


def test_ranker_prefers_generic_refactor_over_move_rename_for_centralization(sop_matrix):
    """
    Given SOP-loader centralization diff signals:
    - new_shared_module = True
    - centralized_config_resolution = True
    - hook_portability = True
    - moves_or_renames_files = False

    Rank ♻️ generic_refactor above 🚚 move_rename.
    """
    # 1. Arrange: Create the specific signals
    signals = DiffSignals(
        new_shared_module=True,
        centralized_config_resolution=True,
        hook_portability=True,
        moves_or_renames_files=False,
    )

    # 2. Act: Rank the intents
    ranked = rank_commit_intents(signals, sop_matrix)

    # 3. Assert: Extract the positions of the two competing intents
    generic_refactor_idx = next(i for i, r in enumerate(ranked) if r.intent_id == "generic_refactor")
    move_rename_idx = next(i for i, r in enumerate(ranked) if r.intent_id == "move_rename")

    # Prove that generic_refactor is ranked higher (lower index) than move_rename
    assert generic_refactor_idx < move_rename_idx, (
        f"Expected 'generic_refactor' to rank higher than 'move_rename'.\n"
        f"generic_refactor score: {ranked[generic_refactor_idx].score}\n"
        f"move_rename score: {ranked[move_rename_idx].score}"
    )


def test_ranker_prefers_docs_for_markdown_only_changes(sop_matrix):
    """
    If ONLY documentation files are changed, `docs` intents should dominate
    and non-doc intents should be heavily penalized (hard vetoed).
    """
    signals = DiffSignals(only_docs=True, touches_docs=True)

    ranked = rank_commit_intents(signals, sop_matrix)

    top_intent = ranked[0]
    assert top_intent.intent_group in ("docs", "miscellaneous")

    # Prove a high-priority feature intent was penalized down the list
    feature_idx = next(i for i, r in enumerate(ranked) if r.intent_id == "feature_addition")
    assert ranked[feature_idx].score < 0, "Non-doc intents should be hard vetoed (negative score)"


def test_ranker_prefers_security_fix_for_security_changes(sop_matrix):
    """
    Security-related changes should prioritize security_privacy_fix over
    generic fixes or refactors, due to its high priority and specific positive signals.
    """
    signals = DiffSignals(touches_security=True, files=["src/auth/jwt.py", "src/secrets.py"])
    ranked = rank_commit_intents(signals, sop_matrix)

    top_intent = ranked[0]
    assert top_intent.intent_id == "security_privacy_fix"
    assert top_intent.score > 50


def test_ranker_prefers_dependency_upgrade(sop_matrix):
    """
    If the diff exclusively updates dependencies, dependency_upgrade should win.
    """
    signals = DiffSignals(
        dependency_upgraded=True,
        package_metadata_changed=True,
        only_dependency_changes=True,
        files=["pyproject.toml", "uv.lock"],
    )
    ranked = rank_commit_intents(signals, sop_matrix)

    top_intent = ranked[0]
    assert top_intent.intent_id == "dependency_upgrade"


def test_ranker_prefers_feature_over_docs_in_mixed_commit(sop_matrix):
    """
    In a mixed commit adding an API and docs, the functional change (feature)
    should rank higher than the documentation update.
    """
    signals = DiffSignals(
        adds_public_api=True, touches_docs=True, only_docs=False, files=["src/api/routes.py", "docs/api.md"]
    )
    ranked = rank_commit_intents(signals, sop_matrix)

    # Feature addition might be index 0, 1, or 2 depending on other signals,
    # but it MUST be ranked higher than documentation_update.
    feature_idx = next(i for i, r in enumerate(ranked) if r.intent_id == "feature_addition")
    docs_idx = next(i for i, r in enumerate(ranked) if r.intent_id == "documentation_update")

    assert feature_idx < docs_idx, "Feature addition should outrank documentation in a mixed commit"


def test_ranker_empty_signals(sop_matrix):
    """
    Verify the ranker returns a complete, non-empty ranking when no signals are present.

    Asserts the returned list has the same length as the SOP matrix and that the top-ranked intent has a positive score.
    """
    signals = DiffSignals()
    ranked = rank_commit_intents(signals, sop_matrix)

    assert len(ranked) == len(sop_matrix)
    # The first result should be one of the intents with highest base priority/specificity
    assert ranked[0].score > 0


def test_docs_only_constraints_export_allowed_and_disallowed_intents(sop_matrix):
    signals = DiffSignals(only_docs=True)
    constraints = derive_intent_selection_constraints(signals, sop_matrix)

    expected_allowed = {
        matrix_row_intent_id(row)
        for row in sop_matrix
        if row.get("intent_group", "miscellaneous") in {"docs", "miscellaneous"}
    }
    expected_disallowed = {matrix_row_intent_id(row) for row in sop_matrix} - expected_allowed

    assert "docs_only" in constraints.reasons
    assert set(constraints.allowed_intent_ids) == expected_allowed
    assert set(constraints.disallowed_intent_ids) == expected_disallowed


def test_tests_only_constraints_export_allowed_and_disallowed_intents(sop_matrix):
    signals = DiffSignals(only_tests=True)
    constraints = derive_intent_selection_constraints(signals, sop_matrix)

    expected_allowed = {
        matrix_row_intent_id(row)
        for row in sop_matrix
        if row.get("intent_group", "miscellaneous") in {"tests", "miscellaneous"}
    }
    expected_disallowed = {matrix_row_intent_id(row) for row in sop_matrix} - expected_allowed

    assert "tests_only" in constraints.reasons
    assert set(constraints.allowed_intent_ids) == expected_allowed
    assert set(constraints.disallowed_intent_ids) == expected_disallowed


def test_dependency_only_constraints_export_allowed_and_disallowed_intents(sop_matrix):
    signals = DiffSignals(only_dependency_changes=True)
    constraints = derive_intent_selection_constraints(signals, sop_matrix)

    expected_allowed = {
        matrix_row_intent_id(row)
        for row in sop_matrix
        if row.get("intent_group", "miscellaneous") in {"runtime_build_package", "miscellaneous"}
    }
    expected_disallowed = {matrix_row_intent_id(row) for row in sop_matrix} - expected_allowed

    assert "dependency_only" in constraints.reasons
    assert set(constraints.allowed_intent_ids) == expected_allowed
    assert set(constraints.disallowed_intent_ids) == expected_disallowed


def test_unconstrained_diff_exports_empty_constraint_sets(sop_matrix):
    constraints = derive_intent_selection_constraints(DiffSignals(), sop_matrix)

    assert constraints.reasons == []
    assert constraints.allowed_intent_ids == []
    assert constraints.disallowed_intent_ids == []


# --- Issue #182 Slice 1: B1 ranker close bars + keep-green + shared snapshot ---


def test_b1_release_notes_product_ranks_feature_addition(sop_matrix):
    """Close bar: #181-class product surface with error-handling noise ranks feat/MINOR/Added.

    Locks the negatives lever: ``new_user_facing_capability``/``new_api`` in
    ``error_handling.negative_signals`` flips the both-signals case from
    error_handling @ 100.5 (HEAD miss) to feature_addition @ 80.0.
    """
    signals = DiffSignals(
        adds_public_api=True,
        error_handling_added=True,
        files=["src/git_cg/release.py"],
    )
    ranked = rank_commit_intents(signals, sop_matrix)
    top = ranked[0]
    assert top.intent_id == "feature_addition"
    assert top.cc_type == "feat"
    assert top.semver_impact == "MINOR"
    assert top.changelog_group == "Added"


def test_b1_release_bugfix_pure_ranks_fix(sop_matrix):
    """Close bar: pure repair on an existing release helper stays fix/PATCH."""
    signals = DiffSignals(
        error_handling_added=True,
        validation_added=True,
        files=["src/git_cg/release.py"],
    )
    ranked = rank_commit_intents(signals, sop_matrix)
    top = ranked[0]
    assert top.cc_type == "fix"
    assert top.semver_impact == "PATCH"


def test_b1_error_handling_only_does_not_flip_to_feat(sop_matrix):
    """Close bar: error-handling-only hardening is not re-ranked as a feature."""
    signals = DiffSignals(error_handling_added=True, files=["src/git_cg/main.py"])
    ranked = rank_commit_intents(signals, sop_matrix)
    top = ranked[0]
    assert top.intent_id == "error_handling"
    assert top.cc_type == "fix"
    assert top.semver_impact == "PATCH"


def test_negatives_lever_keeps_error_only_score_byte_identical(sop_matrix):
    """Keep-green guard: the negatives lever must not move the error-only score.

    ``B1_error_handling_only`` / ``bug_fix_error_handling`` have no product markers
    active, so the new negatives never intersect; the error_handling row stays at
    the HEAD-verified 100.5.
    """
    signals = DiffSignals(error_handling_added=True, files=["src/git_cg/main.py"])
    ranked = rank_commit_intents(signals, sop_matrix)
    error_row = next(r for r in ranked if r.intent_id == "error_handling")
    assert error_row.score == 100.5


def test_shared_ranked_snapshot_is_reused_for_prompt(sop_matrix):
    """Regression: the shared ranked snapshot is passed through, not re-ranked.

    Guards the ``ranked_candidates=gen_context.ranked_intents`` short-circuit: when
    candidates are supplied, ``build_system_prompt`` must not re-run the ranker.
    """
    from unittest.mock import patch

    from git_cg.main import build_system_prompt

    diff = "diff --git a/src/git_cg/release.py b/src/git_cg/release.py\n"
    shared = rank_commit_intents(DiffSignals(adds_public_api=True), sop_matrix)

    with patch("git_cg.main.rank_commit_intents", side_effect=AssertionError("re-ranked")) as mock_rank:
        prompt = build_system_prompt(diff, ranked_candidates=shared)
    mock_rank.assert_not_called()
    assert "PRIMARY CANDIDATES" in prompt
