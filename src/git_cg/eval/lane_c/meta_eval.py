"""Lane C' R2 lab meta-eval (C-R2 / judge_meta_eval_v1).

Offline Equals / FP / FN calibration against **labeled** lab envelopes only.
Expected labels never enter ordinary :func:`project_judge_input` payloads.
All emitted rows are ``authority=lab`` / non-gating and cannot sole-pass
product Hybrid, golden promotion, or first-CI gates.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

from git_cg.eval.enums import Authority, Family, Polarity, Severity, Source
from git_cg.eval.evidence_scrub import scrub_evidence_mapping
from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin
from git_cg.eval.schema_pack import SchemaPackError, validate_instance
from git_cg.eval.score_result import ScoreResultV1
from git_cg.eval.scoring.context import live_pin_refs
from git_cg.eval.scoring.result_builder import metric_row

__all__ = [
    "ERROR_TYPES",
    "MetaEvalError",
    "MetaEvalItem",
    "MetaEvalResult",
    "assert_labels_absent_from_ordinary_payload",
    "build_judge_meta_eval",
    "classify_equals_error",
    "emit_meta_eval_scores",
    "run_judge_meta_eval",
    "summarize_meta_eval",
]

ERROR_TYPES: Final[frozenset[str]] = frozenset({"FP", "FN", "OK", "judge_error"})
_SCHEMA: Final = "judge_meta_eval_v1"
_LAB_EVIDENCE_BASE: Final[dict[str, Any]] = {
    "authority": "lab",
    "diagnostic_only": True,
    "non_gating": True,
    "product_authority": None,
    "lab_protocol": "judge_meta_eval_v1",
    "network_policy": "offline_preferred",
}


class MetaEvalError(ValueError):
    """Invalid meta-eval envelope, item, or label protocol."""


@dataclass(frozen=True, slots=True)
class MetaEvalItem:
    """One labeled lab item (Equals path only)."""

    item_id: str
    expected_label: str
    judge_output_label: str | None = None
    judge_output_score: int | float | None = None
    judge_input_ref: str | Mapping[str, Any] | None = None
    judge_error: bool = False

    def scrubbed_input_ref(self) -> str | dict[str, Any] | None:
        """Return a secret-scrubbed judge input reference (never raw secrets)."""
        if self.judge_input_ref is None:
            return None
        if isinstance(self.judge_input_ref, str):
            text = self.judge_input_ref.strip()
            return text or None
        if isinstance(self.judge_input_ref, Mapping):
            scrubbed = scrub_evidence_mapping(dict(self.judge_input_ref))
            return scrubbed if isinstance(scrubbed, dict) else None
        raise MetaEvalError("judge_input_ref must be a string or mapping")


@dataclass(frozen=True, slots=True)
class MetaEvalResult:
    """Validated envelope + lab score rows."""

    envelope: dict[str, Any]
    rows: list[ScoreResultV1]
    fp_rate: float
    fn_rate: float
    n: int
    equals_count: int


def classify_equals_error(
    *,
    expected_label: str,
    judge_output_label: str | None,
    judge_error: bool = False,
) -> tuple[bool | None, Literal["FP", "FN", "OK", "judge_error"]]:
    """Classify one Equals outcome.

    Positive label convention: truthy expected labels are the members of
    ``_POSITIVE`` (case-insensitive), currently ``{"1", "true", "yes", "y",
    "pos", "positive", "pass", "toxic", "harmful", "fail", "violation",
    "flagged"}``.
    All other non-empty labels are treated as negative. This is lab-only
    calibration vocabulary — not product Hybrid law.
    """
    if judge_error or judge_output_label is None or not str(judge_output_label).strip():
        return None, "judge_error"
    exp = _normalize_label(expected_label)
    got = _normalize_label(judge_output_label)
    equals = exp == got
    if equals:
        return True, "OK"
    exp_pos = _is_positive_label(exp)
    got_pos = _is_positive_label(got)
    if got_pos and not exp_pos:
        return False, "FP"
    if (not got_pos) and exp_pos:
        return False, "FN"
    # Both negative-but-different, or both positive-but-different strings.
    # Count as FN when expected was positive else FP (predicted wrong positive class).
    if exp_pos:
        return False, "FN"
    return False, "FP"


def _normalize_label(label: str) -> str:
    return " ".join(str(label).strip().lower().split())


_POSITIVE: Final[frozenset[str]] = frozenset(
    {
        "1",
        "true",
        "yes",
        "y",
        "pos",
        "positive",
        "pass",
        "toxic",
        "harmful",
        "fail",
        "violation",
        "flagged",
    }
)


def _is_positive_label(normalized: str) -> bool:
    return normalized in _POSITIVE


def _pin_or_default(pin_ref: str | None) -> str:
    if pin_ref is None or not str(pin_ref).strip():
        # Stable lab pin identity over schema pack (content-addressed).
        base = schema_pack_pin()
        _name, sep, digest = base.partition("@")
        if not sep or len(digest) != 64:
            raise MetaEvalError(f"cannot derive judge_meta pin from schema pack pin {base!r}")
        return f"judge_meta_v1@{digest}"
    pin = str(pin_ref).strip()
    # Accept full pin_ref form; otherwise fail closed.
    if "@" not in pin or len(pin.split("@", 1)[1]) != 64:
        raise MetaEvalError(f"pin_ref/judge_pin must look like name_vN@<sha256> (got {pin!r})")
    return pin


def build_judge_meta_eval(
    *,
    eval_id: str,
    judge_id: str,
    items: Sequence[MetaEvalItem | Mapping[str, Any]],
    cohort_id: str | None = None,
    pin_ref: str | None = None,
    judge_pin: str | None = None,
    polarity: str = "pass_fail",
    notes: str | None = None,
    meta: Mapping[str, Any] | None = None,
    validate: bool = True,
) -> dict[str, Any]:
    """Build a ``judge_meta_eval_v1`` envelope (lab-only, offline-preferred)."""
    if not isinstance(eval_id, str) or not eval_id.strip():
        raise MetaEvalError("id must be a non-empty string")
    if not isinstance(judge_id, str) or not judge_id.strip():
        raise MetaEvalError("judge_id must be a non-empty string")
    if polarity not in {"higher_is_better", "lower_is_better", "pass_fail"}:
        raise MetaEvalError(f"unsupported polarity: {polarity!r}")

    pin = _pin_or_default(judge_pin if judge_pin is not None else pin_ref)
    built_items: list[dict[str, Any]] = []
    for raw in items:
        item = _coerce_item(raw)
        equals, error_type = classify_equals_error(
            expected_label=item.expected_label,
            judge_output_label=item.judge_output_label,
            judge_error=item.judge_error,
        )
        entry: dict[str, Any] = {
            "item_id": item.item_id,
            "expected_label": item.expected_label,
            "equals": equals,
            "error_type": error_type,
        }
        ref = item.scrubbed_input_ref()
        if ref is not None:
            entry["judge_input_ref"] = ref
        if item.judge_output_label is not None:
            entry["judge_output_label"] = item.judge_output_label
        if item.judge_output_score is not None:
            entry["judge_output_score"] = item.judge_output_score
        built_items.append(entry)

    aggregates = summarize_meta_eval(built_items)
    envelope: dict[str, Any] = {
        "schema_version": _SCHEMA,
        "id": eval_id.strip(),
        "judge_id": judge_id.strip(),
        "pin_ref": pin,
        "polarity": polarity,
        "authority": "lab",
        "cohort_id": (cohort_id or eval_id).strip(),
        "items": built_items,
        "aggregates": aggregates,
        "network_policy": "offline_preferred",
        "schema_pack": schema_pack_pin(),
        "metric_catalog": metric_catalog_pin(),
    }
    if notes is not None:
        envelope["notes"] = str(notes)
    if meta is not None:
        envelope["meta"] = scrub_evidence_mapping(dict(meta))

    if validate:
        try:
            validate_instance(_SCHEMA, envelope)
        except SchemaPackError as exc:
            raise MetaEvalError(str(exc)) from exc
    return envelope


def summarize_meta_eval(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Compute ``{fp_rate, fn_rate, n, equals_count, judge_error_count}``.

    Items with ``equals is False`` but no ``error_type`` are counted as
    ``unclassified`` rather than biased into FN, so externally built envelopes
    cannot silently skew fp/fn rates.
    """
    n = 0
    fp = 0
    fn = 0
    ok = 0
    errors = 0
    unclassified = 0
    for item in items:
        et = str(item.get("error_type") or "")
        if et == "judge_error":
            errors += 1
            continue
        n += 1
        if et == "FP":
            fp += 1
        elif et == "FN":
            fn += 1
        elif et == "OK" or item.get("equals") is True:
            ok += 1
        elif item.get("equals") is False:
            # Ambiguous without error_type — do not bias FN vs FP.
            unclassified += 1
        else:
            unclassified += 1
    classified = fp + fn + ok
    # Rates use classified denominator so unclassified rows stay honest.
    denom = classified if classified else 0
    fp_rate = (fp / denom) if denom else 0.0
    fn_rate = (fn / denom) if denom else 0.0
    return {
        "fp_rate": fp_rate,
        "fn_rate": fn_rate,
        "n": n,
        "equals_count": ok,
        "judge_error_count": errors,
        "fp_count": fp,
        "fn_count": fn,
        "unclassified_count": unclassified,
    }


