"""Family H — harness / offline / pin / envelope health."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from git_cg.eval.binding.trajectory import TrajectoryError, validate_observed_stages
from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin
from git_cg.eval.schema_pack import SchemaPackError, validate_instance
from git_cg.eval.score_result import ScoreResultV1
from git_cg.eval.scoring.context import ScoreContext, live_pin_refs
from git_cg.eval.scoring.preconditions import PreconditionResult
from git_cg.eval.scoring.result_builder import make_score

FAMILY_H_S2A = (
    "h.catalog_pinned",
    "h.suite_snapshot_pinned",
    "h.offline_complete",
    "h.score_envelope_valid",
    "h.evaluator_error_free",
    "h.eval_input_nonempty",
    "h.eval_input_size_ok",
    "h.eval_error_fanout_bounded",
    "h.pin_integrity",
    "h.online_scores_match_product_card",
)

# S5 / D39 — Lane C' honesty metrics. Emitted for real when Lane C ran; honest
# not-run (passed=False, never green-by-absence) when it did not.
FAMILY_H_CPRIME = (
    "h.judge_input_isolated",
    "h.prompt_pack_pinned",
    "h.prompt_pack_hash_known",
    "h.prompt_pack_suite_fresh",
)

# S3 (R7/N19.6): Family H owns the trajectory completeness/policy sink. These
# consume the two existing catalog metrics — no new catalog ids are invented.
FAMILY_H_S3 = (
    "h.trajectory_stages_declared",
    "h.trajectory_stages_observed",
)


def score_family_h(
    ctx: ScoreContext,
    *,
    pre: PreconditionResult,
    family_scores: list[ScoreResultV1],
    suite_snapshot_pin: str | None,
    offline: bool = True,
    evaluator_errors: list[str] | None = None,
    require_trajectory: bool = False,
    lane_c_run_evidence: Mapping[str, Any] | None = None,
    lane_c_rows: list[ScoreResultV1] | None = None,
) -> list[ScoreResultV1]:
    """Emit Family H pin/offline/envelope/anti-fan-out + trajectory metrics.

    Runs after A/B/D so ``h.score_envelope_valid`` can validate prior rows.
    Live S0 pin identity + suite snapshot pin are fail-closed.

    S3 (R7/N19.6): trajectory evidence is read from ``ctx.meta["trajectory"]``
    (inline at ``bundle.meta.trajectory``). Missing/incomplete trajectory is an
    eval-class fail only when ``require_trajectory`` is set (suite policy);
    otherwise it is advisory. Family H never treats trajectory as topology —
    that plane stays with Family I.

    S5 / D39: optional ``lane_c_run_evidence`` / ``lane_c_rows`` drive the four
    C' honesty metrics. When Lane C did not run, those metrics fail closed with
    an honest not-run reason — never green-by-absence.

    """
    errors = list(evaluator_errors or [])
    scores: list[ScoreResultV1] = []

    pack = schema_pack_pin()
    catalog = metric_catalog_pin()
    pin_ok = bool(pack and catalog)
    # Bundle pin match when present
    if ctx.schema_pack and ctx.schema_pack != pack:
        pin_ok = False
    if ctx.metric_catalog and ctx.metric_catalog != catalog:
        pin_ok = False

    scores.append(
        make_score(
            "h.catalog_pinned",
            bool(catalog),
            reason=None if catalog else "catalog_pin_missing",
            evidence={"metric_catalog": catalog},
            failure_ids=None if catalog else ["EVAL_CATALOG_PIN"],
            product_authority="git_cg.eval.pins.metric_catalog_pin",
        )
    )

    snap_ok = bool(suite_snapshot_pin and str(suite_snapshot_pin).strip())
    scores.append(
        make_score(
            "h.suite_snapshot_pinned",
            snap_ok,
            reason=None if snap_ok else "suite_snapshot_missing",
            evidence={"suite_snapshot_pin": suite_snapshot_pin},
            failure_ids=None if snap_ok else ["EVAL_SUITE_SNAPSHOT_PIN"],
        )
    )

    scores.append(
        make_score(
            "h.offline_complete",
            offline,
            reason=None if offline else "online_path_detected",
            evidence={"offline": offline, "network_forbidden": True},
            failure_ids=None if offline else ["EVAL_OFFLINE_INCOMPLETE"],
        )
    )

    env_bad: list[str] = []
    for s in family_scores:
        try:
            payload = s.model_dump(mode="json")
            ScoreResultV1.model_validate(payload)
        except Exception as exc:
            env_bad.append(f"{s.metric_id}: {exc}")
    env_ok = not env_bad
    scores.append(
        make_score(
            "h.score_envelope_valid",
            env_ok,
            reason=None if env_ok else "invalid_score_envelope",
            evidence={"invalid_count": len(env_bad), "samples": env_bad[:5]},
            failure_ids=None if env_ok else ["EVAL_SCORE_ENVELOPE"],
            product_authority="git_cg.eval.score_result.ScoreResultV1",
        )
    )

    err_free = len(errors) == 0
    scores.append(
        make_score(
            "h.evaluator_error_free",
            err_free,
            reason=None if err_free else "evaluator_exceptions",
            evidence={"errors": errors[:10], "count": len(errors)},
            failure_ids=None if err_free else ["EVAL_EVALUATOR_ERROR"],
        )
    )

    scores.append(
        make_score(
            "h.eval_input_nonempty",
            pre.input_nonempty,
            reason=None if pre.input_nonempty else (pre.reason or "empty_input"),
            evidence={
                "input_nonempty": pre.input_nonempty,
                "input_byte_len": ctx.input_size_bytes,
                "scored_target": ctx.scored_target,
            },
            failure_ids=["FIND-026", "EVAL_INPUT_EMPTY"] if not pre.input_nonempty else None,
        )
    )

    scores.append(
        make_score(
            "h.eval_input_size_ok",
            pre.input_size_ok,
            reason=None if pre.input_size_ok else (pre.reason or "oversize_input"),
            evidence={
                "input_size_ok": pre.input_size_ok,
                "input_byte_len": ctx.input_size_bytes,
                "max_eval_bytes": ctx.max_eval_bytes,
            },
            failure_ids=["FIND-026", "EVAL_INPUT_OVERSIZE"] if not pre.input_size_ok else None,
        )
    )

    # FIND-026: message-dependent families must not clone the input failure.
    input_fail_rows = [
        s
        for s in family_scores
        if s.failure_ids and any(str(fid).startswith("EVAL_INPUT") or str(fid) == "FIND-026" for fid in s.failure_ids)
    ]
    fanout_ok = len(input_fail_rows) == 0
    scores.append(
        make_score(
            "h.eval_error_fanout_bounded",
            fanout_ok,
            reason=None if fanout_ok else "input_failure_fanout",
            evidence={
                "short_circuit": pre.short_circuit,
                "leaked_input_fail_rows": len(input_fail_rows),
            },
            failure_ids=None if fanout_ok else ["FIND-026"],
        )
    )

    scores.append(
        make_score(
            "h.pin_integrity",
            pin_ok,
            reason=None if pin_ok else "pin_mismatch_or_missing",
            evidence={
                "schema_pack": pack,
                "metric_catalog": catalog,
                "bundle_schema_pack": ctx.schema_pack,
                "bundle_metric_catalog": ctx.metric_catalog,
                "pin_refs": live_pin_refs(),
            },
            failure_ids=None if pin_ok else ["EVAL_PIN_INTEGRITY"],
            product_authority="git_cg.eval.pins",
        )
    )

    card_match = True
    mismatches: list[dict[str, Any]] = []
    card = ctx.product_card if ctx.product_card else None
    if card and isinstance(card, dict):
        card_vals = card.get("metrics") or card.get("results") or card
        if isinstance(card_vals, dict):
            by_id = {s.metric_id: s for s in family_scores}
            for mid, cval in card_vals.items():
                if mid not in by_id:
                    continue
                s = by_id[mid]
                if isinstance(cval, bool) and s.passed is not None and bool(s.passed) != cval:
                    card_match = False
                    mismatches.append({"metric_id": mid, "card": cval, "score_passed": s.passed})
                elif isinstance(cval, dict) and "passed" in cval and s.passed is not None:
                    if bool(s.passed) != bool(cval["passed"]):
                        card_match = False
                        mismatches.append(
                            {
                                "metric_id": mid,
                                "card": cval["passed"],
                                "score_passed": s.passed,
                            }
                        )
    # FIND-002: structured bundle / score envelope compliance.
    # ctx.bundle may carry post-encode injection keys (score_card/files) that are
    # not schema fields; strip them for validation only — leave ctx.bundle intact.
    structured_ok = True
    structured_errors: list[str] = []
    try:
        bundle_for_schema = {k: v for k, v in dict(ctx.bundle or {}).items() if k not in {"score_card", "files"}}
        validate_instance("ape_bundle_v1", bundle_for_schema)
    except SchemaPackError as exc:
        structured_ok = False
        structured_errors.append(f"bundle:{exc}")
    except Exception as exc:
        structured_ok = False
        structured_errors.append(f"bundle:{type(exc).__name__}: {exc}")
    # Prior family score envelopes must already be ScoreResultV1-valid
    for s in family_scores:
        try:
            ScoreResultV1.model_validate(s.model_dump(mode="json"))
        except Exception as exc:
            structured_ok = False
            structured_errors.append(f"score:{s.metric_id}:{exc}")
            break
    scores.append(
        make_score(
            "h.structured_bundle_compliance",
            structured_ok,
            reason=None if structured_ok else "structured_bundle_noncompliant",
            evidence={"errors": structured_errors[:8], "finding": "FIND-002"},
            failure_ids=None if structured_ok else ["FIND-002", "EVAL_STRUCTURED_BUNDLE"],
            product_authority="git_cg.eval.schema_pack.validate_instance+ScoreResultV1",
        )
    )

    scores.append(
        make_score(
            "h.online_scores_match_product_card",
            card_match,
            reason=None if card_match else "product_card_mismatch",
            evidence={"mismatches": mismatches, "has_card": bool(card)},
            failure_ids=None if card_match else ["EVAL_PRODUCT_CARD_MISMATCH"],
        )
    )

    # S3 (R7/N19.6): trajectory completeness/policy sink. Trajectory evidence
    # is inlined at bundle.meta.trajectory (surfaced via ctx.meta["trajectory"]).
    # Family H owns this plane; Family I never consumes trajectory as topology.
    scores.extend(_score_trajectory(ctx, require_trajectory=require_trajectory))

    # S5 / D39: optional in-process emission when caller already has Lane C
    # evidence (tests / custom runners). The offline score_bundle path emits
    # these via score_family_h_cprime *after* Lane C so not-run vs ran is honest.
    if lane_c_run_evidence is not None or lane_c_rows is not None:
        scores.extend(
            score_family_h_cprime(
                suite_snapshot_pin=suite_snapshot_pin,
                lane_c_run_evidence=lane_c_run_evidence,
                lane_c_rows=lane_c_rows,
            )
        )

    return scores


def _score_trajectory(ctx: ScoreContext, *, require_trajectory: bool) -> list[ScoreResultV1]:
    """Emit the two S3 trajectory metrics (existing catalog ids only).

    ``h.trajectory_stages_declared`` — declared stage list is present and
    non-empty. ``h.trajectory_stages_observed`` — observed stages are present
    and behaviourally complete (``meta.complete``). Both are eval-class signals:
    they fail only when ``require_trajectory`` is set (suite policy) and the
    evidence is missing/incomplete; otherwise they are advisory passes.

    """
    trajectory = (ctx.meta or {}).get("trajectory")
    declared: list[Any] = []
    observed: list[Any] = []
    meta_complete = False
    trajectory_valid = False
    present = isinstance(trajectory, dict)
    if present:
        raw_declared = trajectory.get("declared_stages")
        raw_observed = trajectory.get("observed_stages")
        traj_meta = trajectory.get("meta")
        if isinstance(raw_declared, list) and isinstance(raw_observed, list):
            try:
                declared = validate_observed_stages(raw_declared)
                observed = validate_observed_stages(raw_observed)
                trajectory_valid = True
            except TrajectoryError:
                declared = []
                observed = []
                trajectory_valid = False
        # Accept only an exact boolean True — truthy strings/ints must not pass
        # require_trajectory completeness (fail closed on malformed meta).
        meta_complete = isinstance(traj_meta, dict) and traj_meta.get("complete") is True

    declared_ok = trajectory_valid and bool(declared)
    observed_ok = trajectory_valid and bool(observed) and meta_complete

    declared_pass = declared_ok or not require_trajectory
    observed_pass = observed_ok or not require_trajectory

    return [
        make_score(
            "h.trajectory_stages_declared",
            declared_pass,
            reason=None if declared_ok else "trajectory_declared_missing",
            evidence={
                "trajectory_present": present,
                "trajectory_valid": trajectory_valid,
                "declared_count": len(declared),
                "require_trajectory": require_trajectory,
            },
            failure_ids=None if declared_pass else ["EVAL_TRAJECTORY_DECLARED"],
        ),
        make_score(
            "h.trajectory_stages_observed",
            observed_pass,
            reason=None if observed_ok else "trajectory_observed_incomplete",
            evidence={
                "trajectory_present": present,
                "trajectory_valid": trajectory_valid,
                "observed_count": len(observed),
                "meta_complete": meta_complete,
                "require_trajectory": require_trajectory,
            },
            failure_ids=None if observed_pass else ["EVAL_TRAJECTORY_OBSERVED"],
        ),
    ]


def score_family_h_cprime(
    *,
    suite_snapshot_pin: str | None = None,
    lane_c_run_evidence: Mapping[str, Any] | None = None,
    lane_c_rows: list[ScoreResultV1] | None = None,
) -> list[ScoreResultV1]:
    """Emit the four S5 / D39 Lane C' honesty metrics.

    Semantics (no false green-by-absence):

    * Lane C not enabled / no evidence → each metric ``passed=False`` with
      ``reason="lane_c_not_run"``.
    * Lane C ran → evaluate isolation / pack pin / hash / suite freshness from
      run evidence + C' rows. Failures are honest eval-class fails.

    """
    ev = dict(lane_c_run_evidence or {})
    rows = list(lane_c_rows or [])

    # Honest not-run when Lane C was not enabled for this case.
    # score_bundle always sets lane_c_enabled explicitly (True/False).
    enabled = ev.get("lane_c_enabled")
    if enabled is False or (enabled is None and not rows and not ev.get("cprime_attempted")):
        return _cprime_not_run_scores(reason="lane_c_not_run")

    return [
        _score_judge_input_isolated(ev, rows),
        _score_prompt_pack_pinned(ev, rows),
        _score_prompt_pack_hash_known(ev, rows),
        _score_prompt_pack_suite_fresh(ev, rows, suite_snapshot_pin=suite_snapshot_pin),
    ]


def _cprime_not_run_scores(*, reason: str) -> list[ScoreResultV1]:
    """Honest fail-closed rows when Lane C' did not run (D39 / F28)."""
    out: list[ScoreResultV1] = []
    for mid in FAMILY_H_CPRIME:
        out.append(
            make_score(
                mid,
                False,
                reason=reason,
                evidence={
                    "lane_c_ran": False,
                    "lane_c_enabled": False,
                    "honest_not_run": True,
                },
                failure_ids=["EVAL_LANE_C_NOT_RUN"],
                product_authority="git_cg.eval.scoring.family_h.score_family_h_cprime",
            )
        )
    return out


