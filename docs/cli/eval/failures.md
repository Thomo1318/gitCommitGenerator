# git-cg eval failures

> **Usage:** `git-cg eval failures …`  
> **Kind:** `command` · **Status:** canonical S6 surface

List failing bundles/cases with metric_ids + failure_ids (§18.3, read-only). Optional NTH-02 filters (``--regime``, ``--family``, ``--failure-id``, ``--severity``) are AND-combined and documented in the API map. The base unfiltered list remains the S6-D01 contract.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval failures [OPTIONS]                                                      
                                                                                
 List failing bundles/cases with metric_ids + failure_ids (§18.3, read-only).   
                                                                                
 Optional NTH-02 filters (``--regime``, ``--family``, ``--failure-id``,         
 ``--severity``) are AND-combined and documented in the API map. The base       
 unfiltered list remains the S6-D01 contract.                                   
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --experiment-id        TEXT  Experiment id (defaults to latest local run).   │
│ --regime               TEXT  Deterministic filter: regime label from         │
│                              fingerprint inputs (e.g. A|B).                  │
│ --family               TEXT  Deterministic filter: score family (e.g.        │
│                              I|H|gate).                                      │
│ --failure-id           TEXT  Deterministic filter: require this failure_id   │
│                              on a failing score.                             │
│ --severity             TEXT  Deterministic filter: block|warn|info.          │
│ --json                       Emit cli_output_envelope_v1 on stdout.          │
│ --help                       Show this message and exit.                     │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
