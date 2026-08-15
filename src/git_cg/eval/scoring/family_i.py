"""Family I — offline topology / lifecycle validators (S2c / FIND-019).

Plane A harness law over fixture / bundle topology evidence. Does **not**
read live Opik traces, invent span IDs, or rewrite product accept-path.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any

from git_cg.eval.score_result import ScoreResultV1
from git_cg.eval.scoring.context import ScoreContext
from git_cg.eval.scoring.result_builder import make_score

__all__ = [
    "FAMILY_I_METRIC_IDS",
    "TopologyEvidence",
    "build_session_thread_index",
    "project_topology_evidence",
    "resolve_case_session_thread_id",
    "score_family_i",
    "synthesize_family_i_fail_closed",
]

# Frozen catalog Family I set (exactly 16 always-emitted rows).
FAMILY_I_METRIC_IDS: tuple[str, ...] = (
    "i.attempt_order_valid",
    "i.correlation_envelope_valid",
    "i.counter_span_consistent",
    "i.export_status_classified",
    "i.finalization_observed",
    "i.graph_observed_matches_declared",
    "i.lifecycle_complete",
    "i.no_cross_case_contamination",
    "i.replay_lineage_valid",
    "i.required_spans_present",
    "i.span_order_valid",
    "i.span_parentage_valid",
    "i.span_tree_valid",
    "i.thread_continuity",
    "i.thread_id_present",
    "i.trace_root_present",
)

# N3 alias table (fixture/legacy → canonical closed taxonomy).
_SPAN_ALIASES: dict[str, str] = {
    "generation": "llm_generation",
    "llm_generation": "llm_generation",
    "score_emit": "final_render",
    "final_render": "final_render",
    "accept_path_finalization": "accept_path_finalization",
    "regeneration": "regeneration",
    "fallback": "fallback",
    "diff_extraction": "diff_extraction",
    "path_classification": "path_classification",
    "intent_ranking": "intent_ranking",
    "contract_resolution": "contract_resolution",
    "plan_normalisation": "plan_normalisation",
    "plan_normalization": "plan_normalisation",
    "gold_evaluation": "gold_evaluation",
    "presentation_guard": "presentation_guard",
    "opik_export": "opik_export",
}

_CLOSED_TAXONOMY: frozenset[str] = frozenset(_SPAN_ALIASES.values())

# Bound accept-path always-required taxonomy (N5).
_BOUND_ALWAYS_REQUIRED: tuple[str, ...] = (
    "diff_extraction",
    "path_classification",
    "intent_ranking",
    "contract_resolution",
    "gold_evaluation",
    "presentation_guard",
    "final_render",
)

# Names that may legally repeat.
_DEFAULT_REPEATABLE: frozenset[str] = frozenset({"regeneration", "fallback"})

# N4 legal terminals after alias.
_LEGAL_TERMINALS: frozenset[str] = frozenset({"ok", "product_error", "export_error", "cancelled"})
_TERMINAL_ALIASES: dict[str, str | None] = {
    "ok": "ok",
    "finalized": "ok",
    "product_error": "product_error",
    "export_error": "export_error",
    "cancelled": "cancelled",
    "open": None,
    "unknown": None,
}

_EXPORT_KNOWN: frozenset[str] = frozenset(
    {
        "not_attempted",
        "queued",
        "exported",
        "export_error",
        "skipped",
        "deferred",
        "ok",
        "failed",
        "partial",
    }
)


@dataclass(slots=True)
class SpanNode:
    """Canonical span node (N15)."""

    name: str
    span_id: str | None = None
    parent_span_id: str | None = None
    raw_name: str | None = None
    order_index: int | None = None


@dataclass(slots=True)
class TopologyEvidence:
    """Projected offline topology evidence (N1-N5 / N14-N17)."""

    present: bool = False
    source: str | None = None
    root_trace_id: str | None = None
    session_thread_id: str | None = None
    terminal_state: str | None = None
    status: str | None = None
    nodes: list[SpanNode] = field(default_factory=list)
    required_spans: list[str] = field(default_factory=list)
    required_declared: bool = False
    missing_spans_declared: list[str] = field(default_factory=list)
    unexpected_spans: list[str] = field(default_factory=list)
    counters: dict[str, Any] = field(default_factory=dict)
    span_counts: dict[str, Any] = field(default_factory=dict)
    replay: dict[str, Any] | None = None
    correlation: Mapping[str, Any] | None = None
    correlation_claimed: bool = False
    declared_graph: Mapping[str, Any] | None = None
    declared_graph_pin_only: bool = False
    export_status: str | None = None
    export_claimed: bool = False
    attempt_indices: list[int] = field(default_factory=list)
    multi_attempt: bool = False
    finalization_claimed: bool = False
    accept_path_claimed: bool = False
    thread_claimed: bool = False
    generation_claimed: bool = False
    plan_path_claimed: bool = False
    fallback_claimed: bool = False
    regen_claimed: bool = False
    repeatable_names: frozenset[str] = field(default_factory=lambda: _DEFAULT_REPEATABLE)
    raw: dict[str, Any] = field(default_factory=dict)
    has_ids: bool = False


def _as_mapping(value: Any) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        return value
    return None


def _non_empty_str(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _alias_span_name(name: str) -> tuple[str, bool]:
    """Return (canonical_or_raw, is_known). Unknown names stay raw → unexpected."""
    key = name.strip()
    if key in _SPAN_ALIASES:
        return _SPAN_ALIASES[key], True
    # identity for already-canonical closed names
    if key in _CLOSED_TAXONOMY:
        return key, True
    return key, False


def _alias_terminal(raw: Any) -> str | None:
    """Map raw terminal strings to N4 legal terminals; open/unknown → None."""
    if raw is None:
        return None
    if not isinstance(raw, str):
        return None
    key = raw.strip().lower()
    if not key:
        return None
    if key in _TERMINAL_ALIASES:
        return _TERMINAL_ALIASES[key]
    # Unknown terminal strings are invalid (fail closed).
    return None


def _intish(value: Any) -> int | None:
    """Accept int or integral float; reject bool and non-integrals."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _first_present_mapping(*candidates: Any) -> tuple[Mapping[str, Any] | None, str | None]:
    """First mapping among fixed topology source labels, else ``(None, None)``."""
    labels = (
        "bundle.topology",
        "meta.topology_canonical",
        "meta.trace_topology",
        "meta.topology",
    )
    for label, cand in zip(labels, candidates, strict=False):
        m = _as_mapping(cand)
        if m is not None:
            return m, label
    return None, None


