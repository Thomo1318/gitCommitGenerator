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
  * `schema_pack_v0@6647b3a3c45e5b22743ccc686eb662f70d8d65858c06fb5f19dafe849e27a5d6`
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
| `src/git_cg/eval/mirror/` | S4 non-blocking Opik mirror + train projection |
| `src/git_cg/eval/lane_c/` | S5 gated Lane C′ cohort (advisory judges) |
| `prompts/eval/lane_c/` | Local prompt-pack SoT (craft/relevance rubrics) |
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
* `gate.semantic_cohort_eligible` is **authorization only** (suite allows Lane C ∧ (deterministic pass ∨ `lab_override`) ∧ judge identity pins resolvable — **not secrets**). When the semantic cohort is not evaluated on the offline Lane A/B path, the gate stays honest-deferred (`reason=semantic_cohort_deferred_offline_later_lane`, `failure_ids=["GATE_SEMANTIC_COHORT_DEFERRED"]`, evidence `offline_lane_ab` / `semantic_cohort_not_evaluated`). Credentials affect **availability/skip only** — never eligibility. See [S5](#s5--gated-lane-c-cohort--optional-judge-lab-233).

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

### Later slices (not S2a baseline)

S2a remains the offline deterministic baseline. Later slices are documented in their own sections:

* **S2b** (C/E/F/G product-authority metrics) shipped in v0.17.0 / PR #227; **S2c** (Family I topology) below.
* **S3** accept-path binding, **S4** Opik mirror, and **S5** gated Lane C′ judges each have dedicated sections.
* S2a itself does **not** invoke network judges or Opik.

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

## Non-goals (historical slice boundaries)

Each slice section documents **what that slice itself does not own**. Later slices may land the deferred work — see the dedicated S3/S4/S5 sections below.

| Slice section | Out of that slice's scope (owned later) |
|:---|:---|
| **S0** | Scoring runtime, Opik network client, accept-path binder |
| **S2a–S2c** | Accept-path binding (S3), Opik upload (S4), Lane C′ judges (S5), operator UX (S6), ADR rewrite (S7) |
| **S3** | Opik mirror/upload + corpus lake (S4), Lane C′ judges (S5), eval CLI/doctor/amend-brief (S6), ADR rewrite (S7) |
| **S4** | Lane C′ judges (S5), full eval doctor/amend-brief/review queue UX (S6), ADR rewrite (S7) |
| **S5** | Full doctor/amend-brief/review-queue UX (S6), ADR-0011 rewrite + durable Zensical API pages (S7), required GEval CI gate (never) |

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

S3 **emits and binds local evidence only.** Upload/drain is **S4**; gated advisory Lane C′ judges are **S5** (see [S5](#s5--gated-lane-c-cohort--optional-judge-lab-233)); full eval CLI/doctor/amend-brief/review queue is **S6**; ADR-0011 rewrite is **S7**.

## S4 — non-blocking Opik mirror + owner corpus lake

> **Implementation issue:** [#232](https://github.com/Thomo1318/gitCommitGenerator/issues/232)
> **Parent design:** [#217](https://github.com/Thomo1318/gitCommitGenerator/issues/217)
> **Package:** `src/git_cg/eval/mirror/**`

S4 projects **precomputed local Layer-A evidence** into Opik for operator compare and an optional **owner training / longitudinal corpus lake**. Opik is never scoring authority, CI sole green, product acceptance authority, or golden source of truth.

### Modes (`git_cg_opik_config_v1`)

| Mode | Network | Secrets | Behaviour |
|:---|:---|:---|:---|
| `off` | no | no | Default. No enqueue/drain/network. |
| `local_only` | no | no | Local queue/payload durability only. |
| `mirror` | optional best-effort | runtime-resolved Opik key | Export failures are dual-axis eval health only. |
| `strict_mirror` | optional best-effort | runtime-resolved Opik key | May fail an **evaluation job**, never product accept. |

Legacy aliases still resolve: `local` → `local_only`, `dogfood` → `strict_mirror`. Invented tokens such as `self_hosted_noauth` are **not** supported modes and never make network auth optional.

Unset/empty mode still defaults to **`off`** (capture-off). An **unknown mode token** also fails closed to `off` for capture safety, but operator surfaces (`git-cg eval config show`, `export status`, `export drain`, and `build_export_plan`) must report **`ExportHealth=config_error`** via `meta.mode_fallback` (**E12**) — never only a quiet ambient disable.

### Explicit projects — no Default Project

Export requires explicit project/lane/environment binding. Missing project/endpoint when export is requested fails as **export validation**, not product/gate failure. There is no silent Default Project dump path.

### Dual-axis fail-open law

| Axis | Export outage effect |
|:---|:---|
| **Product accept / Hybrid gate** | **Never blocked** (`product_accept_blocked=false`) |
| **Evaluation / export health** | May record `export_network` / `export_auth` / `export_validation` / `export_size` |

`gate.deterministic_pass` is local-precompute authority and is never flipped by mirror transport.

### R14 redaction ladder on export

Export always runs the R14 ladder. Default path is `default_scrub`. Owner-rich profiles (`private_message`, `train_rich`, `antipattern_vault`) require explicit owner export enablement and are blocked in CI ambient paths. `raw_dev_unsafe` cannot be selected by the default export path. Scrub failures quarantine/omit fields rather than ambient-leak.

### Queue + transport

```text
.eval/
  export_queue/     # durable queue rows (status/lease/retry)
  export_payloads/  # content-addressed payload artifacts
```

* Batches are bounded (default **≤4MB** envelope), idempotent, and pin-bound.
* Transport imports Opik **lazily** inside the upload call only (`src/git_cg/eval/mirror/transport.py`).
* Installed SDK flush uses whole seconds; config remains `flush_timeout_ms` and is converted with ceiling + outer deadline.
* Notes/errors are scrubbed (URLs, auth headers, secret-shaped tokens, path/query fragments).

### Experiment naming + pins

```text
eval_<lane>_<catalog_version>_<gitsha>_<utc>[_suffix]
```

Records carry full pin metadata (`schema_pack`, `metric_catalog`, harness/catalog versions, environment/project/dataset, redaction profile, etc.). Unresolved git SHA is allowed for local diagnostics only; network export refuses unresolved SHA as `export_validation`.

### Q18 decision (train-positive vs train-negative)

**Decision:** one owner train dataset with explicit **`label` + `split` metadata** (not separate positive/negative datasets).

| Rule | Contract |
|:---|:---|
| Dataset | `cm-eval-owner-train` (single lake id) |
| Labels | closed `positive` \| `negative` |
| Positive gold | only labeled positives; unlabeled excluded |
| Negatives | never silent-merge into `positive_gold` |
| Required metadata | `label`, `split` / `split_group_id`, `redaction_profile`, provenance/source |
| Authority | `corpus_retention` only — **train lake ≠ CI sole green** |

Helpers live in `git_cg.eval.mirror.train` (`build_train_projection`, `filter_positive_gold`, …).

### Operator entrypoints (dev-only)

```bash
# secret-safe resolved config (+ E12 config_error on invalid mode)
uv run git-cg eval config show

# queue inspect / retry / drain (canonical nested form)
uv run git-cg eval export status
uv run git-cg eval export retry
uv run git-cg eval export drain

# temporary dashed aliases (one minor cycle)
uv run git-cg eval export-status
uv run git-cg eval export-drain
```

These are maintainer/export surfaces. Basic commit UX stays unchanged when capture/mirror are off.
Invalid mode tokens surface `health=config_error` on config/status/drain (exit 2 for those operator commands only).

### Offline proof matrix + claim evidence (E13 / P2-8)

The pass-2 offline matrix and S4-A…G claim-evidence table live in [`docs/eval/s4-claim-evidence.md`](./s4-claim-evidence.md). Composition-path proof is required for merge/close — leaf projection tests alone are not sufficient.

### Script absorption boundary

`scripts/compile_opik_dataset.py` is a **retired pointer/wrapper** (S4 P2-3 / E6). It no longer imports Opik, no longer filters on `user_acceptance`, and no longer uploads. Live dataset push is only via the non-blocking mirror queue (`git-cg eval export status|retry|drain`). S4 library law lives under `src/git_cg/eval/mirror/**` (config, R14, batch/queue/payload, lazy transport, pins, projections, Q18 train safeguards). Layer-A local labels remain the SoT; popularity feedback is never a golden/promotion signal. Do not extend the retired script as product contract.

### Boundary

S4 **mirrors precomputed local evidence only.** It does **not** make Opik CI/golden SoT. Gated advisory Lane C′ judges are **S5** (see [S5](#s5--gated-lane-c-cohort--optional-judge-lab-233)); full doctor/amend-brief/review-queue UX is **S6**; ADR-0011 rewrite is **S7**.


## S5 — gated Lane C′ cohort + optional judge lab (#233)

> **Implementation issue:** [#233](https://github.com/Thomo1318/gitCommitGenerator/issues/233)
> **Parent design:** [#217](https://github.com/Thomo1318/gitCommitGenerator/issues/217)
> **Package:** `src/git_cg/eval/lane_c/**`
> **Prompt-pack SoT:** `prompts/eval/lane_c/**`
> **Plan SSOT:** `docs/plans/opik-evaluation-harness.md` (`0.9.5-s5-s6-s7-api-surface`, retaining the `0.9.4-s5-eligibility-split` locks)
> **Baseline / peel:** [`slice0_baseline.json`](./slice0_baseline.json) · [`s5-recovery-peel-inventory.md`](./s5-recovery-peel-inventory.md)
> **Claim evidence:** [`s5-claim-evidence.md`](./s5-claim-evidence.md)

S5 enables **residual advisory** craft/relevance judges **after** eligibility. It is **never** the first CI gate, never sole golden green, and never product accept authority.

### Authority + FIND-007 (narrow ban)

| Law | Contract |
|:---|:---|
| **Authority** | Every C′ row stamps `authority=advisory` and `source=lane_c_judge` (or weaker lab/ops labels). |
| **Deterministic gate** | `gate.deterministic_pass` stays local A/B/D/H (…I) authority. C′ scores cannot veto it. |
| **FIND-007 narrow ban** | Ban only **product-plane, universal, unattended, sole-authoritative GEval-on-every-commit**. Maintainer advisory / async dogfood / lab cohorts remain allowed. |
| **Never first CI gate** | Default CI stays offline Lane A. There is **no** required “GEval gate” job. Lane C′ must not become the first or sole merge gate. |
| **Gold-blind default** | Ordinary `judge_input` omits expected/gold/assert/gate carriers (recursive isolation). |
| **Authz ≠ credentials** | Eligibility is authorization (suite + det-pass/`lab_override` + **identity pins**). Missing API keys are **availability** skips only. |
| **Final-accept linkage** | Ordinary judges consume S3 final-accept projection (`artifact_class`, `final_message_sha256`, encoding, optional `session_thread_id`). No invented `bundle_id`. |
| **No auto-`passed`** | Continuous 1–5 scores use `make_advisory_score` → `passed is None`, `reason="scored"`. Do **not** call raw `make_score(..., passed=None)` for C′ (F01 footgun). |

### Eligibility vs availability

```text
gate.semantic_cohort_eligible =   # authorization ONLY
    suite.allows_lane_c
    AND (gate.deterministic_pass OR suite.lab_override)
    AND judge_identity_pins_resolvable   # model/pack/params — NOT secrets

judge_execution_available =       # skip / lab class ONLY
    credentials_present AND provider_client_constructible
```

* Offline Lane A/B with **no** Lane C verdict keeps the honest deferred gate:
  `reason=semantic_cohort_deferred_offline_later_lane`,
  `failure_ids=["GATE_SEMANTIC_COHORT_DEFERRED"]`,
  evidence `offline_lane_ab=true`, `semantic_cohort_not_evaluated=true`, `cprime_ran=false`.
* Active paths never set `cprime_ran := eligible`. `cprime_ran` is true only when a judge actually invoked and scored.
* `compose_gates` never resolves credentials; it only consumes optional precomputed eligibility/run evidence.

### Operator matrix

| Mode | Preconditions | What happens | Product / det gate |
|:---|:---|:---|:---|
| **Lane C off** (default) | `allows_lane_c=false` or no Lane C wiring | No judges; offline deferred or ineligible skip rows | Unchanged; offline A/B green without keys/network |
| **Eligible + no key** | suite allows + det pass + pins OK; `GIT_CG_EVAL_JUDGE_API_KEY` absent | **Eligible** but **unavailable** → availability skip (`unavailable_creds`); zero judge side effects | Det gate unchanged; not “unauthorized” |
| **Eligible + key** | eligible + key present + client constructible + pack/input OK | `run_lane_c` may invoke pinned craft/relevance judges; advisory rows only | Det/golden **not** flipped by C′ scores |
| **`lab_override`** | det fail + explicit lab override | **Eligible-diagnostic** path: skip rows only (`lab_override_diagnostic`); **zero judge side effects** | Diagnostic provenance; excluded from default quality rollups |

### Env / pins (identity vs secrets)

| Variable / pin | Role |
|:---|:---|
| `GIT_CG_EVAL_JUDGE_MODEL` | **Identity pin** (dated/immutable model id). Undated aliases / `latest` fail closed on CI-shaped suites. |
| `GIT_CG_EVAL_JUDGE_API_KEY` | **Secret** — availability only; never part of eligibility. |
| `GIT_CG_EVAL_JUDGE_BASE_URL` | Optional OpenAI-compatible base URL (NTH-01). |
| Local `prompt_pack_v1` under `prompts/eval/lane_c/` | Runtime SoT for craft/relevance rubrics; content-hash pinned. Cloud Prompt Library is **not** runtime SoT. |

### Supported Python surface (narrow)

| Surface | Status |
|:---|:---|
| `git_cg.eval.lane_c.run_lane_c` | **Supported** gated execution API |
| `git_cg.eval.scoring.score_bundle` (Lane C′ opt-in args) | **Supported** composition entry |
| `make_advisory_score` / eligibility / availability helpers | Supported harness helpers |
| Raw `run_pinned_judge` | Lab/internal seam — **not** the default public execution API |
| General-purpose Python SDK / REST | **Out of scope** (CLI-first; operator map → S6; durable API docs → S7) |

Importing `git_cg.eval.lane_c` stays free of `openai` / provider SDKs until a live transport is actually invoked.

### Offline proof + coverage

```bash
# Full Lane C offline suite
uv run pytest tests/eval/test_lane_c*.py -q --no-cov

# Scoped coverage floor (D40 / S5-H)
uv run pytest tests/eval/test_lane_c*.py \
  --cov=git_cg.eval.lane_c \
  --cov-report=term-missing \
  --cov-fail-under=80
```

Composition/runner claim mapping lives in [`s5-claim-evidence.md`](./s5-claim-evidence.md).

### Residuals (explicit)

| Residual | Disposition |
|:---|:---|
| **R2** meta-eval / Equals | Deferred — future lab home; labels must not enter ordinary `judge_input` |
| **R1** richer rubric packs | Deferred — flags-only later |
| **R6** moderation ops | Deferred — off-by-default; #219 plane coord |
| **R8** flakiness studies | Deferred — lab only |
| **R10** NLP diagnostics | Deferred — lab/diagnostic only |
| **R5** dirty overlays | **N/A** — no `.eval/overlays/` in tree |
| Family H C′ honesty metrics | **Shipped** (`h.judge_input_isolated`, `h.prompt_pack_*`) |
| Legacy `setup_opik_eval_rule.py` / `setup_opik_test_suites.py` | **Frozen** — refuse live accept-path authority |

### Boundary

S5 ships the **gated advisory cohort only.** It does **not** land full doctor/amend-brief/review-queue UX (**S6**), rewrite ADR-0011 / durable Zensical API pages (**S7**), or install a required GEval CI gate (**never**).

