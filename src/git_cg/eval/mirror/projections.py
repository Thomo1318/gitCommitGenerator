"""Bundle → Opik projections (plan §7.2.9, §8.4 deliverable 4).

Projects a redacted ``ape_bundle_v1`` into the upload payload shapes:

* **trace/span** — the final-bytes-bound attempt as a trace; the deterministic
  gate + score card become metadata/feedback (never re-scored in the cloud).
* **thread** — the ``commit_session_thread_v1`` twin as an Opik thread.
* **feedback** — the product deterministic ``score_card`` as feedback scores.

These projections are **lossy by design**: they carry the redacted, allowlisted
bundle, not raw diffs/secrets. No cloud-side scoring rules are created from raw
traces (FIND-013 / §7.2.10); the deterministic product score card is the
authority and is exported as feedback.

Projection laws (Slice 5):

* **P1-8** — final attempt is selected by explicit ``final_accept`` binding
  (attempt ``artifact_class``, matching final-message identity, or sole attempt
  under a final_accept bundle). List order alone is never authoritative when
  multiple unbound attempts exist (fail closed as ``export_validation``).
* **P1-9** — boolean score-card entries project as ``1.0`` / ``0.0`` with
  ``polarity=pass_fail`` (R5); they are never silently dropped.
* **P1-10** — feedback ``source`` uses the closed enum value ``local_wrapper``.
* **E9** — every feedback/trace metadata block carries authority annotations
  (metric id, polarity, artifact class, schema/catalog pins, train/split labels
  where present, redaction profile, experiment identity).

Pure offline builders — no network, no Opik import.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Final

from git_cg.eval.catalog import load_metric_catalog
from git_cg.eval.enums import ArtifactClass, Polarity, Source
from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin

__all__ = [
    "FEEDBACK_SOURCE",
    "ProjectionError",
    "authority_annotations",
    "project_bundle_to_trace",
    "project_score_card_to_feedback",
    "project_session_thread",
    "select_final_attempt",
]

#: Closed feedback source for product score-card projections (P1-10).
FEEDBACK_SOURCE: Final[str] = Source.LOCAL_WRAPPER.value

#: Non-metric score-card keys retained only as metadata (never feedback rows).
_SCORE_CARD_META_KEYS: Final[frozenset[str]] = frozenset(
    {
        "label",
        "notes",
        "note",
        "comment",
        "comments",
        "description",
        "summary",
    }
)


class ProjectionError(ValueError):
    """Projection failed closed (``export_validation`` class equivalent)."""

    def __init__(self, message: str, *, error_class: str = "export_validation") -> None:
        self.error_class = error_class
        super().__init__(message)


def _attempts(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract dictionary-valued attempts from a bundle.
    
    Parameters:
    	bundle (dict[str, Any]): Bundle containing the attempts collection.
    
    Returns:
    	list[dict[str, Any]]: Dictionary-valued attempts from the bundle.
    """
    raw = bundle.get("attempts") or []
    if not isinstance(raw, list):
        return []
    return [a for a in raw if isinstance(a, dict)]


def _attempt_artifact_class(attempt: dict[str, Any]) -> str | None:
    """Return the attempt's artifact class when one is provided directly or in its metadata."""
    direct = attempt.get("artifact_class")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    meta = attempt.get("meta") if isinstance(attempt.get("meta"), dict) else {}
    nested = meta.get("artifact_class")
    if isinstance(nested, str) and nested.strip():
        return nested.strip()
    return None


