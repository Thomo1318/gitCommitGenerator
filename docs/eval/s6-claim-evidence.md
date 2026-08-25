# S6 claim → test matrix seed (Issue #246 / pre-Slice 9)

> **Issue:** [#246](https://github.com/Thomo1318/gitCommitGenerator/issues/246)
> **Parent:** [#217](https://github.com/Thomo1318/gitCommitGenerator/issues/217)
> **Branch package:** `src/git_cg/eval/**` (CLI / doctor / amend-brief / dogfood / sessions / train-export / triage)
> **Plan SSOT:** `docs/plans/opik-evaluation-harness.md`
> **Status:** **Seed only** (Slice 2 exit requirement). Slice 9 expands this into the full claim-evidence close pack, PR body table, and DoD narrative — do **not** treat this file as Slice 9 complete.
>
> **Proof spine (offline):**
>
> ```bash
> uv run pytest \
>   tests/eval/test_api_map_help.py \
>   tests/eval/test_checkpoint_store.py \
>   tests/eval/test_compat_hash.py \
>   tests/eval/test_run_orchestrator.py \
>   tests/eval/test_eval_cli_run.py \
>   tests/eval/test_doctor.py \
>   tests/eval/test_eval_cli_doctor.py \
>   tests/eval/test_eval_opik_doctor.py \
>   tests/eval/test_explain.py \
>   tests/eval/test_diagnose.py \
>   tests/eval/test_eval_cli_explain.py \
>   tests/eval/test_replay.py \
>   tests/eval/test_promote.py \
>   tests/eval/test_review_queue.py \
>   tests/eval/test_eval_cli_replay_promote.py \
>   tests/eval/test_s6_slice7.py \
>   tests/eval/test_eval_cli_triage.py \
>   tests/eval/mirror/test_train.py \
>   -q --no-cov
> ```

This page seeds the **S6-A…H claim → intended test module/node** map required before Slice 9.
Each claim names at least one primary offline evidence anchor. Secondary nodes are optional
cross-checks, not alternate law surfaces.

## Dual-axis law (all claims)

| Axis | Invariant |
|:---|:---|
| Product accept / commit path / ranking / Hybrid gate | Never blocked or flipped by doctor/export/dogfood/judge/missing-creds/timeouts |
| Eval / lab / operator health | May emit red doctor, skip classes, advisory attachments, train drops, denial audits |

## Seed vs Slice 9 close-out

| Deliverable | Owner | This seed? |
|:---|:---|:---|
| Every S6-A…H row names ≥1 intended test module/node | Slice 2 → expand Slice 9 | **Yes** |
| Full narrative evidence + coverage report + PR claim paste | Slice 9 / S6-H* | **No** |
| Maintainer hyperfine artifact for S6-G02(b) | `docs/eval/evidence/s6-g02b-*` + NTH-06 | **landed (maintainer evidence)** |
| PR links #246+#217; closes only #246 | Slice 9 / S6-H05–H06 | Open |

## Composition / CLI spine

```text
api_map + envelope sketches
  → run/resume/recompute/export_only orchestrator + checkpoints
  → doctor / opik doctor (secret-safe)
  → failures → explain → diagnose/issue → compare
  → replay → review_queue → promote (denial taxonomy)
  → amend-brief / sessions / dogfood / train-export
  → triage router (Slice 8)
```

## Claims S6-A…H (seed matrix)

### S6-A — API map · help · envelope

| ID | Summary | Primary evidence (seed) | Status |
|:---|:---|:---|:---|
| **S6-A01** | Supported S6 commands on `eval --help` / nested help | `tests/eval/test_api_map_help.py::test_eval_help_lists_supported_surface`; `test_walk_eval_tree_includes_canonical_commands`; `test_nested_group_help` | landed |
| **S6-A02** | Basic `git-cg --help` stays Opik-free / low-noise | `tests/eval/test_api_map_help.py::test_basic_git_cg_help_no_opik_requirement_or_eval_noise` | landed |
| **S6-A03** | Stability tiers documented | `docs/eval/operator_api_map.md` § Stability tiers; `tests/eval/test_api_map_help.py::test_operator_api_map_matches_live_tree` | landed |
| **S6-A04** | Canonical Python entrypoints named; no general SDK claim | `docs/eval/operator_api_map.md` entrypoint rows; `tests/eval/test_api_map_help.py::test_api_map_documents_single_writer_law` | landed |
| **S6-A05** | Undocumented internals not promised compatible | `docs/eval/operator_api_map.md` A05 wording; render/check suite in `test_api_map_help.py` | landed |
| **S6-A06** | No hard Opik import on normal commit / capture-off path | `tests/eval/test_eval_cli.py::test_eval_cli_module_does_not_import_binder_or_opik`; `tests/eval/test_enums_fail_closed.py::test_s0_c01_eval_package_imports_without_opik`; `tests/eval/test_api_map_help.py::test_eval_cli_module_import_stays_light` | landed |
| **S6-A07** | JSON commands emit one `cli_output_envelope_v1` | `tests/eval/test_api_map_help.py::test_stub_json_emits_envelope`; CLI envelope tests across doctor/explain/run/replay/triage/slice7 | landed |
| **S6-A08** | Per-command envelope `data` sketches + fail-closed `--check` | `tests/eval/test_api_map_help.py::test_minimum_envelope_sketches_registered`; `test_rendered_api_map_contains_all_envelope_sketches`; `test_missing_envelope_sketch_fails_check`; `src/git_cg/eval/envelope_sketches.py` | landed |
| **S6-A09** | `git_cg.eval.__init__.__all__` unchanged unless approved | `src/git_cg/eval/__init__.py` (`__all__` freeze); PR-time review gate (Slice 9 H05 checklist) | landed code; PR attestation open |

### S6-B — run · resume · checkpoint · exit codes

| ID | Summary | Primary evidence (seed) | Status |
|:---|:---|:---|:---|
| **S6-B01** | Checkpoint schema validates required fields | `tests/eval/test_checkpoint_store.py::test_write_load_roundtrip` | landed |
| **S6-B02** | Compat hash stable for identical pin/suite/snapshot inputs | `tests/eval/test_compat_hash.py::test_hash_stable_and_sensitive` | landed |
| **S6-B03** | Hash mismatch → `EVAL_COMPAT_HASH_MISMATCH` (exit 3) | `tests/eval/test_compat_hash.py::test_assert_mismatch_terminal_and_recovery`; `tests/eval/test_run_orchestrator.py::test_resume_compat_mismatch_exit_3_preserves_bytes` | landed |
| **S6-B04** | `resume_missing` scores only pending | `tests/eval/test_run_orchestrator.py::test_resume_missing_scores_only_pending` | landed |
| **S6-B05** | `recompute_scores` without regen when evidence retained | `tests/eval/test_run_orchestrator.py::test_recompute_mints_child_and_preserves_parent`; `test_recompute_score_history_append_only` | landed |
| **S6-B06** | `export_only` never scores | `tests/eval/test_run_orchestrator.py::test_export_only_no_checkpoint_no_score` | landed |
| **S6-B07** | R9 filters cannot silently redefine golden corpus | `tests/eval/test_eval_cli_run.py` filter/help contract; orchestrator case-filter paths in `test_run_orchestrator.py` | landed |
| **S6-B08** | After mismatch, recompute restores via new checkpoint; parent preserved | `tests/eval/test_run_orchestrator.py::test_recompute_mints_child_and_preserves_parent`; mismatch preserve-bytes test | landed |
| **S6-B09** | Checkpoint GC `--keep-last 10`; failed retained; index coherent | `tests/eval/test_checkpoint_store.py::test_prune_keep_last_and_failed_protection`; `test_failed_retained_until_completed`; `test_api_map_help.py::test_keep_last_default_on_run_help` | landed |
| **S6-B10** | CLI exit codes match frozen 0/1/2/3/4 registry | Doctor/run/explain/replay/promote/triage CLI tests asserting exit classes (e.g. `test_eval_cli_run.py`, `test_eval_cli_explain.py`, `test_run_orchestrator.py` exit 2/3/4) | landed |
| **S6-B11** | `eval run` orchestration: wraps scorer; offline default; Lane C/dogfood off; crash-safe per-case cadence; recompute never mutates mismatched prior | `tests/eval/test_run_orchestrator.py::test_fresh_suite_run_writes_checkpoint_and_case_scores`; `test_b11_per_case_checkpoint_cadence_at_most_one_case_loss`; `src/git_cg/eval/run_orchestrator.py` defaults | landed (+ explicit cadence proof) |
| **S6-B12** | `experiment_id` mint/reuse rules | `tests/eval/test_run_orchestrator.py::test_resume_missing_scores_only_pending` (reuse); `test_recompute_mints_child_and_preserves_parent` (mint + parent id) | landed |

### S6-C — doctor · secret safety

| ID | Summary | Primary evidence (seed) | Status |
|:---|:---|:---|:---|
| **S6-C01** | Unpinned latest / missing catalog hash ⇒ doctor fail | `tests/eval/test_doctor.py::test_floating_pin_fails_closed`; `test_is_pinned_rejects_latest_and_malformed` | landed |
| **S6-C02** | Empty-output fan-out / unbound online format metrics ⇒ red | `tests/eval/test_doctor.py` red-path producers; family/FIND coverage via doctor report suite | landed |
| **S6-C03** | Prompt pack change without local pin/result ⇒ warn/red | `tests/eval/test_doctor.py` pin/catalog checks + CLI doctor fixture suite | landed |
| **S6-C04** | `opik config show` masks secrets | `tests/eval/test_eval_opik_doctor.py` + config show mask paths; `tests/eval/mirror/test_config.py::test_mask_secret_never_leaks_prefix` | landed |
| **S6-C05** | `opik doctor` never prints tokens | `tests/eval/test_eval_opik_doctor.py::test_opik_doctor_never_prints_raw_token`; `test_opik_doctor_json_never_prints_raw_token`; `test_opik_doctor_human_mode_masks_token` | landed |
| **S6-C06** | Doctor/export failures do not flip product accept | Dual-axis composition: `tests/eval/mirror/test_composition_s4.py` fail-open; doctor isolation tests | landed |
| **S6-C07** | Phantom metrics have real computation sites + report contract | `tests/eval/test_doctor.py::test_local_doctor_emits_phantom_metric_scores`; `test_doctor_green_score_matches_block_failures`; `test_report_data_shape_is_machine_readable` | landed |
| **S6-C08** | Secret-bearing operator output routes through mask helpers | `tests/eval/test_eval_cli_explain.py::test_cli_explain_and_diagnose_never_print_raw_token`; `tests/eval/test_explain.py::test_explain_masks_secret_shaped_evaluator_errors`; `tests/eval/test_diagnose.py::test_diagnose_masks_secret_bearing_title_notes_and_store_row`; `tests/eval/test_s6_slice7.py::test_train_export_masks_secret_in_retained_message` | landed |

### S6-D — failures · explain · diagnose · compare

| ID | Summary | Primary evidence (seed) | Status |
|:---|:---|:---|:---|
| **S6-D01** | `failures` emits metric_ids + failure_ids | `tests/eval/test_explain.py::test_failures_lists_metric_and_failure_ids`; `tests/eval/test_eval_cli_explain.py::test_cli_failures_json_envelope` | landed |
| **S6-D02** | `explain` contract fields present | `tests/eval/test_explain.py::test_explain_full_contract_no_llm_rca`; `tests/eval/test_eval_cli_explain.py::test_cli_explain_json_contract` | landed |
| **S6-D03** | `explain` scored-field source for format metrics | `tests/eval/test_explain.py::test_explain_full_contract_no_llm_rca` | landed |
| **S6-D04** | No opaque LLM RCA identity path | `tests/eval/test_explain.py::test_explain_full_contract_no_llm_rca` | landed |
| **S6-D05** | Diagnose fingerprint excludes trace/time/raw/URL | `tests/eval/test_diagnose.py::test_fingerprint_excludes_ephemeral_and_sensitive_fields`; `test_fingerprint_is_order_stable` | landed |
| **S6-D06** | Issue list/show/resolve/reopen/suppress offline | `tests/eval/test_diagnose.py` issue lifecycle tests; `tests/eval/test_eval_cli_explain.py::test_cli_issue_full_lifecycle` | landed |
| **S6-D07** | Compare works without network | `tests/eval/test_explain.py::test_compare_metric_and_structural_delta`; `test_compare_detects_lineage_link` | landed |
| **S6-D08** | Illegal transitions / missing evidence fail closed; idempotent upsert | `tests/eval/test_diagnose.py::test_resolve_requires_evidence`; `test_suppress_requires_reason`; `test_illegal_transition_fails_closed`; `test_diagnose_is_idempotent_upsert_by_fingerprint` | landed |

### S6-E — replay · review · promote

| ID | Summary | Primary evidence (seed) | Status |
|:---|:---|:---|:---|
| **S6-E01** | Replay writes new bundle + `replay_compare_v1` | `tests/eval/test_replay.py::test_replay_writes_new_bundle_and_compare_without_mutating_source` | landed |
| **S6-E02** | Source bundle bytes/identity unchanged | same as E01; `test_replay_dry_run_does_not_write` | landed |
| **S6-E03** | Promote requires provenance + label + destination + redaction + split_group_id | `tests/eval/test_promote.py::test_promote_happy_path_writes_decision`; `test_promote_missing_required_fields`; `test_split_group_contamination` | landed |
| **S6-E04** | Human review alone cannot promote golden | `tests/eval/test_promote.py::test_deny_human_sole_gold_with_review` | landed |
| **S6-E05** | Invalid promote path rejected | `tests/eval/test_promote.py::test_deny_silent_gold_label`; `test_invalid_destination`; CLI deny tests | landed |
| **S6-E06** | Review queue local SoT offline | `tests/eval/test_review_queue.py::test_list_and_show`; `test_enqueue_writes_schema_valid_human_review` | landed |
| **S6-E07** | Legacy `human_review_v1` stub migrated to typed `scores` | `tests/eval/test_review_queue.py::test_enqueue_writes_schema_valid_human_review` | landed |
| **S6-E08** | Review lifecycle pending→in_review→adjudicated\|dismissed | `tests/eval/test_review_queue.py::test_claim_adjudicate_lifecycle`; `test_dismiss_from_pending`; `tests/eval/test_eval_cli_replay_promote.py::test_cli_review_lifecycle` | landed |
| **S6-E09** | Named promote denial taxonomy + audit retention | `tests/eval/test_promote.py::test_s6_e09_denial_reason_set_is_closed`; `test_deny_unresolved_dispute_*`; `test_deny_schema_validation_persists_candidate`; `test_dry_run_denial_does_not_write_audit`; `tests/eval/test_eval_cli_replay_promote.py::test_cli_promote_denial_persists_audit` | landed |

### S6-F — amend-brief · sessions

| ID | Summary | Primary evidence (seed) | Status |
|:---|:---|:---|:---|
| **S6-F01** | Amend-brief fully offline | `tests/eval/test_s6_slice7.py::test_amend_brief_offline_l1_projections_and_advisory`; `test_cli_amend_brief_happy_path_envelope` | landed |
| **S6-F02** | Family rollups + failure_ids + blocking/regime/path_class/gold counters | `tests/eval/test_s6_slice7.py::test_amend_brief_offline_l1_projections_and_advisory` | landed |
| **S6-F03** | Can reference `session_thread_id` | `tests/eval/test_s6_slice7.py::test_amend_brief_session_thread_reference_without_preference` | landed |
| **S6-F04** | Preference pair when versions ≥ 2 | `tests/eval/test_s6_slice7.py::test_amend_brief_preference_pair_final_accept_selection`; `test_amend_brief_no_preference_when_session_missing` | landed |
| **S6-F05** | Optional lane_c attachments marked advisory | `src/git_cg/eval/brief.py` (`authority=advisory` attachments); dogfood authority locks in `test_s6_slice7.py::test_dogfood_g03_*` | landed |
| **S6-F06** | Session/thread show read local twin without Opik | `tests/eval/test_s6_slice7.py::test_session_show_happy_path_offline`; `test_thread_show_maps_message_versions_not_chat_timeline`; `test_cli_session_and_thread_show_happy_path` | landed |
| **S6-F07** | `sess_` prefix + lifecycle; escape/missing fail closed; no chat/graph browser | `tests/eval/test_s6_slice7.py::test_session_invalid_id_is_usage`; `test_session_path_escape_is_integrity`; `test_session_open_and_closed_lifecycle_accepted`; binding twin tests under `tests/eval/binding/test_session_thread.py` | landed |

### S6-G — dogfood · train-export

| ID | Summary | Primary evidence (seed) | Status |
|:---|:---|:---|:---|
| **S6-G01** | Non-maintainer default dogfood mode `off` | `tests/eval/test_s6_slice7.py::test_dogfood_g01_non_maintainer_default_off`; `test_dogfood_g01_capture_off_skips_without_product_block` | landed |
| **S6-G02** | Async dogfood never blocks commit path (two-part) | **(a)** `tests/eval/test_s6_slice7.py::test_dogfood_g02a_async_never_invokes_or_awaits_judge`; `test_dogfood_g02a_source_has_no_blocking_wait_primitives`<br>**(b)** `just dogfood-bench` + `test_dogfood_g02b_*` + maintainer artifact `docs/eval/evidence/s6-g02b-dogfood-bench-meta.json` (ci_overlap=True; not a CI gate) | **landed (a+b)** |
| **S6-G03** | Dogfood attachments `authority=advisory` | `tests/eval/test_s6_slice7.py::test_dogfood_g03_authority_always_advisory_and_non_overridable` | landed |
| **S6-G04** | `capture_on=fail` hard_negative without product fail | `tests/eval/test_s6_slice7.py::test_dogfood_g04_capture_on_fail_hard_negative_no_product_block` | landed |
| **S6-G05** | Train-export scrub; row fail → drop + `scrub_report` + continue | `tests/eval/test_s6_slice7.py::test_train_export_row_scrub_failure_drops_and_continues`; `test_train_export_no_quarantine_store` | landed |
| **S6-G06** | Antipattern/hard-negative never silent-join `positive_gold` | `tests/eval/mirror/test_train.py::TestFilterPositiveGold::test_negatives_never_join_positive_gold`; `tests/eval/test_s6_slice7.py::test_train_export_unlabeled_dropped_not_positive` | landed |
| **S6-G07** | Dogfood/judge missing creds are lab/skip only | Lane C skip path `tests/eval/test_lane_c.py::TestRunLaneC::test_missing_credentials_skip_not_ineligible`; dogfood product_block=false skips in `test_s6_slice7.py` G01 paths | landed |
| **S6-G08** | Sample mode records seed/rate/population/selected-set; offline resample | `tests/eval/test_s6_slice7.py::test_dogfood_g08_sample_records_population_and_resamples_offline`; `test_dogfood_g08_env_seed_and_rate_are_honoured` | landed |

### S6-H — docs · CI recipe · PR hygiene (mostly Slice 9)

| ID | Summary | Primary evidence (seed) | Status |
|:---|:---|:---|:---|
| **S6-H01** | README documents E-LOOP, debug loop, command map, API tiers, S6 boundary | Partial live prose in `docs/eval/README.md` + `operator_api_map.md`; **full close narrative is Slice 9** | **Slice 9 open** |
| **S6-H02** | CI offline Lane A recipe documented/implemented | Existing offline pytest/CI Lane A posture; packaging text is Slice 9 | **Slice 9 open** |
| **S6-H03** | Script absorption/retirement boundary recorded | `tests/eval/mirror/test_setup_opik_scripts_absorption.py`; `docs/eval/README.md` script absorption sections | landed |
| **S6-H04** | FIND-007 maintainer-dogfood-vs-universal-gate wording | `docs/eval/README.md` § Authority + FIND-007 | landed |
| **S6-H05** | PR links #246 + #217 and reports claim evidence | PR body (not opened yet) | **Slice 9 open** |
| **S6-H06** | PR closes only #246; never #217/#216/#235 | PR trailer policy at open/merge | **Slice 9 open** |

## Explicit residuals (not Slice 9 blockers for *seed*, may block close)

| Residual | Notes |
|:---|:---|
| **S6-G02(b) / A5 empirical** | **Closed with maintainer evidence** at `docs/eval/evidence/s6-g02b-*` (hyperfine off/on JSON + summary + meta; ci_overlap=True). Recipe default remains 20 runs; capture used 3-run durable pack. Not a CI/product gate. |
| **S6-H01/H02/H05/H06** | Docs/CI/PR packaging — **start only in Slice 9** |
| Optional NTH | **Closed in pre-Slice-9 pack:** `failures` filters; `--dry-run` on promote/train-export/diagnose; multi-rater `eval review rollup`; G02(b)/NTH-06 evidence pack. **Style:** multi-except remains PEP 758 bare `except A, B:` (Ruff py314 canonical; parenthesize is not a residual) |

## PR close pack (paste target for Slice 9 — do not execute yet)

* Links **#246** + parent **#217**
* Trailers: **Closes #246 only**; `Refs: #217` (never Closes #217 / #216 / #235)
* Claim table: this file expanded + coverage summary
* Restate dual-axis + FIND-007 + no required GEval CI gate
* G02(b) bench artifact attached under `docs/eval/evidence/s6-g02b-*`

## Explicitly not evidenced as complete here

* Full Slice 9 DoD narrative / Zensical durable pages
* Live network Opik Cloud dogfood
* Opening/merging the S6 PR


## Pre-Slice-9 NTH + G02(b) close pack (2026-08-25)

Landed without starting Slice 9 docs/PR packaging:

| Item | Evidence |
|:---|:---|
| NTH-02 failures filters | `list_failures(... regime/family/failure_id/severity)`; CLI flags; API map sketch; `tests/eval/test_explain.py::test_failures_filters_*` |
| NTH-03 dry-run complete | `promote` (pre-landed); `train-export --dry-run` alias of `--no-write`; `diagnose --dry-run` no-write + would_write |
| NTH-05 multi-rater UX | `eval review rollup` + `rollup_reviews()` advisory dimension/outcome majority; never sole-promotes gold |
| Style hygiene | **N/A under py314:** Ruff target-version py314 keeps PEP 758 bare multi-except (`except A, B:`). Project documents this in `pyproject.toml` (`tool.interrogate`). No parenthesize residual. |
| NTH-06 / S6-G02(b) | Maintainer hyperfine pack in `docs/eval/evidence/s6-g02b-*`; `justfile` summariser arg order OFF→ON |
| S6-H01/H02/H05/H06 | **Still Slice 9** — not started here |
