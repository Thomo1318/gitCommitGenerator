"""Lane C' Slice 6 residual diagnostics (R1/R8/R10/R6).

All helpers are offline, injectable, and non-gating:

* **R1** — richer rubric metric id flags (opt-in only; never default spine)
* **R8** — flakiness hooks (``runs_per_item`` → ``cprime.flakiness_std``)
* **R10** — NLP similarity diagnostics (``nlp.*``)
* **R6** — scrubbed moderation / compliance ops signals (off-by-default)

None of these rows may sole-pass product Hybrid, golden promotion, accept-path,
or first-CI gates. Default :data:`DEFAULT_LANE_C_METRICS` remains craft/relevance.
"""

from __future__ import annotations

import hashlib
import math
import re
import statistics
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from git_cg.eval.enums import Authority, Family, Polarity, Severity, Source
from git_cg.eval.evidence_scrub import scrub_evidence_mapping
from git_cg.eval.lane_c.advisory import make_advisory_skip
from git_cg.eval.lane_c.judge import JudgeFn, JudgeOutcome, run_pinned_judge
from git_cg.eval.lane_c.judge_input import JudgeInput
from git_cg.eval.lane_c.taxonomy import EXEC_JUDGE_NOT_INVOKED, EXEC_SCORED
from git_cg.eval.score_result import ScoreResultV1
from git_cg.eval.scoring.context import live_pin_refs
from git_cg.eval.scoring.result_builder import metric_row

__all__ = [
    "DEFAULT_RICHER_RUBRIC_METRICS",
    "NLP_METRIC_IDS",
    "RICHER_RUBRIC_METRICS",
    "DiagnosticError",
    "FlakinessResult",
    "ModerationResult",
    "NlpDiagnosticResult",
    "bleu_score",
    "compute_nlp_diagnostics",
    "evaluate_moderation_ops",
    "levenshtein_similarity",
    "measure_flakiness",
    "resolve_richer_rubric_metrics",
    "rouge_l_f1",
]

# R1 — optional richer C' rubrics (never default spine).
RICHER_RUBRIC_METRICS: Final[tuple[str, ...]] = (
    "cprime.usefulness",
    "cprime.answer_relevance",
    "cprime.meaning_match",
    "cprime.hallucination_narrative",
    "cprime.jury_aggregate",
    "cprime.conversation_thread",
)
DEFAULT_RICHER_RUBRIC_METRICS: Final[tuple[str, ...]] = ()  # off-by-default

NLP_METRIC_IDS: Final[tuple[str, ...]] = (
    "nlp.levenshtein",
    "nlp.bleu",
    "nlp.rouge",
    "nlp.bertscore",
)

_NON_GATING: Final[dict[str, Any]] = {
    "diagnostic_only": True,
    "non_gating": True,
    "product_authority": None,
}

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?", re.IGNORECASE)


class DiagnosticError(ValueError):
    """Invalid residual diagnostic configuration or input."""


def resolve_richer_rubric_metrics(
    *,
    enabled: bool | Sequence[str] | None = None,
    include: Sequence[str] | None = None,
) -> tuple[str, ...]:
    """Resolve opt-in R1 richer rubric metric ids.

    * ``enabled=False`` / ``None`` → empty (default off)
    * ``enabled=True`` → full :data:`RICHER_RUBRIC_METRICS`
    * ``enabled`` sequence → that explicit subset (must be known richer ids)
    * ``include`` merges additional known richer ids

    Unknown ids fail closed. Default Lane C spine is never implied here.
    """
    selected: list[str] = []
    if enabled is True:
        selected.extend(RICHER_RUBRIC_METRICS)
    elif isinstance(enabled, Sequence) and not isinstance(enabled, (str, bytes)):
        selected.extend(str(x) for x in enabled)
    elif enabled is not None and enabled is not False:
        raise DiagnosticError("enabled must be bool, sequence of metric ids, or None")

    if include:
        selected.extend(str(x) for x in include)

    if not selected:
        return ()

    allowed = set(RICHER_RUBRIC_METRICS)
    out: list[str] = []
    unknown: list[str] = []
    for mid in selected:
        if mid not in allowed:
            unknown.append(mid)
            continue
        if mid not in out:
            out.append(mid)
    if unknown:
        raise DiagnosticError(f"unknown richer rubric metric id(s): {sorted(set(unknown))}")
    return tuple(out)


