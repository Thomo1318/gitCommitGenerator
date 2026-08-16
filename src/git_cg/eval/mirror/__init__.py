"""S4a Opik mirror — offline core (Issue #217, plan §8.4).

This package projects **precomputed local** eval results toward Opik for
operator compare and the owner training/longitudinal corpus lake (R3). It is
never the scoring engine of record and never the CI sole green.

S4a ships the offline core only:

* :mod:`git_cg.eval.mirror.config` — ``git_cg_opik_config_v1`` resolution
  (FIND-022): fail-closed env parsing, pinned project per lane, **never**
  Default Project fallthrough, secrets only via env at runtime.
* :mod:`git_cg.eval.mirror.redaction` — the R14 owner redaction ladder over
  bundle dicts; secrets always scrubbed; scrub failure **quarantines** the
  field (omit + mark) rather than leaking ambient payload.
* :mod:`git_cg.eval.mirror.batch` — ``export_batch_v1`` builder: deterministic
  idempotency key, pin set, default 4MB payload ceiling (split or
  ``export_size`` classification, never silent oversize).
* :mod:`git_cg.eval.mirror.queue` — ``.eval/export_queue/`` Layer-A rows
  (``export_queue_item_v1``) with the S3 atomic-write/containment law.

Hard laws (F4 fail-open export):

* Export failure classifies as ``export_network`` / ``export_auth`` /
  ``export_validation`` / ``export_size`` and **never** flips
  ``gate.deterministic_pass`` or blocks the product accept path.
* No network, no Opik import, and no scoring anywhere in S4a.
"""

from __future__ import annotations

from git_cg.eval.mirror.batch import (
    DEFAULT_MAX_BATCH_BYTES,
    ExportSizeError,
    build_export_batches,
)
from git_cg.eval.mirror.config import (
    OpikConfigError,
    OpikMode,
    resolve_opik_config,
)
from git_cg.eval.mirror.queue import (
    EXPORT_QUEUE_DIRNAME,
    ExportQueueError,
    enqueue_export_batch,
    load_queue_item,
    mark_queue_item,
)
from git_cg.eval.mirror.redaction import (
    QUARANTINE_MARKER,
    redact_bundle_for_export,
)

__all__ = [
    "DEFAULT_MAX_BATCH_BYTES",
    "EXPORT_QUEUE_DIRNAME",
    "QUARANTINE_MARKER",
    "ExportQueueError",
    "ExportSizeError",
    "OpikConfigError",
    "OpikMode",
    "build_export_batches",
    "enqueue_export_batch",
    "load_queue_item",
    "mark_queue_item",
    "redact_bundle_for_export",
    "resolve_opik_config",
]
