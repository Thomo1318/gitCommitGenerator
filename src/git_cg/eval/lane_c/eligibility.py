"""Lane C' authorization-only eligibility (D4 / C-ELIG).

``gate.semantic_cohort_eligible`` is **entry authorization only**::

    gate.semantic_cohort_eligible =
        suite.allows_lane_c
        AND (gate.deterministic_pass OR suite.lab_override)
        AND judge_identity_pins_resolvable   # model/pack/params — NOT secrets

Credentials, network, and client constructibility are **out of scope** here
(D4' / C-AVAIL). Missing keys must not render a cohort unauthorized.

This module is offline and side-effect free: no network, no provider SDK, no
secret resolution, no raises on missing credentials.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from git_cg.eval.lane_c.taxonomy import (
    EXEC_COHORT_INELIGIBLE,
    EXEC_PIN_INVALID,
    GATE_DET_FAIL_EXCLUDED,
    GATE_LAB_OVERRIDE_DIAGNOSTIC,
    GATE_SCOPE_GATE_REJECT,
)

# Identity pin surface (NOT secrets — never pass through resolve_secret).
ENV_JUDGE_MODEL: Final = "GIT_CG_EVAL_JUDGE_MODEL"

# Optional identity fields (defaults participate in pin_refs evidence).
DEFAULT_PACK_IDENTITY: Final = "prompt_pack_v1@deferred_slice2"
DEFAULT_SAMPLING_IDENTITY: Final = "sampling:temperature=0|max_tokens=256"
DEFAULT_OUTPUT_CONTRACT_IDENTITY: Final = "output_contract:json_object"

# ISO date fragment required for dated/immutable model ids (D8).
_DATED_MODEL_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_LATEST_RE = re.compile(r"(?:^|[^a-z0-9])latest(?:[^a-z0-9]|$)", re.IGNORECASE)


def resolve_allows_lane_c(
    allows_lane_c: bool | None,
    suite: Mapping[str, Any] | None,
) -> bool:
    """Resolve the suite Lane C' opt-in (N19).

    Order: explicit API argument → ``suite.meta.allows_lane_c`` (bool only) →
    ``False``. Lane C' is never on by default.
    """
    if allows_lane_c is not None:
        return bool(allows_lane_c)
    if isinstance(suite, Mapping):
        meta = suite.get("meta")
        if isinstance(meta, Mapping):
            flag = meta.get("allows_lane_c")
            if isinstance(flag, bool):
                return flag
    return False


def resolve_lab_override(
    lab_override: bool | None,
    suite: Mapping[str, Any] | None,
) -> bool:
    """Resolve whether lab override is enabled for a suite.
    
    Parameters:
        lab_override (bool | None): Explicit override setting, taking precedence
            when provided.
        suite (Mapping[str, Any] | None): Suite metadata containing an optional
            boolean ``meta.lab_override`` setting.
    
    Returns:
        bool: The resolved lab override setting, defaulting to ``False``.
    """
    if lab_override is not None:
        return bool(lab_override)
    if isinstance(suite, Mapping):
        meta = suite.get("meta")
        if isinstance(meta, Mapping):
            flag = meta.get("lab_override")
            if isinstance(flag, bool):
                return flag
    return False


def _normalize_model_id(model: str) -> str:
    """Normalise a model identifier by removing leading and trailing whitespace.
    
    Parameters:
    	model (str): The model identifier to normalise.
    
    Returns:
    	str: The model identifier without leading or trailing whitespace.
    """
    return model.strip()


def is_undated_model_alias(model: str) -> bool:
    """
    Determine whether a model identifier is empty, refers to a latest alias, or lacks an ISO date fragment.
    
    Returns:
        bool: `true` if the model identifier is undated or otherwise represents a mutable alias, `false` for a dated identifier.
    """
    m = _normalize_model_id(model)
    if not m:
        return True
    if _LATEST_RE.search(m):
        return True
    if m.lower() == "latest":
        return True
    return _DATED_MODEL_RE.search(m) is None


def judge_identity_pins_resolvable(
    *,
    judge_model: str | None = None,
    pack_identity: str | None = None,
    sampling_identity: str | None = None,
    output_contract_identity: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """
    Validate whether the configured judge identity pins are resolvable.
    
    Parameters:
        judge_model (str | None): Judge model identifier; the environment value is
            used when omitted.
        pack_identity (str | None): Pack identity to validate.
        sampling_identity (str | None): Sampling identity to validate.
        output_contract_identity (str | None): Output-contract identity to validate.
        environ (Mapping[str, str] | None): Environment mapping used for model
            lookup.
    
    Returns:
        bool: `True` when all identity pins are present and valid, `False`
            otherwise.
    """
    env = environ if environ is not None else os.environ
    model = judge_model if judge_model is not None else env.get(ENV_JUDGE_MODEL, "")
    if is_undated_model_alias(model):
        return False

    pack = (pack_identity if pack_identity is not None else DEFAULT_PACK_IDENTITY).strip()
    if not pack:
        return False
    if _LATEST_RE.search(pack):
        return False

    sampling = (sampling_identity if sampling_identity is not None else DEFAULT_SAMPLING_IDENTITY).strip()
    if not sampling:
        return False

    out_contract = (
        output_contract_identity if output_contract_identity is not None else DEFAULT_OUTPUT_CONTRACT_IDENTITY
    ).strip()
    return bool(out_contract)


# Back-compat alias required by Slice 1 symbol list / tip peel surface.
judge_pins_resolvable = judge_identity_pins_resolvable


@dataclass(frozen=True, slots=True)
class LaneCEligibility:
    """Frozen authorization verdict for ``gate.semantic_cohort_eligible`` (C-ELIG).

    ``eligible`` is authorization only — never product/golden pass (D5) and never
    a credential probe (D4'). ``diagnostic_only`` is True when eligibility is
    granted solely via ``lab_override`` on a deterministic-fail cohort.
    """

    allows_lane_c: bool
    deterministic_pass: bool
    lab_override: bool
    pins_resolvable: bool
    eligible: bool
    diagnostic_only: bool
    reason: str
    reasons: tuple[str, ...]
    gate_disposition: str | None
    evidence: dict[str, Any] = field(default_factory=dict)

    # Tip-era alias kept for peel tests / call sites.
    @property
    def judge_pins_resolvable(self) -> bool:
        return self.pins_resolvable


def _pin_evidence(
    *,
    judge_model: str | None,
    pack_identity: str | None,
    sampling_identity: str | None,
    output_contract_identity: str | None,
    environ: Mapping[str, str] | None,
) -> dict[str, Any]:
    """
    Build secret-free evidence describing the configured judge identity pins.
    
    Parameters:
    	judge_model (str | None): Judge model identifier, or the configured environment value when omitted.
    	pack_identity (str | None): Pack identity reference.
    	sampling_identity (str | None): Sampling identity reference.
    	output_contract_identity (str | None): Output-contract identity reference.
    	environ (Mapping[str, str] | None): Environment values used to resolve the judge model.
    
    Returns:
    	dict[str, Any]: Evidence containing pin presence and dating status, identity references, and an indication that secrets were not consulted.
    """
    env = environ if environ is not None else os.environ
    model = judge_model if judge_model is not None else env.get(ENV_JUDGE_MODEL, "")
    model_norm = _normalize_model_id(model)
    pack = (pack_identity if pack_identity is not None else DEFAULT_PACK_IDENTITY).strip()
    sampling = (sampling_identity if sampling_identity is not None else DEFAULT_SAMPLING_IDENTITY).strip()
    out_contract = (
        output_contract_identity if output_contract_identity is not None else DEFAULT_OUTPUT_CONTRACT_IDENTITY
    ).strip()
    return {
        "judge_model_present": bool(model_norm),
        "judge_model_dated": bool(model_norm) and not is_undated_model_alias(model_norm),
        "judge_model_rejected_latest_or_undated": bool(model_norm) and is_undated_model_alias(model_norm),
        # Never echo raw model strings that might be huge; keep short pin token only.
        "judge_model_pin": model_norm[:128] if model_norm else "",
        "pack_identity": pack,
        "sampling_identity": sampling,
        "output_contract_identity": out_contract,
        "pin_refs": [p for p in (model_norm, pack, sampling, out_contract) if p],
        "secrets_consulted": False,
    }


def evaluate_semantic_cohort_eligibility(
    *,
    deterministic_pass: bool,
    allows_lane_c: bool | None = None,
    lab_override: bool | None = None,
    suite: Mapping[str, Any] | None = None,
    judge_model: str | None = None,
    pack_identity: str | None = None,
    sampling_identity: str | None = None,
    output_contract_identity: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> LaneCEligibility:
    """
    Evaluate semantic cohort authorisation using suite scope, deterministic status, lab override, and judge identity pins.
    
    Parameters:
    	deterministic_pass (bool): Whether the cohort passed deterministic evaluation.
    	allows_lane_c (bool | None): Explicit suite opt-in, or ``None`` to resolve it from ``suite``.
    	lab_override (bool | None): Explicit lab override, or ``None`` to resolve it from ``suite``.
    	suite (Mapping[str, Any] | None): Suite metadata used to resolve omitted settings.
    	judge_model (str | None): Dated judge model identity.
    	pack_identity (str | None): Judge pack identity.
    	sampling_identity (str | None): Sampling configuration identity.
    	output_contract_identity (str | None): Output contract identity.
    	environ (Mapping[str, str] | None): Environment values used to resolve the judge model.
    
    Returns:
    	LaneCEligibility: An immutable verdict containing eligibility, diagnostic status, reason codes, gate disposition, and secret-free evidence.
    """
    allows = resolve_allows_lane_c(allows_lane_c, suite)
    override = resolve_lab_override(lab_override, suite)
    pins_ok = judge_identity_pins_resolvable(
        judge_model=judge_model,
        pack_identity=pack_identity,
        sampling_identity=sampling_identity,
        output_contract_identity=output_contract_identity,
        environ=environ,
    )
    det = bool(deterministic_pass)
    gate_ok = det or override
    eligible = bool(allows and gate_ok and pins_ok)
    diagnostic_only = bool(eligible and override and not det)

    reasons: list[str] = []
    gate_disposition: str | None = None
    if eligible:
        if diagnostic_only:
            reason = GATE_LAB_OVERRIDE_DIAGNOSTIC
            reasons.append(GATE_LAB_OVERRIDE_DIAGNOSTIC)
            gate_disposition = GATE_LAB_OVERRIDE_DIAGNOSTIC
        else:
            reason = "eligible"
            reasons.append("eligible")
    elif not allows:
        reason = "lane_c_not_allowed_by_suite"
        reasons.extend(["lane_c_not_allowed_by_suite", EXEC_COHORT_INELIGIBLE])
        gate_disposition = GATE_SCOPE_GATE_REJECT
    elif not gate_ok:
        reason = "deterministic_pass_false_no_lab_override"
        reasons.extend(["deterministic_pass_false_no_lab_override", EXEC_COHORT_INELIGIBLE])
        gate_disposition = GATE_DET_FAIL_EXCLUDED
    else:
        # pins not resolvable
        reason = "judge_identity_pins_unresolvable"
        reasons.extend(["judge_identity_pins_unresolvable", EXEC_PIN_INVALID, EXEC_COHORT_INELIGIBLE])
        gate_disposition = GATE_SCOPE_GATE_REJECT

    evidence = {
        "allows_lane_c": allows,
        "deterministic_pass": det,
        "lab_override": override,
        "pins_resolvable": pins_ok,
        "eligible": eligible,
        "diagnostic_only": diagnostic_only,
        "gate_disposition": gate_disposition,
        **_pin_evidence(
            judge_model=judge_model,
            pack_identity=pack_identity,
            sampling_identity=sampling_identity,
            output_contract_identity=output_contract_identity,
            environ=environ,
        ),
    }

    return LaneCEligibility(
        allows_lane_c=allows,
        deterministic_pass=det,
        lab_override=override,
        pins_resolvable=pins_ok,
        eligible=eligible,
        diagnostic_only=diagnostic_only,
        reason=reason,
        reasons=tuple(reasons),
        gate_disposition=gate_disposition,
        evidence=evidence,
    )
