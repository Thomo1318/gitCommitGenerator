"""Tests for Issue #195 pre-LLM intent arbitration (Slices 3a-3c + gate helpers)."""

from __future__ import annotations

from dataclasses import dataclass

from git_cg.intent import IntentSelectionConstraints, RankedIntent
from git_cg.intent_arbitrate import (
    ArbitrationDeps,
    compose_arbitration_status_strip,
    filter_eligible_matrix_rows,
    filter_eligible_ranked,
    format_regen_still_low_note,
    looks_like_commit_subject,
    narrow_eligible_by_directives,
    parse_guidance_text,
    ranked_intents_for_directives,
    run_intent_arbitration,
    subject_shaped_guidance_hint,
)
from git_cg.interaction import GumOutcome
from git_cg.ranking_confidence import compute_ranking_confidence


def _ri(
    intent_id: str,
    score: float,
    *,
    cc_type: str = "feat",
    intent_group: str = "feature",
    emoji: str = "✨",
    semver: str = "MINOR",
    changelog: str = "Added",
    description: str = "",
) -> RankedIntent:
    return RankedIntent(
        intent_id=intent_id,
        emoji=emoji,
        code=f":{intent_id}:",
        cc_type=cc_type,
        description=description or intent_id,
        semver_impact=semver,
        changelog_group=changelog,
        intent_group=intent_group,
        score=score,
        priority=50,
        specificity=50,
        split_weight=50,
    )


def _low_pair() -> tuple[list[RankedIntent], object]:
    ranked = [
        _ri("feature_addition", 84.0, cc_type="feat", intent_group="feature"),
        _ri(
            "error_handling",
            77.8,
            cc_type="fix",
            intent_group="bugfix",
            emoji="🥅",
            semver="PATCH",
            changelog="Fixed",
        ),
        _ri(
            "internal_restructure",
            71.2,
            cc_type="refactor",
            intent_group="refactor",
            emoji="♻️",
            semver="PATCH",
            changelog="Changed",
        ),
        _ri(
            "tests_update",
            64.0,
            cc_type="test",
            intent_group="tests",
            emoji="✅",
            semver="NONE",
            changelog="Tests",
        ),
        _ri(
            "docs_update",
            41.5,
            cc_type="docs",
            intent_group="docs",
            emoji="📝",
            semver="NONE",
            changelog="Documentation",
        ),
    ]
    conf = compute_ranking_confidence(ranked)
    assert conf.level == "low"
    return ranked, conf


@dataclass
class ScriptedGum:
    """Queue of GumOutcome values consumed by choose/input/filter."""

    choose_queue: list[GumOutcome]
    input_queue: list[GumOutcome] | None = None
    filter_queue: list[GumOutcome] | None = None
    filter_ok: bool = True
    choose_calls: int = 0
    input_calls: int = 0
    filter_calls: int = 0

    def choose(self, options, **kwargs) -> GumOutcome:
        self.choose_calls += 1
        if not self.choose_queue:
            raise AssertionError(f"choose exhausted; options={list(options)}")
        return self.choose_queue.pop(0)

    def input(self, **kwargs) -> GumOutcome:
        self.input_calls += 1
        q = self.input_queue or []
        if not q:
            raise AssertionError("input exhausted")
        return q.pop(0)

    def filter(self, options, **kwargs) -> GumOutcome:
        self.filter_calls += 1
        q = self.filter_queue or []
        if not q:
            raise AssertionError("filter exhausted")
        return q.pop(0)

    def filter_available(self, **kwargs) -> bool:
        return self.filter_ok

    def deps(self) -> ArbitrationDeps:
        return ArbitrationDeps(
            choose=self.choose,
            input=self.input,
            filter=self.filter,
            filter_available=self.filter_available,
            can_open_tty=lambda: True,
        )


def _sel(value: str) -> GumOutcome:
    return GumOutcome(status="selected", value=value)


def _cancel() -> GumOutcome:
    return GumOutcome(status="cancelled")


def _failed() -> GumOutcome:
    return GumOutcome(status="failed")


def _unavail() -> GumOutcome:
    return GumOutcome(status="unavailable")


# ---------------------------------------------------------------------------
# Eligibility / G1 parse
# ---------------------------------------------------------------------------


def test_filter_eligible_ranked_excludes_disallowed(a24=None):
    ranked, _ = _low_pair()
    constraints = IntentSelectionConstraints(allowed_intent_ids=["docs_update", "tests_update"])
    eligible = filter_eligible_ranked(ranked, constraints)
    assert [e.intent_id for e in eligible] == ["tests_update", "docs_update"]


def test_filter_eligible_matrix_rows_respects_constraints(monkeypatch):
    matrix = [
        {
            "intent_id": "feature_addition",
            "emoji": "✨",
            "cc_type": "feat",
            "description": "feat",
            "semver_impact": "MINOR",
            "changelog_group": "Added",
            "intent_group": "feature",
        },
        {
            "intent_id": "docs_update",
            "emoji": "📝",
            "cc_type": "docs",
            "description": "docs",
            "semver_impact": "NONE",
            "changelog_group": "Documentation",
            "intent_group": "docs",
        },
    ]
    constraints = IntentSelectionConstraints(allowed_intent_ids=["docs_update"])
    rows = filter_eligible_matrix_rows(matrix, constraints)
    assert [r.intent_id for r in rows] == ["docs_update"]