def _normalize_node(raw: Any, *, order_index: int | None = None) -> SpanNode | None:
    """Build a ``SpanNode`` from a name string or mapping (N15).

    Prefers producer-declared ``order_index`` / ``index`` over the list-position
    fallback so ``i.span_order_valid`` can fail closed on non-monotonic producers.
    """
    if isinstance(raw, str):
        name_raw = raw.strip()
        if not name_raw:
            return None
        canon, known = _alias_span_name(name_raw)
        return SpanNode(
            name=canon,
            raw_name=None if known else name_raw,
            order_index=order_index,
        )
    m = _as_mapping(raw)
    if m is None:
        return None
    name_val = m.get("name", m.get("span_name"))
    if not isinstance(name_val, str) or not name_val.strip():
        return None
    name_raw = name_val.strip()
    canon, known = _alias_span_name(name_raw)
    span_id = _non_empty_str(m.get("span_id"))
    if span_id is None:
        span_id = _non_empty_str(m.get("id"))
    parent = _non_empty_str(m.get("parent_span_id"))
    if parent is None:
        parent = _non_empty_str(m.get("parent_id"))
    # Prefer producer-declared index when present; fall back to list position.
    idx = _intish(m.get("order_index"))
    if idx is None:
        idx = _intish(m.get("index"))
    if idx is None:
        idx = order_index
    return SpanNode(
        name=canon,
        span_id=span_id,
        parent_span_id=parent,
        raw_name=None if known else name_raw,
        order_index=idx,
    )


def _alias_name_list(values: Any) -> list[str]:
    """Canonical span-name list from strings or ``{name|id}`` mappings."""
    out: list[str] = []
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return out
    for item in values:
        if isinstance(item, str) and item.strip():
            canon, _ = _alias_span_name(item.strip())
            out.append(canon)
        else:
            node = _normalize_node(item)
            if node is not None:
                out.append(node.name)
    return out


def _alias_count_map(values: Any) -> dict[str, Any]:
    """Alias span-count map keys into the closed taxonomy."""
    m = _as_mapping(values)
    if m is None:
        return {}
    out: dict[str, Any] = {}
    for k, v in m.items():
        if not isinstance(k, str) or not k.strip():
            continue
        canon, _ = _alias_span_name(k.strip())
        out[canon] = v
    return out


def _extract_nodes(topo: Mapping[str, Any]) -> list[SpanNode]:
    """Prefer structured spans/nodes; else observed_spans name list (N15)."""
    nodes: list[SpanNode] = []
    # Prefer structured spans / nodes, else observed_spans name list.
    for key in ("spans", "nodes", "observed_nodes"):
        raw = topo.get(key)
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            for i, item in enumerate(raw):
                node = _normalize_node(item, order_index=i)
                if node is not None:
                    nodes.append(node)
            if nodes:
                return nodes
    observed = topo.get("observed_spans")
    if isinstance(observed, Sequence) and not isinstance(observed, (str, bytes)):
        for i, item in enumerate(observed):
            node = _normalize_node(item, order_index=i)
            if node is not None:
                nodes.append(node)
    return nodes


def _resolve_session_thread_id(
    bundle: Mapping[str, Any],
    meta: Mapping[str, Any],
    topo: Mapping[str, Any] | None,
) -> str | None:
    """First non-empty session_thread_id across bundle → topo → meta channels (N14)."""
    for candidate in (
        bundle.get("session_thread_id"),
        (topo or {}).get("session_thread_id") if topo else None,
        meta.get("session_thread_id"),
        (_as_mapping(meta.get("topology")) or {}).get("session_thread_id"),
    ):
        s = _non_empty_str(candidate)
        if s is not None:
            return s
    return None


