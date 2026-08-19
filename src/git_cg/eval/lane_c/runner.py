"""Lane C' gated runner skeleton (C-RUN / Slice 1 S5a).

Supported execution API for C' rows. Slice 1 implements authorization,
availability, closed-taxonomy skips, and honest non-invocation evidence.
Pinned judge transport lands in Slice 4 — this skeleton never opens a network
socket and never imports a provider SDK.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from git_cg.eval.lane_c.availability import (
    LaneCAvailability,
    SecretResolver,
    evaluate_judge_availability,
)
from git_cg.eval.lane_c.eligibility import (
    DEFAULT_PACK_IDENTITY,
    LaneCEligibility,
    evaluate_semantic_cohort_eligibility,
)
from git_cg.eval.lane_c.prompt_pack import (
    PromptPackError,
    prompt_pack_pin,
    record_universe_fingerprint,
    resolve_judge_pack,
)
from git_cg.eval.lane_c.taxonomy import (
    EXEC_COHORT_INELIGIBLE,
    EXEC_JUDGE_NOT_INVOKED,
    EXEC_LAB_OVERRIDE_DIAGNOSTIC,
    EXEC_PACK_DECODE_ERROR,
    EXEC_PACK_UNRESOLVABLE,
    EXEC_UNAVAILABLE_CREDS,
    FAILURE_COHORT_INELIGIBLE,
    FAILURE_JUDGE_NOT_INVOKED,
    FAILURE_LAB_OVERRIDE_DIAGNOSTIC,
    FAILURE_PACK_DECODE_ERROR,
    FAILURE_PACK_UNRESOLVABLE,
    GATE_JUDGE_UNAVAILABLE,
    GATE_LAB_OVERRIDE_DIAGNOSTIC,
    GATE_PROMPT_PACK_MISSING,
    assert_execution_code,
    failure_id_for,
    map_gate_to_execution,
)
from git_cg.eval.score_result import ScoreResultV1
from git_cg.eval.scoring.context import live_pin_refs
from git_cg.eval.scoring.result_builder import make_score

# Default C' metrics when a caller opts into defaults (Slice 4 wires scoring).
DEFAULT_LANE_C_METRICS: tuple[str, ...] = (
    "cprime.geval_craft",
    "cprime.geval_relevance",
)


@dataclass(frozen=True, slots=True)
class LaneCRunResult:
    """Runner result: advisory rows + eligibility/availability + honest counters."""

    rows: list[ScoreResultV1]
    eligibility: LaneCEligibility
    availability: LaneCAvailability
    invoked: bool
    scored_count: int
    cprime_ran: bool
    evidence: dict[str, Any] = field(default_factory=dict)


def _skip_row(
    metric_id: str,
    *,
    execution_code: str,
    eligibility: LaneCEligibility,
    availability: LaneCAvailability | None,
    extra_evidence: Mapping[str, Any] | None = None,
    gate_disposition: str | None = None,
    pin_refs: list[str] | None = None,
) -> ScoreResultV1:
    """Emit one advisory skip row with closed-set reason + failure_id."""
    code = assert_execution_code(execution_code)
    if gate_disposition is not None:
        map_gate_to_execution(gate_disposition, code)
    fid = failure_id_for(code)
    evidence: dict[str, Any] = {
        "skipped": True,
        "execution_code": code,
        "gate_disposition": gate_disposition,
        "eligible": eligibility.eligible,
        "diagnostic_only": eligibility.diagnostic_only,
        "allows_lane_c": eligibility.allows_lane_c,
        "deterministic_pass": eligibility.deterministic_pass,
        "lab_override": eligibility.lab_override,
        "pins_resolvable": eligibility.pins_resolvable,
        "invoked": False,
        "scored_count": 0,
        "cprime_ran": False,
        "eligibility_reason": eligibility.reason,
    }
    if availability is not None:
        evidence.update(
            {
                "available": availability.available,
                "credentials_present": availability.credentials_present,
                "client_constructible": availability.client_constructible,
                "availability_reason": availability.reason,
            }
        )
    if extra_evidence:
        # Hard ban: never allow secret-looking keys from callers.
        for k, v in extra_evidence.items():
            lk = str(k).lower()
            if any(s in lk for s in ("api_key", "secret", "password", "token", "authorization")):
                continue
            evidence[k] = v
    row = make_score(
        metric_id,
        0.0,
        passed=None,
        reason=code,
        evidence=evidence,
        failure_ids=[fid] if fid else None,
        pin_refs=pin_refs,
    )
    # Advisory continuous metrics must not auto-derive passed=True (D30 footgun).
    return row.model_copy(update={"passed": None})


def run_lane_c(
    metric_ids: Sequence[str] | None = None,
    *,
    deterministic_pass: bool,
    allows_lane_c: bool | None = None,
    lab_override: bool | None = None,
    suite: Mapping[str, Any] | None = None,
    judge_model: str | None = None,
    judge_api_key: str | None = None,
    pack_identity: str | None = None,
    sampling_identity: str | None = None,
    output_contract_identity: str | None = None,
    environ: Mapping[str, str] | None = None,
    secret_resolver: SecretResolver | None = None,
    client_factory_ok: bool | None = None,
    use_default_metrics: bool = False,
    prompt_root: Path | None = None,
    universe_root: Path | None = None,
) -> LaneCRunResult:
    """Run the gated Lane C' cohort skeleton.

    Behaviour (Slice 1):

    1. Evaluate authorization-only eligibility (no secrets).
    2. Ineligible → one ``cohort_ineligible`` skip per metric; no side effects.
    3. ``lab_override`` diagnostic (det fail) → ``lab_override_diagnostic`` skips;
       **zero** judge side effects even when credentials exist.
    4. Eligible but unavailable → ``unavailable_creds`` / constructibility skips.
    5. Eligible + available → resolve local ``prompt_pack_v1`` (Slice 2).
       Missing/malformed/non-UTF-8 packs skip as ``pack_unresolvable`` /
       ``pack_decode_error``. Resolved packs still do **not** invoke judges
       (Slice 4); honest ``judge_not_invoked`` skips.
    6. Explicit empty ``metric_ids`` → no rows (``[]``).
    7. Unknown metric ids fail closed via catalog (``KeyError``).

    Never raises on missing credentials. Never imports provider SDKs.
    """
    eligibility = evaluate_semantic_cohort_eligibility(
        deterministic_pass=deterministic_pass,
        allows_lane_c=allows_lane_c,
        lab_override=lab_override,
        suite=suite,
        judge_model=judge_model,
        pack_identity=pack_identity,
        sampling_identity=sampling_identity,
        output_contract_identity=output_contract_identity,
        environ=environ,
    )

    if metric_ids is None:
        ids: list[str] = list(DEFAULT_LANE_C_METRICS) if use_default_metrics else []
    else:
        ids = list(metric_ids)

    # Availability is always computed for honest evidence, even when ineligible.
    availability = evaluate_judge_availability(
        eligible=eligibility.eligible,
        judge_api_key=judge_api_key,
        environ=environ,
        secret_resolver=secret_resolver,
        client_factory_ok=client_factory_ok,
    )

    run_evidence: dict[str, Any] = {
        "eligible": eligibility.eligible,
        "available": availability.available,
        "invoked": False,
        "scored_count": 0,
        "cprime_ran": False,
        "diagnostic_only": eligibility.diagnostic_only,
        "lab_override": eligibility.lab_override,
        "metric_ids": list(ids),
        "eligibility_reason": eligibility.reason,
        "availability_reason": availability.reason,
    }

    if not ids:
        return LaneCRunResult(
            rows=[],
            eligibility=eligibility,
            availability=availability,
            invoked=False,
            scored_count=0,
            cprime_ran=False,
            evidence=run_evidence,
        )

    rows: list[ScoreResultV1] = []

    # 1) Authorization closed.
    if not eligibility.eligible:
        gd = eligibility.gate_disposition or "scope_gate_reject"
        # pins-invalid and suite-reject both map through scope_gate_reject;
        # det-fail maps through det_fail_excluded. Both allow cohort_ineligible.
        if gd not in {"det_fail_excluded", "scope_gate_reject"}:
            gd = "scope_gate_reject"
        map_gate_to_execution(gd, EXEC_COHORT_INELIGIBLE)
        for mid in ids:
            rows.append(
                _skip_row(
                    mid,
                    execution_code=EXEC_COHORT_INELIGIBLE,
                    eligibility=eligibility,
                    availability=availability,
                    gate_disposition=gd,
                    extra_evidence={"failure_class": FAILURE_COHORT_INELIGIBLE},
                )
            )
        return LaneCRunResult(
            rows=rows,
            eligibility=eligibility,
            availability=availability,
            invoked=False,
            scored_count=0,
            cprime_ran=False,
            evidence=run_evidence,
        )

    # 2) lab_override diagnostic path — eligible but never invoke judges (F-B).
    if eligibility.diagnostic_only:
        map_gate_to_execution(GATE_LAB_OVERRIDE_DIAGNOSTIC, EXEC_LAB_OVERRIDE_DIAGNOSTIC)
        for mid in ids:
            rows.append(
                _skip_row(
                    mid,
                    execution_code=EXEC_LAB_OVERRIDE_DIAGNOSTIC,
                    eligibility=eligibility,
                    availability=availability,
                    gate_disposition=GATE_LAB_OVERRIDE_DIAGNOSTIC,
                    extra_evidence={"failure_class": FAILURE_LAB_OVERRIDE_DIAGNOSTIC},
                )
            )
        return LaneCRunResult(
            rows=rows,
            eligibility=eligibility,
            availability=availability,
            invoked=False,
            scored_count=0,
            cprime_ran=False,
            evidence=run_evidence,
        )

    # 3) Eligible but unavailable (creds / client).
    if not availability.available:
        code = availability.execution_code or EXEC_UNAVAILABLE_CREDS
        gd = availability.gate_disposition or GATE_JUDGE_UNAVAILABLE
        map_gate_to_execution(gd, code)
        for mid in ids:
            rows.append(
                _skip_row(
                    mid,
                    execution_code=code,
                    eligibility=eligibility,
                    availability=availability,
                    gate_disposition=gd,
                )
            )
        return LaneCRunResult(
            rows=rows,
            eligibility=eligibility,
            availability=availability,
            invoked=False,
            scored_count=0,
            cprime_ran=False,
            evidence=run_evidence,
        )

    # 4) Eligible + available: resolve local prompt packs (Slice 2) then
    # honest non-invocation (Slice 4 owns judge transport).
    fingerprint = record_universe_fingerprint(universe_root)
    run_evidence["universe_fingerprint"] = fingerprint.as_dict()

    if fingerprint.root_present and not fingerprint.pinned:
        map_gate_to_execution(GATE_PROMPT_PACK_MISSING, EXEC_PACK_UNRESOLVABLE)
        extra = {
            "failure_class": FAILURE_PACK_UNRESOLVABLE,
            "universe_fingerprint": fingerprint.as_dict(),
            "sampling_identity": eligibility.evidence.get("sampling_identity"),
            "output_contract_identity": eligibility.evidence.get("output_contract_identity"),
        }
        for mid in ids:
            rows.append(
                _skip_row(
                    mid,
                    execution_code=EXEC_PACK_UNRESOLVABLE,
                    eligibility=eligibility,
                    availability=availability,
                    gate_disposition=GATE_PROMPT_PACK_MISSING,
                    extra_evidence=extra,
                )
            )
        return LaneCRunResult(
            rows=rows,
            eligibility=eligibility,
            availability=availability,
            invoked=False,
            scored_count=0,
            cprime_ran=False,
            evidence=run_evidence,
        )

    # Authorization may still carry the Slice-1 deferred placeholder.
    # Byte identity is computed from local files; only a real sha256 pin is
    # treated as an expected-identity constraint.
    expected_pack = pack_identity
    if expected_pack in {None, "", DEFAULT_PACK_IDENTITY}:
        expected_pack = None
    for mid in ids:
        try:
            pack = resolve_judge_pack(
                mid,
                prompt_root=prompt_root,
                expected_identity=expected_pack,
            )
        except PromptPackError as exc:
            code = exc.code if exc.code in {EXEC_PACK_UNRESOLVABLE, EXEC_PACK_DECODE_ERROR} else EXEC_PACK_UNRESOLVABLE
            fid = FAILURE_PACK_DECODE_ERROR if code == EXEC_PACK_DECODE_ERROR else FAILURE_PACK_UNRESOLVABLE
            map_gate_to_execution(GATE_PROMPT_PACK_MISSING, code)
            rows.append(
                _skip_row(
                    mid,
                    execution_code=code,
                    eligibility=eligibility,
                    availability=availability,
                    gate_disposition=GATE_PROMPT_PACK_MISSING,
                    extra_evidence={
                        "failure_class": fid,
                        "pack_error": str(exc),
                        "universe_fingerprint": fingerprint.as_dict(),
                        "sampling_identity": eligibility.evidence.get("sampling_identity"),
                        "output_contract_identity": eligibility.evidence.get("output_contract_identity"),
                    },
                )
            )
            continue

        pin = prompt_pack_pin(pack)
        rows.append(
            _skip_row(
                mid,
                execution_code=EXEC_JUDGE_NOT_INVOKED,
                eligibility=eligibility,
                availability=availability,
                gate_disposition=None,
                pin_refs=live_pin_refs(prompt_pack=pin),
                extra_evidence={
                    "failure_class": FAILURE_JUDGE_NOT_INVOKED,
                    "spine_stage": "s5b_prompt_pack",
                    "next_stage": "judge_transport",
                    "pack_id": pack["pack_id"],
                    "pack_identity": pin,
                    "content_sha256": pack["content_sha256"],
                    "sampling_identity": eligibility.evidence.get("sampling_identity"),
                    "output_contract_identity": eligibility.evidence.get("output_contract_identity"),
                    "universe_fingerprint": fingerprint.as_dict(),
                },
            )
        )
    return LaneCRunResult(
        rows=rows,
        eligibility=eligibility,
        availability=availability,
        invoked=False,
        scored_count=0,
        cprime_ran=False,
        evidence=run_evidence,
    )
