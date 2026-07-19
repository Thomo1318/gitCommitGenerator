"""
Tree-sitter language registry and parse pipeline (ADR-0005 Phase 1).

Produces structured parse results and latency/coverage metrics. Does not
mutate ranking or git state. Fingerprint algebra lands in Phase 2.
"""

from __future__ import annotations

import hashlib
import mimetypes
import time
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import tree_sitter
import tree_sitter_language_pack as tslp

# Extension → tree-sitter-language-pack language id.
_LANGUAGE_BY_EXT: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".go": "go",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".rs": "rust",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "c_sharp",
    ".swift": "swift",
    ".scala": "scala",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".md": "markdown",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".sql": "sql",
}


@dataclass(frozen=True)
class ParseResult:
    """Outcome of attempting to parse a single file/blob."""

    path: str
    language: str | None
    status: str  # success | unsupported | binary | failed
    root_type: str | None = None
    error: str | None = None
    latency_ms: float = 0.0
    source_sha16: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SemanticParserMetrics:
    """Aggregate parser telemetry for a batch of files."""

    semantic_parser_enabled: bool = True
    semantic_parser_mode: str = "tree-sitter"
    semantic_languages_requested: list[str] = field(default_factory=list)
    semantic_languages_parsed: list[str] = field(default_factory=list)
    semantic_files_total: int = 0
    semantic_files_parsed: int = 0
    semantic_files_failed: int = 0
    semantic_files_unsupported: int = 0
    semantic_files_binary: int = 0
    semantic_fallback_reasons: list[str] = field(default_factory=list)
    parser_latency_ms: float = 0.0
    semantic_summary_hash: str = ""
    semantic_summary_chars: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ParseBatch:
    """Batch parse output: per-file results + aggregate metrics."""

    results: list[ParseResult] = field(default_factory=list)
    metrics: SemanticParserMetrics = field(default_factory=SemanticParserMetrics)

    def to_dict(self) -> dict[str, Any]:
        return {
            "results": [r.to_dict() for r in self.results],
            "metrics": self.metrics.to_dict(),
        }


def language_for_path(path: str | Path) -> str | None:
    """Map a file path to a tree-sitter language id, if known."""
    ext = Path(path).suffix.lower()
    return _LANGUAGE_BY_EXT.get(ext)


def is_probably_binary(path: str | Path, source: bytes | None = None) -> bool:
    """
    Heuristic binary detection via mimetypes and optional NUL-byte scan.

    Returns:
        True when the path/content should be skipped by the text parser.
    """
    mime, _ = mimetypes.guess_type(str(path))
    if (
        mime
        and not mime.startswith("text/")
        and mime
        not in {
            "application/json",
            "application/xml",
            "application/javascript",
            "application/x-sh",
            "application/x-python",
            "application/toml",
            "application/sql",
        }
    ):
        # Common source-ish exceptions already covered; treat image/audio/etc as binary.
        if mime.split("/", 1)[0] in {"image", "audio", "video", "font"}:
            return True
        if mime in {"application/octet-stream", "application/zip", "application/gzip", "application/pdf"}:
            return True

    return source is not None and b"\x00" in source[:8192]


@lru_cache(maxsize=64)
def get_parser_for(language: str) -> tree_sitter.Parser:
    """
    Return a cached tree-sitter Parser for ``language``.

    Raises:
        Exception: Propagates language-pack errors for unknown/broken grammars.
    """
    # Pack API annotates language_name as a closed Literal; registry values are str.
    return tslp.get_parser(cast(Any, language))


def _source_sha16(source: bytes) -> str:
    return hashlib.sha256(source).hexdigest()[:16]