def project_topology_evidence(
    bundle: Mapping[str, Any] | None,
    *,
    meta: Mapping[str, Any] | None = None,
    topology: Mapping[str, Any] | None = None,
) -> TopologyEvidence | None:
    """Project offline topology evidence into a canonical internal shape (N1-N5).

    Explicit ``topology=`` wins over bundle/meta sources. Returns ``None`` only
    when no topology object and no topology-class sibling claims are present.
    Never invents span IDs, roots, parents, thread IDs, or correlation fields.
    """
    b = dict(bundle) if isinstance(bundle, Mapping) else {}
    m = dict(meta) if isinstance(meta, Mapping) else _as_mapping(b.get("meta")) or {}

    topo_src, source_label = _first_present_mapping(
        topology if topology is not None else b.get("topology"),
        m.get("topology_canonical"),
        m.get("trace_topology"),
        m.get("topology"),
    )
    evidence_map = _as_mapping(m.get("evidence")) or {}
    replay_map = _as_mapping(m.get("replay"))
    corr_from_meta = _as_mapping(m.get("correlation"))
    graph_from_meta = m.get("pipeline_graph")

    # Topology absent entirely if no topo object AND no sibling topology-class claims.
    sibling_claims = any(
        x is not None
        for x in (
            replay_map,
            corr_from_meta,
            _as_mapping(graph_from_meta) if not isinstance(graph_from_meta, str) else graph_from_meta,
            evidence_map.get("counters"),
            evidence_map.get("span_counts"),
            b.get("session_thread_id"),
            m.get("session_thread_id"),
            m.get("export_status"),
        )
    )
    if topo_src is None and not sibling_claims:
        return None

    ev = TopologyEvidence(present=topo_src is not None or sibling_claims, source=source_label)
    topo = dict(topo_src) if topo_src is not None else {}
    ev.raw = dict(topo)

    # Root / thread / terminal
    ev.root_trace_id = _non_empty_str(
        topo.get("root_trace_id")
        or topo.get("root_id")
        or topo.get("trace_id")
        or m.get("root_trace_id")
        or m.get("trace_id")
    )
    ev.session_thread_id = _resolve_session_thread_id(b, m, topo)
    terminal_raw = topo.get("terminal_state", topo.get("terminal"))
    if terminal_raw is None:
        terminal_raw = m.get("terminal_state")
    # Preserve distinction: missing vs present-invalid.
    if terminal_raw is None:
        ev.terminal_state = None
    elif isinstance(terminal_raw, str) and terminal_raw.strip().lower() in {"open", "unknown"}:
        # Explicit incomplete/invalid terminals stay distinguishable via status signals.
        ev.terminal_state = terminal_raw.strip().lower()  # type: ignore[assignment]
    else:
        aliased = _alias_terminal(terminal_raw)
        ev.terminal_state = aliased if aliased is not None else "__invalid__"
    ev.status = _non_empty_str(topo.get("status"))

    # Nodes + required
    nodes = _extract_nodes(topo)
    unexpected: list[str] = []
    for n in nodes:
        if n.raw_name is not None:
            unexpected.append(n.raw_name)
    ev.nodes = nodes
    ev.has_ids = any(n.span_id for n in nodes) or any(n.parent_span_id for n in nodes)

    req = topo.get("required_spans")
    if req is None:
        req = topo.get("required_span_set")
    if isinstance(req, Sequence) and not isinstance(req, (str, bytes)):
        ev.required_spans = _alias_name_list(req)
        ev.required_declared = True
    missing = topo.get("missing_spans")
    if isinstance(missing, Sequence) and not isinstance(missing, (str, bytes)):
        ev.missing_spans_declared = _alias_name_list(missing)
    ev.unexpected_spans = sorted(set(unexpected))

    # Counters / span_counts (topology overrides evidence sibling)
    counters = _as_mapping(topo.get("counters")) or _as_mapping(evidence_map.get("counters")) or {}
    span_counts_raw = topo.get("span_counts")
    if span_counts_raw is None:
        span_counts_raw = evidence_map.get("span_counts")
    ev.counters = dict(counters)
    ev.span_counts = _alias_count_map(span_counts_raw)

    # Replay
    replay = _as_mapping(topo.get("replay")) or replay_map
    if replay is not None:
        ev.replay = dict(replay)

    # Correlation
    corr = _as_mapping(topo.get("correlation")) or corr_from_meta
    multi_proc_fields = any(
        _non_empty_str(topo.get(k)) or _non_empty_str(m.get(k))
        for k in ("hook_phase", "process_id_token", "correlation_id")
    )
    if corr is not None or multi_proc_fields:
        ev.correlation_claimed = True
        if corr is not None:
            ev.correlation = corr
        elif multi_proc_fields:
            built: dict[str, Any] = {}
            for k in ("hook_phase", "process_id_token", "correlation_id"):
                val = _non_empty_str(topo.get(k)) or _non_empty_str(m.get(k))
                if val is not None:
                    built[k] = val
            ev.correlation = built

    # Declared graph
    graph_obj = topo.get("declared_graph")
    if graph_obj is None:
        graph_obj = graph_from_meta
    if isinstance(graph_obj, str) and graph_obj.strip():
        ev.declared_graph_pin_only = True
    elif isinstance(graph_obj, Mapping):
        ev.declared_graph = graph_obj

    # Export
    export_status = (
        _non_empty_str(topo.get("export_status"))
        or _non_empty_str(m.get("export_status"))
        or _non_empty_str(evidence_map.get("export_status"))
    )
    export_attempted = bool(
        topo.get("export_attempted")
        or m.get("export_attempted")
        or evidence_map.get("export_attempted")
        or (export_status is not None)
        or ("opik_export" in {n.name for n in nodes})
        or ("opik_export" in ev.span_counts)
    )
    if export_attempted:
        ev.export_claimed = True
        ev.export_status = export_status

    # Attempt indices
    attempts_raw = topo.get("attempt_indices") or topo.get("attempts") or m.get("attempt_indices")
    indices: list[int] = []
    if isinstance(attempts_raw, Sequence) and not isinstance(attempts_raw, (str, bytes)):
        for item in attempts_raw:
            if isinstance(item, Mapping):
                ai = _intish(item.get("attempt_index", item.get("index")))
                if ai is not None:
                    indices.append(ai)
            else:
                ai = _intish(item)
                if ai is not None:
                    indices.append(ai)
    single_attempt = _intish(topo.get("attempt_index"))
    if single_attempt is not None:
        indices.append(single_attempt)
    ev.attempt_indices = indices
    attempt_count = _intish(topo.get("attempt_count")) or _intish(m.get("attempt_count"))
    ev.multi_attempt = bool(
        (attempt_count is not None and attempt_count > 1)
        or len(set(indices)) > 1
        or bool(topo.get("multi_attempt"))
        or bool(m.get("multi_attempt"))
    )

    # Claims derived from counters / observed
    observed_names = {n.name for n in nodes}
    llm_calls = _intish(counters.get("llm_calls")) or 0
    regen = _intish(counters.get("gold_regen_attempts")) or _intish(counters.get("regen_attempts")) or 0
    fallback_n = _intish(counters.get("fallback_count")) or _intish(counters.get("fallback_attempts")) or 0

    ev.generation_claimed = bool(
        llm_calls > 0
        or "llm_generation" in observed_names
        or "llm_generation" in ev.span_counts
        or bool(topo.get("generation_claimed"))
    )
    ev.plan_path_claimed = bool(
        topo.get("plan_path")
        or topo.get("plan_path_used")
        or m.get("plan_path_used")
        or "plan_normalisation" in observed_names
        or "plan_normalisation" in ev.span_counts
    )
    ev.regen_claimed = bool(regen > 0 or "regeneration" in observed_names)
    ev.fallback_claimed = bool(
        fallback_n > 0
        or "fallback" in observed_names
        or bool(topo.get("fallback_path"))
        or bool(m.get("fallback_path"))
    )
    fin_claimed = bool(
        topo.get("finalization_claimed")
        or m.get("finalization_claimed")
        or topo.get("accept_path")
        or m.get("accept_path")
        or "accept_path_finalization" in observed_names
        or "accept_path_finalization" in ev.required_spans
        or "accept_path_finalization" in ev.span_counts
    )
    # Bound final_accept is an accept-path claim.
    if b.get("bound") is True and b.get("artifact_class") == "final_accept":
        fin_claimed = True
        ev.accept_path_claimed = True
    if b.get("artifact_class") == "final_accept":
        ev.accept_path_claimed = True
    ev.finalization_claimed = fin_claimed

    ev.thread_claimed = bool(
        ev.session_thread_id
        or ev.multi_attempt
        or bool(topo.get("thread_required"))
        or bool(m.get("thread_required"))
        or ev.accept_path_claimed
    )

    # Repeatable overrides
    rep = topo.get("repeatable_spans") or m.get("repeatable_spans")
    if isinstance(rep, Sequence) and not isinstance(rep, (str, bytes)):
        extra = {_alias_span_name(x)[0] for x in rep if isinstance(x, str) and x.strip()}
        ev.repeatable_names = frozenset(set(_DEFAULT_REPEATABLE) | extra)

    return ev


def _observed_name_multiset(ev: TopologyEvidence) -> dict[str, int]:
    """Node multiset when structured; else span_counts fallback."""
    counts: dict[str, int] = defaultdict(int)
    if ev.nodes:
        for n in ev.nodes:
            counts[n.name] += 1
        return dict(counts)
    # Fall back to span_counts when nodes empty.
    for k, v in ev.span_counts.items():
        iv = _intish(v)
        if iv is not None and iv > 0:
            counts[k] += iv
    return dict(counts)


