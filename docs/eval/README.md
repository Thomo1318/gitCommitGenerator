# Evaluation harness contracts (S0)

Offline **schema pack + metric catalog pins** for the Opik evaluation harness.

> **Design SSOT:** [`docs/plans/opik-evaluation-harness.md`](../plans/opik-evaluation-harness.md) @ `0.9.2-body-ingest`
> **Implementation issue:** [#220](https://github.com/Thomo1318/gitCommitGenerator/issues/220)
> **Parent design:** [#217](https://github.com/Thomo1318/gitCommitGenerator/issues/217)

## Dual axis (required)

| Axis | Meaning |
|:---|:---|
| **Gate authority** | Deterministic product-wrapped metrics / `gate.*` only |
| **Training-corpus retention** | Owner R14 ladder (`public_ci` → `train_rich` / `antipattern_vault`) |

**Train axis ≠ gate axis (M11).** Recording `train_rich` rows, preference pairs, or Lane C scores must never by itself promote `gate.deterministic_pass` or sole golden green.

Gold remains a **validator**. Do **not** weaken `GOLD_SKELETON_FALLBACK_FINAL`.

## Pins

```bash
uv run python -c "from git_cg.eval import schema_pack_pin, metric_catalog_pin; print(schema_pack_pin()); print(metric_catalog_pin())"
```

Or:

```bash
just eval-schema-hash
```

Pins are content hashes (`name@sha256`):

* Current frozen S0 identities (asserted in `tests/eval/test_catalog_pins.py`):
  * `schema_pack_v0@91484d242ceedceb9160abd65a6a3f91fca1599251cab4285261c8de161d5cc6`
  * `metric_catalog_v0@430a62c1d7971e1145cfffd41e608a5f6bd39d284a3d050f991b8537f817eb75`
* Recipe: SHA-256 over canonical JSON (sorted keys, compact separators). Schema pack concatenates `filename\0canonical_bytes\0` for every non-underscore `*.schema.json`.
* Fixture examples may use any well-formed 64-hex pin; only the generator/`just eval-schema-hash` output and the pin lock test bind the live content identity.

## Layout

| Path | Role |
|:---|:---|
| `schemas/eval/*.schema.json` | Frozen JSON Schemas (§7.8) |
| `src/git_cg/eval/` | Offline package (enums, ScoreResult, pins) |
| `src/git_cg/eval/data/metric_catalog_v0.json` | Machine catalog (Families A–I + secondary) |
| `tests/eval/` | Offline fail-closed tests |

Legacy `src/git_cg/evals/` (soak/report helpers) is **not** the contract home. S0 uses singular `eval/`.

## expected_* isolation

`expected_final_message` / `expected_gold_codes` are **fixture/meta-eval only**.
They must never appear inside `generation_task_input`.

## Non-goals (S0)

No scoring runtime, no Opik network client, no corpus encoding (S1), no accept-path binder (S3).

Basic `git-cg` users do **not** need Opik installed.