# ---------------------------------------------------------------------------
# R8 — flakiness
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FlakinessResult:
    """Lab flakiness study outcome (advisory only)."""

    scores: list[float]
    mean: float
    std: float
    n: int
    row: ScoreResultV1
    skipped: bool = False


def measure_flakiness(
    *,
    judge_fn: JudgeFn | None,
    prompt: str,
    judge_input: JudgeInput | Mapping[str, str],
    model: str,
    runs_per_item: int = 3,
    metric_id: str = "cprime.flakiness_std",
    timeout_s: float = 15.0,
    pin_refs: list[str] | None = None,
    evidence: Mapping[str, Any] | None = None,
) -> FlakinessResult:
    """Repeat a pinned judge call and emit advisory ``cprime.flakiness_std``.

    Requires an injectable ``judge_fn`` (offline tests supply a stub). Never
    opens a network socket itself. ``runs_per_item`` must be ≥ 2.
    """
    if runs_per_item < 2:
        raise DiagnosticError("runs_per_item must be >= 2")
    if metric_id != "cprime.flakiness_std":
        raise DiagnosticError("flakiness metric_id must be cprime.flakiness_std")
    if not model or not str(model).strip():
        raise DiagnosticError("model pin is required for flakiness studies")

    base_ev = {
        "lab_only": True,
        "runs_per_item": runs_per_item,
        "model": str(model).strip(),
        "residual": "R8",
    }
    if evidence:
        base_ev.update(dict(evidence))
    # Honesty keys are invariant — caller evidence must not override them.
    base_ev.update(_NON_GATING)

    if judge_fn is None:
        row = make_advisory_skip(
            metric_id,
            reason=EXEC_JUDGE_NOT_INVOKED,
            evidence={**base_ev, "skipped": True},
            pin_refs=pin_refs,
        )
        return FlakinessResult(scores=[], mean=0.0, std=0.0, n=0, row=row, skipped=True)

    payload: JudgeInput | Mapping[str, str] = judge_input

    scores: list[float] = []
    errors = 0
    for _ in range(runs_per_item):
        outcome: JudgeOutcome = run_pinned_judge(
            prompt,
            payload,  # type: ignore[arg-type]
            judge_fn=judge_fn,
            model=str(model).strip(),
            timeout_s=timeout_s,
        )
        if outcome.ok and outcome.score is not None:
            scores.append(float(outcome.score))
        else:
            errors += 1

    if len(scores) < 2:
        row = make_advisory_skip(
            metric_id,
            reason=EXEC_JUDGE_NOT_INVOKED,
            evidence={
                **base_ev,
                "skipped": True,
                "score_count": len(scores),
                "error_count": errors,
                "insufficient_scores": True,
            },
            pin_refs=pin_refs,
        )
        mean = float(scores[0]) if scores else 0.0
        return FlakinessResult(scores=scores, mean=mean, std=0.0, n=len(scores), row=row, skipped=True)

    mean = float(statistics.fmean(scores))
    std = float(statistics.pstdev(scores))  # population std over the lab sample
    # flakiness_std is lower_is_better continuous — not a GEval 1-5 mark.
    row = _continuous_advisory_row(
        metric_id,
        std,
        reason=EXEC_SCORED,
        evidence={
            **base_ev,
            "skipped": False,
            "scores": scores,
            "mean": mean,
            "std": std,
            "n": len(scores),
            "error_count": errors,
            "execution_code": EXEC_SCORED,
        },
        pin_refs=pin_refs,
    )
    return FlakinessResult(scores=scores, mean=mean, std=std, n=len(scores), row=row, skipped=False)