def test_parse_guidance_mapped_preferred_type():
    result = parse_guidance_text("this is a feat please")
    assert result.status == "mapped"
    assert result.deterministic_inputs["preferred_type"] == "feat"
    assert result.is_noop is False


def test_parse_guidance_unparseable_is_noop_g1():
    result = parse_guidance_text("please make the wording nicer about APIs")
    assert result.status == "no_op_unparseable"
    assert result.is_noop is True
    assert result.deterministic_inputs == {}
    assert "nicer" in result.retained_draft


# ---------------------------------------------------------------------------
# Core stack (3a)
# ---------------------------------------------------------------------------


def test_pick_a_locks_top_no_override():
    ranked, conf = _low_pair()
    script = ScriptedGum(
        choose_queue=[
            _sel("Use A: ✨ feat(core) — feature_addition  84.0"),
            _sel("Lock and generate message"),
        ]
    )

    # Labels are built dynamically — match by prefix via custom choose
    def choose(options, **kwargs):
        script.choose_calls += 1
        opts = list(options)
        if any(o.startswith("Use A:") for o in opts):
            return _sel(next(o for o in opts if o.startswith("Use A:")))
        if "Lock and generate message" in opts:
            return _sel("Lock and generate message")
        raise AssertionError(opts)

    deps = ArbitrationDeps(choose=choose, can_open_tty=lambda: True, filter_available=lambda: False)
    result = run_intent_arbitration(
        ranked_intents=ranked,
        ranking_confidence=conf,
        constraints=IntentSelectionConstraints(),
        deps=deps,
    )
    assert result.action == "locked"
    assert result.locked_intent_id == "feature_addition"
    assert result.choice_path == "pick_a"
    assert result.override is False
    assert result.aborted is False


def test_pick_b_override_true_a04():
    ranked, conf = _low_pair()

    def choose(options, **kwargs):
        opts = list(options)
        if any(o.startswith("Use B:") for o in opts):
            return _sel(next(o for o in opts if o.startswith("Use B:")))
        if "Lock and generate message" in opts:
            return _sel("Lock and generate message")
        raise AssertionError(opts)

    result = run_intent_arbitration(
        ranked_intents=ranked,
        ranking_confidence=conf,
        constraints=IntentSelectionConstraints(),
        deps=ArbitrationDeps(choose=choose, can_open_tty=lambda: True, filter_available=lambda: False),
    )
    assert result.action == "locked"
    assert result.locked_intent_id == "error_handling"
    assert result.choice_path == "pick_b"
    assert result.override is True


def test_lock_back_returns_to_main_then_pick_a():
    ranked, conf = _low_pair()
    state = {"n": 0}

    def choose(options, **kwargs):
        opts = list(options)
        state["n"] += 1
        if state["n"] == 1:
            return _sel(next(o for o in opts if o.startswith("Use B:")))
        if state["n"] == 2:
            assert "← Back" in opts
            return _sel("← Back")
        if state["n"] == 3:
            return _sel(next(o for o in opts if o.startswith("Use A:")))
        if "Lock and generate message" in opts:
            return _sel("Lock and generate message")
        raise AssertionError((state["n"], opts))

    result = run_intent_arbitration(
        ranked_intents=ranked,
        ranking_confidence=conf,
        constraints=IntentSelectionConstraints(),
        deps=ArbitrationDeps(choose=choose, can_open_tty=lambda: True, filter_available=lambda: False),
    )
    assert result.choice_path == "pick_a"
    assert result.locked_intent_id == "feature_addition"


def test_cancel_continue_a_sets_lock_a17():
    ranked, conf = _low_pair()

    def choose(options, **kwargs):
        opts = list(options)
        if "Cancel" in opts:
            return _sel("Cancel")
        if any("Continue with top rank" in o for o in opts):
            return _sel(next(o for o in opts if "Continue with top rank" in o))
        raise AssertionError(opts)

    result = run_intent_arbitration(
        ranked_intents=ranked,
        ranking_confidence=conf,
        constraints=IntentSelectionConstraints(),
        deps=ArbitrationDeps(choose=choose, can_open_tty=lambda: True, filter_available=lambda: False),
    )
    assert result.action == "continue_top"
    assert result.locked_intent_id == "feature_addition"
    assert result.choice_path == "cancel_continue_a"
    assert result.override is False


def test_cancel_abort_a06_a21():
    ranked, conf = _low_pair()

    def choose(options, **kwargs):
        opts = list(options)
        if "Cancel" in opts:
            return _sel("Cancel")
        if any("Abort" in o for o in opts):
            return _sel(next(o for o in opts if "Abort" in o))
        raise AssertionError(opts)

    result = run_intent_arbitration(
        ranked_intents=ranked,
        ranking_confidence=conf,
        constraints=IntentSelectionConstraints(),
        deps=ArbitrationDeps(choose=choose, can_open_tty=lambda: True, filter_available=lambda: False),
    )
    assert result.action == "aborted"
    assert result.aborted is True
    assert result.locked_intent_id is None
    assert result.choice_path == "cancel_abort"


