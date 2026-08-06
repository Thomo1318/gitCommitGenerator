# Slice 5.5 — Contract lifecycle observability + normaliser governance

## Status
**Implemented and committed** on `refactor/204-commit-presentation-quality` as gold-reworded series `c6afef5`…`6823958` (message-only rewrite; trees match pre-reword tip). Slice 5 remains complete and unregressed.

## Session 6 gold-miss analysis (authoritative home)
Full cross-cutting failure analysis (why raw `git-cg` missed gold on this series, F28–F35, R21–R25, TIP-G13–G17, V12-A39–A45, operator rejects, Opik briefing orthogonality) lives in **issue #204 body** as:

> 🧪 Incident evidence — Session 6 Slice 5.5 contract-lifecycle tip series (2026-08-06)

Do **not** treat this plan file as a second law surface. Link only; amend #204 if the analysis evolves.

## Slice 5 confirmation
- Low-confidence posture + `presentation_fallback_reason`
- `lift_plan_to_contract_semver` + `contract_lift_applied` / `contract_lift_from_semver`
- Wired after presentation seed/overlay, before scoped-history/gold/persist
- Exit: `tests/test_contract_lift.py` + `tests/test_commit_quality.py` green

## Slice 5.5 delivered

### Closed-vocab telemetry (`GenerationTelemetry`)
- `contract_locked_semver`
- `llm_raw_semver`
- `plan_persisted_semver`
- `contract_violation` (bool)
- `plan_normaliser_applied` (bool)
- `plan_normaliser_reason` ∈
  `none | contract_lift | presentation_clamp | matrix_reconstruction | malformed_semver | residual_violation`
- Retained Slice 5: `contract_lift_applied`, `contract_lift_from_semver`
- Coerce on write/read; legacy defaults; no free text

### Pure evaluator
- `evaluate_contract_lifecycle(...) -> ContractLifecycleSnapshot` in `regeneration.py`
- `contract_consistent_feedback_score(violation) -> 1.0|0.0` in `telemetry.py`

### Generation wiring (`main.py`)
- Capture `llm_raw_semver` **before** `enforce_semantic_contract`
- Capture locked SemVer from contract
- Mark `presentation_touched_semver` on seed/overlay
- Lift + **residual re-lift** before advisory merge/gold/persist
- Evaluate lifecycle → telemetry fields
- On `contract_violation`: Sentry companion event (errors-only)

### Opik
- Metadata: all lifecycle fields
- Feedback score: `contract_consistent` (1.0 consistent / 0.0 violation)
- Reason = closed `plan_normaliser_reason`

### Sentry
- `report_commit_plan_contract_violation` in `sentry_config.py`
- Fingerprint: `commit_plan_contract_violation`
- Tags only: locked/persisted SemVer, lift flags, normaliser reason, short hex `diff_hash`
- No prompts/diffs/bodies/blueprint/free text
- Scrub list extended for lifecycle locals

### Residual demotion investigation
| Path | Role | Verdict |
|---|---|---|
| Presentation seed/overlay SemVer clamp | Live plan demotion after enforce | **Root cause of incident**; fixed by Slice 5 lift + 5.5 residual re-lift |
| `CommitIntent` matrix validator | Rewrites SemVer/changelog **only on construct** | Not a post-lock assign demoter |
| `reverse_parse_commit_message` | Opik final-message partial plan (`_partial`) | Telemetry artifact only; not live plan authority |
| Gold regen loop | Re-runs enforce → presentation → lift | Covered by same guards each iteration |
| Secondary changelog allowlist/stubs | Presentation inventory may set `Tests`/`Miscellaneous` | Presentation-owned (D1/D19); not SemVer floor |
| Primary `cc_type`/changelog after overlay | Intentionally presentation-owned when overlay applied | Gold smoke skips these when `presentation_overlay_applied` |

**No additional silent SemVer normaliser found beyond presentation clamp.** Residual re-lift makes locked SemVer a hard floor through persist.

## Verification
```bash
uv run pytest tests/test_contract_lifecycle.py tests/test_contract_lift.py \
  tests/test_commit_quality.py tests/test_telemetry.py tests/test_sentry_config.py -q --tb=line
# 240 passed
uv run ruff check src/git_cg/telemetry.py src/git_cg/regeneration.py \
  src/git_cg/sentry_config.py src/git_cg/main.py tests/test_contract_lifecycle.py
# All checks passed
```

## Files
- `src/git_cg/telemetry.py`
- `src/git_cg/regeneration.py`
- `src/git_cg/sentry_config.py`
- `src/git_cg/main.py`
- `tests/test_contract_lifecycle.py` (new)
- `slice-5.5-contract-lifecycle.md` (this plan)

## Non-goals (honoured)
- No second ranker / matrix intent rewrite
- No raw prompt/diff/body logging
- No Slice 6/7 work
- No broad Sentry expansion