def _continuous_advisory_row(
    metric_id: str,
    value: float,
    *,
    reason: str,
    evidence: Mapping[str, Any],
    pin_refs: list[str] | None = None,
) -> ScoreResultV1:
    """Build continuous advisory/lab/ops row with ``passed is None``."""
    crow = metric_row(metric_id)
    if crow is None:
        raise KeyError(f"unknown metric_id not in catalog: {metric_id}")
    polarity = Polarity(crow["polarity"])
    if polarity is Polarity.PASS_FAIL:
        raise DiagnosticError(f"{metric_id} is pass_fail; use boolean helper")
    payload = scrub_evidence_mapping({**dict(evidence), **_NON_GATING})
    if not isinstance(payload, dict):
        payload = dict(_NON_GATING)
    sev = crow.get("severity")
    return ScoreResultV1(
        metric_id=metric_id,
        polarity=polarity,
        authority=Authority(crow["authority"]),
        source=Source(crow.get("source_default") or "lab_meta"),
        value=float(value),
        name=crow.get("name"),
        family=Family(crow["family"]) if crow.get("family") else None,
        threshold=None,
        passed=None,
        severity=Severity(sev) if sev is not None else None,
        reason=reason,
        evidence=payload,
        failure_ids=None,
        product_authority=None,
        pin_refs=list(pin_refs) if pin_refs is not None else live_pin_refs(),
    )


def _pass_fail_ops_row(
    metric_id: str,
    value: bool,
    *,
    reason: str,
    evidence: Mapping[str, Any],
    pin_refs: list[str] | None = None,
) -> ScoreResultV1:
    crow = metric_row(metric_id)
    if crow is None:
        raise KeyError(f"unknown metric_id not in catalog: {metric_id}")
    payload = scrub_evidence_mapping({**dict(evidence), **_NON_GATING})
    if not isinstance(payload, dict):
        payload = dict(_NON_GATING)
    sev = crow.get("severity")
    return ScoreResultV1(
        metric_id=metric_id,
        polarity=Polarity(crow["polarity"]),
        authority=Authority(crow["authority"]),
        source=Source(crow.get("source_default") or "lab_meta"),
        value=bool(value),
        name=crow.get("name"),
        family=Family(crow["family"]) if crow.get("family") else None,
        threshold=None,
        passed=None,  # never derive gate boolean from ops residual
        severity=Severity(sev) if sev is not None else None,
        reason=reason,
        evidence=payload,
        failure_ids=None,
        product_authority=None,
        pin_refs=list(pin_refs) if pin_refs is not None else live_pin_refs(),
    )


# ---------------------------------------------------------------------------
# R10 — NLP diagnostics
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class NlpDiagnosticResult:
    """Bundle of diagnostic NLP score rows."""

    rows: list[ScoreResultV1]
    values: dict[str, float | None]


def _tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in _TOKEN_RE.finditer(text or "")]


def _levenshtein_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    # Memory-efficient two-row DP
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i]
        for j, cb in enumerate(b, start=1):
            ins = cur[j - 1] + 1
            delete = prev[j] + 1
            sub = prev[j - 1] + (0 if ca == cb else 1)
            cur.append(min(ins, delete, sub))
        prev = cur
    return prev[-1]


def levenshtein_similarity(candidate: str, reference: str) -> float:
    """Normalized Levenshtein similarity in ``[0, 1]`` (1 = identical)."""
    a, b = candidate or "", reference or ""
    if not a and not b:
        return 1.0
    dist = _levenshtein_distance(a, b)
    return 1.0 - (dist / max(len(a), len(b)))


