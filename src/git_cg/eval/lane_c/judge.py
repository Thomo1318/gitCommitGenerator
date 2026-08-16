"""Lane C-prime GEval judge — pinned, gold-blind, fail-closed, never blocking.

This module is the **only** place a Lane C-prime LLM judge is invoked. It is
strictly advisory (F3): a judge score can never pass CI, the accept-path, or
golden promotion on its own, and a judge failure never blocks Lane A/B (F4).

Design laws enforced here:

* **Pinned judge (F5).** The model id comes from the already-resolved
  eligibility pin (``GIT_CG_EVAL_JUDGE_MODEL``); a floating ``latest`` was
  rejected upstream by :func:`judge_pins_resolvable`. The prompt identity is
  the repo-owned ``prompt_pack_v1`` content hash (INT-26) — never a cloud
  "latest" prompt. The rubric text the judge reads is the exact byte set the
  hash pins (single source of truth).
* **Gold-blind (F6 / RK-A4).** The judge input carries only the final commit
  message plus an optional diff-stat summary. No ``expected_*`` labels, goldens,
  or assertions are ever placed in the prompt outside an explicitly labelled
  meta-eval envelope (out of scope for this slice).
* **Input guards (v0.9.1 / INT-49).** Empty/whitespace input and oversize input
  (``h.eval_input_nonempty`` / ``h.eval_input_size_ok``) never reach the network
  — they return a skip outcome before any client is built.
* **Never blocking (F4).** No public function here raises on a judge, pack,
  network, or parse failure. Every failure degrades to a :class:`JudgeOutcome`
  skip with a stable machine-readable reason so the runner records an honest
  non-score.

The network seam is an injectable ``judge_fn`` callable. The default
:func:`openai_compatible_judge_fn` builds an OpenAI-compatible client lazily
(only when actually scoring); tests inject a fake and never touch the network.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from git_cg.eval.lane_c.eligibility import ENV_JUDGE_API_KEY, ENV_JUDGE_MODEL
from git_cg.eval.lane_c.prompt_pack import (
    DEFAULT_PROMPT_ROOT,
    PromptPackError,
    load_pack_prompt_text,
    resolve_judge_pack,
)

#: GEval scores on the rubric's 1-5 scale.
MIN_JUDGE_SCORE = 1
MAX_JUDGE_SCORE = 5

#: Hard ceiling on judge-input characters (INT-49 / h.eval_input_size_ok).
#: Oversize input is skipped, never truncated-and-sent, so a runaway diff stat
#: cannot produce a 504 retry storm. Configurable downward only.
DEFAULT_MAX_INPUT_CHARS = 32_000

#: Bounded judge transport (v0.9.1 — no retry storms in a hook process).
#: The judge runs inside a commit hook; an unbounded client could hang the
#: commit. A short timeout and a single retry keep worst-case latency small,
#: and any exhaustion degrades to a skip row rather than blocking the commit.
DEFAULT_JUDGE_TIMEOUT_S = 15.0
DEFAULT_JUDGE_MAX_RETRIES = 1

#: Stable skip reasons (machine-readable; recorded in ScoreResult.reason).
REASON_EMPTY_INPUT = "lane_c_empty_input"
REASON_INPUT_TOO_LARGE = "lane_c_input_too_large"
REASON_PACK_UNRESOLVABLE = "lane_c_prompt_pack_unresolvable"
REASON_JUDGE_ERROR = "lane_c_judge_error"
REASON_JUDGE_PARSE_ERROR = "lane_c_judge_parse_error"

#: Judge-callable seam. Receives (system_prompt, user_prompt, model, api_key)
#: and returns the raw judge text (expected to be a JSON object string).
JudgeFn = Callable[[str, str, str, str], str]


@dataclass(frozen=True)
class JudgeOutcome:
    """Result of a single pinned-judge evaluation (never raises).

    ``scored`` is True only when the judge returned a parseable in-range score.
    When False, ``reason`` carries the stable skip/failure classification and
    ``score``/``rationale`` are None. ``pack`` is the resolved prompt_pack_v1
    identity (its ``content_sha256`` is the prompt pin evidence).
    """

    scored: bool
    metric_id: str
    score: int | None = None
    rationale: str | None = None
    reason: str | None = None
    pack: dict[str, Any] | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


def resolve_judge_credentials(
    *,
    judge_model: str | None = None,
    judge_api_key: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> tuple[str, str]:
    """Resolve the pinned (model, api_key) pair for the judge call.

    Mirrors the presence probe in :func:`judge_pins_resolvable` (explicit arg →
    environment). The runner only calls this after eligibility confirmed pins
    are resolvable, so the returned values are non-empty. Never logs the key.
    """
    env = environ if environ is not None else os.environ
    model = judge_model if judge_model is not None else env.get(ENV_JUDGE_MODEL, "")
    key = judge_api_key if judge_api_key is not None else env.get(ENV_JUDGE_API_KEY, "")
    return model.strip(), key.strip()


def _render_user_prompt(message: str, diff_summary: str | None) -> str:
    """Assemble the gold-blind judge user prompt.

    Only the final message text and an optional diff-stat summary are included.
    No expected/gold/assertion content is ever added here (F6).
    """
    parts = ["## Commit message under evaluation", "", message.strip()]
    if diff_summary and diff_summary.strip():
        parts += ["", "## Change summary (diff stat)", "", diff_summary.strip()]
    return "\n".join(parts)


def _parse_judge_response(raw: str) -> tuple[int, str]:
    """Parse and validate the judge JSON response. Raises on malformed input.

    The rubric contract is ``{"score": 1-5, "rationale": str}``. Score must be
    an integer in the closed range; bool and out-of-range values are rejected.
    """
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("judge response is not a JSON object")
    score = data.get("score")
    if isinstance(score, bool) or not isinstance(score, int):
        raise ValueError("judge score must be an integer")
    if not (MIN_JUDGE_SCORE <= score <= MAX_JUDGE_SCORE):
        raise ValueError(f"judge score out of range {MIN_JUDGE_SCORE}-{MAX_JUDGE_SCORE}: {score}")
    rationale = data.get("rationale")
    if rationale is not None and not isinstance(rationale, str):
        raise ValueError("judge rationale must be a string")
    return score, (rationale or "")


def openai_compatible_judge_fn(
    system_prompt: str,
    user_prompt: str,
    model: str,
    api_key: str,
    *,
    timeout_s: float = DEFAULT_JUDGE_TIMEOUT_S,
    max_retries: int = DEFAULT_JUDGE_MAX_RETRIES,
) -> str:
    """Default judge transport: an OpenAI-compatible chat completion.

    Built lazily and only when actually scoring, so importing this module stays
    network- and SDK-free (F4 import-safety). The client is bounded (short
    timeout, single retry) so a judge hang can never stall a commit hook.
    Returns the raw message content.
    """
    from openai import OpenAI  # local import: keep module import offline-safe

    client = OpenAI(api_key=api_key, timeout=timeout_s, max_retries=max_retries)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
    )
    return resp.choices[0].message.content or ""


def _pack_dir_for(metric_id: str, prompt_root: Path | None) -> Path:
    """Resolve the on-disk pack directory for a ``cprime.*`` metric id."""
    suffix = metric_id.removeprefix("cprime.")
    if prompt_root is not None:
        return prompt_root / suffix
    from git_cg.eval.paths import REPO_ROOT

    return REPO_ROOT / DEFAULT_PROMPT_ROOT / suffix


def run_pinned_judge(
    metric_id: str,
    *,
    message: str,
    diff_summary: str | None = None,
    judge_model: str,
    judge_api_key: str,
    prompt_root: Path | None = None,
    max_input_chars: int = DEFAULT_MAX_INPUT_CHARS,
    judge_fn: JudgeFn | None = None,
) -> JudgeOutcome:
    """Run the pinned GEval judge for one ``cprime.*`` metric. Never raises.

    Resolution order (each failure degrades to a skip outcome):

    1. **Input guards** — empty/whitespace message → ``lane_c_empty_input``;
       oversize assembled input → ``lane_c_input_too_large``. No client built.
    2. **Pack resolution + text** — :func:`resolve_judge_pack` validates the
       pack identity and :func:`load_pack_prompt_text` reads the exact hashed
       bytes as the system prompt; any failure → ``lane_c_prompt_pack_unresolvable``.
    3. **Judge call** — via the injected (or default) ``judge_fn``; any
       exception → ``lane_c_judge_error``.
    4. **Parse/validate** — malformed or out-of-range score →
       ``lane_c_judge_parse_error``.
    """
    text = (message or "").strip()
    if not text:
        return JudgeOutcome(
            scored=False,
            metric_id=metric_id,
            reason=REASON_EMPTY_INPUT,
            evidence={"h.eval_input_nonempty": False},
        )

    user_prompt = _render_user_prompt(text, diff_summary)
    if len(user_prompt) > max_input_chars:
        return JudgeOutcome(
            scored=False,
            metric_id=metric_id,
            reason=REASON_INPUT_TOO_LARGE,
            evidence={"h.eval_input_size_ok": False, "input_chars": len(user_prompt)},
        )

    try:
        pack = resolve_judge_pack(metric_id, prompt_root=prompt_root)
        system_prompt = load_pack_prompt_text(_pack_dir_for(metric_id, prompt_root))
    except PromptPackError as exc:
        return JudgeOutcome(
            scored=False,
            metric_id=metric_id,
            reason=REASON_PACK_UNRESOLVABLE,
            evidence={"error": str(exc)},
        )

    content_hash = pack.get("content_sha256")
    fn = judge_fn if judge_fn is not None else openai_compatible_judge_fn
    try:
        raw = fn(system_prompt, user_prompt, judge_model, judge_api_key)
    except Exception as exc:  # judge failure must never propagate (F4)
        return JudgeOutcome(
            scored=False,
            metric_id=metric_id,
            reason=REASON_JUDGE_ERROR,
            pack=pack,
            evidence={"error_type": type(exc).__name__, "prompt_pack_sha256": content_hash},
        )

    try:
        score, rationale = _parse_judge_response(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        return JudgeOutcome(
            scored=False,
            metric_id=metric_id,
            reason=REASON_JUDGE_PARSE_ERROR,
            pack=pack,
            evidence={"error": str(exc), "prompt_pack_sha256": content_hash},
        )

    return JudgeOutcome(
        scored=True,
        metric_id=metric_id,
        score=score,
        rationale=rationale,
        pack=pack,
        evidence={
            "judge_model": judge_model,
            "prompt_pack_sha256": content_hash,
            "prompt_pack_id": pack.get("pack_id"),
        },
    )
