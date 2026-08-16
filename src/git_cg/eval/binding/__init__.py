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
``bind_final_accept``, ``bind_unbound``.
"""

from __future__ import annotations

from git_cg.eval.binding.binder import (
    BindInput,
    BindResult,
    bind_final_accept,
    bind_unbound,
    message_sha256_bytes,
)
from git_cg.eval.binding.profiles import capture_enabled

__all__ = [
    "BindInput",
    "BindResult",
    "bind_final_accept",
    "bind_unbound",
    "capture_enabled",
    "message_sha256_bytes",
]
