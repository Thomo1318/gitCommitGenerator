# CROSS_COMMIT_SYNTHESIS_TEMPLATE

> Use when a series has **≥2** gold-miss groups.  
> Method: [`../METHOD.md`](../METHOD.md) §4 regimes + Session 12 synthesis pattern.  
> Package version: `1.0.0-combine`

```yaml
package: commit-message-failure-analysis
doc: cross-commit-synthesis
version: 1.0.0-combine
status: draft
issue: 0
series_id: ISSUE-Sxx
regime_mix: A+B
last_updated: YYYY-MM-DD
```

---

## 0. Open summary

**Result:**  
**Class mix:** e.g. one Regime A + N Regime B  
**Base → gold tip:**  
**Trees preserved per tip:**  
**One-line series diagnosis:**  
**IDs covered:**  

| Group | Path focus | Severity | Regime | Gold subject (short) | Case link |
|:---|:---|:---|:---|:---|:---|
| G1 | | | A/B | | |
| G2 | | | | | |

---

## 1. Series identity map

| Field | G1 | G2 | G3 | G4 |
|:---|:---|:---|:---|:---|
| Raw SHA | | | | |
| Gold SHA | | | | |
| Tree OID | | | | |
| Library class | | | | |
| Acceptance mode | | | | |
| gold_strict | | | | |
| Opik bind | | | | |

### Observed subjects (do not regress)

```text
Gx ❌  <raw subject>
Gx ✅  <gold subject>
```

---

## 2. Regime split

### Regime A tips

List + shared chain + F/P cluster.

### Regime B tips

List + shared chain + F/P cluster.

### Shared process defects

e.g. F80 prepare re-entry across rebuild tips.

---

## 3. Comparative matrix

| Dimension | G1 raw | G2 raw | … | Gold law |
|:---|:---|:---|:---|:---|
| type | | | | |
| SemVer | | | | |
| scope | | | | |
| inventory | | | | |
| attribution | | | | |
| acceptance | | | | |

### Ranking contamination pattern (if Regime B)

| Group | Winning intent | Score | Expected family | Notes |
|:---|:---|:---|:---|:---|
| | | | | |

### Signal poison sources

| Group | Source | False markers |
|:---|:---|:---|:---|
| | | |

---

## 4. Failure ID map across series

| ID | Mode | G1 | G2 | … | Prevention |
|:---|:---|:---:|:---:|:---:|:---|
| F… | | ● | | | P… |

Call out series-wide IDs (e.g. F78 on all tips).

---

## 5. Prevention rules (systems reading)

| P* | Rule | Blocks | Evidence tips |
|:---|:---|:---|:---|
| | | | |

---

## 6. Why tips are not “the same bug”

Contrast Regime A vs B in this series (controls fired vs never fired).

---

## 7. Dogfood / residual irony (if any)

What was supposed to be proven vs what still failed.

---

## 8. Root causes (series-level)

| RC | Statement | Tips |
|:---|:---|:---|
| RC1 | | |
| RC2 | | |

---

## 9. Acceptance tests for the series

Checklist the product/eval must gain before series can close.

1.  
2.  
3.  

---

## 10. Priority order for fixes

1.  
2.  
3.  

---

## 11. Source map

| Group | Full-depth case | GitHub | Opik |
|:---|:---|:---|:---|
| | | | |
