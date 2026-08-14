"""FIND-026 preconditions: empty/oversize input + anti-fan-out short-circuit."""

from __future__ import annotations

from dataclasses import dataclass

from git_cg.eval.scoring.context import ScoreContext


@dataclass(frozen=True, slots=True)
class PreconditionResult:
    """Outcome of FIND-026 precondition checks."""

    input_nonempty: bool
    input_size_ok: bool
    short_circuit: bool
    reason: str | None
    failure_ids: tuple[str, ...]


def evaluate_preconditions(ctx: ScoreContext) -> PreconditionResult:
    """Evaluate empty/missing and oversize guards (FIND-026).

    When input is empty/missing or oversize, remaining message-dependent
    evaluators must short-circuit — only A/H harness metrics run. Owner rows
    are emitted later from every score id (no h.eval_input* filter).
    """
    if not ctx.input_nonempty:
        return PreconditionResult(
            input_nonempty=False,
            input_size_ok=True,
            short_circuit=True,
            reason="scored_artifact_missing_or_empty",
            failure_ids=("FIND-026", "EVAL_INPUT_EMPTY"),
        )
    if not ctx.input_size_ok:
        return PreconditionResult(
            input_nonempty=True,
            input_size_ok=False,
            short_circuit=True,
            reason="scored_artifact_oversize",
            failure_ids=("FIND-026", "EVAL_INPUT_OVERSIZE"),
        )
    return PreconditionResult(
        input_nonempty=True,
        input_size_ok=True,
        short_circuit=False,
        reason=None,
        failure_ids=(),
    )