def _coerce_item(raw: MetaEvalItem | Mapping[str, Any]) -> MetaEvalItem:
    if isinstance(raw, MetaEvalItem):
        if not raw.item_id.strip():
            raise MetaEvalError("item_id must be non-empty")
        if not str(raw.expected_label).strip():
            raise MetaEvalError("expected_label must be non-empty")
        return raw
    if not isinstance(raw, Mapping):
        raise MetaEvalError("meta-eval item must be MetaEvalItem or mapping")
    item_id = str(raw.get("item_id") or "").strip()
    expected = raw.get("expected_label")
    if not item_id:
        raise MetaEvalError("item_id must be non-empty")
    if expected is None or not str(expected).strip():
        raise MetaEvalError("expected_label must be non-empty")
    score = raw.get("judge_output_score", raw.get("score"))
    if isinstance(score, bool) or (score is not None and not isinstance(score, (int, float))):
        raise MetaEvalError("judge_output_score must be numeric when set")
    return MetaEvalItem(
        item_id=item_id,
        expected_label=str(expected),
        judge_output_label=(None if raw.get("judge_output_label") is None else str(raw.get("judge_output_label"))),
        judge_output_score=None if score is None else float(score),
        judge_input_ref=raw.get("judge_input_ref"),
        judge_error=bool(raw.get("judge_error") or raw.get("error_type") == "judge_error"),
    )


