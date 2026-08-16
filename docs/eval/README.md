# Evaluation harness contracts (S0–S3)

Offline **schema pack + metric catalog pins** (S0), **fixture/corpus encoder** (S1), **Plane A score runner** (S2a/S2b/S2c), and **accept-path final-bytes binding + trajectory evidence** (S3) for the Opik evaluation harness.

> **Design SSOT:** [`docs/plans/opik-evaluation-harness.md`](../plans/opik-evaluation-harness.md) @ `0.9.3-s2b-clarifications`
> **Implementation issues:** [#220](https://github.com/Thomo1318/gitCommitGenerator/issues/220) (S0) · [#231](https://github.com/Thomo1318/gitCommitGenerator/issues/231) (S3)
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
| `src/git_cg/eval/scoring/` | S2a–S2c offline Plane A runner (A–I + gates) |
| `src/git_cg/eval/binding/` | S3 accept-path binder + trajectory/session/message-version emitters |
| `tests/fixtures/eval/` | Lane A committed fixtures / suites |
| `src/git_cg/eval/data/metric_catalog_v0.json` | Machine catalog (Families A–I + secondary) |
| `tests/eval/` | Offline fail-closed tests |

Legacy `src/git_cg/evals/` (soak/report helpers) is **not** the contract home. S0 uses singular `eval/`.


## S2a — offline Plane A score runner

> **Implementation issue:** [#225](https://github.com/Thomo1318/gitCommitGenerator/issues/225)
> **Parent design:** [#217](https://github.com/Thomo1318/gitCommitGenerator/issues/217)

S2a scores committed S1 `ape_bundle_v1` fixtures **offline** using product authorities
(Hybrid parse + `commit_gold`), not eval-only rule forks.

### What basic users need

**Nothing.** Normal `git-cg commit` does **not** import `git_cg.eval.scoring`.
S2a is an opt-in evaluation surface for harness developers and CI offline gates.

### Authorities (wrap, do not fork)

| Family | Product authority |
|:---|:---|
| **B Hybrid** | `git_cg.telemetry.reverse_parse_commit_message`, `run_deterministic_checks`, Hybrid header shape aligned with hooks |
| **D Gold** | **one** call to `git_cg.commit_gold.check_commit_gold` → fan-out findings / `STRICT_FAIL_CODES` |
| **A Binding** | S1 bundle schema + artifact-class enum + FIND-027 target order |
| **H Harness** | S0 pins, suite snapshot pin, offline flag, score envelope, FIND-026 anti-fan-out |
| **Gates** | `compose_gates(..., require_block=S2A_REQUIRE_BLOCK)` — **ignores C′ / lab / human / NLP / export** |

Gold remains a **validator**. Do **not** weaken `GOLD_SKELETON_FALLBACK_FINAL`.

### FIND-026 / FIND-027

* **FIND-026:** empty or oversize scored input emits a single classified H failure and **short-circuits** Families B/D (no message-dependent fan-out).
* **FIND-027:** score the **final rendered message** (or explicit product card fallback). Never default to `raw_model_output` / `generation_json` / trace blobs.

### Gate law

```text
gate.deterministic_pass = all(require_block metrics passed)
```

* Default require block: `git_cg.eval.scoring.S2A_REQUIRE_BLOCK` (A + B + D core + H core).
* Suite documents may override via `metrics.require_block`.
* Mean pass-rate, C′, lab, human, NLP, export scores do **not** veto the deterministic gate.
* `gate.semantic_cohort_eligible` is deferred offline-honest (`cprime_deferred_s2a`).

### Offline score API

```bash
# Score the core fixture suite
uv run python - <<PY
from git_cg.eval.scoring import score_suite
res = score_suite("cm-eval-fixtures-core")
for c in res.cases:
    print(c.case_id, c.deterministic_pass, c.short_circuit)
print("snapshot", res.suite_snapshot_pin)
PY
```

### Package layout

| Path | Role |
|:---|:---|
| `src/git_cg/eval/scoring/runner.py` | `score_bundle` / `score_case` / `score_suite` |
| `src/git_cg/eval/scoring/context.py` | FIND-027 score context projection |
| `src/git_cg/eval/scoring/preconditions.py` | FIND-026 short-circuit |
| `src/git_cg/eval/scoring/family_{a,b,d,h}.py` | Family evaluators |
| `src/git_cg/eval/scoring/gates.py` | `compose_gates` + `S2A_REQUIRE_BLOCK` |
| `src/git_cg/eval/scoring/product_bridges.py` | Thin bridges into product modules |
| `scripts/opik_metrics.py` | **Legacy/advisory only** — not S2 law |

### Verification

```bash
uv run pytest tests/eval/test_score_runner.py \
  tests/eval/test_gates_composition.py \
  tests/eval/test_family_*.py \
  tests/eval/test_find026_antifanout.py \
  tests/eval/test_find027_artifact_bind.py \
  tests/eval/test_no_eval_policy_fork.py -q
```

### Deferred (not S2a baseline)

Lane C judges, Opik upload (S4), and S5–S7 remain out of scope here. Accept-path binding (S3) is documented in its own section below.
S2b (C/E/F/G product-authority metrics) shipped in v0.17.0 / PR #227; S2c (Family I topology) is documented below.

## S2c — Family I topology / lifecycle validators

> **Implementation issue:** [#229](https://github.com/Thomo1318/gitCommitGenerator/issues/229)

Family I always emits **16** offline topology/lifecycle rows on every scored case
(including FIND-026 short-circuit). Topology is **not** message-dependent.

### Policy: `require_topology`

| Source | Behaviour |
|:---|:---|
| Explicit `require_topology=` on `score_bundle` / `score_case` / `score_suite` | Wins when a real `bool` |
| `suite["meta"]["require_topology"]` | Used when the value is a real `bool` |
| Default | `false` |

Never inferred from `bound` / `ctx.bound`.

When `require_topology=false` (default):

* Family I still runs and records failures honestly.
* Failures **do not** join `S2A_REQUIRE_BLOCK` / `S2B_REQUIRE_BLOCK`.
* Golden promotion uses the S2b baseline only (det + gold + skeleton + bound).

When `require_topology=true`:

* Effective gate block is the stable unique union of the base require block and
  `S2C_TOPOLOGY_BLOCK` (12 catalog `severity=block` IDs).
* Golden promotion additionally requires passing:
  * `i.lifecycle_complete`
  * `i.required_spans_present`

`S2C_TOPOLOGY_BLOCK` is **never** stuffed into the frozen S2A/S2B constants.

### Runner order

```text
Short-circuit: A → I → H → envelope validate → gates
Normal:        A–G → I → H → envelope validate → gates
```

Family I evaluator exceptions recover **fail-closed** as 16 failed I rows
(`synthesize_family_i_fail_closed`) and force `h.evaluator_error_free=false`.

### Suite two-pass thread index (N14)

`score_suite` always:

1. Encodes every case.
2. Builds a read-only `session_thread_id → case_ids` index (`build_session_thread_index`).
3. Scores each case with that index (cross-case contamination checks).

No process-global mutable index. Fixture-level non-empty `session_thread_id` is
copied onto the bundle root by the S1 encoder (schema field; pins unchanged).

### Package surface

| Export | Role |
|:---|:---|
| `score_family_i` | 16-row Family I evaluator |
| `FAMILY_I_METRIC_IDS` | Frozen 16-id emission order |
| `S2C_TOPOLOGY_BLOCK` | Opt-in 12-id gate union |
| `build_session_thread_index` | Suite-level read-only thread map |
| `resolve_require_topology` | N19 policy helper |
| `compose_gates(..., require_topology=False)` | Gate law (default false) |

### Verification

```bash
uv run pytest tests/eval/test_family_i.py \
  tests/eval/test_gates_composition.py \
  tests/eval/test_score_runner.py \
  tests/eval/test_corpus_encoder.py \
  tests/eval/test_find026_antifanout.py -q

uv run pytest tests/eval/test_topology_split_negatives.py -q
uv run ruff check
uv run pyright
```

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
| `tests/fixtures/eval/cases/204-archive/` | #204 archive ramp rows (suite `204-archive`; not Q8 close-gate) |
| `tests/fixtures/eval/cases/invalid/` | Fail-closed probes (SEED-N1 / SEED-I1) |
| `tests/fixtures/eval/snapshots/` | Checked-in `dataset_snapshot_v1` goldens; runtime re-encoding verifies hashes |
| `tests/fixtures/eval/bundles/` | Checked-in golden `ape_bundle_v1` dumps |
| `tests/fixtures/eval/FIXTURE_INDEX.md` | Auto-generated fixture index |

Core offline suite: **`cm-eval-fixtures-core`** (V1 + A1 + B1).

Archive ramp suite: **`204-archive`** (A1/B1 + B2/B3/B4/A2).

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
* `materialize.py` — checked-in golden bundles + snapshots
* `index.py` — auto-generated fixture index markdown
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

S1 **close bar (Q8)** remains the core seed matrix:

| Seed | Case | Notes |
|:---|:---|:---|
| SEED-V1 | `seed-v1-valid-fixture` | Ordinary valid offline fixture |
| SEED-A1 | `seed-a1-session12-regime-a` | Regime A Session-12 recovery-poison class (`204-S12-G1`) |
| SEED-B1 | `seed-b1-session12-regime-b` | Regime B plausible false-green class (`204-S12-G2`) |
| SEED-N1 | `cases/invalid/*` | Invalid envelope / class / unbound coercion probes |
| SEED-I1 | `seed-i1-*-task-input` | expected/gold isolation negatives |

**Archive ramp (optional suite `204-archive` / alias `cm-eval-204-archive`):**

| Seed | Case | Notes |
|:---|:---|:---|
| SEED-B2 | `seed-b2-session12-g3` | Session-12 G3 Regime B tests-as-fix |
| SEED-B3 | `seed-b3-session12-g4` | Session-12 G4 docs attribution bleed |
| SEED-B4 | `seed-b4-quality-package-dogfood` | quality-package Regime B (F81–F83) |
| SEED-A2 | `seed-a2-instance-a-precursor` | Instance-A precursor Regime A |

Full historical #204 completeness remains **not** a merge blocker; the ramp is
the committed import path + expansion surface.

### Topology / split / judge negatives (§8.1 addendum)

Offline encoder fail-closed probes (S1). Full Family I scoring is S2c (`score_family_i`):

| Probe | Case | Contract |
|:---|:---|:---|
| Incomplete topology | `seed-n-topology-incomplete` | `require_complete_for_encode` |
| Counter/span mismatch | `seed-n-counter-mismatch` | Session-12 class regen counter vs spans |
| Split contamination | `seed-n-split-contamination` | train + gate co-membership |
| JUDGE-INPUT leak | `seed-n-judge-input-leak` | `judge_*` in `generation_task_input` |
| Replay lineage gap | `seed-n-replay-lineage-missing` | replay missing parent ids |
| Valid topology control | `seed-v-topology-complete` | encodes cleanly |

### Golden bundles + fixture index

```bash
# Materialize checked-in ape_bundle_v1 + dataset_snapshot_v1 goldens
uv run python -m git_cg.eval.corpus.materialize

# Regenerate auto fixture index markdown
uv run python -m git_cg.eval.corpus.index --write
```

| Path | Role |
|:---|:---|
| `tests/fixtures/eval/bundles/<suite>/*.ape_bundle_v1.json` | Checked-in golden bundles |
| `tests/fixtures/eval/snapshots/<suite>.dataset_snapshot_v1.json` | Checked-in snapshot goldens |
| `tests/fixtures/eval/FIXTURE_INDEX.md` | Auto-generated suite/case index |

Identity remains proven by runtime re-encode equality tests; goldens bind the
current S0 pin identities for review/CI drift detection.

### Migration boundary

* Do **not** treat ad-hoc encode scripts as product contract.
* Do **not** mutate product validators, hooks, accept-path, or telemetry for S1.
* Do **not** require network / Opik credentials for fixture encode or snapshot hash.

## Non-goals

| Slice | Still out of scope here |
|:---|:---|
| **S0** | Scoring runtime, Opik network client, accept-path binder |
| **S2a–S2c** | Lane C judges, accept-path binding (S3), Opik upload (S4), S5–S7 |
| **S3** | Opik mirror/upload + corpus lake (S4), Lane C′ judges (S5), eval CLI/doctor/amend-brief (S6), ADR rewrite (S7) |

Basic `git-cg` users do **not** need Opik installed.

## S3 — accept-path final-bytes binding + trajectory evidence

> **Implementation issue:** [#231](https://github.com/Thomo1318/gitCommitGenerator/issues/231)
> **Parent design:** [#217](https://github.com/Thomo1318/gitCommitGenerator/issues/217)

S3 binds the **real accepted final message bytes** (exact `COMMIT_EDITMSG` / accept-path final bytes) into `ape_bundle_v1` with `artifact_class=final_accept`, emits R7 `trajectory_evidence_v1` (declared vs observed stages), writes an additive R13 `commit_session_thread_v1` local twin, and records chronological `message_versions` (draft/amend/final). It makes Lane B binding **live** without any Opik network/mirror work.

### Capture is off by default (basic users unaffected)

| Variable | Default | Meaning |
|:---|:---|:---|
| `GIT_CG_EVAL_CAPTURE` | **`off`** (unset/empty/unknown → off) | Master switch for S3 local bind + trajectory + session-twin capture |
| `GIT_CG_EVAL_PROFILE` | unset | Optional alias read only when capture is unset: `basic`⇒off; `maintainer`/`train`/`dogfood`⇒on. Capture env wins if both set. |

Truthy = `1`/`true`/`on`/`yes`; falsy = unset/empty/`0`/`false`/`off`/`no`; any other token fails closed to **off**. A normal `git-cg commit` makes **no** `.eval` writes and **no** network calls when capture is off.

### Local Layer-A paths (repo-local, gitignored)

```text
.eval/
  bundles/acceptpath/<session_thread_id>.json   # final_accept ape_bundle_v1
  sessions/<session_thread_id>.json             # commit_session_thread_v1 twin
```

`/.eval/` is gitignored. Writes are atomic (temp + `os.replace`), mode `0600`/`0700`, and path-contained under the resolved repo root. Bundle JSON files are authoritative; any `index.json` is rebuildable cache only.

### Product-pass vs eval-fail (mandatory split)

A **valid final message with incomplete evidence** (missing trajectory, capture failure, unbound) is a **product pass + eval/observability fail** — never a Hybrid/gold prose rejection. Binding is best-effort and never blocks the accept path.

### `.eval` privacy / retention (your responsibility)

`.eval/` can contain **final commit messages and drafts**. Gitignore is **not** retention:

* Local maintainer responsibility to delete/rotate `.eval/` contents.
* Do **not** enable capture on shared/public repos without scrub.
* No automatic cloud upload in S3 (that is S4); capture is off by default.
* Default redaction profile is `default_scrub`; the final-message text is retained verbatim locally because it is the scored artifact (diffs/prompts/secrets are still scrubbed).

### Boundary

S3 **emits and binds local evidence only.** It does **not** upload to Opik / drain export queues (S4), run Lane C′/GEval judges (S5), provide the full eval CLI/doctor/amend-brief/review queue (S6), or rewrite ADR-0011 (S7).
