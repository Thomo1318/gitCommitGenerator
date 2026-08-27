# git-cg record-telemetry

> **Usage:** `git-cg record-telemetry …`

Record final commit telemetry and bind accepted final bytes (S3).

## Help

```text
Usage: git-cg record-telemetry [OPTIONS] [COMMIT_MSG_FILE]

 Record final commit telemetry and bind accepted final bytes (S3).

 Reads ``COMMIT_EDITMSG`` as exact bytes (hash authority), classifies how the
 generated message was edited when telemetry state is present, records Opik
 metadata, and best-effort binds accept-path evidence via
 :func:`bind_accept_path`. Missing telemetry state or binding failures never
 block product accept (N19 F8 / capture-off-by-default).

 Parameters:
     commit_msg_file: Path to the final commit message file.
     verbose: Enables progress / error output.

╭─ Arguments ──────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│   commit_msg_file      [COMMIT_MSG_FILE]  Path to the final commit message file [default: .git/COMMIT_EDITMSG]       │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --verbose  -v        Enable verbose output                                                                           │
│ --help               Show this message and exit.                                                                     │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```
