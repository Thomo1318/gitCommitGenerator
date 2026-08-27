"""Fixture → ape_bundle_v1 / eval_case_v1 encoder."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from git_cg.eval.corpus.canonical import content_sha256, message_sha256
from git_cg.eval.corpus.task_input import TaskInputError, project_generation_task_input
from git_cg.eval.enums import ARTIFACT_CLASS, PROVENANCE_LABEL, REDACTION_PROFILE
from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin
from git_cg.eval.schema_pack import SchemaPackError, validate_instance

PRODUCER_ID = "fixture_encoder_s1"


class CorpusEncodeError(ValueError):
    """Fixture encode / validation failure."""


def _require_str(data: Mapping[str, Any], key: str) -> str:
    """Require a non-empty string field and fail closed otherwise."""
    val = data.get(key)
    if not isinstance(val, str) or not val.strip():
        raise CorpusEncodeError(f"missing or empty required field: {key}")
    return val


def _optional_str(data: Mapping[str, Any], key: str, *, allow_empty: bool = False) -> str | None:
    """Return the raw string when present; reject blank unless allow_empty."""
    val = data.get(key)
    if val is None:
        return None
    if not isinstance(val, str):
        raise CorpusEncodeError(f"{key} must be a string when present")
    if not allow_empty and not val.strip():
        raise CorpusEncodeError(f"{key} must be non-empty when present")
    return val


def _optional_str_list(data: Mapping[str, Any], key: str) -> list[str] | None:
    """Return ``list(val)`` when present; require an array of strings."""
    val = data.get(key)
    if val is None:
        return None
    if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
        raise CorpusEncodeError(f"{key} must be an array of strings when present")
    return list(val)


def _validate_enum(value: str, allowed: tuple[str, ...], field: str) -> str:
    """Fail closed when ``value`` is outside the closed enum vocabulary."""
    if value not in allowed:
        raise CorpusEncodeError(f"unknown {field}: {value!r}; allowed={list(allowed)}")
    return value


def _meta_with_producer(meta: Mapping[str, Any] | None, *, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Attach producer metadata while preserving scrub-safe fields."""
    out: dict[str, Any] = {}
    if meta:
        if not isinstance(meta, Mapping):
            raise CorpusEncodeError("meta must be an object")
        out.update(dict(meta))
    out.setdefault("producer", PRODUCER_ID)
    if extra:
        out.update(extra)
    return out


def _as_mapping(value: Any, field: str) -> Mapping[str, Any] | None:
    """Return ``value`` when it is a mapping; ``None`` if absent."""
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise CorpusEncodeError(f"{field} must be an object when present")
    return value


