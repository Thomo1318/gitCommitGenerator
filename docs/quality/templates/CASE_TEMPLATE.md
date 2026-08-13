# CASE_TEMPLATE — gold-miss case

> **Copy this file** to `docs/quality/cases/<issue>/<slug>.md`.  
> **Do not** leave placeholders in promoted SSOT.  
> **Method:** [`../METHOD.md`](../METHOD.md)  
> **Package version:** `1.0.0-combine`

```yaml
package: commit-message-failure-analysis
doc: case
version: 1.0.0-combine
status: draft
issue: 0
case_id: ISSUE-Gn
series_class: residual-close-out  # precursor | implementation-dogfood | residual-close-out | post-control-dogfood | forward
regime: B  # A | B | A+B
opik: unbound  # bound | unbound
sources: []
last_updated: YYYY-MM-DD
```

---

## 0. Open summary

**Result:** MISS gold · Regime `<A|B|A+B>`  
**Path focus:**  
**Severity:** Critical | High | Medium | Low  
**Raw → gold:** `<raw_sha>` → `<gold_sha>` (tree preserved: yes/no · tree OID: `<oid>`)  
**Branch / base→tip:** `<branch>` · `<base>` → `<tip>`  
**One-line diagnosis:**  
**IDs:** F… · P… · TIP… / V12-A… (if any)  
**Series class:**  

| Field | Value |
|:---|:---|
| Issue | # |
| Case ID | |
| Reviewer | |
| Date | |
| Library class (intended) | tests-only / fixtures / docs / product_src / mixed / … |
| Acceptance mode (raw) | ai_accepted / fallback / ai_edited_minor / … |

---

## 1. Incident identity

| Field | Value |
|:---|:---|
| Governing issue | |
| Child / slice (if any) | |
| Branch | |
| Scope of series | single tip / multi-group |
| Planned split (if multi) | |
| Message-only rebuild? | yes/no |
| Notes | |

### Rewrite map

| Role | SHA | Subject (short) | Tree OID |
|:---|:---|:---|:---|
| Git-raw | | | |
| Git-mid (optional) | | | |
| Gold-final | | | |

**Rewrite-map-confirmed:** yes/no  

---

## 2. Git provenance

| Label | Value / notes |
|:---|:---|
| Git-raw | |
| Git-mid | |
| Gold-final | |
| Tree preserved | |
| Notes | |

---

## 3. Opik identity

> If no bind: set **Opik-unbound** and stop inventing spans.

| Field | Value |
|:---|:---|
| Binding status | bound / **Opik-unbound** |
| Reason if unbound | |
| Project | |
| Trace ID | |
| Root span | |
| Generation / LLM spans | |
| Final / telemetry span | |
| Model | |
| Time window (UTC) | |
| What Opik captured | plans / final_commit_plan / not COMMIT_EDITMSG bytes / … |
| What Opik did **not** capture | |

---

## 4. Evidence confidence matrix

| Claim | Confidence | Basis |
|:---|:---|:---|
| Diff / path set | Direct / Reconstructed | |
| Semantic signals | | |
| Ranking + scores | | |
| Locked contract | | |
| Prompt policy / skeleton | | |
| Attempt N plans | | |
| Fallback reason / body | | |
| Exact final message bytes | | |
| gold_strict findings | | |
| Hook / prepare re-entry | | |
| Telemetry counters | | |

---

## 5. Executive finding

State what failed **in the pipeline** (stage + mechanism), not only the wrong subject.

1.  
2.  
3.  
4.  

---

## 6. Diff truth

### Paths (raw commit)

```text
# paste --name-status or path list
```

### Library classification

| Question | Answer |
|:---|:---|
| Intended diff class | |
| GOLD_STANDARD default type | |
| GOLD_STANDARD default SemVer | |
| GOLD_STANDARD changelog family | |
| Dominant module / scope canon | |
| Stable IDs that must appear in inventory | TIP-G… / V12-A… / GUARD_* / schema pins / … |
| High-risk body contract required? | yes/no — which |

### Semantic health (extractor)

| Check | Outcome |
|:---|:---|
| Diff extract completed | |
| False capability / validation / secret / runtime markers? | |
| Fixture/prose contamination? | |
| `path_class_gate` | empty / value |
| `staged_paths` | empty / value |
| claim_tags / gold_guidance | empty / value |