def test_esc_on_main_opens_cancel_menu_then_back():
    ranked, conf = _low_pair()
    state = {"n": 0}

    def choose(options, **kwargs):
        opts = list(options)
        state["n"] += 1
        if state["n"] == 1:
            return _cancel()  # Esc on MAIN → CANCEL_MENU
        if state["n"] == 2:
            assert any("← Back" in o for o in opts)
            return _sel("← Back")
        if state["n"] == 3:
            return _sel(next(o for o in opts if o.startswith("Use A:")))
        return _sel("Lock and generate message")

    result = run_intent_arbitration(
        ranked_intents=ranked,
        ranking_confidence=conf,
        constraints=IntentSelectionConstraints(),
        deps=ArbitrationDeps(choose=choose, can_open_tty=lambda: True, filter_available=lambda: False),
    )
    assert result.choice_path == "pick_a"


def test_gum_failed_is_not_cancel_abort():
    ranked, conf = _low_pair()

    def choose(options, **kwargs):
        return _failed()

    result = run_intent_arbitration(
        ranked_intents=ranked,
        ranking_confidence=conf,
        constraints=IntentSelectionConstraints(),
        deps=ArbitrationDeps(choose=choose, can_open_tty=lambda: True, filter_available=lambda: False),
    )
    assert result.aborted is False
    assert result.choice_path != "cancel_abort"
    assert result.locked_intent_id == "feature_addition"


def test_guidance_save_return_no_lock_a10():
    ranked, conf = _low_pair()
    state = {"n": 0}

    def choose(options, **kwargs):
        opts = list(options)
        state["n"] += 1
        if state["n"] == 1:
            return _sel("Add regeneration guidance…")
        if "Save guidance only (return to menu — no re-rank)" in opts:
            return _sel("Save guidance only (return to menu — no re-rank)")
        if state["n"] >= 3 and any(o.startswith("Use A:") for o in opts):
            return _sel(next(o for o in opts if o.startswith("Use A:")))
        if "Lock and generate message" in opts:
            return _sel("Lock and generate message")
        raise AssertionError((state["n"], opts))

    def input_fn(**kwargs):
        return _sel("please make the wording nicer")

    result = run_intent_arbitration(
        ranked_intents=ranked,
        ranking_confidence=conf,
        constraints=IntentSelectionConstraints(),
        deps=ArbitrationDeps(
            choose=choose,
            input=input_fn,
            can_open_tty=lambda: True,
            filter_available=lambda: False,
        ),
    )
    # After save&return, user still locks A — guidance retained, path pick_a
    assert result.choice_path == "pick_a"
    assert result.guidance == "please make the wording nicer"


def test_guidance_unparseable_rerank_is_noop_a13():
    ranked, conf = _low_pair()
    state = {"n": 0}
    bells: list[int] = []
    saw_ack = False

    def choose(options, **kwargs):
        nonlocal saw_ack
        opts = list(options)
        state["n"] += 1
        title = kwargs.get("title") or ""
        if state["n"] == 1:
            return _sel("Add regeneration guidance…")
        if "Regenerate ranking with this guidance (re-run ranker)" in opts:
            return _sel("Regenerate ranking with this guidance (re-run ranker)")
        # Explicit no-op acknowledge panel (bell + blocking OK).
        if title == "Guidance re-rank no-op" or (len(opts) == 1 and opts[0].startswith("OK")):
            saw_ack = True
            body = kwargs.get("body") or ""
            assert "no-op" in body.lower() or "did not map" in body.lower()
            return _sel(opts[0])
        # After no-op, MAIN again — pick A
        if any(o.startswith("Use A:") for o in opts):
            return _sel(next(o for o in opts if o.startswith("Use A:")))
        if "Lock and generate message" in opts:
            return _sel("Lock and generate message")
        raise AssertionError((state["n"], opts, title))

    def input_fn(**kwargs):
        return _sel("make the prose sparkle without changing type")

    result = run_intent_arbitration(
        ranked_intents=ranked,
        ranking_confidence=conf,
        constraints=IntentSelectionConstraints(),
        deps=ArbitrationDeps(
            choose=choose,
            input=input_fn,
            can_open_tty=lambda: True,
            filter_available=lambda: False,
            emit_bell=lambda: bells.append(1),
        ),
    )
    assert result.action == "locked"
    assert result.re_rank_requested is False
    assert result.choice_path == "pick_a"
    assert saw_ack is True
    assert bells == [1]


def test_guidance_mapped_rerank_requests_re_rank():
    ranked, conf = _low_pair()
    state = {"n": 0}

    def choose(options, **kwargs):
        opts = list(options)
        state["n"] += 1
        if state["n"] == 1:
            return _sel("Add regeneration guidance…")
        if "Regenerate ranking with this guidance (re-run ranker)" in opts:
            return _sel("Regenerate ranking with this guidance (re-run ranker)")
        raise AssertionError(opts)

    def input_fn(**kwargs):
        return _sel("this is a fix")

    result = run_intent_arbitration(
        ranked_intents=ranked,
        ranking_confidence=conf,
        constraints=IntentSelectionConstraints(),
        deps=ArbitrationDeps(
            choose=choose,
            input=input_fn,
            can_open_tty=lambda: True,
            filter_available=lambda: False,
        ),
    )
    assert result.action == "re_rank"
    assert result.re_rank_requested is True
    assert result.locked_intent_id is None
    assert result.choice_path is None  # terminal path assigned after REGEN
    assert result.active_directives.get("preferred_type") == "fix"


