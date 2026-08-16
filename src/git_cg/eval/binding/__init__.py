"""S3 accept-path binding package (Issue #231, S3-contract-v1.4).

Lane A local SoT: binds the accept-path final bytes (``COMMIT_EDITMSG``) to the
generation lineage (trace / session / thread) **before** any Opik write, and
projects trajectory evidence for the five hook stages. This package wraps
product authorities (``git_cg.telemetry``) — it never reimplements Hybrid,
gold, or provenance policy, and it never performs network or Opik I/O.
"""

from __future__ import annotations

from git_cg.eval.binding.binder import (
    STAGE_ORDER,
    AcceptPathBindingError,
    AcceptPathBindingV1,
    BindingStatus,
    HookStage,
    StageCaptureV1,
    bind_accept_path,
    project_trajectory_evidence,
)

__all__ = [
    "STAGE_ORDER",
    "AcceptPathBindingError",
    "AcceptPathBindingV1",
    "BindingStatus",
    "HookStage",
    "StageCaptureV1",
    "bind_accept_path",
    "project_trajectory_evidence",
]
