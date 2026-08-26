# git-cg eval train-export

> **Usage:** `git-cg eval train-export …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Export governed train rows from landed bundles (R14 / §7.5). Row scrub-failure policy: drop + report (scrub_report) + continue; never emit cleartext; no .eval/quarantine/. Antipattern/hard-negative rows never enter positive_gold (S6-G06). ``--dry-run`` is the NTH-03 alias of ``--no-write`` (validate + would-write summary; zero store mutation).

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval train-export [OPTIONS]                                                  
                                                                                
 Export governed train rows from landed bundles (R14 / §7.5).                   
                                                                                
 Row scrub-failure policy: drop + report (scrub_report) + continue; never       
 emit cleartext; no .eval/quarantine/. Antipattern/hard-negative rows never     
 enter positive_gold (S6-G06). ``--dry-run`` is the NTH-03 alias of             
 ``--no-write`` (validate + would-write summary; zero store mutation).          
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --bundle-id                       TEXT  Bundle id(s) to export; default      │
│                                         exports all landed bundles.          │
│ --profile                         TEXT  Redaction profile (never             │
│                                         raw_dev_unsafe).                     │
│                                         [default: train_rich]                │
│ --capture-on                      TEXT  pass|fail|all corpus eligibility.    │
│                                         [default: all]                       │
│ --split-group-id                  TEXT                                       │
│ --notes                           TEXT                                       │
│ --write             --no-write          [default: write]                     │
│ --dry-run                               Validate + project export without    │
│                                         writing (alias of --no-write).       │
│ --json                                  Emit cli_output_envelope_v1 on       │
│                                         stdout.                              │
│ --help                                  Show this message and exit.          │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