def select_final_attempt(bundle: dict[str, Any]) -> dict[str, Any] | None:
    """
    Select the attempt bound to the bundle's final output.
    
    Attempts are matched by explicit ``final_accept`` classification, final-message
    hash, or final-message content. A sole attempt is selected when no stronger
    binding exists. A bundle-level final message is synthesised as a final-accept
    carrier when no attempts are present and the bundle is classified as
    ``final_accept``.
    
    Parameters:
        bundle (dict[str, Any]): Bundle containing attempts and final-output
            binding information.
    
    Returns:
        dict[str, Any] | None: The selected attempt, or a synthesised final-accept
        carrier. Returns ``None`` for an empty bundle without a final message.
    
    Raises:
        ProjectionError: If multiple attempts claim final acceptance or share the
        same final-output binding, or if multiple attempts have no identifiable
        final binding.
    """
    attempts = _attempts(bundle)
    final_token = ArtifactClass.FINAL_ACCEPT.value
    bundle_class = str(bundle.get("artifact_class") or "").strip()
    bundle_message = bundle.get("final_message")
    bundle_sha = bundle.get("final_message_sha256")

    if not attempts:
        if bundle_class == final_token and bundle_message is not None:
            return {
                "final_message": bundle_message,
                "final_message_sha256": bundle_sha,
                "scored_target": "final_message",
                "artifact_class": final_token,
            }
        return None

    explicit = [a for a in attempts if _attempt_artifact_class(a) == final_token]
    if len(explicit) == 1:
        return explicit[0]
    if len(explicit) > 1:
        raise ProjectionError("multiple attempts claim artifact_class=final_accept (export_validation)")

    if isinstance(bundle_sha, str) and bundle_sha.strip():
        matched = [a for a in attempts if a.get("final_message_sha256") == bundle_sha]
        if len(matched) == 1:
            return matched[0]
        if len(matched) > 1:
            raise ProjectionError("multiple attempts share final_message_sha256 (export_validation)")

    if bundle_message is not None:
        matched = [a for a in attempts if a.get("final_message") == bundle_message]
        if len(matched) == 1:
            return matched[0]
        if len(matched) > 1:
            raise ProjectionError("multiple attempts share final_message identity (export_validation)")

    if len(attempts) == 1:
        return attempts[0]

    # Multiple attempts without an explicit final_accept binding: fail closed.
    raise ProjectionError(
        "final_accept binding not identifiable among attempts (refusing attempts[-1] fallback; export_validation)"
    )


def _bundle_meta(bundle: dict[str, Any]) -> dict[str, Any]:
    meta = bundle.get("meta")
    return dict(meta) if isinstance(meta, dict) else {}


@lru_cache(maxsize=1)
def _metric_index() -> dict[str, dict[str, Any]]:
    """Map metric_id + bare suffixes + names onto catalog rows."""
    catalog = load_metric_catalog()
    index: dict[str, dict[str, Any]] = {}
    for row in catalog.get("metrics") or []:
        if not isinstance(row, dict):
            continue
        mid = row.get("metric_id")
        if not isinstance(mid, str) or not mid:
            continue
        index[mid] = row
        if "." in mid:
            suffix = mid.rsplit(".", 1)[-1]
            # First writer wins for ambiguous bare suffixes.
            index.setdefault(suffix, row)
        name = row.get("name")
        if isinstance(name, str) and name.strip():
            index.setdefault(name.strip().lower(), row)
    return index


def _resolve_metric_row(key: str) -> dict[str, Any] | None:
    """Resolve a metric key to its catalogue entry.
    
    Parameters:
    	key (str): Metric key or name to look up.
    
    Returns:
    	dict[str, Any] | None: The matching metric catalogue entry, or `None` when no entry matches.
    """
    index = _metric_index()
    if key in index:
        return index[key]
    lowered = key.lower()
    if lowered in index:
        return index[lowered]
    # Common dotted alias: format_compliance may live under family prefix later.
    return None


