# S6 Slice 0 — landed-state census + policy lock (#246)

> **Issue:** [#246](https://github.com/Thomo1318/gitCommitGenerator/issues/246)
> **Parent design:** [#217](https://github.com/Thomo1318/gitCommitGenerator/issues/217) · portfolio epic [#216](https://github.com/Thomo1318/gitCommitGenerator/issues/216)
> **Branch:** `evals/246-s6-eval-cli-doctor-amend-brief-dogfood-train-export-sessions` @ `86fed7ebdb4a`
> **Contract base:** post-S5 `main` / tip (`v0.21.0` lineage) @ `86fed7ebdb4a`
> **Plan SSOT:** [`docs/plans/opik-evaluation-harness.md`](../plans/opik-evaluation-harness.md) @ `0.9.6-s6-slice0-reconciliation`
> **Machine baseline:** [`s6-slice0-baseline.json`](./s6-slice0-baseline.json)
> **Slice class:** documentation / census / naming lock only — **no** runtime S6 writers, schema re-freeze, or new CLI commands in this slice.

## 1. Policy lock (architecture un-reopened)

| Lock | Status | Evidence |
|:---|:---|:---|
| D1–D31 + I1–I12 still match plan `0.9.5` + closed S4/S5 shapes | **Confirmed** | Plan header/version retained as prior lock; S6 amends only named drift surfaces below. No ranking/SOP/Hybrid authority move. |
| Package home remains `src/git_cg/eval/` | **Confirmed** | CLI at `src/git_cg/eval/cli.py` → `eval_app`. No operator wiring into `src/git_cg/main.py` ranking. |
| `git_cg.eval.__init__.__all__` stays S0 contract floor | **Confirmed** | Exports only enums, `ScoreResultV1`, catalog/pin helpers. **No silent public expansion in Slice 0** (D5). |
| Offline baseline green | **Confirmed** | `uv run pytest tests/eval -q` → **1105 passed** (see baseline JSON). |
| Disk-pressure local runs | **Allowed** | Maintainers may disable coverage/cache providers locally; CI still proves the full required matrix. |

## 2. Path-helper split (D31) — decided

| Module | Lines (tip) | Owns | S6 rule |
|:---|---:|:---|:---|
| `src/git_cg/eval/paths.py` | 28 | Static asset discovery only: `SCHEMA_DIR`, `CATALOG_PATH`, `schema_files()` | **Do not extend** for runtime stores. |
| `src/git_cg/eval/binding/paths.py` | 243 | Layer-A runtime law: `eval_tree_root`, `sessions_dir`, `atomic_write_json` (`os.replace`), containment/symlink-escape defense, `0600`/`0700` | **All S6 store paths extend here only** (`checkpoints`, `review_queue`, `dogfood`, `amend_briefs`, `diagnostics`, `issues`, `replays`, `index`, `train_export`, `antipattern_vault`, …). |

Recorded for Slice 2 API map/docs so agents cannot extend the wrong module.

## 3. Landed surfaces S6 must consume (extend vs build-new)

### 3.1 Consume / extend (do not rebuild)

| Surface | Landed home | S6 relationship |
|:---|:---|:---|
| Deterministic score APIs | `scoring/runner.py` (`score_bundle` / `score_case` / `score_suite`), `scoring/gates.py` (`compose_gates`), `score_result.py` (`ScoreResultV1`) | `eval run` / resume / recompute **wrap** these — no second scorer. |
| Catalog / schema pins | `pins.py`, `schema_pack.py`, `catalog.py`, `paths.py` | Doctor + compat hash preimage consumers. |
| S3 final-accept binding | `binding/binder.py`, `binding/accept_hook.py` | Read/explain/promote consumers only. |
| S3 trajectory evidence | `binding/trajectory.py` | Explain/blame/replay evidence. |
| S3 session twins | `binding/session_thread.py` (`build_session_twin`, `write_session_twin`) | S6 adds **`session show` / `thread show` read/map only** — not a chat timeline or graph browser. |
| S3 message versions | `binding/message_versions.py` | Amend-brief preference pairs when versions ≥ 2. |
| S4 Opik config + secret mask | `mirror/config.py` (`resolve_opik_config`, `mask_secret`) | `eval opik config show` / `opik doctor` secret-safe surfaces. |
| S4 export queue / drain | `mirror/queue.py`, `mirror/exporter.py`, `mirror/exporter.py`, `cli.py` export group | Nested `eval export status\|retry\|drain` already landed; S6 keeps nested canonical. |
| S4 redaction / train projection | `mirror/redaction.py`, `mirror/train.py` (`build_train_projection`) | `train-export` CLI consumes; no R14 rebuild. |
| S4 experiments | `mirror/experiments.py` | Run/resume provenance; optional additive fields only. |
| S5 Lane C′ | `lane_c/runner.py` (`run_lane_c`), eligibility/availability/judge_input/prompt_pack/meta_eval | Dogfood + amend attachments consume; authority stays advisory. |

### 3.2 Build new in later S6 slices (not Slice 0)

| Surface | First implementing slice | Notes |
|:---|:---|:---|
| Greenfield schema re-freeze + `cli_output_envelope_v1` | Slice 1 | See schema census. |
| Operator command skeleton + `api_map.py` + envelope sketches | Slice 2 | Path lock below. |
| Checkpoints / resume / `eval run` orchestration | Slice 3 | Recovery law locked in plan §7.5. |
| `eval doctor` + `eval opik doctor` metric producers | Slice 4 | Closes phantom `h.compat_hash_resume` / `h.doctor_green` / `h.export_config_resolved`. |
| failures/explain/compare/diagnose/issues | Slice 5 | Deterministic; no Ollie. |
| replay/promote/review queue | Slice 6 | New bundle only; human advisory. |
| amend-brief / dogfood / sessions / train-export UX | Slice 7 | S6-G02 two-part async law. |
| Script absorption execution | Slice 8 | Decisions recorded here. |
| Docs/CI/claim matrix close-out | Slice 9 | |

## 4. Schema census (Slice 1 input)

Live pack: **26** non-underscore schemas under `schemas/eval/` (plus `_enums.schema.json` helper).
Live pins at census time:

* `schema_pack_v0@7b4eaf312d2255b1dbfeca095a6fb716e5d30f3a3b3ad8648f6a8c705a070539`
> **Slice 1 note (post-re-freeze):** live schema pack pin is now `schema_pack_v0@a5ca2c6bc580aa929084a9abcd9abd66a7cb426050bee38bfe73baf99aa47a7e` after greenfield re-freeze of six S6 schemas, additive live-writer extensions, and new `cli_output_envelope_v1`. The Slice 0 pin above remains the historical landed-state census value and must not be rewritten.

* `metric_catalog_v0@430a62c1d7971e1145cfffd41e608a5f6bd39d284a3d050f991b8537f817eb75`

| Schema | Live shape (tip) | S6 classification | Slice 1 action |
|:---|:---|:---|:---|
| `evaluation_checkpoint_v1` | required `id`+`compat_hash`; untyped `meta`; missing full resume contract | **Greenfield re-freeze** | Required checkpoint identity/experiment ref/`compat_hash`/progress/timestamps; closed mode includes all **five** resume modes; forbid `compatibility_hash` alias |
| `amend_brief_v1` | minimal stub (`brief_id`); untyped `meta` | **Greenfield re-freeze** | R11 L1 rollup contract + optional attachments |
| `diag_issue_v1` | `id`/`fingerprint`/`code`; untyped `meta` | **Greenfield re-freeze** | status machine + typed diagnostic fields |
| `replay_compare_v1` | `source_id`/`replay_id`; untyped `meta` | **Greenfield re-freeze** | lineage + regression_status enum |
| `human_review_v1` | top-level `rating` + `reviewer`; untyped `meta` | **Greenfield re-freeze** | migrate to typed `scores` map (no dual-shape window) |
| `dogfood_attachment_v1` | `mode`/`score` stub; untyped `meta` | **Greenfield re-freeze** | R12 attachment contract; `authority=advisory` |
| `cli_output_envelope_v1` | frozen `{schema_version, command, ok, data, errors[], warnings[], meta?}` with closed message items + enumerated meta | **New (S6)** | Schema frozen in Slice 1; producers in Slice 2+ |
| `commit_session_thread_v1` | live S3 writer validates on write | **Live-writer additive only** | Optional R13 links only; no new required fields without writer+tests |
| `train_row_v1` / `train_export_v1` | live S4 projection | **Live-writer additive / consume** | Optional metadata only; preserve R14 |
| `experiment_v1` | live S4 writer | **Live-writer additive only** | Optional checkpoint/resume refs only |

**Meta law:** untyped `meta: {"type":"object"}` free-for-all on the six greenfield stubs is **forbidden** after Slice 1; normative fields are top-level typed fields.

## 5. Canonical CLI naming + alias/deprecation stance

### 5.1 Canonical surface (locked)

```text
git-cg eval run …
git-cg eval resume …
git-cg eval recompute-scores …
git-cg eval doctor
git-cg eval amend-brief …
git-cg eval dogfood …
git-cg eval train-export …
git-cg eval session show …
git-cg eval thread show …
git-cg eval failures …
git-cg eval explain …
git-cg eval compare …
git-cg eval replay …
git-cg eval promote …
git-cg eval diagnose …
git-cg eval issue list|show|resolve|reopen|suppress
git-cg eval opik doctor
git-cg eval opik config show
git-cg eval export status|retry|drain
```

* **`eval run`** is canonical (not `eval suite run`).
* **`eval session show`** is canonical (not dashed `session-show`).
* **`eval opik config show`** is canonical Opik/config doctor companion.
* Nested **`eval export …`** is canonical export surface (already landed).

### 5.2 Landed aliases — deprecation decisions

| Landed form | Status | S6 stance | Removal target |
|:---|:---|:---|:---|
| `git-cg eval config show` | Landed flat S4 command | **Temporary compatibility alias only** if kept secret-safe. Canonical = `eval opik config show`. Emit deprecation on use (stderr human / envelope `warnings[]` JSON). | **Remove in the first minor release after S6 GA** (tracked in operator API map). |
| `git-cg eval export-status` | Landed dashed alias | **Temporary bridge** — not permanent law. Nested `eval export status` canonical. Deprecation notice required. | **Remove in the first minor release after S6 GA** (same cycle as config alias). |
| `git-cg eval export-retry` | Landed dashed alias | same | same |
| `git-cg eval export-drain` | Landed dashed alias | same | same |

### 5.3 Operator API map artifact path (locked for Slice 2)

| Artifact | Path | Check mode |
|:---|:---|:---|
| Generated operator API map | `docs/eval/operator_api_map.md` | `api_map.py --check` wired into `just`/CI (Slice 2) |
| Generator | `src/git_cg/eval/api_map.py` (Slice 2) | Introspect live Typer tree only — not S7 autodoc |

## 6. Script absorption census (Slice 8 executes)

| Script | Live state (tip) | Slice 0 disposition | Slice 8 action |
|:---|:---|:---|:---|
| `scripts/compile_opik_dataset.py` | Retired fail-closed pointer (S4) | **Already absorbed/retired** | Verify pointer remains; do not revive |
| `scripts/eval_commit_message.py` | Frozen fail-closed pointer (S5; S8 pointer tighten) | **Thin-shim / frozen** | Keep refuse+pointer; CLI homes include `eval run` / `eval triage` / `eval doctor`; no dual score law |
| `scripts/opik_metrics.py` | Frozen fail-closed pointer (S5) | **Thin-shim / frozen** | Keep refuse+pointer |
| `scripts/setup_opik_eval_rule.py` | Frozen fail-closed pointer (S5 D24) | **Thin-shim / frozen** | Keep refuse+pointer |
| `scripts/setup_opik_test_suites.py` | Frozen fail-closed pointer (S5 D24) | **Thin-shim / frozen** | Keep refuse+pointer |
| `scripts/opik_trace_triage.py` | **Absorbed** (fail-closed pointer; offline `eval triage` router) | **`absorbed_pointer_cli_s8`** | Frozen refusal shim → `git-cg eval triage` composing `eval doctor` / `eval failures` / `eval explain`; never popularity/`user_acceptance` as gold law |
| `scripts/sync_promptfoo_to_opik.py` | Live Promptfoo→Opik sync | **Explicitly out of S6 scope** | Leave for #219 / prompt-ops plane; do not make S6 operator law |
| `scripts/sync_prompts_to_opik.py` | Live system-prompt cloud sync | **Explicitly out of S6 scope** | Leave as optional maintainer cloud utility; not doctor/run/resume authority |

### 6.1 S6-H / D27 absorption proof (Slice 8)

| Legacy surface | Disposition | Replacement | Proof |
|:---|:---|:---|:---|
| `scripts/opik_trace_triage.py` | `absorbed_pointer_cli_s8` | `git-cg eval triage` → doctor / failures / explain | triage CLI + script-freeze / absorption tests |
| `scripts/eval_commit_message.py` | frozen thin shim (pointer tightened) | `git-cg eval run` / `eval triage` / `eval doctor` + scoring/Lane C | existing freeze tests + pointer tests |

`absorbed_pointer_cli_s8` means: the legacy script is a frozen refusal shim whose supported replacement is the offline `git-cg eval triage` router. It does **not** preserve Opik acceptance-threshold triage, and `user_acceptance` is not gold or accept-path law.


## 7. Plan-drift reconciliation (executed in this slice)

Plan SSOT patched to locked S6 terms (no third law surface):

| Drift | Pre-Slice-0 plan text | Locked term |
|:---|:---|:---|
| Checkpoint / experiment hash field | `compatibility_hash` / `compatibility_hash_inputs` | **`compat_hash`** / **`compat_hash_inputs`** (no untracked alias) |
| Session command | `session-show` | **`eval session show`** |
| Resume table | four-ish modes; weak recovery | **Five modes** + **recovery law** (mismatch preserves checkpoint read-only; recover via `fresh_suite_run` or `recompute_scores` over retained evidence; **checkpoint migration tooling = non-goal**) |
| R12 “+0ms” | literal wall-clock shorthand | **S6-G02 two-part claim**: (a) structural never-awaited seam (CI-gated); (b) empirical below-floor delta via `just dogfood-bench` / hyperfine (maintainer evidence, not merge gate) |
| Plan index | S6 read as future-only design | `docs/plans/README.md` status pointer updated |

## 8. Phantom metrics note (Slice 4 input)

Catalog-registered but **not** implemented in `scoring/family_h.py` today:

* `h.compat_hash_resume`
* `h.doctor_green`
* `h.export_config_resolved`

Doctor is their computation site (eval/observability class only — never product-accept gates).

## 9. Exit criteria (Slice 0)

| Criterion | Status |
|:---|:---|
| Architecture un-reopened | ✅ |
| Canonical CLI names decided | ✅ |
| Schema classifications decided | ✅ |
| Script disposition table recorded | ✅ |
| Path-helper split documented | ✅ |
| Alias/deprecation stance recorded | ✅ |
| API map path locked | ✅ |
| Plan SSOT + plans README reconciled | ✅ |
| Baseline known / recorded | ✅ |
| No runtime S6 writers/commands in this slice | ✅ |
| **Slice 1 may start** | ✅ |

## 10. Verification commands

```bash
uv run pytest tests/eval -q
just eval-schema-hash
# optional local disk-pressure form:
# uv run pytest tests/eval -q -p no:cacheprovider --no-cov -o addopts=''
```
