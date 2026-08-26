# git-cg eval export retry

> **Usage:** `git-cg eval export retry …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Re-queue failed export rows for another drain attempt. Default policy: reclaim rows whose last_error_class is retryable (``export_network`` / ``export_timeout`` / empty). Validation/auth/size failures require ``--force``. Transitions ``failed → pending`` so the next ``export drain`` can claim them. Never blocks product accept.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval export retry [OPTIONS]                                                         
                                                                                
 Re-queue failed export rows for another drain attempt.                         
                                                                                
 Default policy: reclaim rows whose last_error_class is retryable               
 (``export_network`` / ``export_timeout`` / empty). Validation/auth/size        
 failures require ``--force``. Transitions ``failed → pending`` so the next     
 ``export drain`` can claim them. Never blocks product accept.                  
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --root             DIRECTORY  Repo root (defaults to discovery).             │
│ --id               TEXT       Retry a single failed queue id (default: all   │
│                               failed rows).                                  │
│ --force                       Also retry export_validation / export_auth /   │
│                               export_size failures.                          │
│ --max-items        INTEGER    Cap on failed rows re-queued this invocation.  │
│ --json                        Emit cli_output_envelope_v1 on stdout.         │
│ --help                        Show this message and exit.                    │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../../index.md)
* [Operator API map](../../../eval/operator_api_map.md)
* [Eval operator guide](../../../eval/README.md)
