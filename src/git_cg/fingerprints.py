"""
Three-fingerprint algebra (shape / code / text) — ADR-0005 Phase 2 / Issue #160.

Pure evidence producers. No ranking side effects. Property-testable (#167).

Invariants (unit-tested here; Hypothesis in #167):
* deterministic + idempotent on the same (tree, source)
* stable pre-order serialization
* comment-only edit preserves shape_fp + code_fp
* pure identifier/literal text change preserves shape_fp, changes code_fp
* equal inputs => equal triples
"""

from __future__ import annotations

import hashlib
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

import tree_sitter
import tree_sitter_language_pack as tslp

from git_cg.ast_parser import ParseStatus, get_parser_for, language_for_path, parse_source
from git_cg.similarity import FORMATTING_BODY_SIMILARITY_THRESHOLD, body_similarity

# Leaf kinds whose text participates in code_fp / text_fp.
LEAF_TEXT_KINDS: frozenset[str] = frozenset(
    {
        "identifier",
        "string",
        "integer",
        "float",
        "operator",
        "true",
        "false",
        "none",
        "type_identifier",
        "property_identifier",
        "field_identifier",
    }
)

COMMENT_KINDS: frozenset[str] = frozenset(
    {
        "comment",
        "line_comment",
        "block_comment",
    }
)

# Soft guard against pathological trees (metrics skip, not crash).
DEFAULT_MAX_NODES = 200_000


class FingerprintClass(StrEnum):
    """Classification of a paired HEAD vs index comparison."""

    NOOP = "noop"
    COMMENTS_ONLY = "comments_only"
    IDENTIFIER_OR_LITERAL_ONLY = "identifier_or_literal_only"
    FORMATTING_ONLY = "formatting_only"
    STRUCTURAL = "structural"
    INCONSISTENT = "inconsistent"
    ADD_ONLY = "add_only"
    DELETE_ONLY = "delete_only"
    UNPARSED = "unparsed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class FingerprintTriple:
    """shape / code / text short hashes for one syntax tree."""

    shape_fp: str
    code_fp: str
    text_fp: str


@dataclass(frozen=True)
class FileFingerprintResult:
    """Per-path fingerprint comparison outcome (non-content)."""

    path: str
    classification: FingerprintClass
    markers: tuple[str, ...] = ()
    body_similarity: float | None = None
    baseline_fps: FingerprintTriple | None = None
    staged_fps: FingerprintTriple | None = None
    reason: str | None = None
    language: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["classification"] = str(self.classification)
        if self.baseline_fps is not None:
            payload["baseline_fps"] = asdict(self.baseline_fps)
        if self.staged_fps is not None:
            payload["staged_fps"] = asdict(self.staged_fps)
        return payload


@dataclass
class FingerprintBatchMetrics:
    """Aggregate fingerprint telemetry (safe for Opik allowlists)."""

    fingerprint_files_compared: int = 0
    fingerprint_latency_ms: float = 0.0
    body_similarity_min: float | None = None
    body_similarity_avg: float | None = None
    grammar_version: str = "unknown"
    class_counts: dict[str, int] = field(default_factory=dict)
    markers: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FingerprintBatch:
    """Batch compare output."""

    results: list[FileFingerprintResult] = field(default_factory=list)
    metrics: FingerprintBatchMetrics = field(default_factory=FingerprintBatchMetrics)

    def to_dict(self) -> dict[str, Any]:
        return {
            "results": [r.to_dict() for r in self.results],
            "metrics": self.metrics.to_dict(),
        }


def grammar_version() -> str:
    """Return a stable-ish grammar pack identity for metrics/cache invalidation."""
    version = getattr(tslp, "__version__", None) or getattr(tslp, "VERSION", None)
    if version:
        return f"tree-sitter-language-pack=={version}"
    return f"tree-sitter-language-pack@{getattr(tslp, '__file__', 'unknown')}"


