import pytest

from git_cg.intent import DiffSignals, rank_commit_intents
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
