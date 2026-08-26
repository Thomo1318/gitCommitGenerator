# git-cg eval triage

> **Usage:** `git-cg eval triage …`  
> **Kind:** `command` · **Status:** canonical S6 surface

One-shot advisory view: doctor + failures + explain. Composes library engines only — never nests Typer presentation commands. Not score law: does not promote gold, rank intents, or revive Opik ``user_acceptance`` threshold triage. Emits one human report or one ``cli_output_envelope_v1`` with an ``eval_triage_v0`` data payload.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval triage [OPTIONS]                                                        
                                                                                
 One-shot advisory view: doctor + failures + explain.                           
                                                                                
 Composes library engines only — never nests Typer presentation commands.       
 Not score law: does not promote gold, rank intents, or revive Opik             
 ``user_acceptance`` threshold triage. Emits one human report or one            
 ``cli_output_envelope_v1`` with an ``eval_triage_v0`` data payload.            
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --suite                TEXT       Suite id for the doctor section (default:  │
│                                   cm-eval-fixtures-core).                    │
│                                   [default: cm-eval-fixtures-core]           │
│ --fixture-root         DIRECTORY  Optional fixture root override for the     │
│                                   doctor section.                            │
│ --experiment-id        TEXT       Experiment id for failures/explain         │
│                                   (defaults to latest local run).            │
│ --case                 TEXT       Case id for explain (auto-selects when     │
│                                   exactly one failing case).                 │
│ --skip-doctor                     Skip the doctor section.                   │
│ --skip-failures                   Skip the failures section.                 │
│ --skip-explain                    Skip the explain section.                  │
│ --json                            Emit cli_output_envelope_v1 on stdout.     │
│ --help                            Show this message and exit.                │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
