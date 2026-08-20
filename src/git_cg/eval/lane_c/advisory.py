"""Lane C-prime advisory score emission (C-ADV / D30).

C' numeric GEval rows must never use ``make_score(..., passed=None)``: that
helper derives ``passed=True`` for higher-is-better values ≥ 1 (F01). This
module constructs ``ScoreResultV1`` directly and forces ``passed=None``.

Success ``reason`` is the closed execution code ``scored``. Free-text
rationale lives only in ``evidence["rationale"]`` (scrubbed, ≤800 chars).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Final

from git_cg.eval.enums import Authority, Family, Polarity, Severity, Source
from git_cg.eval.evidence_scrub import scrub_evidence_mapping
from git_cg.eval.lane_c.taxonomy import EXEC_SCORED, assert_execution_code, failure_id_for, validate_closed_reason
from git_cg.eval.score_result import ScoreResultV1
from git_cg.eval.scoring.context import live_pin_refs
from git_cg.eval.scoring.result_builder import metric_row

__all__ = [
    "GEVAL_SCALE",
    "MAX_RATIONALE_CHARS",
    "make_advisory_score",
    "make_advisory_skip",
    "scrub_evidence_mapping",
    "scrub_rationale",
]

GEVAL_SCALE: Final = "geval_1_5"
MAX_RATIONALE_CHARS: Final = 800
_GEVAL_MIN: Final = 1.0
_GEVAL_MAX: Final = 5.0

# C0/C1 controls and DEL - rationale must not carry injection / log-breakers (F26).
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_WS_RE = re.compile(r" {2,}")


def scrub_rationale(text: str | None) -> str | None:
    """
    Sanitise rationale text for storage.
    
    Returns:
    	str | None: The cleaned rationale, capped at the maximum length, or `None` when the text is empty.
    """
    if text is None:
        return None
    cleaned = _CONTROL_RE.sub(" ", str(text))
    cleaned = _WS_RE.sub(" ", cleaned).strip()
    if not cleaned:
        return None
    if len(cleaned) > MAX_RATIONALE_CHARS:
        cleaned = cleaned[:MAX_RATIONALE_CHARS]
    return cleaned


def _catalog_row(metric_id: str) -> dict[str, Any]:
    """Retrieve a metric catalog entry by identifier.
    
    Parameters:
    	metric_id (str): Identifier of the metric to retrieve.
    
    Returns:
    	dict[str, Any]: The matching metric catalog entry.
    
    Raises:
    	KeyError: If the metric identifier is not present in the catalog.
    """
    row = metric_row(metric_id)
    if row is None:
        raise KeyError(f"unknown metric_id not in catalog: {metric_id}")
    return row


def _build_row(
    metric_id: str,
    value: int | float,
    *,
    reason: str,
    evidence: dict[str, Any],
    failure_ids: list[str] | None,
    pin_refs: list[str] | None,
    duration_ms: int | float | None,
    product_authority: str | None,
    name: str | None,
) -> ScoreResultV1:
    """
    Construct a catalog-aligned score result with the supplied value, execution metadata, evidence, and references.
    
    Parameters:
        metric_id (str): Identifier of the metric in the catalogue.
        value (int | float): Score value to include in the result.
        reason (str): Execution reason associated with the result.
        evidence (dict[str, Any]): Evidence associated with the score.
        failure_ids (list[str] | None): Failure identifiers associated with the result.
        pin_refs (list[str] | None): Pin references to attach to the result.
        duration_ms (int | float | None): Execution duration in milliseconds.
        product_authority (str | None): Product authority associated with the result.
        name (str | None): Optional display name overriding the catalogue name.
    
    Returns:
        ScoreResultV1: A score result populated with catalogue metadata and nullable pass status.
    """
    row = _catalog_row(metric_id)
    polarity = Polarity(row["polarity"])
    authority = Authority(row["authority"])
    source = Source(row.get("source_default") or "lane_c_judge")
    family = Family(row["family"]) if row.get("family") else None
    sev_raw = row.get("severity")
    severity = Severity(sev_raw) if sev_raw is not None else None
    return ScoreResultV1(
        metric_id=metric_id,
        polarity=polarity,
        authority=authority,
        source=source,
        value=value,
        name=name if name is not None else row.get("name"),
        family=family,
        threshold=None,
        passed=None,
        severity=severity,
        reason=reason,
        evidence=evidence,
        failure_ids=failure_ids,
        product_authority=product_authority,
        pin_refs=list(pin_refs) if pin_refs is not None else live_pin_refs(),
        duration_ms=duration_ms,
    )


def _coerce_geval_value(value: object) -> int | float:
    """
    Validate and normalise a GEval score within the range 1 to 5.
    
    Parameters:
    	value (object): The score to validate.
    
    Returns:
    	int | float: The score, with whole-number values represented as integers.
    
    Raises:
    	ValueError: If the value is boolean, not numeric, or outside the range 1 to 5.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"GEval score must be a number in 1..5, got {type(value).__name__}")
    numeric = float(value)
    if numeric < _GEVAL_MIN or numeric > _GEVAL_MAX:
        raise ValueError(f"GEval score must be in 1..5, got {value!r}")
    if numeric.is_integer():
        return int(numeric)
    return numeric


