"""Phase 7 semantic context: summary model, risk assessment, and Opik-tracked builder.

Assembles a bounded ``SemanticDiffSummary`` from Phase 1-3 producer outputs and
graph product queries. Ranking/SemVer authority remains the SOP matrix; this
module must not import CRG directly (use ``graph_context`` adapters from main).
"""

from __future__ import annotations

from typing import Any, Literal

import opik
from pydantic import BaseModel, Field

from git_cg.intent import GraphEnrichmentFacts, GraphFactOutcome
from git_cg.telemetry import redact_payload

SEMANTIC_DIFF_SUMMARY_SCHEMA_VERSION = "semantic_diff_summary_v1"

# Bounds (Issue #162 locked defaults)
MAX_FALLBACK_REASONS = 32
MAX_REASON_STRING_LENGTH = 240
MAX_NOTABLE_CALLERS = 16
MAX_FINGERPRINT_CLASS_KEYS = 32
MAX_RISK_PRIORITIES = 16
COMMIT_PATH_GRAPH_MAX_DEPTH = 2
COMMIT_PATH_GRAPH_DETAIL_LEVEL = "minimal"

GraphOutcomeLiteral = Literal["ok", "unavailable", "error"]


def _bound_str(value: str, *, max_len: int = MAX_REASON_STRING_LENGTH) -> str:
    text = str(value)
    if len(text) <= max_len:
        return text
    return text[: max(0, max_len - 3)] + "..."


def _bound_str_list(
    values: list[str] | None,
    *,
    max_items: int,
    max_len: int = MAX_REASON_STRING_LENGTH,
) -> list[str]:
    if not values:
        return []
    out: list[str] = []
    for raw in values:
        if not isinstance(raw, str):
            continue
        out.append(_bound_str(raw, max_len=max_len))
        if len(out) >= max_items:
            break
    return out


def _redact_reason_list(values: list[str] | None) -> list[str]:
    redacted: list[str] = []
    for reason in _bound_str_list(values, max_items=MAX_FALLBACK_REASONS):
        cleaned = redact_payload(reason)
        if cleaned == "[REDACTION FAILED - PAYLOAD OMITTED FOR SAFETY]":
            redacted.append("[REDACTED]")
        else:
            redacted.append(_bound_str(cleaned))
    return redacted


class RiskAssessment(BaseModel):
    """Bounded risk projection from detect_changes (non-content labels only)."""

    risk_score: float | None = None
    outcome: GraphOutcomeLiteral = "unavailable"
    priorities: list[str] = Field(default_factory=list)

    def bounded(self) -> RiskAssessment:
        """Return a copy with priority list/string caps applied."""
        return RiskAssessment(
            risk_score=self.risk_score,
            outcome=self.outcome,
            priorities=_bound_str_list(self.priorities, max_items=MAX_RISK_PRIORITIES),
        )


class SemanticDiffSummary(BaseModel):
    """Versioned, bounded projection of parser + fingerprint + graph product facts."""

    schema_version: str = SEMANTIC_DIFF_SUMMARY_SCHEMA_VERSION
    parser_coverage_ratio: float | None = None
    parser_fallback_reasons: list[str] = Field(default_factory=list)
    body_similarity_min: float | None = None
    body_similarity_avg: float | None = None
    fingerprint_class_counts: dict[str, int] | None = None
    blast_radius_size: int | None = None
    affected_flows_count: int | None = None
    test_coverage_gap: bool | None = None
    test_gaps_count: int | None = None
    risk_score: float | None = None
    impacts_tests: bool | None = None
    impacts_production_code: bool | None = None
    impacts_hub_node: bool | None = None
    complex_function_changed: bool | None = None
    notable_callers: list[str] = Field(default_factory=list)
    fallback_reasons: list[str] = Field(default_factory=list)

    def bounded(self) -> SemanticDiffSummary:
        """Return a copy with list/dict caps applied."""
        counts = self.fingerprint_class_counts
        if isinstance(counts, dict) and len(counts) > MAX_FINGERPRINT_CLASS_KEYS:
            # Keep stable key order for determinism.
            items = sorted(counts.items(), key=lambda kv: kv[0])[:MAX_FINGERPRINT_CLASS_KEYS]
            counts = dict(items)
        return SemanticDiffSummary(
            schema_version=self.schema_version or SEMANTIC_DIFF_SUMMARY_SCHEMA_VERSION,
            parser_coverage_ratio=self.parser_coverage_ratio,
            parser_fallback_reasons=_bound_str_list(self.parser_fallback_reasons, max_items=MAX_FALLBACK_REASONS),
            body_similarity_min=self.body_similarity_min,
            body_similarity_avg=self.body_similarity_avg,
            fingerprint_class_counts=counts,
            blast_radius_size=self.blast_radius_size,
            affected_flows_count=self.affected_flows_count,
            test_coverage_gap=self.test_coverage_gap,
            test_gaps_count=self.test_gaps_count,
            risk_score=self.risk_score,
            impacts_tests=self.impacts_tests,
            impacts_production_code=self.impacts_production_code,
            impacts_hub_node=self.impacts_hub_node,
            complex_function_changed=self.complex_function_changed,
            notable_callers=_bound_str_list(self.notable_callers, max_items=MAX_NOTABLE_CALLERS),
            fallback_reasons=_bound_str_list(self.fallback_reasons, max_items=MAX_FALLBACK_REASONS),
        )


