# S4 claim evidence matrix (E13 + P2-8)

> **Issue:** [#232](https://github.com/Thomo1318/gitCommitGenerator/issues/232)
> **Parent:** [#217](https://github.com/Thomo1318/gitCommitGenerator/issues/217)
> **Branch package:** `src/git_cg/eval/mirror/**`
> **Proof command (offline):**
>
> ```bash
> uv run pytest tests/eval/mirror tests/eval/test_eval_cli.py -q --no-cov
> ```

This page is the **pass-2 offline matrix (E13)** mapped into the **S4-A…G claim-evidence table (P2-8)**.  
Merge evidence is composition-path aware (`build_export_plan` / drain), not leaf unit tests alone.

## Dual-axis law (all claims)

| Axis | Invariant |
|:---|:---|
| Product accept / `gate.deterministic_pass` | Never blocked or flipped by export/drain/config errors (`product_accept_blocked=false`) |
| Export / evaluation health | May record `config_error`, `export_*` classes, `strict_mirror_failed` |

## E13 — minimum offline matrix

### Contract / schema

| Requirement | Evidence (offline tests) |
|:---|:---|
| Mode vocabulary accept/reject (`off\|local_only\|mirror\|strict_mirror`) | `tests/eval/mirror/test_config.py` (`test_canonical_modes_accepted`, `test_unknown_mode_*`, `test_e12_*`, legacy alias tests) |
| Closed enum rejection + disjointness (E4) | `tests/eval/mirror/test_enum_disjoint.py` |
| `additionalProperties: false` + `raw_dev_unsafe` exclusion (E3) | `tests/eval/mirror/test_config.py::test_e3_schema_keeps_additional_properties_false_and_blocks_raw_dev` |
| Canonical JSON stability; NaN/Inf rejected | `tests/eval/mirror/test_batch.py`, `tests/eval/mirror/test_payload.py` |
| No secret fields in fixtures | `tests/eval/mirror/test_config.py` fixture/schema tests (S4-A05) |
| Invalid mode → operator `config_error` (E12) | `test_config.py::test_e12_*`, `test_composition_s4.py::test_e12_*`, `tests/eval/test_eval_cli.py` drain/status/config show cases |

### Pipeline join (P0-5 / E8)

| Requirement | Evidence |
|:---|:---|
| redact→project preserves `gate` + `score_card` | `tests/eval/mirror/test_composition_s4.py::test_redact_project_batch_enqueue_drain_preserves_authority` |
| `build_export_plan` is sole join path | `test_composition_s4.py::test_build_export_plan_is_sole_join_path` |
| `final_accept` binding wins over `attempts[-1]` | `tests/eval/mirror/test_projections.py` (final_accept selection) |
| Quarantine never cleartext later in batch/queue/transport notes | `tests/eval/mirror/test_redaction.py`, transport scrub tests in `test_transport.py` |

### Durability / identity

| Requirement | Evidence |
|:---|:---|
| Missing/corrupt payload → classified failure; no item-id-only upload | `tests/eval/mirror/test_payload.py`, `test_exporter.py` |
| Same ids + different payload bytes ⇒ different idempotency key | `tests/eval/mirror/test_batch.py` |
| Lane/env/dataset/experiment/profile change ⇒ different key | `tests/eval/mirror/test_batch.py` |
| 4MB exact and +1 byte on final measured body | `tests/eval/mirror/test_batch.py` |

### Queue

| Requirement | Evidence |
|:---|:---|
| Concurrent drainers cannot double-send | `tests/eval/mirror/test_queue.py` |
| Stale `sending` reclaim after lease | `tests/eval/mirror/test_queue.py` |
| Crash after remote success before local `sent` | `tests/eval/mirror/test_queue.py` / `test_exporter.py` |
| Retry limits / dropped / backoff / malformed quarantine | `tests/eval/mirror/test_queue.py`, CLI retry tests in `test_eval_cli.py` |

### Transport

| Requirement | Evidence |
|:---|:---|
| Opik absent / lazy import (`path:lineno` allowlist E5) | `tests/eval/mirror/test_transport.py` |
| Flush adapter units + `flush() is False` | `tests/eval/mirror/test_transport.py` |
| 1ms / 999 / 1000 / 5000 / hang cases | `tests/eval/mirror/test_transport.py` |
| Auth/network/validation/size classes; scrubbed notes | `tests/eval/mirror/test_transport.py`, `test_secrets.py` |

### Isolation / dual-axis / absorption / train

| Requirement | Evidence |
|:---|:---|
| Product path unchanged with mirror off / opik missing | `test_composition_s4.py` mode-off + fail-open tests; transport package import mask |
| Export failure cannot flip `gate.deterministic_pass` | `test_composition_s4.py::test_transport_failure_is_fail_open_on_product_axis` |
| Legacy `compile_opik_dataset.py` no live upload; no `user_acceptance` SoT (E6) | `tests/eval/mirror/test_compile_opik_dataset_absorption.py` |
| Unlabeled antipattern cannot enter `positive_gold`; labels/splits mandatory (Q18 / S4-F) | `tests/eval/mirror/test_train.py` |

## P2-8 — Claims S4-A…G

| Claim | Summary | Primary evidence |
|:---|:---|:---|
| **S4-A** | Config + project pinning; no Default Project; secret-free fixtures | `test_config.py` (+ E12 visibility) |
| **S4-B** | R14 redaction + quarantine + profile ladder | `test_redaction.py` |
| **S4-C** | `export_batch_v1`, size bound, idempotency, queue transitions, error_class | `test_batch.py`, `test_queue.py`, `test_payload.py`, `test_exporter.py` |
| **S4-D** | Transport isolation + failure classes + bounded flush | `test_transport.py`, `test_secrets.py`, composition fail-open |
| **S4-E** | Experiments, pins, projections (bundle/score/session) | `test_experiments.py`, `test_projections.py`, composition join |
| **S4-F** | Train dual-axis safety + Q18 single-dataset metadata law | `test_train.py`, `docs/eval/README.md` Q18 section |
| **S4-G** | Docs + absorption + board/PR hygiene | `docs/eval/README.md`, this file, `test_compile_opik_dataset_absorption.py`, PR close pack |

### Composition-path proof (merge gate spine)

Must stay green for merge (S4-A + B + D + E deterministic offline) and close (all seven):

```text
redact → project → experiment pins → batch → enqueue → drain(mock)
```

Implemented by `git_cg.eval.mirror.composition.build_export_plan` and covered in `tests/eval/mirror/test_composition_s4.py`.

## PR close pack (checklist paste)

* Links **#232** + parent **#217**; dependency **#231** / post-S3 `main` (`v0.19.0`)
* Trailers: **Closes #232 only**; `Refs: #217` (never Closes #217 / #216 / #233)
* Claims S4-A…G evidence summarized (this file)
* I1–I12 non-violation restated
* Deferred: S5 Lane C′/GEval (#233), S6 doctor/amend-brief UX, S7 ADR rewrite, live dogfood drain demo
* Q18 decision: single owner train dataset + `label`/`split` metadata
* No S5–S7 implementation in the PR surface

## Explicitly not evidenced here

* Live network dogfood against Opik Cloud (operator-only)
* Full `git-cg eval opik doctor` polish (S6)
* Richer train packaging beyond minimal +/- projection

## Final verification (2026-08-18)

| Gate | Result |
|:---|:---|
| Proof command | `uv run pytest tests/eval/mirror tests/eval/test_eval_cli.py -q --no-cov` |
| Result | **354 passed** in ~116s |
| PR | [#236](https://github.com/Thomo1318/gitCommitGenerator/pull/236) @ `2209def` |
| Issue | [#232](https://github.com/Thomo1318/gitCommitGenerator/issues/232) — implementation complete; merge closes issue only |
| CodeRabbit | 40/40 threads resolved |
| Branch facts | `53` commits · `74` files · +10614 / −255 |
| CI | **all reported checks SUCCESS** · mergeable=`MERGEABLE` · mergeStateStatus=`CLEAN` |

### Explicitly deferred (not blocking S4 close)

* S5 Lane C′ / GEval → [#233](https://github.com/Thomo1318/gitCommitGenerator/issues/233)
* S6 doctor / amend-brief / review UX
* S7 ADR rewrite
* Live Opik dogfood drain demo (operator-only)
* Richer train packaging / broader legacy script flag absorption → [#235](https://github.com/Thomo1318/gitCommitGenerator/issues/235)
* Parent board mark-done on [#217](https://github.com/Thomo1318/gitCommitGenerator/issues/217) after merge

