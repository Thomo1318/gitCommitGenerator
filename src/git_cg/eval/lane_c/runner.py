"""Lane C' gated runner (C-RUN / Slice 4 S5c).

Supported execution API for C' rows. Authorization, availability, closed-taxonomy
skips, prompt-pack resolution, and optional injectable pinned-judge scoring.
Default path never opens a network socket and never imports a provider SDK.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from git_cg.eval.lane_c.advisory import make_advisory_score, make_advisory_skip
from git_cg.eval.lane_c.availability import (
    LaneCAvailability,
    SecretResolver,
    evaluate_judge_availability,
)
from git_cg.eval.lane_c.diagnostics import resolve_richer_rubric_metrics
from git_cg.eval.lane_c.eligibility import (
    DEFAULT_PACK_IDENTITY,
    LaneCEligibility,
    evaluate_semantic_cohort_eligibility,
)
from git_cg.eval.lane_c.judge import JudgeFn, run_pinned_judge
from git_cg.eval.lane_c.judge_input import (
    JudgeInput,
    JudgeInputError,
    project_judge_input,
)
from git_cg.eval.lane_c.prompt_pack import (
    PromptPackError,
    load_pack_prompt_text,
    prompt_pack_pin,
    record_universe_fingerprint,
    resolve_judge_pack,
)
from git_cg.eval.lane_c.taxonomy import (
    EXEC_COHORT_INELIGIBLE,
    EXEC_EMPTY_INPUT,
    EXEC_JUDGE_NOT_INVOKED,
    EXEC_LAB_OVERRIDE_DIAGNOSTIC,
    EXEC_OVERSIZE_INPUT,
    EXEC_PACK_DECODE_ERROR,
    EXEC_PACK_UNRESOLVABLE,
    EXEC_PARSE_ERROR,
    EXEC_SCORED,
    EXEC_TIMEOUT,
    EXEC_TRANSPORT_ERROR,
    EXEC_UNAVAILABLE_CREDS,
    EXECUTION_CODES,
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

# Default C' metrics when a caller opts into defaults.
DEFAULT_LANE_C_METRICS: tuple[str, ...] = (
    "cprime.geval_craft",
    "cprime.geval_relevance",
)

_INPUT_SKIP_CODES = frozenset({EXEC_EMPTY_INPUT, EXEC_OVERSIZE_INPUT, EXEC_PARSE_ERROR})
_JUDGE_FAIL_CODES = frozenset(
    {
        EXEC_EMPTY_INPUT,
        EXEC_OVERSIZE_INPUT,
        EXEC_TIMEOUT,
        EXEC_TRANSPORT_ERROR,
        EXEC_PARSE_ERROR,
    }
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


def _base_evidence(
    *,
    eligibility: LaneCEligibility,
    availability: LaneCAvailability | None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Secret-free eligibility/availability evidence base (+ optional extras)."""
    evidence: dict[str, Any] = {
        "eligible": eligibility.eligible,
        "diagnostic_only": eligibility.diagnostic_only,
        "allows_lane_c": eligibility.allows_lane_c,
        "deterministic_pass": eligibility.deterministic_pass,
        "lab_override": eligibility.lab_override,
        "pins_resolvable": eligibility.pins_resolvable,
        "eligibility_reason": eligibility.reason,
        "sampling_identity": eligibility.evidence.get("sampling_identity"),
        "output_contract_identity": eligibility.evidence.get("output_contract_identity"),
        "judge_model_pin": eligibility.evidence.get("judge_model_pin"),
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
    if extra:
        for k, v in extra.items():
            lk = str(k).lower()
            if any(s in lk for s in ("api_key", "secret", "password", "token", "authorization")):
                continue
            evidence[k] = v
    return evidence


def _skip_row(
    metric_id: str,
    *,
    execution_code: str,
    eligibility: LaneCEligibility,
    availability: LaneCAvailability | None,
    extra_evidence: Mapping[str, Any] | None = None,
    gate_disposition: str | None = None,
    pin_refs: list[str] | None = None,
    duration_ms: int | float | None = None,
) -> ScoreResultV1:
    """Emit one advisory skip row with closed-set reason + failure_id."""
    code = assert_execution_code(execution_code)
    if gate_disposition is not None:
        map_gate_to_execution(gate_disposition, code)
    fid = failure_id_for(code)
    evidence = _base_evidence(
        eligibility=eligibility,
        availability=availability,
        extra=extra_evidence,
    )
    # Preserve an explicit invoked flag from callers (e.g. transport attempted),
    # otherwise default to False for pre-invoke skips.
    invoked = bool(evidence["invoked"]) if "invoked" in evidence else False
    evidence.update(
        {
            "skipped": True,
            "execution_code": code,
            "gate_disposition": gate_disposition,
            "invoked": invoked,
            "scored_count": 0,
            "cprime_ran": False,
        }
    )
    return make_advisory_skip(
        metric_id,
        reason=code,
        evidence=evidence,
        failure_ids=[fid] if fid else None,
        pin_refs=pin_refs,
        duration_ms=duration_ms,
    )


def _resolve_projected_input(
    *,
    judge_input: JudgeInput | Mapping[str, Any] | None,
    final_accept_evidence: Any | None,
    lab_override: bool,
    max_input_chars: int | None,
) -> tuple[JudgeInput | None, str | None, str | None]:
    """Return (projected, skip_code, error_note). Never raises."""
    if judge_input is None and final_accept_evidence is None:
        return None, None, None
    try:
        kwargs: dict[str, Any] = {"lab_override": lab_override}
        if max_input_chars is not None:
            kwargs["max_input_chars"] = max_input_chars
        if isinstance(judge_input, JudgeInput):
            return judge_input, None, None
        if judge_input is not None:
            return project_judge_input(judge_input, **kwargs), None, None
        return project_judge_input(final_accept_evidence, **kwargs), None, None
    except JudgeInputError as exc:
        code = getattr(exc, "code", None)
        if code in _INPUT_SKIP_CODES:
            return None, str(code), str(exc)[:200]
        # Isolation / linkage failures are host-side contract errors, not quality.
        return None, EXEC_PARSE_ERROR, str(exc)[:200]
    except Exception as exc:
        return None, EXEC_PARSE_ERROR, f"{type(exc).__name__}: {exc}"[:200]


def _pack_dir_for(pack: Mapping[str, Any], prompt_root: Path | None) -> Path:
    """Return the pack directory, preferring the path recorded at resolve time."""
    from git_cg.eval.paths import REPO_ROOT

    recorded = pack.get("pack_dir") or pack.get("_pack_dir")
    if isinstance(recorded, Path):
        return recorded
    if isinstance(recorded, str) and recorded.strip():
        return Path(recorded)
    pack_id = str(pack.get("pack_id") or "")
    suffix = pack_id.removeprefix("lane_c_")
    if prompt_root is not None:
        return Path(prompt_root) / suffix
    return REPO_ROOT / "prompts" / "eval" / "lane_c" / suffix


def aggregate_pack_evidence(rows: Sequence[Any]) -> dict[str, Any]:
    """Aggregate pack_identity / content_sha256 evidence from C' rows (exported)."""
    pack_ids: list[str] = []
    hashes: list[str] = []
    for row in rows:
        payload = getattr(row, "evidence", None) or {}
        if not isinstance(payload, Mapping):
            continue
        pid = payload.get("pack_identity")
        if isinstance(pid, str) and pid not in pack_ids:
            pack_ids.append(pid)
        digest = payload.get("content_sha256")
        if isinstance(digest, str) and digest not in hashes:
            hashes.append(digest)
    out: dict[str, Any] = {}
    if pack_ids:
        out["pack_identities"] = pack_ids
        out["pack_identity"] = pack_ids[0]
    if hashes:
        out["content_hashes"] = hashes
        out["content_sha256"] = hashes[0]
    return out


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
    richer_rubrics: bool | Sequence[str] | None = None,
    prompt_root: Path | None = None,
    universe_root: Path | None = None,
    judge_fn: JudgeFn | None = None,
    judge_input: JudgeInput | Mapping[str, Any] | None = None,
    final_accept_evidence: Any | None = None,
    max_input_chars: int | None = None,
) -> LaneCRunResult:
    """Run the gated Lane C' cohort.

     Behaviour:

     1. Evaluate authorization-only eligibility (no secrets).
     2. Ineligible → one ``cohort_ineligible`` skip per metric; no side effects.
     3. ``lab_override`` diagnostic (det fail) → ``lab_override_diagnostic`` skips;
        **zero** judge side effects even when credentials exist.
     4. Eligible but unavailable → ``unavailable_creds`` / constructibility skips.
     5. Eligible + available → resolve local ``prompt_pack_v1``.
        Missing/malformed/non-UTF-8 packs skip as ``pack_unresolvable`` /
        ``pack_decode_error``.
     6. Without injectable ``judge_fn`` **or** projected judge input → honest
        ``judge_not_invoked`` (backward compatible with Slice 1-3).
     7. With both → invoke pinned judge per metric; emit advisory scored/skip rows.
     8. Explicit empty ``metric_ids`` → no rows (``[]``) — never expands to all R1 (D13).
     9. Unknown metric ids fail closed via catalog (``KeyError``).
    10. ``richer_rubrics`` is off-by-default; extends None/default or non-empty
        metric lists only (advisory; packs may be unresolvable).

     Never raises on missing credentials. Never imports provider SDKs at module
     import time. Judge exceptions never abort the case.

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
        # R1 opt-in may extend the default/empty-None path only.
        richer = resolve_richer_rubric_metrics(enabled=richer_rubrics)
        for mid in richer:
            if mid not in ids:
                ids.append(mid)
    else:
        # D13: explicit empty metric list emits zero C' rows (not "all R1").
        ids = list(metric_ids)
        if ids:
            richer = resolve_richer_rubric_metrics(enabled=richer_rubrics)
            for mid in richer:
                if mid not in ids:
                    ids.append(mid)

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

    # 2) lab_override diagnostic path - eligible but never invoke judges (F-B).
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

    # 4) Eligible + available: resolve packs, then optionally invoke judge.
    fingerprint = record_universe_fingerprint(universe_root)
    run_evidence["universe_fingerprint"] = fingerprint.as_dict()

    if fingerprint.root_present and not fingerprint.pinned:
        map_gate_to_execution(GATE_PROMPT_PACK_MISSING, EXEC_PACK_UNRESOLVABLE)
        extra = {
            "failure_class": FAILURE_PACK_UNRESOLVABLE,
            "universe_fingerprint": fingerprint.as_dict(),
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

    expected_pack = pack_identity
    if expected_pack in {None, "", DEFAULT_PACK_IDENTITY}:
        expected_pack = None

    projected, input_skip, input_note = _resolve_projected_input(
        judge_input=judge_input,
        final_accept_evidence=final_accept_evidence,
        lab_override=bool(eligibility.lab_override),
        max_input_chars=max_input_chars,
    )

    # Family H honesty (D39): surface isolation/projection outcome on run evidence.
    # Host size guards (empty/oversize) are not isolation leaks. parse_error and
    # other projection failures are treated as isolation/contract failures.
    if input_skip is None and projected is not None:
        run_evidence["judge_input_projected"] = True
        run_evidence["judge_input_isolated"] = True
        run_evidence["judge_input_present"] = True
    elif input_skip is not None:
        run_evidence["judge_input_projected"] = False
        run_evidence["judge_input_skip_code"] = input_skip
        run_evidence["judge_input_error"] = input_note
        run_evidence["input_error"] = input_note
        run_evidence["judge_input_isolated"] = input_skip in {
            EXEC_EMPTY_INPUT,
            EXEC_OVERSIZE_INPUT,
        }
    elif judge_input is None and final_accept_evidence is None:
        run_evidence["judge_input_projected"] = False
        run_evidence["judge_input_present"] = False

    # Host-guard / projection failure before any judge call.
    if input_skip is not None:
        for mid in ids:
            rows.append(
                _skip_row(
                    mid,
                    execution_code=input_skip,
                    eligibility=eligibility,
                    availability=availability,
                    gate_disposition=None,
                    extra_evidence={
                        "failure_class": failure_id_for(input_skip),
                        "input_error": input_note,
                        "judge_input_isolated": run_evidence.get("judge_input_isolated"),
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

    can_invoke = judge_fn is not None and projected is not None
    model_pin = str(eligibility.evidence.get("judge_model_pin") or judge_model or "")
    sampling_pin = str(eligibility.evidence.get("sampling_identity") or "")
    output_pin = str(eligibility.evidence.get("output_contract_identity") or "")

    invoked = False
    scored_count = 0

    for mid in ids:
        try:
            pack = resolve_judge_pack(
                mid,
                prompt_root=prompt_root,
                expected_identity=expected_pack,
            )
            # Record resolved directory so loaders do not re-derive pack_id→path.
            if "pack_dir" not in pack and "_pack_dir" not in pack:
                pack = dict(pack)
                pack["pack_dir"] = str(_pack_dir_for(pack, prompt_root))
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
                        "pack_error": str(exc)[:200],
                        "universe_fingerprint": fingerprint.as_dict(),
                    },
                )
            )
            continue

        pin = prompt_pack_pin(pack)
        pin_refs = live_pin_refs(prompt_pack=pin)
        # Identity pins for scored rows.
        for extra_pin in (model_pin, sampling_pin, output_pin):
            if extra_pin and extra_pin not in pin_refs:
                pin_refs.append(extra_pin)

        if not can_invoke:
            rows.append(
                _skip_row(
                    mid,
                    execution_code=EXEC_JUDGE_NOT_INVOKED,
                    eligibility=eligibility,
                    availability=availability,
                    gate_disposition=None,
                    pin_refs=pin_refs,
                    extra_evidence={
                        "failure_class": FAILURE_JUDGE_NOT_INVOKED,
                        "spine_stage": "s5c_judge_ready",
                        "next_stage": "judge_transport",
                        "pack_id": pack["pack_id"],
                        "pack_identity": pin,
                        "content_sha256": pack["content_sha256"],
                        "universe_fingerprint": fingerprint.as_dict(),
                        "judge_fn_present": judge_fn is not None,
                        "judge_input_present": projected is not None,
                    },
                )
            )
            continue

        # Invoke pinned judge (exceptions never escape).
        try:
            pack_dir = _pack_dir_for(pack, prompt_root)
            prompt_text = load_pack_prompt_text(pack_dir)
        except PromptPackError as exc:
            code = exc.code if exc.code in {EXEC_PACK_UNRESOLVABLE, EXEC_PACK_DECODE_ERROR} else EXEC_PACK_DECODE_ERROR
            map_gate_to_execution(GATE_PROMPT_PACK_MISSING, code)
            rows.append(
                _skip_row(
                    mid,
                    execution_code=code,
                    eligibility=eligibility,
                    availability=availability,
                    gate_disposition=GATE_PROMPT_PACK_MISSING,
                    pin_refs=pin_refs,
                    extra_evidence={
                        "failure_class": failure_id_for(code),
                        "pack_error": str(exc)[:200],
                        "pack_identity": pin,
                        "universe_fingerprint": fingerprint.as_dict(),
                    },
                )
            )
            continue
        except Exception as exc:
            rows.append(
                _skip_row(
                    mid,
                    execution_code=EXEC_PACK_DECODE_ERROR,
                    eligibility=eligibility,
                    availability=availability,
                    gate_disposition=GATE_PROMPT_PACK_MISSING,
                    pin_refs=pin_refs,
                    extra_evidence={
                        "failure_class": FAILURE_PACK_DECODE_ERROR,
                        "pack_error": f"{type(exc).__name__}"[:80],
                        "pack_identity": pin,
                    },
                )
            )
            continue

        try:
            outcome = run_pinned_judge(
                prompt_text,
                projected,  # type: ignore[arg-type]
                judge_fn=judge_fn,  # type: ignore[arg-type]
                model=model_pin,
            )
        except Exception as exc:
            invoked = True  # exception path: transport was attempted
            rows.append(
                _skip_row(
                    mid,
                    execution_code=EXEC_TRANSPORT_ERROR,
                    eligibility=eligibility,
                    availability=availability,
                    pin_refs=pin_refs,
                    extra_evidence={
                        "failure_class": failure_id_for(EXEC_TRANSPORT_ERROR),
                        "error_type": type(exc).__name__,
                        "pack_identity": pin,
                        "invoked": True,
                    },
                )
            )
            continue

        # Host guards (empty/oversize) return without calling judge_fn.
        row_invoked = outcome.execution_code not in {EXEC_EMPTY_INPUT, EXEC_OVERSIZE_INPUT}
        if row_invoked:
            invoked = True

        duration = outcome.duration_ms
        if outcome.ok and outcome.score is not None:
            scored_count += 1
            evidence = _base_evidence(
                eligibility=eligibility,
                availability=availability,
                extra={
                    "skipped": False,
                    "invoked": True,
                    "cprime_ran": True,
                    "pack_id": pack["pack_id"],
                    "pack_identity": pin,
                    "content_sha256": pack["content_sha256"],
                    "universe_fingerprint": fingerprint.as_dict(),
                    **outcome.as_evidence(),
                },
            )
            rows.append(
                make_advisory_score(
                    mid,
                    outcome.score,
                    reason=EXEC_SCORED,
                    evidence=evidence,
                    pin_refs=pin_refs,
                    duration_ms=duration,
                    rationale=outcome.rationale,
                )
            )
            continue

        code = outcome.execution_code if outcome.execution_code in _JUDGE_FAIL_CODES else EXEC_PARSE_ERROR
        if code not in EXECUTION_CODES:
            code = EXEC_PARSE_ERROR
        # timeout/transport map under judge_unavailable when used as gate disposition.
        gd = None
        if code in {EXEC_TIMEOUT, EXEC_TRANSPORT_ERROR}:
            gd = GATE_JUDGE_UNAVAILABLE
            try:
                map_gate_to_execution(gd, code)
            except Exception:
                gd = None
        evidence = _base_evidence(
            eligibility=eligibility,
            availability=availability,
            extra={
                "skipped": True,
                "invoked": row_invoked,
                "cprime_ran": False,
                "pack_id": pack["pack_id"],
                "pack_identity": pin,
                "content_sha256": pack["content_sha256"],
                "universe_fingerprint": fingerprint.as_dict(),
                **outcome.as_evidence(),
            },
        )
        if gd is not None:
            evidence["gate_disposition"] = gd
        rows.append(
            make_advisory_skip(
                mid,
                reason=code,
                evidence=evidence,
                failure_ids=[failure_id_for(code)] if failure_id_for(code) else None,
                pin_refs=pin_refs,
                duration_ms=duration,
            )
        )

    cprime_ran = bool(invoked and scored_count > 0)
    run_evidence.update(
        {
            "invoked": invoked,
            "scored_count": scored_count,
            "cprime_ran": cprime_ran,
            "judge_input_present": projected is not None,
        }
    )
    run_evidence.update(aggregate_pack_evidence(rows))
    return LaneCRunResult(
        rows=rows,
        eligibility=eligibility,
        availability=availability,
        invoked=invoked,
        scored_count=scored_count,
        cprime_ran=cprime_ran,
        evidence=run_evidence,
    )
