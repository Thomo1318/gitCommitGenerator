"""Phase 9 scoped-history producers (Issue #163).

Graph/AST-derived advisory evidence for split/rename/purpose markers.
Ranker/SOP remains the sole authority for intent_id / gitmoji / cc_type /
semver_impact / changelog_group. Producers are pure over collected facts,
gated by ``is_semantic_enabled``, and never mutate DiffSignals / DiffFileSummary
or the worktree/index.
"""

from __future__ import annotations

import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import SimpleNamespace
from typing import Any

from git_cg.semantic import _bound_str
from git_cg.semantic_flags import is_semantic_enabled

# ---------------------------------------------------------------------------
# Closed enums / constants (unit-tested)
# ---------------------------------------------------------------------------

MAX_FILE_FLOW_ENTRIES = 64
MAX_FLOWS_PER_FILE = 16
MAX_RENAME_PAIRS = 32
MAX_GUIDANCE_LEN = 480
MAX_RATIONALE_LEN = 240

# Rename composite thresholds (0.0-1.0 body_similarity axis).
RENAME_HIGH_BODY_SIMILARITY = 0.85
RENAME_MEDIUM_BODY_SIMILARITY = 0.55
RENAME_LOW_BODY_SIMILARITY = 0.25
# Operator-facing band floors (high / medium / low). band_rename_pair uses HIGH+LOW
# directly; MEDIUM remains part of the published matrix for docs and future tuning.
RENAME_BODY_SIMILARITY_THRESHOLDS = (
    RENAME_HIGH_BODY_SIMILARITY,
    RENAME_MEDIUM_BODY_SIMILARITY,
    RENAME_LOW_BODY_SIMILARITY,
)


class ScopedHistoryFallbackReason(StrEnum):
    """Closed fallback vocabulary for scoped-history producers."""

    NONE = "none"
    FLAG_OFF = "flag_off"
    GRAPH_UNAVAILABLE = "graph_unavailable"
    SHADOW_UNAVAILABLE = "shadow_unavailable"
    PARTIAL = "partial"
    ERROR = "error"


class RenameConfidence(StrEnum):
    """Banded rename confidence emitted to telemetry (no floats in Opik)."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


_FALLBACK_VALUES = frozenset(r.value for r in ScopedHistoryFallbackReason)
_RENAME_BANDS = frozenset(b.value for b in RenameConfidence)


def coerce_fallback_reason(value: Any) -> str:
    """Coerce unknown/empty values to the closed fallback set (default ``none``)."""
    if value is None:
        return ScopedHistoryFallbackReason.NONE.value
    text = str(value).strip().lower()
    if text in _FALLBACK_VALUES:
        return text
    return ScopedHistoryFallbackReason.NONE.value


def coerce_rename_confidence(value: Any) -> str:
    """Coerce unknown/empty values to a rename band (default ``none``)."""
    if value is None:
        return RenameConfidence.NONE.value
    text = str(value).strip().lower()
    if text in _RENAME_BANDS:
        return text
    return RenameConfidence.NONE.value


# ---------------------------------------------------------------------------
# Evidence carrier (C2)
# ---------------------------------------------------------------------------


@dataclass
class ScopedHistoryEvidence:
    """In-process evidence carrier for Phase 9 producers (never Opik-dumped)."""

    fallback_reason: str = ScopedHistoryFallbackReason.NONE.value
    split_high_confidence: bool = False
    split_rationale: str = ""
    rename_confidence: str = RenameConfidence.NONE.value
    rename_rationale: str = ""
    guidance: str | None = None
    file_to_flow_ids: dict[str, list[str]] = field(default_factory=dict)
    # Optional structural marker deltas under semantic-ON (closed vocab only).
    structural_error_handling: bool = False
    structural_public_api: bool = False
    structural_new_command: bool = False
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialise allowlisted non-content fields for metrics/result dicts."""
        return {
            "fallback_reason": coerce_fallback_reason(self.fallback_reason),
            "split_high_confidence": bool(self.split_high_confidence),
            "split_rationale": _bound_str(self.split_rationale or "", max_len=MAX_RATIONALE_LEN),
            "rename_confidence": coerce_rename_confidence(self.rename_confidence),
            "rename_rationale": _bound_str(self.rename_rationale or "", max_len=MAX_RATIONALE_LEN),
            "guidance": (
                _bound_str(self.guidance, max_len=MAX_GUIDANCE_LEN)
                if isinstance(self.guidance, str) and self.guidance
                else None
            ),
            # file_to_flow_ids stays in-process only — callers must not emit to Opik.
            "file_to_flow_ids": dict(self.file_to_flow_ids),
            "structural_error_handling": bool(self.structural_error_handling),
            "structural_public_api": bool(self.structural_public_api),
            "structural_new_command": bool(self.structural_new_command),
            "latency_ms": float(self.latency_ms or 0.0),
        }


