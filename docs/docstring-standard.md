# git-cg Contract Docstring Standard

> **Status:** active house standard (ratifies de facto practice)  
> **Scope:** first-party Python under `src/git_cg/`  
> **Baseline:** [PEP 257](https://peps.python.org/pep-0257/)  
> **Structured sections (when used):** [Google style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings) `Args` / `Returns` / `Raises` / `Attributes`  
> **Coverage gate:** [`interrogate`](https://interrogate.readthedocs.io/) ≥ **80%** on **changed** `src/git_cg/**/*.py` (patch-scoped CI); full-tree badge is informational  
> **Related:** [Development Guide — docstring coverage](./DEVELOPMENT.md#docstring-coverage-interrogate) · S7 API-surface policy (CLI-first; curated contracts; no full-package autodoc)

This document names the project docstring standard so reviews stop grading the tree as “incomplete Google Style.”

**Name:** Contract Docstring Standard  
**Not the standard:** NumPy section underlines, Sphinx `:param:`/`:type:` field lists as default, Epytext `@param`, Markdown `### Arguments` blocks inside source docstrings, or “Google sections on every function.”

---

## One-line rule

> Write **contracts and invariants**, not signature narration.  
> Use **Google sections only when behaviour is not obvious from names + types**.  
> **Presence is gated; template shape is not.**

---

## Documentation system (where truth lives)

| Layer | Home | Role |
|:---|:---|:---|
| Operator UX | Typer help, `docs/eval/operator_api_map.md`, usage docs | Human command discovery |
| Durable product/eval law | ADRs, `docs/eval/*`, quality package | Behavioural SSOT outside code |
| Source contracts | Module / public / private docstrings | Invariants, authority, failure classes next to implementation |
| Optional signature pages | S7 allowlisted `mkdocstrings` only | Subordinate to hand-written contracts — never full-tree autodoc |

Source docstrings **complement** curated docs. They do not replace the API map, and they must not pretend internals are a public SDK.

---

## Tiers

### Tier 0 — Modules (crown jewel)

**Required** for non-trivial modules (engines, stores, CLI-facing libraries, security/secret/telemetry boundaries).

Module docstrings should state:

1. **Purpose & scope** — what operator/surface/subsystem this is  
2. **Invariants & forbidden behaviour** — fail-closed rules, authority limits, non-goals  
3. **Boundary laws** when relevant — offline/network, secret-safe projection, accept/rank/gold non-mutation, import-light / lazy heavy deps  
4. **Anchors** as needed — issue/slice/FIND/INT references belong here or in the body, not in CLI summary lines  

High-risk eval modules (`doctor`, `promote`, `diagnose`, `explain`, …) are the reference examples: law-first narrative, sometimes ASCII state machines, explicit “never …” lists.

**Do not** hollow out module law blocks to make room for per-function template sections.

### Tier 1 — Public functions & classes

**Required:**

* PEP 257 summary line: concise, usually imperative, ends with a period  
* Types on the signature carry the parameter/return schema (Python 3.14 syntax)  
* Body text for non-obvious **side effects**, **failure classes**, **authority**, or **idempotency**

**Google sections are optional escalation**, not the default. Add `Args` / `Returns` / `Raises` / `Attributes` when **at least one** holds:

| Trigger | Examples |
|:---|:---|
| Behaviour ≠ names/types | Units, ordering, default authority, path root semantics |
| Multiple outcomes | Exit-code classes, envelope vs raise, soft vs hard fail |
| Supported library export | Surfaces S7 may document / allowlist — not every internal engine function |
| Non-obvious raises | Part of a supported failure taxonomy callers must handle |
| Dataclass fields need law | Only when field meaning/invariants are not obvious from names + types |

**Prefer not** to add Google sections when they only restate `repo_root: Path` → “repository root path.”

### Tier 2 — Private helpers (`_name`)

**Default:** one line when the helper encodes law, edge behaviour, or a non-obvious predicate.  
**Skip** only when the name + types are complete and the body is pure/obvious.  
**Coverage still counts:** private helpers are included by interrogate (`ignore-private = false`). Prefer a short true docstring over a fake `Args` block.

Good private docs name the **law** (“fingerprint excludes trace/time/raw URL”) rather than the mechanics (“loop over items”).

### Tier 3 — CLI command docstrings (Typer)

The function docstring **is** `--help`.

| Rule | Detail |
|:---|:---|
| First line = operator UX | Active, human summary of what the command does |
| No RFC alphabet soup on line 1 | Avoid leading with `S6-E09`, `INT-44`, `FIND-026`, issue numbers |
| Citations in the body | Slice/issue/law references after the summary |
| Options | Prefer `typer.Option(help=...)` for flag help; docstring explains command-level behaviour |

Library/engine modules may lead with issue/slice context; **CLI modules must not** sacrifice the summary line for that metadata.

---

## Style choices (explicit)

| Choice | House position |
|:---|:---|
| PEP 257 structure | **Required baseline** |
| Google `Args`/`Returns`/`Raises` | **Preferred section syntax when sections are warranted** |
| NumPy dashed sections | **Not used** |
| Sphinx `:param:` / `:type:` | **Not default** (type echo); occasional `:func:` / `` short refs`` OK |
| Epytext `@param` | **Not used** |
| Markdown `### Arguments` in code | **Not used** — Markdown belongs in `docs/`, not as the in-source template |
| Inline comments | **Why / trade-off**, not narrating the next line |
| Restating the signature in prose | **Forbidden as padding** |

---

## Worked patterns

### Module (law-first — preferred for engines)

```python
"""S6 Slice 4 offline doctors (Issue #246).

Two distinct, network-free operator surfaces:

* :func:`run_local_doctor` — ``git-cg eval doctor``: ...
* :func:`run_opik_doctor` — ``git-cg eval opik doctor``: secret-safe ...

Doctor is observability-only. It never mutates product accept, ranking, golden
promotion, or Families A–I authority. ``h.doctor_green`` aggregates
**block-severity** checks only; warn-severity failures never flip green to red.

Import law: import-light. Heavy helpers are lazy inside functions.
"""
```

### Public function without Google sections (default when types suffice)

```python
def run_local_doctor(
    *,
    repo_root: Path,
    suite_id: str = "cm-eval-fixtures-core",
    fixture_root: Path | None = None,
    max_eval_bytes: int | None = None,
) -> DoctorReport:
    """Offline local doctor. Network-free; fail-closed on floating pins.

    Produces checks across pin integrity, suite/fixture load, FIND-026/027/028
    guards, and checkpoint compatibility; projects phantom metrics and
    aggregates ``h.doctor_green``.
    """
```

### Public function with selective Google sections (when escalation triggers fire)

```python
def promote(repo: Path, *, dry_run: bool = False, ...) -> dict[str, Any]:
    """Run one promotion decision through the closed state machine.

    Denied candidates persist candidate-class audit rows and never mint
    fixture/gold. ``dry_run`` validates and previews without writes.

    Args:
        repo: Repository root containing Layer-A ``.eval/`` stores.
        dry_run: When True, perform denial/acceptance preview with zero
            persistence of audit rows or destination artifacts.

    Returns:
        Decision payload including destination, acceptance bit, and paths
        (paths may be omitted or null when ``dry_run`` is True).

    Raises:
        PromoteError: Named ``denial_reason`` closed taxonomy; fail-closed.
    """
```

### Private helper

```python
def _is_pinned(pin: Any) -> bool:
    """True when ``pin`` is a well-formed content pin (not floating/latest)."""
```

### CLI command

```python
@eval_app.command("promote")
def promote_cmd(...) -> None:
    """Promote a scrubbed candidate into a governed destination.

    Enforces provenance, redaction, split-group contamination checks, and the
    closed denial taxonomy (S6-E09). Refuses silent or human-sole gold mint.
    """
```

---

## Anti-patterns (reject in review)

1. **Google theatre** — `Args`/`Returns` that only echo names and annotations  
2. **Attributes walls** on obvious frozen dataclasses / `to_dict` serializers  
3. **Raising fictional exceptions** in `Raises:` that the code path does not use  
4. **CLI summary pollution** — first line is issue/RFC catalogue  
5. **Diluting module invariants** to chase section symmetry  
6. **Coverage stubs** — meaningless one-word docs to satisfy interrogate  
7. **Autodoc pressure** — documenting internal modules as if they were public SDK  
8. **Style thrash** — reformatting whole packages to Google during unrelated feature work  

---

## Coverage & tooling

| Mechanism | Behaviour |
|:---|:---|
| CI patch gate | Changed `src/git_cg/**/*.py` only; `fail-under` 80; Python **3.14** mandatory |
| Full-tree scan | Informational health + README badge via `just docstrings` |
| Config | `[tool.interrogate]` in `pyproject.toml` (`ignore-private = false`, excludes `src/git_cg/evals`) |
| Commands | `just docstrings-patch` · `just docstrings` (see Development Guide) |
| Ruff pydocstyle Google enforcement | **Not enabled** as a repo-wide shape gate (by design) |

**Stretch goal (not merge gate):** raise docstring quality on touched state-machine modules with real one-liners (promote/replay/orchestrator helpers), aiming toward healthier full-tree percentages without stub spam.

When fixing coverage: **document the law or edge**, or extract/rename until the name is the doc. Do not bulk-insert empty Google templates.

---

## Adoption rules for authors & reviewers

### New / amended code

1. Module touched non-trivially → refresh Tier 0 invariants if behaviour/authority changed  
2. New public entrypoint → Tier 1 summary + side effects; add Google sections only on triggers  
3. New private helper with law/edge → one-line Tier 2 doc  
4. New Typer command → Tier 3 operator-first summary  
5. Run `just docstrings-patch` before push when `src/git_cg` changed  

### Reviews

| Finding | Valid? |
|:---|:---|
| “Missing Google `Args` on obvious typed params” | **Usually no** — ask what was non-obvious |
| “Module lacks invariants / forbidden behaviour on a fail-closed engine” | **Yes** |
| “CLI first line is unreadable RFC soup” | **Yes** |
| “Private helpers undocumented and interrogate patch gate fails” | **Yes** — short real docs |
| “Please convert entire file to Google for consistency” | **No** unless a supported-export / escalation trigger pass |

### Relation to older phrases

* ADR/phase text saying “project docstring idiom/standard” → **this document**  
* `TODO.md` “adhere to Google Style” → **superseded** by selective-Google tiering here  
* S5-H02 “public API docstring idiom” → module/public **contract** docs on supported surfaces, not full Google sprawl  

---

## Change control

* Normative for `src/git_cg/` docstring shape and review expectations  
* Coverage thresholds and interrogate invocation remain owned by `pyproject.toml` + CI workflows + Development Guide  
* S7 may add allowlisted signature rendering later; it must not redefine this standard as full-package Google autodoc  
* Material changes to tier rules should update this file in the same PR as the policy change  

---

## Summary checklist

```text
[ ] Module states purpose, invariants, boundaries (when non-trivial)
[ ] Public summary line is enough; Google sections only if triggered
[ ] Types carry schema; prose carries law/side effects
[ ] Private helpers: short law docs or honestly obvious
[ ] CLI first line is operator help
[ ] No signature-echo padding
[ ] just docstrings-patch green on src/git_cg changes
```
