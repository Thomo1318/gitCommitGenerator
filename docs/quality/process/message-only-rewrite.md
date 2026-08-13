# Message-only gold rewrite

> Unifies **P-S8-9 / F44** (S6–11) with **F80 / P-S12-9** (Session 12).  
> Package version: `1.0.0-combine`  
> Related: [`../METHOD.md`](../METHOD.md) · [`../PREVENTION_BACKLOG.md`](../PREVENTION_BACKLOG.md)

## Goal

Replace a wrong commit **message** while **preserving the tree** (and preferably author dates when intentional).

## Hard rules

1. **Tree OID must not change** (`Rewrite-map-confirmed`).  
2. **`--no-verify` alone is insufficient** — `prepare-commit-msg` may still invoke `git-cg` (**F80**).  
3. Prefer disabling prepare re-entry for the rewrite window.  
4. Do not re-stage unrelated work; do not “fix” the tree while polishing the message.  
5. Record raw SHA → gold SHA in the case file.  
6. **Clean worktree required** before any `git reset --hard <new>` path (or explicitly stash/preserve uncommitted work, or stop).

## Approved controls (pick one primary)

### A. `GIT_CG_SKIP_PREPARE` (primary for hk-managed installs)

Product support is shipped in `git-cg`: prepare-commit-msg generation no-ops when the env var is truthy.

Accepted truthy values (case-insensitive): `1`, `true`, `yes`, `on`.

```bash
# preferred amend path under hk
GIT_CG_SKIP_PREPARE=1 git commit --amend -F .git/NEW_COMMIT_MSG
```

Notes:

* This short-circuits **prepare generation only**.  
* `commit-msg` validation / telemetry finalization may still run — that is desired unless the operator has a documented unbound/offline reason.  
* Prefer this over disabling hooks wholesale.

### B. File method for multi-line messages (always pair with A when amending)

```bash
# write exact Hybrid message + trailers to a temp file, then:
GIT_CG_SKIP_PREPARE=1 git commit --amend -F .git/NEW_COMMIT_MSG
# clean up temp file after success
```

See project amend SOP: prefer `-F` over multi `-m` for Hybrid bodies + trailers.

### C. `core.hooksPath=/dev/null` — **unsupported under hk-managed installs**

```bash
# NOT reliable in this repository when hooks are managed by hk
git -c core.hooksPath=/dev/null commit --amend -F .git/NEW_COMMIT_MSG
```

Observed: hk `prepare-commit-msg` / `commit-msg` can still run even with `core.hooksPath=/dev/null`. Do **not** present this as a guaranteed short-circuit for managed installs.

### D. `git commit-tree` rebuild (fallback for multi-tip / hk edge cases)

Use when amend+skip is awkward (stacked message-only rebuilds, partial history rewrite, or hook side-effects must be avoided at construction time).

```bash
# 0) require clean worktree (or explicitly preserve/stop)
git status --porcelain
test -z "$(git status --porcelain)"

# 1) capture pre-rewrite tip + tree
raw=$(git rev-parse HEAD)
tree=$(git rev-parse HEAD^{tree})
parent=$(git rev-parse HEAD^)

# 2) build replacement commit object (set author/committer env as needed)
new=$(git commit-tree "$tree" -p "$parent" < .git/NEW_COMMIT_MSG)

# 3) move branch (ONLY with clean worktree / explicit preserve policy)
git reset --hard "$new"

# 4) verify tree unchanged vs pre-rewrite tip
test "$(git rev-parse HEAD^{tree})" = "$(git rev-parse "$raw"^{tree})"
```

After `commit-tree` paths:

* Manually confirm Hybrid/`commit-msg` compliance for the new message (construction bypassed normal commit creation UX).  
* Clean any stale prepare/telemetry state if the rewrite intentionally skipped hook finalization.  
* Never `reset --hard` over uncommitted work without an explicit preserve step.

## Verification

```bash
# tree unchanged vs pre-rewrite tip
git rev-parse HEAD^{tree}
git rev-parse <raw_sha>^{tree}
# subjects
git log -1 --format=%s <raw_sha>
git log -1 --format=%s HEAD
```

## Case filing

After rewrite, complete METHOD case with:

* Git-raw / Gold-final  
* Rewrite-map-confirmed  
* Note whether prepare re-entry was observed pre-mitigation (F80)  
* Note which control was used (`GIT_CG_SKIP_PREPARE`, commit-tree, etc.)

## Environment note — hk-managed hooks (2026-08-13 / 204-QP-RB)

In this repository, hooks are driven by **hk** (`hk.pkl` `prepare-commit-msg` → `git-cg`), not only files under `.git/hooks`.

Observed:

* `git -c core.hooksPath=/dev/null commit -F <msgfile>` **still ran** hk `prepare-commit-msg` and `commit-msg` steps during a gold message landing.  
* Message bytes may survive if `git-cg` chooses not to overwrite a supplied `-F` body, but **re-entry still happens** (Opik/telemetry side effects, rewrite risk).  
* **Primary managed control:** `GIT_CG_SKIP_PREPARE=1` (product-honoured no-op for prepare generation).  
* **Fallback without prepare re-entry at object construction:** `git commit-tree` + clean-worktree `git reset --hard <new>` with tree-OID verification.

This is the operational binding of **F80 / P-S12-9**.