def empty_scoped_history_evidence(*, fallback_reason: str = "none") -> ScopedHistoryEvidence:
    """Return a zero-safe evidence carrier."""
    return ScopedHistoryEvidence(fallback_reason=coerce_fallback_reason(fallback_reason))


# ---------------------------------------------------------------------------
# Flow evidence extraction
# ---------------------------------------------------------------------------


def _as_str_list(value: Any, *, max_items: int = MAX_FLOWS_PER_FILE) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple, set)):
        out: list[str] = []
        for item in value:
            if item is None:
                continue
            if isinstance(item, dict):
                for key in ("id", "flow_id", "name", "flow_name"):
                    if item.get(key) is not None:
                        text = str(item[key]).strip()
                        if text:
                            out.append(text)
                            break
            else:
                text = str(item).strip()
                if text:
                    out.append(text)
            if len(out) >= max_items:
                break
        return out[:max_items]
    return []


def extract_file_to_flow_ids(
    flows_payload: Mapping[str, Any] | None,
    *,
    staged_files: Sequence[str] | None = None,
    max_files: int = MAX_FILE_FLOW_ENTRIES,
) -> dict[str, list[str]]:
    """
    Build a bounded file → flow-id map from an affected_flows payload.

    Accepts several CRG shapes (flows list with files, file_to_flows map, etc.).
    Paths not in ``staged_files`` (when provided) are dropped. Never raises.
    """
    if not isinstance(flows_payload, Mapping):
        return {}

    staged_set = {str(p) for p in staged_files} if staged_files is not None else None
    mapping: dict[str, list[str]] = {}

    def _add(path: str, flow_ids: Sequence[str]) -> None:
        path = str(path).strip()
        if not path:
            return
        if staged_set is not None and path not in staged_set:
            return
        if path not in mapping:
            if len(mapping) >= max_files:
                return
            mapping[path] = []
        existing = mapping[path]
        for fid in flow_ids:
            text = str(fid).strip()
            if text and text not in existing and len(existing) < MAX_FLOWS_PER_FILE:
                existing.append(text)

    # Shape A: explicit file → flows map.
    for key in ("file_to_flows", "file_to_flow_ids", "files_to_flows"):
        raw = flows_payload.get(key)
        if isinstance(raw, Mapping):
            for path, flows in raw.items():
                _add(str(path), _as_str_list(flows))

    # Shape B: list of flow objects with file membership.
    flows_list = flows_payload.get("flows") or flows_payload.get("affected_flows") or flows_payload.get("items")
    if isinstance(flows_list, list):
        for flow in flows_list:
            if not isinstance(flow, Mapping):
                continue
            flow_id = None
            for key in ("id", "flow_id", "name", "flow_name"):
                if flow.get(key) is not None:
                    flow_id = str(flow[key]).strip()
                    break
            if not flow_id:
                continue
            files = (
                flow.get("files")
                or flow.get("changed_files")
                or flow.get("paths")
                or flow.get("file_paths")
                or flow.get("members")
                or []
            )
            for path in _as_str_list(files, max_items=max_files):
                _add(path, [flow_id])

    # Shape C: per-file entries under "files".
    files_block = flows_payload.get("files")
    if isinstance(files_block, list):
        for entry in files_block:
            if not isinstance(entry, Mapping):
                continue
            path = entry.get("path") or entry.get("file") or entry.get("name")
            if path is None:
                continue
            flows = entry.get("flows") or entry.get("flow_ids") or entry.get("affected_flows") or []
            _add(str(path), _as_str_list(flows))
    elif isinstance(files_block, Mapping):
        for path, flows in files_block.items():
            _add(str(path), _as_str_list(flows))

    return mapping


