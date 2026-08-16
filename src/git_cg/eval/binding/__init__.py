"""S3 accept-path binding package (Issue #231, S3-contract-v1.4).

Lane A local source of truth: binds the **exact accepted final message bytes**
(``COMMIT_EDITMSG``) into a schema-valid ``ape_bundle_v1`` with
``artifact_class=final_accept`` on the honest happy path, with explicit
bound/unbound labeling, scoped idempotent persistence under the repo-local
``.eval/`` tree, and capture gated **off by default** for basic users.

This package wraps product authorities (``git_cg.telemetry``,
``git_cg.eval.corpus.canonical``, ``git_cg.eval.schema_pack``) — it never
reimplements Hybrid, gold, ranker/SOP, or provenance policy, and it never
performs network or Opik I/O on the bind path.

Public API (D4, locked): ``capture_enabled``, ``BindInput``, ``BindResult``,
``bind_final_accept``, ``bind_unbound``. Trajectory evidence (R7/D3/D10) is
emitted via ``build_trajectory_evidence`` and the ``DECLARED_STAGES``
vocabulary. Session-thread twins (R13/D12) via ``build_session_twin`` /
``write_session_twin``; message_versions hooks (D12/M7) via
``build_message_versions``.
"""

from __future__ import annotations

from git_cg.eval.binding.accept_hook import (
    AcceptBindResult,
    bind_accept_path,
)
from git_cg.eval.binding.binder import (
    BindInput,
    BindResult,
    bind_final_accept,
    bind_unbound,
    message_sha256_bytes,
)
from git_cg.eval.binding.message_versions import build_message_versions
from git_cg.eval.binding.profiles import capture_enabled
from git_cg.eval.binding.session_thread import (
    build_session_twin,
    write_session_twin,
)
from git_cg.eval.binding.trajectory import (
    DECLARED_STAGES,
    build_trajectory_evidence,
)

__all__ = [
    "DECLARED_STAGES",
    "AcceptBindResult",
    "BindInput",
    "BindResult",
    "bind_accept_path",
    "bind_final_accept",
    "bind_unbound",
    "build_message_versions",
    "build_session_twin",
    "build_trajectory_evidence",
    "capture_enabled",
    "message_sha256_bytes",
    "write_session_twin",
]
