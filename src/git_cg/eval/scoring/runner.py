"""S2 offline Plane A scoring runner over ``ape_bundle_v1`` fixtures."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
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
from git_cg.eval.scoring.family_h import score_family_h, score_family_h_cprime
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
    """Resolve trajectory-require policy (R7/N19.6).

    Order: explicit API argument → ``suite.meta.require_trajectory`` (bool only)
    → ``False``. Never inferred from ``bound`` or from topology policy - Family
    H owns trajectory; Family I owns topology. The two planes stay separate.
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
    """Minimal ``ScoreContext`` when projection fails (H still emits FIND-026)."""
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

        Duplicate metric IDs are rejected (fail closed) - last-write-wins is banned.
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
    enable_lane_c: bool = False,
    lane_c_metric_ids: Sequence[str] | None = None,
    judge_fn: Any | None = None,
    judge_input: Any | None = None,
    final_accept_evidence: Any | None = None,
    judge_model: str | None = None,
    judge_api_key: str | None = None,
    lane_c_environ: Mapping[str, str] | None = None,
    lane_c_lab_override: bool | None = None,
    lane_c_allows: bool | None = None,
    max_input_chars: int | None = None,
) -> ScoreCaseResult:
    """Score one already-encoded ``ape_bundle_v1`` mapping offline (Plane A).

    Order: context → FIND-026 preconditions → A → (B/C/D/E/F/G if runnable with
    one shared gold slot) → **I** → H → optional gated Lane C' → envelope
    validate → gates. Short-circuit is A + I + H + optional C' + envelope
    validate + gates (topology is not message-dependent). Default path stays
    offline/no-network: Lane C' runs only when ``enable_lane_c=True``. Family /
    gate / Lane C' exceptions become evaluator errors + fail-closed gate
    composition and never abort the case.
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

    # Optional gated Lane C' (advisory only). Default offline path never invokes.
    lane_c_eligibility = None
    lane_c_rows: list[ScoreResultV1] = []
    lane_c_run_evidence: dict[str, Any] = {"lane_c_enabled": bool(enable_lane_c)}
    if enable_lane_c:
        try:
            from git_cg.eval.lane_c import run_lane_c

            # Prefer explicit final-accept evidence; else project from context.
            fa_evidence = final_accept_evidence
            if fa_evidence is None and judge_input is None:
                fa_evidence = {
                    "final_message_text": getattr(ctx, "final_message", None) or "",
                    "case_id": ctx.case_id,
                    "artifact_class": getattr(ctx, "artifact_class", None),
                    "bound": getattr(ctx, "bound", None),
                    "files": list(getattr(ctx, "files", ()) or ()),
                }

            # Provisional deterministic eligibility from family scores only.
            # True-advisory prefixes never veto; missing/failed required metrics do.
            by_tmp = {s.metric_id: s for s in scores}
            det_pass = True
            for mid in req:
                if str(mid).startswith(("cprime.", "gate.")):
                    continue
                row = by_tmp.get(mid)
                if row is None or row.passed is False:
                    det_pass = False
                    break
                if row.passed is None and getattr(row.polarity, "value", str(row.polarity)) == "pass_fail":
                    det_pass = False
                    break

            c_result = run_lane_c(
                lane_c_metric_ids,
                deterministic_pass=det_pass,
                allows_lane_c=lane_c_allows,
                lab_override=lane_c_lab_override,
                suite=suite,
                judge_model=judge_model,
                judge_api_key=judge_api_key,
                environ=lane_c_environ,
                use_default_metrics=lane_c_metric_ids is None,
                judge_fn=judge_fn,
                judge_input=judge_input,
                final_accept_evidence=fa_evidence,
                max_input_chars=max_input_chars,
            )
            lane_c_rows = list(c_result.rows)
            scores.extend(lane_c_rows)
            lane_c_eligibility = c_result.eligibility
            lane_c_run_evidence = dict(c_result.evidence)
            lane_c_run_evidence["lane_c_enabled"] = True
            lane_c_run_evidence["cprime_attempted"] = True
            # Surface pack identities from scored/skip rows for Family H honesty.
            pack_ids: list[str] = []
            hashes: list[str] = []
            pin_refs_acc: list[str] = []
            for row in lane_c_rows:
                for pref in row.pin_refs or []:
                    if isinstance(pref, str) and pref not in pin_refs_acc:
                        pin_refs_acc.append(pref)
                payload = row.evidence or {}
                pid = payload.get("pack_identity")
                if isinstance(pid, str) and pid not in pack_ids:
                    pack_ids.append(pid)
                digest = payload.get("content_sha256")
                if isinstance(digest, str) and digest not in hashes:
                    hashes.append(digest)
            if pack_ids:
                lane_c_run_evidence.setdefault("pack_identities", pack_ids)
                lane_c_run_evidence.setdefault("pack_identity", pack_ids[0])
            if hashes:
                lane_c_run_evidence.setdefault("content_hashes", hashes)
                lane_c_run_evidence.setdefault("content_sha256", hashes[0])
            if pin_refs_acc:
                lane_c_run_evidence.setdefault("pin_refs", pin_refs_acc)
        except Exception as exc:
            errors.append(f"lane_c:{type(exc).__name__}: {exc}")
            lane_c_eligibility = None
            lane_c_rows = []
            lane_c_run_evidence = {
                "lane_c_enabled": True,
                "cprime_attempted": True,
                "invoked": False,
                "scored_count": 0,
                "cprime_ran": False,
                "available": False,
                "error": type(exc).__name__,
            }

    # S5 / D39 — Family H C' honesty metrics after Lane C (never green-by-absence).
    try:
        scores.extend(
            score_family_h_cprime(
                suite_snapshot_pin=suite_snapshot_pin,
                lane_c_run_evidence=lane_c_run_evidence,
                lane_c_rows=lane_c_rows,
            )
        )
    except Exception as exc:
        errors.append(f"family_h_cprime:{type(exc).__name__}: {exc}")

    # Re-validate envelopes after C' rows + H honesty metrics (C' already constructed).
    valid_scores = []
    env_bad = 0
    i_ids = set(FAMILY_I_METRIC_IDS)
    cprime_h_ids = {
        "h.judge_input_isolated",
        "h.prompt_pack_pinned",
        "h.prompt_pack_hash_known",
        "h.prompt_pack_suite_fresh",
    }
    for s in scores:
        if s.metric_id in i_ids or str(s.metric_id).startswith("cprime.") or s.metric_id in cprime_h_ids:
            # Already constructed via catalog helpers / recovered paths.
            try:
                valid_scores.append(ScoreResultV1.model_validate(s.model_dump(mode="json")))
            except Exception:
                env_bad += 1
            continue
        try:
            payload = s.model_dump(mode="json")
            valid_scores.append(ScoreResultV1.model_validate(payload))
        except Exception:
            env_bad += 1
    scores = valid_scores
    if env_bad:
        errors.append(f"envelope_post_c:{env_bad}_invalid")

    try:
        gates = compose_gates(
            scores,
            require_block=req,
            bound=ctx.bound,
            require_topology=topo_required,
            gold_mode=gold_mode,
            lane_c_eligibility=lane_c_eligibility,
            lane_c_run_evidence=lane_c_run_evidence,
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
    # suite_path is a test override only - reject it when case membership diverges
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
