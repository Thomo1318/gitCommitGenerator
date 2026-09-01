"""Lab / Lane C advisory operator surface.

Nested under ``git-cg eval lab …`` only. Signals are advisory: they never
become CI, golden, product-accept, or promotion authority.

Import law: no binder, no Opik SDK, no provider SDK at import time. Status and
pins stay offline and secret-safe. ``run`` delegates to ``run_lane_c`` and
preserves its gated, non-authoritative semantics.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from git_cg.eval.lane_c.availability import (
    LaneCAvailability,
    evaluate_judge_availability,
)
from git_cg.eval.lane_c.eligibility import (
    LaneCEligibility,
    evaluate_semantic_cohort_eligibility,
)
from git_cg.eval.lane_c.runner import LaneCRunResult, run_lane_c
from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin
from git_cg.eval.score_result import ScoreResultV1

# Closed authority markers for lab envelopes (operator-facing).
LAB_AUTHORITY: str = "advisory"
LAB_PRODUCT_GATE: bool = False
LAB_COMMAND_PREFIX: str = "eval lab"

FORBIDDEN_LAB_VERBS: frozenset[str] = frozenset(
    {
        "doctor",
        "amend-brief",
        "review-queue",
        "review_queue",
        "amend_brief",
    }
)


def _eligibility_payload(eligibility: LaneCEligibility) -> dict[str, Any]:
    """Serialize eligibility without secrets or free-form credential material."""
    return {
        "allows_lane_c": eligibility.allows_lane_c,
        "deterministic_pass": eligibility.deterministic_pass,
        "lab_override": eligibility.lab_override,
        "pins_resolvable": eligibility.pins_resolvable,
        "eligible": eligibility.eligible,
        "diagnostic_only": eligibility.diagnostic_only,
        "reason": eligibility.reason,
        "reasons": list(eligibility.reasons),
        "gate_disposition": eligibility.gate_disposition,
        "evidence": dict(eligibility.evidence),
    }


def _availability_payload(availability: LaneCAvailability) -> dict[str, Any]:
    """Serialize availability; evidence is already secret-free by contract."""
    evidence = dict(availability.evidence)
    # Never surface raw key material if a future caller leaks it into evidence.
    for banned in ("api_key", "token", "secret", "authorization", "password"):
        evidence.pop(banned, None)
    evidence["raw_key_echoed"] = False
    return {
        "eligible": availability.eligible,
        "credentials_present": availability.credentials_present,
        "client_constructible": availability.client_constructible,
        "available": availability.available,
        "reason": availability.reason,
        "gate_disposition": availability.gate_disposition,
        "execution_code": availability.execution_code,
        "evidence": evidence,
    }


def _score_row_payload(row: ScoreResultV1) -> dict[str, Any]:
    """Dump one advisory score row as plain JSON-compatible data."""
    return row.model_dump(mode="json")


def build_lab_status(
    *,
    deterministic_pass: bool = True,
    allows_lane_c: bool | None = True,
    lab_override: bool | None = False,
    suite: Mapping[str, Any] | None = None,
    judge_model: str | None = None,
    pack_identity: str | None = None,
    sampling_identity: str | None = None,
    output_contract_identity: str | None = None,
    environ: Mapping[str, str] | None = None,
    judge_api_key: str | None = None,
) -> dict[str, Any]:
    """Build offline lab status: eligibility + availability (no network).

    Never resolves provider SDKs. Credential presence is boolean-only.
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
    availability = evaluate_judge_availability(
        eligible=eligibility.eligible,
        judge_api_key=judge_api_key,
        environ=environ,
    )
    return {
        "authority": LAB_AUTHORITY,
        "product_gate": LAB_PRODUCT_GATE,
        "offline": True,
        "eligibility": _eligibility_payload(eligibility),
        "availability": _availability_payload(availability),
    }


def build_lab_pins() -> dict[str, Any]:
    """Present frozen schema_pack and metric_catalog pins for ``eval lab pins``.

    Offline and secret-safe. Reuses existing pin helpers; does not expand
    prompt-pack or sampling pin detail beyond the frozen catalog surface.
    """
    return {
        "authority": LAB_AUTHORITY,
        "product_gate": LAB_PRODUCT_GATE,
        "offline": True,
        "schema_pack_pin": schema_pack_pin(),
        "metric_catalog_pin": metric_catalog_pin(),
    }


def run_lab_advisory(
    metric_ids: Sequence[str] | None = None,
    *,
    deterministic_pass: bool = True,
    allows_lane_c: bool | None = True,
    lab_override: bool | None = False,
    suite: Mapping[str, Any] | None = None,
    judge_model: str | None = None,
    judge_api_key: str | None = None,
    pack_identity: str | None = None,
    sampling_identity: str | None = None,
    output_contract_identity: str | None = None,
    environ: Mapping[str, str] | None = None,
    use_default_metrics: bool = False,
) -> tuple[LaneCRunResult, dict[str, Any]]:
    """Run Lane C through the supported entrypoint; stamp advisory-only metadata.

    Does not install a live judge transport. Without an injectable judge and
    projected input, ``run_lane_c`` stays honest (skip / not-invoked rows).
    """
    result = run_lane_c(
        metric_ids,
        deterministic_pass=deterministic_pass,
        allows_lane_c=allows_lane_c,
        lab_override=lab_override,
        suite=suite,
        judge_model=judge_model,
        judge_api_key=judge_api_key,
        pack_identity=pack_identity,
        sampling_identity=sampling_identity,
        output_contract_identity=output_contract_identity,
        environ=environ,
        use_default_metrics=use_default_metrics,
    )
    payload = {
        "authority": LAB_AUTHORITY,
        "product_gate": LAB_PRODUCT_GATE,
        "advisory_only": True,
        "never_auto_promote": True,
        "invoked": result.invoked,
        "scored_count": result.scored_count,
        "cprime_ran": result.cprime_ran,
        "eligibility": _eligibility_payload(result.eligibility),
        "availability": _availability_payload(result.availability),
        "evidence": dict(result.evidence),
        "rows": [_score_row_payload(row) for row in result.rows],
    }
    # Scrub accidental secret-shaped keys from top-level evidence copies.
    for banned in ("api_key", "token", "secret", "authorization", "password"):
        payload["evidence"].pop(banned, None)
    return result, payload


def assert_no_forbidden_lab_verbs(command_names: Sequence[str]) -> None:
    """Fail closed when doctor / amend-brief / review-queue leak onto lab_app."""
    found = sorted({name for name in command_names if name in FORBIDDEN_LAB_VERBS})
    if found:
        raise ValueError("lab_app must not register reserved operator verbs: " + ", ".join(found))


__all__ = [
    "FORBIDDEN_LAB_VERBS",
    "LAB_AUTHORITY",
    "LAB_COMMAND_PREFIX",
    "LAB_PRODUCT_GATE",
    "assert_no_forbidden_lab_verbs",
    "build_lab_pins",
    "build_lab_status",
    "run_lab_advisory",
]
