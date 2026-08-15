"""Gate composition for S2a/S2b/S2c (required-block; true advisories never veto)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from git_cg.eval.score_result import ScoreResultV1
from git_cg.eval.scoring.result_builder import make_score

# S2a required metric block — catalog has no require_block field; suite may override.
S2A_REQUIRE_BLOCK: tuple[str, ...] = (
    # Family A
    "a.bundle_schema_valid",
    "a.artifact_class_known",
    "a.final_message_present",
    "a.binding_unbound_explicit",
    "a.binding_complete",
    "a.final_bytes_stable",
    "a.scored_target_order_ok",
    # Family B
    "b.header_shape",
    "b.gitmoji_present",
    "b.cc_type_known",
    "b.scope_shape",
    "b.subject_length",
    "b.trailers_parse",
    "b.trailers_issue_ref",
    "b.trailers_semver",
    "b.trailers_change_types",
    "b.trailers_changelog_groups",
    "b.structured_envelope",
    # Family D core
    "d.gold_report_ok",
    "d.strict_fail_set",
    "d.skeleton_fallback_final",
    "d.process_meta_body",
    # Family H core
    "h.catalog_pinned",
    "h.suite_snapshot_pinned",
    "h.offline_complete",
    "h.score_envelope_valid",
    "h.evaluator_error_free",
    "h.eval_input_nonempty",
    "h.eval_error_fanout_bounded",
    "h.pin_integrity",
)

# S2b opt-in 68-ID block = S2A (30) + C block (6) + E block (5) + F block (6)
# + G (6) + remaining D (14) + h.structured_bundle_compliance (1).
_S2B_C_BLOCK: tuple[str, ...] = (
    "c.contract_smoke",
    "c.diff_class_resolved",
    "c.scope_forced_ok",
    "c.security_claim_evidence",
    "c.semver_ceiling",
    "c.type_allowed",
)
_S2B_E_BLOCK: tuple[str, ...] = (
    "e.banned_craft_openers",
    "e.changelog_groups_allowlisted",
    "e.presentation_constraints_applied",
    "e.secondary_intent_fill_legal",
    "e.skeleton_avoidance",
)
_S2B_F_BLOCK: tuple[str, ...] = (
    "f.body_attribution",
    "f.counter_integrity",
    "f.included_changes_vs_diff",
    "f.security_claims_need_paths",
    "f.staged_path_allowlist",
    "f.subject_attribution",
)
_S2B_G_BLOCK: tuple[str, ...] = (
    "g.issue_null_policy",
    "g.no_eval_policy_fork",
    "g.ranked_identity_preserved",
    "g.secrets_not_in_message",
    "g.semantic_contract_bound",
    "g.sop_not_mutated",
)
_S2B_D_REMAINING: tuple[str, ...] = (
    "d.body_inventory",
    "d.breaking_compat",
    "d.docs_implementation_claim",
    "d.fixture_product_framing",
    "d.group_primary_match",
    "d.high_risk_theme_coverage",
    "d.included_changes_coverage",
    "d.path_class_semver",
    "d.path_class_type",
    "d.scope_filename",
    "d.semver_matrix",
    "d.subject_inventory",
    "d.subject_title_case",
    "d.type_group_coherent",
)

S2B_REQUIRE_BLOCK: tuple[str, ...] = (
    *S2A_REQUIRE_BLOCK,
    *_S2B_C_BLOCK,
    *_S2B_E_BLOCK,
    *_S2B_F_BLOCK,
    *_S2B_G_BLOCK,
    *_S2B_D_REMAINING,
    "h.structured_bundle_compliance",
)

# S2c topology block (12 catalog severity=block Family I ids). Never silently
# stuffed into S2A/S2B; joined only when require_topology=true (N7/N19).
S2C_TOPOLOGY_BLOCK: tuple[str, ...] = (
    "i.trace_root_present",
    "i.lifecycle_complete",
    "i.span_tree_valid",
    "i.span_parentage_valid",
    "i.required_spans_present",
    "i.thread_id_present",
    "i.thread_continuity",
    "i.counter_span_consistent",
    "i.finalization_observed",
    "i.replay_lineage_valid",
    "i.no_cross_case_contamination",
    "i.correlation_envelope_valid",
)

# True advisory families only — never gate veto, even if placed in require_block.
_ADVISORY_PREFIXES = (
    "cprime",
    "lab.",
    "human.",
    "nlp.",
    "export.",
    "dogfood.",
)


def _is_true_advisory(metric_id: str) -> bool:
    """True for C-prime / lab / human / NLP / export / dogfood (never gate veto)."""
    if metric_id.startswith("cprime"):
        return True
    return any(metric_id.startswith(p) for p in _ADVISORY_PREFIXES if p != "cprime")


def compose_gates(
    results: Sequence[ScoreResultV1],
    *,
    require_block: Iterable[str] | None = None,
    bound: bool | None = None,
    require_topology: bool = False,
    gold_mode: str = "strict",
) -> list[ScoreResultV1]:
    """
    Compose deterministic, promotion, and semantic-cohort gate results from score rows.
    
    Parameters:
    	results (Sequence[ScoreResultV1]): Score rows used to evaluate the gates.
    	require_block (Iterable[str] | None): Required metric IDs; defaults to the S2a block.
    	bound (bool | None): Whether the evaluation is bound.
    	require_topology (bool): Whether to include S2c topology metrics and require topology checks for promotion.
    	gold_mode (str): Gold evaluation mode recorded in gate evidence.
    
    Returns:
    	list[ScoreResultV1]: The deterministic, golden-promotion, and semantic-cohort gate results.
    
    Raises:
    	ValueError: If duplicate non-gate metric IDs are present in the score rows.
    """
    base_req = tuple(require_block) if require_block is not None else S2A_REQUIRE_BLOCK
    # Stable unique union; S2C_TOPOLOGY_BLOCK order preserved for new tails.
    req = tuple(dict.fromkeys((*base_req, *S2C_TOPOLOGY_BLOCK))) if require_topology else base_req

    # Reject duplicate metric IDs in the score stream (silent last-write-wins banned).
    seen: dict[str, int] = {}
    dups: list[str] = []
    for r in results:
        mid = r.metric_id
        seen[mid] = seen.get(mid, 0) + 1
    for mid, n in seen.items():
        if n > 1 and not mid.startswith("gate."):
            dups.append(mid)
    if dups:
        raise ValueError(f"duplicate metric_id in score stream: {sorted(dups)}")

    by_id: dict[str, ScoreResultV1] = {r.metric_id: r for r in results}

    missing: list[str] = []
    failed: list[str] = []
    ignored_failures: list[str] = []

    # Label true-advisory failures only (not unrequested C/E/F/G).
    for mid, row in by_id.items():
        if mid.startswith("gate."):
            continue
        if _is_true_advisory(mid) and row.passed is False:
            ignored_failures.append(mid)

    for mid in req:
        if _is_true_advisory(mid):
            # True advisories never veto even if explicitly required.
            continue
        row = by_id.get(mid)
        if row is None:
            missing.append(mid)
            continue
        if row.passed is False or (
            row.passed is None and getattr(row.polarity, "value", str(row.polarity)) == "pass_fail"
        ):
            failed.append(mid)

    det_ok = not missing and not failed

    gates: list[ScoreResultV1] = [
        make_score(
            "gate.deterministic_pass",
            det_ok,
            reason=None if det_ok else "require_block_failed",
            evidence={
                "require_block": list(req),
                "base_require_block": list(base_req),
                "missing": missing,
                "failed": failed,
                "ignored_advisory_failures": ignored_failures,
                "bound": bound,
                "require_topology": require_topology,
                "s2c_topology_block": list(S2C_TOPOLOGY_BLOCK) if require_topology else [],
                "gold_mode": gold_mode,
            },
            failure_ids=None if det_ok else (["GATE_REQUIRE_BLOCK"] + failed + [f"missing:{m}" for m in missing]),
        )
    ]

    gold_row = by_id.get("d.gold_report_ok")
    skel_row = by_id.get("d.skeleton_fallback_final")
    gold_pass = bool(gold_row and gold_row.passed)
    # Fail-closed: missing skeleton row must block promotion even if a custom
    # require_block omitted ``d.skeleton_fallback_final``.
    skel_clean = bool(skel_row and skel_row.passed)
    s2b_promo = det_ok and gold_pass and skel_clean and (bound is not False)

    life_row = by_id.get("i.lifecycle_complete")
    req_spans_row = by_id.get("i.required_spans_present")
    life_ok = bool(life_row and life_row.passed is True)
    req_spans_ok = bool(req_spans_row and req_spans_row.passed is True)
    # I metrics are NOT consulted for golden when require_topology=false.
    promo_ok = s2b_promo and life_ok and req_spans_ok if require_topology else s2b_promo

    gates.append(
        make_score(
            "gate.golden_promotion_eligible",
            promo_ok,
            reason=None if promo_ok else "promotion_blocked",
            evidence={
                "deterministic_pass": det_ok,
                "gold_ok": gold_pass,
                "skeleton_clean": skel_clean,
                "bound": bound,
                "require_topology": require_topology,
                "lifecycle_complete": life_ok,
                "required_spans_present": req_spans_ok,
                "s2b_promo": s2b_promo,
            },
            failure_ids=None if promo_ok else ["GATE_PROMOTION_BLOCKED"],
        )
    )

    # Offline S2b/S2c: C-prime / semantic cohort remains later-lane (not C).
    gates.append(
        make_score(
            "gate.semantic_cohort_eligible",
            False,
            passed=False,
            reason="semantic_cohort_deferred_offline_later_lane",
            evidence={"cprime_ran": False, "offline_s2b": True},
            failure_ids=["GATE_SEMANTIC_COHORT_DEFERRED"],
        )
    )

    return gates


def assert_s2b_block_len() -> None:
    """Internal invariant: S2B_REQUIRE_BLOCK is exactly 68 unique catalog IDs."""
    if len(S2B_REQUIRE_BLOCK) != 68:
        raise AssertionError(f"S2B_REQUIRE_BLOCK len={len(S2B_REQUIRE_BLOCK)} expected 68")
    if len(set(S2B_REQUIRE_BLOCK)) != 68:
        raise AssertionError("S2B_REQUIRE_BLOCK contains duplicates")


def assert_s2c_block_len() -> None:
    """Validates the size, uniqueness, and Family I membership of the S2c topology metric block.
    
    Raises:
        AssertionError: If the block does not contain exactly 12 unique Family I metric IDs.
    """
    if len(S2C_TOPOLOGY_BLOCK) != 12:
        raise AssertionError(f"S2C_TOPOLOGY_BLOCK len={len(S2C_TOPOLOGY_BLOCK)} expected 12")
    if len(set(S2C_TOPOLOGY_BLOCK)) != 12:
        raise AssertionError("S2C_TOPOLOGY_BLOCK contains duplicates")
    if any(not mid.startswith("i.") for mid in S2C_TOPOLOGY_BLOCK):
        raise AssertionError("S2C_TOPOLOGY_BLOCK must contain only Family I metric ids")
