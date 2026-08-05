"""Deterministic diff signal extraction for git-cg intent ranking.

This module is the foundation for ranking SOP matrix rows before prompting the
LLM. It does not call the model and does not decide the final commit message.

Design goals:
    * Extract cheap, deterministic signals from staged diff text and file paths.
    * Keep signals explicit and testable.
    * Provide evidence strings that can later be shown to the LLM or used in
      golden-diff tests.
    * Keep marker accumulation flat and additive (multiple markers may coexist).
    * Allow optional Phase 1/2 facts as closed-vocabulary marker enrichment only
      when semantic mode is enabled — never write ``semver_impact`` here.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, Field

from git_cg.semantic_flags import is_semantic_enabled


class DiffSignals(BaseModel):
    """Deterministic signals extracted from a staged git diff."""

    has_breaking_change: bool = False

    touches_security: bool = False
    touches_tests: bool = False
    touches_docs: bool = False
    touches_ci: bool = False
    touches_build: bool = False
    touches_hooks: bool = False
    touches_config: bool = False
    touches_release: bool = False

    moves_or_renames_files: bool = False
    deletes_files: bool = False
    adds_files: bool = False

    adds_public_api: bool = False
    changes_architecture: bool = False

    only_docs: bool = False
    only_tests: bool = False
    only_formatting: bool = False
    only_dependency_changes: bool = False
    only_config: bool = False

    new_shared_module: bool = False
    removed_duplicate_logic: bool = False
    centralized_config_resolution: bool = False
    hook_portability: bool = False
    resource_moves: bool = False

    dependency_added: bool = False
    dependency_removed: bool = False
    dependency_upgraded: bool = False
    dependency_downgraded: bool = False
    package_metadata_changed: bool = False
    packaged_data_changed: bool = False

    validation_added: bool = False
    error_handling_added: bool = False
    logging_changed: bool = False
    secrets_management_changed: bool = False
    secret_scanning_changed: bool = False

    evidence: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)

    lines_added: int = 0
    lines_removed: int = 0
    files_changed_count: int = 0


class DiffFileSummary(BaseModel):
    """File-level summary extracted from git diff metadata."""

    paths: list[str] = Field(default_factory=list)
    added_paths: list[str] = Field(default_factory=list)
    deleted_paths: list[str] = Field(default_factory=list)
    renamed_paths: list[tuple[str, str]] = Field(default_factory=list)


_DOC_EXTENSIONS = {
    ".md",
    ".mdx",
    ".rst",
    ".txt",
    ".adoc",
}

_TEST_PATH_PARTS = {
    "test",
    "tests",
    "spec",
    "specs",
    "__tests__",
}

_CI_PATH_PREFIXES = (
    ".github/",
    ".gitlab/",
    ".circleci/",
    ".buildkite/",
    "azure-pipelines",
)

_BUILD_FILES = {
    "pyproject.toml",
    "uv.lock",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "mise.toml",
    "Brewfile",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
}

_RELEASE_FILES = {
    "CHANGELOG.md",
    "VERSION",
    "package.json",
    "pyproject.toml",
}

_CONFIG_EXTENSIONS = {
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".pkl",
    ".kdl",
    ".ini",
    ".cfg",
    ".conf",
}

_SECURITY_PATH_PARTS = {
    "security",
    "secrets",
    "secret",
    "auth",
    "authn",
    "authz",
    "permission",
    "permissions",
    "credential",
    "credentials",
}

_HOOK_PATH_PARTS = {
    "hooks",
    ".git",
    "hk.pkl",
    "pre-commit",
    "prepare-commit-msg",
    "commit-msg",
}

_DEPENDENCY_FILES = {
    "pyproject.toml",
    "uv.lock",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
}

_ARCHITECTURE_TERMS = (
    "architecture",
    "architectural",
    "subsystem",
    "orchestrator",
    "registry",
    "loader",
    "resolver",
    "adapter",
    "strategy",
    "pipeline",
)

_VALIDATION_TERMS = (
    "validate",
    "validation",
    "validator",
    "schema",
    "guard",
    "safety",
    "strict",
)

_ERROR_HANDLING_TERMS = (
    "try:",
    "except ",
    "raise ",
    "fallback",
    "recover",
    "timeout",
    "error handling",
)

_LOGGING_TERMS = (
    "console.log",
    "console.print",
    "logger.",
    "logging.",
    "log.",
    "debug",
    "trace",
)

_SECRET_SCANNING_TERMS = (
    "gitleaks",
    "trufflehog",
    "secret scanning",
    "secret scanner",
)

_SECRETS_MANAGEMENT_TERMS = (
    "1password",
    "op ",
    "op_",
    "fnox",
    "age",
    "secret",
    "secrets",
    "credential",
    "token",
)

_PUBLIC_API_PATTERNS = (
    r"^\+\s*def\s+[a-zA-Z_][a-zA-Z0-9_]*\(",
    r"^\+\s*class\s+[a-zA-Z_][a-zA-Z0-9_]*",
    r"^\+\s*@app\.command",
    r"^\+\s*app\s*=",
)


def _normalize_diff_for_content_matching(diff_output: str) -> str:
    def _normalize_line(line: str) -> str:
        if line.startswith(("diff --git ", "index ", "+++", "---")):
            return ""
        if line.startswith(("+a/", "-a/", "+b/", "-b/")):
            return line[0] + line[3:]
        return line

    normalized = (_normalize_line(line) for line in diff_output.splitlines())
    return "\n".join(filter(None, normalized))


def extract_diff_signals(diff_output: str) -> DiffSignals:
    """Extract deterministic signals from staged diff output.

    Args:
        diff_output: Staged diff text, ideally from `git diff --cached` or rtk.

    Returns:
        DiffSignals with booleans, touched files, and evidence messages.
    """
    file_summary = extract_diff_file_summary(diff_output)
    paths = file_summary.paths

    # Normalize diff to prevent false positives from metadata lines (like file paths)
    normalized_diff = _normalize_diff_for_content_matching(diff_output)
    lowered_diff = normalized_diff.lower()

    signals = DiffSignals(files=paths)

    _apply_file_signals(signals, file_summary)
    _apply_content_signals(signals, diff_output, lowered_diff)
    _apply_only_signals(signals, paths)
    _apply_diff_metrics(signals, diff_output)

    return signals


def extract_diff_file_summary(diff_output: str) -> DiffFileSummary:
    """Extract touched, added, deleted, and renamed paths from git diff text."""
    paths: list[str] = []
    added_paths: list[str] = []
    deleted_paths: list[str] = []
    renamed_from: str | None = None
    renamed_paths: list[tuple[str, str]] = []

    for line in diff_output.splitlines():
        if line.startswith("diff --git "):
            parsed = _parse_diff_git_paths(line)
            if parsed:
                old_path, new_path = parsed
                _append_unique(paths, new_path)
                if old_path != new_path:
                    renamed_paths.append((old_path, new_path))
            continue

        if line.startswith("new file mode "):
            if paths:
                _append_unique(added_paths, paths[-1])
            continue

        if line.startswith("deleted file mode "):
            if paths:
                _append_unique(deleted_paths, paths[-1])
            continue

        if line.startswith("rename from "):
            renamed_from = line.removeprefix("rename from ").strip()
            continue

        if line.startswith("rename to ") and renamed_from:
            renamed_to = line.removeprefix("rename to ").strip()
            renamed_paths.append((renamed_from, renamed_to))
            _append_unique(paths, renamed_to)
            renamed_from = None
            continue

        if line.startswith("+++ b/"):
            path = line.removeprefix("+++ b/").strip()
            if path != "/dev/null":
                _append_unique(paths, path)
            continue

        if line.startswith("--- a/"):
            path = line.removeprefix("--- a/").strip()
            if path != "/dev/null":
                _append_unique(paths, path)

    return DiffFileSummary(
        paths=paths,
        added_paths=added_paths,
        deleted_paths=deleted_paths,
        renamed_paths=renamed_paths,
    )


def _apply_file_signals(signals: DiffSignals, file_summary: DiffFileSummary) -> None:
    paths = file_summary.paths

    if file_summary.added_paths:
        signals.adds_files = True
        signals.evidence.append(f"Added files: {', '.join(file_summary.added_paths[:5])}")

    if file_summary.deleted_paths:
        signals.deletes_files = True
        signals.evidence.append(f"Deleted files: {', '.join(file_summary.deleted_paths[:5])}")

    if file_summary.renamed_paths:
        signals.moves_or_renames_files = True
        signals.resource_moves = True
        rendered = [f"{old} -> {new}" for old, new in file_summary.renamed_paths[:5]]
        signals.evidence.append(f"Renamed or moved paths: {', '.join(rendered)}")

    if any(_is_docs_path(path) for path in paths):
        signals.touches_docs = True
        signals.evidence.append("Documentation files changed")

    if any(_is_test_path(path) for path in paths):
        signals.touches_tests = True
        signals.evidence.append("Test files changed")

    if any(_is_ci_path(path) for path in paths):
        signals.touches_ci = True
        signals.evidence.append("CI workflow files changed")

    if any(_is_build_path(path) for path in paths):
        signals.touches_build = True
        signals.evidence.append("Build/tooling files changed")

    if any(_is_hook_path(path) for path in paths):
        signals.touches_hooks = True
        signals.evidence.append("Git hook configuration or hook-adjacent files changed")

    if any(_is_config_path(path) for path in paths):
        signals.touches_config = True
        signals.evidence.append("Configuration files changed")

    if any(_is_release_path(path) for path in paths):
        signals.touches_release = True
        signals.evidence.append("Release/version metadata files changed")

    if any(_is_security_path(path) for path in paths):
        signals.touches_security = True
        signals.evidence.append("Security/auth/credential-related paths changed")

    if any(_is_dependency_path(path) for path in paths):
        signals.package_metadata_changed = True
        signals.evidence.append("Dependency or package metadata files changed")

    if any(path.startswith("src/git_cg/data/") or "git_cg/data" in path for path in paths):
        signals.packaged_data_changed = True
        signals.evidence.append("Packaged runtime data changed")

    if any(path == "config/gitops_agent_sop.json" or path == "config/gitops_sop.schema.json" for path in paths):
        signals.packaged_data_changed = True
        signals.evidence.append("SOP or SOP schema changed")


def _apply_content_signals(signals: DiffSignals, diff_output: str, lowered_diff: str) -> None:
    added_lines = [line for line in diff_output.splitlines() if line.startswith("+") and not line.startswith("+++")]

    if "breaking change:" in lowered_diff or re.search(r"^\+\s*.+!:", diff_output, flags=re.MULTILINE):
        signals.has_breaking_change = True
        signals.evidence.append("Breaking-change syntax or footer detected")

    if any(re.search(pattern, diff_output, flags=re.MULTILINE) for pattern in _PUBLIC_API_PATTERNS):
        signals.adds_public_api = True
        signals.evidence.append("Public API or CLI surface appears to be added")

    if any(term in lowered_diff for term in _ARCHITECTURE_TERMS):
        signals.changes_architecture = True
        signals.evidence.append("Architecture-related terms detected")

    if "src/git_cg/sop.py" in lowered_diff or "load_sop" in lowered_diff or "resolve_sop_path" in lowered_diff:
        signals.new_shared_module = True
        signals.centralized_config_resolution = True
        signals.evidence.append("Centralized SOP/config loader signals detected")

    if "os.getcwd()" in lowered_diff and ("load_sop" in lowered_diff or "resolve_sop_path" in lowered_diff):
        signals.removed_duplicate_logic = True
        signals.centralized_config_resolution = True
        signals.evidence.append("Duplicate cwd-based SOP resolution appears to be replaced")

    if "prepare-commit-msg" in lowered_diff or "commit_source" in lowered_diff or "--amend-regenerate" in lowered_diff:
        signals.hook_portability = True
        signals.touches_hooks = True
        signals.evidence.append("Git hook portability or hook-source handling changed")

    if any(term in lowered_diff for term in _VALIDATION_TERMS):
        signals.validation_added = True
        signals.evidence.append("Validation or safety-guard terms detected")

    if any(term in lowered_diff for term in _ERROR_HANDLING_TERMS):
        signals.error_handling_added = True
        signals.evidence.append("Error handling or fallback terms detected")

    if any(term in lowered_diff for term in _LOGGING_TERMS):
        signals.logging_changed = True
        signals.evidence.append("Logging/tracing/debug output changed")

    if any(term in lowered_diff for term in _SECRET_SCANNING_TERMS):
        signals.secret_scanning_changed = True
        signals.touches_security = True
        signals.evidence.append("Secret scanning tooling detected")

    if any(term in lowered_diff for term in _SECRETS_MANAGEMENT_TERMS):
        signals.secrets_management_changed = True
        signals.evidence.append("Secrets-management terms detected")

    if _dependency_added(added_lines):
        signals.dependency_added = True
        signals.evidence.append("Potential dependency addition detected")

    if _dependency_removed(diff_output):
        signals.dependency_removed = True
        signals.evidence.append("Potential dependency removal detected")


def _apply_only_signals(signals: DiffSignals, paths: list[str]) -> None:
    if not paths:
        return

    signals.only_docs = all(_is_docs_path(path) for path in paths)
    signals.only_tests = all(_is_test_path(path) for path in paths)
    signals.only_config = all(_is_config_path(path) for path in paths)

    dependency_paths = [_is_dependency_path(path) for path in paths]
    signals.only_dependency_changes = bool(paths) and all(dependency_paths)

    # Conservative placeholder: formatting-only detection should later use
    # a parser/formatter diff or language-aware analysis.
    signals.only_formatting = False

    if signals.only_docs:
        signals.evidence.append("All changed files are documentation files")

    if signals.only_tests:
        signals.evidence.append("All changed files are test files")

    if signals.only_dependency_changes:
        signals.evidence.append("All changed files are dependency/package metadata files")


def _parse_diff_git_paths(line: str) -> tuple[str, str] | None:
    # Expected: diff --git a/path b/path
    parts = line.split()
    if len(parts) < 4:
        return None

    old = parts[2]
    new = parts[3]

    if old.startswith("a/"):
        old = old[2:]
    if new.startswith("b/"):
        new = new[2:]

    return old, new


def _is_docs_path(path: str) -> bool:
    p = PurePosixPath(path)
    lowered = path.lower()
    return (
        p.suffix.lower() in _DOC_EXTENSIONS
        or lowered.startswith("docs/")
        or lowered.startswith("doc/")
        or lowered in {"readme.md", "changelog.md"}
    )


def _is_test_path(path: str) -> bool:
    p = PurePosixPath(path)
    parts = {part.lower() for part in p.parts}
    name = p.name.lower()
    return (
        bool(parts & _TEST_PATH_PARTS)
        or name.startswith("test_")
        or ".test." in name
        or ".spec." in name
        or name.endswith("_test.go")
    )


def _is_ci_path(path: str) -> bool:
    lowered = path.lower()
    return lowered.startswith(_CI_PATH_PREFIXES) or "workflow" in lowered


def _is_build_path(path: str) -> bool:
    name = PurePosixPath(path).name
    return name in _BUILD_FILES


def _is_hook_path(path: str) -> bool:
    lowered = path.lower()
    name = PurePosixPath(path).name.lower()
    return any(part in lowered for part in _HOOK_PATH_PARTS) or name in _HOOK_PATH_PARTS


def _is_config_path(path: str) -> bool:
    p = PurePosixPath(path)
    return p.suffix.lower() in _CONFIG_EXTENSIONS or p.name in _BUILD_FILES


def _is_release_path(path: str) -> bool:
    return PurePosixPath(path).name in _RELEASE_FILES


def _is_security_path(path: str) -> bool:
    lowered = path.lower()
    return any(part in lowered for part in _SECURITY_PATH_PARTS)


def _is_dependency_path(path: str) -> bool:
    return PurePosixPath(path).name in _DEPENDENCY_FILES


def _dependency_added(added_lines: list[str]) -> bool:
    dependency_indicators = (
        "dependencies",
        "dependency-groups",
        "requires =",
        "version =",
        '"dependencies"',
        '"devDependencies"',
    )
    return any(any(indicator in line for indicator in dependency_indicators) for line in added_lines)


def _dependency_removed(diff_output: str) -> bool:
    removed_lines = [line for line in diff_output.splitlines() if line.startswith("-") and not line.startswith("---")]
    dependency_indicators = (
        "dependencies",
        "dependency-groups",
        "requires =",
        "version =",
        '"dependencies"',
        '"devDependencies"',
    )
    return any(any(indicator in line for indicator in dependency_indicators) for line in removed_lines)


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


class RankedIntent(BaseModel):
    """An SOP matrix row scored against extracted diff signals."""

    intent_id: str
    emoji: str
    code: str
    cc_type: str
    description: str
    semver_impact: str
    changelog_group: str
    intent_group: str
    score: float
    priority: int
    specificity: int
    split_weight: int
    selection_rule: str | None = None
    evidence: list[str] = Field(default_factory=list)
    penalties: list[str] = Field(default_factory=list)


class IntentSelectionConstraints(BaseModel):
    """Explicit allowed/disallowed intent constraints derived from deterministic diff signals."""

    reasons: list[str] = Field(default_factory=list)
    allowed_intent_ids: list[str] = Field(default_factory=list)
    disallowed_intent_ids: list[str] = Field(default_factory=list)


GraphFactOutcome = Literal["ok", "unavailable", "error"]


class GraphEnrichmentFacts(BaseModel):
    """Structural graph facts for marker enrichment only (no CRG I/O here)."""

    total_impacted: int | None = None
    test_gaps_count: int | None = None
    impacted_has_test_nodes: bool | None = None
    impacted_has_production_nodes: bool | None = None
    outcome: GraphFactOutcome = "unavailable"


class FingerprintEnrichmentFacts(BaseModel):
    """Phase 2 fingerprint / body-similarity aggregates for marker enrichment only."""

    class_counts: dict[str, int] | None = None
    body_similarity_min: float | None = None
    body_similarity_avg: float | None = None
    markers: list[str] | None = None


class SemanticEnrichmentFacts(BaseModel):
    """Optional Phase 1/2 facts assembled outside the ranker (e.g. in main).

    ``intent`` / ``rank_commit_intents`` must not import CRG or perform graph I/O.
    Missing or non-ok facts degrade to zero extra markers.
    """

    graph: GraphEnrichmentFacts | None = None
    fingerprints: FingerprintEnrichmentFacts | None = None


# Closed enrichment vocabulary (Issue #161). Only strings that exist in the
# production SOP positive/negative signal sets may affect ranking. Strings
# absent from the live matrix are filtered out at rank time.
CLOSED_ENRICHMENT_MARKERS: frozenset[str] = frozenset(
    {
        "major_subsystem_restructured",
        "core_architecture_changed",
        "internal_restructure",
        "formatting_only",
        "whitespace_or_style_cleanup",
        "comments_only",
        "inline_comment_changed",
        "source_comments_added",
        # Phase 9 (#163) P1/P2 structural markers (semantic-ON enrichment only).
        "exception_handling_added",
        "error_handling_improved",
        "try_except_added",
        "new_api",
        "new_user_facing_capability",
        "functional_code_changed",
        "new_command",
    }
)


def matrix_signal_vocabulary(matrix: list[dict]) -> frozenset[str]:
    """
    Collect the marker vocabulary declared by the positive and negative signals in SOP matrix rows.

    Parameters:
        matrix (list[dict]): SOP matrix rows containing optional signal lists.

    Returns:
        frozenset[str]: Unique positive and negative signal markers.
    """
    vocab: set[str] = set()
    for row in matrix:
        vocab.update(str(item) for item in (row.get("positive_signals") or []) if item)
        vocab.update(str(item) for item in (row.get("negative_signals") or []) if item)
    return frozenset(vocab)


def _filter_enrichment_markers(
    candidates: set[str],
    *,
    matrix_vocab: frozenset[str] | None = None,
) -> set[str]:
    """Keep only closed-vocabulary markers, optionally intersected with SOP rows."""
    allowed = set(CLOSED_ENRICHMENT_MARKERS)
    if matrix_vocab is not None:
        allowed &= set(matrix_vocab)
    return {marker for marker in candidates if marker in allowed}


def _enrich_markers_from_graph(facts: GraphEnrichmentFacts | None) -> set[str]:
    """
    Map successful structural graph facts to closed-vocabulary enrichment markers.

    Parameters:
        facts (GraphEnrichmentFacts | None): Structural graph facts to interpret.

    Returns:
        set[str]: Markers derived from the impacted-item count, or an empty set when facts are unavailable, unsuccessful, or contain no applicable count.
    """
    if facts is None or facts.outcome != "ok":
        return set()

    markers: set[str] = set()
    if facts.total_impacted is not None:
        impacted = int(facts.total_impacted)
        if impacted >= 25:
            markers.update({"major_subsystem_restructured", "core_architecture_changed"})
        elif impacted >= 10:
            markers.add("internal_restructure")
    # test_gaps_count intentionally does not emit markers unless/until a matching
    # SOP string exists (test_coverage_gap is not in the current matrix).
    return markers


def _enrich_markers_from_fingerprints(facts: FingerprintEnrichmentFacts | None) -> set[str]:
    """
    Extracts supported markers from fingerprint enrichment facts.

    Parameters:
        facts (FingerprintEnrichmentFacts | None): Fingerprint aggregates and optional marker candidates.

    Returns:
        set[str]: Closed-vocabulary markers identified in the facts.
    """
    if facts is None:
        return set()

    markers: set[str] = set()
    class_counts = facts.class_counts or {}
    for key, count in class_counts.items():
        if count and key in CLOSED_ENRICHMENT_MARKERS:
            markers.add(key)

    # High body similarity with an identifier/literal-only class is formatting-ish.
    if (
        facts.body_similarity_min is not None
        and facts.body_similarity_min > 0.9
        and int(class_counts.get("identifier_or_literal_only", 0) or 0) > 0
    ):
        markers.add("formatting_only")

    for raw in facts.markers or []:
        if raw in CLOSED_ENRICHMENT_MARKERS:
            markers.add(raw)
    return markers


def enrich_markers_from_facts(
    facts: SemanticEnrichmentFacts | None,
    *,
    matrix_vocab: frozenset[str] | None = None,
) -> set[str]:
    """
    Derive enrichment markers from optional semantic facts.

    Parameters:
        facts (SemanticEnrichmentFacts | None): Semantic facts from which to derive markers.
        matrix_vocab (frozenset[str] | None): Optional matrix-defined vocabulary that further restricts the markers.

    Returns:
        set[str]: Markers allowed by the enrichment vocabulary and, when provided, the matrix vocabulary.
    """
    if facts is None:
        return set()
    candidates = set()
    candidates |= _enrich_markers_from_graph(facts.graph)
    candidates |= _enrich_markers_from_fingerprints(facts.fingerprints)
    return _filter_enrichment_markers(candidates, matrix_vocab=matrix_vocab)


def collect_active_markers(
    signals: DiffSignals,
    *,
    enrichment: SemanticEnrichmentFacts | None = None,
    enable_semantic: bool | None = None,
    matrix_vocab: frozenset[str] | None = None,
) -> set[str]:
    """
    Build the active marker set from diff signals and optional semantic enrichment.

    Parameters:
        enrichment (SemanticEnrichmentFacts | None): Optional semantic facts used when semantic mode is enabled.
        enable_semantic (bool | None): Controls whether semantic enrichment is included.
        matrix_vocab (frozenset[str] | None): Optional marker vocabulary restricting enrichment markers.

    Returns:
        set[str]: The additive markers derived from the signals and, when enabled, filtered enrichment facts.
    """
    markers = set(_generate_signal_markers(signals))
    if not is_semantic_enabled(enable_semantic):
        return markers
    markers |= enrich_markers_from_facts(enrichment, matrix_vocab=matrix_vocab)
    return markers


def matrix_row_intent_id(row: dict) -> str:
    """
    Get the canonical intent identifier for a matrix row.

    Parameters:
        row (dict): Mapping representing a matrix row; may contain `intent_id` or `code`.

    Returns:
        intent_id (str): The value of `intent_id` if present; otherwise the `code` value with surrounding colons stripped; `'unknown'` if neither field exists.
    """
    intent_id = row.get("intent_id")
    if intent_id:
        return intent_id
    code = row.get("code")
    return str(code or "unknown").strip(":")


def derive_intent_selection_constraints(signals: DiffSignals, matrix: list[dict]) -> IntentSelectionConstraints:
    """
    Derives explicit allow/disallow intent ID constraints from diff-only signals and the provided intent matrix.

    When one or more `only_*` signals on `signals` are set this function computes a narrowed set of allowed intent groups (for example docs-only, tests-only, dependency-only), records the applied gate reasons, and classifies each matrix row's intent identifier into `allowed_intent_ids` or `disallowed_intent_ids` based on the row's `intent_group` (rows default to group `"miscellaneous"` when absent). If no `only_*` gate applies the function returns an empty IntentSelectionConstraints instance (no restrictions).

    Parameters:
        signals (DiffSignals): Extracted deterministic diff signals (used to detect `only_*` gates).
        matrix (list[dict]): SOP matrix rows to classify; each row should expose an intent identifier and may include an `intent_group` (defaults to `"miscellaneous"`).

    Returns:
        IntentSelectionConstraints: A constraints object containing `reasons` for applied gates and explicit `allowed_intent_ids` and `disallowed_intent_ids` lists.
    """
    reasons: list[str] = []
    allowed_groups: set[str] | None = None

    def _apply_allowed_groups(groups: set[str], reason: str) -> None:
        """
        Update the running allowed_groups by intersecting it with `groups` (or set it if unset) and record the given `reason`.

        Parameters:
            groups (set[str]): Group identifiers to allow or intersect with the current allowed set.
            reason (str): Short identifier explaining why these groups are being applied; recorded once.
        """
        nonlocal allowed_groups
        allowed_groups = groups if allowed_groups is None else allowed_groups.intersection(groups)
        _append_unique(reasons, reason)

    if signals.only_docs:
        _apply_allowed_groups({"docs", "miscellaneous"}, "docs_only")

    if signals.only_tests:
        _apply_allowed_groups({"tests", "miscellaneous"}, "tests_only")

    if signals.only_dependency_changes:
        _apply_allowed_groups({"runtime_build_package", "miscellaneous"}, "dependency_only")

    if allowed_groups is None:
        return IntentSelectionConstraints()

    allowed_intent_ids: list[str] = []
    disallowed_intent_ids: list[str] = []

    for row in matrix:
        intent_id = matrix_row_intent_id(row)
        intent_group = row.get("intent_group", "miscellaneous")
        if intent_group in allowed_groups:
            _append_unique(allowed_intent_ids, intent_id)
        else:
            _append_unique(disallowed_intent_ids, intent_id)

    return IntentSelectionConstraints(
        reasons=reasons,
        allowed_intent_ids=allowed_intent_ids,
        disallowed_intent_ids=disallowed_intent_ids,
    )


def _generate_signal_markers(signals: DiffSignals) -> set[str]:
    """Map DiffSignals into SOP matrix semantic marker strings.

    Marker accumulation is **flat, independent, and additive**: each ``if`` may
    contribute markers without precluding others. A single diff can therefore
    carry multiple families at once (e.g. breaking-change markers and tests
    markers together).

    Returns:
        markers (set[str]): Active marker identifiers (for example
        ``breaking_change_declared``, ``docs_only``, ``dependency_added``).
    """
    markers: set[str] = set()

    # Breaking changes
    if signals.has_breaking_change:
        markers.update(["breaking_change_declared", "breaking_change_footer", "backwards_incompatible_behavior"])

    # Documentation
    if signals.touches_docs:
        markers.update(["readme_changed", "markdown_changed", "documentation_expanded"])
    if signals.only_docs:
        markers.update(["docs_only", "documentation_typo_only", "docs_text_only"])

    # Tests
    if signals.touches_tests:
        markers.update(["tests_added", "tests_updated", "test_fixtures_changed"])
    if signals.only_tests:
        markers.update(["test_only", "tests_only", "test_logic_primary"])

    # Files (Moves/Renames/Deletes/Adds)
    if signals.moves_or_renames_files:
        markers.update(["git_rename_detected", "path_moved", "resource_renamed", "module_renamed"])
    if signals.deletes_files:
        markers.update(["files_deleted", "code_removed", "dead_code_removed", "unused_code_removed"])
    if signals.adds_files:
        markers.update(["files_added", "new_project_scaffold", "initial_structure"])

    # Dependencies & Packages
    if signals.dependency_added:
        markers.update(["dependency_added", "new_package_in_pyproject", "lockfile_new_dependency"])
    if signals.dependency_removed:
        markers.update(["dependency_removed", "package_removed_from_manifest"])
    if signals.dependency_upgraded:
        markers.update(["dependency_version_increased", "package_upgrade"])
    if signals.dependency_downgraded:
        markers.update(["dependency_version_decreased", "rollback_dependency"])
    if signals.only_dependency_changes:
        markers.update(["dependency_only", "non_dependency_version_change"])
    if signals.package_metadata_changed:
        markers.update(["package_metadata_only", "package_artifact_changed"])
    if signals.packaged_data_changed:
        markers.update(["packaged_data_changed", "wheel_or_sdist_config_changed"])

    # Security & Validation
    if signals.touches_security:
        markers.update(["security_vulnerability_fixed", "privacy_issue_fixed"])
    if signals.validation_added:
        markers.update(["validation_added", "validation_hardened", "schema_validation_changed"])
    if signals.error_handling_added:
        markers.update(["exception_handling_added", "error_handling_improved", "try_except_added"])
    if signals.secret_scanning_changed or signals.secrets_management_changed:
        markers.update(["security_tooling_only_without_fix", "secret_reference_changed"])

    # Features & API
    if signals.adds_public_api:
        markers.update(["new_api", "new_user_facing_capability", "functional_code_changed"])

    # Architecture & Refactoring
    if signals.changes_architecture:
        markers.update(["major_subsystem_restructured", "core_architecture_changed"])
    if signals.centralized_config_resolution or signals.new_shared_module:
        markers.update(["centralize_logic", "deduplicate_code", "extract_shared_helper", "internal_restructure"])

    # CI/CD & Hooks
    if signals.touches_ci:
        markers.update(["ci_workflow_updated", "github_actions_changed", "pipeline_fix"])
    if signals.touches_hooks:
        markers.update(["git_hook_configuration", "automation_script_changed"])

    # Code quality / Formatting
    if signals.only_formatting:
        markers.update(["formatting_only", "whitespace_or_style_cleanup"])

    return markers


def rank_commit_intents(
    signals: DiffSignals,
    matrix: list[dict],
    *,
    enrichment: SemanticEnrichmentFacts | None = None,
    enable_semantic: bool | None = None,
) -> list[RankedIntent]:
    """
    Rank SOP matrix rows against extracted diff signals and return them sorted by score.

    Scores each matrix row using priority and specificity as a base, then adjusts the score for matched positive and negative signals and applies hard vetoes when the diff is exclusively docs, tests, or dependency changes. Evidence and penalty messages for matches and vetoes are included on each returned item.

    Optional ``enrichment`` may add closed-vocabulary markers when semantic mode is
    enabled. Enrichment never assigns ``semver_impact``; that field is copied only
    from matched matrix rows. When semantic mode is off, enrichment is ignored.

    Parameters:
        signals (DiffSignals): Extracted deterministic signals and metadata from the diff.
        matrix (list[dict]): SOP matrix rows where each row may include keys such as
            "intent_id" or "code", "intent_group", "priority", "specificity",
            "split_weight", "positive_signals", "negative_signals" and descriptive fields.
        enrichment: Optional Phase 1/2 facts container assembled by the caller.
        enable_semantic: Explicit semantic flag; defaults to ``is_semantic_enabled()``.

    Returns:
        list[RankedIntent]: Ranked intents with computed `score`, `evidence` and `penalties`,
        sorted highest score first (ties broken by `priority` then `specificity`).
    """
    ranked: list[RankedIntent] = []
    matrix_vocab = matrix_signal_vocabulary(matrix)
    active_markers = collect_active_markers(
        signals,
        enrichment=enrichment,
        enable_semantic=enable_semantic,
        matrix_vocab=matrix_vocab,
    )

    for row in matrix:
        # Fallback values for matrices that haven't been fully updated yet
        intent_id = matrix_row_intent_id(row)
        intent_group = row.get("intent_group", "miscellaneous")
        priority = int(row.get("priority", 50))
        specificity = int(row.get("specificity", 50))
        split_weight = int(row.get("split_weight", 50))

        # Base score (gives a gentle advantage to high-priority/high-specificity items)
        score = (priority * 0.4) + (specificity * 0.1)
        evidence = []
        penalties = []

        # Evaluate Positive Signals (Matrix -> Signals)
        positive_rules = set(row.get("positive_signals", []))
        matched_positives = positive_rules.intersection(active_markers)
        for match in matched_positives:
            score += 20.0
            evidence.append(f"Matched positive signal: {match}")

        # Evaluate Negative Signals (Matrix -> Signals)
        negative_rules = set(row.get("negative_signals", []))
        matched_negatives = negative_rules.intersection(active_markers)
        for match in matched_negatives:
            score -= 30.0
            penalties.append(f"Matched negative signal: {match}")

        # Hard Vetoes / Absolute Penalties based on `DiffSignals`
        if signals.only_docs and intent_group not in ("docs", "miscellaneous"):
            score -= 100.0
            penalties.append("Hard veto: Only docs changed, but intent is not docs/misc")

        if signals.only_tests and intent_group not in ("tests", "miscellaneous"):
            score -= 100.0
            penalties.append("Hard veto: Only tests changed, but intent is not tests")

        if signals.only_dependency_changes and intent_group not in ("runtime_build_package", "miscellaneous"):
            score -= 100.0
            penalties.append("Hard veto: Only dependencies changed, but intent is not build/package")

        # Create the RankedIntent
        ranked.append(
            RankedIntent(
                intent_id=intent_id,
                emoji=row.get("emoji", ""),
                code=row.get("code", ""),
                cc_type=row.get("cc_type", "chore"),
                description=row.get("description", ""),
                semver_impact=row.get("semver_impact", "NONE"),
                changelog_group=row.get("changelog_group", "Miscellaneous"),
                intent_group=intent_group,
                score=score,
                priority=priority,
                specificity=specificity,
                split_weight=split_weight,
                selection_rule=row.get("selection_rule"),
                evidence=evidence,
                penalties=penalties,
            )
        )

    # Sort descending by score, then priority, then specificity
    ranked.sort(key=lambda x: (x.score, x.priority, x.specificity), reverse=True)
    return ranked


def _apply_diff_metrics(signals: DiffSignals, diff_output: str) -> None:
    for line in diff_output.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            signals.lines_added += 1
        elif line.startswith("-") and not line.startswith("---"):
            signals.lines_removed += 1

    signals.files_changed_count = len(signals.files)

    if signals.lines_added or signals.lines_removed:
        signals.evidence.append(
            f"Diff size: +{signals.lines_added}/-{signals.lines_removed} across {signals.files_changed_count} files"
        )
