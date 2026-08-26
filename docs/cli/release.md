# git-cg release

> **Usage:** `git-cg release …`

Run the release workflow.

## Help

```text
Usage: git-cg release [OPTIONS]                                                       
                                                                                
 Run the release workflow.                                                      
                                                                                
 Calculates SemVer impact from Hybrid trailers, injects versions, updates       
 CHANGELOG.md, and assembles gold-standard GitHub Release notes (Issue #181).   
                                                                                
 Parameters:                                                                    
     dry_run: Print planned changelog/notes without writing files or            
 publishing.                                                                    
     verbose: Extra logging.                                                    
     pre_release: Pre-release identifier to add or bump (e.g. `alpha`, `rc`).   
     theme: Optional title theme after ``vX.Y.Z:``.                             
     notes_file: Optional path for the GitHub notes markdown file.              
     publish_github: Create the GitHub release with ``gh`` (non-dry-run only).  
     github_latest: When publishing, mark as full latest release instead of     
 pre-release.                                                                   
     skip_github_notes: Legacy path — version/changelog only.                   
     repo_slug: Optional ``owner/repo`` override for notes links and publish.   
     github_target: Optional ref for ``gh release create --target``.            
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --dry-run            -d            Print changes without modifying files or  │
│                                    executing git tags                        │
│ --verbose            -v            Enable verbose output                     │
│ --pre-release                TEXT  Add or bump a pre-release identifier      │
│                                    (e.g., 'alpha', 'rc')                     │
│ --theme                      TEXT  GitHub release title theme after the      │
│                                    version (e.g. 'Semantic Context           │
│                                    integration')                             │
│ --notes-file                 TEXT  Path to write gold-standard GitHub        │
│                                    release notes markdown (default under     │
│                                    .git/)                                    │
│ --publish-github                   Create the GitHub Release via `gh` after  │
│                                    preparing files (requires network + auth) │
│ --github-latest                    Publish GitHub release as latest (not     │
│                                    pre-release). Default is pre-release.     │
│ --skip-github-notes                Only bump versions/CHANGELOG; skip        │
│                                    gold-standard GitHub notes assembly       │
│ --repo-slug                  TEXT  GitHub owner/repo for compare links and   │
│                                    gh publish (default: detect from          │
│                                    origin/gh)                                │
│ --github-target              TEXT  Optional git ref for gh release create    │
│                                    --target; omit to use an existing local   │
│                                    tag                                       │
│ --help                             Show this message and exit.               │
╰──────────────────────────────────────────────────────────────────────────────╯
```