def evaluate_split_evidence(
    file_to_flow_ids: Mapping[str, Sequence[str]] | None,
    *,
    staged_files: Sequence[str] | None = None,
    preflight_groups_count: int = 0,
) -> tuple[bool, str]:
    """
    Flow-first split evidence (Option A close-bar).

    High confidence only when staged files partition into ≥2 groups whose flow
    sets share **no** flow identity. A single flow spanning all staged files is
    the negative case. Preflight multi-group elevates confidence when already
    present (does not run preflight).
    """
    if preflight_groups_count and int(preflight_groups_count) > 1:
        return True, _bound_str(
            f"preflight_groups_count={int(preflight_groups_count)} indicates multiple natural partitions",
            max_len=MAX_RATIONALE_LEN,
        )

    if not file_to_flow_ids:
        return False, ""

    staged = [str(p) for p in (staged_files or list(file_to_flow_ids.keys())) if p]
    if len(staged) < 2:
        return False, ""

    # Restrict to staged files that have at least one flow id.
    membership: dict[str, frozenset[str]] = {}
    for path in staged:
        flows = file_to_flow_ids.get(path) or file_to_flow_ids.get(str(path))
        if not flows:
            continue
        ids = frozenset(str(f).strip() for f in flows if str(f).strip())
        if ids:
            membership[path] = ids

    if len(membership) < 2:
        return False, ""

    # Union-find over files that share any flow identity.
    parent: dict[str, str] = {p: p for p in membership}

    def _find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def _union(a: str, b: str) -> None:
        ra, rb = _find(a), _find(b)
        if ra != rb:
            parent[rb] = ra

    paths = list(membership.keys())
    for i, left in enumerate(paths):
        for right in paths[i + 1 :]:
            if membership[left] & membership[right]:
                _union(left, right)

    components: dict[str, list[str]] = {}
    for path in paths:
        root = _find(path)
        components.setdefault(root, []).append(path)

    if len(components) < 2:
        return False, _bound_str(
            "staged files share flow membership (single connected component)",
            max_len=MAX_RATIONALE_LEN,
        )

    # Confirm component flow sets are pairwise disjoint (defensive).
    component_flows = []
    for members in components.values():
        flows: set[str] = set()
        for path in members:
            flows |= set(membership[path])
        component_flows.append(frozenset(flows))

    for i, left in enumerate(component_flows):
        for right in component_flows[i + 1 :]:
            if left & right:
                return False, ""

    return True, _bound_str(
        f"flow-disjoint partition across {len(components)} groups ({len(membership)} staged files with flow evidence)",
        max_len=MAX_RATIONALE_LEN,
    )


# ---------------------------------------------------------------------------
# Rename confidence (C1)
# ---------------------------------------------------------------------------


def band_rename_pair(
    *,
    git_rename: bool,
    code_fp_match: bool | None,
    body_sim: float | None,
) -> RenameConfidence:
    """
    Map per-pair signals to a rename confidence band.

    * high — git rename AND (code_fp match OR body_sim ≥ HIGH)
    * medium — git rename without high corroboration, or strong single-signal
      (body_sim ≥ MEDIUM is documented for operators; git-rename path bands medium
      regardless of the medium threshold once high is ruled out)
    * low — weak single-signal (body_sim ≥ LOW)
    * none — no usable signal
    """
    sim = float(body_sim) if body_sim is not None else None
    strong_sim = sim is not None and sim >= RENAME_HIGH_BODY_SIMILARITY
    weak_sim = sim is not None and sim >= RENAME_LOW_BODY_SIMILARITY
    # Medium threshold is documented for operators; non-git LOW uses the LOW floor
    # (MEDIUM > LOW so medium_sim ⊆ weak_sim). Keep the constant exported below.

    if git_rename and (code_fp_match is True or strong_sim):
        return RenameConfidence.HIGH
    if git_rename:
        # Git rename without high corroboration still bands medium (not low/none).
        return RenameConfidence.MEDIUM
    if code_fp_match is True and strong_sim:
        return RenameConfidence.HIGH
    if code_fp_match is True or strong_sim:
        return RenameConfidence.MEDIUM
    if weak_sim:
        return RenameConfidence.LOW
    return RenameConfidence.NONE


_BAND_RANK = {
    RenameConfidence.NONE.value: 0,
    RenameConfidence.LOW.value: 1,
    RenameConfidence.MEDIUM.value: 2,
    RenameConfidence.HIGH.value: 3,
}


def _max_band(current: str, candidate: RenameConfidence) -> str:
    if _BAND_RANK.get(candidate.value, 0) > _BAND_RANK.get(current, 0):
        return candidate.value
    return current