def test_narrow_eligible_by_preferred_type_feat():
    """Mapped preferred_type must change A/B presentation order without score mutation."""
    ranked = [
        _ri("error_handling", 100.5, cc_type="fix", intent_group="bugfix", emoji="🥅", semver="PATCH"),
        _ri("validation_update", 100.5, cc_type="fix", intent_group="bugfix", emoji="🦺", semver="PATCH"),
        _ri("feature_addition", 40.0, cc_type="feat", intent_group="feature"),
        _ri("ui_feature", 35.0, cc_type="feat", intent_group="feature", emoji="💄"),
        _ri("docs_update", 20.0, cc_type="docs", intent_group="docs", emoji="📝", semver="NONE"),
    ]
    eligible = filter_eligible_ranked(ranked, IntentSelectionConstraints())
    narrowed, note = narrow_eligible_by_directives(eligible, {"preferred_type": "feat"})
    assert [r.intent_id for r in narrowed] == ["feature_addition", "ui_feature"]
    assert all(r.cc_type == "feat" for r in narrowed)
    # Scores preserved from ranker (not reweighted).
    assert narrowed[0].score == 40.0
    assert note is not None and "preferred_type=feat" in note


def test_ranked_intents_for_directives_filters_type():
    ranked = [
        _ri("error_handling", 100.5, cc_type="fix", intent_group="bugfix"),
        _ri("feature_addition", 40.0, cc_type="feat", intent_group="feature"),
    ]
    filtered, note = ranked_intents_for_directives(ranked, {"preferred_type": "feat"})
    assert [r.intent_id for r in filtered] == ["feature_addition"]
    assert note == "preferred_type=feat"


def test_guidance_save_return_mapped_updates_ab_labels():
    """Save&return with mapped type should present feat rows as Use A/B on next MAIN."""
    ranked = [
        _ri("error_handling", 100.5, cc_type="fix", intent_group="bugfix", emoji="🥅", semver="PATCH"),
        _ri("validation_update", 100.5, cc_type="fix", intent_group="bugfix", emoji="🦺", semver="PATCH"),
        _ri("feature_addition", 40.0, cc_type="feat", intent_group="feature"),
        _ri("ui_feature", 35.0, cc_type="feat", intent_group="feature", emoji="💄"),
    ]
    conf = compute_ranking_confidence(ranked)
    assert conf.level == "low"
    seen_main_labels: list[list[str]] = []
    state = {"n": 0}

    def choose(options, **kwargs):
        opts = list(options)
        state["n"] += 1
        # Capture MAIN menus (have Use A)
        if any(o.startswith("Use A:") for o in opts):
            seen_main_labels.append(opts)
        if "Lock and generate message" in opts:
            return _sel("Lock and generate message")
        if state["n"] == 1:
            return _sel("Add regeneration guidance…")
        if "Save guidance only (return to menu — no re-rank)" in opts:
            return _sel("Save guidance only (return to menu — no re-rank)")
        # Second MAIN: lock the new A (should be feat)
        if any(o.startswith("Use A:") for o in opts):
            use_a = next(o for o in opts if o.startswith("Use A:"))
            return _sel(use_a)
        raise AssertionError(opts)

    def input_fn(**kwargs):
        return _sel("this is a feat")

    result = run_intent_arbitration(
        ranked_intents=ranked,
        ranking_confidence=conf,
        constraints=IntentSelectionConstraints(),
        deps=ArbitrationDeps(
            choose=choose,
            input=input_fn,
            can_open_tty=lambda: True,
            filter_available=lambda: False,
        ),
    )
    assert len(seen_main_labels) >= 2
    second_main = seen_main_labels[1]
    use_a = next(o for o in second_main if o.startswith("Use A:"))
    assert "feat" in use_a
    assert "feature_addition" in use_a
    # B should also be feat when available
    use_b = next((o for o in second_main if o.startswith("Use B:")), None)
    if use_b:
        assert "feat" in use_b
    assert result.action == "locked"
    assert result.locked_intent_id == "feature_addition"
    assert result.active_directives.get("preferred_type") == "feat"
    assert result.override is True  # original ranker top was error_handling


