# git-cg eval issue reopen

> **Usage:** `git-cg eval issue reopen …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Reopen a previously resolved/suppressed local diagnostic issue.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval issue reopen [OPTIONS] ISSUE_ID                                               
                                                                                
 Reopen a previously resolved/suppressed local diagnostic issue.                
                                                                                
╭─ Arguments ──────────────────────────────────────────────────────────────────╮
│ *    issue_id      TEXT  Issue id. [required]                                │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --json          Emit cli_output_envelope_v1 on stdout.                       │
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../../index.md)
* [Operator API map](../../../eval/operator_api_map.md)
* [Eval operator guide](../../../eval/README.md)
