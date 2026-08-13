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

## Approved controls (pick one primary)

### A. hooksPath null (preferred for offline rewrite sessions)

```bash
# example pattern — adjust to operator environment
git -c core.hooksPath=/dev/null commit --amend -F .git/NEW_COMMIT_MSG
```

### B. Skip prepare via env (when supported by install)

```bash
GIT_CG_SKIP_PREPARE=1 git commit --amend -F .git/NEW_COMMIT_MSG
```

Confirm in your hook install that this var is honoured before relying on it.

### C. File method for multi-line messages (project preference)

```bash
# write exact message
# git commit --amend -F .git/NEW_COMMIT_MSG
# clean up temp file after success
```

See user/project amend SOP: prefer `-F` over multi `-m` for Hybrid bodies + trailers.

## Verification

```bash
# tree unchanged vs pre-amend tip
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

## Environment note — hk-managed hooks (2026-08-13 / 204-QP-RB)

In this repository, hooks are driven by **hk** (`hk.pkl` `prepare-commit-msg` → `git-cg`), not only files under `.git/hooks`.

Observed:

* `git -c core.hooksPath=/dev/null commit -F <msgfile>` **still ran** hk `prepare-commit-msg` and `commit-msg` steps during a gold message landing.
* Message bytes may survive if `git-cg` chooses not to overwrite a supplied `-F` body, but **re-entry still happens** (Opik/telemetry side effects, rewrite risk).
* **Reliable message-only construction without prepare re-entry:** `git commit-tree <tree> -p <parent> < msgfile` then `git reset --hard <new>` (set `GIT_AUTHOR_*` / `GIT_COMMITTER_*` as needed).

Until product/install exposes a guaranteed `GIT_CG_SKIP_PREPARE=1` short-circuit that hk also honours, treat **commit-tree** as the gold standard for multi-tip rebuilds (F80 / P-S12-9).

