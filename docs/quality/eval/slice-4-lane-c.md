# Slice 4 — S5c pinned GEval seam

Issue #233 contracts: `C-ADV`, `C-JUDGE`, `C-RUN`, `C-SEC`.

## Goal

Land advisory GEval emission + injectable pinned judge + gated `run_lane_c` wiring without changing default offline Plane A behaviour.

## Files

- `src/git_cg/eval/lane_c/advisory.py` — `make_advisory_score` + rationale scrub
- `src/git_cg/eval/lane_c/judge.py` — `JudgeOutcome`, credentials, injectable transport
- `src/git_cg/eval/lane_c/runner.py` — invoke judge only when input + judge_fn supplied
- `src/git_cg/eval/lane_c/__init__.py` — keep `run_lane_c` as supported API
- `src/git_cg/eval/scoring/runner.py` — isolated optional Lane C family block
- `tests/eval/test_lane_c_advisory_score.py`
- `tests/eval/test_lane_c_judge.py`
- `tests/eval/test_lane_c.py` — scored/skip wiring + promo immunity

## Invariants

- `passed is None` for all C′ numeric rows (never use `make_score` derivation)
- success `reason="scored"`; rationale only in `evidence["rationale"]` ≤800 scrubbed
- `evidence["scale"]="geval_1_5"`
- no `api_key` on runner/test-facing judge callable
- `GIT_CG_EVAL_JUDGE_API_KEY` via `resolve_secret`; model env is identity only
- provider SDK lazy-imported inside transport invocation only
- timeout 15s; max retries 1; never retry empty/oversize
- parse/transport failures become closed taxonomy skips
- default `score_bundle` stays offline / no network / no C′ unless opted in
- poisoned C′ `passed=True` cannot veto det or golden promotion

## Exit

Focused advisory + judge + lane_c + score-runner tests green offline.