def _cprime_row_evidence(rows: list[ScoreResultV1]) -> list[dict[str, Any]]:
    """Collect evidence payloads from ``cprime.*`` rows (ids + pin_refs)."""
    collected: list[dict[str, Any]] = []
    for row in rows:
        if not str(row.metric_id).startswith("cprime."):
            continue
        payload = dict(row.evidence or {})
        payload["_metric_id"] = row.metric_id
        payload["_pin_refs"] = list(row.pin_refs or [])
        collected.append(payload)
    return collected


def _score_judge_input_isolated(
    ev: Mapping[str, Any],
    rows: list[ScoreResultV1],
) -> ScoreResultV1:
    """``h.judge_input_isolated`` — gold-blind projection held for the run."""
    row_ev = _cprime_row_evidence(rows)
    isolation_ok = ev.get("judge_input_isolated")
    isolation_error = ev.get("judge_input_error") or ev.get("input_error")
    projected = ev.get("judge_input_projected")
    skip_code = ev.get("judge_input_skip_code") or ev.get("input_skip_code")

    # Derive from rows when top-level evidence is sparse (fail-closed over ALL rows).
    if isolation_ok is None:
        saw_verdict = False
        aggregate_ok = True
        for payload in row_ev:
            if "judge_input_isolated" in payload:
                saw_verdict = True
                if payload.get("judge_input_isolated") is False:
                    aggregate_ok = False
                    isolation_error = isolation_error or payload.get("judge_input_error") or payload.get("input_error")
            # Isolation/linkage contract failures surface as parse_error skips.
            if (payload.get("execution_code") == "parse_error" and payload.get("input_error")) or (
                payload.get("input_error") and payload.get("judge_input_isolated") is False
            ):
                saw_verdict = True
                aggregate_ok = False
                isolation_error = isolation_error or payload.get("input_error")
        if saw_verdict:
            isolation_ok = aggregate_ok

    # If a projection was attempted and no isolation error was recorded, pass.
    if isolation_ok is None:
        if projected is True or ev.get("judge_input_present") is True:
            isolation_ok = True
        elif skip_code in {"empty_input", "oversize_input"}:
            # Host guards are not isolation leaks — isolation held; size is separate.
            isolation_ok = True
        elif skip_code == "parse_error" and isolation_error:
            isolation_ok = False
        elif row_ev:
            # C' rows exist without an isolation complaint → held.
            isolation_ok = not any(
                "expected" in str(p.get("input_error") or "").lower()
                or "gold" in str(p.get("input_error") or "").lower()
                or "isolation" in str(p.get("input_error") or "").lower()
                for p in row_ev
            )
        else:
            isolation_ok = False

    ok = bool(isolation_ok)
    reason = None if ok else ("judge_input_isolation_failed" if isolation_error else "judge_input_isolation_unknown")
    return make_score(
        "h.judge_input_isolated",
        ok,
        reason=reason,
        evidence={
            "lane_c_enabled": True,
            "judge_input_isolated": ok,
            "judge_input_projected": projected,
            "judge_input_skip_code": skip_code,
            "judge_input_error": str(isolation_error)[:200] if isolation_error else None,
            "cprime_row_count": len(row_ev),
        },
        failure_ids=None if ok else ["EVAL_JUDGE_INPUT_ISOLATION"],
        product_authority="git_cg.eval.lane_c.judge_input.project_judge_input",
    )


