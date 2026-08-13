# Provenance and confidence

> Package version: `1.0.0-combine`  
> Method: [`../METHOD.md`](../METHOD.md) §§6–7

## Git provenance labels

| Label | Meaning |
|:---|:---|
| `Git-raw` | First generator (or first observed bad) tip |
| `Git-mid` | Intermediate rewrite before gold |
| `Gold-final` | Accepted gold tip |
| `Rewrite-map-confirmed` | Same tree OID raw→gold |
| `Opik-unbound` | No trustworthy Opik bind |

## Confidence labels

| Label | Meaning | Allowed use |
|:---|:---|:---|
| **Direct** | Read from git object, Opik span, or product log | Unqualified claims |
| **Reconstructed** | Inferred (e.g. plan→bytes not stored) | Must be labelled in prose and matrix |

## Rules

1. Every full case has a confidence matrix.  
2. Exact `COMMIT_EDITMSG` bytes are **Reconstructed** unless git object or capture proves them.  
3. Never invent trace/span IDs.  
4. `Opik-unbound` is valid; silent omission is not.  
5. Post-control dogfood cases should still bind Opik when the lab run produced traces.
