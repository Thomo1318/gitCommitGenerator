"""Tier-1 Feedback Definition vocabulary map (S7-2).

Data-only alignment of emitted product/human score names to their
harness-pinned Opik Feedback Definition metadata. The map lives at
``config/feedback_definitions.json`` and is validated against
``schemas/eval/feedback_definition_v1.schema.json``.

Authority / offline-first:
    This map is *vocabulary only*. It never gates CI, never feeds a promote
    decision, and is never read back from Opik. Loading is fail-open to an
    empty map when the data file is absent so the eval harness keeps working
    offline; schema-invalid content raises (that is a real authoring defect).

Scale provenance (normative):
    ``scale_min``/``scale_max``/``categories`` are harness vocabulary
    *conventions* enforced by the drift-guard test and the Opik workspace
    Feedback Definitions — they are NOT claims about what ``human_review_v1``
    or the emitters validate. Landed schema truth: ``human.craft_rating`` is an
    unconstrained ``number``, ``human.gold_dispute`` a plain ``boolean``, and
    only ``human.regime_label`` pins ``enum ['A', 'B', 'unknown']``.

Boundary pins (normative):
    * ``ranking_override`` is a metadata ``bool`` internally
      (``telemetry.py`` ``GenerationTelemetry.ranking_override``); it becomes a
      ``1.0``/``0.0`` float score only at the Opik boundary. The map documents
      this so nothing stores a raw bool as a score value.
    * ``human.notes_present`` is derived/read-only metadata (``notes`` is a
      top-level free-text string in ``human_review_v1``), never a minted FD,
      and excluded from the drift guard.
    * ``final_accept`` is an ``artifact_class``/``provenance_label``
      binding-identity enum value (a provenance tag), not a review-outcome
      score, and is excluded from the Tier-1 FD vocabulary.

Versioning / migration policy (additive-only for ``feedback_definition_v1``):
    * Preserve existing definition IDs; do not silently rename or remove them.
    * Additive new IDs are compatible within the same schema_version only after
      the schema pack and drift-guard registry are updated together.
    * Renames/removals require a new schema/map version (e.g. v2) plus an
      explicit migration note — never reinterpret historical annotations.
    * Unknown future ``schema_version`` values fail closed at load time.
    * Remote Opik FD drift is advisory only; local map remains vocabulary SoT.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from git_cg.eval.paths import REPO_ROOT
from git_cg.eval.schema_pack import validate_instance

SCHEMA_NAME: Final = "feedback_definition_v1"
DATA_PATH: Final = REPO_ROOT / "config" / "feedback_definitions.json"

#: Product-owned scores emitted from ``main.py``.
PRODUCT_SCORES: Final = ("user_acceptance", "ranking_override", "contract_consistent")

#: Human-review scores built by ``review_queue._build_scores``.
HUMAN_SCORES: Final = ("human.craft_rating", "human.gold_dispute", "human.regime_label")

#: Single vocabulary source consumed by the drift-guard test. ``notes_present``
#: is deliberately absent (derived metadata, never a minted FD).
FEEDBACK_DEFINITION_REGISTRY: Final = PRODUCT_SCORES + HUMAN_SCORES


class FeedbackDefinitionError(ValueError):
    """Feedback Definition map load/validation failure."""


#: Supported local map schema versions (unknown versions fail closed).
SUPPORTED_SCHEMA_VERSIONS: Final = frozenset({SCHEMA_NAME})

#: Human-readable additive-only migration policy for operators/docs/tests.
MIGRATION_POLICY: Final = (
    "additive_only_v1: preserve IDs; additions require schema+registry update; "
    "renames/removals need new schema_version + explicit migration; "
    "unknown versions fail closed; no silent historical reinterpretation"
)


def assert_supported_schema_version(schema_version: str) -> None:
    """Fail closed when ``schema_version`` is not in the supported set."""
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise FeedbackDefinitionError(
            f"unsupported feedback definition schema_version: {schema_version!r} "
            f"(supported: {sorted(SUPPORTED_SCHEMA_VERSIONS)}; policy={MIGRATION_POLICY})"
        )


def load_feedback_definitions(path: Path | None = None) -> dict[str, Any]:
    """Load and validate the Tier-1 Feedback Definition map.

    Fail-open to an empty map when the data file is absent (offline-first:
    a missing optional vocabulary file is not an eval failure). Raise
    :class:`FeedbackDefinitionError` on malformed JSON or schema-invalid
    content — those are real authoring defects and must fail closed.
    """
    target = path if path is not None else DATA_PATH
    if not target.is_file():
        return {"schema_version": SCHEMA_NAME, "definitions": {}}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FeedbackDefinitionError(f"unreadable feedback definitions: {target}") from exc
    if not isinstance(data, dict):
        raise FeedbackDefinitionError(f"feedback definitions must be an object: {target}")
    schema_version = data.get("schema_version")
    if not isinstance(schema_version, str) or not schema_version.strip():
        raise FeedbackDefinitionError(f"feedback definitions missing schema_version: {target}")
    assert_supported_schema_version(schema_version.strip())
    try:
        validate_instance(SCHEMA_NAME, data)
    except Exception as exc:  # schema_pack raises SchemaPackError (ValueError)
        raise FeedbackDefinitionError(f"feedback definitions failed schema validation: {target}") from exc
    return data


def defined_score_names(definitions: dict[str, Any] | None = None) -> list[str]:
    """Return the sorted score names present in the map (loaded if omitted)."""
    data = definitions if definitions is not None else load_feedback_definitions()
    defs = data.get("definitions", {})
    return sorted(defs) if isinstance(defs, dict) else []


__all__ = [
    "DATA_PATH",
    "FEEDBACK_DEFINITION_REGISTRY",
    "HUMAN_SCORES",
    "MIGRATION_POLICY",
    "PRODUCT_SCORES",
    "SCHEMA_NAME",
    "SUPPORTED_SCHEMA_VERSIONS",
    "FeedbackDefinitionError",
    "assert_supported_schema_version",
    "defined_score_names",
    "load_feedback_definitions",
]
