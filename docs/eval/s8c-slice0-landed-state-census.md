# S8c Slice 0 — landed-state census + policy lock (#258)

> **Issue:** [#258](https://github.com/Thomo1318/gitCommitGenerator/issues/258) · umbrella [#235](https://github.com/Thomo1318/gitCommitGenerator/issues/235) (migration table read, status only)
> **Branch:** `eval/258-8c-s4-mirror-export-residuals` @ `edb55be201dced99740b6092849f5660d1814bff` (= `origin/main`, `v0.25.0`, post-S8b PR #263)
> **Slice:** S8-S4-00 — required entry gate. Documentation / census / policy lock only. **No product code.**
> **Machine baseline:** [`s8c-slice0-baseline.json`](./s8c-slice0-baseline.json)
> **Format precedent:** [`s6-slice0-landed-state-census.md`](./s6-slice0-landed-state-census.md) (#246)

Every claim below was verified against the live tree at `edb55be` on 2026-09-11. The stale 2026-09-01 census comment pinned at `e32a75b` was **not** used as evidence. Line numbers are at the pinned base.

**Umbrella status (read-only):** #235's migration table lists S8c/#258 as *Planned* with a residual inventory matching this issue's scope (packer perf, `size_bytes` convergence, flush Option A, train profile fail-closed, optional CLI/test hygiene, E6 rejection upheld). The S8b row still shows PR #263 *open* @ `ae2bbce` — stale relative to the merged `v0.25.0` base this census pins. Status observation only; updating the umbrella is not S8c scope.

## 1. Policy lock (laws preserved — not reopened in S8c)

| Law | Status | Evidence (at `edb55be`) |
|:---|:---|:---|
| `_build_batch()` is the sole exact size / schema-validation authority | Confirmed | `batch.py:115`; every packing path routes through it — singleton pre-validation, candidate probe, flush |
| 4 MiB default ceiling | Confirmed | `DEFAULT_MAX_BATCH_BYTES = 4 * 1024 * 1024` (`batch.py:42`) |
| Any positive `max_bytes`; no downward-only rule | Confirmed | `batch.py:233` `raise ValueError("max_bytes must be >= 1")`; nothing restricts raising |
| Sanitizer runs before packing | Confirmed | `sanitize_export_tree` at `batch.py:268` (pre-validation loop) and inside `_build_batch` (`batch.py:140`, `:201`) |
| F4 fail-open — `product_accept_blocked` always `False` | Confirmed | `result.py:63`, `:69`, `:88`, `:197`, `:219` |
| E6 — `user_acceptance` never a correctness / promotion signal | Confirmed | `scripts/compile_opik_dataset.py:75` `selection_predicate`; forbidden-signal guards `:94–96`; tests in `tests/eval/mirror/test_compile_opik_dataset_absorption.py` |
| S8b sanitizer + `RAW_DEV_UNSAFE` export guard | Confirmed present | `redaction.py:250` `sanitize_export_tree`; `redaction.py:453` rejects `RAW_DEV_UNSAFE` on export |
| Intentional PEP 758 `except A, B:` forms | Confirmed valid | `experiments.py:74`, `queue.py:196`, `payload.py:129`; AST-parsed OK under Python 3.14.7 — do not rewrite |
| Lazy Opik import isolation (E5) | Confirmed | `transport.py:218` — sole allowed lazy import site, pinned by path:enclosing_function |
| Opik SDK pin | Confirmed | `opik==2.0.52` (`uv.lock:1718–1720`) |
| Canonical CLI surface | Confirmed | `git-cg eval opik config show` (landed); `export_timeout` present — do not drop |

## 2. Consumed-surface census (verified at `edb55be`)

### 2.1 Batch packer (`src/git_cg/eval/mirror/batch.py`)

| Census item | Finding | Evidence |
|:---|:---|:---|
| `build_export_batches()` rebuilds via `_build_batch()` | Confirmed | `batch.py:205`; `try_batch()` wraps `_build_batch()` and is called for every singleton pre-validation, every growth candidate, and every flush — rebuild-per-candidate, no size cache |
| `ENVELOPE_HEADROOM_BYTES` unused / reserved | Confirmed | `batch.py:45` (`256 * 1024`), exported in `__all__` (`:31`); zero call sites in `src/` |
| Stale "configurable downward" wording | Confirmed | `batch.py:13` ("Default 4 MB; configurable downward.") and `:41` ("configurable downward only") — law is `max_bytes >= 1`, not the comment; correct in S8-S4-02/S8-S4-03 docs pass |
| `payload_size_bytes` unaffected by D-8 | Confirmed — record, do not audit further | `batch.py:182` `len(canonical_json_bytes(transport_body))` measures the transport body **before** the field exists inside it — no self-reference. Guard recorded: future magnitude sweep asserts `payload_size_bytes <= size_bytes` per emitted batch |
| `batch_idempotency_key()` excludes `size_bytes` | Confirmed | `batch.py:77–107` |
| `envelope_size_bytes()` | Confirmed | `batch.py:110` |

### 2.2 Transport / flush (`src/git_cg/eval/mirror/transport.py`)

| Census item | Finding | Evidence |
|:---|:---|:---|
| `_bounded_flush` is cooperative / synchronous | Confirmed | `transport.py:397–430`; post-call monotonic deadline; `flush()` itself is blocking — Python cannot forcibly interrupt it |
| Pre-amendment predicate (D-2 before-state) | Confirmed | `transport.py:426` `if ok is False:` — the adopted amendment changes this to `is not True` in S8-S4-03 |
| Timeout / overrun / non-`True` result classification | Confirmed | `export_network` class; never false transport success |
| `docs/eval/README.md` already honest | Confirmed | `README.md:533` "Installed SDK flush uses whole seconds; config remains `flush_timeout_ms` and is converted with ceiling + outer deadline." — preserve, do not regress |
| Queue-projector flush is a **separate** path | Registered, out of S8c scope | `queue_projector.py:259–264`: best-effort `flush(timeout=2)`, return ignored, `except Exception: pass` — F4 fail-open advisory (non-SoT) path, not `_bounded_flush`; named follow-up (RK-S8c-12), do not fold into S8-S4-03 |

### 2.3 Train projection (`src/git_cg/eval/mirror/train.py`)

| Census item | Finding | Evidence |
|:---|:---|:---|
| Unlabeled / unknown rows return `None` | Confirmed | `train.py:57`, `:60`, `:75`, `:94` |
| Labeled rows can emit `redaction_profile=None` | Confirmed (the D-3 defect) | `train.py:116` `"redaction_profile": str(profile) if profile is not None else None` |
| `filter_positive_gold` does not validate profile | Confirmed | `train.py:133–151` — label check + sanitize only |
| `build_train_projection` exposes `excluded_unlabeled` only | Confirmed | `train.py:191`; no `excluded_profile` key exists anywhere yet |
| Composition wraps train projection in broad `except Exception` | Confirmed | `composition.py:419` `except Exception as exc:  # train projection must not kill export plan` |
| Sanitizer import present in train path | Confirmed | `train.py:24`; call sites `:129`, `:150`, `:196` |
| `build_export_plan` redacts before projection | Confirmed | `composition.py:304` (redact) → `:415` (project) → `:416` (sanitize) |

### 2.4 Train-export consumers (`src/git_cg/eval/train_export.py`)

| Consumer | Site | Current behaviour |
|:---|:---|:---|
| `project_train_row` | `:190–192` | Per-row projection; `split_group_id` read at `:209` via `proj.get("split_group_id") or proj.get("split")` |
| `build_train_projection` | `:324` | Summary exposes `excluded_unlabeled` only (`:395`, `:486`) — no `excluded_profile` tolerance yet (F-R10 audit lands in S8-S4-04) |
| `filter_positive_gold` | `:325` | Consumes projection rows; no profile validation |

## 3. Baselines (recorded 2026-09-11 at `edb55be`)

| Baseline | Result |
|:---|:---|
| `uv run pytest tests/eval/mirror -q --tb=short` | **396 passed / 0 failures** (37.23s this run; issue records ~36.6s on 2026-09-10 — both green; timing is not AC) |
| Branch coverage, owned modules (`-o addopts=''`, `--cov-branch`) | batch **95%** / train **96%** / transport **97%** / composition **94%** / combined **96%** (591 stmts, 202 branches) |
| Public docstrings, mirror package | `tools/check_docstring_coverage.py src/git_cg/eval/mirror --threshold 80` → **125/125 = 100%** (matches the issue's AC-10 claim exactly; the tool's public-only count is authoritative) |
| Historical flake | `test_secret_failure_claim_mark_guards` combined-run flake no longer reproduces — retired as census evidence; the stale "136 passed + flake" pre-review claim is not reused |

## 4. D-1 packer rebuild cost — measured evidence + owner judgment

Measured 2026-09-10 at `edb55be` against public `build_export_batches()` with `DEFAULT_SCRUB` payloads, wall-clock, single batch per row (ad-hoc review probe; reproducibility recipe in issue #258 D-1; evidence only — **not** an acceptance criterion):

| Items | Payload | Wall time |
|---:|---:|---:|
| 50 | 102 KiB | 53 ms |
| 100 | 203 KiB | 148 ms |
| 200 | 404 KiB | 516 ms |
| 400 | 808 KiB | 1,885 ms |

~4× per doubling → quadratic remeasure cost within a single batch; extrapolated ~45–50 s for one 4 MiB batch. Interaction note: the S8-S4-02 convergence loop adds remeasures only at digit boundaries (zero in the common case), so it does not materially change this baseline.

**Owner judgment (recorded at census, 2026-09-11): DEFER S8-S4-01 with notes.**

1. The measured cost is a performance characteristic, not a correctness defect — no AC is violated today.
2. Routine eval mirror batches sit well below the 4 MiB ceiling; the 400-item / 808 KiB / 1.9 s probe is above routine export volume.
3. Any optimisation must prove byte-identical equivalence against `_build_batch()` exact authority; the equivalence-proof burden adds risk to the packing law for a non-correctness gain.
4. Defer is lawful (D-1: "deferred-with-notes" satisfies the slice). The 2026-09-10 measurement is recorded either way, so the defer precondition ("defer unless measured") is discharged.

**Re-open triggers:** observed real-workflow batch builds that hurt operator flows (e.g. routine batches exceeding ~5 s wall time), or a ceiling-raise demand that makes quadratic cost binding. If re-opened, S8-S4-01 proceeds only under its design-first gate with byte-identical equivalence proof.

## 5. D-8 `size_bytes` digit-width escape — reproduced evidence (final)

Reproduced 2026-09-10 via the **public** `build_export_batches()` path at ~9,999 / ~99,999 / ~999,999 byte boundaries. Stored `size_bytes` vs `envelope_size_bytes()` differ by the width delta at each boundary:

| Boundary | Stored `size_bytes` | Actual `envelope_size_bytes()` |
|---:|---:|---:|
| ~9,999 | 10002 | 10003 |
| ~99,999 | 100003 | 100004 |
| ~999,999 | 1000004 | 1000005 |

These are representative evidence of the defect class, **not** future test constants. This census item is final and not subject to re-litigation: S8-S4-02 is promoted to required on this evidence and links to the D-8 normative fix (bounded convergence loop, named `MAX_SIZE_CONVERGENCE_PASSES`, fail-closed `else`, post-write ceiling check, invariant `batch["size_bytes"] == envelope_size_bytes(batch)`). Not implemented in this slice.

## 6. Flush overclaim inventory (input to S8-S4-03)

| Site | Current wording | Disposition |
|:---|:---|:---|
| `transport.py:23` (module docstring) | "cannot hang on exit" | Correct in S8-S4-03 (cooperative / blocking honesty) |
| `transport.py:199` (class docstring) | "cannot hang on exit (FIND-022 / P0-4)" | Correct in S8-S4-03 |
| `docs/plans/opik-evaluation-harness.md:2000` | "`flush_timeout_ms: int` # hard bound for short-lived procs" | Correct in S8-S4-03 (cooperative, not a hard bound) |
| `src/git_cg/eval/mirror/config.py:100` | "Default bounded flush for short-lived hook processes" | Correct in S8-S4-03 |
| `src/git_cg/eval/mirror/exporter.py:1` | "FIND-022 bounded flush" | Correct in S8-S4-03 |
| `docs/plans/opik-evaluation-harness.md:2519` | "default max batch payload 4MB (configurable downward; raise only with explicit owner note)" | Correct when touching this docs surface (D-6 / F-R11) — both phrases overclaim |
| `docs/plans/opik-evaluation-harness.md:1206` | `h.flush_bounded` metric row: "flush used explicit timeout on short-lived procs" | **Census verification note only** — verified present; no rewrite (F-R11) |
| `docs/plans/opik-evaluation-harness.md:2510`, `:3170`, `:3804` | v0.9.0 addendum "bounded flush" / §10.6 heading / FIND-022 index row | Historical / addendum references — qualify without deleting historical context |
| `docs/eval/README.md:533` | Already honest | Preserve; do not regress |

## 7. Schema / profile census (F-R12 — record, no defect claimed)

| Surface | Finding | Evidence |
|:---|:---|:---|
| `RedactionProfile` enum | 8 tokens | `enums.py:88–98`: `public_ci`, `default_scrub`, `private_message`, `train_rich`, `antipattern_vault`, `message_only`, `meta_eval_scrub`, `raw_dev_unsafe` |
| `train_row_v1.schema.json` | 8-token enum in `$defs.redaction_profile`; property-level `allOf` + `not: {const: raw_dev_unsafe}` exclusion | schema `:103–113` (`$defs`), `:173–181` (property) |
| Shared export validator | Rejects `RAW_DEV_UNSAFE` | `redaction.py:453` |
| Effective export vocabulary | 7 tokens — `RedactionProfile` minus `RAW_DEV_UNSAFE` | Enum, schema, and validator **currently agree** |
| Differing failure modes (intentional) | Train-export schema validation **drops/raises** on invalid profiles; mirror train projection will **skip/count** (`excluded_profile`) | Different boundaries, both fail-closed — by design, not a defect |

Any future enum / schema / validator drift must be re-checked; the D-3 vocabulary-drift guard test covers the Python side.

## 8. Sanitize-redundancy census (record — do not refactor)

The train path sanitizes up to three times today: `project_train_row` per row (`train.py:129`), `filter_positive_gold` per positive row (`:150`), and `build_train_projection` over the whole projection (`:196`). `sanitize_export_tree` is structurally idempotent (drops exact forbidden keys, copies, never rewrites string values) and size-neutral, so the redundancy is belt-and-braces, not a defect. **Do not** remove any sanitize call site (S8b law); **do not** add a fourth pass in the new profile-validation code. `filter_positive_gold`'s internal sanitize stays mandatory — it may be handed malformed direct input (D-3 refusal path).

## 9. Coverage census

| Item | Finding | Evidence |
|:---|:---|:---|
| `just eval-per-file-coverage` excludes mirror modules | Confirmed | `justfile:175+` lists `review_queue`, `promote`, `evidence_scrub`, `feedback_definitions`, `checkpoint_store`, `run_orchestrator` — no `mirror/*` |
| `just eval-package-coverage` is a broader eval floor, not S8c-specific | Confirmed | `justfile:162` (`--cov=src/git_cg/eval`, fail-under 80) |
| Owned-module branch floors at `edb55be` | batch 95 / train 96 / transport 97 / composition 94 / combined ~96 | Measured 2026-09-11 (§3) — AC-10 is a **maintain** gate, not an achieve gate |
| Mirror public docstrings | 125/125 = 100% | `tools/check_docstring_coverage.py` (§3) — maintain ≥80 |
| Graph test links | Unreliable — inspect tests by source | Census verified tests by direct source reads |

## 10. Scope freeze / non-goals (S8c)

**In scope:** S8-S4-00 (this census) → S8-S4-02 (`size_bytes` convergence, required) → S8-S4-03 (flush docs honesty + D-2 predicate, required) → S8-S4-04 (train projection fail-closed, required). S8-S4-01 deferred (§4). S8-S4-05 / S8-S4-06 are optional NTH, not close-bar.

**Non-goals (frozen):**

* No S8a / S8b / S8d–S8f or S10/#240 work; no Sentry flush audit (#235, F-R19)
* No flush preemption (Option B); no `_bounded_flush` change beyond the adopted D-2 predicate tightening
* No E6 weakening; no F4 authority changes
* No sanitizer / redaction reimplementation; no sanitize call-site removal
* No invented `redaction_profile`; no `applied_redaction_profile` fallback / default profile
* No downward-only `max_bytes` validation; no mandatory `ENVELOPE_HEADROOM_BYTES` wiring
* No PEP 758 rewrites
* No broad CLI / test / style cleanup; no new CLI surface; no `export_timeout` removal
* No new test/runtime dependencies (e.g. `hypothesis`, `mutmut`)
* No timing benchmarks as acceptance (AC-9)
* No manual `CHANGELOG.md` edit (release automation only, F-R18)
* No queue-projector flush change (RK-S8c-12 — named follow-up, out of scope)
* No issue-body / umbrella mutation in this slice

## 11. Exit criteria (S8-S4-00)

| Criterion | Status |
|:---|:---|
| Census recorded locally | Done — this file + [`s8c-slice0-baseline.json`](./s8c-slice0-baseline.json) |
| Baselines captured | Done — §3 (396 passed / 0 failures; coverage floors; docstrings 125/125) |
| Scope frozen | Done — §10 |
| No product code changed | Confirmed — docs-only diff |
| S8-S4-04 may start | **Yes** (S8-S4-02 / S8-S4-03 may proceed in parallel per slice order; S8-S4-01 deferred with notes per §4) |

## 12. Verification commands (re-runnable)

```bash
# baseline floor
uv run pytest tests/eval/mirror -q --tb=short

# owned-module branch coverage (maintain ≥80 each)
uv run pytest tests/eval/mirror -o addopts="" \
  --cov=git_cg.eval.mirror.batch \
  --cov=git_cg.eval.mirror.train \
  --cov=git_cg.eval.mirror.transport \
  --cov=git_cg.eval.mirror.composition \
  --cov-branch -q

# public docstring floor (maintain ≥80)
uv run python tools/check_docstring_coverage.py src/git_cg/eval/mirror --threshold 80

# consumed-surface spot checks
rg -n 'def build_export_batches|def _build_batch|def envelope_size_bytes|ENVELOPE_HEADROOM_BYTES' src/git_cg/eval/mirror/batch.py
rg -n 'def _bounded_flush|if ok is False' src/git_cg/eval/mirror/transport.py
rg -n 'except Exception as exc:  # train projection' src/git_cg/eval/mirror/composition.py
rg -n 'except OSError, ' src/git_cg/eval/mirror/experiments.py src/git_cg/eval/mirror/queue.py src/git_cg/eval/mirror/payload.py
```