def authority_annotations(
    bundle: dict[str, Any],
    *,
    experiment_name: str,
    metric_id: str | None = None,
    polarity: str | None = None,
    value_kind: str | None = None,
    scored_target: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Builds authority metadata for projected trace and feedback payloads.
    
    Parameters:
    	bundle (dict[str, Any]): Bundle containing provenance and redaction metadata.
    	experiment_name (str): Name of the experiment associated with the projection.
    	metric_id (str | None): Identifier of the associated metric.
    	polarity (str | None): Metric scoring polarity.
    	value_kind (str | None): Kind of value represented by the metric.
    	scored_target (str | None): Target used for scoring.
    	extra (dict[str, Any] | None): Additional non-null metadata fields to include.
    
    Returns:
    	dict[str, Any]: E9 authority annotations with schema, metric-catalog, provenance, and projection controls.
    """
    meta = _bundle_meta(bundle)
    profile = meta.get("redaction_profile") or bundle.get("redaction_profile") or meta.get("applied_redaction_profile")
    annotations: dict[str, Any] = {
        "metric_id": metric_id,
        "polarity": polarity,
        "value_kind": value_kind or polarity,
        "source": FEEDBACK_SOURCE,
        "authority": "projection",
        "artifact_class": bundle.get("artifact_class") or meta.get("artifact_class"),
        "scored_target": scored_target,
        "schema_pack": schema_pack_pin(),
        "metric_catalog": metric_catalog_pin(),
        "redaction_profile": profile,
        "experiment_name": experiment_name,
        "label": meta.get("label") or meta.get("provenance_label") or bundle.get("provenance_label"),
        "train_label": meta.get("train_label"),
        "split": meta.get("split"),
        "split_group_id": meta.get("split_group_id"),
        "provenance_label": meta.get("provenance_label") or bundle.get("provenance_label"),
        "product_score_authority": True,
        "cloud_rescore_forbidden": True,
    }
    if extra:
        for key, value in extra.items():
            if value is not None:
                annotations[key] = value
    # Drop pure-null optional fields for tighter payloads (pins/source stay).
    required = {
        "source",
        "schema_pack",
        "metric_catalog",
        "experiment_name",
        "product_score_authority",
        "cloud_rescore_forbidden",
        "authority",
    }
    return {k: v for k, v in annotations.items() if v is not None or k in required}


def project_bundle_to_trace(
    bundle: dict[str, Any],
    *,
    experiment_name: str,
) -> dict[str, Any]:
    """
    Project a redacted evaluation bundle into a trace payload.
    
    Parameters:
    	bundle (dict[str, Any]): Redacted evaluation bundle data.
    	experiment_name (str): Name associated with the projected evaluation.
    
    Returns:
    	dict[str, Any]: Trace payload containing redacted final-attempt data, gate results, score-card metadata, and authority annotations.
    """
    final = select_final_attempt(bundle) or {}
    gate = bundle.get("gate") or {}
    score_card = bundle.get("score_card") or bundle.get("product_card") or {}
    annotations = authority_annotations(
        bundle,
        experiment_name=experiment_name,
        scored_target=final.get("scored_target") or "final_message",
        extra={
            "final_accept_bound": (
                str(bundle.get("artifact_class") or "") == ArtifactClass.FINAL_ACCEPT.value
                or _attempt_artifact_class(final) == ArtifactClass.FINAL_ACCEPT.value
            ),
            "bundle_id": bundle.get("id") or bundle.get("case_id"),
        },
    )

    return {
        "input": {
            "bundle_id": bundle.get("id") or bundle.get("case_id"),
            "schema_version": bundle.get("schema_version"),
            "attempt_count": len(_attempts(bundle)),
            "artifact_class": bundle.get("artifact_class"),
        },
        "output": {
            "final_message": final.get("final_message"),
            "scored_target": final.get("scored_target"),
            "final_message_sha256": final.get("final_message_sha256") or bundle.get("final_message_sha256"),
        },
        "metadata": {
            "experiment_name": experiment_name,
            "deterministic_pass": gate.get("deterministic_pass") if isinstance(gate, dict) else None,
            "gate": gate,
            "score_card": score_card,
            "redaction_profile": annotations.get("redaction_profile"),
            "authority": annotations,
        },
    }


def project_session_thread(
    session_thread: dict[str, Any],
    *,
    experiment_name: str,
) -> dict[str, Any]:
    """Project a ``commit_session_thread_v1`` twin to an Opik thread payload.

    Preserves the session id and lifecycle; message versions are carried as
    redacted thread messages. No ids are invented.
    """
    meta = session_thread.get("meta") or {}
    if not isinstance(meta, dict):
        meta = {}
    return {
        "thread_id": session_thread.get("session_thread_id") or session_thread.get("id"),
        "experiment_name": experiment_name,
        "lifecycle": meta.get("lifecycle"),
        "messages": list(session_thread.get("message_versions") or []),
        "metadata": {
            "attempt_ids": list(session_thread.get("attempt_ids") or []),
            "redaction_profile": session_thread.get("redaction_profile"),
            "trace_id": meta.get("trace_id"),
            "generation_thread_id": meta.get("generation_thread_id"),
            "schema_pack": schema_pack_pin(),
            "metric_catalog": metric_catalog_pin(),
            "source": FEEDBACK_SOURCE,
            "authority": "projection",
            "cloud_rescore_forbidden": True,
        },
    }


def _coerce_feedback_value(value: Any) -> tuple[float, str, str] | None:
    """
    Convert a boolean or numeric score-card value into a feedback value, polarity, and value kind.
    
    Parameters:
        value (Any): The score-card value to convert.
    
    Returns:
        tuple[float, str, str] | None: The converted value, polarity, and value kind, or `None` for nonnumeric values.
    """
    if isinstance(value, bool):
        return (1.0 if value else 0.0, Polarity.PASS_FAIL.value, "boolean")
    if isinstance(value, (int, float)):
        return (float(value), Polarity.HIGHER_IS_BETTER.value, "numeric")
    return None


def project_score_card_to_feedback(
    bundle: dict[str, Any],
    *,
    experiment_name: str,
) -> list[dict[str, Any]]:
    """
    Project numeric and boolean score-card values into local feedback records.
    
    Parameters:
        bundle (dict[str, Any]): Bundle containing the score card and final scored target.
        experiment_name (str): Name associated with each feedback record.
    
    Returns:
        list[dict[str, Any]]: Feedback records for projectable score-card values. Boolean
            values are represented as ``1.0`` or ``0.0`` with ``pass_fail`` polarity;
            nonnumeric values are skipped.
    """
    score_card = bundle.get("score_card") or bundle.get("product_card") or {}
    if not isinstance(score_card, dict):
        return []

    final = select_final_attempt(bundle) or {}
    scored_target = final.get("scored_target") or "final_message"
    out: list[dict[str, Any]] = []
    boolean_meta: dict[str, bool] = {}

    for key, value in score_card.items():
        name = str(key)
        if name in _SCORE_CARD_META_KEYS and not isinstance(value, (bool, int, float)):
            continue

        coerced = _coerce_feedback_value(value)
        if coerced is None:
            # Non-numeric/non-bool entries are skipped (labels/strings), not
            # booleans — those are handled above.
            continue

        float_value, default_polarity, value_kind = coerced
        if isinstance(value, bool):
            boolean_meta[name] = value

        row = _resolve_metric_row(name)
        metric_id = str(row["metric_id"]) if row and row.get("metric_id") else name
        if value_kind == "boolean":
            polarity = Polarity.PASS_FAIL.value
        elif row and isinstance(row.get("polarity"), str):
            polarity = row["polarity"]
        else:
            polarity = default_polarity

        annotations = authority_annotations(
            bundle,
            experiment_name=experiment_name,
            metric_id=metric_id,
            polarity=polarity,
            value_kind=value_kind,
            scored_target=scored_target,
            extra={
                "catalog_authority": row.get("authority") if row else None,
                "catalog_family": row.get("family") if row else None,
                "score_card_key": name,
            },
        )
        out.append(
            {
                "name": metric_id,
                "value": float_value,
                "experiment_name": experiment_name,
                "source": FEEDBACK_SOURCE,
                "polarity": polarity,
                "metric_id": metric_id,
                "authority": annotations,
            }
        )

    # Preserve original boolean surface as metadata-adjacent feedback list tag
    # via a non-score field on the last annotation set when present — callers
    # also receive booleans inside projected score_card on the trace.
    if boolean_meta and out:
        # Annotate first row only would be asymmetric; stamp all bool-derived.
        for item in out:
            key = str((item.get("authority") or {}).get("score_card_key") or "")
            if key in boolean_meta:
                auth = dict(item.get("authority") or {})
                auth["boolean_source_value"] = boolean_meta[key]
                item["authority"] = auth
    return out