def _resolve_required_set(
    ev: TopologyEvidence,
    *,
    bound: bool,
    require_topology: bool,
) -> tuple[list[str] | None, str | None]:
    """Return ``(required_list, fail_reason)`` for required-span resolution (N5).

    Declared required set wins; bound paths fall back to the always-required
    accept-path taxonomy. ``None`` list + reason means fail/inapplicable upstream.
    """
    if ev.required_declared and ev.required_spans:
        # Preserve order, unique.
        return list(dict.fromkeys(ev.required_spans)), None
    if ev.required_declared and not ev.required_spans:
        return [], None

    # Canonical required_span_set already handled via required_declared.

    if bound and ev.present and (ev.nodes or ev.span_counts or ev.required_declared):
        req = list(_BOUND_ALWAYS_REQUIRED)
        if ev.generation_claimed:
            req.append("llm_generation")
        if ev.plan_path_claimed:
            req.append("plan_normalisation")
        if ev.regen_claimed:
            req.append("regeneration")
        if ev.fallback_claimed:
            req.append("fallback")
        if ev.finalization_claimed or ev.accept_path_claimed or bound:
            req.append("accept_path_finalization")
        if ev.export_claimed:
            req.append("opik_export")
        return list(dict.fromkeys(req)), None

    if require_topology:
        return None, "required_set_unresolvable"
    return None, None  # inapplicable


def _fingerprint_span_name(name: str) -> str:
    """Pass closed-taxonomy names; digest unknown/raw names for N11 fingerprints."""
    key = name.strip()
    if key in _CLOSED_TAXONOMY:
        return key
    return "unknown:" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def _diag_fingerprint_inputs(
    *,
    metric_id: str,
    failure_ids: list[str] | None,
    blame_span: str | None,
    first_divergent: str | None,
    missing: Sequence[str] | None,
    unexpected: Sequence[str] | None,
    artifact_class: str | None,
    regime: Any,
    path_class: str | None,
) -> dict[str, Any]:
    """Sanitised N11 fingerprint inputs only — no raw text / ids / paths / urls.

    Closed-taxonomy span names pass through; unknown names are digested via
    ``_fingerprint_span_name``. ``path_class`` is a path-class key, not a filesystem path.
    Row-level evidence may still carry raw names for local debugging.
    """
    out: dict[str, Any] = {
        "metric_ids": [metric_id],
    }
    if failure_ids:
        out["failure_ids"] = sorted(str(x) for x in failure_ids)
    if blame_span:
        out["blame_span"] = _fingerprint_span_name(blame_span)
    if first_divergent:
        out["first_divergent_span"] = _fingerprint_span_name(first_divergent)
    if missing:
        out["missing_required_spans"] = sorted({_fingerprint_span_name(x) for x in missing})
    if unexpected:
        out["unexpected_spans"] = sorted({_fingerprint_span_name(x) for x in unexpected})
    if artifact_class:
        out["artifact_class"] = artifact_class
    if isinstance(regime, str) and regime.strip():
        out["regime"] = regime.strip()
    if isinstance(path_class, str) and path_class.strip():
        # path-class *key*, not filesystem path
        out["path_class_key"] = path_class.strip()
    return out


def _row(
    metric_id: str,
    ok: bool,
    *,
    reason: str | None = None,
    evidence: dict[str, Any] | None = None,
    failure_ids: list[str] | None = None,
) -> ScoreResultV1:
    """Emit one Family I pass_fail row with strict bool value == passed."""
    val = bool(ok)
    return make_score(
        metric_id,
        val,
        passed=val,
        reason=reason,
        evidence=evidence,
        failure_ids=failure_ids,
        product_authority="git_cg.eval.scoring.family_i",
    )


def synthesize_family_i_fail_closed(
    *,
    reason: str = "family_i_evaluator_error",
    errors: Sequence[str] | None = None,
) -> list[ScoreResultV1]:
    """Emit all 16 Family I rows fail-closed (N18 recovery)."""
    evidence = {
        "recovery": True,
        "reason": reason,
        "errors": list(errors or [])[:10],
    }
    rows: list[ScoreResultV1] = []
    for mid in FAMILY_I_METRIC_IDS:
        rows.append(
            _row(
                mid,
                False,
                reason=reason,
                evidence=dict(evidence),
                failure_ids=["EVAL_FAMILY_I_RECOVERY"],
            )
        )
    return rows


