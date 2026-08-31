# S7 claim → test matrix (Issue #254 / S7-8 packaging)

> **Issue:** [#254](https://github.com/Thomo1318/gitCommitGenerator/issues/254)
> **Parent:** [#217](https://github.com/Thomo1318/gitCommitGenerator/issues/217)
> **Portfolio epic:** [#216](https://github.com/Thomo1318/gitCommitGenerator/issues/216)
> **Docs deferral (S8):** [#235](https://github.com/Thomo1318/gitCommitGenerator/issues/235)
> **Branch package:** `src/git_cg/eval/**` + product-path lazy Opik init in `src/git_cg/main.py`
> **Plan SSOT (raw dogfood evidence):** `docs/plans/opik-evaluation-harness.md` @ `0.9.8-s7-dogfood-findings-board` §8.7.2
> **Authority:** issue **#254 body** wins S7 implementation detail; plan §8.7.2 wins raw FIND/S7-DOG rows
> **Status:** **S7-8 packaging** — every S7-A…G claim cites ≥1 offline evidence anchor; composition/CLI path required (not leaf helpers alone).
>
> **Proof spine (offline):**
>
> ```bash
> just eval-s7-proof
> # equivalent:
> uv run pytest tests/eval -o addopts="" \
>   --cov=src/git_cg/eval --cov-branch --cov-report=term-missing \
>   --cov-fail-under=80 -q
>
> just docstrings-patch
> ```

This page maps **S7-A…G claims → test module/node** for #254 close.
Each claim names at least one primary offline evidence anchor. Secondary nodes are optional cross-checks, not alternate law surfaces.

## Dual-axis law (all claims)

| Axis | Invariant |
|:---|:---|
| Product accept / commit path / ranking / Hybrid gate | Never blocked or flipped by human scores, cloud queue, doctor, export, or missing Opik |
| Eval / lab / operator interaction | May emit advisory rollups, pin warnings, masked notes, offline mirror no-ops, denial audits |

## S7-8 packaging checklist

| Deliverable | Owner | Status |
|:---|:---|:---|
| Every S7-A…G row names ≥1 real test module/node | S7-0…S7-7 + S7-8 packaging | **Yes** (tables below) |
| `just eval-s7-proof` package-scoped cov floor (AC-13) | `justfile` `eval-s7-proof` | **landed** |
| Docstring patch gate | `just docstrings-patch` | **landed** |
| FIND-069/070/071/073 regression nodes | S7-7 | **landed** |
| FIND-072 label-only decision recorded (not coded fail-closed) | `promote.py` `REDACTION_PROFILES` comment | **landed** |
| No S8 docs-platform surface under S7 | `tests/eval/test_no_docs_platform_surface.py` + this file | **landed** |
| PR links #254 + `Refs: #217`; closes only #254 | PR-time | **PR-time** |

## Composition / CLI spine

```text
four-lane pin doctor (offline)
  → Tier-1 FD map + drift guard
  → review enqueue → claim → adjudicate(approve_promote|reject|needs_work) / dismiss
  → advisory rollup (authority=advisory)
  → promote guards (DENY_HUMAN_SOLE_GOLD + unresolved dispute)
  → optional queue_mirror (write-only; offline no-op; never read back)
  → secret scrub on promote/review free text (incl. short-segment JWT)
  → product path: lazy Opik init only when mode≠off
```

## Claims S7-A…G

### S7-A — Four-lane Opik pins (offline)

| ID | Summary | Primary evidence | Status |
|:---|:---|:---|:---|
| **S7-A** | Four-lane pins resolve secret-safely offline (local shape + lane completeness); missing/unresolvable pin → warning not product fail; remote existence / optional create non-authoritative | `tests/eval/mirror/test_config.py` (lane pin resolution / secret-safe config); `tests/eval/test_eval_opik_doctor.py` (offline doctor layers, no raw tokens) | landed |

### S7-B — Feedback Definition vocabulary

| ID | Summary | Primary evidence | Status |
|:---|:---|:---|:---|
| **S7-B** | FD map matches emitted product + `human.*` vocabulary 1:1; drift-guard fails on divergence | `tests/eval/test_feedback_definitions.py::test_map_matches_emitted_vocabulary`; `tests/eval/test_schemas.py` (schema-pack membership) | landed |
| **S7-B** (notes) | `human.notes_present` is derived metadata — **never** a minted FD | `tests/eval/test_feedback_definitions.py::test_notes_present_not_a_minted_fd` | landed |
| **S7-B** (provenance) | `final_accept` is artifact/provenance enum, not a review score | `tests/eval/test_feedback_definitions.py::test_final_accept_not_a_review_score` | landed |

### S7-C — Review lifecycle HITL bind

| ID | Summary | Primary evidence | Status |
|:---|:---|:---|:---|
| **S7-C** | Landed lifecycle `enqueue`/`claim`/`adjudicate`/`dismiss` persists atomic Layer-A rows; `approve_promote` is the human leg | `tests/eval/test_review_queue.py` lifecycle + contention/atomic suites; `tests/eval/test_eval_cli_replay_promote.py::test_cli_human_leg_approve_promote_composition` | landed |
| **S7-C** (composition) | Full HITL composition reaches promote with human leg bound | `tests/eval/test_promote.py::test_hitl_enqueue_claim_adjudicate_rollup_promote_denied`; `tests/eval/test_eval_cli_replay_promote.py::test_cli_human_leg_approve_promote_composition` | landed |

### S7-D — Advisory rollup / no sole-promote

| ID | Summary | Primary evidence | Status |
|:---|:---|:---|:---|
| **S7-D** | Human `approve_promote` cannot sole-promote golden (guards landed; S7 wires advisory rollup only) | `tests/eval/test_promote.py::test_deny_human_sole_gold_with_review`; `::test_majority_approve_promote_rollup_cannot_sole_promote_gold`; `::test_hitl_enqueue_claim_adjudicate_rollup_promote_denied` | landed |
| **S7-D** (dispute) | Rollup evidence cannot bypass unresolved-dispute deny | `tests/eval/test_promote.py::test_human_rollup_never_overrides_unresolved_dispute_guard` | landed |

### S7-E — Optional cloud queue mirror (non-SoT)

| ID | Summary | Primary evidence | Status |
|:---|:---|:---|:---|
| **S7-E** | Mirror is offline no-op and never read back; write-only by construction; live projection optional | `tests/eval/mirror/test_queue_mirror.py::test_mirror_offline_noop`; `::test_mirror_never_read_back`; `::test_queue_mirror_is_write_only_by_construction` | landed |

### S7-F — Docs boundary (no S8 swim)

| ID | Summary | Primary evidence | Status |
|:---|:---|:---|:---|
| **S7-F** | No S8 docs-platform / autodoc / REST surface shipped under S7 | `tests/eval/test_no_docs_platform_surface.py::test_branch_diff_excludes_docs_platform_surface`; `::test_no_s8_docs_scope` | landed |
| **S7-F** (scope note) | Durable ADR-0011 / Zensical / mkdocstrings remain **#235 (S8)**; this file is interaction/claim packaging only | this document + issue #254 non-goals | landed (docs) |

### S7-G — Secret scrub (FIND-069 / FIND-073)

| ID | Summary | Primary evidence | Status |
|:---|:---|:---|:---|
| **S7-G** | Promote notes + review free text scrub secret-shaped tokens incl. short-segment JWTs | `tests/eval/test_evidence_scrub.py::test_short_segment_jwt_masked`; `::test_jwt_quantifier_pin_and_no_trailing_word_boundary`; `::test_secret_patterns_are_masked`; `tests/eval/test_review_queue.py::test_bearer_jwt_short_segment_is_masked` | landed |
| **S7-G** (mask-to-empty) | Mask-to-empty **never** falls back to raw operator text | `tests/eval/test_promote.py::test_notes_masked_no_raw_fallback`; `::test_promote_notes_mask_to_empty_never_restores_raw`; `tests/eval/test_evidence_scrub.py::test_mask_to_empty_never_restores_raw`; `::test_notes_masked_no_raw_fallback` | landed |
| **S7-G** (dry-run emit) | Dry-run promote decisions mask notes before emit (no persist required) | `tests/eval/test_promote.py::test_promote_notes_masked_on_dry_run_stdout_path`; `::test_promote_notes_mask_secrets_before_persist` | landed |
| **S7-G** (false positives) | Ordinary dotted text / short non-token `eyJ` shapes are not masked | `tests/eval/test_evidence_scrub.py::test_jwt_false_positive_suite_not_masked` | landed |

## FIND disposition anchors (S7-owned)

| FIND | Class | Evidence anchor | Status |
|:---|:---|:---|:---|
| **FIND-069** | secret-safety | promote notes mask-before-persist/emit + mask-to-empty | landed |
| **FIND-070** | contract/UX | promote trace_id precedence + precondition errors (existing promote tests) | landed |
| **FIND-071** | contract/UX | `ape_bundle_v1` top-level `id` rejection copy (existing promote schema tests) | landed |
| **FIND-072** | design-open → **recorded** | `src/git_cg/eval/promote.py` `REDACTION_PROFILES` comment: label-only promote semantics; export remains fail-closed on `raw_dev_unsafe` | recorded (no behaviour change) |
| **FIND-073** | secret-scrub | JWT header`{5,}` / payload`{1,}` / sig`{5,}`; lookaround anchors; no trailing `\b` | landed |
| **FIND-068** | product isolation (I10) | `tests/test_main_opik_lazy_init.py` AST + mode-off import/stderr isolation | landed |
| **FIND-047** | amend-brief UX | `amend-brief --case` CLI wiring (S7-7) | landed |
| **FIND-060/061** | export-queue honesty | stable zero counts + retry not-found plain copy (S7-7) | landed |
| **FIND-062/064** | operator UX | config-show plain summary + checkpoint list (S7-6) | landed |

## S8 boundary (hard non-goal)

S7 covers interaction and claim packaging only. The following stay under **#235 (S8)** and must not appear as implementation in the S7 branch diff:

* ADR-0011 full eval-layer rewrite prose
* Durable Zensical API pages
* Allowlist `mkdocstrings` / broad autodoc program
* REST/OpenAPI operator SDK surfaces
* Live Opik Cloud as a required CI merge gate (S8-LAW-01)

Structural guard: `tests/eval/test_no_docs_platform_surface.py::test_no_s8_docs_scope`.

## PR paste pack (maintainer)

```text
S7 close evidence: docs/eval/s7-claim-evidence.md
Proof: just eval-s7-proof && just docstrings-patch
Claims: S7-A…G each name offline test nodes (composition-aware)
Authority: local review_queue SoT; human advisory; Lane A sole accept/CI/golden SoT
Secrets: FIND-069/073 scrub + mask-to-empty; FIND-072 label-only recorded
Docs: no S8 platform surface (#235)

Refs: #217
SemVer-Impact: MINOR
Change-Types: feat, test, docs, security
Changelog-Groups: Added, Changed, Security
```

Close **#254 only**. Never use closing keywords for #217 / #216 / #235.