def _lab_row(
    metric_id: str,
    value: bool | int | float,
    *,
    reason: str,
    evidence: Mapping[str, Any],
    pin_refs: list[str] | None = None,
) -> ScoreResultV1:
    """Catalog-aligned lab row with ``passed is None`` (never gate-derived)."""
    row = metric_row(metric_id)
    if row is None:
        raise KeyError(f"unknown metric_id not in catalog: {metric_id}")
    polarity = Polarity(row["polarity"])
    if polarity is Polarity.PASS_FAIL and type(value) is not bool:
        raise MetaEvalError(f"{metric_id} requires boolean value")
    if polarity is not Polarity.PASS_FAIL and isinstance(value, bool):
        raise MetaEvalError(f"{metric_id} rejects boolean value")
    payload = scrub_evidence_mapping({**_LAB_EVIDENCE_BASE, **dict(evidence)})
    if not isinstance(payload, dict):
        payload = dict(_LAB_EVIDENCE_BASE)
    sev_raw = row.get("severity")
    return ScoreResultV1(
        metric_id=metric_id,
        polarity=polarity,
        authority=Authority(row["authority"]),
        source=Source(row.get("source_default") or "lab_meta"),
        value=value,
        name=row.get("name"),
        family=Family(row["family"]) if row.get("family") else None,
        threshold=None,
        passed=None,
        severity=Severity(sev_raw) if sev_raw is not None else None,
        reason=reason,
        evidence=payload,
        failure_ids=None,
        product_authority=None,
        pin_refs=list(pin_refs) if pin_refs is not None else live_pin_refs(),
    )