def _tree_and_parentage(
    ev: TopologyEvidence,
) -> tuple[bool, str | None, dict[str, Any], bool, str | None, dict[str, Any]]:
    """Return ``tree_ok/reason/ev`` and ``parentage_ok/reason/ev`` (ID or name-only).

    ID mode uses iterative DFS cycle detection so deep valid chains cannot
    ``RecursionError``. Dangling parents fail parentage even when multiple roots
    dominate tree status.
    """
    tree_ev: dict[str, Any] = {"node_count": len(ev.nodes), "has_ids": ev.has_ids}
    par_ev: dict[str, Any] = {"has_ids": ev.has_ids}

    if not ev.nodes and not ev.span_counts and not ev.required_spans:
        # Empty observed structure with present topology shell — still a well-formed empty list.
        return True, None, tree_ev, True, "parentage_ids_not_provided", {**par_ev, "mode": "name_only"}

    # Name-only well-formed list: tree passes if names parse; parentage inapplicable.
    if not ev.has_ids:
        # Singleton duplicate detection still applies on names.
        counts = _observed_name_multiset(ev)
        dups = sorted(
            name for name, n in counts.items() if n > 1 and name not in ev.repeatable_names and name in _CLOSED_TAXONOMY
        )
        if dups:
            tree_ev["duplicate_singleton_names"] = dups
            return (
                False,
                "duplicate_singleton_span_names",
                tree_ev,
                True,
                "parentage_ids_not_provided",
                {**par_ev, "mode": "name_only"},
            )
        if any(n.raw_name is None and not n.name for n in ev.nodes):
            return False, "malformed_span_nodes", tree_ev, True, "parentage_ids_not_provided", par_ev
        return True, None, tree_ev, True, "parentage_ids_not_provided", {**par_ev, "mode": "name_only"}

    # ID mode
    ids = [n.span_id for n in ev.nodes if n.span_id]
    id_set = set(ids)
    if len(ids) != len(id_set):
        tree_ev["duplicate_span_ids"] = True
        return False, "duplicate_span_ids", tree_ev, False, "duplicate_span_ids", par_ev

    by_id = {n.span_id: n for n in ev.nodes if n.span_id}
    self_parents = [n.span_id for n in ev.nodes if n.span_id and n.parent_span_id == n.span_id]
    if self_parents:
        tree_ev["self_parents"] = self_parents
        par_ev["self_parents"] = self_parents
        return False, "self_parent", tree_ev, False, "self_parent", par_ev

    dangling = sorted({n.parent_span_id for n in ev.nodes if n.parent_span_id and n.parent_span_id not in by_id})
    # Cycle detection (iterative DFS) — deep valid chains must not raise RecursionError.
    graph: dict[str, str | None] = {n.span_id: n.parent_span_id for n in ev.nodes if n.span_id}
    visiting: set[str] = set()
    visited: set[str] = set()
    cycle_found = False

    for start in graph:
        if start in visited or cycle_found:
            continue
        stack: list[tuple[str, str]] = [(start, "enter")]
        while stack:
            node_id, phase = stack.pop()
            if phase == "exit":
                visiting.discard(node_id)
                visited.add(node_id)
                continue
            if node_id in visiting:
                cycle_found = True
                break
            if node_id in visited:
                continue
            visiting.add(node_id)
            stack.append((node_id, "exit"))
            parent = graph.get(node_id)
            if parent and parent in graph:
                stack.append((parent, "enter"))
        if cycle_found:
            break

    if cycle_found:
        tree_ev["cycle"] = True
        return False, "cycle_detected", tree_ev, False, "cycle_detected", par_ev

    roots = [sid for sid, parent in graph.items() if not parent or parent not in graph]
    # Root also via parent missing: nodes whose parent is None
    explicit_roots = [n.span_id for n in ev.nodes if n.span_id and not n.parent_span_id]
    root_ids = sorted(set(roots) | set(explicit_roots))
    tree_ev["roots"] = root_ids
    if dangling:
        par_ev["dangling_parents"] = dangling
    if len(root_ids) > 1:
        tree_ev["multiple_roots"] = True
        # Dangling parentage still fails even when multiple roots dominate tree status.
        if dangling:
            return False, "multiple_roots", tree_ev, False, "dangling_parent", par_ev
        return False, "multiple_roots", tree_ev, True, None, par_ev

    if dangling:
        # Contract: dangling parent / orphan in ID mode ⇒ fail parentage.
        return True, None, tree_ev, False, "dangling_parent", par_ev

    # Singleton name duplicates still invalid in ID mode
    counts = _observed_name_multiset(ev)
    dups = sorted(
        name for name, n in counts.items() if n > 1 and name not in ev.repeatable_names and name in _CLOSED_TAXONOMY
    )
    if dups:
        tree_ev["duplicate_singleton_names"] = dups
        return False, "duplicate_singleton_span_names", tree_ev, True, None, par_ev

    return True, None, tree_ev, True, None, par_ev


def _graph_sets(graph: Mapping[str, Any]) -> tuple[set[str], set[tuple[str, str]]]:
    """Required canonical nodes (optional excluded) + directed edges from a declared graph."""
    nodes: set[str] = set()
    edges: set[tuple[str, str]] = set()

    raw_nodes = graph.get("nodes")
    optional_nodes: set[str] = set()
    if isinstance(raw_nodes, Sequence) and not isinstance(raw_nodes, (str, bytes)):
        for item in raw_nodes:
            if isinstance(item, str) and item.strip():
                nodes.add(_alias_span_name(item.strip())[0])
            elif isinstance(item, Mapping):
                nm = item.get("name") or item.get("id")
                if isinstance(nm, str) and nm.strip():
                    canon = _alias_span_name(nm.strip())[0]
                    nodes.add(canon)
                    if item.get("optional") is True:
                        optional_nodes.add(canon)

    raw_edges = graph.get("edges")
    if isinstance(raw_edges, Sequence) and not isinstance(raw_edges, (str, bytes)):
        for item in raw_edges:
            if isinstance(item, Sequence) and not isinstance(item, (str, bytes)) and len(item) >= 2:
                a, b = item[0], item[1]
                if isinstance(a, str) and isinstance(b, str):
                    edges.add((_alias_span_name(a.strip())[0], _alias_span_name(b.strip())[0]))
            elif isinstance(item, Mapping):
                a = item.get("from") or item.get("source") or item.get("parent")
                b = item.get("to") or item.get("target") or item.get("child")
                if isinstance(a, str) and isinstance(b, str):
                    edges.add((_alias_span_name(a.strip())[0], _alias_span_name(b.strip())[0]))

    # stash optional on graph via nodes side-channel: return only required nodes for mismatch
    required_nodes = nodes - optional_nodes
    return required_nodes, edges


