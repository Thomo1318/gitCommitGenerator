"""Lane C-prime entry eligibility — ``gate.semantic_cohort_eligible`` enforcement.

Plan §6.11::

    gate.semantic_cohort_eligible =
        suite.allows_lane_c
        AND (gate.deterministic_pass OR suite.lab_override)
        AND pins_resolvable(judge)

This module is **offline and side-effect free**. It never calls the network,
never imports the Opik SDK, and never raises on missing credentials — a judge
that cannot be resolved simply makes the cohort ineligible (fail-closed), which
keeps Lane A/B green without judge credentials (F4 / AC: missing credentials →
skip/lab-fail class, Lane A still pass).

Suite flags follow the N19 resolution order used by ``require_topology`` /
``require_trajectory``: explicit API argument → ``suite.meta.<flag>`` (bool
only) → ``False``. Neither flag is ever inferred from ``bound``.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

# Pinned-judge configuration surface. A Lane C-prime judge is resolvable only when
# BOTH a pinned model id AND a credential are present. Floating "latest" judges
# are forbidden on every path (F5); an absent pin therefore fails closed.
ENV_JUDGE_MODEL = "GIT_CG_EVAL_JUDGE_MODEL"
ENV_JUDGE_API_KEY = "GIT_CG_EVAL_JUDGE_API_KEY"


def resolve_allows_lane_c(
    allows_lane_c: bool | None,
    suite: Mapping[str, Any] | None,
) -> bool:
    """Resolve the suite Lane C-prime opt-in (N19).

    Order: explicit API argument → ``suite.meta.allows_lane_c`` (bool only) →
    ``False``. Lane C-prime is never on by default; a suite must opt in explicitly.
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
    """Resolve the explicit lab-override escape hatch (N19).

    Order: explicit API argument → ``suite.meta.lab_override`` (bool only) →
    ``False``. When True, the cohort may run even if ``gate.deterministic_pass``
    is False — but only for explicitly labeled lab suites, never as a product
    gate. Never inferred from ``bound`` or from ``allows_lane_c``.
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


def judge_pins_resolvable(
    *,
    judge_model: str | None = None,
    judge_api_key: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Fail-closed probe: is a pinned judge resolvable without network I/O?

    A judge is resolvable only when a **pinned model id** AND a **credential**
    are both present. This is a pure presence check — it performs no network
    call, no SDK import, and no secret logging. Any missing piece returns
    ``False`` so the cohort degrades to skip/lab-fail rather than raising.

    Parameters default to the process environment; callers may inject explicit
    values (tests, dogfood profiles) without touching ``os.environ``.
    """
    env = environ if environ is not None else os.environ
    model = judge_model if judge_model is not None else env.get(ENV_JUDGE_MODEL, "")
    key = judge_api_key if judge_api_key is not None else env.get(ENV_JUDGE_API_KEY, "")
    # A bare "latest" / empty model is an unpinned float → reject (F5).
    if not model or not model.strip() or model.strip().lower() == "latest":
        return False
    return bool(key and key.strip())


@dataclass(frozen=True)
class LaneCEligibility:
    """Structured verdict for ``gate.semantic_cohort_eligible``.

    ``eligible`` is the AND of the three plan §6.11 clauses. The component
    booleans and ``reason`` are carried so the gate row can emit honest
    evidence and so the Lane C-prime runner can classify a skip without recomputing.
    """

    allows_lane_c: bool
    deterministic_pass: bool
    lab_override: bool
    judge_pins_resolvable: bool
    eligible: bool
    reason: str
    evidence: dict[str, Any] = field(default_factory=dict)


def evaluate_semantic_cohort_eligibility(
    *,
    deterministic_pass: bool,
    allows_lane_c: bool | None = None,
    lab_override: bool | None = None,
    suite: Mapping[str, Any] | None = None,
    judge_model: str | None = None,
    judge_api_key: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> LaneCEligibility:
    """Evaluate the plan §6.11 ``gate.semantic_cohort_eligible`` formula.

    ``deterministic_pass`` is the already-composed ``gate.deterministic_pass``
    value for the cohort (Lane A/B result). The remaining clauses are resolved
    here from the suite and the judge-pin probe.

    Never raises on missing credentials; the result is fail-closed. The
    ``reason`` is stable machine-readable text for gate-row evidence.
    """
    allows = resolve_allows_lane_c(allows_lane_c, suite)
    override = resolve_lab_override(lab_override, suite)
    pins_ok = judge_pins_resolvable(
        judge_model=judge_model,
        judge_api_key=judge_api_key,
        environ=environ,
    )

    gate_ok = bool(deterministic_pass) or override
    eligible = allows and gate_ok and pins_ok

    if eligible:
        reason = "eligible"
    elif not allows:
        reason = "lane_c_not_allowed_by_suite"
    elif not gate_ok:
        reason = "deterministic_pass_false_no_lab_override"
    else:  # not pins_ok
        reason = "judge_pins_unresolvable"

    return LaneCEligibility(
        allows_lane_c=allows,
        deterministic_pass=bool(deterministic_pass),
        lab_override=override,
        judge_pins_resolvable=pins_ok,
        eligible=eligible,
        reason=reason,
        evidence={
            "allows_lane_c": allows,
            "deterministic_pass": bool(deterministic_pass),
            "lab_override": override,
            "judge_pins_resolvable": pins_ok,
            "judge_model_pinned": bool(
                (judge_model if judge_model is not None else (environ or os.environ).get(ENV_JUDGE_MODEL, "")).strip()
            ),
        },
    )
