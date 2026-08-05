# Scoped-history fixtures (Phase 9 / Issue #163)

Deterministic inputs for `git_cg.scoped_history` producers. Fixtures are **advisory
evidence only** — they never authorise `intent_id` / gitmoji / SemVer / changelog.

## Behavior matrix

| Fixture set | Inputs | Expected producer outcome | Disposition |
| --- | --- | --- | --- |
| **Flow disjoint** | `flow_disjoint_flows.json` + `flow_disjoint_staged.txt` | `split_high_confidence=True`; rationale mentions flow-disjoint partition (auth vs billing) | **keep** |
| **Flow overlap** | `flow_overlap_flows.json` + `flow_overlap_staged.txt` | `split_high_confidence=False` (shared flow component) | **keep** |
| **Rename identical** | `rename_old.py` → `rename_new.py` (same body) | `rename_confidence=high` when paired as a git rename with identical bytes/`code_fp` | **keep** |
| **Structural error** | `structural_error.py` | `structural_error_handling=True`, `structural_public_api=True` under semantic-ON | **keep** |
| **Structural CLI** | `structural_cli.py` | `structural_new_command=True` (typer/`@app.command`) + public API marker | **keep** |

### Flow partition rules

* Staged files are projected through `extract_file_to_flow_ids` (CRG payload shapes A/B/C).
* High-confidence split requires **≥2 flow-disjoint connected components** among staged files that carry flow evidence (or `preflight_groups_count ≥ 2` as an alternate signal).
* Shared membership collapses to a single component → no high-confidence split.

### Rename bands (per pair)

| Signals | Band |
| --- | --- |
| git rename ∧ (`code_fp` match ∨ body_sim ≥ 0.85) | `high` |
| git rename without full corroboration | `medium` |
| weak single-signal similarity only | `low` |
| no usable signal / semantic-off | `none` |

### Structural markers

* Closed vocabulary only: `structural_error_handling`, `structural_public_api`, `structural_new_command`.
* Fail-open on parser/import errors (all `False`).
* `new_command` requires structural decorator/call evidence **and** a lexical CLI hint (e.g. `typer`, `click`, `@app.command`).

### Disposition legend

* **keep** — fixture is part of the Phase 9 regression pack; do not delete-after.
* **delete-after** — reserved for ephemeral scratch inputs (none checked in here).

## Claim IDs exercised

| Claim | Coverage via fixtures / unit tests |
| --- | --- |
| P9-B01 | Flow disjoint / overlap split evidence |
| P9-B02 | Preflight multi-group split (unit) |
| P9-B04 / P9-B05 | Rename high / none bands |
| P9-B08 / P9-B09 | Authority untouched + OR-merge (unit) |
| P9-B10 | Channel-4 guidance bans (unit + `test_main`) |
| P9-B11 / P9-B12 | Structural error + CLI markers |
