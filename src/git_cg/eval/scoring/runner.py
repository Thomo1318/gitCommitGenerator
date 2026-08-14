"""S2a offline Plane A scoring runner over ``ape_bundle_v1`` fixtures."""

from __future__ import annotations

import json
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
from git_cg.eval.scoring.family_d import GoldBridge, score_family_d
from git_cg.eval.scoring.family_h import score_family_h
from git_cg.eval.scoring.gates import S2A_REQUIRE_BLOCK, compose_gates
from git_cg.eval.scoring.preconditions import evaluate_preconditions
from git_cg.eval.scoring.result_builder import make_score

__all__ = [
    "ScoreCaseResult",
    "ScoreSuiteResult",
    "score_bundle",
    "score_case",
    "score_suite",
]


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

    @property
    def all_results(self) -> list[ScoreResultV1]:
        return [*self.scores, *self.gates]

    @property
    def deterministic_pass(self) -> bool | None:
        for g in self.gates:
            if g.metric_id == "gate.deterministic_pass":
                return g.passed
        return None

    def by_id(self) -> dict[str, ScoreResultV1]:
        return {s.metric_id: s for s in self.all_results}


@dataclass(slots=True)
class ScoreSuiteResult:
    """Suite-level aggregation of case scores."""

    suite_id: str
    cases: list[ScoreCaseResult] = field(default_factory=list)
    suite_snapshot_pin: str | None = None
    require_block: tuple[str, ...] = S2A_REQUIRE_BLOCK
    snapshot: dict[str, Any] | None = None

    @property
    def all_pass(self) -> bool:
        return all(c.deterministic_pass is True for c in self.cases)


def score_bundle(
    bundle: dict[str, Any],
    *,
    suite: dict[str, Any] | None = None,
    suite_snapshot_pin: str | None = None,
    require_block: tuple[str, ...] | None = None,
    gold_mode: str = "strict",
    gold_bridge: GoldBridge | None = None,
    offline: bool = True,
    max_eval_bytes: int | None = None,
    case_id: str | None = None,
) -> ScoreCaseResult:
    """Score one ``ape_bundle_v1`` mapping (already loaded/encoded)."""
    errors: list[str] = []
    scores: list[ScoreResultV1] = []

    try:
        kwargs: dict[str, Any] = {"suite": suite, "case_id": case_id}
        if max_eval_bytes is not None:
            kwargs["max_eval_bytes"] = max_eval_bytes
        ctx = project_score_context(bundle, **kwargs)
    except ScoreContextError as exc:
        errors.append(f"context:{exc}")
        # Minimal recovery context so H can still emit FIND-026
        bid = case_id or (bundle.get("case_id") if isinstance(bundle, dict) else None) or "unknown"
        ctx = ScoreContext(
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
        )
    except Exception as exc:
        errors.append(f"context:{type(exc).__name__}: {exc}")
        bid = case_id or (bundle.get("case_id") if isinstance(bundle, dict) else None) or "unknown"
        ctx = ScoreContext(
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
        )

    pre = evaluate_preconditions(ctx)
    req = require_block if require_block is not None else S2A_REQUIRE_BLOCK

    if pre.short_circuit:
        # FIND-026: skip B/D; still run A + H + gates
        try:
            scores.extend(score_family_a(ctx))
        except Exception as exc:
            errors.append(f"family_a:{type(exc).__name__}: {exc}")
        try:
            scores.extend(
                score_family_h(
                    ctx,
                    pre=pre,
                    family_scores=list(scores),
                    suite_snapshot_pin=suite_snapshot_pin,
                    offline=offline,
                    evaluator_errors=errors,
                )
            )
        except Exception as exc:
            errors.append(f"family_h:{type(exc).__name__}: {exc}")
    else:
        for name, fn in (
            ("family_a", lambda: score_family_a(ctx)),
            ("family_b", lambda: score_family_b(ctx)),
            (
                "family_d",
                lambda: score_family_d(ctx, gold_mode=gold_mode, gold_bridge=gold_bridge),
            ),
        ):
            try:
                scores.extend(fn())
            except Exception as exc:
                errors.append(f"{name}:{type(exc).__name__}: {exc}")
        try:
            scores.extend(
                score_family_h(
                    ctx,
                    pre=pre,
                    family_scores=list(scores),
                    suite_snapshot_pin=suite_snapshot_pin,
                    offline=offline,
                    evaluator_errors=errors,
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

    # Envelope validate / drop invalid rows
    valid_scores: list[ScoreResultV1] = []
    env_bad = 0
    for s in scores:
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
    )


def score_case(
    case_path: str | Path,
    *,
    suite_snapshot_pin: str | None = None,
    require_block: tuple[str, ...] | None = None,
    gold_mode: str = "strict",
    gold_bridge: GoldBridge | None = None,
    offline: bool = True,
    case_id: str | None = None,
    suite_id: str | None = None,
) -> ScoreCaseResult:
    """Load a fixture case JSON file, encode via S1, and score the bundle."""
    path = Path(case_path)
    fixture = json.loads(path.read_text(encoding="utf-8"))
    cid = case_id or fixture.get("case_id") or path.stem
    encoded = encode_fixture(fixture, case_id=str(cid), suite_id=suite_id, validate=True)
    bundle = encoded["bundle"]
    return score_bundle(
        bundle,
        suite_snapshot_pin=suite_snapshot_pin,
        require_block=require_block,
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
    gold_mode: str = "strict",
    gold_bridge: GoldBridge | None = None,
    offline: bool = True,
    suite_path: str | Path | None = None,
) -> ScoreSuiteResult:
    """Score every case in a committed suite using S1 loaders + snapshot pin."""
    root = Path(fixture_root) if fixture_root else default_fixture_root()

    # Optional path form for tests
    if suite_path is not None:
        path = Path(suite_path)
        suite_doc = json.loads(path.read_text(encoding="utf-8"))
        sid = str(suite_doc.get("suite_id") or suite_id)
    else:
        suite_doc = load_suite(suite_id, fixture_root=root)
        sid = str(suite_doc.get("suite_id") or suite_id)

    metrics = suite_doc.get("metrics") or {}
    if require_block is not None:
        req = tuple(require_block)
    elif isinstance(metrics, dict) and metrics.get("require_block"):
        req = tuple(metrics["require_block"])
    else:
        req = S2A_REQUIRE_BLOCK

    # Snapshot pin (content-addressed) always binds the *canonical* committed suite.
    # suite_path is a test override only — reject it when case membership diverges
    # so the pin cannot claim one corpus while we score another.
    snapshot = build_snapshot(sid, fixture_root=root, validate=True)
    suite_pin = str(snapshot.get("snapshot_hash") or snapshot.get("id") or "")
    pinned_suite = snapshot.get("suite") if isinstance(snapshot.get("suite"), dict) else {}
    pinned_case_ids = list(pinned_suite.get("case_ids") or [])
    scored_case_ids = list(suite_doc.get("case_ids") or [])
    if suite_path is not None and scored_case_ids != pinned_case_ids:
        raise ValueError(
            "suite_path case_ids diverge from canonical suite "
            f"{sid!r}: scored={scored_case_ids!r} pinned={pinned_case_ids!r}"
        )

    pairs = load_suite_fixtures(suite_doc, fixture_root=root)
    cases_out: list[ScoreCaseResult] = []
    for cid, fixture in pairs:
        encoded = encode_fixture(fixture, case_id=cid, suite_id=sid, validate=True)
        cases_out.append(
            score_bundle(
                encoded["bundle"],
                suite=suite_doc,
                suite_snapshot_pin=suite_pin,
                require_block=req,
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
    )