def parse_source(
    path: str,
    source: bytes,
    *,
    language: str | None = None,
) -> ParseResult:
    """
    Parse a single source blob with tree-sitter.

    Status values:
    - ``binary``: skipped as non-text
    - ``unsupported``: no language mapping
    - ``failed``: grammar/parse error
    - ``success``: root node available
    """
    started = time.perf_counter()

    if is_probably_binary(path, source):
        return ParseResult(
            path=path,
            language=None,
            status="binary",
            latency_ms=(time.perf_counter() - started) * 1000.0,
        )

    lang = language or language_for_path(path)
    if not lang:
        return ParseResult(
            path=path,
            language=None,
            status="unsupported",
            error="no language mapping for extension",
            latency_ms=(time.perf_counter() - started) * 1000.0,
            source_sha16=_source_sha16(source),
        )

    try:
        parser = get_parser_for(lang)
        tree = parser.parse(source)
        root = tree.root_node
        # tree-sitter may still produce a root with ERROR children; treat has_error as failed.
        if getattr(root, "has_error", False):
            return ParseResult(
                path=path,
                language=lang,
                status="failed",
                root_type=getattr(root, "type", None),
                error="parse tree contains errors",
                latency_ms=(time.perf_counter() - started) * 1000.0,
                source_sha16=_source_sha16(source),
            )
        return ParseResult(
            path=path,
            language=lang,
            status="success",
            root_type=getattr(root, "type", None),
            latency_ms=(time.perf_counter() - started) * 1000.0,
            source_sha16=_source_sha16(source),
        )
    except Exception as exc:
        return ParseResult(
            path=path,
            language=lang,
            status="failed",
            error=f"{type(exc).__name__}: {exc}",
            latency_ms=(time.perf_counter() - started) * 1000.0,
            source_sha16=_source_sha16(source),
        )


def parse_files(files: dict[str, bytes]) -> ParseBatch:
    """
    Parse a mapping of repo-relative path → source bytes.

    Never raises for individual file failures; aggregates metrics instead.
    """
    batch = ParseBatch()
    metrics = batch.metrics
    metrics.semantic_files_total = len(files)

    requested: set[str] = set()
    parsed: set[str] = set()
    fallback_reasons: list[str] = []
    summary_parts: list[str] = []
    total_latency = 0.0

    for path, source in sorted(files.items()):
        result = parse_source(path, source)
        batch.results.append(result)
        total_latency += result.latency_ms

        if result.language:
            requested.add(result.language)

        if result.status == "success":
            metrics.semantic_files_parsed += 1
            if result.language:
                parsed.add(result.language)
            summary_parts.append(f"{path}:{result.language}:{result.root_type}:{result.source_sha16}")
        elif result.status == "unsupported":
            metrics.semantic_files_unsupported += 1
            reason = f"unsupported:{path}"
            fallback_reasons.append(reason)
            summary_parts.append(f"{path}:unsupported")
        elif result.status == "binary":
            metrics.semantic_files_binary += 1
            fallback_reasons.append(f"binary:{path}")
            summary_parts.append(f"{path}:binary")
        else:
            metrics.semantic_files_failed += 1
            reason = f"failed:{path}:{result.error or 'unknown'}"
            fallback_reasons.append(reason)
            summary_parts.append(f"{path}:failed")

    metrics.semantic_languages_requested = sorted(requested)
    metrics.semantic_languages_parsed = sorted(parsed)
    metrics.semantic_fallback_reasons = fallback_reasons
    metrics.parser_latency_ms = round(total_latency, 3)

    summary = "\n".join(summary_parts)
    metrics.semantic_summary_chars = len(summary)
    metrics.semantic_summary_hash = hashlib.sha256(summary.encode()).hexdigest()[:16] if summary else ""

    return batch


def empty_parser_metrics(*, enabled: bool = False) -> dict[str, Any]:
    """Return a zeroed metrics dict for flag-off / skipped semantic runs."""
    metrics = SemanticParserMetrics(
        semantic_parser_enabled=enabled, semantic_parser_mode="disabled" if not enabled else "tree-sitter"
    )
    return metrics.to_dict()
