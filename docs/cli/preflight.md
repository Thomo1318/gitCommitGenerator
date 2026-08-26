# git-cg preflight

> **Usage:** `git-cg preflight …`

Print a read-only diff-class / path-class preflight summary (Issue #204).

## Help

```text
Usage: git-cg preflight [OPTIONS] [PATHS]...                                          
                                                                                
 Print a read-only diff-class / path-class preflight summary (Issue #204).      
                                                                                
 Does not invoke the LLM, ranker, hooks, or git writes. Safe for CI and local   
 operator dry-runs before commit generation.                                    
                                                                                
╭─ Arguments ──────────────────────────────────────────────────────────────────╮
│   paths      [PATHS]...  Optional staged-path overrides. Defaults to `git    │
│                          diff --cached --name-only`.                         │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --json               Emit machine-readable JSON instead of human tables.     │
│ --verbose  -v        Include stub notes and theme bullets.                   │
│ --help               Show this message and exit.                             │
╰──────────────────────────────────────────────────────────────────────────────╯
```