def _collect_pack_identities(
    ev: Mapping[str, Any],
    rows: list[ScoreResultV1],
) -> tuple[list[str], list[str], list[str]]:
    """Return (pack_identities, content_hashes, pin_refs) from run evidence + rows."""
    identities: list[str] = []
    hashes: list[str] = []
    pin_refs: list[str] = []

    def _add_identity(raw: Any) -> None:
        """Record a ``prompt_pack_v1@<64-hex>`` identity and its digest when well-formed."""
        if isinstance(raw, str) and raw.startswith("prompt_pack_v1@") and raw not in identities:
            identities.append(raw)
            digest = raw.split("@", 1)[1]
            # Same 64-hex honesty gate as content_sha256 (fail closed on short digests).
            if isinstance(digest, str) and len(digest) == 64 and digest not in hashes:
                hashes.append(digest)

    def _add_hash(raw: Any) -> None:
        if isinstance(raw, str) and len(raw) == 64 and raw not in hashes:
            hashes.append(raw)

    for key in ("pack_identity", "prompt_pack_pin", "pack_identities"):
        val = ev.get(key)
        if isinstance(val, list):
            for item in val:
                _add_identity(item)
        else:
            _add_identity(val)
    for key in ("content_sha256", "prompt_pack_hash", "content_hashes"):
        val = ev.get(key)
        if isinstance(val, list):
            for item in val:
                _add_hash(item)
        else:
            _add_hash(val)
    raw_pins = ev.get("pin_refs")
    if isinstance(raw_pins, list):
        for p in raw_pins:
            if isinstance(p, str) and p not in pin_refs:
                pin_refs.append(p)
            _add_identity(p)

    for payload in _cprime_row_evidence(rows):
        _add_identity(payload.get("pack_identity"))
        _add_hash(payload.get("content_sha256"))
        for p in payload.get("_pin_refs") or []:
            if isinstance(p, str) and p not in pin_refs:
                pin_refs.append(p)
            _add_identity(p)

    return identities, hashes, pin_refs


