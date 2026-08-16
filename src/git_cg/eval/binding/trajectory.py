"""S3 trajectory evidence emitter (R7 / D3 / D10).

Emits schema-valid ``trajectory_evidence_v1`` objects: the **declared** stage
vocabulary (D3, ordered closed list) versus the **observed** stage names that
actually ran. The emitter is pure and deterministic — no clock, no network, no
Opik I/O — and never fabricates stage success (N19 F7).

Plane separation (N19.6): this module only *produces* trajectory evidence.
**Family H** owns trajectory completeness/policy scoring; **Family I** validates
topology evidence only and never consumes trajectory as topology. Behavioural
completeness (``meta.complete``) is an eval-class signal, never a product fail.

Shape law (D10): top-level ``declared_stages`` / ``observed_stages`` are plain
``string[]`` of stage names (frozen schema ``additionalProperties: false``).
Rich ``{name, status}`` detail and the ``complete`` flag live **only** under
``meta``.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

__all__ = [
    "DECLARED_STAGES",
    "OBSERVED_STAGE_STATUSES",
    "REQUIRED_CORE_STAGES",
    "TrajectoryError",
    "build_trajectory_evidence",
    "is_complete",
    "validate_observed_stages",
]

# D3 — ordered closed declared stage vocabulary (product accept-path taxonomy).
# This is the full default declared list; conditional stages are *observed*
# only when they actually ran.
DECLARED_STAGES: tuple[str, ...] = (
    "diff_extraction",
    "path_classification",
    "intent_ranking",
    "contract_resolution",
    "llm_generation",
    "plan_normalisation",
    "gold_evaluation",
    "presentation_guard",
    "regeneration",
    "fallback",
    "final_render",
    "accept_path_finalization",
    "opik_export",
)

# D3 minimal happy-path observed core (capture on + generation ran). Used by
# ``is_complete`` to derive the behavioural completeness signal.
REQUIRED_CORE_STAGES: frozenset[str] = frozenset(
    {
        "diff_extraction",
        "path_classification",
        "intent_ranking",
        "contract_resolution",
        "gold_evaluation",
        "presentation_guard",
        "final_render",
        "accept_path_finalization",
    }
)

# D10 — allowed ``status`` values for ``meta.observed_stage_details`` entries.
OBSERVED_STAGE_STATUSES: frozenset[str] = frozenset({"observed", "skipped", "failed", "unknown"})

_DECLARED_SET: frozenset[str] = frozenset(DECLARED_STAGES)


class TrajectoryError(ValueError):
    """Trajectory evidence construction failure (fail closed)."""


def _as_name_list(observed: Iterable[str]) -> list[str]:
    """Normalise observed stage names to a list of non-empty strings.

    Fail closed on non-string or blank entries — observed stages are stage
    *names* only (D10), never ``{name, status}`` objects.
    """
    names: list[str] = []
    for item in observed:
        if not isinstance(item, str):
            raise TrajectoryError(f"observed stage must be a stage-name string, got {type(item).__name__}")
        name = item.strip()
        if not name:
            raise TrajectoryError("observed stage name must be non-empty")
        names.append(name)
    return names


def validate_observed_stages(observed: Iterable[str]) -> list[str]:
    """Validate observed stage names against the D3 closed vocabulary.

    Returns the de-duplicated observed names in D3 declared order. Fails closed
    on unknown stage names (never invent stages that did not run).
    """
    names = _as_name_list(observed)
    unknown = [n for n in names if n not in _DECLARED_SET]
    if unknown:
        raise TrajectoryError(f"unknown observed stage(s) not in D3 declared vocabulary: {unknown}")
    seen: set[str] = set()
    dupes = [n for n in names if n in seen or seen.add(n)]
    if dupes:
        raise TrajectoryError(f"duplicate observed stage(s): {sorted(set(dupes))}")
    order = {name: i for i, name in enumerate(DECLARED_STAGES)}
    return sorted(names, key=order.__getitem__)


def is_complete(observed: Iterable[str]) -> bool:
    """Behavioural completeness signal (D3/D10 ``meta.complete``).

    ``True`` only when ``accept_path_finalization`` is observed **and** every
    required core stage is present. This is an eval-class signal, never a
    product fail.
    """
    names = set(_as_name_list(observed))
    if "accept_path_finalization" not in names:
        return False
    return REQUIRED_CORE_STAGES.issubset(names)


def _normalise_details(
    details: Iterable[dict[str, Any]] | None,
) -> list[dict[str, str]]:
    """Validate optional ``meta.observed_stage_details`` entries.

    Each entry must be ``{"name": <declared stage>, "status": <allowed>}``.
    Names must be a subset of the declared vocabulary; detail is additive
    telemetry only — consumers work from ``observed_stages`` strings alone.
    """
    if details is None:
        return []
    out: list[dict[str, str]] = []
    for entry in details:
        if not isinstance(entry, dict):
            raise TrajectoryError("observed_stage_details entries must be objects")
        name = entry.get("name")
        status = entry.get("status")
        if not isinstance(name, str) or name.strip() not in _DECLARED_SET:
            raise TrajectoryError(f"observed_stage_details name must be a declared stage: {name!r}")
        if status not in OBSERVED_STAGE_STATUSES:
            raise TrajectoryError(
                f"observed_stage_details status must be one of {sorted(OBSERVED_STAGE_STATUSES)}: {status!r}"
            )
        out.append({"name": name.strip(), "status": status})
    return out


def build_trajectory_evidence(
    evidence_id: str,
    observed_stages: Iterable[str],
    *,
    declared_stages: Iterable[str] | None = None,
    observed_stage_details: Iterable[dict[str, Any]] | None = None,
    notes: str | None = None,
    metric_catalog: str | None = None,
    schema_pack: str | None = None,
) -> dict[str, Any]:
    """Build a schema-valid ``trajectory_evidence_v1`` object (D10).

    ``observed_stages`` are validated against the D3 closed vocabulary and
    emitted in declared order. ``meta.complete`` is derived from the observed
    set; optional ``meta.observed_stage_details`` carries additive
    ``{name, status}`` telemetry. No top-level ``complete`` key is emitted
    (frozen schema forbids it).
    """
    if not isinstance(evidence_id, str) or not evidence_id.strip():
        raise TrajectoryError("trajectory evidence id must be a non-empty string")

    declared = list(DECLARED_STAGES) if declared_stages is None else validate_observed_stages(declared_stages)
    observed = validate_observed_stages(observed_stages)

    meta: dict[str, Any] = {"complete": is_complete(observed)}
    details = _normalise_details(observed_stage_details)
    if details:
        meta["observed_stage_details"] = details

    evidence: dict[str, Any] = {
        "schema_version": "trajectory_evidence_v1",
        "id": evidence_id.strip(),
        "declared_stages": declared,
        "observed_stages": observed,
        "meta": meta,
    }
    if notes is not None:
        evidence["notes"] = notes
    if metric_catalog is not None:
        evidence["metric_catalog"] = metric_catalog
    if schema_pack is not None:
        evidence["schema_pack"] = schema_pack
    return evidence