def evaluate_rename_confidence(
    renamed_paths: Sequence[tuple[str, str]] | None,
    *,
    old_bytes_by_path: Mapping[str, bytes] | None = None,
    new_bytes_by_path: Mapping[str, bytes] | None = None,
    enable_semantic: bool | None = True,
) -> tuple[str, str]:
    """
    Composite rename confidence over git rename pairs + cross-path fingerprints.

    Fail-open per pair on missing blobs. Does not mutate inputs. No-op when
    semantic is disabled.
    """
    if not is_semantic_enabled(enable_semantic):
        return RenameConfidence.NONE.value, ""

    pairs = list(renamed_paths or [])[:MAX_RENAME_PAIRS]
    if not pairs:
        return RenameConfidence.NONE.value, ""

    old_map = dict(old_bytes_by_path or {})
    new_map = dict(new_bytes_by_path or {})

    best = RenameConfidence.NONE.value
    high_count = 0
    evaluated = 0

    try:
        from git_cg.fingerprints import collect_fingerprints_from_source
        from git_cg.similarity import body_similarity
    except Exception:
        # Fingerprint stack unavailable — git-rename alone → medium.
        if pairs:
            return RenameConfidence.MEDIUM.value, _bound_str(
                f"git rename pairs={len(pairs)} (fingerprint stack unavailable)",
                max_len=MAX_RATIONALE_LEN,
            )
        return RenameConfidence.NONE.value, ""

    for old_path, new_path in pairs:
        git_rename = True  # membership in renamed_paths
        old_bytes = old_map.get(old_path)
        new_bytes = new_map.get(new_path)
        code_match: bool | None = None
        sim: float | None = None

        if old_bytes is not None and new_bytes is not None:
            try:
                old_fp, _, old_err = collect_fingerprints_from_source(old_path, old_bytes)
                new_fp, _, new_err = collect_fingerprints_from_source(new_path, new_bytes)
                if old_fp is not None and new_fp is not None and not old_err and not new_err:
                    code_match = old_fp.code_fp == new_fp.code_fp
                sim = float(body_similarity(old_bytes, new_bytes))
            except Exception:
                code_match = None
                sim = None

        band = band_rename_pair(git_rename=git_rename, code_fp_match=code_match, body_sim=sim)
        evaluated += 1
        if band == RenameConfidence.HIGH:
            high_count += 1
        best = _max_band(best, band)

    if best == RenameConfidence.HIGH.value:
        rationale = f"corroborated rename pairs={high_count}/{evaluated}"
    elif best == RenameConfidence.MEDIUM.value:
        rationale = f"git rename pairs={evaluated} without full fingerprint corroboration"
    elif best == RenameConfidence.LOW.value:
        rationale = f"weak rename signal across {evaluated} pair(s)"
    else:
        rationale = ""

    return best, _bound_str(rationale, max_len=MAX_RATIONALE_LEN)


# ---------------------------------------------------------------------------
# P1 / P2 structural markers (C4)
# ---------------------------------------------------------------------------

_PY_ERROR_TYPES = frozenset(
    {
        "try_statement",
        "except_clause",
        "except_group_clause",
        "raise_statement",
        "finally_clause",
    }
)
_JS_ERROR_TYPES = frozenset(
    {
        "try_statement",
        "catch_clause",
        "finally_clause",
        "throw_statement",
    }
)
_PUBLIC_DEF_TYPES = frozenset(
    {
        "function_definition",
        "class_definition",
        "async_function_definition",
        "function_declaration",
        "class_declaration",
        "method_definition",
        "export_statement",
        "public_field_definition",
        "decorated_definition",
    }
)
_CLI_HINT_TYPES = frozenset(
    {
        "decorator",
        "call",
        "command",
    }
)
# Identifier-boundary CLI hints. Plain ``cli`` / ``command`` must not match
# substrings inside ``client`` / ``commandeer`` / ``cli_unrelated``.
_CLI_HINT_PATTERN = re.compile(
    r"(?i)(?<![A-Za-z0-9_])(?:"
    r"app\.command|add_argument|add_parser|argparse|typer|click|cli"
    r")(?![A-Za-z0-9_])"
)


