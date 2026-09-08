# Acceptpath Binding Mutation-Testing Advisory

> **Status**: Advisory. Not a close-bar requirement, not an acceptance criterion.
> **Refs**: #257 (NTH-B04).

## Purpose

Record mutation-testing targets for the acceptpath binding subsystem. Mutation
testing injects intentional faults; surviving mutants mean the suite can still
pass after a behavioural change.

This is not a runnable mutation suite. No mutation-testing dependency is
installed. Do not treat a mutation score as a CI, merge, or product-accept
gate.

## Target Areas

Priority order for a future mutation run, if tooling is approved:

| Priority | Area | Source | Rationale |
|:---:|---|---|---|
| 1 | Identity checks | `src/git_cg/eval/binding/binder.py` | Scoped reuse key `(repo_root, accept_event_token, final_message_sha256)` must be exact. A mutant that weakens equality or drops a component can collide identities. |
| 2 | v2 key versioning | `src/git_cg/eval/binding/binder.py` | `_INDEX_VERSION = 2` must ignore wrong-version indexes. A mutant that accepts any version can load stale or corrupt cache entries. |
| 3 | Redaction | `src/git_cg/eval/binding/binder.py`, `src/git_cg/eval/evidence_scrub.py` | Draft and score-card evidence must stay secret-safe; masking must be idempotent. Final accepted bytes are never scrubbed. A mutant that skips scrub can leak secrets. |
| 4 | Timeout | `src/git_cg/eval/binding/lock.py` | Lock acquisition timeout must return `None` so bind can fall back to unlocked atomic-replace. A mutant that waits forever stalls the bind path. Product accept must still not block. |
| 5 | Final-byte hashing | `src/git_cg/eval/binding/binder.py` | `message_sha256_bytes` must hash original bytes, not replacement-decoded text. A mutant that hashes the projected text breaks hash-source asymmetry. |

## Tooling

Mutation testing is not currently runnable in this project. Candidate tools
for owner-approved adoption:

| Tool | Status | Notes |
|---|---|---|
| [`mutmut`](https://mutmut.readthedocs.io/) | Not installed | Pure-Python mutation tester; pytest integration; no C-extension support |
| [`cosmic-ray`](https://cosmic-ray.readthedocs.io/) | Not installed | AST-based mutation testing; distributed execution; heavier setup |
| [`pitest`](https://pitest.org/) | JVM-only | Not applicable to this Python codebase |

**Policy**: no new dependencies by default. Mutation-testing tooling would
need explicit owner approval, a dependency-security review, and a lockfile
impact assessment before adoption.

## Existing Tests For Target Areas

These files exercise the target areas. Use them as a starting map for a
future mutation run, not as a coverage baseline or mutation score.

| Area | Test file |
|---|---|
| Identity checks | `tests/eval/binding/test_binder.py` |
| v2 key versioning | `tests/eval/binding/test_binder_cache.py` |
| Redaction | `tests/eval/binding/test_binder_redaction.py`, `tests/eval/test_evidence_scrub.py` |
| Timeout | `tests/eval/binding/test_binder_lock.py` |
| Final-byte hashing | `tests/eval/binding/test_binder.py` |

## Advisory Recipe

`just eval-mutation-advisory` prints this document. It does not run mutation
testing, does not measure coverage, and does not install tooling.

```bash
just eval-mutation-advisory
```

## Future Adoption Path

If mutation-testing tooling is approved and installed:

1. Mutate `src/git_cg/eval/binding/` with the approved tool.
2. Record killed versus surviving mutants.
3. Investigate survivors. Each survivor is a test gap.
4. Add targeted tests for survivors in the priority areas above.
5. Re-run until the kill rate stabilises or reaches an agreed advisory threshold.

The mutation score remains advisory only. It must never gate CI, block
merges, or act as an acceptance criterion.
