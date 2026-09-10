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
* :mod:`git_cg.eval.mirror.payload` — content-addressed redacted bodies under
  ``.eval/export_payloads/`` (P0-3 / E11).
* :mod:`git_cg.eval.mirror.queue` — ``.eval/export_queue/`` Layer-A ops rows
  (``export_queue_item_v1``) with claim/lease + S3 atomic-write law.

S4b adds the network-facing half (still fail-open, never product-blocking):

* :mod:`git_cg.eval.mirror.secrets` — runtime secret resolution via the
  product :func:`git_cg.secrets.resolve_secret` pathway; never persisted.
* :mod:`git_cg.eval.mirror.transport` — :class:`Transport` protocol, lazy
  Opik SDK transport, deterministic mock, classified errors.
* :mod:`git_cg.eval.mirror.experiments` — ``experiment_v1`` naming + pin set.
* :mod:`git_cg.eval.mirror.projections` — bundle → trace/span, session twin →
  thread, deterministic score card → feedback (no cloud re-scoring); P1-8/9/10
  final_accept selection, boolean projection, closed ``local_wrapper`` source,
  and E9 authority annotations.
* :mod:`git_cg.eval.mirror.composition` — ``build_export_plan`` sole join path
  (Layer-A → redact → project → batch → enqueue) for merge evidence (E8 / P0-5).
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
    EXPORT_STATUSES,
    ExportSizeError,
    ExportStatus,
    batch_idempotency_key,
    build_export_batches,
    envelope_size_bytes,
    map_queue_status_to_export_status,
)
from git_cg.eval.mirror.composition import (
    ExportPlanError,
    ExportPlanResult,
    LayerAObjects,
    build_export_plan,
)
from git_cg.eval.mirror.config import (
    OpikConfigError,
    OpikEnvironment,
    OpikMode,
    resolve_opik_config,
)
from git_cg.eval.mirror.experiments import (
    UNRESOLVED_GIT_SHA,
    ExperimentPins,
    ExportGitShaError,
    build_experiment,
    build_experiment_pins,
    experiment_name,
    is_unresolved_git_sha,
    require_resolved_git_sha,
    resolve_git_sha,
)
from git_cg.eval.mirror.exporter import (
    DrainSummary,
    drain_queue,
    list_pending_items,
    mirror_result_from_drain,
)
from git_cg.eval.mirror.health import ExportHealth, derive_export_health_rollup
from git_cg.eval.mirror.payload import (
    EXPORT_PAYLOADS_DIRNAME,
    ExportPayloadError,
    export_payloads_dir,
    load_payload_artifact,
    payload_ref_for_sha,
    persist_payload_artifact,
)
from git_cg.eval.mirror.projections import (
    FEEDBACK_SOURCE,
    ProjectionError,
    authority_annotations,
    project_bundle_to_trace,
    project_score_card_to_feedback,
    project_session_thread,
    select_final_attempt,
)
from git_cg.eval.mirror.queue import (
    EXPORT_QUEUE_DIRNAME,
    QUEUE_STATUSES,
    ExportQueueError,
    claim_queue_item,
    enqueue_export_batch,
    load_queue_item,
    load_queue_payload,
    mark_queue_item,
    release_stale_leases,
)
from git_cg.eval.mirror.redaction import (
    QUARANTINE_MARKER,
    redact_bundle_for_export,
    sanitize_export_tree,
)
from git_cg.eval.mirror.result import (
    MirrorResult,
    build_mirror_result,
    evaluation_job_result,
    export_result,
)
from git_cg.eval.mirror.secrets import MirrorSecretError, OpikRuntimeSecrets
from git_cg.eval.mirror.train import (
    POSITIVE_GOLD,
    TRAIN_DATASET_ID,
    TRAIN_LABELS,
    TrainProjectionError,
    build_train_projection,
    filter_positive_gold,
    normalize_train_label,
    project_train_row,
)
from git_cg.eval.mirror.transport import (
    EXPORT_ERROR_CLASSES,
    LAZY_OPIK_IMPORT_ALLOWLIST,
    ExportTransportError,
    MockTransport,
    OpikSdkTransport,
    Transport,
    classify_export_error,
    flush_timeout_seconds,
    scrub_export_note,
)

__all__ = [
    "DEFAULT_MAX_BATCH_BYTES",
    "EXPORT_ERROR_CLASSES",
    "EXPORT_PAYLOADS_DIRNAME",
    "EXPORT_QUEUE_DIRNAME",
    "EXPORT_STATUSES",
    "FEEDBACK_SOURCE",
    "LAZY_OPIK_IMPORT_ALLOWLIST",
    "POSITIVE_GOLD",
    "QUARANTINE_MARKER",
    "QUEUE_STATUSES",
    "TRAIN_DATASET_ID",
    "TRAIN_LABELS",
    "UNRESOLVED_GIT_SHA",
    "DrainSummary",
    "ExperimentPins",
    "ExportGitShaError",
    "ExportHealth",
    "ExportPayloadError",
    "ExportPlanError",
    "ExportPlanResult",
    "ExportQueueError",
    "ExportSizeError",
    "ExportStatus",
    "ExportTransportError",
    "LayerAObjects",
    "MirrorResult",
    "MirrorSecretError",
    "MockTransport",
    "OpikConfigError",
    "OpikEnvironment",
    "OpikMode",
    "OpikRuntimeSecrets",
    "OpikSdkTransport",
    "ProjectionError",
    "TrainProjectionError",
    "Transport",
    "authority_annotations",
    "batch_idempotency_key",
    "build_experiment",
    "build_experiment_pins",
    "build_export_batches",
    "build_export_plan",
    "build_mirror_result",
    "build_train_projection",
    "claim_queue_item",
    "classify_export_error",
    "derive_export_health_rollup",
    "drain_queue",
    "enqueue_export_batch",
    "envelope_size_bytes",
    "evaluation_job_result",
    "experiment_name",
    "export_payloads_dir",
    "export_result",
    "filter_positive_gold",
    "flush_timeout_seconds",
    "is_unresolved_git_sha",
    "list_pending_items",
    "load_payload_artifact",
    "load_queue_item",
    "load_queue_payload",
    "map_queue_status_to_export_status",
    "mark_queue_item",
    "mirror_result_from_drain",
    "normalize_train_label",
    "payload_ref_for_sha",
    "persist_payload_artifact",
    "project_bundle_to_trace",
    "project_score_card_to_feedback",
    "project_session_thread",
    "project_train_row",
    "redact_bundle_for_export",
    "release_stale_leases",
    "require_resolved_git_sha",
    "resolve_git_sha",
    "resolve_opik_config",
    "sanitize_export_tree",
    "scrub_export_note",
    "select_final_attempt",
]
