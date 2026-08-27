# git-cg commit

> **Usage:** `git-cg commit …`

Generate an AI commit message based on staged changes.

## Help

```text
Usage: git-cg commit [OPTIONS] [COMMIT_MSG_FILE] [COMMIT_SOURCE] [EXTRA_ARGS]...

 Generate an AI commit message based on staged changes.

╭─ Arguments ──────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│   commit_msg_file      [COMMIT_MSG_FILE]  Path to the commit message file [default: .git/COMMIT_EDITMSG]             │
│   commit_source        [COMMIT_SOURCE]    Source of the commit message (e.g., 'message', 'template', or empty for    │
│                                           default generation)                                                        │
│   extra_args           [EXTRA_ARGS]...    Any extra arguments passed by git hooks                                    │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --engine            -e                          TEXT  AI engine to use (e.g. omlx, mtplx) [default: mtplx]           │
│ --dry-run           -d                                Do not write the commit message, just print it                 │
│ --verbose           -v                                Enable verbose output                                          │
│ --amend-regenerate                                    Opt in to regenerating the message on git --amend (source      │
│                                                       'commit'). Off by default.                                     │
│ --strict                                              Exit non-zero on failure. Leave OFF for git hooks so a failed  │
│                                                       generation never blocks the commit; turn ON for CLI/CI use.    │
│ --interactive       -i                                Enable terminal-native interactive review via gum when a TTY   │
│                                                       is available.                                                  │
│ --gold-strict                                         Resolve gold lint to strict mode without enabling general      │
│                                                       --strict.                                                      │
│ --term              -t                                Use Terminal Editor ($EDITOR) when editing commit messages     │
│                                                       (Default).                                                     │
│                                                       [default: True]                                                │
│ --gui               -g                                Use GUI Editor ($VISUAL) when editing commit messages.         │
│ --enable-semantic       --no-enable-semantic          Enable Phase 1 semantic producers (default:                    │
│                                                       GIT_CG_ENABLE_SEMANTIC env or off).                            │
│ --rank-arbitrate        --no-rank-arbitrate           Allow Low-confidence pre-LLM intent arbitration when -i + TTY  │
│                                                       (default: GIT_CG_RANK_ARBITRATE env or auto).                  │
│ --blueprint                                     TEXT  Optional presentation CommitBlueprint as inline JSON or        │
│                                                       @path.json (max 64KiB; never overrides ranked intent_id).      │
│ --help                                                Show this message and exit.                                    │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```