def _sha16(parts: list[str]) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def collect_fingerprints(
    root: tree_sitter.Node,
    source: bytes,
    *,
    max_nodes: int = DEFAULT_MAX_NODES,
) -> FingerprintTriple:
    """
    Compute shape_fp, code_fp, text_fp for a syntax tree.

    shape_fp: node-type tuple only, comments dropped.        -> structure
    code_fp : shape_fp + leaf text for identifiers/literals. -> identifier-sensitive
    text_fp : code_fp + comment node text.                   -> full text-sensitive
    """
    shape: list[str] = []
    code: list[str] = []
    text: list[str] = []
    nodes_seen = 0

    stack: list[tree_sitter.Node] = [root]
    while stack:
        node = stack.pop()
        nodes_seen += 1
        if nodes_seen > max_nodes:
            # Deterministic overflow marker rather than partial silent hashes.
            overflow = f"overflow:{max_nodes}"
            return FingerprintTriple(
                shape_fp=_sha16([overflow, "shape"]),
                code_fp=_sha16([overflow, "code"]),
                text_fp=_sha16([overflow, "text"]),
            )

        node_type = node.type
        is_comment = node_type in COMMENT_KINDS

        if not is_comment:
            shape.append(node_type)
            code.append(node_type)
        text.append(node_type)

        child_count = int(getattr(node, "child_count", 0) or 0)
        if child_count == 0:
            snippet = source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")
            if is_comment:
                text.append(f"#{snippet}")
            elif node_type in LEAF_TEXT_KINDS:
                code.append(f"`{snippet}`")
                text.append(f"`{snippet}`")
        else:
            # Pre-order with children pushed right-to-left => left-to-right visit.
            children = list(node.children)
            stack.extend(reversed(children))

    return FingerprintTriple(shape_fp=_sha16(shape), code_fp=_sha16(code), text_fp=_sha16(text))


def collect_fingerprints_from_source(
    path: str,
    source: bytes,
    *,
    language: str | None = None,
    max_nodes: int = DEFAULT_MAX_NODES,
) -> tuple[FingerprintTriple | None, str | None, str | None]:
    """
    Parse ``source`` and collect fingerprints.

    Returns:
        (triple_or_none, language_or_none, error_or_none)
    """
    parsed = parse_source(path, source, language=language)
    if parsed.status != ParseStatus.SUCCESS:
        return None, parsed.language, parsed.error or str(parsed.status)

    lang = parsed.language or language or language_for_path(path)
    if not lang:
        return None, None, "no language"

    try:
        parser = get_parser_for(lang)
        tree = parser.parse(source)
        root = tree.root_node
        if getattr(root, "has_error", False):
            return None, lang, "parse tree contains errors"
        return collect_fingerprints(root, source, max_nodes=max_nodes), lang, None
    except Exception as exc:  # pragma: no cover - defensive
        return None, lang, f"{type(exc).__name__}:{exc}"


def classify_fingerprint_equality(
    *,
    shape_eq: bool,
    code_eq: bool,
    text_eq: bool,
    similarity: float | None = None,
    formatting_threshold: float = FORMATTING_BODY_SIMILARITY_THRESHOLD,
) -> tuple[FingerprintClass, tuple[str, ...]]:
    """
    Map an equality triple (+ optional body similarity) to class + markers.

    Complete truth table including anomaly cells.
    """
    if shape_eq and code_eq and text_eq:
        return FingerprintClass.NOOP, ()

    if shape_eq and code_eq and not text_eq:
        return FingerprintClass.COMMENTS_ONLY, ("comments_only",)

    if shape_eq and (not code_eq) and (not text_eq):
        if similarity is not None and similarity > formatting_threshold:
            return FingerprintClass.FORMATTING_ONLY, ("formatting_only", "whitespace_or_style_cleanup")
        if similarity is not None and similarity >= 0.0:
            return FingerprintClass.IDENTIFIER_OR_LITERAL_ONLY, (
                "identifier_or_literal_only",
                "runtime_logic_changed",
            )
        return FingerprintClass.IDENTIFIER_OR_LITERAL_ONLY, ("identifier_or_literal_only",)

    if shape_eq and (not code_eq) and text_eq:
        return FingerprintClass.INCONSISTENT, ("fingerprint_inconsistent",)

    if (not shape_eq) and code_eq:
        # Structural-ish inconsistency (shape changed but code hash matched).
        return FingerprintClass.INCONSISTENT, ("fingerprint_inconsistent", "runtime_logic_changed")

    if (not shape_eq) and (not code_eq) and text_eq:
        return FingerprintClass.INCONSISTENT, ("fingerprint_inconsistent",)

    # shape differs, code differs, text differs (or remaining structural cases)
    return FingerprintClass.STRUCTURAL, ("runtime_logic_changed",)