---

## 7. Ranking vs locked contract

| Intent / signal | Score | Notes |
|:---|:---|:---|
| top-1 | | |
| top-2 | | |
| expected gold family | | |

| Contract field | Locked value | Gold expectation | Match? |
|:---|:---|:---|:---|
| type | | | |
| emoji / intent_id | | | |
| SemVer | | | |
| changelog | | | |
| scope (if locked) | | | |

Arbitration skipped? yes/no — why  

---

## 8. Attempt loop / fallback / clean-accept

### Attempts

| Attempt | What model emitted | Guards / findings | Retained state | Outcome |
|:---:|:---|:---|:---|:---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| Final | | | | |

### Final path

| Field | Value |
|:---|:---|
| Path class | Regime A fallback / Regime B clean accept / mixed |
| `presentation_fallback_reason` | none / … |
| Acceptance mode | |
| Normalisers applied | |

---

## 9. Prompt and evidence-channel defects

| Channel | Observed | Should have been |
|:---|:---|:---|
| path_class_gate | | |
| staged_paths | | |
| gold_guidance | | |
| claim_tags / TIP harvest | | |
| low-confidence skeleton | | |
| body template policy | | |
| contradictions (if any) | | |

---

## 10. Raw ↔ gold dimension table

| Dimension | Raw | Gold | Miss? |
|:---|:---|:---|:---|
| Primary type | | | |
| Scope | | | |
| Subject | | | |
| SemVer-Impact | | | |
| Change-Types | | | |
| Changelog-Groups | | | |
| Body contract | | | |
| Process-meta leak | | | |
| Included changes | | | |
| Attribution | | | |
| Issue trailer | | | |
| Acceptance mode | | | |

### Raw message (exact if known)

```text
```

### Gold message (exact)

```text
```

---

## 11. Root-cause chain

```text
diff/extract
→ …
→ first divergence: <stage>
→ …
→ irreversible miss: <stage>
→ write/accept
→ telemetry
```

### Primary defect

**…**

### Secondary defects

1.  
2.  
3.  

---

## 12. Failure and prevention IDs

| ID | Applies? | Notes |
|:---|:---:|:---|
| F… | ● | |
| R… | | |
| P… | | |

Only IDs registered in [`FAILURE_TAXONOMY.md`](../FAILURE_TAXONOMY.md) / [`PREVENTION_BACKLOG.md`](../PREVENTION_BACKLOG.md) (mint rows if new).

---

## 13. Accept path, gold_strict, hooks

| Check | Observed | Required |
|:---|:---|:---|
| gold_strict | on/off · findings N | fail closed on … |
| fallback as final allowed? | | **no** (P-S12-1) |
| process-meta body | | **no** (P-S12-2) |
| prepare-commit-msg re-entry | | P-S12-9 / message-only process |
| telemetry label vs truth | | must not launder |

---

## 14. Corrective controls and tests

### Controls (by boundary)

| Boundary | Control | P* | Status |
|:---|:---|:---|:---|
| path-class envelope | | | |
| signal quarantine | | | |
| prompt construction | | | |
| regen state | | | |
| fallback fail-closed | | | |
| inventory / stable-id harvest | | | |
| gold_strict | | | |
| hooks / message-only | | | |
| telemetry honesty | | | |

### Regression tests / fixtures

| Test or fixture | Path | Covers |
|:---|:---|:---|
| | | |

### Eval harness linkage (if any)

| Item | Value |
|:---|:---|
| session tags | e.g. `session-12-seed` |
| metric families | |
| expected codes | |

---

## 15. Final assessment

| Field | Value |
|:---|:---|
| Severity in series | |
| Regime confidence | |
| Residual risk | |
| Blocks release / epic? | yes/no |
| Follow-ups | |

---

## 16. Cross-commit synthesis

> Delete this section for single-tip cases.  
> For ≥2 groups, complete [`CROSS_COMMIT_SYNTHESIS_TEMPLATE.md`](./CROSS_COMMIT_SYNTHESIS_TEMPLATE.md) or link the series synthesis case.

**Link:**  

---

## 17. Source map

| Kind | Ref |
|:---|:---|
| GitHub comment | |
| Opik trace | |
| Local notes | |
| Related cases | |
