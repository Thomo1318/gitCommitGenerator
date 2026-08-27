"""ScoreResult_v1 model — offline envelope only (no scoring runtime)."""

from __future__ import annotations

from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    field_validator,
    model_validator,
)

from git_cg.eval.enums import Authority, Family, Polarity, Severity, Source

_Numeric = StrictInt | StrictFloat


class ScoreResultV1(BaseModel):
    """Canonical score envelope.

    Required: metric_id, polarity, authority, source, value.
    Boolean ``value`` is only valid for ``polarity=pass_fail``.
    ``pass_fail`` requires a real boolean (not 0/1 int/float).
    Non-boolean scores accept JSON numbers as int or float (StrictInt|StrictFloat).
    Advisory/lab/train scores never imply ``gate.deterministic_pass`` alone (M11).
    """

    model_config = ConfigDict(extra="forbid")

    metric_id: str = Field(min_length=1)
    polarity: Polarity
    authority: Authority
    source: Source
    # Strict union: bool must not coerce to float (and vice-versa).
    # Int-valued count metrics (e.g. d.strict_fail_set) remain valid JSON numbers.
    value: StrictBool | _Numeric
    name: str | None = None
    family: Family | None = None
    threshold: _Numeric | None = None
    passed: StrictBool | None = None
    severity: Severity | None = None
    reason: str | None = None
    evidence: dict[str, Any] | None = None
    evidence_paths: list[str] | None = None
    failure_ids: list[str] | None = None
    product_authority: str | None = None
    pin_refs: list[str] | None = None
    duration_ms: _Numeric | None = Field(default=None, ge=0)

    @field_validator("metric_id")
    @classmethod
    def _metric_id_non_empty(cls, v: str) -> str:
        """Pydantic guard: metric_id must be a non-empty string."""
        if not v.strip():
            raise ValueError("metric_id must be non-empty")
        return v

    @model_validator(mode="after")
    def _value_matches_polarity(self) -> ScoreResultV1:
        """Pydantic guard: value domain matches the metric polarity contract."""
        is_bool = type(self.value) is bool
        if self.polarity is Polarity.PASS_FAIL:
            if not is_bool:
                raise ValueError(
                    "value must be a boolean when polarity=pass_fail (ints/floats are rejected; use true/false)"
                )
        elif is_bool:
            raise ValueError("boolean value is only valid when polarity=pass_fail")
        return self


# Helpful alias for docs / type checkers reading the plan name.
ScoreResult_v1 = ScoreResultV1
