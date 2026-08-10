# Accept-path fixtures (Issue #212)

Frozen dogfood evidence from 2026-08-09 MTPLX 2.5.4 accept-path runs.

These fixtures exist so implementers are **not** dependent on ephemeral `/tmp` paths.

> **Commit gate:** this tree must be committed in a **standalone commit before any #212 source edit**. Deterministic APC-A/B/C tests must assert against the committed tree, not a floating working copy.

## Cases

| Directory | Envelope | Observed failure (2026-08-09) | Close gate? |
|:---|:---|:---|:---|
| `docs-only/` | `docs/usage.md` checklist | `path_class_gate=empty`, contract `secrets_update`, 🔐 chore PATCH | **Yes** |
| `product-source/` | `src/demo/greeter.py` optional kw-only default + `greet_many` | `path_class_gate=empty`, false `breaking_change` / MAJOR | **Yes** |
| `tests-only/` | `tests/test_mathy.py` edge tests | `path_class_gate=empty`, false `breaking_change` / MAJOR | **Yes** |
| `gold-trigger/` | `src/demo/util.py` normalize helpers + vague docs | `path_class_gate=empty`, false MAJOR; gold `not_needed` | **Yes** (path/contract; gold not spine) |
| `lmlx-docs-compare/` | LMLX docs twin (partial artifact set) | same quality class as docs-only; slower | **No** — informational only |
| `_suite/` | suite rollup metadata | product/tests/gold rollup | metadata |

## Minimum files per close-gate case

* `staged.diff` — staged patch used for deterministic classification tests
* `COMMIT_EDITMSG` — observed generated message
* `GIT_CG_OPIK_STATE.json` and/or `telemetry-extract.txt` — observed telemetry
* `summary.txt` / CLI logs when present

`lmlx-docs-compare/` is an informational twin of `docs-only/` with full artifact parity for bakeoff compare. Do **not** block #212 close on LMLX outcomes.

## Expected triples after #212 (law)

| Case | Expected intent / type | Expected SemVer | Expected `path_class_gate` | Required assertion surface |
|:---|:---|:---|:---|:---|
| docs-only | docs family; **not** `secrets_update` | `NONE` under docs envelope | `docs_only` | **Must** assert `path_class_gate`, `intent_id != secrets_update`, forced/final `cc_type=docs`, forced/final `semver=NONE`, and constraint note `docs_only_force_docs_none`. Gitmoji is matrix-derived from intent — prefer asserting intent/constraints over hard-coding 📖 vs 🔐 glyphs. |
| product-source | non-breaking `feat` | `MINOR` | `product_src` | `intent_id`/feat family + `semver=MINOR` + gate |
| tests-only | `test` | `NONE` | `tests_only` | `intent_id`/test family + `semver=NONE` + gate |
| gold-trigger | non-forced-MAJOR per SOP/envelope | not MAJOR without true break evidence | `product_src` | gate + non-MAJOR without break evidence; gold may stay `not_needed` |

### Docs security negative (required)

Empty-class already sets `forbid_security_primary=True` but does **not** force docs cc/semver. Live dogfood still locked `secrets_update` under `path_class_gate=empty`, so `forbid_security` on empty is **not** a sufficient substitute for a real `docs_only` force. Tests must prove docs-only cannot resolve `secrets_update`.

Gold remains a **validator**, not close-spine authority.

## Provenance

* Original live paths (may rot):
  * `/tmp/git-cg-acceptpath-mtplx-20260809-142925`
  * `/tmp/git-cg-acceptpath-mtplx-suite-20260809-143832/`
  * `/tmp/git-cg-acceptpath-sop-20260809-122933`
* Captured into repo working tree: 2026-08-09 (Australia/Sydney)
* Branch/HEAD reference: `refactor/204-commit-presentation-quality` @ `e9c2864`
* Parent: #204 · Residual: #212

## Usage

Deterministic tests should prefer these committed files over `/tmp`.
Live MTPLX re-dogfood is operator confirmation only, not the merge gate.


## Shared pack API

Import ``tests/acceptpath_pack.py`` (module ``acceptpath_pack`` on ``sys.path`` via pytest root) for bakeoffs:

```python
from acceptpath_pack import iter_close_gate_cases, staged_diff, assert_pack_integrity

assert_pack_integrity()
for case in iter_close_gate_cases():
    diff = case.staged_diff()
    envelope = case.expected_envelope()
```

Close-gate cases remain the four MTPLX envelopes. ``lmlx-docs-compare`` is informational only.