def _validate_topology_and_evidence(meta: Mapping[str, Any]) -> None:
    """Optional S1 fail-closed probes for topology / counters / split / replay.

    Full Family I scoring is S2+. S1 only enforces fixture-declared require_*
    contracts so seed negatives and valid controls can live offline today.
    """
    topology = _as_mapping(meta.get("topology"), "meta.topology")
    if topology is not None:
        status = topology.get("status")
        if status is not None and status not in {
            "complete",
            "incomplete",
            "present",
            "absent",
            "unknown",
        }:
            raise CorpusEncodeError(f"unknown topology status: {status!r}")
        required = topology.get("required_spans")
        observed = topology.get("observed_spans")
        missing = topology.get("missing_spans")
        if required is not None and (not isinstance(required, list) or not all(isinstance(x, str) for x in required)):
            raise CorpusEncodeError("meta.topology.required_spans must be an array of strings")
        if observed is not None and (not isinstance(observed, list) or not all(isinstance(x, str) for x in observed)):
            raise CorpusEncodeError("meta.topology.observed_spans must be an array of strings")
        if missing is not None and (not isinstance(missing, list) or not all(isinstance(x, str) for x in missing)):
            raise CorpusEncodeError("meta.topology.missing_spans must be an array of strings")

        require_complete = bool(topology.get("require_complete_for_encode"))
        if require_complete:
            if status == "incomplete":
                raise CorpusEncodeError("topology incomplete: require_complete_for_encode=true and status=incomplete")
            if isinstance(required, list) and isinstance(observed, list):
                missing_calc = sorted(set(required) - set(observed))
                if missing_calc:
                    raise CorpusEncodeError("topology incomplete: missing required spans: " + ", ".join(missing_calc))
            if isinstance(missing, list) and missing:
                raise CorpusEncodeError(
                    "topology incomplete: missing_spans non-empty under require_complete_for_encode"
                )

    evidence = _as_mapping(meta.get("evidence"), "meta.evidence")
    if evidence is not None and bool(evidence.get("require_counter_span_consistent")):
        counters = evidence.get("counters")
        span_counts = evidence.get("span_counts")
        if not isinstance(counters, Mapping) or not isinstance(span_counts, Mapping):
            raise CorpusEncodeError(
                "counter/span consistency check requires meta.evidence.counters and span_counts objects"
            )
        regen_attempts = counters.get("gold_regen_attempts", 0)
        regen_spans = span_counts.get("regeneration", 0)
        for field, value in (
            ("counters.gold_regen_attempts", regen_attempts),
            ("span_counts.regeneration", regen_spans),
        ):
            if not isinstance(value, int) or isinstance(value, bool):
                raise CorpusEncodeError(f"counter/span values must be integers: {field}={value!r}")
        regen_attempts_n = regen_attempts
        regen_spans_n = regen_spans
        if regen_attempts_n > 0 and regen_spans_n <= 0:
            raise CorpusEncodeError(
                "counter/span mismatch: gold_regen_attempts>0 but regeneration span count is 0 "
                "(Session-12 class / i.counter_span_consistent)"
            )
        if regen_attempts_n == 0 and regen_spans_n > 0:
            raise CorpusEncodeError("counter/span mismatch: regeneration spans present but gold_regen_attempts==0")

    split = _as_mapping(meta.get("split"), "meta.split")
    if split is not None and bool(split.get("forbid_train_and_gate_co_membership")):
        train_lane = split.get("train_lane")
        gate_lane = split.get("gate_lane")
        contaminated = bool(split.get("contaminated"))
        if contaminated or (
            isinstance(train_lane, str)
            and train_lane.startswith("train_")
            and isinstance(gate_lane, str)
            and gate_lane.startswith("gate_")
        ):
            raise CorpusEncodeError(
                "split contamination: fixture claims both train and gate lane membership "
                f"(train_lane={train_lane!r}, gate_lane={gate_lane!r})"
            )

    replay = _as_mapping(meta.get("replay"), "meta.replay")
    if replay is not None and bool(replay.get("require_lineage_fields")) and bool(replay.get("is_replay")):
        parent_trace = replay.get("parent_trace_id")
        parent_thread = replay.get("parent_session_thread_id")
        missing_fields = []
        if not (isinstance(parent_trace, str) and parent_trace.strip()):
            missing_fields.append("parent_trace_id")
        if not (isinstance(parent_thread, str) and parent_thread.strip()):
            missing_fields.append("parent_session_thread_id")
        if missing_fields:
            raise CorpusEncodeError("replay lineage incomplete: missing " + ", ".join(missing_fields))