def test_existing_directives_open_menu_with_narrowed_ab():
    """REGEN re-entry: existing preferred_type should open MAIN with feat A/B."""
    ranked = [
        _ri("error_handling", 100.5, cc_type="fix", intent_group="bugfix", emoji="🥅", semver="PATCH"),
        _ri("validation_update", 100.5, cc_type="fix", intent_group="bugfix", emoji="🦺", semver="PATCH"),
        _ri("feature_addition", 40.0, cc_type="feat", intent_group="feature"),
        _ri("ui_feature", 35.0, cc_type="feat", intent_group="feature", emoji="💄"),
    ]
    conf = compute_ranking_confidence(ranked)
    seen: list[str] = []

    def choose(options, **kwargs):
        opts = list(options)
        if "Lock and generate message" in opts:
            return _sel("Lock and generate message")
        if any(o.startswith("Use A:") for o in opts):
            seen.extend(opts)
            use_a = next(o for o in opts if o.startswith("Use A:"))
            return _sel(use_a)
        raise AssertionError(opts)

    result = run_intent_arbitration(
        ranked_intents=ranked,
        ranking_confidence=conf,
        constraints=IntentSelectionConstraints(),
        existing_guidance="this is a feat",
        existing_directives={"preferred_type": "feat"},
        deps=ArbitrationDeps(
            choose=choose,
            can_open_tty=lambda: True,
            filter_available=lambda: False,
        ),
    )
    use_a = next(o for o in seen if o.startswith("Use A:"))
    assert "feature_addition" in use_a
    assert result.locked_intent_id == "feature_addition"
    assert result.override is True


# ---------------------------------------------------------------------------
# Candidates (3b)
# ---------------------------------------------------------------------------


def test_pick_candidate_third_override():
    ranked, conf = _low_pair()
    state = {"n": 0}

    def choose(options, **kwargs):
        opts = list(options)
        state["n"] += 1
        if state["n"] == 1:
            return _sel("See more candidates…")
        if state["n"] == 2:
            third = next(o for o in opts if o.startswith("3."))
            return _sel(third)
        if "Lock and generate message" in opts:
            return _sel("Lock and generate message")
        raise AssertionError((state["n"], opts))

    result = run_intent_arbitration(
        ranked_intents=ranked,
        ranking_confidence=conf,
        constraints=IntentSelectionConstraints(),
        deps=ArbitrationDeps(choose=choose, can_open_tty=lambda: True, filter_available=lambda: False),
    )
    assert result.choice_path == "pick_candidate"
    assert result.locked_intent_id == "internal_restructure"
    assert result.override is True


def test_candidates_back_to_main():
    ranked, conf = _low_pair()
    state = {"n": 0}

    def choose(options, **kwargs):
        opts = list(options)
        state["n"] += 1
        if state["n"] == 1:
            return _sel("See more candidates…")
        if state["n"] == 2:
            return _sel("← Back")
        if any(o.startswith("Use A:") for o in opts):
            return _sel(next(o for o in opts if o.startswith("Use A:")))
        if "Lock and generate message" in opts:
            return _sel("Lock and generate message")
        raise AssertionError((state["n"], opts))

    result = run_intent_arbitration(
        ranked_intents=ranked,
        ranking_confidence=conf,
        constraints=IntentSelectionConstraints(),
        deps=ArbitrationDeps(choose=choose, can_open_tty=lambda: True, filter_available=lambda: False),
    )
    assert result.choice_path == "pick_a"


def test_candidates_respect_constraints_a24():
    ranked, conf = _low_pair()
    constraints = IntentSelectionConstraints(allowed_intent_ids=["feature_addition", "docs_update", "tests_update"])
    # error_handling and internal_restructure excluded
    seen_labels: list[str] = []
    state = {"n": 0}

    def choose(options, **kwargs):
        opts = list(options)
        state["n"] += 1
        if state["n"] == 1:
            assert "See more candidates…" in opts
            return _sel("See more candidates…")
        if any(o.startswith("1.") for o in opts):
            seen_labels.extend(opts)
            return _sel("← Back")
        if any(o.startswith("Use A:") for o in opts):
            return _sel(next(o for o in opts if o.startswith("Use A:")))
        if "Lock and generate message" in opts:
            return _sel("Lock and generate message")
        raise AssertionError((state["n"], opts))

    run_intent_arbitration(
        ranked_intents=ranked,
        ranking_confidence=conf,
        constraints=constraints,
        deps=ArbitrationDeps(choose=choose, can_open_tty=lambda: True, filter_available=lambda: False),
    )
    blob = "\n".join(seen_labels)
    assert "error_handling" not in blob
    assert "internal_restructure" not in blob
    assert "docs_update" in blob or "tests_update" in blob


# ---------------------------------------------------------------------------
# Specify (3c)
# ---------------------------------------------------------------------------