def compare_file_fingerprints(
    path: str,
    *,
    baseline_source: bytes | None,
    staged_source: bytes | None,
    max_nodes: int = DEFAULT_MAX_NODES,
    compute_similarity: bool = True,
) -> FileFingerprintResult:
    """Compare one path's HEAD vs index sources and classify the change."""
    if baseline_source is None and staged_source is None:
        return FileFingerprintResult(
            path=path,
            classification=FingerprintClass.SKIPPED,
            reason="both_missing",
        )
    if baseline_source is None and staged_source is not None:
        return FileFingerprintResult(
            path=path,
            classification=FingerprintClass.ADD_ONLY,
            markers=("files_added",),
            reason="add_only",
        )
    if baseline_source is not None and staged_source is None:
        return FileFingerprintResult(
            path=path,
            classification=FingerprintClass.DELETE_ONLY,
            markers=("files_deleted",),
            reason="delete_only",
        )

    assert baseline_source is not None and staged_source is not None

    base_fp, base_lang, base_err = collect_fingerprints_from_source(path, baseline_source, max_nodes=max_nodes)
    staged_fp, staged_lang, staged_err = collect_fingerprints_from_source(path, staged_source, max_nodes=max_nodes)
    language = staged_lang or base_lang

    if base_fp is None or staged_fp is None:
        reason_parts = []
        if base_err:
            reason_parts.append(f"baseline:{base_err}")
        if staged_err:
            reason_parts.append(f"staged:{staged_err}")
        return FileFingerprintResult(
            path=path,
            classification=FingerprintClass.UNPARSED,
            reason=";".join(reason_parts) or "unparsed",
            language=language,
        )

    shape_eq = base_fp.shape_fp == staged_fp.shape_fp
    code_eq = base_fp.code_fp == staged_fp.code_fp
    text_eq = base_fp.text_fp == staged_fp.text_fp

    sim: float | None = None
    # Similarity is only required for the shape✓ code✗ text✗ gate, but we also
    # compute it for non-noop paired parses to populate telemetry min/avg.
    if compute_similarity and not (shape_eq and code_eq and text_eq):
        try:
            sim = body_similarity(baseline_source, staged_source)
        except Exception as exc:  # pragma: no cover - defensive
            return FileFingerprintResult(
                path=path,
                classification=FingerprintClass.SKIPPED,
                reason=f"similarity_error:{type(exc).__name__}",
                baseline_fps=base_fp,
                staged_fps=staged_fp,
                language=language,
            )

    classification, markers = classify_fingerprint_equality(
        shape_eq=shape_eq,
        code_eq=code_eq,
        text_eq=text_eq,
        similarity=sim,
    )
    return FileFingerprintResult(
        path=path,
        classification=classification,
        markers=markers,
        body_similarity=sim,
        baseline_fps=base_fp,
        staged_fps=staged_fp,
        language=language,
    )


def compare_fingerprint_sets(
    *,
    baseline_files: dict[str, bytes],
    staged_files: dict[str, bytes],
    max_nodes: int = DEFAULT_MAX_NODES,
    compute_similarity: bool = True,
) -> FingerprintBatch:
    """
    Pair HEAD/index path sets and classify each path.

    Paths only in staged => add_only; only in baseline => delete_only;
    in both => fingerprint compare. Never raises for individual failures.
    """
    started = time.perf_counter()
    batch = FingerprintBatch()
    batch.metrics.grammar_version = grammar_version()

    all_paths = sorted(set(baseline_files) | set(staged_files))
    similarities: list[float] = []
    marker_set: set[str] = set()
    counts: Counter[str] = Counter()

    for path in all_paths:
        result = compare_file_fingerprints(
            path,
            baseline_source=baseline_files.get(path),
            staged_source=staged_files.get(path),
            max_nodes=max_nodes,
            compute_similarity=compute_similarity,
        )
        batch.results.append(result)
        counts[str(result.classification)] += 1
        marker_set.update(result.markers)
        if result.reason:
            batch.metrics.reasons.append(f"{path}:{result.reason}")
        if result.body_similarity is not None:
            similarities.append(result.body_similarity)
        if result.classification not in {
            FingerprintClass.ADD_ONLY,
            FingerprintClass.DELETE_ONLY,
            FingerprintClass.SKIPPED,
        }:
            # Count attempted compares including unparsed/inconsistent/etc.
            batch.metrics.fingerprint_files_compared += 1

    batch.metrics.class_counts = dict(sorted(counts.items()))
    batch.metrics.markers = sorted(marker_set)
    if similarities:
        batch.metrics.body_similarity_min = round(min(similarities), 6)
        batch.metrics.body_similarity_avg = round(sum(similarities) / len(similarities), 6)
    batch.metrics.fingerprint_latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
    # Cap reason list for telemetry safety/size.
    batch.metrics.reasons = batch.metrics.reasons[:100]
    return batch


def empty_fingerprint_metrics() -> dict[str, Any]:
    """Zeroed fingerprint metrics for flag-off / skipped runs."""
    return FingerprintBatchMetrics(
        class_counts={},
        grammar_version=grammar_version(),
    ).to_dict()
