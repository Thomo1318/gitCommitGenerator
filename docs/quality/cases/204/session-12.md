# CASE — Session 12 · G1 residual close-out (Regime A)

> **Status:** active / full  
> **Copy lineage:** promoted from [#204 comment 5213748048](https://github.com/Thomo1318/gitCommitGenerator/issues/204#issuecomment-5213748048) (G1 section)  
> **Method:** [`../../METHOD.md`](../../METHOD.md)  
> **Template:** [`../../templates/CASE_TEMPLATE.md`](../../templates/CASE_TEMPLATE.md)  
> **Package version:** `1.0.0-combine`  
> **Series:** Session 12 · Session 6 residual close-out · message-only rebuild  
> **Sibling cases:** [`session-12-g2.md`](./session-12-g2.md) · [`session-12-g3.md`](./session-12-g3.md) · [`session-12-g4.md`](./session-12-g4.md) · [`session-12-synthesis.md`](./session-12-synthesis.md) · [`session-12-dogfood-g2-g4.md`](./session-12-dogfood-g2-g4.md)  
> **Consumer:** eval harness [#217](https://github.com/Thomo1318/gitCommitGenerator/issues/217) / [`docs/plans/opik-evaluation-harness.md`](../../../plans/opik-evaluation-harness.md) (`session-12-seed`)  
> **Authority:** this file is package SSOT for S12-G1. The GitHub comment is intake/archive evidence only.

```yaml
package: commit-message-failure-analysis
doc: case
version: 1.0.0-combine
status: active
issue: 204
case_id: 204-S12-G1
series_id: 204-S12
series_class: residual-close-out
regime: A
opik: bound
sources:
  - github:issue-comment:5213748048
  - git:raw:5117f60ddbedf36041d6b10d0dc1084d6b2458b6
  - git:gold:4aa90a8fb6d8fa5df166ea6f4ed2f4a34f5c738c
  - opik:trace:019fda92-4f84-7f28-8b0b-9bd9a346f272
last_updated: 2026-08-13
```

---

## 0. Open summary

**Result:** MISS gold · Regime **A** (controls fire; recovery makes it worse)  
**Path focus:** `src/git_cg/commit_quality.py`  
**Severity:** Critical  
**Raw → gold:** `5117f60ddbedf36041d6b10d0dc1084d6b2458b6` → `4aa90a8fb6d8fa5df166ea6f4ed2f4a34f5c738c`  
**Tree preserved:** yes · tree OID `5e91ec2d…` (message-only)  
**Branch / base→tip:** `refactor/204-commit-presentation-quality` · `2e965c5` → series gold tip `3b96ed6` (G1 gold `4aa90a8`)  
**One-line diagnosis:** Healthy product-law add locked near-correct `feature_addition`/`feat`, then contradictory body policy (banned `Context:`/`Changes:` required on skeleton path) thrash-exhausted regeneration and shipped skeleton fallback as a successful final: `chore`/`NONE` + process-meta body under `gold_strict=true`.  
**IDs:** **F72** · **F73** · **F74** · **F75** · F78 (inventory) · P-S12-1 · P-S12-2 · P-S12-3 · P-S12-5 · P-S12-6 · extends F55/F56/F64  
**Series class:** residual-close-out (Session 12 · Session 6 residual)

| Field | Value |
|:---|:---|
| Issue | #204 |
| Case ID | 204-S12-G1 |
| Reviewer | Thomo1318 / Session 12 forensic archive |
| Date | 2026-08-07 (incident) · promoted 2026-08-13 |
| Library class (intended) | product `src/**` · `commit_quality` policy/guard laws |
| Acceptance mode (raw) | fallback success path · telemetry provenance `ai_edited_minor` |

### Observed subjects (do not regress)

```text
S12-G1 ❌  fallback/process-meta path — chore/NONE + diagnostic body + snake scope
S12-G1 ✅  ✨ feat(commit-quality): add Session 6 scope, capability, and guard laws
```

### Package indexes

| Registry | Link |
|:---|:---|
| Failure IDs | [`../../FAILURE_TAXONOMY.md`](../../FAILURE_TAXONOMY.md) F72–F75 |
| Prevention | [`../../PREVENTION_BACKLOG.md`](../../PREVENTION_BACKLOG.md) P-S12-1/2/3/5/6 |
| Series synthesis | [`session-12-g2.md`](./session-12-g2.md) · [`session-12-g3.md`](./session-12-g3.md) · [`session-12-g4.md`](./session-12-g4.md) · [`session-12-synthesis.md`](./session-12-synthesis.md) |
| Source map | [`../../references/source-map.md`](../../references/source-map.md) |
| Method exemplar | Regime A — METHOD §4 / §13 |

---

## 1. Incident identity

| Field | Value |
|:---|:---|
| Governing issue | #204 |
| Child / slice | Session 12 · Session 6 residual close-out · G1 of 4 |
| Branch | `refactor/204-commit-presentation-quality` |
| Scope of series | multi-group residual (G1–G4); this file = G1 only |
| Planned split | G1 product laws · G2 fixtures · G3 V12-A pack · G4 docs |
| Message-only rebuild? | **yes** (tree preserved) |
| Notes | Not a grouping failure. File split matched plan. G2–G4 homes: `session-12-g2.md` · `session-12-g3.md` · `session-12-g4.md` · dogfood + synthesis (all active full). |

### Rewrite map

| Role | SHA | Subject (short) | Tree OID |
|:---|:---|:---|:---|
| Git-raw | `5117f60ddbedf36041d6b10d0dc1084d6b2458b6` | fallback / process-meta (chore path) | `5e91ec2d…` |
| Gold-final | `4aa90a8fb6d8fa5df166ea6f4ed2f4a34f5c738c` | `feat(commit-quality): add Session 6 scope, capability, and guard laws` | `5e91ec2d…` |

**Rewrite-map-confirmed:** yes (message-only; tree identical)

---

## 2. Git provenance

| Label | Value / notes |
|:---|:---|
| Git-raw | `5117f60` on residual series |
| Git-mid | n/a (single raw tip → gold) |
| Gold-final | `4aa90a8` |
| Tree preserved | **yes** |
| Notes | Series base `2e965c5` → gold tip `3b96ed6`. Scope of this case is G1 only. |

---

## 3. Opik identity

| Field | Value |
|:---|:---|
| Binding status | **bound** |
| Project | `gitCommitGenerator` (`019e7e59-7caf-70a6-8756-f84a55b5d5fd`) |
| Trace ID | `019fda92-4f84-7f28-8b0b-9bd9a346f272` |
| Root span | `019fda92-4f85-72cc-a5da-3495e35d3e4a` (`_run_commit_generation`) |
| Final telemetry span | `019fdaa0-3954-755b-9eff-1a3feb21e95f` / series note `019fda92-4f84-…` family |
| Model | `Youssofal/Qwen3.6-27B-MTPLX-Optimized-Speed` via `127.0.0.1` |
| Time window (UTC) | `2026-08-07T04:54:09Z` → `05:08:35Z` gen · telemetry ~`05:09:21Z` |
| What Opik captured | startup contract, diff extract, semantic health, ranked candidates, locked contract, three attempt prompt/generation/LLM spans, fallback transition, final telemetry counters |
| What Opik did **not** capture | exact bytes written to `.git/COMMIT_EDITMSG` (inferred final labelled where needed) |

> Direct evidence from Opik. Source-path claims verified against product code. **Inferred** rendered text is labelled as such in the body below.

---

# Full-depth forensic body (promoted)

> The sections below are the authoritative G1 reconstruction promoted from comment `5213748048`. Heading levels normalised to package case style. Content substance unchanged.


**Scope for this section:** G1 only. Sibling full-depth cases: [`session-12-g2.md`](./session-12-g2.md), [`session-12-g3.md`](./session-12-g3.md), [`session-12-g4.md`](./session-12-g4.md).

| Field | Value |
| --- | --- |
| Raw tip | `5117f60` |
| Gold tip | `4aa90a8` |
| Diff class | `src/git_cg/commit_quality.py` only |
| Gold subject | `✨ feat(commit-quality): add Session 6 scope, capability, and guard laws` |
| Project | `gitCommitGenerator` (`019e7e59-7caf-70a6-8756-f84a55b5d5fd`) |
| Trace | `019fda92-4f84-7f28-8b0b-9bd9a346f272` (`log_final_commit_telemetry`) |
| Root span | `019fda92-4f85-72cc-a5da-3495e35d3e4a` (`_run_commit_generation`) |
| Window | `2026-08-07T04:54:09Z` → `05:08:35Z` (~14.4 min generation) |
| Final telemetry | `2026-08-07T05:09:21Z` |
| Model | `Youssofal/Qwen3.6-27B-MTPLX-Optimized-Speed` via `127.0.0.1` |

> Direct evidence from Opik. Source-path claims verified against current `main.py` / `commit_quality.py` / `models.py`. **Inferred** rendered text is labelled as such — Opik did **not** capture the exact bytes written to `.git/COMMIT_EDITMSG`.

---

## Executive finding

S12-G1 was not a diff-understanding failure. The system correctly identified a substantive product-code change and the intended dominant posture as a feature. The failure occurred in the presentation orchestration and recovery path:

1. The deterministic contract locked `feature_addition` / `✨` / `feat` / `MINOR` / `Added`.
2. The prompt simultaneously instructed the model to use a `Context:`/`Changes:` body structure.
3. The presentation guard explicitly prohibited that same structure.
4. Regeneration retained the original contract and previous plan instead of changing the conflicting body strategy.
5. The shared regeneration budget was exhausted.
6. The deterministic fallback converted the plan into a `chore`/`NONE` message with process-diagnostic prose.
7. That fallback was treated as a successful final generation and written through the normal commit-message path.

The result was an operator-visible message that did not describe the implementation and instead described the generator’s recovery procedure.

---

## Identity and observed evidence

| Item | Value |
| --- | --- |
| Project | `gitCommitGenerator` |
| Trace | `019fda92-4f84-7f28-8b0b-9bd9a346f272` |
| Root orchestration span | `019fda92-4f85-72cc-a5da-3495e35d3e4a` |
| Root operation | `_run_commit_generation` |
| Root window | `2026-08-07T04:54:09.540633Z` – `05:08:35.149139Z` |
| Diff span | `019fda92-51d2-76e4-a3f1-0177f0712500` |
| Semantic span | `019fda92-5225-7f80-80dc-b4000e0cc8a7` |
| Final telemetry span | `019fdaa0-3954-755b-9eff-1a3feb21e95f` |
| Raw tip | `5117f60` |
| Gold tip | `4aa90a8` |
| Changed path | `src/git_cg/commit_quality.py` |
| Tree relationship | Gold commit changed only the message; the tree was preserved |

The four relevant generation cycles were:

| Cycle | Prompt span | Generation span | LLM span | Approximate result |
| --- | --- | --- | --- | --- |
| 1 | `019fda92-5e91-74b5-b75e-9d2ff3f0bfbe` | `019fda92-5e96-7dab-ac78-765762052121` | `019fda92-5e9a-765f-aad9-cb51149a01b7` | Original `feat` plan with banned body |
| 2 | `019fda94-d17e-730c-a941-959663f64416` | `019fda94-d17f-7a1a-a43b-a2cfc3747546` | `019fda94-d181-7b75-a396-b5943bf5d0a4` | Same plan and same body structure |
| 3 | `019fda96-e93a-72a8-a7a3-78d29fea3e71` | `019fda96-e93b-7529-b0dd-d968a37f4b56` | `019fda96-e93c-76a9-a51c-1cfcb561de8a` | Raw model response remained the prior plan; post-generation fallback produced `chore`/`NONE` |

The final telemetry was recorded separately at approximately `05:09:21 UTC`, after the generation root span had ended:

```json
{
  "provenance": "ai_edited_minor",
  "status": "recorded"
}
```

This provenance value indicates that the resulting message differed from an earlier generated message sufficiently to be classified as a minor AI edit. It does not establish that the final file was corrected to gold, nor does it expose the exact bytes written to `.git/COMMIT_EDITMSG`.

---

## 1. Startup contract (direct Opik)

Root input:

```json
{
  "commit_msg_file": ".git/COMMIT_EDITMSG",
  "engine": "lmlx",
  "dry_run": false,
  "verbose": true,
  "amend_regenerate": false,
  "strict": true,
  "interactive": true,
  "gui_editor": false,
  "enable_semantic": true,
  "gold_strict": true,
  "rank_arbitrate": true,
  "blueprint": null
}
```

Root output: `true` (routine success).

**Observation:** this was a live write path under `gold_strict=true`. Failure is not “tooling down”; it is “accepted wrong message.”

---

## 2. What the diff actually contained

The diff extractor completed successfully. Opik recorded:

```text
src/git_cg/commit_quality.py | 156 ++++++++++++++++++++++++++++++++++++++++++-
1 file changed, 153 insertions(+), 3 deletions(-)
```

Span `019fda92-51d2-76e4-a3f1-0177f0712500` (~30 ms) confirms one product source file and the concrete product deltas:

1. **`INVALID_FINAL_SCOPES`** — rejects package/root/epic-noun scopes (`git_cg`, `src`, `lifecycle`, `contract-lifecycle`, …) when module/behaviour should dominate (V12-A26 / TIP-G7 / TIP-G16).
2. **`CAPABILITY_CONCERN_TAGS`** — capability/schema-add tags (`new_capability`, `operator_visible_capability`, `lifecycle_fields`, `schema_add`, `score_boundary`, `telemetry_schema`) drive feat presentation and MINOR ceiling (TIP-G13 / V12-A39).
3. **Presentation overlay scope repair** — invalid final scopes replaced via force_scope → preferred_scope → priors → dominant product scope → behaviour hint → role fallback.
4. **Three new hallucination guards**
   * `GUARD_EVALUATOR_MUTATION_VERB` (TIP-G14)
   * `GUARD_CONTEXT_CHANGES_TEMPLATE` (TIP-G16 / Session 6)
   * `GUARD_ATTRIBUTION_BLEED` (TIP-G17)

The extracted source itself contains comments identifying these as Session 6 / V12-A behaviour, including references to `TIP-G13`, `TIP-G16`, `TIP-G17`, and the Session 6 module-scope law.

This was therefore not a trivial wording-only change. It was a product-code implementation that expanded the commit-quality policy and guard system.

**No extraction failure.** The system saw the exact laws it later failed to present.

---

## 3. Semantic analysis was successful

Span `019fda92-5225-7f80-80dc-b4000e0cc8a7` (~0.3 ms) recorded:

```text
parser_coverage_ratio: 1.0
parser_fallback_reasons: []
body_similarity_min/avg: 0.999511
fingerprint_class_counts: {structural: 1}
risk_score: 0.6
fallback_reasons: []
```

This matters for the causal assessment:

* Python parsing was not a problem.
* The semantic layer did not fall back.
* The change was classified structurally.
* The implementation was available to the ranking and prompting stages.
* There was no model-server or parser outage.

**Assessment:** semantic understanding was healthy. G1 is not a parser/semantic miss. The later miss therefore cannot reasonably be attributed to an inability to read or parse the diff.

---

## 4. Ranking vs locked contract

From attempt-1 `build_system_prompt` (`019fda92-5e91-74b5-b75e-9d2ff3f0bfbe`):

| Rank | intent_id | score | matrix type | matrix SemVer |
| --- | --- | ---: | --- | --- |
| 1 | `validation_update` | **100.5** | `fix` | `PATCH` |
| 2 | `feature_addition` | **100.0** | `feat` | `MINOR` |
| 3 | `secrets_update` | 62.5 | `chore` | `PATCH` |

Locked contract:

```text
primary_intent_id: feature_addition
gitmoji: ✨
cc_type: feat
semver_impact: MINOR
changelog_group: Added
lock_resolution: accepted
```

Also observed on every prompt build:

* `staged_paths: []`
* `claim_tags: []`
* `concern_tags: null`
* `gold_guidance: null`
* `scoped_history_guidance: null`
* `active_directives: {}`

**Assessment:**

* Ranker preferred validation (`fix`/`PATCH`) by 0.5.
* Contract arbitration forced feature posture (`feat`/`MINOR`).
* Gold later wanted `feat` primary with fix secondaries and final **PATCH** impact — so contract direction was partly right on type, wrong on SemVer ceiling and inventory specificity.
* Empty `staged_paths` / `claim_tags` / `gold_guidance` meant no hard envelope or named-law harvest entered the prompt.
* The principal differences between the correct gold header and the locked contract were not the dominant type or emoji. They were canonical scope spelling (`commit-quality` rather than `commit_quality`), a more precise subject, appropriate secondary fix entries, and final Session 6 SemVer/changelog presentation rules.

The ranking layer therefore supplied a usable starting point. The orchestration layer failed to convert it into a compliant final presentation.

---

## 5. Generation loop — three attempts

### Attempt 1 — first model plan

| Span | Name | Duration |
| --- | --- | --- |
| `019fda92-5e91-...` | `build_system_prompt` | ~2 ms |
| `019fda92-5e96-...` | `generate_commit_message` | ~160.5 s |
| `019fda92-5e9a-...` | `chat_completion_create` | ~160.5 s |

Usage: prompt 6925 / completion 3828 (reasoning 3448) / total 10753.

**Model plan (accepted into generate output):**

```text
✨ feat(commit_quality): add commit message quality validation
SemVer: MINOR | Changelog: Added

Secondary:
- 🦺 fix(scope): enforce valid commit scopes
- 🐛 fix(guards): catch hallucinated commit claims

Body:
Context:
The existing commit quality checks lack strict guards...

Changes:
Defines `INVALID_FINAL_SCOPES` ...
Appends `CAPABILITY_CONCERN_TAGS` ...
Expands hallucination guards ...
```

**What was correct**

* `feature_addition`
* `✨`
* `feat`
* the implementation’s scope and guard responsibilities
* two meaningful secondary responsibilities: scope enforcement and hallucination-claim protection

The model was not inventing unrelated product work. Its rationale explicitly tied the secondary entries to the changed source code.

**What was wrong**

1. **Non-canonical scope** — `commit_quality` vs gold `commit-quality`
2. **Generic subject** — `add commit message quality validation` did not identify the Session 6 scope, capability, and guard laws
3. **Insufficient inventory precision** — secondaries described broad areas but not the named laws expected by gold
4. **Banned body template** — `Context:` / `Changes:` even though Hybrid expects body + `Included changes:` via secondaries
5. **Contract-locked `MINOR`** rather than gold `PATCH`

The model’s own reasoning shows it knowingly followed the low-confidence skeleton that demands Context/Changes prose.

**Key point:** Attempt 1 was a recoverable presentation miss. It was not yet the catastrophic failure. A valid retry could have retained the correct product posture while changing only scope, subject, body wording, and inventory detail.

---

### Attempt 2 — guard finding injected, contradiction preserved

| Span | Name | Duration |
| --- | --- | --- |
| `019fda94-d17e-...` | `build_system_prompt` | ~1 ms |
| `019fda94-d17f-...` | `generate_commit_message` | ~137.1 s |
| `019fda94-d181-...` | `chat_completion_create` | ~137.1 s |

Usage: prompt 7525 / completion 3318 (reasoning 2801) / total 10843.

Retry prompt now contained **both**:

**A. Guard finding (correct):**

```text
[GUARD_CONTEXT_CHANGES_TEMPLATE]
Body uses banned Context:/Changes: template;
prefer Hybrid `Included changes:` via secondary_intents (Session 6).
```

**B. Low-confidence skeleton (contradictory, still present):**

```text
Structure body_summary with Context/Changes prose only.
...
BODY_SUMMARY STRUCTURE ONLY (Context/Changes prose — never final Included changes):
Context:
- Ranking confidence is low for role `mixed`.
...
Changes:
- Summarise the behaviour ...
```

Plus previous-plan delta context that itself still used Context/Changes.

The previous plan was passed back with:

```text
primary_intent: feature_addition
scope: commit_quality
cc_type: feat
semver_impact: MINOR
```

and the same secondary intents.

**Model response:** same header/secondaries; body became bulletized Context/Changes — still banned.

```text
Context:
- Ranking confidence is low for role `mixed`.
- Existing commit quality checks lack ...

Changes:
- Defines `INVALID_FINAL_SCOPES` ...
- Appends `CAPABILITY_CONCERN_TAGS` ...
- Expands hallucination guards ...
```

**Causal point:** regeneration did not remove the instruction that caused the guard. It told the model to repair the banned template while continuing to require that template.

A regeneration loop can only improve output if the next prompt changes the decision boundary. Here, the loop preserved:

* the same locked semantic contract
* the same prior plan
* the same body skeleton
* the same contradictory format rules

The model was therefore being asked to repair a violation while being told to reproduce it. The retry should have done one of the following:

* removed the `Context:`/`Changes:` skeleton entirely
* replaced it with a body policy compatible with the guard
* regenerated from a clean plan rather than preserving the contradictory previous plan
* or bypassed the model and rendered a deterministic, evidence-based conservative message

It did none of these.

---

### Attempt 3 — model still emits banned plan; runtime replaces with fallback

| Span | Name | Duration |
| --- | --- | --- |
| `019fda96-e93a-...` | `build_system_prompt` | ~1 ms |
| `019fda96-e93b-...` | `generate_commit_message` | ~171.8 s |
| `019fda96-e93c-...` | `chat_completion_create` | ~171.8 s |

Usage: prompt 7543 / completion 4295 (reasoning 3729) / total 11838.

**LLM raw content (direct):** still began as:

```text
primary: feature_addition / ✨ / feat / commit_quality
description: add commit message quality validation
semver: MINOR
```

i.e. another Context/Changes-class feat plan (same family as attempts 1–2).

**`generate_commit_message` output (direct, post-processing):**

```json
{
  "primary_intent": {
    "intent_id": "feature_addition",
    "gitmoji": "✨",
    "cc_type": "chore",
    "scope": "commit_quality",
    "description": "apply staged presentation-safe changes",
    "semver_impact": "NONE",
    "changelog_group": "Miscellaneous"
  },
  "secondary_intents": [
    {
      "intent_id": "validation_update",
      "gitmoji": "🦺",
      "cc_type": "fix",
      "scope": "scope",
      "description": "enforce valid commit scopes",
      "semver_impact": "NONE",
      "changelog_group": "Changed"
    },
    {
      "intent_id": "bug_fix",
      "gitmoji": "🐛",
      "cc_type": "fix",
      "scope": "guards",
      "description": "catch hallucinated commit claims",
      "semver_impact": "NONE",
      "changelog_group": "Fixed"
    }
  ],
  "body_summary": "Deterministic presentation fallback after guard exhaustion.\nWording constrained to staged paths and path-class priors.\nCleared guard codes: GUARD_CONTEXT_CHANGES_TEMPLATE.",
  "split_recommended": false,
  "breaking_change": false
}
```

**This is the smoking gun.**

* The model did **not** choose `chore`/`NONE`.
* Deterministic fallback overwrote presentation fields after guard-budget exhaustion.
* Fallback preserved `intent_id=feature_addition` and `gitmoji=✨` while forcing:
  * `cc_type=chore`
  * `semver_impact=NONE`
  * `changelog_group=Miscellaneous`
  * generic subject `apply staged presentation-safe changes`
  * **process-meta body** naming the fallback and cleared guard code
* Thin secondaries from the failed plans were retained.

That created an internally inconsistent plan:

```text
intent_id = feature_addition
gitmoji = ✨
cc_type = chore
semver = NONE
```

The fallback’s own subject admitted that it was describing the act of recovering the message rather than the product change.

**Inferred rendered raw message** (plan-derived; Opik did not store exact `COMMIT_EDITMSG` bytes):

```text
✨ chore(commit_quality): apply staged presentation-safe changes

Deterministic presentation fallback after guard exhaustion.
Wording constrained to staged paths and path-class priors.
Cleared guard codes: GUARD_CONTEXT_CHANGES_TEMPLATE.

Included changes:
- 🦺 fix(scope): enforce valid commit scopes
- 🐛 fix(guards): catch hallucinated commit claims

SemVer-Impact: NONE
Change-Types: chore, fix
Changelog-Groups: Miscellaneous, Changed, Fixed
```

`Refs: #204` is **unconfirmed** in Opik plan spans (depends on issue-reference state at write time). Archive “Raw miss” lines that show `feat(commit_quality): apply staged…` reflect the **operator-visible tip subject after any minor edit / hook interaction**; the **fallback plan itself** locked presentation type to `chore`/`NONE`.

---

## 6. The prompt itself contained a direct contradiction

The first prompt span exposes the central orchestration defect.

It instructed the model that:

* the body should use a `Context:`/`Changes:` structure
* the final message should use `Included changes:` through `secondary_intents`
* `body_summary` must not contain an `Included changes:` heading
* the presentation guard prohibited the `Context:`/`Changes:` template

The low-confidence skeleton explicitly required:

```text
Context:
...
Changes:
...
```

The same prompt family also included the Hybrid rule that the body should not reproduce the included-change inventory and that secondary intents should own the final `Included changes:` section.

This is not merely a model-compliance issue. The model was given incompatible instructions:

```text
body must use Context:/Changes:
```

and later:

```text
Context:/Changes: is banned
```

The second-generation prompt added the guard finding `GUARD_CONTEXT_CHANGES_TEMPLATE` but retained the low-confidence skeleton requiring the same structure. In other words, regeneration added a diagnostic warning without removing the instruction that caused the warning.

---

## 7. The fallback body crossed the operator-facing boundary

The body recorded in the third generation span was:

```text
Deterministic presentation fallback after guard exhaustion.
Wording constrained to staged paths and path-class priors.
Cleared guard codes: GUARD_CONTEXT_CHANGES_TEMPLATE.
```

This is telemetry and diagnostic content, not commit history.

It exposes:

* the internal recovery mechanism
* the fact that the retry budget was exhausted
* the guard code
* the internal path-class strategy

A commit message should describe the repository change, not the generator’s failure state. Even if the fallback had correctly classified the source change, this body would still violate the operator-facing message boundary.

---

## 8. Recovery budget exhaustion was the transition point

The causal sequence is:

```text
Attempt 1:
  valid semantic posture
  invalid Context:/Changes: body
        ↓
guard rejects presentation
        ↓
Attempt 2:
  previous plan retained
  contradictory body skeleton retained
        ↓
guard rejects the same presentation defect
        ↓
Attempt 3:
  model again returns the original feat plan
        ↓
shared regeneration budget exhausted
        ↓
apply_guard_skeleton_fallback(...)
        ↓
fallback changes type/SemVer/subject/body
        ↓
fallback is accepted as a CommitPlan
        ↓
normal render/write path proceeds
```

Source-level flow confirms:

1. Low-confidence guidance required `body_summary` to use **`Context:` / `Changes:`** prose.
2. Gold/presentation guards **ban** that template (`GUARD_CONTEXT_CHANGES_TEMPLATE`).
3. Model followed the low-confidence skeleton on **all three raw attempts**.
4. Guard rejected → retry prompts preserved the previous invalid plan **and** the same contradictory skeleton.
5. Shared guard/gold regen budget (`gold_regen_attempts < 2` in `main.py` ~3347–3412) exhausted.
6. `apply_guard_skeleton_fallback(...)` (`commit_quality.py` ~3514) replaced presentation fields:
   * preserves ranked `intent_id` + gitmoji only
   * path-class priors → generic subject `apply staged presentation-safe changes`
   * deterministic exhaustion prose + optional thin Included stubs
   * this run: **`chore(commit_quality)` / SemVer `NONE` / Changelog `Miscellaneous`**
   * body: *Deterministic presentation fallback after guard exhaustion* · *Wording constrained to staged paths…* · *Cleared guard codes: GUARD_CONTEXT_CHANGES_TEMPLATE*
   * residual secondaries: `fix(scope)` / `fix(guards)` only — **not** the five gold Included lines

The important design failure is not merely that regeneration ended. Exhaustion is an expected operational condition. The defect is that exhaustion selected a diagnostic skeleton as a successful final message rather than causing a fail-closed result.

A correct exhaustion policy should have been:

```text
guard failure after final retry
→ do not write
→ surface the guard and attempted recovery state
→ require manual correction or deterministic safe regeneration
```

An alternative acceptable policy would be a fully conservative renderer that produces a valid message describing only the changed source behaviour. The implemented fallback did neither.

---

## 9. Rendering and write path were routine, not causal

Source-level flow confirms the normal path:

1. A `CommitPlan` is produced.
2. `CommitPlan.render()` (`models.py` ~432–508) constructs the message: header ← primary · body · `Included changes:` ← secondaries · trailers from all intents.
3. The main command renders the result (~3586).
4. `_write_commit_message()` (`main.py` ~890–908; write ~3621) writes the message file.
5. The command returns routine success.

There is no evidence that rendering corrupted a previously valid message. The wrong content was already present in the fallback plan before rendering.

This distinction is important:

* **Plan construction was wrong.**
* **Rendering faithfully materialised that wrong plan.**
* **Writing completed normally.**

The renderer should still have had a final safety check, but the primary defect occurred earlier: the fallback plan was allowed to cross into the normal rendering pipeline.

---

## 10. Telemetry understated the failure

Final span `019fdaa0-3954-755b-9eff-1a3feb21e95f`:

```text
provenance: ai_edited_minor
status: recorded
```

Meaning:

* A message was written and later edited.
* Trailer-stripped similarity remained ≥ ~0.85 versus the AI output (`ai_edited_minor`), **or** the classifier saw only a minor edit at telemetry time.
* This does **not** prove gold compliance.
* Later history rewrite to `4aa90a8` is the gold correction; trees preserved, message replaced.

Thus, the telemetry correctly reported that a message was recorded, but its vocabulary did not distinguish:

```text
successful generation
```

from:

```text
guard exhaustion followed by diagnostic fallback
```

That is a correctness-observability failure.

---

## 11. Gold delta (what G1 should have said)

Gold:

```text
✨ feat(commit-quality): add Session 6 scope, capability, and guard laws

Extend pure presentation policy in commit_quality without touching ranked
intent_id, matrix gitmoji, or SOP scoring. Package/epic scopes
(git_cg, commit-plan, lifecycle, …) are rejected when a dominant module
or behaviour slug exists; CAPABILITY_CONCERN_TAGS promote schema/lifecycle
product diffs to feat with a MINOR ceiling unless correctness tags win.

Hallucination guards gain evaluator mutation verbs (enforce/lift/mutate),
competing Context:/Changes: body templates, and tests/docs attribution
bleed, so residual message-quality failures fail closed before gold.

Included changes:
- ✨ feat(commit-quality): CAPABILITY_CONCERN_TAGS drive feat + MINOR ceiling
- 🦺 fix(commit-quality): INVALID_FINAL_SCOPES → module/behaviour replacement
- 🥅 fix(commit-quality): GUARD_EVALUATOR_MUTATION_VERB on pure test bodies
- 🥅 fix(commit-quality): GUARD_CONTEXT_CHANGES_TEMPLATE for Context:/Changes:
- 🥅 fix(commit-quality): GUARD_ATTRIBUTION_BLEED on tests/docs-only product claims

Refs: #204
SemVer-Impact: PATCH
Change-Types: feat, fix
Changelog-Groups: Added, Fixed
```

Required qualities the raw path missed:

| Dimension | Raw outcome | Gold requirement |
| --- | --- | --- |
| Primary type | fallback `chore` (after failed `feat`) | `feat` |
| Scope | `commit_quality` | `commit-quality` |
| Subject | generic / fallback boilerplate | Session 6 scope + capability + guard laws |
| SemVer | fallback `NONE` (contract had `MINOR`) | `PATCH` (with fix secondaries) |
| Body | process-meta fallback prose | product rationale, no diagnostics |
| Inventory | generic scope/guards secondaries | named laws: invalid scopes, capability tags, evaluator-verb / context-template / attribution guards |
| Guard recovery | accept diagnostic fallback | either valid conservative message or fail closed |

---

## 12. G1-specific root cause

The G1-specific root cause can be stated precisely:

> The low-confidence presentation skeleton required the exact `Context:`/`Changes:` format rejected by the presentation guard. Regeneration retained that contradiction and the prior plan, so the shared guard budget was exhausted without producing a valid candidate. The fallback then converted its internal recovery explanation into an operator-facing commit body and was allowed to proceed through the normal render/write path.

The failure was amplified by a second issue:

> The fallback preserved only the ranked identity and emoji while changing type, SemVer, subject, and body. It therefore produced a hybrid of semantic intent and generic recovery metadata rather than a conservative description of the actual source change.

### Root-cause chain

```text
healthy diff + semantic
→ ranker: validation_update 100.5 vs feature_addition 100.0
→ contract lock: feat + MINOR + Added
→ prompt emits contradictory body policy:
     guard bans Context:/Changes:
     low-confidence skeleton requires Context:/Changes:
→ attempt 1 emits banned template
→ guard fires GUARD_CONTEXT_CHANGES_TEMPLATE
→ retry keeps prior plan + keeps contradictory skeleton
→ attempts 2 and 3 repeat banned template
→ shared regeneration budget exhausted
→ apply_guard_skeleton_fallback(...) rewrites presentation to chore/NONE
   and injects diagnostic body text
→ renderer writes fallback as final commit message
→ command returns success under gold_strict=true
→ telemetry records ai_edited_minor / recorded
```

### Primary defect

**Self-contradictory regeneration policy + operator-visible fallback.**

The system correctly detected `GUARD_CONTEXT_CHANGES_TEMPLATE`, then forced the model to keep producing that template, then laundered exhaustion into a commit message containing internal recovery prose.

### Secondary defects

1. **No authoritative path/module envelope** after contract lock (`staged_paths` empty; scope not normalized to `commit-quality`).
2. **No named-law harvest** from diff symbols / comments (`INVALID_FINAL_SCOPES`, `CAPABILITY_CONCERN_TAGS`, guard codes, TIP/V12 IDs).
3. **SemVer envelope incomplete:** contract forced `MINOR`; gold needed `PATCH` with fix secondaries; fallback jumped to `NONE`.
4. **`gold_strict=true` did not block write** after fallback.
5. **Telemetry provenance ≠ correctness.**

---

## 13. Severity

**Highest in Session 12.**

G2–G4 are wrong-but-clean acceptances.  
G1 is worse: controls fired, recovery destroyed message quality, and the pipeline still succeeded.

Maps to existing IDs: **F72** (fallback as final), **F73** (process meta body leak), **F74** (type/SemVer collapse), **F78** (thin Included), **P-S12-1/2/5**.

---

## 14. Corrective controls for G1

G1 requires controls at three separate boundaries.

### A. Prompt-construction validation

Before calling the model, validate that the assembled prompt does not contain contradictory body rules.

At minimum, reject or rewrite any prompt containing both:

```text
Context:/Changes: required
```

and:

```text
Context:/Changes: prohibited
```

The prompt builder should emit one authoritative body policy, for example:

```text
Use concise rationale prose. Do not use Context:/Changes: headings.
Emit Included changes only through secondary_intents.
```

### B. Regeneration-state validation

A retry must not preserve a previous plan when the guard finding invalidates a structural choice in that plan.

For `GUARD_CONTEXT_CHANGES_TEMPLATE`:

* clear or replace `body_summary`
* remove the contradictory skeleton
* preserve semantic fields only if they remain valid
* do not tell the model to retain the prior body structure

The retry prompt should explicitly state that the body format has changed, rather than merely appending a warning.

### C. Fail-closed fallback

The fallback must never emit:

* `Deterministic presentation fallback`
* `guard exhaustion`
* `Cleared guard codes`
* `path-class priors`
* internal guard identifiers
* retry or regeneration state

If a valid conservative message cannot be constructed, the command must refuse to write and return a structured failure.

A safe fallback for this diff would have needed to remain anchored to the implementation, for example:

```text
✨ feat(commit-quality): add Session 6 scope and guard laws

Add Session 6 scope and capability rules to constrain presentation choices.

Included changes:
- 🦺 fix(commit-quality): reject invalid final scopes
- 🐛 fix(commit-quality): guard evaluator and attribution claims
```

The precise final wording would still require the project’s gold envelope, but it must describe the source change rather than the fallback machinery.

### Required fixes implied by G1 evidence

1. **Remove the contradiction** — low-confidence body skeleton must not request `Context:`/`Changes:` while that template is a hard guard.
2. **Fallback must not be operator-facing diagnostics** — ban body text matching `Deterministic presentation fallback`, `Cleared guard codes:`, and other process-meta recovery strings.
3. **Fail closed on guard-budget exhaustion when `gold_strict=true`** — do not write chore/NONE boilerplate as a successful commit.
4. **Post-render hard checks before write**
   * scope canonicalization (`commit-quality`)
   * no process-meta prose
   * no banned body template
   * required symbol/law inventory present
   * SemVer/type envelope consistent with path class + secondaries
5. **Populate prompt evidence channels that were empty here**
   * `staged_paths`
   * `claim_tags` / concern tags
   * gold guidance when `gold_strict=true`

---

## 15. Final G1 assessment

S12-G1 is the most severe Session 12 failure because the system did detect the presentation defect, yet the recovery path made the result worse and still reported routine completion.

The causal chain is fully supported by the Opik evidence:

* successful extraction: `019fda92-51d2-76e4-a3f1-0177f0712500`
* successful semantic analysis: `019fda92-5225-7f80-80dc-b4000e0cc8a7`
* original contract-following model output: `019fda92-5e96-7dab-ac78-765762052121`
* unchanged retry plan: `019fda94-d17f-7a1a-a43b-a2cfc3747546`
* contradictory retry prompt: `019fda94-d17e-730c-a941-959663f64416`
* model still returning the original posture on Attempt 3: `019fda96-e93c-76a9-a51c-1cfcb561de8a`
* fallback-generated `chore`/`NONE` plan: `019fda96-e93b-7529-b0dd-d968a37f4b56`
* routine telemetry despite the miss: `019fdaa0-3954-755b-9eff-1a3feb21e95f`

Therefore, G1 was caused by **contradictory presentation instructions combined with non-fail-closed guard recovery**, not by semantic analysis, Git extraction, the local model’s availability, rendering, or file writing.

### Evidence confidence

| Claim | Confidence | Basis |
| --- | --- | --- |
| Diff/semantic healthy | **Direct** | Opik spans |
| Contract locked feat/MINOR | **Direct** | prompt inputs |
| Attempts 1–2 banned template | **Direct** | generate + LLM spans |
| Prompt contradiction (ban + require Context/Changes) | **Direct** | attempt 2/3 prompt text |
| Attempt 3 model still feat/MINOR | **Direct** | LLM span content prefix |
| Final plan is deterministic fallback | **Direct** | generate span output vs LLM output mismatch |
| Exact COMMIT_EDITMSG bytes | **Reconstructed** | from final plan; not stored in Opik |
| `ai_edited_minor` means minor human edit, not gold | **Direct classification, inferred meaning** | telemetry + later rewrite |

---

## Stop point (G1)

**S12-G1 is complete at full depth in this archive.**

---

---

## Package cross-links

| Need | Link |
|:---|:---|
| Series systems reading | [`session-12-g2.md`](./session-12-g2.md) · [`session-12-g3.md`](./session-12-g3.md) · [`session-12-g4.md`](./session-12-g4.md) · [`session-12-synthesis.md`](./session-12-synthesis.md) |
| Later Regime B self-dogfood on this package | [`quality-package-regime-b.md`](./quality-package-regime-b.md) |
| F72–F80 registry | [`../../FAILURE_TAXONOMY.md`](../../FAILURE_TAXONOMY.md) |
| P-S12-1…9 registry | [`../../PREVENTION_BACKLOG.md`](../../PREVENTION_BACKLOG.md) |
| METHOD Regime A mapping | [`../../METHOD.md`](../../METHOD.md) §4 · §13 |
| Eval consumer plan | [`../../../plans/opik-evaluation-harness.md`](../../../plans/opik-evaluation-harness.md) |
| Archive intake (non-SSOT) | [comment 5213748048](https://github.com/Thomo1318/gitCommitGenerator/issues/204#issuecomment-5213748048) |

### Promotion record

| Field | Value |
|:---|:---|
| Promoted on | 2026-08-13 |
| From | #204 comment `5213748048` · G1 `<details>` body |
| Sibling status | G2–G4 + dogfood promoted to package SSOT (`session-12-g2.md` · `session-12-g3.md` · `session-12-g4.md` · `session-12-dogfood-g2-g4.md`) |
| SSOT rule | Package path wins over GitHub comment after promote |

---

## Document control

| Field | Value |
|:---|:---|
| Case ID | 204-S12-G1 |
| Package version | `1.0.0-combine` |
| Status | active / full |
| Last updated | 2026-08-13 |