def emit_meta_eval_scores(
    envelope: Mapping[str, Any],
    *,
    pin_refs: list[str] | None = None,
) -> list[ScoreResultV1]:
    """Emit lab Equals + FP/FN aggregate rows from a validated envelope."""
    if str(envelope.get("schema_version") or "") != _SCHEMA:
        raise MetaEvalError("envelope schema_version must be judge_meta_eval_v1")
    if str(envelope.get("authority") or "lab") != "lab":
        raise MetaEvalError("meta-eval authority must be lab")
    items = envelope.get("items")
    if not isinstance(items, list):
        raise MetaEvalError("envelope.items must be a list")
    aggregates = envelope.get("aggregates")
    if not isinstance(aggregates, Mapping):
        aggregates = summarize_meta_eval(items)

    base = {
        "cohort_id": envelope.get("cohort_id"),
        "judge_id": envelope.get("judge_id"),
        "eval_id": envelope.get("id"),
        "network_policy": envelope.get("network_policy") or "offline_preferred",
        "aggregates": dict(aggregates),
    }
    refs = list(pin_refs) if pin_refs is not None else live_pin_refs()
    pin = envelope.get("pin_ref")
    if isinstance(pin, str) and pin not in refs:
        refs.append(pin)

    rows: list[ScoreResultV1] = []
    # Per-item equals as a cohort rollup boolean: true only when all comparable OK.
    n = int(aggregates.get("n") or 0)
    equals_all = n > 0 and int(aggregates.get("equals_count") or 0) == n
    rows.append(
        _lab_row(
            "lab.judge_equals_label",
            bool(equals_all),
            reason="meta_eval_equals",
            evidence={**base, "rollup": "all_comparable_items_equal"},
            pin_refs=refs,
        )
    )
    rows.append(
        _lab_row(
            "lab.judge_fp_rate",
            float(aggregates.get("fp_rate") or 0.0),
            reason="meta_eval_fp_rate",
            evidence=base,
            pin_refs=refs,
        )
    )
    rows.append(
        _lab_row(
            "lab.judge_fn_rate",
            float(aggregates.get("fn_rate") or 0.0),
            reason="meta_eval_fn_rate",
            evidence=base,
            pin_refs=refs,
        )
    )
    return rows


def run_judge_meta_eval(
    *,
    eval_id: str,
    judge_id: str,
    items: Sequence[MetaEvalItem | Mapping[str, Any]],
    cohort_id: str | None = None,
    pin_ref: str | None = None,
    judge_pin: str | None = None,
    notes: str | None = None,
    meta: Mapping[str, Any] | None = None,
) -> MetaEvalResult:
    """Build, validate, and score one offline meta-eval cohort."""
    envelope = build_judge_meta_eval(
        eval_id=eval_id,
        judge_id=judge_id,
        items=items,
        cohort_id=cohort_id,
        pin_ref=pin_ref,
        judge_pin=judge_pin,
        notes=notes,
        meta=meta,
        validate=True,
    )
    rows = emit_meta_eval_scores(envelope)
    aggregates = envelope["aggregates"]
    return MetaEvalResult(
        envelope=envelope,
        rows=rows,
        fp_rate=float(aggregates["fp_rate"]),
        fn_rate=float(aggregates["fn_rate"]),
        n=int(aggregates["n"]),
        equals_count=int(aggregates.get("equals_count") or 0),
    )


def assert_labels_absent_from_ordinary_payload(payload: Mapping[str, Any]) -> None:
    """Fail closed if a mapping looks like an ordinary judge payload carrying labels."""
    from git_cg.eval.lane_c.judge_input import _normalize_key_name

    forbidden = {
        "expected_label",
        "expected_labels",
        "gold_label",
        "gold_labels",
        "judge_labels",
        "expected_gold",
    }
    found = sorted(
        k
        for k in payload
        if _normalize_key_name(str(k)) in forbidden or _normalize_key_name(str(k)).startswith("expected")
    )
    # Allow only inside explicit meta-eval builders — callers use this on JudgeInput.as_dict().
    if found:
        raise MetaEvalError("ordinary judge payload must not carry meta-eval labels: " + ", ".join(found))


# Re-export helper name used by tests without expanding public surface accidentally.
def iter_error_types(items: Iterable[Mapping[str, Any]]) -> list[str]:
    """Return error_type values in item order."""
    return [str(i.get("error_type") or "") for i in items]
