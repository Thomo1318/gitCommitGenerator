# Evaluation harness contracts (S0–S1)

Offline **schema pack + metric catalog pins** (S0) and **fixture/corpus encoder** (S1) for the Opik evaluation harness.

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
| `src/git_cg/eval/corpus/` | S1 fixture encoder + snapshot builder |
| `tests/fixtures/eval/` | Lane A committed fixtures / suites |
| `src/git_cg/eval/data/metric_catalog_v0.json` | Machine catalog (Families A–I + secondary) |
| `tests/eval/` | Offline fail-closed tests |

Legacy `src/git_cg/evals/` (soak/report helpers) is **not** the contract home. S0 uses singular `eval/`.

## expected_* isolation

`expected_final_message` / `expected_gold_codes` are **fixture/meta-eval only**.
They must never appear inside `generation_task_input`.

## S1 — offline corpus encoder

> **Implementation issue:** [#223](https://github.com/Thomo1318/gitCommitGenerator/issues/223)
> **Parent design:** [#217](https://github.com/Thomo1318/gitCommitGenerator/issues/217)

Lane A local source of truth: committed fixtures encode into validated
`ape_bundle_v1` / `eval_case_v1` / `dataset_snapshot_v1` artifacts.

### Fixture layout

| Path | Role |
|:---|:---|
| `tests/fixtures/eval/suites/` | Suite definitions (`eval_suite_v1` shape + encoder `case_paths`) |
| `tests/fixtures/eval/cases/valid/` | Ordinary valid fixtures (SEED-V1) |
| `tests/fixtures/eval/cases/session-12/` | Session-12 Regime A/B seeds (SEED-A1 / SEED-B1) |
| `tests/fixtures/eval/cases/204-archive/` | Future full #204 archive rows (not an S1 completeness gate) |
| `tests/fixtures/eval/cases/invalid/` | Fail-closed probes (SEED-N1 / SEED-I1) |
| `tests/fixtures/eval/snapshots/` | Optional notes; hashes are built at runtime |
| `tests/fixtures/eval/bundles/` | Optional materialized bundle dumps |

Core offline suite: **`cm-eval-fixtures-core`** (V1 + A1 + B1).

### Encoder / snapshot usage

```bash
uv run python - <<'PY'
from git_cg.eval.corpus import (
    encode_fixture,
    load_fixture_dict,
    default_fixture_root,
    build_core_snapshot,
    build_snapshot,
    resolve_dataset_id,
)

root = default_fixture_root()
fix = load_fixture_dict(root / "cases/valid/seed-v1-valid-fixture.json")
out = encode_fixture(fix)
print(out["bundle_ref"])
print(out["bundle"]["schema_pack"])

snap = build_core_snapshot()
print(snap["snapshot_hash"], snap["item_count"])

# aliases (§7.3.2) — stable plan ids are authoritative
print(resolve_dataset_id("cm-eval-204-archive"))  # -> 204-archive
print(build_snapshot("cm-eval-fixtures-core")["snapshot_hash"])
PY
```

Package surface: `src/git_cg/eval/corpus/`

* `aliases.py` — stable dataset ids + historical aliases
* `encoder.py` — fixture → `ape_bundle_v1` + `eval_case_v1`
* `task_input.py` — fail-closed `generation_task_input` projection
* `suites.py` / `fixtures.py` / `snapshots.py` — suite load + ordered snapshot hash
* `canonical.py` — sorted-keys compact JSON + SHA-256

### Local SoT vs Opik mirror

| Surface | Role |
|:---|:---|
| **Local fixtures + encoder** | Lane A source of truth (offline, pin-bound, deterministic) |
| **Opik datasets / experiments** | Downstream mirror / execution surface (S4+) |

S1 does **not** upload, sync, or require Opik. Unbound historical seeds keep
`bound=false` and `provenance_label=Opik-unbound` (or `fixture`). They are never
silently coerced into `final_accept`.

### Dataset aliases (§7.3.2)

| Alias (historical body) | Stable id |
|:---|:---|
| `cm-eval-204-archive` | `204-archive` |
| `cm-eval-acceptpath-live` | `acceptpath-live` |
| `cm-eval-gold-counter-integrity` | `gold-counter-integrity` |
| `cm-eval-semantic-cohort` | `semantic-cohort` |
| `cm-eval-regression-queue` | `regression-queue` |
| `cm-eval-fixtures-core` | `cm-eval-fixtures-core` |

Unknown aliases fail closed.

### Dual-axis authority (S1 reminder)

| Axis | S1 implication |
|:---|:---|
| **Gate authority** | Not exercised; no scoring runtime |
| **Training-corpus retention** | Fixtures may carry regime / failure / prevention ids for later train lanes |

`expected_*` / gold targets may live on the **fixture envelope / bundle** for
later meta-eval (S2+). They must **never** appear in `generation_task_input`.

### Seed matrix vs full #204 archive

S1 commits a **seed** matrix only:

| Seed | Case | Notes |
|:---|:---|:---|
| SEED-V1 | `seed-v1-valid-fixture` | Ordinary valid offline fixture |
| SEED-A1 | `seed-a1-session12-regime-a` | Regime A Session-12 recovery-poison class (`204-S12-G1`) |
| SEED-B1 | `seed-b1-session12-regime-b` | Regime B plausible false-green class (`204-S12-G2`) |
| SEED-N1 | `cases/invalid/*` | Invalid envelope / class / unbound coercion probes |
| SEED-I1 | `seed-i1-*-task-input` | expected/gold isolation negatives |

Full #204 archive completeness is **not** an S1 blocker. Archive migration
stays under later slices; ad-hoc scripts must not become product SoT.

### Migration boundary

* Do **not** treat ad-hoc encode scripts as product contract.
* Do **not** mutate product validators, hooks, accept-path, or telemetry for S1.
* Do **not** require network / Opik credentials for fixture encode or snapshot hash.

## Non-goals

| Slice | Still out of scope here |
|:---|:---|
| **S0** | Scoring runtime, Opik network client, accept-path binder |
| **S1** | S2–S7 metrics/judges, accept-path binding (S3), Opik upload (S4), full #204 migration |

Basic `git-cg` users do **not** need Opik installed.
