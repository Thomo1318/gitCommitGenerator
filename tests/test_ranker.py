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