def make_advisory_score(
    metric_id: str,
    value: int | float,
    *,
    reason: str = EXEC_SCORED,
    evidence: Mapping[str, Any] | None = None,
    failure_ids: list[str] | None = None,
    pin_refs: list[str] | None = None,
    duration_ms: int | float | None = None,
    rationale: str | None = None,
    product_authority: str | None = None,
    name: str | None = None,
) -> ScoreResultV1:
    """
    Create a catalog-aligned advisory GEval score row.
    
    Parameters:
        metric_id (str): Catalog identifier for the metric.
        value (int | float): GEval score from 1 to 5.
        reason (str): Execution code, which must be ``scored``.
        rationale (str | None): Optional rationale stored in sanitised evidence.
    
    Returns:
        ScoreResultV1: Advisory score row with ``passed`` set to ``None``.
    
    Raises:
        ValueError: If the execution code or score is invalid.
        KeyError: If ``metric_id`` is not in the metric catalogue.
    """
    code = validate_closed_reason(reason, allow_scored=True)
    if code != EXEC_SCORED:
        raise ValueError(f"make_advisory_score requires reason={EXEC_SCORED!r}, got {reason!r}")
    score = _coerce_geval_value(value)

    payload: dict[str, Any] = scrub_evidence_mapping(dict(evidence) if evidence else {})
    if not isinstance(payload, dict):
        payload = {}
    payload["scale"] = GEVAL_SCALE
    payload["skipped"] = False
    payload["execution_code"] = EXEC_SCORED

    text = rationale if rationale is not None else payload.get("rationale")
    scrubbed = scrub_rationale(text if text is None or isinstance(text, str) else str(text))
    if scrubbed is not None:
        payload["rationale"] = scrubbed
    else:
        payload.pop("rationale", None)

    return _build_row(
        metric_id,
        score,
        reason=EXEC_SCORED,
        evidence=payload,
        failure_ids=failure_ids,
        pin_refs=pin_refs,
        duration_ms=duration_ms,
        product_authority=product_authority,
        name=name,
    )


def make_advisory_skip(
    metric_id: str,
    *,
    reason: str,
    evidence: Mapping[str, Any] | None = None,
    failure_ids: list[str] | None = None,
    pin_refs: list[str] | None = None,
    duration_ms: int | float | None = None,
    product_authority: str | None = None,
    name: str | None = None,
) -> ScoreResultV1:
    """
    Emit a skipped advisory score without a fabricated quality score.
    
    Parameters:
    	metric_id (str): Identifier of the catalog metric.
    	reason (str): Closed execution code describing why scoring was skipped.
    	evidence (Mapping[str, Any] | None): Additional evidence to include.
    	failure_ids (list[str] | None): Failure identifiers associated with the skip.
    	pin_refs (list[str] | None): Pin references associated with the result.
    	duration_ms (int | float | None): Execution duration in milliseconds.
    	product_authority (str | None): Product authority metadata.
    	name (str | None): Optional display name for the metric.
    
    Returns:
    	ScoreResultV1: A skipped result with value 0.0 and nullable `passed`.
    
    Raises:
    	ValueError: If `reason` is `scored`.
    """
    code = assert_execution_code(reason)
    if code == EXEC_SCORED:
        raise ValueError("make_advisory_skip cannot emit reason='scored'")
    payload: dict[str, Any] = scrub_evidence_mapping(dict(evidence) if evidence else {})
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("skipped", True)
    payload["execution_code"] = code
    # Never stamp a quality scale on a skip - 0.0 is not a GEval mark.
    payload.pop("scale", None)
    payload.pop("rationale", None)

    fid = failure_ids
    if fid is None:
        mapped = failure_id_for(code)
        fid = [mapped] if mapped else None

    return _build_row(
        metric_id,
        0.0,
        reason=code,
        evidence=payload,
        failure_ids=fid,
        pin_refs=pin_refs,
        duration_ms=duration_ms,
        product_authority=product_authority,
        name=name,
    )