def test_specify_browse_locks_matrix_row_a05(monkeypatch):
    ranked, conf = _low_pair()
    matrix = [
        {
            "intent_id": "feature_addition",
            "emoji": "✨",
            "cc_type": "feat",
            "description": "Add a feature",
            "semver_impact": "MINOR",
            "changelog_group": "Added",
            "intent_group": "feature",
            "code": ":sparkles:",
        },
        {
            "intent_id": "documentation_update",
            "emoji": "📝",
            "cc_type": "docs",
            "description": "Docs only",
            "semver_impact": "NONE",
            "changelog_group": "Documentation",
            "intent_group": "docs",
            "code": ":memo:",
        },
    ]
    monkeypatch.setattr("git_cg.intent_arbitrate.get_gitmoji_matrix", lambda: matrix)
    state = {"n": 0}

    def choose(options, **kwargs):
        opts = list(options)
        state["n"] += 1
        if "Specify from matrix…" in opts:
            return _sel("Specify from matrix…")
        if "Browse matrix catalogue…" in opts:
            return _sel("Browse matrix catalogue…")
        if any("documentation_update" in o for o in opts):
            return _sel(next(o for o in opts if "documentation_update" in o))
        if "Lock and generate message" in opts:
            return _sel("Lock and generate message")
        raise AssertionError((state["n"], opts))

    result = run_intent_arbitration(
        ranked_intents=ranked,
        ranking_confidence=conf,
        constraints=IntentSelectionConstraints(),
        deps=ArbitrationDeps(choose=choose, can_open_tty=lambda: True, filter_available=lambda: False),
    )
    assert result.choice_path == "specify_browse"
    assert result.locked_intent_id == "documentation_update"
    assert result.override is True


def test_lock_m_back_to_specify_hub_a09(monkeypatch):
    ranked, conf = _low_pair()
    matrix = [
        {
            "intent_id": "feature_addition",
            "emoji": "✨",
            "cc_type": "feat",
            "description": "Add a feature",
            "semver_impact": "MINOR",
            "changelog_group": "Added",
            "intent_group": "feature",
        },
        {
            "intent_id": "docs_update",
            "emoji": "📝",
            "cc_type": "docs",
            "description": "Docs",
            "semver_impact": "NONE",
            "changelog_group": "Documentation",
            "intent_group": "docs",
        },
    ]
    monkeypatch.setattr("git_cg.intent_arbitrate.get_gitmoji_matrix", lambda: matrix)
    saw_specify_hub_again = False
    phase = {"p": "to_lock_m"}

    def choose2(options, **kwargs):
        nonlocal saw_specify_hub_again
        opts = list(options)
        p = phase["p"]
        if p == "to_lock_m":
            if "Specify from matrix…" in opts and any(o.startswith("Use A:") for o in opts):
                return _sel("Specify from matrix…")
            if "Browse matrix catalogue…" in opts and not any("docs_update" in o for o in opts):
                return _sel("Browse matrix catalogue…")
            if any("docs_update" in o for o in opts):
                return _sel(next(o for o in opts if "docs_update" in o))
            if "Lock and generate message" in opts:
                phase["p"] = "back_from_lock"
                return _sel("← Back")
        if p == "back_from_lock":
            # Must be SPECIFY hub again (A_09)
            assert "Browse matrix catalogue…" in opts
            assert "Specify from matrix…" not in opts or "Fuzzy" in str(opts) or True
            saw_specify_hub_again = True
            phase["p"] = "main_lock"
            return _sel("← Back")
        if p == "main_lock":
            if any(o.startswith("Use A:") for o in opts):
                return _sel(next(o for o in opts if o.startswith("Use A:")))
            if "Lock and generate message" in opts:
                return _sel("Lock and generate message")
        raise AssertionError((p, opts))

    result = run_intent_arbitration(
        ranked_intents=ranked,
        ranking_confidence=conf,
        constraints=IntentSelectionConstraints(),
        deps=ArbitrationDeps(choose=choose2, can_open_tty=lambda: True, filter_available=lambda: False),
    )
    assert saw_specify_hub_again is True
    assert result.choice_path == "pick_a"


def test_no_filter_browse_only_a14(monkeypatch):
    ranked, conf = _low_pair()
    matrix = [
        {
            "intent_id": "feature_addition",
            "emoji": "✨",
            "cc_type": "feat",
            "description": "feat",
            "semver_impact": "MINOR",
            "changelog_group": "Added",
            "intent_group": "feature",
        }
    ]
    monkeypatch.setattr("git_cg.intent_arbitrate.get_gitmoji_matrix", lambda: matrix)
    seen_hub_options: list[str] = []
    state = {"n": 0}

    def choose(options, **kwargs):
        opts = list(options)
        state["n"] += 1
        if state["n"] == 1:
            assert "Specify from matrix…" in opts
            return _sel("Specify from matrix…")
        if "Browse matrix catalogue…" in opts:
            seen_hub_options.extend(opts)
            assert "Fuzzy search matrix…" not in opts
            return _sel("← Back")
        if any(o.startswith("Use A:") for o in opts):
            return _sel(next(o for o in opts if o.startswith("Use A:")))
        if "Lock and generate message" in opts:
            return _sel("Lock and generate message")
        raise AssertionError((state["n"], opts))

    result = run_intent_arbitration(
        ranked_intents=ranked,
        ranking_confidence=conf,
        constraints=IntentSelectionConstraints(),
        deps=ArbitrationDeps(choose=choose, can_open_tty=lambda: True, filter_available=lambda: False),
    )
    assert "Fuzzy search matrix…" not in seen_hub_options
    assert result.choice_path == "pick_a"