def bleu_score(candidate: str, reference: str, *, max_n: int = 2) -> float:
    """Tiny corpus-free BLEU-like score (modified n-gram precision + brevity)."""
    cand = _tokenize(candidate)
    ref = _tokenize(reference)
    if not cand and not ref:
        return 1.0
    if not cand or not ref:
        return 0.0
    precisions: list[float] = []
    for n in range(1, max_n + 1):
        cand_ngrams = Counter(tuple(cand[i : i + n]) for i in range(len(cand) - n + 1))
        ref_ngrams = Counter(tuple(ref[i : i + n]) for i in range(len(ref) - n + 1))
        if not cand_ngrams:
            precisions.append(0.0)
            continue
        overlap = sum(min(cnt, ref_ngrams[ng]) for ng, cnt in cand_ngrams.items())
        precisions.append(overlap / sum(cand_ngrams.values()))
    if any(p == 0.0 for p in precisions):
        # Smoothing: avoid hard-zero geometric mean for short texts.
        precisions = [p if p > 0.0 else 1e-9 for p in precisions]
    log_avg = sum(math.log(p) for p in precisions) / len(precisions)
    precision = math.exp(log_avg)
    # Brevity penalty
    c, r = len(cand), len(ref)
    bp = 1.0 if c > r else math.exp(1.0 - (r / max(c, 1)))
    return float(bp * precision)


def rouge_l_f1(candidate: str, reference: str) -> float:
    """ROUGE-L F1 based on LCS over tokens."""
    cand = _tokenize(candidate)
    ref = _tokenize(reference)
    if not cand and not ref:
        return 1.0
    if not cand or not ref:
        return 0.0
    lcs = _lcs_len(cand, ref)
    prec = lcs / len(cand)
    rec = lcs / len(ref)
    if prec + rec == 0:
        return 0.0
    return float(2 * prec * rec / (prec + rec))


def _lcs_len(a: Sequence[str], b: Sequence[str]) -> int:
    if not a or not b:
        return 0
    # Two-row LCS length
    prev = [0] * (len(b) + 1)
    for ca in a:
        cur = [0]
        for j, cb in enumerate(b, start=1):
            if ca == cb:
                cur.append(prev[j - 1] + 1)
            else:
                cur.append(max(prev[j], cur[-1]))
        prev = cur
    return prev[-1]


def compute_nlp_diagnostics(
    candidate: str,
    reference: str,
    *,
    metrics: Sequence[str] | None = None,
    bertscore_fn: Callable[[str, str], float] | None = None,
    pin_refs: list[str] | None = None,
    enabled: bool = True,
) -> NlpDiagnosticResult:
    """Emit diagnostic ``nlp.*`` rows (off unless ``enabled``).

    BERTScore is optional: without ``bertscore_fn`` / dependency the row is an
    honest diagnostic skip (``value=0.0``, ``passed=None``) rather than a fake
    similarity score.
    """
    if not enabled:
        return NlpDiagnosticResult(rows=[], values={})

    wanted = list(metrics) if metrics is not None else list(NLP_METRIC_IDS)
    unknown = [m for m in wanted if m not in NLP_METRIC_IDS]
    if unknown:
        raise DiagnosticError(f"unknown nlp metric id(s): {unknown}")

    values: dict[str, float | None] = {}
    rows: list[ScoreResultV1] = []
    base = {**_NON_GATING, "residual": "R10", "family": "nlp"}

    for mid in wanted:
        if mid == "nlp.levenshtein":
            val = levenshtein_similarity(candidate, reference)
            values[mid] = val
            rows.append(
                _continuous_advisory_row(
                    mid,
                    val,
                    reason="nlp_diagnostic",
                    evidence={**base, "metric": "levenshtein_similarity"},
                    pin_refs=pin_refs,
                )
            )
        elif mid == "nlp.bleu":
            val = bleu_score(candidate, reference)
            values[mid] = val
            rows.append(
                _continuous_advisory_row(
                    mid,
                    val,
                    reason="nlp_diagnostic",
                    evidence={**base, "metric": "bleu"},
                    pin_refs=pin_refs,
                )
            )
        elif mid == "nlp.rouge":
            val = rouge_l_f1(candidate, reference)
            values[mid] = val
            rows.append(
                _continuous_advisory_row(
                    mid,
                    val,
                    reason="nlp_diagnostic",
                    evidence={**base, "metric": "rouge_l_f1"},
                    pin_refs=pin_refs,
                )
            )
        elif mid == "nlp.bertscore":
            if bertscore_fn is None:
                values[mid] = None
                rows.append(
                    _continuous_advisory_row(
                        mid,
                        0.0,
                        reason="nlp_bertscore_unavailable",
                        evidence={
                            **base,
                            "skipped": True,
                            "available": False,
                            "metric": "bertscore",
                            "note": "optional dependency/fn not provided; honest skip",
                        },
                        pin_refs=pin_refs,
                    )
                )
            else:
                val = float(bertscore_fn(candidate, reference))
                if val < 0.0 or val > 1.0:
                    raise DiagnosticError("bertscore_fn must return value in [0, 1]")
                values[mid] = val
                rows.append(
                    _continuous_advisory_row(
                        mid,
                        val,
                        reason="nlp_diagnostic",
                        evidence={**base, "metric": "bertscore", "available": True},
                        pin_refs=pin_refs,
                    )
                )
    return NlpDiagnosticResult(rows=rows, values=values)