def encode_fixture(
    fixture: Mapping[str, Any],
    *,
    case_id: str | None = None,
    suite_id: str | None = None,
    validate: bool = True,
) -> dict[str, Any]:
    """Encode a committed fixture object into bundle + case + identities.

    Returns a mapping with ``bundle``, ``case``, ``bundle_ref``, ``bundle_hash``,
    ``case_hash``, ``canonical_bundle``, and ``canonical_case``. Raises
    ``CorpusEncodeError`` when the fixture or generated records fail validation.
    Fixture-level ``session_thread_id`` is strip-normalised before bundle identity.
    """
    if not isinstance(fixture, Mapping):
        raise CorpusEncodeError("fixture must be an object")

    resolved_case_id = case_id or fixture.get("case_id")
    if not isinstance(resolved_case_id, str) or not resolved_case_id.strip():
        raise CorpusEncodeError("case_id is required")
    resolved_case_id = resolved_case_id.strip()

    artifact_class = fixture.get("artifact_class", "fixture_expected")
    if not isinstance(artifact_class, str):
        raise CorpusEncodeError("artifact_class must be a string")
    artifact_class = _validate_enum(artifact_class, ARTIFACT_CLASS, "artifact_class")

    # Binding defaults: fixtures/archive seeds are unbound unless explicitly bound.
    if "bound" in fixture:
        bound = fixture["bound"]
        if not isinstance(bound, bool):
            raise CorpusEncodeError("bound must be a boolean")
    else:
        bound = False

    provenance_label = fixture.get("provenance_label")
    if provenance_label is None:
        # sensible defaults for offline seeds
        provenance_label = "fixture" if artifact_class in {"fixture", "fixture_expected"} else "Opik-unbound"
    if not isinstance(provenance_label, str):
        raise CorpusEncodeError("provenance_label must be a string")
    provenance_label = _validate_enum(provenance_label, PROVENANCE_LABEL, "provenance_label")

    # Fail closed: never silently promote unbound historical evidence to final_accept.
    if bound is False and artifact_class == "final_accept":
        raise CorpusEncodeError(
            "artifact_class=final_accept requires bound=true; "
            "unbound historical evidence must not use final_accept artifact class"
        )
    if bound is False and provenance_label == "final_accept":
        raise CorpusEncodeError(
            "provenance_label=final_accept requires bound=true; "
            "unbound historical evidence must use Opik-unbound/fixture/Git-* labels"
        )
    if bound is True and provenance_label == "Opik-unbound":
        raise CorpusEncodeError("bound=true is incompatible with provenance_label=Opik-unbound")

    redaction_profile = fixture.get("redaction_profile", "default_scrub")
    if not isinstance(redaction_profile, str):
        raise CorpusEncodeError("redaction_profile must be a string")
    redaction_profile = _validate_enum(redaction_profile, REDACTION_PROFILE, "redaction_profile")

    final_message = _optional_str(fixture, "final_message")
    expected_final_message = _optional_str(fixture, "expected_final_message")
    expected_gold_codes = _optional_str_list(fixture, "expected_gold_codes")
    failure_ids = _optional_str_list(fixture, "failure_ids")
    prevention_ids = _optional_str_list(fixture, "prevention_ids")
    regime = fixture.get("regime")
    if regime is not None and regime not in {"A", "B", "unknown", "n/a"}:
        raise CorpusEncodeError(f"invalid regime: {regime!r}")
    instance_kind = _optional_str(fixture, "instance_kind")
    path_class_gate = fixture.get("path_class_gate", None)
    if path_class_gate is not None and not isinstance(path_class_gate, str):
        raise CorpusEncodeError("path_class_gate must be a string or null")

    # Archive-shaped enforcement when source declares 204_archive.
    corpus_source = None
    tags = _optional_str_list(fixture, "tags") or []
    raw_meta = fixture.get("meta")
    meta_in: Mapping[str, Any] = raw_meta if isinstance(raw_meta, Mapping) else {}
    corpus_source = meta_in.get("corpus_source") or fixture.get("corpus_source")
    if corpus_source == "204_archive":
        if regime not in {"A", "B", "unknown"}:
            raise CorpusEncodeError("204_archive fixtures require regime in {A,B,unknown}")
        if failure_ids is None:
            raise CorpusEncodeError("204_archive fixtures require failure_ids (may be empty only if explicit [])")
        # empty list is allowed only if key present; require key via above
        if "session-12-seed" in tags and regime not in {"A", "B"}:
            raise CorpusEncodeError("session-12-seed fixtures require regime A or B")

    # Optional topology / evidence / split / replay fail-closed probes (S1 seed negatives).
    if isinstance(meta_in, Mapping):
        _validate_topology_and_evidence(meta_in)

    try:
        gti = project_generation_task_input(fixture.get("generation_task_input"), strict=True)
    except TaskInputError as exc:
        raise CorpusEncodeError(str(exc)) from exc

    # Also fail if expected fields were smuggled under generation_task_input before projection
    raw_gti = fixture.get("generation_task_input")
    if isinstance(raw_gti, Mapping):
        for k in raw_gti:
            if isinstance(k, str) and (k.startswith("expected") or k.startswith("gold")):
                # project_generation_task_input already rejects; belt-and-suspenders message
                raise CorpusEncodeError(f"generation_task_input must not contain expected/gold fields (found {k!r})")

    unbound_reason = _optional_str(fixture, "unbound_reason")
    if bound is False and not unbound_reason:
        unbound_reason = "offline_fixture_seed"

    pack_pin = schema_pack_pin()
    catalog_pin = metric_catalog_pin()

    bundle: dict[str, Any] = {
        "schema_version": "ape_bundle_v1",
        "case_id": resolved_case_id,
        "artifact_class": artifact_class,
        "bound": bound,
        "schema_pack": pack_pin,
        "metric_catalog": catalog_pin,
        "provenance_label": provenance_label,
        "redaction_profile": redaction_profile,
    }
    if unbound_reason is not None:
        bundle["unbound_reason"] = unbound_reason
    if final_message is not None:
        bundle["final_message"] = final_message
        bundle["final_message_sha256"] = message_sha256(final_message)
    if expected_final_message is not None:
        bundle["expected_final_message"] = expected_final_message
    if expected_gold_codes is not None:
        bundle["expected_gold_codes"] = expected_gold_codes
    if failure_ids is not None:
        bundle["failure_ids"] = failure_ids
    if prevention_ids is not None:
        bundle["prevention_ids"] = prevention_ids
    if regime is not None:
        bundle["regime"] = regime
    if instance_kind is not None:
        bundle["instance_kind"] = instance_kind
    if path_class_gate is not None:
        bundle["path_class_gate"] = path_class_gate
    if gti is not None:
        bundle["generation_task_input"] = gti

    # Fixture-level session_thread_id (S2c / N14). Schema allows the root field;
    # copy only non-empty strings. Does not alter schema pins.
    session_thread_id = _optional_str(fixture, "session_thread_id")
    if session_thread_id is not None:
        # Normalize at encode boundary so bundle identity matches scoring resolve.
        bundle["session_thread_id"] = session_thread_id.strip()

    session_tags = tags
    meta_extra: dict[str, Any] = {
        "suite_id": suite_id,
        "tags": session_tags,
        "corpus_source": corpus_source,
        "session_tags": [t for t in session_tags if t == "session-12-seed"],
    }
    # drop Nones from meta_extra
    meta_extra = {k: v for k, v in meta_extra.items() if v not in (None, [], "")}
    bundle["meta"] = _meta_with_producer(
        fixture.get("meta") if isinstance(fixture.get("meta"), Mapping) else None,
        extra=meta_extra,
    )

    bundle_hash = content_sha256(bundle)
    bundle_ref = f"bundle:{resolved_case_id}@{bundle_hash}"

    case_row: dict[str, Any] = {
        "schema_version": "eval_case_v1",
        "id": f"case:{resolved_case_id}",
        "case_id": resolved_case_id,
        "artifact_class": artifact_class,
        "bundle_ref": bundle_ref,
        "schema_pack": pack_pin,
        "metric_catalog": catalog_pin,
        "tags": session_tags,
        "meta": {
            "producer": PRODUCER_ID,
            "bundle_hash": bundle_hash,
            "suite_id": suite_id,
            "regime": regime,
            "corpus_source": corpus_source,
        },
    }
    # prune empty
    if not case_row["tags"]:
        del case_row["tags"]
    case_row["meta"] = {k: v for k, v in case_row["meta"].items() if v is not None}

    if validate:
        try:
            validate_instance("ape_bundle_v1", bundle)
            validate_instance("eval_case_v1", case_row)
        except SchemaPackError as exc:
            raise CorpusEncodeError(str(exc)) from exc

    from git_cg.eval.corpus.canonical import canonical_json_text

    return {
        "bundle": bundle,
        "case": case_row,
        "bundle_ref": bundle_ref,
        "bundle_hash": bundle_hash,
        "case_hash": content_sha256(case_row),
        "canonical_bundle": canonical_json_text(bundle),
        "canonical_case": canonical_json_text(case_row),
    }