def _score_prompt_pack_pinned(
    ev: Mapping[str, Any],
    rows: list[ScoreResultV1],
) -> ScoreResultV1:
    """``h.prompt_pack_pinned`` — pack pin present; universe fingerprint pinned."""
    identities, hashes, pin_refs = _collect_pack_identities(ev, rows)
    fp = ev.get("universe_fingerprint")
    fp_pinned = True
    fp_status = None
    if isinstance(fp, Mapping):
        fp_status = fp.get("status")
        # Absent universe root is honest and non-blocking; present+unpinned fails.
        fp_pinned = bool(fp.get("pinned")) if fp.get("root_present") is True else True
    pack_ok = bool(identities) or bool(hashes)
    # Also accept pin_refs carrying prompt_pack_v1@…
    if not pack_ok:
        pack_ok = any(isinstance(p, str) and p.startswith("prompt_pack_v1@") for p in pin_refs)

    ok = pack_ok and fp_pinned
    if ok:
        reason = None
    elif not pack_ok:
        reason = "prompt_pack_pin_missing"
    else:
        reason = "universe_fingerprint_unpinned"
    return make_score(
        "h.prompt_pack_pinned",
        ok,
        reason=reason,
        evidence={
            "lane_c_enabled": True,
            "pack_identities": identities,
            "content_hashes": hashes,
            "pin_refs": pin_refs,
            "universe_fingerprint_status": fp_status,
            "universe_fingerprint_pinned": fp_pinned,
        },
        failure_ids=None if ok else ["EVAL_PROMPT_PACK_PIN"],
        product_authority="git_cg.eval.lane_c.prompt_pack",
    )