def empty_graph_product_fields() -> dict[str, Any]:
    """Zero-safe Phase 7 graph product fields for flag-off / failure defaults."""
    return {
        "blast_radius_size": None,
        "affected_flows_count": None,
        "test_coverage_gap": None,
        "test_gaps_count": None,
        "risk_assessment": None,
        "graph_enrichment": None,
        "graph_fallback_reasons": [],
        "impacts_tests": None,
        "impacts_production_code": None,
        # Optional Phase 7 nice-to-haves: populated only when already present in
        # detect/impact payloads (no extra graph queries).
        "impacts_hub_node": None,
        "complex_function_changed": None,
        "notable_callers": [],
    }


def _outcome_from_graph_result(result: Any) -> GraphOutcomeLiteral:
    if result is None:
        return "unavailable"
    ok = bool(getattr(result, "ok", False))
    raw = getattr(result, "outcome", None)
    value = str(getattr(raw, "value", raw) or "").lower()
    if ok and value in {"ok", ""}:
        return "ok"
    if value == "error":
        return "error"
    if value == "unavailable":
        return "unavailable"
    return "error" if not ok and value == "error" else ("ok" if ok else "unavailable")


def _count_from_payload(data: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        if key not in data:
            continue
        value = data.get(key)
        if value is None:
            continue
        if isinstance(value, bool):
            continue
        if isinstance(value, int | float):
            return int(value)
        if isinstance(value, list | tuple | set):
            return len(value)
        if isinstance(value, dict):
            # Common CRG shapes: {"total": N} or nested lists under known keys.
            for nested_key in ("total", "count", "size", "total_impacted"):
                nested = value.get(nested_key)
                if isinstance(nested, int | float):
                    return int(nested)
            for nested_key in ("items", "flows", "nodes", "results", "impacted"):
                nested = value.get(nested_key)
                if isinstance(nested, list | tuple | set):
                    return len(nested)
    return None


def _test_gaps_count(data: dict[str, Any]) -> int | None:
    for key in ("test_gaps", "test_coverage_gaps", "knowledge_gaps", "untested_hotspots"):
        if key not in data:
            continue
        value = data.get(key)
        if isinstance(value, list | tuple | set):
            return len(value)
        if isinstance(value, int | float):
            return int(value)
        if isinstance(value, dict):
            nested = value.get("items") or value.get("gaps") or value.get("untested_hotspots")
            if isinstance(nested, list | tuple | set):
                return len(nested)
            count = _count_from_payload(value, "count", "total", "size")
            if count is not None:
                return count
    # detect_changes sometimes nests under summary-like keys
    for container_key in ("gaps", "coverage", "review"):
        container = data.get(container_key)
        if isinstance(container, dict):
            nested = _test_gaps_count(container)
            if nested is not None:
                return nested
    return None


def _risk_score(data: dict[str, Any]) -> float | None:
    for key in ("risk_score", "risk", "score"):
        value = data.get(key)
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, dict):
            for nested_key in ("score", "value", "risk_score"):
                nested = value.get(nested_key)
                if isinstance(nested, int | float):
                    return float(nested)
    summary = data.get("summary")
    if isinstance(summary, dict):
        return _risk_score(summary)
    return None