def _walk_node_types(tree: Any, *, max_nodes: int = 4000) -> set[str]:
    """Collect node type names from a tree-sitter tree (bounded)."""
    root = getattr(tree, "root_node", None) or tree
    types: set[str] = set()
    stack = [root]
    seen = 0
    while stack and seen < max_nodes:
        node = stack.pop()
        seen += 1
        node_type = getattr(node, "type", None)
        if isinstance(node_type, str):
            types.add(node_type)
        children = getattr(node, "children", None)
        if children:
            stack.extend(list(children))
    return types


def _source_has_cli_hint(source: bytes) -> bool:
    """Return True when source contains a CLI identifier (boundary-anchored)."""
    text = source.decode("utf-8", errors="replace")
    return bool(_CLI_HINT_PATTERN.search(text))


def _definition_names(tree: Any, *, max_nodes: int = 4000) -> list[str]:
    """Collect definition identifier names from a tree-sitter tree (bounded)."""
    root = getattr(tree, "root_node", None) or tree
    names: list[str] = []
    stack = [root]
    seen = 0
    while stack and seen < max_nodes:
        node = stack.pop()
        seen += 1
        node_type = getattr(node, "type", None)
        if node_type in _PUBLIC_DEF_TYPES:
            name_node = None
            # tree-sitter python/js commonly expose child_by_field_name("name")
            cbf = getattr(node, "child_by_field_name", None)
            if callable(cbf):
                try:
                    name_node = cbf("name")
                except Exception:
                    name_node = None
            if name_node is None:
                for child in list(getattr(node, "children", None) or []):
                    if getattr(child, "type", None) in {"identifier", "property_identifier", "type_identifier"}:
                        name_node = child
                        break
            if name_node is not None:
                try:
                    raw = getattr(name_node, "text", None)
                    if isinstance(raw, (bytes, bytearray)):
                        names.append(raw.decode("utf-8", errors="replace"))
                    elif isinstance(raw, str):
                        names.append(raw)
                except Exception:
                    pass
        children = getattr(node, "children", None)
        if children:
            stack.extend(list(children))
    return names


def evaluate_structural_markers(
    parse_results: Sequence[Any] | None,
    *,
    enable_semantic: bool | None = True,
) -> tuple[bool, bool, bool]:
    """
    P1/P2 structural marker evidence from ParseResult.tree objects.

    Returns:
        (error_handling_added, public_api_added, new_command)
    Fail-open: returns all False on parse unavailability (lexical path remains).
    """
    if not is_semantic_enabled(enable_semantic):
        return False, False, False
    if not parse_results:
        return False, False, False

    error_handling = False
    public_api = False
    new_command = False

    for result in parse_results:
        tree = getattr(result, "tree", None)
        # Skip missing trees. Non-success parse status is tolerated when a tree is
        # present (callers may attach partial ParseResult views).
        if tree is None:
            continue
        try:
            types = _walk_node_types(tree)
        except Exception:
            continue

        if types & _PY_ERROR_TYPES or types & _JS_ERROR_TYPES:
            error_handling = True
        if types & _PUBLIC_DEF_TYPES:
            # Public API only when a non-private definition name is present.
            # Without recoverable names, fall back to "definition present".
            names = _definition_names(tree)
            if names:
                if any(not n.startswith("_") for n in names):
                    public_api = True
            else:
                public_api = True
        if types & _CLI_HINT_TYPES:
            # Require a lexical CLI hint in addition to structural call/decorator nodes.
            source = getattr(result, "source", None)
            if isinstance(source, (bytes, bytearray)) and _source_has_cli_hint(bytes(source)):
                new_command = True

    return error_handling, public_api, new_command


def structural_markers_from_sources(
    files: Mapping[str, bytes] | None,
    *,
    enable_semantic: bool | None = True,
    parse_results: Sequence[Any] | None = None,
) -> tuple[bool, bool, bool]:
    """Derive P1/P2 structural markers from staged sources (fail-open).

    When ``parse_results`` is provided (e.g. reused parser-stage batch results),
    skip a second ``parse_files`` call. Otherwise parse ``files`` once.
    """
    if not is_semantic_enabled(enable_semantic):
        return False, False, False

    file_map = dict(files or {})
    raw_results = list(parse_results) if parse_results is not None else None

    if raw_results is None:
        if not file_map:
            return False, False, False
        try:
            from git_cg.ast_parser import parse_files
        except Exception:
            return False, False, False
        try:
            batch = parse_files(file_map)
        except Exception:
            return False, False, False
        # Fail-open when parser stub/batch lacks results (tests or degraded parser).
        raw_results = getattr(batch, "results", None)
        if raw_results is None:
            return False, False, False

    # Attach source bytes onto results for CLI hint / name checks (in-memory only).
    enriched = []
    for result in raw_results:
        try:
            # ParseResult is frozen — build a lightweight view.
            view = SimpleNamespace(
                tree=getattr(result, "tree", None),
                status=getattr(result, "status", None),
                path=getattr(result, "path", None),
                source=file_map.get(getattr(result, "path", None)) if file_map else getattr(result, "source", None),
            )
            # Prefer already-attached source when file_map miss.
            if view.source is None:
                view.source = getattr(result, "source", None)
            enriched.append(view)
        except Exception:
            enriched.append(result)
    return evaluate_structural_markers(enriched, enable_semantic=True)


