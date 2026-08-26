# git-cg eval review

> **Usage:** `git-cg eval review …`  
> **Kind:** `group` · **Status:** group

Local human review queue (advisory only).

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval review [OPTIONS] COMMAND [ARGS]...                                      
                                                                                
 Local human review queue (advisory only).                                      
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ enqueue     Enqueue an advisory human-review item.                           │
│ list        List local review-queue items.                                   │
│ rollup      Roll up multi-rater advisory scores for review items.            │
│ show        Show one local review-queue item.                                │
│ claim       Claim a pending review item (pending → in_review).               │
│ adjudicate  Adjudicate an in_review item (emits typed outcome_ref; never     │
│             writes gold).                                                    │
│ dismiss     Dismiss a pending/in_review item (terminal).                     │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## Children

* [`git-cg eval review adjudicate`](review/adjudicate.md) — Adjudicate an in_review item (emits typed outcome_ref; never writes gold).
* [`git-cg eval review claim`](review/claim.md) — Claim a pending review item (pending → in_review).
* [`git-cg eval review dismiss`](review/dismiss.md) — Dismiss a pending/in_review item (terminal).
* [`git-cg eval review enqueue`](review/enqueue.md) — Enqueue an advisory human-review item.
* [`git-cg eval review list`](review/list.md) — List local review-queue items.
* [`git-cg eval review rollup`](review/rollup.md) — Roll up multi-rater advisory scores for review items. Read-only dimension/outcome majority + craft spread. Authority stays advisory; never s
* [`git-cg eval review show`](review/show.md) — Show one local review-queue item.

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