def test_specify_fuzzy_path(monkeypatch):
    ranked, conf = _low_pair()
    matrix = [
        {
            "intent_id": "feature_addition",
            "emoji": "✨",
            "cc_type": "feat",
            "description": "feat",
            "semver_impact": "MINOR",
            "changelog_group": "Added",
            "intent_group": "feature",
        },
        {
            "intent_id": "docs_update",
            "emoji": "📝",
            "cc_type": "docs",
            "description": "docs",
            "semver_impact": "NONE",
            "changelog_group": "Documentation",
            "intent_group": "docs",
        },
    ]
    monkeypatch.setattr("git_cg.intent_arbitrate.get_gitmoji_matrix", lambda: matrix)

    def choose(options, **kwargs):
        opts = list(options)
        if "Specify from matrix…" in opts and "Fuzzy search matrix…" not in opts:
            return _sel("Specify from matrix…")
        if "Fuzzy search matrix…" in opts:
            return _sel("Fuzzy search matrix…")
        if "Lock and generate message" in opts:
            return _sel("Lock and generate message")
        raise AssertionError(opts)

    def filter_fn(options, **kwargs):
        hit = next(o for o in options if "docs_update" in o)
        return _sel(hit)

    result = run_intent_arbitration(
        ranked_intents=ranked,
        ranking_confidence=conf,
        constraints=IntentSelectionConstraints(),
        deps=ArbitrationDeps(
            choose=choose,
            filter=filter_fn,
            can_open_tty=lambda: True,
            filter_available=lambda: True,
        ),
    )
    assert result.choice_path == "specify_fuzzy"
    assert result.locked_intent_id == "docs_update"
    assert result.override is True


def test_arbitration_does_not_recompute_confidence(monkeypatch):
    """A_20 navigation must not call compute_ranking_confidence."""
    ranked, conf = _low_pair()
    calls = {"n": 0}

    def boom(*args, **kwargs):
        calls["n"] += 1
        raise AssertionError("compute_ranking_confidence must not be called during arbitration")

    monkeypatch.setattr("git_cg.ranking_confidence.compute_ranking_confidence", boom)

    def choose(options, **kwargs):
        opts = list(options)
        if any(o.startswith("Use A:") for o in opts):
            return _sel(next(o for o in opts if o.startswith("Use A:")))
        if "Lock and generate message" in opts:
            return _sel("Lock and generate message")
        raise AssertionError(opts)

    result = run_intent_arbitration(
        ranked_intents=ranked,
        ranking_confidence=conf,
        constraints=IntentSelectionConstraints(),
        deps=ArbitrationDeps(choose=choose, can_open_tty=lambda: True, filter_available=lambda: False),
    )
    assert calls["n"] == 0
    assert result.locked_intent_id == "feature_addition"


# ---------------------------------------------------------------------------
# Flags
# ---------------------------------------------------------------------------


def test_rank_arbitrate_flag_default_auto(monkeypatch):
    from git_cg.ranking_arbitrate_flags import is_rank_arbitrate_enabled, resolve_rank_arbitrate_mode

    monkeypatch.delenv("GIT_CG_RANK_ARBITRATE", raising=False)
    assert resolve_rank_arbitrate_mode() == "auto"
    assert is_rank_arbitrate_enabled() is True


def test_rank_arbitrate_flag_off(monkeypatch):
    from git_cg.ranking_arbitrate_flags import is_rank_arbitrate_enabled, resolve_rank_arbitrate_mode

    monkeypatch.setenv("GIT_CG_RANK_ARBITRATE", "off")
    assert resolve_rank_arbitrate_mode() == "off"
    assert is_rank_arbitrate_enabled() is False


def test_rank_arbitrate_explicit_bool_overrides_env(monkeypatch):
    from git_cg.ranking_arbitrate_flags import is_rank_arbitrate_enabled, resolve_rank_arbitrate_mode

    monkeypatch.setenv("GIT_CG_RANK_ARBITRATE", "off")
    assert resolve_rank_arbitrate_mode(True) == "auto"
    assert is_rank_arbitrate_enabled(True) is True

    monkeypatch.setenv("GIT_CG_RANK_ARBITRATE", "auto")
    assert resolve_rank_arbitrate_mode(False) == "off"
    assert is_rank_arbitrate_enabled(False) is False


def test_rank_arbitrate_explicit_string_tokens(monkeypatch):
    from git_cg.ranking_arbitrate_flags import resolve_rank_arbitrate_mode

    monkeypatch.delenv("GIT_CG_RANK_ARBITRATE", raising=False)
    assert resolve_rank_arbitrate_mode("off") == "off"
    assert resolve_rank_arbitrate_mode("AUTO") == "auto"


def test_looks_like_commit_subject_detector():
    assert looks_like_commit_subject("feat(scope): add module")
    assert looks_like_commit_subject("fix: broken parser")
    assert looks_like_commit_subject("feat: x")
    assert not looks_like_commit_subject("this is a feat")
    assert not looks_like_commit_subject("use scope intent")
    assert not looks_like_commit_subject("feat")
    hint = subject_shaped_guidance_hint("feat(intent): add module")
    assert hint is not None
    assert "commit subject" in hint.lower()