# ---------------------------------------------------------------------------
# Guidance (C3) + OR-merge
# ---------------------------------------------------------------------------


def build_scoped_history_guidance(
    *,
    split_high_confidence: bool,
    split_rationale: str = "",
    rename_confidence: str = "none",
    rename_rationale: str = "",
) -> str | None:
    """
    Build directive-free Channel-4 guidance text.

    Must never mention preferred_type / authority field overrides.
    """
    parts: list[str] = []
    if split_high_confidence:
        detail = split_rationale.strip() or "disjoint affected-flow membership across staged files"
        parts.append(
            f"Split evidence: {detail}. Consider whether distinct surfaces warrant secondary intents or a split."
        )
    band = coerce_rename_confidence(rename_confidence)
    if band in {RenameConfidence.HIGH.value, RenameConfidence.MEDIUM.value}:
        detail = rename_rationale.strip() or f"rename confidence band={band}"
        parts.append(f"Rename evidence: {detail}. Path changes may reflect rename or move activity.")
    if not parts:
        return None
    text = " ".join(parts)
    # Hard ban authority leakage.
    lowered = text.lower()
    for banned in ("preferred_type", "intent_id must", "override semver", "change gitmoji", "set cc_type"):
        if banned in lowered:
            return None
    return _bound_str(text, max_len=MAX_GUIDANCE_LEN)


def or_merge_split_recommended(model_value: bool, evidence_high_confidence: bool) -> bool:
    """OR-merge: evidence may force True; must never clear model True."""
    return bool(model_value) or bool(evidence_high_confidence)


def apply_scoped_history_to_plan(
    plan: Any,
    evidence: ScopedHistoryEvidence | Mapping[str, Any] | None,
) -> Any:
    """
    OR-merge split_recommended and append short rationale. Never touches authority fields.

    Returns the same plan instance (mutates advisory fields only).
    """
    if plan is None or evidence is None:
        return plan

    if isinstance(evidence, ScopedHistoryEvidence):
        split_hc = bool(evidence.split_high_confidence)
        split_rationale = evidence.split_rationale or ""
        rename_band = evidence.rename_confidence
        rename_rationale = evidence.rename_rationale or ""
    else:
        split_hc = bool(evidence.get("split_high_confidence"))
        split_rationale = str(evidence.get("split_rationale") or "")
        rename_band = coerce_rename_confidence(evidence.get("rename_confidence"))
        rename_rationale = str(evidence.get("rename_rationale") or "")

    try:
        model_split = bool(getattr(plan, "split_recommended", False))
        merged = or_merge_split_recommended(model_split, split_hc)
        if hasattr(plan, "split_recommended"):
            plan.split_recommended = merged

        notes: list[str] = []
        if split_hc and split_rationale:
            notes.append(f"scoped-history split: {split_rationale}")
        if (
            coerce_rename_confidence(rename_band)
            in {
                RenameConfidence.HIGH.value,
                RenameConfidence.MEDIUM.value,
            }
            and rename_rationale
        ):
            notes.append(f"scoped-history rename: {rename_rationale}")
        if notes and hasattr(plan, "rationale"):
            existing = str(getattr(plan, "rationale", "") or "").strip()
            addition = _bound_str("; ".join(notes), max_len=MAX_RATIONALE_LEN)
            if addition:
                plan.rationale = _bound_str(
                    f"{existing}; {addition}" if existing else addition,
                    max_len=MAX_RATIONALE_LEN * 2,
                )
    except Exception:
        return plan
    return plan


# ---------------------------------------------------------------------------
# Top-level evaluator
# ---------------------------------------------------------------------------