def score_family_i(
    ctx: ScoreContext,
    *,
    require_topology: bool = False,
    session_thread_index: Mapping[str, tuple[str, ...]] | None = None,
    topology: Mapping[str, Any] | None = None,
    **_evidence_kwargs: Any,
) -> list[ScoreResultV1]:
    """Score all 16 Family I topology/lifecycle metrics offline (S2c).

    Always emits one schema-valid ``ScoreResultV1`` per frozen Family I catalog
    id, in catalogue order. Never invents span/root/parent/thread/correlation
    evidence. Missing topology shells fail honestly under ``require_topology``;
    unclaimed correlation/replay/export rows pass without fabricating greens.
    """
    bundle = ctx.bundle if isinstance(ctx.bundle, Mapping) else {}
    meta = ctx.meta if isinstance(ctx.meta, Mapping) else {}
    ev = project_topology_evidence(bundle, meta=meta, topology=topology)

    artifact_class = ctx.artifact_class
    regime = bundle.get("regime") if isinstance(bundle, Mapping) else None
    path_class = ctx.path_class_gate
    bound = bool(ctx.bound)

    def base_evidence(**extra: Any) -> dict[str, Any]:
        out: dict[str, Any] = {
            "require_topology": require_topology,
            "topology_present": bool(ev and ev.present),
            "topology_source": getattr(ev, "source", None) if ev else None,
            "bound": bound,
            "artifact_class": artifact_class,
        }
        if ev is not None and ev.unexpected_spans:
            out["unexpected_spans"] = list(ev.unexpected_spans)
        out.update(extra)
        return out

    # -------- Missing topology shell --------
    if ev is None:
        rows: list[ScoreResultV1] = []
        absent = "topology_evidence_absent"
        # Block/warn/info generally fail honestly; correlation/replay/export pass unclaimed.
        special_pass = {
            "i.correlation_envelope_valid": "correlation_not_claimed",
            "i.replay_lineage_valid": "replay_not_claimed",
            "i.export_status_classified": "export_not_claimed",
        }
        for mid in FAMILY_I_METRIC_IDS:
            if mid in special_pass:
                rows.append(
                    _row(
                        mid,
                        True,
                        reason=special_pass[mid],
                        evidence=base_evidence(inapplicable=True),
                    )
                )
                continue
            # Cross-case without index → honest inapplicable pass
            if mid == "i.no_cross_case_contamination" and not session_thread_index:
                rows.append(
                    _row(
                        mid,
                        True,
                        reason="cross_case_evidence_unavailable",
                        evidence=base_evidence(inapplicable=True),
                    )
                )
                continue
            fid = ["EVAL_TOPOLOGY_ABSENT"]
            evidence = base_evidence(
                diag_fingerprint_inputs=_diag_fingerprint_inputs(
                    metric_id=mid,
                    failure_ids=fid,
                    blame_span=None,
                    first_divergent=None,
                    missing=None,
                    unexpected=None,
                    artifact_class=artifact_class,
                    regime=regime,
                    path_class=path_class,
                )
            )
            rows.append(_row(mid, False, reason=absent, evidence=evidence, failure_ids=fid))
        return _ordered(rows)

    assert ev is not None
    observed = _observed_name_multiset(ev)
    observed_names = set(observed)

    # ----- tree / parentage shared -----
    tree_ok, tree_reason, tree_ev, par_ok, par_reason, par_ev = _tree_and_parentage(ev)

    # ----- required set -----
    required, req_fail_reason = _resolve_required_set(ev, bound=bound, require_topology=require_topology)
    missing_required: list[str] = []
    required_ok: bool
    required_reason: str | None
    if req_fail_reason == "required_set_unresolvable":
        required_ok = False
        required_reason = "required_set_unresolvable"
    elif required is None:
        # inapplicable
        required_ok = True
        required_reason = "required_set_not_applicable"
    else:
        missing_required = [name for name in required if observed.get(name, 0) <= 0]
        # Also honour declared missing_spans when provided as additional signal
        for name in ev.missing_spans_declared:
            if name not in missing_required and observed.get(name, 0) <= 0 and name in required:
                missing_required.append(name)
        required_ok = not missing_required
        required_reason = None if required_ok else "missing_required_spans"

    blame_span = missing_required[0] if missing_required else None
    first_divergent = blame_span

    # ----- lifecycle -----
    term = ev.terminal_state
    if term is None or term == "open":
        life_ok, life_reason = False, "terminal_missing_or_open"
    elif term in {"unknown", "__invalid__"}:
        life_ok, life_reason = False, "terminal_invalid"
    elif term in _LEGAL_TERMINALS:
        life_ok, life_reason = True, None
    else:
        life_ok, life_reason = False, "terminal_invalid"

    # ----- root -----
    root_ok = bool(ev.root_trace_id)
    root_reason = None if root_ok else ("topology_evidence_absent" if not ev.present else "root_trace_missing")

    # ----- counters -----
    counter_ok = True
    counter_reason: str | None = None
    counter_ev: dict[str, Any] = {
        "counters": dict(ev.counters),
        "span_counts": dict(ev.span_counts),
    }
    has_counter_evidence = bool(ev.counters) or bool(ev.span_counts)
    if not has_counter_evidence:
        counter_ok = True
        counter_reason = "counters_not_claimed"
    else:
        regen_attempts = _intish(ev.counters.get("gold_regen_attempts"))
        if regen_attempts is None:
            regen_attempts = _intish(ev.counters.get("regen_attempts"))
        regen_spans = _intish(ev.span_counts.get("regeneration"))
        if regen_spans is None:
            regen_spans = observed.get("regeneration", 0)
        if regen_attempts is not None:
            if regen_attempts > 0 and (regen_spans or 0) <= 0:
                counter_ok = False
                counter_reason = "counter_span_mismatch_regen"
            elif regen_attempts == 0 and (regen_spans or 0) > 0:
                counter_ok = False
                counter_reason = "counter_span_mismatch_regen_extra"
        # llm_calls vs generation when both present
        llm_calls = _intish(ev.counters.get("llm_calls"))
        gen_spans = _intish(ev.span_counts.get("llm_generation"))
        if gen_spans is None:
            gen_spans = observed.get("llm_generation")
        if llm_calls is not None and gen_spans is not None and llm_calls > 0 and gen_spans <= 0:
            counter_ok = False
            counter_reason = counter_reason or "counter_span_mismatch_llm"
        counter_ev["regen_attempts"] = regen_attempts
        counter_ev["regen_spans"] = regen_spans

    # ----- finalization -----
    fin_observed = observed.get("accept_path_finalization", 0) > 0
    if (
        ev.finalization_claimed
        or (require_topology and (ev.accept_path_claimed or bound))
        or (require_topology and bound)
    ):
        fin_ok = fin_observed
        fin_reason = None if fin_ok else "finalization_missing"
    else:
        # not claimed
        fin_ok = True
        fin_reason = "finalization_not_claimed" if not fin_observed else None

    # ----- replay -----
    if ev.replay is None or not bool(ev.replay.get("is_replay")):
        replay_ok = True
        replay_reason: str | None = "replay_not_claimed"
        replay_ev: dict[str, Any] = {"claimed": False}
    else:
        parent_trace = _non_empty_str(ev.replay.get("parent_trace_id"))
        parent_thread = _non_empty_str(ev.replay.get("parent_session_thread_id"))
        missing_lineage = []
        if not parent_trace:
            missing_lineage.append("parent_trace_id")
        if not parent_thread:
            missing_lineage.append("parent_session_thread_id")
        # Require lineage when is_replay (contract + fixture require_lineage_fields)
        require_fields = bool(ev.replay.get("require_lineage_fields", True))
        if require_fields and missing_lineage:
            replay_ok = False
            replay_reason = "replay_lineage_incomplete"
        else:
            replay_ok = True
            replay_reason = None
        replay_ev = {
            "claimed": True,
            "missing_fields": missing_lineage,
            "has_parent_trace": bool(parent_trace),
            "has_parent_thread": bool(parent_thread),
        }

    # ----- correlation -----
    if not ev.correlation_claimed:
        corr_ok = True
        corr_reason: str | None = "correlation_not_claimed"
        corr_ev: dict[str, Any] = {"claimed": False}
    else:
        corr_map = dict(ev.correlation or {})
        cid = _non_empty_str(corr_map.get("correlation_id"))
        if not cid:
            corr_ok = False
            corr_reason = "correlation_id_missing"
        else:
            # behavioural join fields when multi-process explicitly claimed
            multi = any(_non_empty_str(corr_map.get(k)) for k in ("hook_phase", "process_id_token", "hooks")) or bool(
                corr_map.get("multi_process")
            )
            if multi and not (
                _non_empty_str(corr_map.get("hook_phase"))
                or _non_empty_str(corr_map.get("process_id_token"))
                or corr_map.get("hooks")
            ):
                corr_ok = False
                corr_reason = "correlation_join_fields_missing"
            else:
                corr_ok = True
                corr_reason = None
        corr_ev = {"claimed": True, "has_correlation_id": bool(cid)}

    # ----- export -----
    if not ev.export_claimed:
        export_ok = True
        export_reason: str | None = "export_not_claimed"
        export_ev: dict[str, Any] = {"claimed": False}
    else:
        status = (ev.export_status or "").strip().lower()
        if status and status in _EXPORT_KNOWN:
            export_ok = True
            export_reason = None
        elif status:
            export_ok = False
            export_reason = "export_status_unknown"
        else:
            export_ok = False
            export_reason = "export_status_missing"
        export_ev = {"claimed": True, "export_status": ev.export_status}

    # ----- graph observed vs declared -----
    if ev.declared_graph_pin_only and ev.declared_graph is None:
        graph_ok = True
        graph_reason: str | None = "declared_graph_object_unavailable"
        graph_ev: dict[str, Any] = {"pin_only": True}
    elif ev.declared_graph is None:
        graph_ok = True
        graph_reason = "declared_graph_not_claimed"
        graph_ev = {"claimed": False}
    else:
        decl_nodes, decl_edges = _graph_sets(ev.declared_graph)
        obs_nodes = set(observed_names)
        # Optional plan nodes may be absent without failing — already removed in _graph_sets
        missing_nodes = sorted(n for n in decl_nodes if n not in obs_nodes)
        # Edge check when we have id parent relationships
        obs_edges: set[tuple[str, str]] = set()
        if ev.has_ids:
            by_id = {n.span_id: n for n in ev.nodes if n.span_id}
            for n in ev.nodes:
                if n.span_id and n.parent_span_id and n.parent_span_id in by_id:
                    parent = by_id[n.parent_span_id]
                    obs_edges.add((parent.name, n.name))
        else:
            # name-only order edges between consecutive observed list
            ordered = [n.name for n in ev.nodes]
            for a, b in pairwise(ordered):
                obs_edges.add((a, b))
        missing_edges = sorted(e for e in decl_edges if e not in obs_edges) if decl_edges else []
        graph_ok = not missing_nodes and not missing_edges
        graph_reason = None if graph_ok else "graph_observed_mismatch"
        graph_ev = {
            "declared_nodes": sorted(decl_nodes),
            "missing_nodes": missing_nodes,
            "missing_edges": [list(e) for e in missing_edges],
        }

    # ----- span order -----
    if ev.declared_graph is not None and any(n.order_index is not None for n in ev.nodes):
        # If graph edges exist, ensure order_index respects parent-before-child when both indexed
        order_map = {n.name: n.order_index for n in ev.nodes if n.order_index is not None}
        _, decl_edges = _graph_sets(ev.declared_graph)
        bad: list[list[str]] = []
        for a, b in decl_edges:
            if a in order_map and b in order_map and order_map[a] > order_map[b]:
                bad.append([a, b])
        order_ok = not bad
        order_reason = None if order_ok else "span_order_violation"
        order_ev: dict[str, Any] = {"violations": bad}
    elif ev.nodes and all(n.order_index is not None for n in ev.nodes):
        idxs = [int(n.order_index) for n in ev.nodes if n.order_index is not None]
        order_ok = idxs == sorted(idxs)
        order_reason = None if order_ok else "span_order_non_monotonic"
        order_ev = {"indices": idxs}
    else:
        order_ok = True
        order_reason = "order_evidence_absent"
        order_ev = {"inapplicable": True}

    # ----- attempt order -----
    if ev.attempt_indices:
        # Contract: attempt_index monotonic non-decreasing; equal values are allowed.
        attempt_ok = all(a <= b for a, b in pairwise(ev.attempt_indices))
        attempt_reason = None if attempt_ok else "attempt_order_non_monotonic"
        attempt_ev: dict[str, Any] = {"attempt_indices": list(ev.attempt_indices)}
    else:
        attempt_ok = True
        attempt_reason = "attempt_indices_not_provided"
        attempt_ev = {"inapplicable": True}

    # ----- thread id present -----
    thread_id = ev.session_thread_id
    if thread_id:
        thread_present_ok = True
        thread_present_reason = None
    elif (
        (require_topology and (bound or ev.thread_claimed or ev.multi_attempt or ev.accept_path_claimed))
        or ev.thread_claimed
        or ev.multi_attempt
        or ev.accept_path_claimed
    ):
        thread_present_ok = False
        thread_present_reason = "thread_id_missing"
    else:
        thread_present_ok = True
        thread_present_reason = "thread_not_claimed"

    # ----- thread continuity -----
    if ev.multi_attempt and thread_id:
        # Without per-attempt thread list, presence of shared id + monotonic attempts is enough.
        cont_ok = attempt_ok if ev.attempt_indices else True
        cont_reason = None if cont_ok else "thread_continuity_broken"
        cont_ev: dict[str, Any] = {
            "session_thread_id_present": True,
            "multi_attempt": True,
            "attempt_indices": list(ev.attempt_indices),
        }
    elif not ev.multi_attempt:
        cont_ok = True
        cont_reason = "single_attempt_no_continuity_claim"
        cont_ev = {"multi_attempt": False}
    else:
        cont_ok = not require_topology
        cont_reason = "thread_continuity_unresolved" if not require_topology else "thread_id_missing"
        if require_topology and not thread_id:
            cont_ok = False
            cont_reason = "thread_id_missing"
        cont_ev = {"multi_attempt": True, "session_thread_id_present": bool(thread_id)}

    # ----- cross-case contamination -----
    if session_thread_index and thread_id:
        peers = tuple(session_thread_index.get(thread_id, ()))
        # contamination if other case ids share this thread
        foreign = sorted({c for c in peers if c != ctx.case_id})
        if foreign:
            xcase_ok = False
            xcase_reason: str | None = "cross_case_thread_shared"
            xcase_ev: dict[str, Any] = {
                "session_thread_id_present": True,
                "peer_case_ids": list(peers),
                "foreign_case_ids": foreign,
            }
        else:
            xcase_ok = True
            xcase_reason = None
            xcase_ev = {"session_thread_id_present": True, "peer_case_ids": list(peers)}
    elif session_thread_index is None:
        xcase_ok = True
        xcase_reason = "cross_case_evidence_unavailable"
        xcase_ev = {"index_present": False}
    else:
        # index present but this case has no thread id
        xcase_ok = True
        xcase_reason = "cross_case_evidence_unavailable"
        xcase_ev = {"index_present": True, "session_thread_id_present": False}

    # Build rows
    def emit(
        mid: str,
        ok: bool,
        reason: str | None,
        evidence: dict[str, Any],
        *,
        failure_ids: list[str] | None = None,
        missing: Sequence[str] | None = None,
        blame: str | None = None,
        divergent: str | None = None,
    ) -> ScoreResultV1:
        evd = base_evidence(**evidence)
        if missing:
            evd["missing_required_spans"] = list(missing)
        if ev.unexpected_spans:
            evd.setdefault("unexpected_spans", list(ev.unexpected_spans))
        if blame:
            evd["blame_span"] = blame
        if divergent:
            evd["first_divergent_span"] = divergent
        fids = failure_ids
        if not ok and not fids:
            fids = ["EVAL_TOPOLOGY"]
        if not ok:
            evd["diag_fingerprint_inputs"] = _diag_fingerprint_inputs(
                metric_id=mid,
                failure_ids=fids,
                blame_span=blame,
                first_divergent=divergent,
                missing=missing,
                unexpected=ev.unexpected_spans,
                artifact_class=artifact_class,
                regime=regime,
                path_class=path_class,
            )
        return _row(mid, ok, reason=reason, evidence=evd, failure_ids=fids if not ok else None)

    rows_map: dict[str, ScoreResultV1] = {}
    rows_map["i.trace_root_present"] = emit(
        "i.trace_root_present",
        root_ok,
        root_reason,
        {"root_trace_id_present": bool(ev.root_trace_id)},
    )
    rows_map["i.lifecycle_complete"] = emit(
        "i.lifecycle_complete",
        life_ok,
        life_reason,
        {"terminal_state": term},
        blame=blame_span if not life_ok else None,
    )
    rows_map["i.span_tree_valid"] = emit(
        "i.span_tree_valid",
        tree_ok,
        tree_reason,
        tree_ev,
    )
    rows_map["i.span_parentage_valid"] = emit(
        "i.span_parentage_valid",
        par_ok,
        par_reason,
        par_ev,
    )
    rows_map["i.required_spans_present"] = emit(
        "i.required_spans_present",
        required_ok,
        required_reason,
        {
            "required_spans": list(required or []),
            "observed_spans": sorted(observed_names),
            "required_declared": ev.required_declared,
        },
        missing=missing_required,
        blame=blame_span,
        divergent=first_divergent,
    )
    rows_map["i.span_order_valid"] = emit(
        "i.span_order_valid",
        order_ok,
        order_reason,
        order_ev,
    )
    rows_map["i.thread_id_present"] = emit(
        "i.thread_id_present",
        thread_present_ok,
        thread_present_reason,
        {
            "session_thread_id_present": bool(thread_id),
            "multi_attempt": ev.multi_attempt,
            "thread_claimed": ev.thread_claimed,
        },
    )
    rows_map["i.thread_continuity"] = emit(
        "i.thread_continuity",
        cont_ok,
        cont_reason,
        cont_ev,
    )
    rows_map["i.counter_span_consistent"] = emit(
        "i.counter_span_consistent",
        counter_ok,
        counter_reason,
        counter_ev,
        blame="regeneration" if not counter_ok else None,
    )
    rows_map["i.finalization_observed"] = emit(
        "i.finalization_observed",
        fin_ok,
        fin_reason,
        {
            "finalization_observed": fin_observed,
            "finalization_claimed": ev.finalization_claimed,
            "accept_path_claimed": ev.accept_path_claimed,
        },
        missing=["accept_path_finalization"] if not fin_ok else None,
        blame="accept_path_finalization" if not fin_ok else None,
    )
    rows_map["i.export_status_classified"] = emit(
        "i.export_status_classified",
        export_ok,
        export_reason,
        export_ev,
    )
    rows_map["i.graph_observed_matches_declared"] = emit(
        "i.graph_observed_matches_declared",
        graph_ok,
        graph_reason,
        graph_ev,
    )
    rows_map["i.replay_lineage_valid"] = emit(
        "i.replay_lineage_valid",
        replay_ok,
        replay_reason,
        replay_ev,
    )
    rows_map["i.no_cross_case_contamination"] = emit(
        "i.no_cross_case_contamination",
        xcase_ok,
        xcase_reason,
        xcase_ev,
    )
    rows_map["i.attempt_order_valid"] = emit(
        "i.attempt_order_valid",
        attempt_ok,
        attempt_reason,
        attempt_ev,
    )
    rows_map["i.correlation_envelope_valid"] = emit(
        "i.correlation_envelope_valid",
        corr_ok,
        corr_reason,
        corr_ev,
    )

    return _ordered(list(rows_map.values()))


