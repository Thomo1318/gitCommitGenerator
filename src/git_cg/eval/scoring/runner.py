"""S2 offline Plane A scoring runner over ``ape_bundle_v1`` fixtures."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from git_cg.eval.corpus.encoder import encode_fixture
from git_cg.eval.corpus.fixtures import default_fixture_root, load_suite_fixtures
from git_cg.eval.corpus.snapshots import build_snapshot
from git_cg.eval.corpus.suites import load_suite
from git_cg.eval.score_result import ScoreResultV1
from git_cg.eval.scoring.context import ScoreContext, ScoreContextError, project_score_context
from git_cg.eval.scoring.family_a import score_family_a
from git_cg.eval.scoring.family_b import score_family_b
from git_cg.eval.scoring.family_c import score_family_c
from git_cg.eval.scoring.family_d import GoldBridge, score_family_d
from git_cg.eval.scoring.family_e import score_family_e
from git_cg.eval.scoring.family_f import score_family_f
from git_cg.eval.scoring.family_g import score_family_g
from git_cg.eval.scoring.family_h import score_family_h
from git_cg.eval.scoring.family_i import (
    FAMILY_I_METRIC_IDS,
    build_session_thread_index,
    score_family_i,
    synthesize_family_i_fail_closed,
)
from git_cg.eval.scoring.gates import S2A_REQUIRE_BLOCK, compose_gates
from git_cg.eval.scoring.gold_slot import build_gold_slot
from git_cg.eval.scoring.preconditions import evaluate_preconditions
from git_cg.eval.scoring.result_builder import make_score

__all__ = [
    "ScoreCaseResult",
    "ScoreSuiteResult",
    "resolve_require_topology",
    "resolve_require_trajectory",
    "score_bundle",
    "score_case",
    "score_suite",
]


def resolve_require_topology(
    require_topology: bool | None,
    suite: Mapping[str, Any] | None,
) -> bool:
    """Resolve topology-require policy (N19).

    Order: explicit API argument → ``suite.meta.require_topology`` (bool only) →
    ``False``. Never inferred from ``bound``.
    """
    if require_topology is not None:
        return bool(require_topology)
    if isinstance(suite, Mapping):
        meta = suite.get("meta")
        if isinstance(meta, Mapping):
            flag = meta.get("require_topology")
            if isinstance(flag, bool):
                return flag
    return False


def resolve_require_trajectory(
    require_trajectory: bool | None,
    suite: Mapping[str, Any] | None,
) -> bool:
    """
    Resolve whether trajectory requirements apply to scoring.
    
    Parameters:
    	require_trajectory (bool | None): Explicit trajectory requirement, taking precedence when provided.
    	suite (Mapping[str, Any] | None): Suite metadata that may define ``meta.require_trajectory``.
    
    Returns:
    	bool: The explicit policy, the boolean value from suite metadata, or ``False`` when neither is provided.
    """
    if require_trajectory is not None:
        return bool(require_trajectory)
    if isinstance(suite, Mapping):
        meta = suite.get("meta")
        if isinstance(meta, Mapping):
            flag = meta.get("require_trajectory")
            if isinstance(flag, bool):
                return flag
    return False


def _recovery_context(
    bundle: Any,
    suite: dict[str, Any] | None,
    case_id: str | None,
    exc: BaseException,
) -> ScoreContext:
    """
    Create a fail-closed scoring context when context projection fails.
    
    Parameters:
        bundle: The bundle from which to recover the case identifier and content.
        suite: Optional suite metadata to include in the recovered context.
        case_id: Optional explicit case identifier.
        exc: The exception raised during context projection.
    
    Returns:
        A minimal scoring context containing the projection error and missing-value defaults.
    """
    bid = case_id or (bundle.get("case_id") if isinstance(bundle, dict) else None) or "unknown"
    return ScoreContext(
        case_id=str(bid),
        bundle=dict(bundle) if isinstance(bundle, dict) else {},
        suite=dict(suite) if isinstance(suite, dict) else None,
        final_message=None,
        final_message_sha256=None,
        artifact_class="unknown",
        bound=False,
        unbound_reason="context_projection_failed",
        schema_pack=None,
        metric_catalog=None,
        expected_final_message=None,
        expected_gold_codes=(),
        failure_ids=(),
        path_class_gate=None,
        generation_task_input=None,
        product_card={},
        scored_target="missing",
        warnings=(f"context_error:{exc}",),
        score_card={},
        files=(),
    )


def _run_family_i(
    ctx: ScoreContext,
    *,
    require_topology: bool,
    session_thread_index: Mapping[str, tuple[str, ...]] | None,
    errors: list[str],
) -> list[ScoreResultV1]:
    """Always emit 16 Family I rows; recover fail-closed on evaluator errors (N18).

    Covers whole-evaluator exceptions, missing metric ids, invalid envelopes,
    and ``value != passed`` mismatches.
    """
    try:
        rows = score_family_i(
            ctx,
            require_topology=require_topology,
            session_thread_index=session_thread_index,
        )
    except Exception as exc:
        errors.append(f"family_i:{type(exc).__name__}: {exc}")
        return synthesize_family_i_fail_closed(
            reason="family_i_evaluator_error",
            errors=[f"{type(exc).__name__}: {exc}"],
        )

    # Envelope-validate I rows and replace invalid / missing ones (N18).
    by_id: dict[str, ScoreResultV1] = {}
    for row in rows:
        mid = row.metric_id
        try:
            payload = row.model_dump(mode="json")
            valid = ScoreResultV1.model_validate(payload)
            if valid.passed is not None and bool(valid.value) != bool(valid.passed):
                raise ValueError("value_passed_mismatch")
            by_id[mid] = valid
        except Exception as exc:
            errors.append(f"family_i_envelope:{mid}:{type(exc).__name__}")
            recovered = synthesize_family_i_fail_closed(
                reason="family_i_envelope_invalid",
                errors=[f"{mid}:{type(exc).__name__}"],
            )
            # Use the matching recovered row for this metric only.
            for r in recovered:
                if r.metric_id == mid:
                    by_id[mid] = r
                    break

    out: list[ScoreResultV1] = []
    for mid in FAMILY_I_METRIC_IDS:
        row = by_id.get(mid)
        if row is None:
            errors.append(f"family_i_missing:{mid}")
            out.extend(
                r
                for r in synthesize_family_i_fail_closed(reason="family_i_row_missing_recovered")
                if r.metric_id == mid
            )
        else:
            out.append(row)
    return out


@dataclass(slots=True)
class ScoreCaseResult:
    """Per-case scoring outcome."""

    case_id: str
    scores: list[ScoreResultV1] = field(default_factory=list)
    gates: list[ScoreResultV1] = field(default_factory=list)
    context: ScoreContext | None = None
    short_circuit: bool = False
    evaluator_errors: list[str] = field(default_factory=list)
    suite_snapshot_pin: str | None = None
    gold_call_count: int = 0
    gold_call_identity: str | None = None
    require_topology: bool = False

    @property
    def all_results(self) -> list[ScoreResultV1]:
        """Family scores followed by composed gate rows."""
        return [*self.scores, *self.gates]

    @property
    def deterministic_pass(self) -> bool | None:
        """``gate.deterministic_pass`` value, or ``None`` if the gate row is missing."""
        for g in self.gates:
            if g.metric_id == "gate.deterministic_pass":
                return g.passed
        return None

    def by_id(self) -> dict[str, ScoreResultV1]:
        """Index ``all_results`` by ``metric_id``.

        Duplicate metric IDs are rejected (fail closed) — last-write-wins is banned.
        """
        out: dict[str, ScoreResultV1] = {}
        dups: list[str] = []
        for s in self.all_results:
            if s.metric_id in out:
                dups.append(s.metric_id)
            out[s.metric_id] = s
        if dups:
            raise ValueError(f"duplicate metric_id in case results: {sorted(set(dups))}")
        return out


@dataclass(slots=True)
class ScoreSuiteResult:
    """Suite-level aggregation of case scores."""

    suite_id: str
    cases: list[ScoreCaseResult] = field(default_factory=list)
    suite_snapshot_pin: str | None = None
    require_block: tuple[str, ...] = S2A_REQUIRE_BLOCK
    snapshot: dict[str, Any] | None = None
    require_topology: bool = False
    session_thread_index: dict[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def all_pass(self) -> bool:
        """True only if there is at least one case and every case passes (fail-closed)."""
        if not self.cases:
            return False
        return all(c.deterministic_pass is True for c in self.cases)


def score_bundle(
    bundle: dict[str, Any],
    *,
    suite: dict[str, Any] | None = None,
    suite_snapshot_pin: str | None = None,
    require_block: tuple[str, ...] | None = None,
    require_topology: bool | None = None,
    require_trajectory: bool | None = None,
    session_thread_index: Mapping[str, tuple[str, ...]] | None = None,
    gold_mode: str = "strict",
    gold_bridge: GoldBridge | None = None,
    offline: bool = True,
    max_eval_bytes: int | None = None,
    case_id: str | None = None,
) -> ScoreCaseResult:
    """Score one encoded ``ape_bundle_v1`` mapping offline.
    
    Evaluates the applicable scoring families, composes deterministic gates, and
    fails closed when context projection, family evaluation, result validation, or
    gate composition encounters an error. Message-dependent families are skipped
    when preconditions require short-circuiting; gold evaluation is otherwise
    limited to one shared call.
    
    Parameters:
        bundle (dict[str, Any]): Encoded bundle to score.
        require_block (tuple[str, ...] | None): Required metric block for gate composition.
        require_topology (bool | None): Whether topology compliance is required.
        require_trajectory (bool | None): Whether trajectory compliance is required.
    
    Returns:
        ScoreCaseResult: Per-case scores, gates, context, execution metadata, and
        evaluator errors.
    """
    errors: list[str] = []
    scores: list[ScoreResultV1] = []
    gold_call_count = 0
    gold_call_identity: str | None = None
    topo_required = resolve_require_topology(require_topology, suite)
    traj_required = resolve_require_trajectory(require_trajectory, suite)

    try:
        kwargs: dict[str, Any] = {"suite": suite, "case_id": case_id}
        if max_eval_bytes is not None:
            kwargs["max_eval_bytes"] = max_eval_bytes
        ctx = project_score_context(bundle, **kwargs)
    except ScoreContextError as exc:
        errors.append(f"context:{exc}")
        ctx = _recovery_context(bundle, suite, case_id, exc)
    except Exception as exc:
        errors.append(f"context:{type(exc).__name__}: {exc}")
        ctx = _recovery_context(bundle, suite, case_id, exc)

    pre = evaluate_preconditions(ctx)
    req = require_block if require_block is not None else S2A_REQUIRE_BLOCK

    if pre.short_circuit:
        # FIND-026: skip message-dependent families (B/C/D/E/F/G); still run A + I + H + gates.
        # Zero gold calls on short-circuit.
        try:
            scores.extend(score_family_a(ctx))
        except Exception as exc:
            errors.append(f"family_a:{type(exc).__name__}: {exc}")
        scores.extend(
            _run_family_i(
                ctx,
                require_topology=topo_required,
                session_thread_index=session_thread_index,
                errors=errors,
            )
        )
        try:
            scores.extend(
                score_family_h(
                    ctx,
                    pre=pre,
                    family_scores=list(scores),
                    suite_snapshot_pin=suite_snapshot_pin,
                    offline=offline,
                    evaluator_errors=errors,
                    require_trajectory=traj_required,
                )
            )
        except Exception as exc:
            errors.append(f"family_h:{type(exc).__name__}: {exc}")
    else:
        # Runner-owned gold slot: exactly one gold call for evaluable messages.
        slot = build_gold_slot(ctx, gold_mode=gold_mode, gold_bridge=gold_bridge, short_circuit=False)
        gold_call_count = slot.call_count
        gold_call_identity = slot.call_identity

        family_runners: list[tuple[str, Any]] = [
            ("family_a", lambda: score_family_a(ctx)),
            ("family_b", lambda: score_family_b(ctx)),
            (
                "family_c",
                lambda: score_family_c(ctx, gold_slot=slot, plan=slot.plan, signals=slot.signals),
            ),
            (
                "family_d",
                lambda: score_family_d(
                    ctx,
                    gold_mode=gold_mode,
                    gold_bridge=None,  # must not call gold when slot supplied
                    gold_slot=slot,
                    plan=slot.plan,
                    signals=slot.signals,
                ),
            ),
            (
                "family_e",
                lambda: score_family_e(ctx, gold_slot=slot, plan=slot.plan, signals=slot.signals),
            ),
            ("family_f", lambda: score_family_f(ctx, gold_slot=slot, plan=slot.plan)),
            ("family_g", lambda: score_family_g(ctx, gold_slot=slot, plan=slot.plan)),
        ]
        for name, fn in family_runners:
            try:
                scores.extend(fn())
            except Exception as exc:
                errors.append(f"{name}:{type(exc).__name__}: {exc}")
        # Family I always runs after A-G and before H (N6/N8).
        scores.extend(
            _run_family_i(
                ctx,
                require_topology=topo_required,
                session_thread_index=session_thread_index,
                errors=errors,
            )
        )
        try:
            scores.extend(
                score_family_h(
                    ctx,
                    pre=pre,
                    family_scores=list(scores),
                    suite_snapshot_pin=suite_snapshot_pin,
                    offline=offline,
                    evaluator_errors=errors,
                    require_trajectory=traj_required,
                )
            )
        except Exception as exc:
            errors.append(f"family_h:{type(exc).__name__}: {exc}")

    # Ensure core H input metric exists even if H blew up
    if not any(s.metric_id == "h.eval_input_nonempty" for s in scores):
        try:
            scores.append(
                make_score(
                    "h.eval_input_nonempty",
                    pre.input_nonempty,
                    reason=pre.reason,
                    failure_ids=list(pre.failure_ids) if not pre.input_nonempty else None,
                )
            )
        except Exception as exc:
            errors.append(f"h_fallback:{exc}")

    # Envelope validate / drop invalid non-I rows; I rows already recovered above.
    valid_scores: list[ScoreResultV1] = []
    env_bad = 0
    i_ids = set(FAMILY_I_METRIC_IDS)
    for s in scores:
        if s.metric_id in i_ids:
            # Already envelope-validated / recovered.
            valid_scores.append(s)
            continue
        try:
            payload = s.model_dump(mode="json")
            valid_scores.append(ScoreResultV1.model_validate(payload))
        except Exception:
            env_bad += 1
    scores = valid_scores
    if env_bad:
        errors.append(f"envelope:{env_bad}_invalid")

    if errors:
        rewritten: list[ScoreResultV1] = []
        for s in scores:
            if s.metric_id == "h.evaluator_error_free" and s.passed is not False:
                rewritten.append(
                    make_score(
                        "h.evaluator_error_free",
                        False,
                        reason="evaluator_exceptions",
                        evidence={"errors": errors[:10], "count": len(errors)},
                        failure_ids=["EVAL_EVALUATOR_ERROR"],
                    )
                )
            else:
                rewritten.append(s)
        scores = rewritten

    try:
        gates = compose_gates(
            scores,
            require_block=req,
            bound=ctx.bound,
            require_topology=topo_required,
            gold_mode=gold_mode,
        )
    except Exception as exc:
        errors.append(f"gates:{type(exc).__name__}: {exc}")
        gates = []

    return ScoreCaseResult(
        case_id=ctx.case_id,
        scores=scores,
        gates=gates,
        context=ctx,
        short_circuit=pre.short_circuit,
        evaluator_errors=errors,
        suite_snapshot_pin=suite_snapshot_pin,
        gold_call_count=gold_call_count,
        gold_call_identity=gold_call_identity,
        require_topology=topo_required,
    )


def score_case(
    case_path: str | Path,
    *,
    suite: dict[str, Any] | None = None,
    suite_snapshot_pin: str | None = None,
    require_block: tuple[str, ...] | None = None,
    require_topology: bool | None = None,
    session_thread_index: Mapping[str, tuple[str, ...]] | None = None,
    gold_mode: str = "strict",
    gold_bridge: GoldBridge | None = None,
    offline: bool = True,
    case_id: str | None = None,
    suite_id: str | None = None,
) -> ScoreCaseResult:
    """Load fixture JSON, encode via S1, then ``score_bundle`` offline."""
    path = Path(case_path)
    fixture = json.loads(path.read_text(encoding="utf-8"))
    cid = case_id or fixture.get("case_id") or path.stem
    sid = suite_id
    if sid is None and isinstance(suite, Mapping):
        sid = suite.get("suite_id") if isinstance(suite.get("suite_id"), str) else None
    encoded = encode_fixture(fixture, case_id=str(cid), suite_id=sid, validate=True)
    bundle = encoded["bundle"]
    return score_bundle(
        bundle,
        suite=suite,
        suite_snapshot_pin=suite_snapshot_pin,
        require_block=require_block,
        require_topology=require_topology,
        session_thread_index=session_thread_index,
        gold_mode=gold_mode,
        gold_bridge=gold_bridge,
        offline=offline,
        case_id=str(cid),
    )


def score_suite(
    suite_id: str = "cm-eval-fixtures-core",
    *,
    fixture_root: str | Path | None = None,
    require_block: tuple[str, ...] | None = None,
    require_topology: bool | None = None,
    gold_mode: str = "strict",
    gold_bridge: GoldBridge | None = None,
    offline: bool = True,
    suite_path: str | Path | None = None,
) -> ScoreSuiteResult:
    """Score every case in a committed suite under the canonical S1 snapshot pin.

    Always content-addresses the suite via ``build_snapshot(suite_id)``. When
    ``suite_path`` loads an alternate document with the same ``suite_id``, case
    membership must match the pinned suite or scoring fails closed.

    Two-pass flow (N14): encode all cases, build a read-only session-thread
    index, then score each case with that index.
    """
    root = Path(fixture_root) if fixture_root else default_fixture_root()

    # Optional path form for tests
    if suite_path is not None:
        path = Path(suite_path)
        suite_doc = json.loads(path.read_text(encoding="utf-8"))
        sid = str(suite_doc.get("suite_id") or suite_id)
        # Preserve meta for N19 when loading from an alternate suite_path.
        if "meta" not in suite_doc or not isinstance(suite_doc.get("meta"), dict):
            suite_doc["meta"] = {}
    else:
        suite_doc = load_suite(suite_id, fixture_root=root)
        sid = str(suite_doc.get("suite_id") or suite_id)

    # Require-block resolution (legacy suite metrics.require_block still honored).
    metrics = suite_doc.get("metrics") or {}
    if require_block is not None:
        req = tuple(require_block)
    elif isinstance(metrics, dict) and metrics.get("require_block"):
        req = tuple(metrics["require_block"])
    else:
        req = S2A_REQUIRE_BLOCK

    topo_required = resolve_require_topology(require_topology, suite_doc)

    # Snapshot pin (content-addressed) always binds the *canonical* committed suite.
    # suite_path is a test override only — reject it when case membership diverges
    # so the pin cannot claim one corpus while we score another.
    snapshot = build_snapshot(sid, fixture_root=root, validate=True)
    suite_pin = str(snapshot.get("snapshot_hash") or snapshot.get("id") or "")
    raw_pinned_suite = snapshot.get("suite")
    pinned_suite: dict[str, Any] = raw_pinned_suite if isinstance(raw_pinned_suite, dict) else {}
    pinned_case_ids = list(pinned_suite.get("case_ids") or [])
    scored_case_ids = list(suite_doc.get("case_ids") or [])
    if suite_path is not None and scored_case_ids != pinned_case_ids:
        raise ValueError(
            "suite_path case_ids diverge from canonical suite "
            f"{sid!r}: scored={scored_case_ids!r} pinned={pinned_case_ids!r}"
        )

    pairs = load_suite_fixtures(suite_doc, fixture_root=root)

    # Pass 1: encode every case and build the N14 thread index.
    encoded_pairs: list[tuple[str, dict[str, Any]]] = []
    for cid, fixture in pairs:
        encoded = encode_fixture(fixture, case_id=cid, suite_id=sid, validate=True)
        encoded_pairs.append((cid, encoded["bundle"]))
    thread_index = build_session_thread_index(encoded_pairs)

    # Pass 2: score with the read-only index.
    cases_out: list[ScoreCaseResult] = []
    for cid, bundle in encoded_pairs:
        cases_out.append(
            score_bundle(
                bundle,
                suite=suite_doc,
                suite_snapshot_pin=suite_pin,
                require_block=req,
                require_topology=topo_required,
                session_thread_index=thread_index,
                gold_mode=gold_mode,
                gold_bridge=gold_bridge,
                offline=offline,
                case_id=cid,
            )
        )

    return ScoreSuiteResult(
        suite_id=sid,
        cases=cases_out,
        suite_snapshot_pin=suite_pin,
        require_block=req,
        snapshot=snapshot,
        require_topology=topo_required,
        session_thread_index=dict(thread_index),
    )
