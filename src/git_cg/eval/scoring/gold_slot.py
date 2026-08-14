"""Runner-owned gold slot (D40 / T14a) — one GoldReport per evaluable case."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from git_cg.commit_gold import GoldReport
from git_cg.eval.scoring.context import ScoreContext
from git_cg.eval.scoring.product_bridges import (
    parse_message_to_plan,
    run_gold_once,
    signals_from_context,
)
from git_cg.intent import DiffSignals
from git_cg.models import CommitPlan


@dataclass(slots=True)
class GoldSlot:
    """Shared gold evaluation state owned by the runner.

    Fields map 1:1 to the live ``run_gold_once`` 3-tuple plus call identity and
    error (D40-D42). Families D/C/F consume this object; they must not call gold
    when the slot is supplied.
    """

    report: GoldReport | None = None
    strict_hits: frozenset[str] = field(default_factory=frozenset)
    ok: bool = False
    call_identity: str | None = None
    error: str | None = None
    call_count: int = 0
    plan: CommitPlan | None = None
    signals: DiffSignals | None = None
    contract_provided: bool = False
    ranked_intents_provided: bool = False
    skipped: bool = False
    skip_reason: str | None = None

    @property
    def shared_evidence(self) -> dict[str, Any]:
        """Evidence fragment proving shared ownership (D41)."""
        return {
            "call_identity": self.call_identity,
            "error": self.error,
            "report_is": id(self.report) if self.report is not None else None,
            "shared": True,
            "call_count": self.call_count,
            "contract_provided": self.contract_provided,
            "ranked_intents_provided": self.ranked_intents_provided,
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
        }


def build_gold_slot(
    ctx: ScoreContext,
    *,
    gold_mode: str = "strict",
    gold_bridge: Any | None = None,
    plan: CommitPlan | None = None,
    signals: DiffSignals | None = None,
    contract: Any | None = None,
    ranked_intents: list | None = None,
    short_circuit: bool = False,
) -> GoldSlot:
    """Build the runner-owned gold slot.

    On FIND-026 short-circuit: zero gold calls, ``skipped=True``.
    On evaluable messages: exactly one ``run_gold_once`` (or injected bridge).
    Constructor/parse/bridge exceptions set ``error`` and leave ``report is None``
    with no retry (D41).
    """
    slot = GoldSlot()
    if short_circuit:
        slot.skipped = True
        slot.skip_reason = "find026_short_circuit"
        return slot

    msg = (ctx.final_message or "").strip()
    if not msg:
        # Product-card-only targets are not gold-message evaluable.
        slot.skipped = True
        slot.skip_reason = "no_final_message_for_gold"
        return slot

    slot.call_identity = uuid4().hex
    slot.contract_provided = contract is not None
    slot.ranked_intents_provided = ranked_intents is not None

    try:
        built_plan = plan or parse_message_to_plan(msg)
        # Gold path-class scaffolding may use placeholders; C/F path-security
        # never reads these as staged evidence (T13).
        path_files = list(ctx.path_evidence)
        built_signals = signals or signals_from_context(
            path_class_gate=ctx.path_class_gate,
            generation_task_input=ctx.generation_task_input,
            files=path_files or None,
            allow_placeholder_paths=not bool(path_files),
        )
        slot.plan = built_plan
        slot.signals = built_signals

        bridge = gold_bridge
        if bridge is not None:
            report, strict_hits, ok = bridge(built_plan, built_signals, gold_mode)
        else:
            report, strict_hits, ok = run_gold_once(
                built_plan,
                built_signals,
                gold_mode=gold_mode,
                contract=contract,
                ranked_intents=ranked_intents,
            )
        slot.call_count = 1
        slot.report = report
        slot.strict_hits = frozenset(strict_hits)
        slot.ok = bool(ok)
    except Exception as exc:
        slot.error = f"{type(exc).__name__}: {exc}"
        slot.report = None
        slot.strict_hits = frozenset()
        slot.ok = False
        # call_count stays 0 if bridge never returned; if bridge raised after
        # entry we still count the attempt as one failed call.
        if slot.call_count == 0:
            slot.call_count = 1

    return slot
