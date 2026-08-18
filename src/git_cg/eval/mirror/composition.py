"""E8 composition API — sole merge-evidence path for S4 export (Issue #232).

``build_export_plan`` is the single public join:

    Layer-A objects → R14 redact → project → experiment pins → batch → enqueue

Leaf unit tests of redaction / projections / batch / queue remain useful, but
**S4-C/E/F merge evidence must include this composition path** (P0-5 / E8).

Hard laws:

* Offline only — no Opik import, no network.
* Product accept is never blocked (``product_accept_blocked`` always false).
* Modes ``off`` / ``local_only`` short-circuit without enqueue (health tokens).
* Failures classify as ``export_*`` and surface on :class:`ExportPlanResult`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Final

from git_cg.eval.enums import RedactionProfile
from git_cg.eval.mirror.batch import ExportSizeError, build_export_batches
from git_cg.eval.mirror.config import mode_fallback_token
from git_cg.eval.mirror.experiments import build_experiment
from git_cg.eval.mirror.health import ExportHealth
from git_cg.eval.mirror.projections import (
    ProjectionError,
    project_bundle_to_trace,
    project_score_card_to_feedback,
    project_session_thread,
)
from git_cg.eval.mirror.queue import ExportQueueError, enqueue_export_batch
from git_cg.eval.mirror.redaction import redact_bundle_for_export
from git_cg.eval.mirror.result import MirrorResult, build_mirror_result
from git_cg.eval.mirror.train import build_train_projection

__all__ = [
    "ExportPlanError",
    "ExportPlanResult",
    "LayerAObjects",
    "build_export_plan",
]

_SHORT_CIRCUIT_MODES: Final[frozenset[str]] = frozenset({"off", "local_only", "local"})


class ExportPlanError(ValueError):
    """Composition failure (``export_*`` class; never product-blocking)."""

    def __init__(self, message: str, *, error_class: str = "export_validation") -> None:
        """Initialise an export plan error with its classification."""
        self.error_class = error_class
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class LayerAObjects:
    """Typed Layer-A inputs for composition (bundles + optional twins)."""

    bundles: tuple[dict[str, Any], ...] = ()
    session_threads: tuple[dict[str, Any], ...] = ()
    include_train: bool = False

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> LayerAObjects:
        """
        Create a LayerAObjects instance from a mapping of bundles, session threads, and train-projection settings.
        
        Parameters:
        	raw (Mapping[str, Any] | None): Input mapping containing bundle and session-thread data. Singular and plural keys are supported.
        
        Returns:
        	LayerAObjects: Normalised immutable Layer-A objects.
        """
        if raw is None:
            return cls()
        bundles = raw.get("bundles") or raw.get("bundle") or ()
        if isinstance(bundles, Mapping):
            bundle_list: list[dict[str, Any]] = [dict(bundles)]
        else:
            bundle_list = [dict(b) for b in bundles if isinstance(b, Mapping)]
        threads = raw.get("session_threads") or raw.get("sessions") or ()
        if isinstance(threads, Mapping):
            thread_list: list[dict[str, Any]] = [dict(threads)]
        else:
            thread_list = [dict(t) for t in threads if isinstance(t, Mapping)]
        include_train = bool(raw.get("include_train", False))
        return cls(
            bundles=tuple(bundle_list),
            session_threads=tuple(thread_list),
            include_train=include_train,
        )


@dataclass(frozen=True, slots=True)
class ExportPlanResult:
    """Outcome of :func:`build_export_plan` (dual-axis + queue refs)."""

    mode: str
    health: ExportHealth
    queue_row_refs: tuple[str, ...] = ()
    batch_ids: tuple[str, ...] = ()
    item_refs: tuple[str, ...] = ()
    projected: int = 0
    enqueued: int = 0
    skipped: int = 0
    failed: int = 0
    error_classes: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)
    train: dict[str, Any] | None = None
    product_accept_blocked: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "product_accept_blocked", False)
        if not isinstance(self.health, ExportHealth):
            object.__setattr__(self, "health", ExportHealth(str(self.health)))
        classes = tuple(dict.fromkeys(str(c) for c in self.error_classes if c))
        object.__setattr__(self, "error_classes", classes)

    def to_dict(self) -> dict[str, Any]:
        """
        Serialise the export result into a dictionary suitable for transport or persistence.
        
        Returns:
        	dict[str, Any]: A dictionary containing the export status, queue and batch references, item counts, errors, notes, train data, and acceptance flag.
        """
        return {
            "mode": self.mode,
            "health": self.health.value if isinstance(self.health, ExportHealth) else str(self.health),
            "queue_row_refs": list(self.queue_row_refs),
            "batch_ids": list(self.batch_ids),
            "item_refs": list(self.item_refs),
            "projected": int(self.projected),
            "enqueued": int(self.enqueued),
            "skipped": int(self.skipped),
            "failed": int(self.failed),
            "error_classes": list(self.error_classes),
            "notes": list(self.notes),
            "train": self.train,
            "product_accept_blocked": False,
        }

    def as_mirror_result(self) -> MirrorResult:
        """Convert the export plan outcome into a mirror result.
        
        Returns:
        	MirrorResult: A mirror result containing the plan's mode, health, item counts, error classes, and notes.
        """
        return build_mirror_result(
            mode=self.mode,
            health=self.health,
            attempted=self.projected,
            succeeded=self.enqueued,
            failed=self.failed,
            deferred=self.skipped,
            error_classes=self.error_classes,
            notes=self.notes,
        )


def _as_config(config: Mapping[str, Any] | None) -> dict[str, Any]:
    """
    Normalise an optional export configuration to a dictionary.
    
    Parameters:
    	config: Configuration values to copy, or `None` to use disabled mode with the default redaction profile.
    
    Returns:
    	A dictionary containing the supplied configuration or the default disabled configuration.
    """
    if config is None:
        return {"mode": "off", "redaction_profile": RedactionProfile.DEFAULT_SCRUB.value}
    return dict(config)


def _project_name(config: Mapping[str, Any]) -> str:
    """Resolve the evaluation project name from configuration.
    
    Parameters:
    	config (Mapping[str, Any]): Configuration containing project settings.
    
    Returns:
    	str: The configured evaluation project name, or ``"git-cg-eval"`` when none is provided.
    """
    projects = config.get("projects")
    if isinstance(projects, Mapping):
        eval_p = str(projects.get("eval") or "").strip()
        if eval_p:
            return eval_p
    return str(config.get("project_name") or "").strip() or "git-cg-eval"


def _profile(config: Mapping[str, Any]) -> RedactionProfile | str:
    """Resolve the configured redaction profile.
    
    Parameters:
    	config (Mapping[str, Any]): Configuration containing the optional redaction profile.
    
    Returns:
    	RedactionProfile | str: The configured redaction profile, or the default scrubbing profile.
    """
    return config.get("redaction_profile") or RedactionProfile.DEFAULT_SCRUB.value


def _environment(config: Mapping[str, Any]) -> str:
    """Resolve the configured export environment.
    
    Parameters:
    	config (Mapping[str, Any]): Configuration containing the optional environment value.
    
    Returns:
    	str: The configured environment, or ``"eval"`` when no value is provided.
    """
    return str(config.get("environment") or "eval")


def _item_ref(bundle: Mapping[str, Any], index: int) -> str:
    """Identify a stable reference for a bundle.
    
    Parameters:
    	bundle (Mapping[str, Any]): Bundle data containing a possible identifier.
    	index (int): Position used to generate a fallback reference.
    
    Returns:
    	str: The first recognised non-empty bundle identifier, or an indexed fallback.
    """
    for key in ("id", "case_id", "bundle_id", "final_message_sha256"):
        value = bundle.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return f"bundle_{index}"


def _normalize_layer_a(
    layer_a_objects: LayerAObjects | Mapping[str, Any] | Sequence[Mapping[str, Any]] | None,
) -> LayerAObjects:
    """Normalise Layer-A input into a LayerAObjects container.
    
    Parameters:
    	layer_a_objects: Layer-A data supplied as an existing container, mapping, sequence of bundle mappings, or None.
    
    Returns:
    	The normalised LayerAObjects container.
    """
    if layer_a_objects is None:
        return LayerAObjects()
    if isinstance(layer_a_objects, LayerAObjects):
        return layer_a_objects
    if isinstance(layer_a_objects, Mapping):
        # Bare bundle dict vs envelope.
        if "schema_version" in layer_a_objects or "attempts" in layer_a_objects or "score_card" in layer_a_objects:
            return LayerAObjects(bundles=(dict(layer_a_objects),))
        return LayerAObjects.from_mapping(layer_a_objects)
    # Sequence of bundles.
    bundles = [dict(b) for b in layer_a_objects if isinstance(b, Mapping)]
    return LayerAObjects(bundles=tuple(bundles))


def build_export_plan(
    layer_a_objects: LayerAObjects | Mapping[str, Any] | Sequence[Mapping[str, Any]] | None,
    config: Mapping[str, Any] | None,
    *,
    repo_root: Path | None = None,
    git_sha: str | None = None,
    dataset_id: str = "cm-eval-fixtures-core",
    project_lane: str = "eval",
    lane: str = "mirror",
    catalog_version: str = "v0",
    when: datetime | None = None,
    network_export: bool = False,
    enqueue: bool = True,
    include_train: bool | None = None,
) -> ExportPlanResult:
    """
    Compose Layer-A evidence into redacted, projected export batches and optionally enqueue them.
    
    Parameters:
        layer_a_objects: Layer-A bundles and optional session threads to project.
        config: Export configuration mapping.
        repo_root: Repository root used for queue persistence.
        git_sha: Git revision associated with the export.
        dataset_id: Dataset identifier for experiment metadata.
        project_lane: Project lane for experiment metadata.
        lane: Export lane for experiment metadata.
        catalog_version: Catalogue version for experiment metadata.
        when: Timestamp used for experiment naming.
        network_export: Whether network-export Git revision requirements apply.
        enqueue: Whether to persist the constructed batches.
        include_train: Override the input's train-projection setting.
    
    Returns:
        An export plan containing projection counts, batch metadata, queue references,
        health, errors, notes, and optional train data. Product acceptance is never
        blocked by export failures.
    """
    cfg = _as_config(config)
    mode = str(cfg.get("mode") or "off")
    objects = _normalize_layer_a(layer_a_objects)
    do_train = objects.include_train if include_train is None else bool(include_train)

    notes: list[str] = []
    error_classes: list[str] = []

    # E12: invalid mode tokens fail closed to off for capture safety, but the
    # composition join must surface config_error (not silent skipped_off only).
    bad_mode = mode_fallback_token(cfg)
    if bad_mode is not None:
        n_objects = len(objects.bundles) + len(objects.session_threads)
        return ExportPlanResult(
            mode=mode,
            health=ExportHealth.CONFIG_ERROR,
            skipped=n_objects,
            failed=0,
            error_classes=("export_validation",),
            notes=(
                f"config_error: invalid mode token {bad_mode!r} "
                f"(fail-closed to {mode!r}; operator export misconfiguration)",
            ),
        )

    if mode in _SHORT_CIRCUIT_MODES:
        health = ExportHealth.SKIPPED_OFF if mode in {"off"} else ExportHealth.DEFERRED
        return ExportPlanResult(
            mode=mode,
            health=health,
            skipped=len(objects.bundles) + len(objects.session_threads),
            notes=(f"mode={mode}; composition short-circuit",),
        )

    if not objects.bundles and not objects.session_threads:
        return ExportPlanResult(
            mode=mode,
            health=ExportHealth.DEFERRED,
            notes=("no layer-a objects to project",),
            skipped=0,
        )

    profile = _profile(cfg)
    project = _project_name(cfg)
    environment = _environment(cfg)

    transport_items: list[tuple[str, dict[str, Any]]] = []
    projected = 0
    failed = 0
    redacted_bundles: list[dict[str, Any]] = []

    # Map sessions by loose correlation (session_thread_id) for per-bundle attach.
    sessions_by_id: dict[str, dict[str, Any]] = {}
    orphan_sessions: list[dict[str, Any]] = []
    for session in objects.session_threads:
        sid = str(session.get("session_thread_id") or session.get("id") or "").strip()
        if sid:
            sessions_by_id.setdefault(sid, session)
        else:
            orphan_sessions.append(session)

    for index, bundle in enumerate(objects.bundles):
        item_ref = _item_ref(bundle, index)
        try:
            redacted = redact_bundle_for_export(bundle, profile)
            redacted_bundles.append(redacted)
            content_key = str(redacted.get("id") or redacted.get("case_id") or item_ref)
            experiment = build_experiment(
                lane,
                catalog_version,
                git_sha=git_sha,
                when=when,
                network_export=network_export,
                repo_root=repo_root,
                environment=environment,
                project=project,
                project_lane=project_lane,
                dataset_id=dataset_id,
                artifact_class=str(redacted.get("artifact_class") or "export_batch"),
                redaction_profile=str(
                    redacted.get("redaction_profile")
                    or (redacted.get("meta") or {}).get("redaction_profile")
                    or profile
                ),
                content_key=content_key,
            )
            exp_name = str(experiment.get("experiment_name") or "")
            trace = project_bundle_to_trace(redacted, experiment_name=exp_name)
            feedback = project_score_card_to_feedback(redacted, experiment_name=exp_name)

            # Prefer source correlation before redacted/top-level fallthrough
            # (defense-in-depth if redaction omits session ids under thin profiles).
            source_meta = bundle.get("meta") if isinstance(bundle.get("meta"), dict) else {}
            redacted_meta = redacted.get("meta") if isinstance(redacted.get("meta"), dict) else {}
            sid = str(
                bundle.get("session_thread_id")
                or source_meta.get("session_thread_id")
                or redacted.get("session_thread_id")
                or redacted_meta.get("session_thread_id")
                or ""
            ).strip()
            thread_payload = None
            if sid and sid in sessions_by_id:
                thread_payload = project_session_thread(
                    sessions_by_id.pop(sid),
                    experiment_name=exp_name,
                )

            payload: dict[str, Any] = {
                "trace": trace,
                "feedback": feedback,
                "experiment": experiment,
                "gate": redacted.get("gate"),
                "score_card": redacted.get("score_card") or redacted.get("product_card"),
                "bundle_id": redacted.get("id") or redacted.get("case_id"),
                "artifact_class": redacted.get("artifact_class"),
                "authority": (trace.get("metadata") or {}).get("authority"),
            }
            if thread_payload is not None:
                payload["thread"] = thread_payload

            transport_items.append((item_ref, payload))
            projected += 1
        except (ProjectionError, ExportSizeError, ValueError, TypeError) as exc:
            failed += 1
            err_class = getattr(exc, "error_class", "export_validation")
            error_classes.append(str(err_class))
            notes.append(f"{item_ref}: {exc}"[:200])

    # Orphan / remaining sessions project as standalone thread items.
    remaining_sessions: Iterable[dict[str, Any]] = [
        *sessions_by_id.values(),
        *orphan_sessions,
    ]
    for s_index, session in enumerate(remaining_sessions):
        s_ref = str(session.get("session_thread_id") or session.get("id") or f"session_{s_index}")
        try:
            experiment = build_experiment(
                lane,
                catalog_version,
                git_sha=git_sha,
                when=when,
                network_export=network_export,
                repo_root=repo_root,
                environment=environment,
                project=project,
                project_lane=project_lane,
                dataset_id=dataset_id,
                artifact_class="export_batch",
                redaction_profile=str(session.get("redaction_profile") or profile),
                content_key=s_ref,
            )
            exp_name = str(experiment.get("experiment_name") or "")
            thread_payload = project_session_thread(session, experiment_name=exp_name)
            transport_items.append(
                (
                    s_ref,
                    {
                        "thread": thread_payload,
                        "experiment": experiment,
                        "authority": (thread_payload.get("metadata") or {}).get("authority"),
                    },
                )
            )
            projected += 1
        except (ProjectionError, ValueError, TypeError) as exc:
            failed += 1
            err_class = getattr(exc, "error_class", "export_validation")
            error_classes.append(str(err_class))
            notes.append(f"{s_ref}: {exc}"[:200])

    train_payload: dict[str, Any] | None = None
    if do_train and redacted_bundles:
        try:
            train_payload = build_train_projection(redacted_bundles)
        except Exception as exc:  # train projection must not kill export plan
            error_classes.append("export_validation")
            notes.append(f"train_projection: {exc}"[:200])

    if not transport_items:
        health = ExportHealth.CONFIG_ERROR if failed else ExportHealth.DEFERRED
        return ExportPlanResult(
            mode=mode,
            health=health,
            projected=projected,
            failed=failed,
            error_classes=tuple(error_classes),
            notes=tuple(notes) or ("no transport items after projection",),
            train=train_payload,
        )

    try:
        batches = build_export_batches(
            transport_items,
            profile,
            project=project,
            experiment_id=str((transport_items[0][1].get("experiment") or {}).get("experiment_name") or ""),
            environment=environment,
            dataset_id=dataset_id,
            project_lane=project_lane,
        )
    except ExportSizeError as exc:
        return ExportPlanResult(
            mode=mode,
            health=ExportHealth.CONFIG_ERROR,
            projected=projected,
            failed=failed + 1,
            error_classes=tuple([*error_classes, "export_size"]),
            notes=tuple([*notes, str(exc)[:200]]),
            train=train_payload,
        )

    if not enqueue:
        return ExportPlanResult(
            mode=mode,
            health=ExportHealth.PENDING,
            batch_ids=tuple(str(b.get("batch_id") or b.get("id") or "") for b in batches),
            item_refs=tuple(ref for ref, _ in transport_items),
            projected=projected,
            enqueued=0,
            skipped=len(batches),
            failed=failed,
            error_classes=tuple(error_classes),
            notes=tuple([*notes, "enqueue=false; batches built only"]),
            train=train_payload,
        )

    queue_refs: list[str] = []
    batch_ids: list[str] = []
    enqueued = 0
    for batch in batches:
        try:
            path = enqueue_export_batch(
                batch,
                repo_root=repo_root,
                network_export=network_export,
                git_sha=git_sha,
            )
            qid = path.stem
            queue_refs.append(qid)
            batch_ids.append(str(batch.get("batch_id") or batch.get("id") or qid))
            enqueued += 1
        except ExportQueueError as exc:
            failed += 1
            error_classes.append(exc.error_class)
            notes.append(str(exc)[:200])
        except Exception as exc:
            failed += 1
            error_classes.append("export_validation")
            notes.append(str(exc)[:200])

    if enqueued and not failed:
        health = ExportHealth.PENDING
    elif enqueued and failed:
        health = ExportHealth.PARTIAL
    elif failed:
        health = ExportHealth.CONFIG_ERROR
    else:
        health = ExportHealth.DEFERRED

    return ExportPlanResult(
        mode=mode,
        health=health,
        queue_row_refs=tuple(queue_refs),
        batch_ids=tuple(batch_ids),
        item_refs=tuple(ref for ref, _ in transport_items),
        projected=projected,
        enqueued=enqueued,
        failed=failed,
        error_classes=tuple(error_classes),
        notes=tuple(notes),
        train=train_payload,
    )