def evaluate_scoped_history(
    *,
    enable_semantic: bool | None,
    file_to_flow_ids: Mapping[str, Sequence[str]] | None = None,
    staged_files: Sequence[str] | None = None,
    renamed_paths: Sequence[tuple[str, str]] | None = None,
    old_bytes_by_path: Mapping[str, bytes] | None = None,
    new_bytes_by_path: Mapping[str, bytes] | None = None,
    staged_sources: Mapping[str, bytes] | None = None,
    parse_results: Sequence[Any] | None = None,
    preflight_groups_count: int = 0,
    fallback_reason: str = "none",
) -> ScopedHistoryEvidence:
    """
    Run Phase 9 producers and return a bounded evidence carrier.

    No-op (flag_off defaults) when semantic is disabled. Never raises.
    """
    t0 = time.perf_counter()
    if not is_semantic_enabled(enable_semantic):
        return empty_scoped_history_evidence(fallback_reason=ScopedHistoryFallbackReason.NONE.value)

    evidence = empty_scoped_history_evidence(fallback_reason=fallback_reason)
    try:
        # Bound retained flow map.
        bounded_map: dict[str, list[str]] = {}
        if file_to_flow_ids:
            for i, (path, flows) in enumerate(file_to_flow_ids.items()):
                if i >= MAX_FILE_FLOW_ENTRIES:
                    break
                bounded_map[str(path)] = [str(f) for f in list(flows)[:MAX_FLOWS_PER_FILE] if str(f).strip()]
        evidence.file_to_flow_ids = bounded_map

        split_hc, split_r = evaluate_split_evidence(
            bounded_map,
            staged_files=staged_files,
            preflight_groups_count=preflight_groups_count,
        )
        evidence.split_high_confidence = split_hc
        evidence.split_rationale = split_r

        rename_band, rename_r = evaluate_rename_confidence(
            renamed_paths,
            old_bytes_by_path=old_bytes_by_path,
            new_bytes_by_path=new_bytes_by_path,
            enable_semantic=True,
        )
        evidence.rename_confidence = rename_band
        evidence.rename_rationale = rename_r

        err_h, pub_api, new_cmd = structural_markers_from_sources(
            staged_sources,
            enable_semantic=True,
            parse_results=parse_results,
        )
        evidence.structural_error_handling = err_h
        evidence.structural_public_api = pub_api
        evidence.structural_new_command = new_cmd

        evidence.guidance = build_scoped_history_guidance(
            split_high_confidence=split_hc,
            split_rationale=split_r,
            rename_confidence=rename_band,
            rename_rationale=rename_r,
        )
        evidence.fallback_reason = coerce_fallback_reason(fallback_reason)
    except Exception:
        evidence.fallback_reason = ScopedHistoryFallbackReason.ERROR.value
    finally:
        evidence.latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)
    return evidence


def evidence_from_metrics_dict(metrics: Mapping[str, Any] | None) -> ScopedHistoryEvidence:
    """Rehydrate a ScopedHistoryEvidence from a metrics/result dict."""
    if not isinstance(metrics, Mapping):
        return empty_scoped_history_evidence()
    raw = metrics.get("scoped_history_evidence")
    if isinstance(raw, ScopedHistoryEvidence):
        return raw
    if not isinstance(raw, Mapping):
        # Flat keys on metrics.
        raw = metrics
    file_map = raw.get("file_to_flow_ids") if isinstance(raw.get("file_to_flow_ids"), dict) else {}
    return ScopedHistoryEvidence(
        fallback_reason=coerce_fallback_reason(raw.get("fallback_reason") or raw.get("scoped_history_fallback_reason")),
        split_high_confidence=bool(raw.get("split_high_confidence")),
        split_rationale=str(raw.get("split_rationale") or ""),
        rename_confidence=coerce_rename_confidence(raw.get("rename_confidence")),
        rename_rationale=str(raw.get("rename_rationale") or ""),
        guidance=raw.get("guidance") if isinstance(raw.get("guidance"), str) else raw.get("scoped_history_guidance"),
        file_to_flow_ids={str(k): [str(x) for x in (v or [])] for k, v in dict(file_map).items()},
        structural_error_handling=bool(raw.get("structural_error_handling")),
        structural_public_api=bool(raw.get("structural_public_api")),
        structural_new_command=bool(raw.get("structural_new_command")),
        latency_ms=float(raw.get("latency_ms") or raw.get("scoped_history_latency_ms") or 0.0),
    )
