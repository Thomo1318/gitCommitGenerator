"""Closed C' skip/failure taxonomy (D42 two-layer model).

Gate-disposition codes explain why a cohort did not enter ordinary execution.
Execution codes stamp skip/score rows. Every gate disposition maps to one or
more execution codes; unmapped or colliding codes fail validation.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Final

# ---------------------------------------------------------------------------
# Gate-disposition layer (why the cohort did not enter ordinary execution)
# ---------------------------------------------------------------------------

GATE_DET_FAIL_EXCLUDED: Final = "det_fail_excluded"
GATE_SCOPE_GATE_REJECT: Final = "scope_gate_reject"
GATE_PROMPT_PACK_MISSING: Final = "prompt_pack_missing"
GATE_JUDGE_UNAVAILABLE: Final = "judge_unavailable"
GATE_LAB_OVERRIDE_DIAGNOSTIC: Final = "lab_override_diagnostic"
GATE_BUDGET_CAP_REACHED: Final = "budget_cap_reached"

GATE_DISPOSITION_CODES: Final[frozenset[str]] = frozenset(
    {
        GATE_DET_FAIL_EXCLUDED,
        GATE_SCOPE_GATE_REJECT,
        GATE_PROMPT_PACK_MISSING,
        GATE_JUDGE_UNAVAILABLE,
        GATE_LAB_OVERRIDE_DIAGNOSTIC,
        GATE_BUDGET_CAP_REACHED,
    }
)

# ---------------------------------------------------------------------------
# Execution-layer codes (C-TAX minimum set + success marker)
# ---------------------------------------------------------------------------

EXEC_COHORT_INELIGIBLE: Final = "cohort_ineligible"
EXEC_UNAVAILABLE_CREDS: Final = "unavailable_creds"
EXEC_CLIENT_UNCONSTRUCTIBLE: Final = "client_unconstructible"
EXEC_PIN_INVALID: Final = "pin_invalid"
EXEC_PACK_UNRESOLVABLE: Final = "pack_unresolvable"
EXEC_PACK_DECODE_ERROR: Final = "pack_decode_error"
EXEC_EMPTY_INPUT: Final = "empty_input"
EXEC_OVERSIZE_INPUT: Final = "oversize_input"
EXEC_TIMEOUT: Final = "timeout"
EXEC_TRANSPORT_ERROR: Final = "transport_error"
EXEC_PARSE_ERROR: Final = "parse_error"
EXEC_LAB_OVERRIDE_DIAGNOSTIC: Final = "lab_override_diagnostic"
EXEC_SCORED: Final = "scored"
EXEC_UNKNOWN_METRIC: Final = "unknown_metric"
# Slice-1 honest non-run after eligibility+availability when later spine
# stages (pack/judge) are not yet invoked. Not a product failure.
EXEC_JUDGE_NOT_INVOKED: Final = "judge_not_invoked"

EXECUTION_CODES: Final[frozenset[str]] = frozenset(
    {
        EXEC_COHORT_INELIGIBLE,
        EXEC_UNAVAILABLE_CREDS,
        EXEC_CLIENT_UNCONSTRUCTIBLE,
        EXEC_PIN_INVALID,
        EXEC_PACK_UNRESOLVABLE,
        EXEC_PACK_DECODE_ERROR,
        EXEC_EMPTY_INPUT,
        EXEC_OVERSIZE_INPUT,
        EXEC_TIMEOUT,
        EXEC_TRANSPORT_ERROR,
        EXEC_PARSE_ERROR,
        EXEC_LAB_OVERRIDE_DIAGNOSTIC,
        EXEC_SCORED,
        EXEC_UNKNOWN_METRIC,
        EXEC_JUDGE_NOT_INVOKED,
    }
)

# Gate disposition → allowed execution codes (D42 / S5-D16).
GATE_TO_EXECUTION: Final[dict[str, frozenset[str]]] = {
    GATE_DET_FAIL_EXCLUDED: frozenset({EXEC_COHORT_INELIGIBLE}),
    GATE_SCOPE_GATE_REJECT: frozenset({EXEC_COHORT_INELIGIBLE}),
    GATE_PROMPT_PACK_MISSING: frozenset({EXEC_PACK_UNRESOLVABLE, EXEC_PACK_DECODE_ERROR}),
    GATE_JUDGE_UNAVAILABLE: frozenset(
        {
            EXEC_UNAVAILABLE_CREDS,
            EXEC_CLIENT_UNCONSTRUCTIBLE,
            EXEC_TIMEOUT,
            EXEC_TRANSPORT_ERROR,
        }
    ),
    GATE_LAB_OVERRIDE_DIAGNOSTIC: frozenset({EXEC_LAB_OVERRIDE_DIAGNOSTIC}),
    # Budget is gate-layer only — no execution row is emitted.
    GATE_BUDGET_CAP_REACHED: frozenset(),
}

# Stable failure_id stamps for ScoreResult rows (closed; not free-form).
FAILURE_COHORT_INELIGIBLE: Final = "CPRIME_COHORT_INELIGIBLE"
FAILURE_UNAVAILABLE_CREDS: Final = "CPRIME_UNAVAILABLE_CREDS"
FAILURE_CLIENT_UNCONSTRUCTIBLE: Final = "CPRIME_CLIENT_UNCONSTRUCTIBLE"
FAILURE_PIN_INVALID: Final = "CPRIME_PIN_INVALID"
FAILURE_PACK_UNRESOLVABLE: Final = "CPRIME_PACK_UNRESOLVABLE"
FAILURE_PACK_DECODE_ERROR: Final = "CPRIME_PACK_DECODE_ERROR"
FAILURE_EMPTY_INPUT: Final = "CPRIME_EMPTY_INPUT"
FAILURE_OVERSIZE_INPUT: Final = "CPRIME_OVERSIZE_INPUT"
FAILURE_TIMEOUT: Final = "CPRIME_TIMEOUT"
FAILURE_TRANSPORT_ERROR: Final = "CPRIME_TRANSPORT_ERROR"
FAILURE_PARSE_ERROR: Final = "CPRIME_PARSE_ERROR"
FAILURE_LAB_OVERRIDE_DIAGNOSTIC: Final = "CPRIME_LAB_OVERRIDE_DIAGNOSTIC"
FAILURE_JUDGE_NOT_INVOKED: Final = "CPRIME_JUDGE_NOT_INVOKED"
FAILURE_UNKNOWN_METRIC: Final = "CPRIME_UNKNOWN_METRIC"

EXEC_TO_FAILURE_ID: Final[dict[str, str]] = {
    EXEC_COHORT_INELIGIBLE: FAILURE_COHORT_INELIGIBLE,
    EXEC_UNAVAILABLE_CREDS: FAILURE_UNAVAILABLE_CREDS,
    EXEC_CLIENT_UNCONSTRUCTIBLE: FAILURE_CLIENT_UNCONSTRUCTIBLE,
    EXEC_PIN_INVALID: FAILURE_PIN_INVALID,
    EXEC_PACK_UNRESOLVABLE: FAILURE_PACK_UNRESOLVABLE,
    EXEC_PACK_DECODE_ERROR: FAILURE_PACK_DECODE_ERROR,
    EXEC_EMPTY_INPUT: FAILURE_EMPTY_INPUT,
    EXEC_OVERSIZE_INPUT: FAILURE_OVERSIZE_INPUT,
    EXEC_TIMEOUT: FAILURE_TIMEOUT,
    EXEC_TRANSPORT_ERROR: FAILURE_TRANSPORT_ERROR,
    EXEC_PARSE_ERROR: FAILURE_PARSE_ERROR,
    EXEC_LAB_OVERRIDE_DIAGNOSTIC: FAILURE_LAB_OVERRIDE_DIAGNOSTIC,
    EXEC_JUDGE_NOT_INVOKED: FAILURE_JUDGE_NOT_INVOKED,
    EXEC_UNKNOWN_METRIC: FAILURE_UNKNOWN_METRIC,
}


class TaxonomyError(ValueError):
    """Raised when a taxonomy code is unknown or cross-layer mapping collides."""


def assert_execution_code(code: str) -> str:
    """Fail closed when ``code`` is outside the execution closed set."""
    if code not in EXECUTION_CODES:
        raise TaxonomyError(f"unknown C' execution code: {code!r}")
    return code


def assert_gate_disposition(code: str) -> str:
    """Fail closed when ``code`` is outside the gate-disposition closed set."""
    if code not in GATE_DISPOSITION_CODES:
        raise TaxonomyError(f"unknown C' gate-disposition code: {code!r}")
    return code


def map_gate_to_execution(gate_code: str, execution_code: str) -> None:
    """Validate gate-disposition ↔ execution mapping (S5-D16).

    ``budget_cap_reached`` is gate-only (empty execution set). Passing any
    execution code with it is a cross-layer collision.
    """
    g = assert_gate_disposition(gate_code)
    e = assert_execution_code(execution_code)
    allowed = GATE_TO_EXECUTION[g]
    if not allowed:
        raise TaxonomyError(f"gate disposition {g!r} is gate-layer only; execution code {e!r} collides")
    if e not in allowed:
        raise TaxonomyError(
            f"execution code {e!r} is not mapped from gate disposition {g!r}; allowed={sorted(allowed)}"
        )


def failure_id_for(execution_code: str) -> str | None:
    """Return the stable failure_id for a skip execution code (None for scored)."""
    code = assert_execution_code(execution_code)
    if code == EXEC_SCORED:
        return None
    return EXEC_TO_FAILURE_ID[code]


@dataclass(frozen=True, slots=True)
class TaxonomyPair:
    """Paired gate-disposition + execution classification for one skip path."""

    gate_disposition: str | None
    execution_code: str

    def validate(self) -> TaxonomyPair:
        assert_execution_code(self.execution_code)
        if self.gate_disposition is not None:
            map_gate_to_execution(self.gate_disposition, self.execution_code)
        return self


def validate_closed_reason(reason: str, *, allow_scored: bool = True) -> str:
    """Ensure a ScoreResult.reason is a closed execution code (D42)."""
    if reason == EXEC_SCORED and not allow_scored:
        raise TaxonomyError("reason=scored is not valid on this path")
    return assert_execution_code(reason)


def iter_gate_disposition_codes() -> Iterable[str]:
    return sorted(GATE_DISPOSITION_CODES)


def iter_execution_codes() -> Iterable[str]:
    return sorted(EXECUTION_CODES)


def mapping_table() -> Mapping[str, tuple[str, ...]]:
    """Stable mapping snapshot for tests/docs."""
    return {g: tuple(sorted(v)) for g, v in sorted(GATE_TO_EXECUTION.items())}