def _ordered(rows: Iterable[ScoreResultV1]) -> list[ScoreResultV1]:
    """Stable emission order matching ``FAMILY_I_METRIC_IDS``; fill gaps fail-closed."""
    by = {r.metric_id: r for r in rows}
    out: list[ScoreResultV1] = []
    for mid in FAMILY_I_METRIC_IDS:
        row = by.get(mid)
        if row is None:
            out.append(
                _row(
                    mid,
                    False,
                    reason="family_i_row_missing_recovered",
                    evidence={"recovery": True},
                    failure_ids=["EVAL_FAMILY_I_RECOVERY"],
                )
            )
            continue
        # Enforce value == passed for pass_fail rows (N18).
        if row.passed is not None and bool(row.value) != bool(row.passed):
            out.append(
                _row(
                    mid,
                    False,
                    reason="family_i_value_passed_mismatch",
                    evidence={"recovery": True, "prior_value": row.value, "prior_passed": row.passed},
                    failure_ids=["EVAL_FAMILY_I_RECOVERY"],
                )
            )
            continue
        out.append(row)
    return out


def resolve_case_session_thread_id(bundle: Mapping[str, Any]) -> str | None:
    """Resolve a case's session thread id for suite index construction (N14)."""
    if not isinstance(bundle, Mapping):
        return None
    meta = _as_mapping(bundle.get("meta")) or {}
    topo = (
        _as_mapping(bundle.get("topology"))
        or _as_mapping(meta.get("topology_canonical"))
        or _as_mapping(meta.get("trace_topology"))
        or _as_mapping(meta.get("topology"))
    )
    return _resolve_session_thread_id(bundle, meta, topo)


def build_session_thread_index(
    case_bundles: Sequence[tuple[str, Mapping[str, Any]]],
) -> dict[str, tuple[str, ...]]:
    """Build read-only ``thread_id → sorted unique case_ids`` mapping (N14)."""
    acc: dict[str, set[str]] = defaultdict(set)
    for case_id, bundle in case_bundles:
        if not isinstance(case_id, str) or not case_id.strip():
            continue
        tid = resolve_case_session_thread_id(bundle if isinstance(bundle, Mapping) else {})
        if tid is None:
            continue
        acc[tid].add(case_id.strip())
    return {tid: tuple(sorted(cases)) for tid, cases in sorted(acc.items(), key=lambda kv: kv[0])}
