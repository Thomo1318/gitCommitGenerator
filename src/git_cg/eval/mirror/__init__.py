"""S4a Opik mirror — offline core (Issue #232 / #217, plan §8.4).

This package projects **precomputed local** eval results toward Opik for
operator compare and the owner training/longitudinal corpus lake (R3). It is
never the scoring engine of record and never the CI sole green.

S4a ships the offline core:

* :mod:`git_cg.eval.mirror.config` — ``git_cg_opik_config_v1`` resolution
  (FIND-022): fail-closed env parsing, pinned project lanes, **never**
  Default Project fallthrough, secrets only via env at runtime.
* :mod:`git_cg.eval.mirror.health` — closed ``ExportHealth`` §18.7 tokens (E1).
* :mod:`git_cg.eval.mirror.result` — machine-readable ``MirrorResult`` (P0-7)
  with dual axis ``export_result`` / ``evaluation_job_result`` (P1-5).
* :mod:`git_cg.eval.mirror.redaction` — the R14 owner redaction ladder over
  bundle dicts; secrets always scrubbed; scrub failure **quarantines** the
  field (omit + mark) rather than leaking ambient payload.
* :mod:`git_cg.eval.mirror.batch` — ``export_batch_v1`` builder: deterministic
  idempotency key, pin set, default 4MB payload ceiling (split or
  ``export_size`` classification, never silent oversize).
* :mod:`git_cg.eval.mirror.queue` — ``.eval/export_queue/`` Layer-A rows
  (``export_queue_item_v1``) with the S3 atomic-write/containment law.

S4b adds the network-facing half (still fail-open, never product-blocking):

* :mod:`git_cg.eval.mirror.secrets` — runtime secret resolution via the
  product :func:`git_cg.secrets.resolve_secret` pathway; never persisted.
* :mod:`git_cg.eval.mirror.transport` — :class:`Transport` protocol, lazy
  Opik SDK transport, deterministic mock, classified errors.
* :mod:`git_cg.eval.mirror.experiments` — ``experiment_v1`` naming + pin set.
* :mod:`git_cg.eval.mirror.projections` — bundle → trace/span, session twin →
  thread, deterministic score card → feedback (no cloud re-scoring).
* :mod:`git_cg.eval.mirror.exporter` — queue drain orchestration with bounded
  flush and F4 fail-open classification.

Hard laws (F4 fail-open export):

* Export failure classifies as ``export_network`` / ``export_auth`` /
  ``export_validation`` / ``export_size`` and **never** flips
  ``gate.deterministic_pass`` or blocks the product accept path.
* The Opik SDK is imported lazily (only inside the real transport); the
  offline core and product accept path never import Opik.
* No cloud-side scoring rules are created from raw traces; the deterministic
  product score card is the authority and is exported as feedback.
"""

from __future__ import annotations

from git_cg.eval.mirror.batch import (
    DEFAULT_MAX_BATCH_BYTES,
    ExportSizeError,
    build_export_batches,
)
from git_cg.eval.mirror.config import (
    OpikConfigError,
    OpikEnvironment,
    OpikMode,
    resolve_opik_config,
)
from git_cg.eval.mirror.experiments import build_experiment, experiment_name
from git_cg.eval.mirror.exporter import (
    DrainSummary,
    drain_queue,
    list_pending_items,
    mirror_result_from_drain,
)
from git_cg.eval.mirror.health import ExportHealth, derive_export_health_rollup
from git_cg.eval.mirror.projections import (
    project_bundle_to_trace,
    project_score_card_to_feedback,
    project_session_thread,
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
from git_cg.eval.mirror.result import (
    MirrorResult,
    build_mirror_result,
    evaluation_job_result,
    export_result,
)
from git_cg.eval.mirror.secrets import MirrorSecretError, OpikRuntimeSecrets
from git_cg.eval.mirror.transport import (
    EXPORT_ERROR_CLASSES,
    ExportTransportError,
    MockTransport,
    OpikSdkTransport,
    Transport,
)

__all__ = [
    "DEFAULT_MAX_BATCH_BYTES",
    "EXPORT_ERROR_CLASSES",
    "EXPORT_QUEUE_DIRNAME",
    "QUARANTINE_MARKER",
    "DrainSummary",
    "ExportHealth",
    "ExportQueueError",
    "ExportSizeError",
    "ExportTransportError",
    "MirrorResult",
    "MirrorSecretError",
    "MockTransport",
    "OpikConfigError",
    "OpikEnvironment",
    "OpikMode",
    "OpikRuntimeSecrets",
    "OpikSdkTransport",
    "Transport",
    "build_experiment",
    "build_export_batches",
    "build_mirror_result",
    "derive_export_health_rollup",
    "drain_queue",
    "enqueue_export_batch",
    "evaluation_job_result",
    "experiment_name",
    "export_result",
    "list_pending_items",
    "load_queue_item",
    "mark_queue_item",
    "mirror_result_from_drain",
    "project_bundle_to_trace",
    "project_score_card_to_feedback",
    "project_session_thread",
    "redact_bundle_for_export",
    "resolve_opik_config",
]