# ---------------------------------------------------------------------------
# R6 — moderation ops (scrubbed, off-by-default, no Promptfoo)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ModerationResult:
    """Scrubbed moderation ops signal (never raw sample body)."""

    flagged: bool
    category: str | None
    risk: float
    rows: list[ScoreResultV1]
    evidence: dict[str, Any]


# Lightweight local heuristic — not a red-team engine (#219 owns Promptfoo depth).
_FLAG_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("credential_exfil", re.compile(r"\b(api[_-]?key|secret[_-]?key|private[_-]?key)\b\s*[:=]", re.I)),
    ("credential_exfil", re.compile(r"\bsk-[A-Za-z0-9]{16,}\b")),
    ("prompt_injection", re.compile(r"\b(ignore\s+(all\s+)?previous\s+instructions|jailbreak)\b", re.I)),
    ("malware_assist", re.compile(r"\b(ransomware|keylogger|reverse\s+shell)\b", re.I)),
)


def evaluate_moderation_ops(
    text: str,
    *,
    enabled: bool = False,
    pin_refs: list[str] | None = None,
    category_hint: str | None = None,
) -> ModerationResult:
    """Emit scrubbed ``ops.moderation_flag`` / ``ops.compliance_risk`` rows.

    Default ``enabled=False`` (off). Never returns the raw sample body in
    evidence. No Promptfoo dependency — #219 remains the red-team plane.
    """
    if not enabled:
        return ModerationResult(
            flagged=False,
            category=None,
            risk=0.0,
            rows=[],
            evidence={"enabled": False, "residual": "R6", "plane": "#219-coord"},
        )

    sample = text or ""
    category: str | None = category_hint
    flagged = False
    if category is None:
        for cat, pattern in _FLAG_PATTERNS:
            if pattern.search(sample):
                flagged = True
                category = cat
                break
    else:
        flagged = True

    # Risk in [0, 1]; lower_is_better on ops.compliance_risk.
    risk = 1.0 if flagged else 0.0
    if flagged and category == "prompt_injection":
        risk = 0.8
    elif flagged and category == "credential_exfil":
        risk = 0.9
    elif flagged and category == "malware_assist":
        risk = 1.0

    evidence = scrub_evidence_mapping(
        {
            **_NON_GATING,
            "residual": "R6",
            "enabled": True,
            "flagged": flagged,
            "category": category,
            "risk": risk,
            "sample_chars": len(sample),
            "sample_sha16": hashlib.sha256(sample.encode("utf-8", errors="replace")).hexdigest()[:16],
            "raw_sample_retained": False,
            "promptfoo": False,
            "plane": "#219-coord",
            "note": "scrubbed ops signal only; Promptfoo red-team remains #219",
        }
    )
    if not isinstance(evidence, dict):
        evidence = {"residual": "R6"}

    rows = [
        _pass_fail_ops_row(
            "ops.moderation_flag",
            bool(flagged),
            reason="ops_moderation",
            evidence=evidence,
            pin_refs=pin_refs,
        ),
        _continuous_advisory_row(
            "ops.compliance_risk",
            float(risk),
            reason="ops_compliance_risk",
            evidence=evidence,
            pin_refs=pin_refs,
        ),
    ]
    return ModerationResult(
        flagged=flagged,
        category=category,
        risk=risk,
        rows=rows,
        evidence=evidence,
    )