def _priority_labels(data: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    for key in ("priorities", "priority_items", "review_priorities", "priority_ordered"):
        value = data.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    labels.append(item)
                elif isinstance(item, dict):
                    for label_key in ("name", "title", "id", "path", "kind"):
                        label = item.get(label_key)
                        if isinstance(label, str) and label:
                            labels.append(label)
                            break
        if labels:
            break
    return _bound_str_list(labels, max_items=MAX_RISK_PRIORITIES)


def _impact_flags(data: dict[str, Any]) -> tuple[bool | None, bool | None]:
    """Best-effort production/test impact flags from detect/impact payloads."""
    has_test: bool | None = None
    has_prod: bool | None = None

    def _scan_nodes(nodes: list[Any]) -> None:
        nonlocal has_test, has_prod
        for node in nodes:
            if not isinstance(node, dict):
                continue
            is_test = node.get("is_test")
            kind = str(node.get("kind") or node.get("type") or "").lower()
            name = str(node.get("name") or node.get("qualified_name") or "").lower()
            path = str(node.get("file_path") or node.get("file") or "").lower()
            testish = is_test is True or kind == "test" or "/tests/" in path or name.startswith("test_")
            if testish:
                has_test = True
            else:
                # Only mark production when we saw a concrete non-test node.
                has_prod = True

    for key in ("impacted_nodes", "nodes", "changed_functions", "entities", "key_entities"):
        value = data.get(key)
        if isinstance(value, list):
            _scan_nodes(value)

    if data.get("impacted_has_test_nodes") is not None:
        has_test = bool(data.get("impacted_has_test_nodes"))
    if data.get("impacted_has_production_nodes") is not None:
        has_prod = bool(data.get("impacted_has_production_nodes"))

    return has_test, has_prod


def _truthy_flag(value: Any) -> bool | None:
    """Coerce common payload flag shapes to bool; None when absent/unknown."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float) and not isinstance(value, bool):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "y", "hub", "complex"}:
            return True
        if text in {"0", "false", "no", "n"}:
            return False
    return None


def _harvest_hub_complex_callers(
    *payloads: dict[str, Any],
) -> tuple[bool | None, bool | None, list[str]]:
    """
    Best-effort hub/complex/callers from already-fetched detect/impact dicts.

    Never issues graph queries. Missing keys leave flags None and callers empty.
    """
    hub: bool | None = None
    complex_changed: bool | None = None
    callers: list[str] = []

    def _or_true(current: bool | None, flag: bool | None) -> bool | None:
        if flag is True:
            return True
        if current is True:
            return True
        if flag is False and current is None:
            return False
        return current

    for data in payloads:
        if not isinstance(data, dict) or not data:
            continue

        for key in (
            "impacts_hub_node",
            "impacts_hub",
            "hub_impacted",
            "touches_hub",
            "is_hub",
        ):
            hub = _or_true(hub, _truthy_flag(data.get(key)))

        for key in (
            "complex_function_changed",
            "complex_functions_changed",
            "has_complex_function",
            "complex_change",
        ):
            complex_changed = _or_true(complex_changed, _truthy_flag(data.get(key)))

        # Non-empty large/complex function lists imply complex_function_changed.
        for key in ("large_functions", "complex_functions", "complex_nodes", "oversized_functions"):
            value = data.get(key)
            if (isinstance(value, list | tuple | set) and len(value) > 0) or (
                isinstance(value, int | float) and not isinstance(value, bool) and value > 0
            ):
                complex_changed = True

        # Priority labels often include hub-ish review items from detect_changes.
        for label in _priority_labels(data):
            low = label.lower()
            if "hub" in low:
                hub = True
            if "complex" in low or "large function" in low:
                complex_changed = True

        # Node scans: hub/complex flags on impacted entities.
        for key in ("impacted_nodes", "nodes", "changed_functions", "entities", "key_entities", "hub_nodes"):
            value = data.get(key)
            if not isinstance(value, list):
                continue
            for node in value:
                if not isinstance(node, dict):
                    continue
                if _truthy_flag(node.get("is_hub")) is True or _truthy_flag(node.get("hub")) is True:
                    hub = True
                kind = str(node.get("kind") or node.get("type") or "").lower()
                name = str(node.get("name") or node.get("qualified_name") or "").lower()
                if "hub" in kind or name.endswith("_hub") or ".hub." in name:
                    hub = True
                lines = node.get("lines") or node.get("line_count") or node.get("nloc")
                complexity = node.get("complexity") or node.get("cyclomatic_complexity")
                try:
                    if lines is not None and int(lines) >= 50:
                        complex_changed = True
                    if complexity is not None and float(complexity) >= 10:
                        complex_changed = True
                except TypeError, ValueError:
                    pass

        # Callers already present on the payload (bounded later by summary).
        for key in ("notable_callers", "callers", "top_callers", "caller_names", "notable_caller_names"):
            value = data.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and item.strip():
                        callers.append(item.strip())
                    elif isinstance(item, dict):
                        for label_key in ("name", "qualified_name", "id", "symbol", "caller"):
                            label = item.get(label_key)
                            if isinstance(label, str) and label.strip():
                                callers.append(label.strip())
                                break
            elif isinstance(value, dict):
                for label_key in ("names", "items", "callers"):
                    nested = value.get(label_key)
                    if isinstance(nested, list):
                        for item in nested:
                            if isinstance(item, str) and item.strip():
                                callers.append(item.strip())

    # Dedupe callers preserving order.
    seen: set[str] = set()
    unique_callers: list[str] = []
    for name in callers:
        if name in seen:
            continue
        seen.add(name)
        unique_callers.append(name)
        if len(unique_callers) >= MAX_NOTABLE_CALLERS:
            break

    return hub, complex_changed, unique_callers


def map_graph_product_results(
    *,
    detect_result: Any | None = None,
    impact_result: Any | None = None,
    flows_result: Any | None = None,
) -> dict[str, Any]:
    """
    Collapse graph adapter results into Phase 7 product fields + enrichment facts.

    Parameters:
        detect_result: Optional ``GraphOperationResult`` from ``detect_changes``.
        impact_result: Optional ``GraphOperationResult`` from ``impact_radius``.
        flows_result: Optional ``GraphOperationResult`` from ``affected_flows``.

    Returns:
        dict[str, Any]: Product fields suitable for producer metrics and summary build.
    """
    fields = empty_graph_product_fields()
    fallbacks: list[str] = []

    detect_data = getattr(detect_result, "data", {}) if detect_result is not None else {}
    impact_data = getattr(impact_result, "data", {}) if impact_result is not None else {}
    flows_data = getattr(flows_result, "data", {}) if flows_result is not None else {}
    if not isinstance(detect_data, dict):
        detect_data = {}
    if not isinstance(impact_data, dict):
        impact_data = {}
    if not isinstance(flows_data, dict):
        flows_data = {}

    detect_outcome = _outcome_from_graph_result(detect_result) if detect_result is not None else "unavailable"
    impact_outcome = _outcome_from_graph_result(impact_result) if impact_result is not None else "unavailable"
    flows_outcome = _outcome_from_graph_result(flows_result) if flows_result is not None else "unavailable"

    for label, result, outcome in (
        ("detect_changes", detect_result, detect_outcome),
        ("impact_radius", impact_result, impact_outcome),
        ("affected_flows", flows_result, flows_outcome),
    ):
        if result is None:
            continue
        if outcome != "ok":
            err_type = getattr(result, "error_type", None) or outcome
            fallbacks.append(f"{label}:{err_type}")

    blast = _count_from_payload(impact_data, "total_impacted", "impacted_count", "blast_radius_size", "count")
    if blast is None:
        blast = _count_from_payload(detect_data, "total_impacted", "impacted_count", "blast_radius_size")
    fields["blast_radius_size"] = blast

    flows_count = _count_from_payload(flows_data, "total", "affected_flows_count", "flow_count", "flows")
    if flows_count is None:
        flows_count = _count_from_payload(detect_data, "affected_flows_count", "flows", "affected_flows")
    fields["affected_flows_count"] = flows_count

    gaps = _test_gaps_count(detect_data)
    if gaps is None:
        gaps = _test_gaps_count(impact_data)
    fields["test_gaps_count"] = gaps
    fields["test_coverage_gap"] = (gaps > 0) if gaps is not None else None

    risk_score = _risk_score(detect_data)
    if risk_score is None:
        risk_score = _risk_score(impact_data)
    priorities = _priority_labels(detect_data)
    risk_outcome: GraphOutcomeLiteral = detect_outcome if detect_result is not None else "unavailable"
    if detect_result is None and impact_result is not None:
        risk_outcome = impact_outcome
    fields["risk_assessment"] = RiskAssessment(
        risk_score=risk_score,
        outcome=risk_outcome,
        priorities=priorities,
    ).bounded()

    has_test, has_prod = _impact_flags(detect_data)
    if has_test is None and has_prod is None:
        has_test, has_prod = _impact_flags(impact_data)
    fields["impacts_tests"] = has_test
    fields["impacts_production_code"] = has_prod

    hub, complex_changed, callers = _harvest_hub_complex_callers(detect_data, impact_data)
    fields["impacts_hub_node"] = hub
    fields["complex_function_changed"] = complex_changed
    fields["notable_callers"] = callers

    enrichment_outcome: GraphFactOutcome = "unavailable"
    if impact_outcome == "ok" or detect_outcome == "ok":
        enrichment_outcome = "ok"
    elif impact_outcome == "error" or detect_outcome == "error":
        enrichment_outcome = "error"

    fields["graph_enrichment"] = GraphEnrichmentFacts(
        total_impacted=blast,
        test_gaps_count=gaps,
        impacted_has_test_nodes=has_test,
        impacted_has_production_nodes=has_prod,
        outcome=enrichment_outcome,
    )
    fields["graph_fallback_reasons"] = _bound_str_list(fallbacks, max_items=MAX_FALLBACK_REASONS)
    return fields


def _parser_coverage_ratio(metrics: dict[str, Any] | None) -> float | None:
    if not isinstance(metrics, dict):
        return None
    total = metrics.get("semantic_files_total")
    parsed = metrics.get("semantic_files_parsed")
    try:
        total_i = int(total)
        parsed_i = int(parsed)
    except TypeError, ValueError:
        return None
    if total_i <= 0:
        return 0.0
    return max(0.0, min(1.0, parsed_i / total_i))


def semantic_analysis_metadata(summary: SemanticDiffSummary | None) -> dict[str, Any]:
    """
    Build non-content Opik/span metadata for a semantic summary.

    Parameters:
        summary (SemanticDiffSummary | None): Summary to project.

    Returns:
        dict[str, Any]: Allowlisted Phase 7 metadata fields.
    """
    if summary is None:
        return {
            "blast_radius_size": None,
            "affected_flows_count": None,
            "test_coverage_gap": None,
            "test_gaps_count": None,
            "semantic_context_schema_version": "",
            "semantic_context_fallback_reasons": None,
        }
    bounded = summary.bounded()
    return {
        "blast_radius_size": bounded.blast_radius_size,
        "affected_flows_count": bounded.affected_flows_count,
        "test_coverage_gap": bounded.test_coverage_gap,
        "test_gaps_count": bounded.test_gaps_count,
        "semantic_context_schema_version": bounded.schema_version,
        "semantic_context_fallback_reasons": _redact_reason_list(bounded.fallback_reasons) or None,
    }


@opik.track(
    name="semantic_analysis",
    project_name="gitCommitGenerator",
    ignore_arguments=["producer_metrics", "risk_assessment", "graph_product"],
)
def build_semantic_summary(
    producer_metrics: dict[str, Any] | None = None,
    *,
    risk_assessment: RiskAssessment | None = None,
    graph_product: dict[str, Any] | None = None,
) -> SemanticDiffSummary:
    """
    Build a bounded ``SemanticDiffSummary`` from producer metrics / graph product fields.

    Performs no git/graph/parser I/O. Missing inputs yield a partial summary with
    explicit ``fallback_reasons``. Emits Opik span metadata for Phase 7 fields.

    Parameters:
        producer_metrics (dict[str, Any] | None): Output bundle from semantic producers.
        risk_assessment (RiskAssessment | None): Optional pre-built risk model.
        graph_product (dict[str, Any] | None): Optional graph product field dict.

    Returns:
        SemanticDiffSummary: Bounded summary suitable for ``GenerationContext``.
    """
    metrics = dict(producer_metrics or {})
    product = dict(graph_product or {})
    # Prefer explicit graph_product overrides, else producer bundle fields.
    for key, default in empty_graph_product_fields().items():
        if key not in product:
            product[key] = metrics.get(key, default)

    fallbacks: list[str] = []
    for key in ("graph_fallback_reasons", "semantic_fallback_reasons"):
        raw = metrics.get(key) if key == "semantic_fallback_reasons" else product.get(key)
        if isinstance(raw, list):
            fallbacks.extend(str(item) for item in raw if item is not None)

    parser_metrics = metrics.get("semantic_parser_metrics")
    parser_reasons: list[str] = []
    if isinstance(parser_metrics, dict):
        raw_reasons = parser_metrics.get("semantic_fallback_reasons")
        if isinstance(raw_reasons, list):
            parser_reasons = [str(item) for item in raw_reasons if item is not None]
            fallbacks.extend(parser_reasons)

    risk = risk_assessment
    if risk is None:
        raw_risk = product.get("risk_assessment")
        if isinstance(raw_risk, RiskAssessment):
            risk = raw_risk
        elif isinstance(raw_risk, dict):
            try:
                risk = RiskAssessment.model_validate(raw_risk)
            except Exception:
                fallbacks.append("risk_assessment:invalid")
                risk = None

    blast = product.get("blast_radius_size")
    flows = product.get("affected_flows_count")
    gap = product.get("test_coverage_gap")
    gaps_count = product.get("test_gaps_count")
    if gap is None and isinstance(gaps_count, int):
        gap = gaps_count > 0

    if (
        blast is None
        and flows is None
        and gap is None
        and not isinstance(parser_metrics, dict)
        and not any(
            metrics.get(k) is not None
            for k in ("body_similarity_min", "body_similarity_avg", "fingerprint_class_counts")
        )
    ):
        fallbacks.append("summary:no_producer_success")

    fp_counts = metrics.get("fingerprint_class_counts")
    if fp_counts is not None and not isinstance(fp_counts, dict):
        fp_counts = None
        fallbacks.append("fingerprints:invalid_class_counts")

    summary = SemanticDiffSummary(
        schema_version=SEMANTIC_DIFF_SUMMARY_SCHEMA_VERSION,
        parser_coverage_ratio=_parser_coverage_ratio(parser_metrics if isinstance(parser_metrics, dict) else None),
        parser_fallback_reasons=parser_reasons,
        body_similarity_min=metrics.get("body_similarity_min"),
        body_similarity_avg=metrics.get("body_similarity_avg"),
        fingerprint_class_counts=dict(fp_counts) if isinstance(fp_counts, dict) else None,
        blast_radius_size=int(blast) if isinstance(blast, int | float) else None,
        affected_flows_count=int(flows) if isinstance(flows, int | float) else None,
        test_coverage_gap=bool(gap) if gap is not None else None,
        test_gaps_count=int(gaps_count) if isinstance(gaps_count, int | float) else None,
        risk_score=risk.risk_score if risk is not None else None,
        impacts_tests=product.get("impacts_tests"),
        impacts_production_code=product.get("impacts_production_code"),
        impacts_hub_node=product.get("impacts_hub_node"),
        complex_function_changed=product.get("complex_function_changed"),
        notable_callers=list(product.get("notable_callers") or [])
        if isinstance(product.get("notable_callers"), list)
        else [],
        fallback_reasons=fallbacks,
    ).bounded()

    # Attach span metadata when Opik context is active; ignore failures.
    try:
        from opik import opik_context

        meta = semantic_analysis_metadata(summary)
        opik_context.update_current_span(metadata=meta)
        opik_context.update_current_trace(metadata=meta)
    except Exception:
        pass

    return summary