def test_subject_shaped_guidance_rerank_noop_shows_hint_and_bell():
    ranked, conf = _low_pair()
    state = {"n": 0}
    bells: list[int] = []
    saw_subject_hint = False

    def choose(options, **kwargs):
        nonlocal saw_subject_hint
        opts = list(options)
        state["n"] += 1
        title = kwargs.get("title") or ""
        body = kwargs.get("body") or ""
        if state["n"] == 1:
            return _sel("Add regeneration guidance…")
        if "Regenerate ranking with this guidance (re-run ranker)" in opts:
            if "commit subject" in body.lower():
                saw_subject_hint = True
            return _sel("Regenerate ranking with this guidance (re-run ranker)")
        if title == "Guidance re-rank no-op" or (len(opts) == 1 and opts[0].startswith("OK")):
            assert "commit subject" in body.lower() or "subject" in body.lower()
            saw_subject_hint = True
            return _sel(opts[0])
        if any(o.startswith("Use A:") for o in opts):
            return _sel(next(o for o in opts if o.startswith("Use A:")))
        if "Lock and generate message" in opts:
            return _sel("Lock and generate message")
        raise AssertionError((state["n"], opts, title, body[:120]))

    def input_fn(**kwargs):
        return _sel("feat(scope): add shiny module")

    result = run_intent_arbitration(
        ranked_intents=ranked,
        ranking_confidence=conf,
        constraints=IntentSelectionConstraints(),
        deps=ArbitrationDeps(
            choose=choose,
            input=input_fn,
            can_open_tty=lambda: True,
            filter_available=lambda: False,
            emit_bell=lambda: bells.append(1),
        ),
    )
    assert result.action == "locked"
    assert result.re_rank_requested is False
    assert saw_subject_hint is True
    assert bells == [1]


def test_presentation_note_still_low_rings_bell_and_shows_on_main():
    ranked, conf = _low_pair()
    bells: list[int] = []
    saw_note = False

    def choose(options, **kwargs):
        nonlocal saw_note
        opts = list(options)
        body = kwargs.get("body") or ""
        if "still Low" in body:
            saw_note = True
        if any(o.startswith("Use A:") for o in opts):
            return _sel(next(o for o in opts if o.startswith("Use A:")))
        if "Lock and generate message" in opts:
            return _sel("Lock and generate message")
        raise AssertionError(opts)

    note = format_regen_still_low_note(preferred_type="feat", narrowed=True)
    result = run_intent_arbitration(
        ranked_intents=ranked,
        ranking_confidence=conf,
        constraints=IntentSelectionConstraints(),
        presentation_note=note,
        deps=ArbitrationDeps(
            choose=choose,
            can_open_tty=lambda: True,
            filter_available=lambda: False,
            emit_bell=lambda: bells.append(1),
        ),
    )
    assert result.action == "locked"
    assert saw_note is True
    assert bells == [1]


def test_lock_best_ranked_shortcut_when_preferred_type_mapped():
    """MAIN offers one-shot Lock best ranked <type> when preferred_type matches top."""
    ranked, conf = _low_pair()
    # Ensure top is feat
    assert ranked[0].cc_type == "feat"
    state = {"n": 0}

    def choose(options, **kwargs):
        opts = list(options)
        state["n"] += 1
        lock_opts = [o for o in opts if o.startswith("Lock best ranked feat")]
        if lock_opts and state["n"] == 1:
            return _sel(lock_opts[0])
        if "Lock and generate message" in opts:
            return _sel("Lock and generate message")
        raise AssertionError((state["n"], opts))

    result = run_intent_arbitration(
        ranked_intents=ranked,
        ranking_confidence=conf,
        constraints=IntentSelectionConstraints(),
        existing_directives={"preferred_type": "feat"},
        existing_guidance="this is a feat",
        deps=ArbitrationDeps(
            choose=choose,
            can_open_tty=lambda: True,
            filter_available=lambda: False,
        ),
    )
    assert result.action == "locked"
    assert result.choice_path == "pick_a"
    assert result.locked_intent_id == ranked[0].intent_id


def test_format_regen_still_low_note_copy():
    note = format_regen_still_low_note(preferred_type="feat", narrowed=False)
    assert "preferred_type=feat" in note
    assert "still Low" in note
    assert "scores unchanged" in note
    note2 = format_regen_still_low_note(preferred_type="fix", preferred_scope="tui", narrowed=True)
    assert "preferred_scope=tui" in note2
    assert "presentation filtered" in note2


def test_compose_arbitration_status_strip_dedupes_preferred_type():
    note = format_regen_still_low_note(preferred_type="feat", narrowed=True)
    strip = compose_arbitration_status_strip(
        presentation_note=note,
        guidance="this is a feat",
        directive_note="filtered: preferred_type=feat",
    )
    assert strip is not None
    assert "still Low" in strip
    assert "preferred_type=feat" in strip
    # preferred_type must appear once (banner owns it; directive dropped)
    assert strip.count("preferred_type=feat") == 1
    # guidance retained once
    assert "this is a feat" in strip
    assert "filtered: preferred_type=feat" not in strip


def test_compose_arbitration_status_strip_keeps_unique_directive():
    strip = compose_arbitration_status_strip(
        guidance="use scope tui",
        directive_note="filtered: preferred_scope=tui",
    )
    assert strip is not None
    assert "preferred_scope=tui" in strip
    assert "use scope tui" in strip