def _score_prompt_pack_hash_known(
    ev: Mapping[str, Any],
    rows: list[ScoreResultV1],
) -> ScoreResultV1:
    """``h.prompt_pack_hash_known`` — content hash recorded for the run."""
    identities, hashes, pin_refs = _collect_pack_identities(ev, rows)
    ok = bool(hashes) or any(
        isinstance(i, str) and i.startswith("prompt_pack_v1@") and len(i.split("@", 1)[1]) == 64 for i in identities
    )
    return make_score(
        "h.prompt_pack_hash_known",
        ok,
        reason=None if ok else "prompt_pack_hash_missing",
        evidence={
            "lane_c_enabled": True,
            "content_hashes": hashes,
            "pack_identities": identities,
            "pin_refs": [p for p in pin_refs if isinstance(p, str) and p.startswith("prompt_pack_v1@")],
        },
        failure_ids=None if ok else ["EVAL_PROMPT_PACK_HASH"],
        product_authority="git_cg.eval.lane_c.prompt_pack.prompt_pack_content_hash",
    )


def _score_prompt_pack_suite_fresh(
    ev: Mapping[str, Any],
    rows: list[ScoreResultV1],
    *,
    suite_snapshot_pin: str | None,
) -> ScoreResultV1:
    """``h.prompt_pack_suite_fresh`` — pack change has local suite pin (FIND-028).

    Local law: a known prompt-pack pin plus a non-empty suite snapshot pin is
    fresh enough for offline S5. Cloud prompt churn without a local suite pin
    fails (doctor-red class). Severity remains catalog ``warn``.

    """
    identities, hashes, _pin_refs = _collect_pack_identities(ev, rows)
    pack_known = bool(identities) or bool(hashes)
    snap_ok = bool(suite_snapshot_pin and str(suite_snapshot_pin).strip())
    # Explicit freshness flag from runner wins when provided.
    explicit = ev.get("prompt_pack_suite_fresh")
    if explicit is not None:
        ok = bool(explicit)
        reason = None if ok else "prompt_pack_suite_stale"
    else:
        ok = pack_known and snap_ok
        if ok:
            reason = None
        elif not pack_known:
            reason = "prompt_pack_pin_missing"
        else:
            reason = "suite_snapshot_missing_for_pack"
    return make_score(
        "h.prompt_pack_suite_fresh",
        ok,
        reason=reason,
        evidence={
            "lane_c_enabled": True,
            "pack_known": pack_known,
            "suite_snapshot_pin": suite_snapshot_pin,
            "pack_identities": identities,
            "content_hashes": hashes,
            "finding": "FIND-028",
        },
        failure_ids=None if ok else ["FIND-028", "EVAL_PROMPT_PACK_SUITE_FRESH"],
        product_authority="git_cg.eval.scoring.family_h.score_family_h_cprime",
    )
