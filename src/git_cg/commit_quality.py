"""Pure presentation-quality policy (Issue #204 · Phase 7.30).

Owns path-role TrailerPriors and (later slices) diff-class gates, SemVer/type
ceilings, craft/hallucination/inventory guards, and blueprint apply helpers.

Authority boundaries:
* Matrix ranker remains sole ranking / SemVer / intent authority.
* This module must not call ``rank_commit_intents`` or mutate rank scores.
* No git I/O, LLM calls, or hook interactivity.
* Reuses intent path classifiers and gold ``_file_groups`` — does not fork them.
* ``scope_canon`` may be imported; gold may consume outputs of this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from git_cg.commit_gold import _file_groups
from git_cg.intent import (
    DiffSignals,
    _is_build_path,
    _is_ci_path,
    _is_config_path,
    _is_docs_path,
    _is_hook_path,
    _is_release_path,
    _is_security_path,
    _is_test_path,
)
from git_cg.models import CommitType, SemVerImpact, TrailerPriors
from git_cg.scope_canon import normalize_scope

if TYPE_CHECKING:
    from git_cg.models import CommitPlan
    from git_cg.ranking_confidence import RankingConfidence


def _norm_path(path: str) -> str:
    """Lowercase path with backslashes normalised to slashes."""
    return path.replace(chr(92), "/").lower()


# Soft presentation defaults for non-forced roles (product_src / mixed).
# Intentionally not feat/MINOR — matrix High/Med owns product framing.
_SOFT_CC = CommitType.CHORE
_SOFT_SEMVER = SemVerImpact.NONE
_SOFT_CHANGELOG = "Miscellaneous"

# ---------------------------------------------------------------------------
# Slice 2b — Diff-class gates · changelog anti-signal · security path evidence
# ---------------------------------------------------------------------------

# Closed diff-class vocabulary (D11). Internal frozen value objects (D22).
DIFF_CLASS_TESTS = "tests_only"
DIFF_CLASS_FIXTURES = "fixtures_only"
DIFF_CLASS_DOCS = "docs_only"
DIFF_CLASS_ADR = "adr_only"
DIFF_CLASS_CONFIG_CI = "config_ci_only"
DIFF_CLASS_RELEASE = "release_only"
DIFF_CLASS_PRODUCT = "product_src"
DIFF_CLASS_MIXED = "mixed"
DIFF_CLASS_EMPTY = "empty"

# Positive security path evidence beyond intent._is_security_path (D13).
_SECURITY_PATH_EXTRA_PARTS = frozenset(
    {
        "secrets",
        "secret",
        "credential",
        "credentials",
        "fnox",
        "sops",
        "age",
        "scanner",
        "gitleaks",
        "trufflehog",
    }
)
_SECURITY_PATH_EXTRA_NAMES = frozenset(
    {
        "secrets.py",
        "secret.py",
        "credentials.py",
        "fnox.toml",
        ".sops.yaml",
        "gitleaks.toml",
    }
)

# Docs/ADR/test prose that must NOT alone promote security presentation (D13).
SECURITY_NEGATIVE_PROSE_MARKERS: frozenset[str] = frozenset(
    {
        "sole authority",
        "never authorise intent_id",
        "never authorize intent_id",
        "authority untouched",
        "redacted on write",
        "matrix authority",
        "ranking authority",
    }
)

# High-risk subject/body nouns that require path evidence (D14 partial / D13).
SECURITY_CLAIM_TOKENS: frozenset[str] = frozenset(
    {
        "secrets",
        "secret",
        "credentials",
        "credential",
        "password",
        "token",
        "api key",
        "apikey",
    }
)

CHANGELOG_BASENAMES = frozenset({"changelog.md"})


@dataclass(frozen=True)
class DiffClass:
    """Frozen staged-path classification for presentation gates (D11)."""

    name: str
    paths: tuple[str, ...]
    has_runtime_surface: bool
    has_security_path_evidence: bool
    changelog_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class PresentationConstraints:
    """Frozen presentation force/forbid set derived from DiffClass (D11/D12/D13).

    Does not mutate ranked intent_id. Applied as presentation overlay / validation.
    """

    diff_class: str
    force_cc_type: CommitType | None = None
    force_semver: SemVerImpact | None = None
    force_changelog_group: str | None = None
    force_scope: str | None = None
    forbid_cc_types: frozenset[str] = field(default_factory=frozenset)
    forbid_semver: frozenset[str] = field(default_factory=frozenset)
    forbid_security_primary: bool = False
    changelog_antisignal_applied: bool = False
    security_requires_path_evidence: bool = True
    notes: tuple[str, ...] = ()


# Closed stub role vocabulary (internal policy; BlueprintStub serialises a subset later).
STUB_ROLES: frozenset[str] = frozenset(
    {
        "prod",
        "test",
        "docs",
        "adr",
        "fixtures",
        "telemetry",
        "sentry",
        "perf",
        "refactor",
        "security",
        "other",
    }
)

# Deterministic concern-tag → inventory seed notes (D18 / D20 / §K).
# Keys are lower-case concern tags; values are short description seeds (≤80).
_CONCERN_STUB_SEEDS: dict[str, tuple[str, str, str]] = {
    # role, surface, note
    "fallback_none_overwrite": (
        "prod",
        "telemetry",
        "preserve scoped_history_fallback_reason=none",
    ),
    "parser_batch_results": (
        "prod",
        "telemetry",
        "reuse parser_batch_results for markers",
    ),
    "rename_harden": (
        "prod",
        "main",
        "discover staged renames via name-status",
    ),
    "nul_rename_parse": (
        "prod",
        "scoped-history",
        "parse NUL -z rename pairs correctly",
    ),
    "scrub_vars": (
        "sentry",
        "sentry",
        "expand Sentry scrub vars for evidence",
    ),
    "scrub_sentinel": (
        "telemetry",
        "telemetry",
        "preserve [REDACTED] sentinel on scrub fail",
    ),
    "redacted_sentinel": (
        "telemetry",
        "telemetry",
        "preserve [REDACTED] sentinel not None",
    ),
    "redaction_sentinel": (
        "telemetry",
        "telemetry",
        "preserve [REDACTED] sentinel not None",
    ),
    "closed_enum": (
        "prod",
        "telemetry",
        "coerce closed-enum telemetry tags safely",
    ),
    "fallback_enum": (
        "prod",
        "scoped-history",
        "keep graph-stage none/error fallback enums",
    ),
    "cli_hint_reject": (
        "prod",
        "scoped-history",
        "reject bare-command CLI hint tokens",
    ),
    "directive_free_wording": (
        "prod",
        "scoped-history",
        "keep Channel-4 wording directive-free",
    ),
    "directive_verb_drop": (
        "prod",
        "scoped-history",
        "drop directive verbs from guidance text",
    ),
    "authority_leakage_ban": (
        "test",
        "scoped-history",
        "ban authority-leakage claim wording",
    ),
    "correctness": (
        "prod",
        "scoped-history",
        "fix internal correctness failure mode",
    ),
    "safety": (
        "prod",
        "scoped-history",
        "harden safety-critical failure path",
    ),
    "parse_harden": (
        "prod",
        "scoped-history",
        "harden parse path against bad input",
    ),
    "fail_open": (
        "prod",
        "scoped-history",
        "preserve fail-open classification path",
    ),
    "error_signal": (
        "prod",
        "telemetry",
        "preserve error-signal telemetry fields",
    ),
    "masking_none": (
        "telemetry",
        "telemetry",
        "avoid masking failed redaction to None",
    ),
    "dark_launch": (
        "prod",
        "semantic",
        "thread dark-launch harvest helpers",
    ),
    "free_harvest": (
        "prod",
        "semantic",
        "harvest free hub/complex/callers maps",
    ),
    "flag_default_off": (
        "prod",
        "semantic",
        "keep flag-default-off harvest optional",
    ),
    "carry_through": (
        "prod",
        "scoped-history",
        "carry preflight counters through plan",
    ),
    "preflight_carry": (
        "prod",
        "scoped-history",
        "carry preflight counters through plan",
    ),
    "preflight_carry_through": (
        "prod",
        "scoped-history",
        "carry preflight counters through plan",
    ),
    "elevation": (
        "prod",
        "scoped-history",
        "wire preflight into split elevation",
    ),
}


@dataclass(frozen=True)
class Stub:
    """Internal included-change inventory seed (Issue #204 · Slice 4 · D5/D18).

    Prompt inventory pressure only — not a ranked intent and not a wording lock.
    Serialisable BlueprintStub lands in models.py in a later slice.
    """

    role: str
    surface: str
    suggested_cc_type: CommitType
    scope: str | None = None
    note: str | None = None
    claim_tags: tuple[str, ...] = ()
    source: str = "path"  # path | concern | claim | signal

    def __post_init__(self) -> None:
        if self.role not in STUB_ROLES:
            raise ValueError(f"stub role must be one of {sorted(STUB_ROLES)}; got {self.role!r}")
        if self.note is not None and len(self.note) > 80:
            object.__setattr__(self, "note", self.note[:80])
        if len(self.claim_tags) > 8:
            object.__setattr__(self, "claim_tags", self.claim_tags[:8])


def _is_changelog_path(path: str) -> bool:
    return PurePosixPath(path).name.lower() in CHANGELOG_BASENAMES


def _is_runtime_surface_path(path: str) -> bool:
    """Return whether path can justify non-NONE SemVer / product framing (D11 global).

    Changelog/docs release notes are **not** runtime surfaces (D12). Version /
    packaging manifests and hooks/scripts/src are.
    """
    lowered = _norm_path(path)
    p = PurePosixPath(path)
    if _is_changelog_path(path) or _is_docs_path(path):
        # Pure docs artifacts never unlock SemVer by themselves.
        return False
    if lowered.startswith("src/") or lowered.startswith("scripts/"):
        return True
    if _is_hook_path(path):
        return True
    # Explicit version / packaging manifests (not CHANGELOG).
    return p.name in {"VERSION", "pyproject.toml", "package.json"}


def has_security_path_evidence(paths: list[str]) -> bool:
    """Return whether any staged path is positive security evidence (D13).

    Uses a **tight** allowlist. Broad intent ``_is_security_path`` matches weak
    tokens like ``auth`` in fixture flow names — those must **not** alone unlock
    security presentation (negative prose / path markers).
    """
    for path in paths:
        # Docs / ADR / pure fixture markdown never count as security path evidence.
        if _is_docs_path(path) or _is_adr_path(path):
            continue
        if _is_fixtures_path(path) and not any(
            tok in _norm_path(path) for tok in ("secret", "credential", "password", "gitleaks", "sops", "fnox")
        ):
            continue

        lowered = _norm_path(path)
        name = PurePosixPath(path).name.lower()
        if name in _SECURITY_PATH_EXTRA_NAMES:
            return True
        parts = {part.lower() for part in PurePosixPath(path).parts}
        # Strong parts only — exclude bare "auth" / "permission" weak tokens.
        strong = parts & _SECURITY_PATH_EXTRA_PARTS
        if strong:
            return True
        if name == "secrets.py" or lowered.endswith("/secrets.py"):
            return True
        if "secret" in lowered and (lowered.startswith(".github/") or "workflow" in lowered or "scanner" in lowered):
            return True
        # Reuse intent helper only for non-docs product/config paths with strong names.
        if _is_security_path(path) and any(
            tok in lowered for tok in ("secret", "credential", "password", "token", "sops", "fnox", "gitleaks")
        ):
            return True
    return False


def changelog_paths_in(paths: list[str]) -> list[str]:
    """Return staged changelog artifact paths (docs coverage; prose excluded)."""
    return [p for p in paths if _is_changelog_path(p)]


def filter_paths_for_content_signals(paths: list[str]) -> list[str]:
    """D12 exclude_from_signals: drop changelog paths from content-marker inputs."""
    return [p for p in paths if not _is_changelog_path(p)]


def prose_has_security_negative_markers(text: str) -> bool:
    """Return whether *text* contains docs/ADR negative security prose markers."""
    lowered = text.lower()
    return any(marker in lowered for marker in SECURITY_NEGATIVE_PROSE_MARKERS)


def security_claims_without_path_evidence(text: str, paths: list[str]) -> list[str]:
    """Return security claim tokens present in *text* without path evidence (D13/D14)."""
    if has_security_path_evidence(paths):
        return []
    lowered = text.lower()
    hits = [tok for tok in sorted(SECURITY_CLAIM_TOKENS) if tok in lowered]
    return hits


def classify_diff_class(paths: list[str]) -> DiffClass:
    """Classify staged paths into a closed DiffClass for presentation gates (D11)."""
    clean = [p for p in paths if p and str(p).strip()]
    changelog = tuple(changelog_paths_in(clean))
    runtime = any(_is_runtime_surface_path(p) for p in clean)
    sec = has_security_path_evidence(clean)
    if not clean:
        return DiffClass(
            name=DIFF_CLASS_EMPTY,
            paths=(),
            has_runtime_surface=False,
            has_security_path_evidence=False,
            changelog_paths=(),
        )

    roles = _classify_path_roles(clean)
    # Prefer ADR over generic docs when exclusive.
    # ADR + usage/docs is still a pure documentation family (TIP-G12), not product mixed.
    if roles == {"adr"} or roles == {"adr", "release"}:
        name = DIFF_CLASS_ADR
    elif roles <= {"adr", "docs", "release"} and roles & {"docs", "adr"}:
        # docs-only, docs+adr, docs+release, docs+adr+release
        name = DIFF_CLASS_DOCS
    elif roles == {"fixtures"}:
        name = DIFF_CLASS_FIXTURES
    elif roles == {"tests"}:
        name = DIFF_CLASS_TESTS
    elif roles == {"config_ci"} or roles == {"config_ci", "release"}:
        name = DIFF_CLASS_CONFIG_CI
    elif roles == {"release"}:
        name = DIFF_CLASS_RELEASE
    elif roles == {"product_src"}:
        name = DIFF_CLASS_PRODUCT
    else:
        name = DIFF_CLASS_MIXED

    return DiffClass(
        name=name,
        paths=tuple(clean),
        has_runtime_surface=runtime,
        has_security_path_evidence=sec,
        changelog_paths=changelog,
    )


def presentation_constraints(diff_class: DiffClass) -> PresentationConstraints:
    """Build force/forbid presentation constraints from a DiffClass (D11/D12/D13)."""
    notes: list[str] = []
    antisignal = bool(diff_class.changelog_paths)
    if antisignal:
        notes.append("changelog_antisignal_exclude_from_signals")

    force_cc: CommitType | None = None
    force_semver: SemVerImpact | None = None
    force_group: str | None = None
    force_scope: str | None = None
    forbid_cc: set[str] = set()
    forbid_semver: set[str] = set()
    forbid_security = False

    name = diff_class.name

    if name == DIFF_CLASS_TESTS:
        force_cc = CommitType.TEST
        force_semver = SemVerImpact.NONE
        force_group = "Tests"
        # Prefer behaviour slug (scoped-history) over generic "test" when paths imply it.
        force_scope = _behaviour_scope_hint(list(diff_class.paths)) or "test"
        forbid_cc.update({"feat", "fix"})
        forbid_security = True
        forbid_semver.update({"PATCH", "MINOR", "MAJOR"})
        notes.append("tests_only_force_test_none")
    elif name == DIFF_CLASS_FIXTURES:
        force_cc = CommitType.DOCS
        force_semver = SemVerImpact.NONE
        force_group = "Documentation"
        force_scope = "fixtures"
        forbid_cc.update({"feat", "fix"})
        forbid_security = True
        forbid_semver.update({"PATCH", "MINOR", "MAJOR"})
        notes.append("fixtures_only_force_docs_none")
    elif name == DIFF_CLASS_DOCS:
        force_cc = CommitType.DOCS
        force_semver = SemVerImpact.NONE
        force_group = "Documentation"
        force_scope = _docs_scope_hint(list(diff_class.paths))
        forbid_cc.update({"feat", "fix"})
        forbid_security = True
        forbid_semver.update({"PATCH", "MINOR", "MAJOR"})
        notes.append("docs_only_force_docs_none")
    elif name == DIFF_CLASS_ADR:
        force_cc = CommitType.DOCS
        force_semver = SemVerImpact.NONE
        force_group = "Documentation"
        force_scope = "adr"
        forbid_cc.update({"feat", "fix", "chore"})
        forbid_security = True
        forbid_semver.update({"PATCH", "MINOR", "MAJOR"})
        notes.append("adr_only_force_docs_adr_none")
    elif name in {DIFF_CLASS_CONFIG_CI, DIFF_CLASS_RELEASE, DIFF_CLASS_EMPTY}:
        # No product runtime ⇒ NONE ceiling unless version files (handled via runtime flag).
        if not diff_class.has_runtime_surface:
            force_semver = SemVerImpact.NONE
            forbid_semver.update({"PATCH", "MINOR", "MAJOR"})
            notes.append("no_runtime_surface_semver_none")
        forbid_security = not diff_class.has_security_path_evidence
    elif name == DIFF_CLASS_PRODUCT:
        forbid_security = not diff_class.has_security_path_evidence
    else:  # mixed
        if not diff_class.has_runtime_surface:
            force_semver = SemVerImpact.NONE
            forbid_semver.update({"PATCH", "MINOR", "MAJOR"})
            notes.append("mixed_no_runtime_semver_none")
            path_list = list(diff_class.paths)
            has_tests = any(_is_meaningful_test_path(p) for p in path_list)
            has_docs = any((_is_docs_path(p) or _is_adr_path(p) or _is_fixtures_path(p)) for p in path_list)
            # Test-dominant non-runtime mixed (tests+ADR/docs/fixtures): never invent feat.
            if has_tests:
                force_cc = CommitType.TEST
                force_group = "Tests"
                force_scope = _behaviour_scope_hint(path_list)
                forbid_cc.update({"feat", "fix"})
                notes.append("mixed_no_runtime_test_primary")
            elif has_docs:
                force_cc = CommitType.DOCS
                force_group = "Documentation"
                force_scope = _docs_scope_hint(path_list)
                forbid_cc.update({"feat", "fix"})
                notes.append("mixed_no_runtime_docs_primary")
        forbid_security = not diff_class.has_security_path_evidence

    # Global D11: no runtime surface ⇒ NONE
    if not diff_class.has_runtime_surface and force_semver is None:
        force_semver = SemVerImpact.NONE
        forbid_semver.update({"PATCH", "MINOR", "MAJOR"})
        notes.append("global_no_runtime_semver_none")

    if forbid_security:
        notes.append("security_primary_forbidden_without_path_evidence")

    return PresentationConstraints(
        diff_class=name,
        force_cc_type=force_cc,
        force_semver=force_semver,
        force_changelog_group=force_group,
        force_scope=force_scope,
        forbid_cc_types=frozenset(forbid_cc),
        forbid_semver=frozenset(forbid_semver),
        forbid_security_primary=forbid_security,
        changelog_antisignal_applied=antisignal,
        security_requires_path_evidence=True,
        notes=tuple(notes),
    )


def constraints_from_paths(
    staged_paths: list[str],
    *,
    signals: DiffSignals | None = None,
) -> PresentationConstraints:
    """Classify paths and return presentation constraints (Slice 2b entrypoint)."""
    paths = _resolve_paths(staged_paths, signals)
    return presentation_constraints(classify_diff_class(paths))


def _is_fixtures_path(path: str) -> bool:
    """Return whether *path* is under a fixtures tree (docs-or-test corpus)."""
    parts = {part.lower() for part in PurePosixPath(path).parts}
    return "fixtures" in parts


def _is_adr_path(path: str) -> bool:
    """Return whether *path* is an ADR document path."""
    lowered = _norm_path(path)
    parts = {part.lower() for part in PurePosixPath(path).parts}
    if "adrs" in parts or "adr" in parts:
        return True
    name = PurePosixPath(path).name.lower()
    return name.startswith("adr-") or "/adrs/" in lowered or "/adr/" in lowered


def _is_meaningful_test_path(path: str) -> bool:
    """Return whether *path* is a real test module (not fixtures corpus)."""
    return _is_test_path(path) and not _is_fixtures_path(path)


def _behaviour_scope_hint(paths: list[str]) -> str | None:
    """Infer behaviour-first scope from staged paths (e.g. scoped-history)."""
    if not paths:
        return None
    blob = " ".join(_norm_path(p) for p in paths)
    if "scoped_history" in blob or "scoped-history" in blob or "scoped_hist" in blob:
        return normalize_scope("scoped-history")
    if "phase9" in blob:
        return normalize_scope("phase9")
    return None


def _classify_path_roles(paths: list[str]) -> set[str]:
    """Map staged paths to closed presentation roles (may be multi-label per path)."""
    roles: set[str] = set()
    for path in paths:
        if _is_fixtures_path(path):
            roles.add("fixtures")
            # Fixtures often also match test/docs helpers; keep fixtures dominant label.
            continue
        if _is_adr_path(path) and _is_docs_path(path):
            roles.add("adr")
            continue
        groups = _file_groups(path)
        if "tests" in groups:
            roles.add("tests")
        if "docs" in groups:
            roles.add("docs")
        if "config_ci" in groups:
            roles.add("config_ci")
        if "release" in groups:
            # Pure release files that are also docs (CHANGELOG) stay docs-primary
            # when every path is docs-classed; otherwise note release.
            roles.add("release")
        if not groups and not _is_docs_path(path) and not _is_test_path(path):
            roles.add("product_src")
    return roles


def _dominant_product_scope(paths: list[str]) -> str | None:
    """If a single product module dominates, return its canonical scope hint."""
    product_paths = [
        p
        for p in paths
        if not _is_test_path(p)
        and not _is_docs_path(p)
        and not _is_ci_path(p)
        and not _is_build_path(p)
        and not _is_hook_path(p)
        and not _is_config_path(p)
        and not _is_release_path(p)
        and not _is_fixtures_path(p)
    ]
    if not product_paths:
        return None
    basenames = {PurePosixPath(p).stem.lower() for p in product_paths}
    if len(basenames) == 1:
        only = next(iter(basenames))
        return normalize_scope(only)
    # Prefer src/git_cg/<mod>.py style single-module dominance by full path stem.
    stems = [PurePosixPath(p).stem for p in product_paths]
    if len(set(stems)) == 1:
        return normalize_scope(stems[0])
    return None


def _docs_scope_hint(paths: list[str]) -> str | None:
    """Pick docs/usage/phase9/adr scope hint from staged docs paths."""
    lowered = [_norm_path(p) for p in paths]
    if any(_is_adr_path(p) for p in paths):
        return normalize_scope("adr")
    if any("phase9" in p for p in lowered):
        return normalize_scope("phase9")
    if any(p.endswith("usage.md") or "/usage.md" in p or p.endswith("/usage") for p in lowered):
        return normalize_scope("usage")
    if any(_is_fixtures_path(p) for p in paths):
        return normalize_scope("fixtures")
    return normalize_scope("docs")


def _config_ci_defaults(paths: list[str]) -> tuple[CommitType, str]:
    """Return (cc_type, scope_hint) for pure config/ci/hooks/build slices."""
    if paths and all(_is_ci_path(p) for p in paths):
        return CommitType.CI, "ci"
    if paths and all(_is_build_path(p) for p in paths):
        return CommitType.BUILD, "build"
    if paths and all(_is_hook_path(p) for p in paths):
        return CommitType.CHORE, "chore"
    # Mixed config_ci subtypes → chore/Miscellaneous with generic chore scope.
    if (
        paths
        and any(_is_ci_path(p) for p in paths)
        and not any(_is_build_path(p) or _is_hook_path(p) or _is_config_path(p) for p in paths if not _is_ci_path(p))
        and all(_is_ci_path(p) or _is_config_path(p) for p in paths)
    ):
        return CommitType.CI, "ci"
    if paths and any(_is_build_path(p) for p in paths) and all(_is_build_path(p) or _is_config_path(p) for p in paths):
        return CommitType.BUILD, "build"
    return CommitType.CHORE, "chore"


def _resolve_paths(staged_paths: list[str], signals: DiffSignals | None) -> list[str]:
    """Prefer explicit staged paths; fall back to signals.files."""
    paths = [p for p in staged_paths if p and str(p).strip()]
    if paths:
        return paths
    if signals is not None and signals.files:
        return list(signals.files)
    return []


def derive_trailer_priors(
    staged_paths: list[str],
    *,
    signals: DiffSignals | None = None,
) -> TrailerPriors:
    """Derive frozen path-role presentation priors from staged paths.

    Single-role slices get forced presentation defaults (tests/docs/ADR/fixtures/
    config_ci). Mixed and product_src return soft non-feat defaults and leave
    High/Med framing to the matrix ranker.

    Parameters:
        staged_paths: Paths in the staged diff (may be empty when *signals* carries files).
        signals: Optional ``DiffSignals``; ``files`` used when *staged_paths* is empty.

    Returns:
        TrailerPriors: Frozen presentation priors (not a ranking decision).
    """
    paths = _resolve_paths(staged_paths, signals)
    if not paths:
        return TrailerPriors(
            cc_type=_SOFT_CC,
            semver_impact=_SOFT_SEMVER,
            changelog_group=_SOFT_CHANGELOG,
            scope_hint=None,
            role="mixed",
        )

    roles = _classify_path_roles(paths)

    # --- single-role forced defaults (Slice 2 table) ---
    if roles == {"tests"}:
        return TrailerPriors(
            cc_type=CommitType.TEST,
            semver_impact=SemVerImpact.NONE,
            changelog_group="Tests",
            scope_hint=_behaviour_scope_hint(paths) or normalize_scope("test"),
            role="tests",
        )

    if roles == {"fixtures"}:
        return TrailerPriors(
            cc_type=CommitType.DOCS,
            semver_impact=SemVerImpact.NONE,
            changelog_group="Documentation",
            scope_hint=normalize_scope("fixtures"),
            role="fixtures",
        )

    if roles == {"adr"}:
        return TrailerPriors(
            cc_type=CommitType.DOCS,
            semver_impact=SemVerImpact.NONE,
            changelog_group="Documentation",
            scope_hint=normalize_scope("adr"),
            role="adr",
        )

    if roles <= {"adr", "docs", "release"} and roles & {"docs", "adr"} and "product_src" not in roles:
        # docs-only / ADR family, including CHANGELOG-as-docs (+ release dual-label)
        # and ADR+usage (TIP-G12). Exclusive ADR keeps role=adr.
        if roles == {"adr"} or roles == {"adr", "release"}:
            return TrailerPriors(
                cc_type=CommitType.DOCS,
                semver_impact=SemVerImpact.NONE,
                changelog_group="Documentation",
                scope_hint=normalize_scope("adr"),
                role="adr",
            )
        return TrailerPriors(
            cc_type=CommitType.DOCS,
            semver_impact=SemVerImpact.NONE,
            changelog_group="Documentation",
            scope_hint=_docs_scope_hint(paths),
            role="docs",
        )

    if roles == {"release"}:
        return TrailerPriors(
            cc_type=CommitType.CHORE,
            semver_impact=SemVerImpact.NONE,
            changelog_group="Miscellaneous",
            scope_hint=normalize_scope("release") or "release",
            role="release",
        )

    if roles == {"config_ci"} or roles == {"config_ci", "release"}:
        cc_type, scope = _config_ci_defaults(paths)
        return TrailerPriors(
            cc_type=cc_type,
            semver_impact=SemVerImpact.NONE,
            changelog_group="Miscellaneous",
            scope_hint=normalize_scope(scope),
            role="config_ci",
        )

    if roles == {"product_src"}:
        return TrailerPriors(
            cc_type=_SOFT_CC,
            semver_impact=_SOFT_SEMVER,
            changelog_group=_SOFT_CHANGELOG,
            scope_hint=_dominant_product_scope(paths),
            role="product_src",
        )

    # Mixed multi-role — no forced feat/MINOR
    scope_hint = _dominant_product_scope(paths)
    return TrailerPriors(
        cc_type=_SOFT_CC,
        semver_impact=_SOFT_SEMVER,
        changelog_group=_SOFT_CHANGELOG,
        scope_hint=scope_hint,
        role="mixed",
    )


# ---------------------------------------------------------------------------
# Slice 2c — SemVer ceiling · type dominance · changelog↔types · cardinality
# ---------------------------------------------------------------------------

# Contract-break markers that may unlock MAJOR presentation (D16).
DEFAULT_CONTRACT_BREAK_MARKERS: frozenset[str] = frozenset(
    {
        "breaking change",
        "breaks api",
        "public api removed",
        "remove public",
        "cli contract break",
        "sop matrix break",
        "schema break",
        "incompatible",
    }
)

# Correctness / safety concern tags that force fix-over-feat dominance (D17).
CORRECTNESS_CONCERN_TAGS: frozenset[str] = frozenset(
    {
        "correctness",
        "safety",
        "parse_harden",
        "fail_open",
        "scrub_sentinel",
        "redaction_sentinel",
        "redacted_sentinel",
        "fallback_none_overwrite",
        "closed_enum",
        "rename_harden",
        "error_signal",
        "masking_none",
        "scrub_vars",
        "parser_batch_results",
        "nul_rename_parse",
        "fallback_enum",
        "cli_hint_reject",
        "directive_free_wording",
        "directive_verb_drop",
        "authority_leakage_ban",
    }
)

# Dark-launch / non-operator-visible additive tags → PATCH ceiling even if feat (D16).
DARK_LAUNCH_TAGS: frozenset[str] = frozenset(
    {
        "dark_launch",
        "flag_default_off",
        "free_harvest",
        "carry_through",
        "preflight_carry",
        "preflight_carry_through",
        "elevation",
    }
)

# Carry-through / stub-wiring feat presentation uses Changed (not Added-led) (TIP-G11).
CARRY_THROUGH_TAGS: frozenset[str] = frozenset(
    {
        "carry_through",
        "preflight_carry",
        "preflight_carry_through",
        "elevation",
    }
)

# Change-type → required changelog group fragments (D19).
_TYPE_CHANGELOG_REQUIREMENTS: dict[str, str] = {
    "test": "Tests",
    "docs": "Documentation",
    "fix": "Fixed",
    "feat": "Added",
    "refactor": "Changed",
    "perf": "Changed",
    "style": "Changed",
    "build": "Miscellaneous",
    "ci": "Miscellaneous",
    "chore": "Miscellaneous",
    "revert": "Miscellaneous",
    "release": "Miscellaneous",
}


def semver_presentation_ceiling(
    paths: list[str],
    signals: DiffSignals | None = None,
    *,
    contract_break_markers: frozenset[str] | set[str] | None = None,
    concern_tags: frozenset[str] | set[str] | None = None,
    evidence_text: str = "",
) -> SemVerImpact:
    """Return the maximum presentation SemVer impact allowed (D16).

    Does not select the matrix intent — only caps what presentation may emit.
    """
    clean = _resolve_paths(list(paths or []), signals)
    dc = classify_diff_class(clean)
    tags = {t.lower() for t in (concern_tags or set())}
    markers = contract_break_markers if contract_break_markers is not None else DEFAULT_CONTRACT_BREAK_MARKERS
    blob = evidence_text.lower()

    # Pure non-runtime classes → NONE
    if dc.name in {
        DIFF_CLASS_TESTS,
        DIFF_CLASS_FIXTURES,
        DIFF_CLASS_DOCS,
        DIFF_CLASS_ADR,
        DIFF_CLASS_EMPTY,
    } or (not dc.has_runtime_surface and dc.name != DIFF_CLASS_PRODUCT):
        return SemVerImpact.NONE

    has_break = any(m in blob for m in markers)
    if has_break:
        return SemVerImpact.MAJOR

    # Internal correctness / dark-launch / no new operator-visible capability → PATCH
    if tags & CORRECTNESS_CONCERN_TAGS or tags & DARK_LAUNCH_TAGS:
        return SemVerImpact.PATCH

    # Default product_src / mixed without break or capability evidence: PATCH ceiling
    # (MINOR only when explicit operator-visible capability tag is supplied).
    if "operator_visible_capability" in tags or "new_capability" in tags:
        return SemVerImpact.MINOR

    return SemVerImpact.PATCH


def dominant_presentation_cc_type(
    paths: list[str],
    *,
    signals: DiffSignals | None = None,
    concern_tags: frozenset[str] | set[str] | None = None,
    priors: TrailerPriors | None = None,
) -> CommitType | None:
    """Return forced presentation primary type when policy dominates (D17 / D11).

    Returns None when matrix High/Med may keep its primary without overlay.
    """
    clean = _resolve_paths(list(paths or []), signals)
    tags = {t.lower() for t in (concern_tags or set())}
    base = priors or derive_trailer_priors(clean, signals=signals)
    cons = presentation_constraints(classify_diff_class(clean))

    if cons.force_cc_type is not None:
        return cons.force_cc_type

    # Correctness/safety on product paths → fix over feat
    if tags & CORRECTNESS_CONCERN_TAGS and base.role in {"product_src", "mixed"}:
        return CommitType.FIX

    return None


def required_changelog_groups(
    change_types: list[str] | tuple[str, ...],
    *,
    primary_cc_type: str | CommitType | None = None,
) -> list[str]:
    """Return required Changelog-Groups for the given Change-Types (D19)."""
    types = [str(t).lower() for t in change_types if t]
    required: list[str] = []
    seen: set[str] = set()
    for t in types:
        group = _TYPE_CHANGELOG_REQUIREMENTS.get(t)
        if group and group not in seen:
            seen.add(group)
            required.append(group)

    primary = str(primary_cc_type).lower() if primary_cc_type is not None else None
    if primary == "fix" and "Fixed" not in seen:
        required.insert(0, "Fixed")
        seen.add("Fixed")

    # Reject Miscellaneous-only when types are test/docs — ensure groups present.
    if types and set(types) <= {"test", "docs"} and not required:
        required = ["Tests"] if "test" in types else ["Documentation"]

    return required


def changelog_groups_allowlisted(
    change_types: list[str] | tuple[str, ...],
    changelog_groups: list[str] | tuple[str, ...],
    *,
    primary_cc_type: str | CommitType | None = None,
) -> bool:
    """Return whether presented changelog groups satisfy the D19 allowlist."""
    groups = [g.strip() for g in changelog_groups if g and str(g).strip()]
    required = required_changelog_groups(change_types, primary_cc_type=primary_cc_type)
    if not required:
        return True
    # Miscellaneous-only is illegal when test/docs/fix requirements exist.
    if groups == ["Miscellaneous"] and required:
        return False
    # Added-only illegal when primary is fix
    primary = str(primary_cc_type).lower() if primary_cc_type is not None else None
    if primary == "fix" and groups == ["Added"]:
        return False
    for req in required:
        if req == "Added" and ("feat" in {str(t).lower() for t in change_types} or primary == "feat"):
            # feat may present as Added (capability) or Changed (carry-through/plumbing).
            if "Added" not in groups and "Changed" not in groups:
                return False
            continue
        if req not in groups:
            return False
    return True


def min_included_change_bullets(
    paths: list[str],
    *,
    concern_tags: frozenset[str] | set[str] | None = None,
) -> int:
    """Minimum Included-changes bullet count from path surfaces + concerns (D18 / §K).

    Floor only — concrete inventory seeds live in ``build_included_change_stubs``.
    """
    clean = [p for p in paths if p and str(p).strip()]
    if not clean:
        return 0

    tags = {t.lower() for t in (concern_tags or set())}
    has_test = any(_is_meaningful_test_path(p) for p in clean)
    has_docs = any((_is_docs_path(p) or _is_adr_path(p)) and not _is_fixtures_path(p) for p in clean)
    has_fixtures = any(_is_fixtures_path(p) for p in clean)
    has_prod = any(not _is_test_path(p) and not _is_docs_path(p) and not _is_fixtures_path(p) for p in clean)
    surfaces = 0
    if has_test:
        surfaces += 1
    if has_docs or has_fixtures:
        surfaces += 1
    if has_prod:
        surfaces += 1

    concern_count = len(tags) if tags else 0
    # Multi-concern product diffs: required_bullets = max(surfaces, concern_count)
    floor = max(surfaces, concern_count, 1 if clean else 0)
    # tests with product → at least 2 (prod + test)
    if has_test and has_prod:
        floor = max(floor, 2)
    # ≥2 test modules each count as a concern atom (§K.2)
    test_modules = _test_module_stems(clean)
    if len(test_modules) >= 2:
        floor = max(floor, len(test_modules))
    return floor


def _test_module_stems(paths: list[str]) -> list[str]:
    """Return ordered unique test module stems (tests/test_*.py only)."""
    stems: list[str] = []
    seen: set[str] = set()
    for path in paths:
        if not _is_meaningful_test_path(path):
            continue
        name = PurePosixPath(path).name
        if not (name.startswith("test_") and name.endswith(".py")):
            # Keep non-standard test paths as stem too when under tests/
            stem = PurePosixPath(path).stem
        else:
            stem = PurePosixPath(path).stem
        key = stem.lower()
        if key in seen:
            continue
        seen.add(key)
        stems.append(stem)
    return stems


def _product_module_stems(paths: list[str]) -> list[str]:
    """Return ordered unique product module stems (src/scripts/hooks, not tests/docs)."""
    stems: list[str] = []
    seen: set[str] = set()
    for path in paths:
        if _is_meaningful_test_path(path) or _is_fixtures_path(path):
            continue
        if _is_docs_path(path) or _is_adr_path(path):
            continue
        if _is_changelog_path(path):
            continue
        lowered = _norm_path(path)
        # config/ci alone still surfaces as product-ish inventory when mixed
        if (
            not _is_runtime_surface_path(path)
            and not lowered.startswith("src/")
            and not lowered.startswith("scripts/")
            and not (_is_ci_path(path) or _is_build_path(path) or _is_hook_path(path) or _is_config_path(path))
        ):
            continue
        stem = PurePosixPath(path).stem
        key = stem.lower()
        if key in seen:
            continue
        seen.add(key)
        stems.append(stem)
    return stems


def _doc_surface_keys(paths: list[str]) -> list[tuple[str, str, str]]:
    """Return ordered (role, surface, note) triples for docs/ADR/fixtures surfaces."""
    out: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for path in paths:
        lowered = _norm_path(path)
        name = PurePosixPath(path).name.lower()
        if _is_fixtures_path(path):
            key = f"fixtures:{PurePosixPath(path).as_posix().lower()}"
            if key in seen:
                continue
            seen.add(key)
            note = "document fixture corpus"
            if any(tok in lowered for tok in ("gpg", "gpgsign", "signing", "no-gpg-sign")):
                note = "harden fixture GPG/signing setup"
            elif name == "readme.md":
                note = "document fixture README"
            out.append(("fixtures", "fixtures", note))
            continue
        if _is_adr_path(path):
            key = f"adr:{name}"
            if key in seen:
                continue
            seen.add(key)
            if name in {"index.md", "readme.md"}:
                note = "retarget ADR index links"
            elif name.startswith("adr-") or name[:4].isdigit():
                note = "document ADR decision path"
            else:
                note = "document ADR surface"
            out.append(("adr", "adr", note))
            continue
        if _is_docs_path(path) or _is_changelog_path(path):
            if name == "changelog.md":
                key = "docs:changelog"
                surface, note = "docs", "record changelog entry"
            elif name == "usage.md":
                key = "docs:usage"
                surface, note = "usage", "document operator usage"
            elif name == "development.md":
                key = "docs:development"
                surface, note = "docs", "document development guidance"
            else:
                key = f"docs:{name}"
                surface, note = "docs", f"document {PurePosixPath(path).stem} surface"
            if key in seen:
                continue
            seen.add(key)
            out.append(("docs", surface, note))
    return out


def _path_role_for_product_stem(stem: str) -> str:
    key = stem.lower().replace("-", "_")
    if key in {"telemetry"}:
        return "telemetry"
    if key in {"sentry_config", "sentry"}:
        return "sentry"
    if key in {"secrets", "secret"}:
        return "security"
    return "prod"


def _suggested_cc_for_role(
    role: str,
    *,
    tags: set[str],
    pure_docs_or_tests: bool,
) -> CommitType:
    """Pick a presentation-legal suggested cc_type for a stub role."""
    if role in {"test"}:
        return CommitType.TEST
    if role in {"docs", "adr", "fixtures"}:
        return CommitType.DOCS
    if pure_docs_or_tests:
        # Never seed feat/fix capability on pure test/docs/ADR inventories.
        return CommitType.TEST if role == "test" else CommitType.DOCS
    if tags & CORRECTNESS_CONCERN_TAGS:
        return CommitType.FIX
    if tags & DARK_LAUNCH_TAGS or tags & CARRY_THROUGH_TAGS:
        return CommitType.FEAT
    if role in {"telemetry", "sentry", "prod", "perf", "refactor", "security", "other"}:
        return CommitType.FIX if tags & CORRECTNESS_CONCERN_TAGS else CommitType.CHORE
    return CommitType.CHORE


def _scope_for_stub(role: str, surface: str, paths: list[str]) -> str | None:
    behaviour = _behaviour_scope_hint(paths)
    # Behaviour cross-wires prefer scoped-history over leaf module alone.
    if behaviour == "scoped-history" and role in {"prod", "test", "telemetry", "sentry", "perf", "refactor"}:
        return behaviour
    if role == "test":
        return behaviour or normalize_scope(surface if surface != "test" else "test")
    if role in {"docs", "adr", "fixtures"}:
        if role == "adr":
            return normalize_scope("adr")
        if role == "fixtures":
            return normalize_scope("fixtures")
        return normalize_scope(surface)
    if behaviour == "scoped-history" and surface in {
        "main",
        "scoped_history",
        "scoped-history",
        "semantic",
        "telemetry",
        "sentry_config",
        "sentry",
    }:
        return behaviour
    return normalize_scope(surface)


def build_included_change_stubs(
    paths: list[str],
    signals: DiffSignals | None = None,
    ranked_intents: list | None = None,
    *,
    concern_tags: frozenset[str] | set[str] | None = None,
    claim_tags: list[str] | tuple[str, ...] | None = None,
) -> list[Stub]:
    """Build deterministic Included-changes inventory stubs (D5 / D18 / §K).

    Returns prompt-inventory seeds only. Does **not** mutate ranked intents,
    invent feat/MINOR capability on pure tests/docs, or force junk secondaries
    on single-surface single-concern diffs.

    Thresholds (non-empty when any hold):
    * ≥2 test modules
    * ≥2 top-level doc/product surfaces
    * multi-concern product_src / mixed with concern tags
    * mixed prod+test (dual-surface)
    """
    del ranked_intents  # reserved for later matrix-legal secondary fill; unused in MVP
    clean = _resolve_paths(list(paths or []), signals)
    if not clean:
        return []

    tags = {t.lower() for t in (concern_tags or set())}
    claims = tuple(dict.fromkeys(str(c) for c in (claim_tags or ()) if c))
    dc = classify_diff_class(clean)
    pure_docs_or_tests = dc.name in {
        DIFF_CLASS_TESTS,
        DIFF_CLASS_FIXTURES,
        DIFF_CLASS_DOCS,
        DIFF_CLASS_ADR,
    } or (not dc.has_runtime_surface and dc.name != DIFF_CLASS_PRODUCT)

    test_modules = _test_module_stems(clean)
    product_modules = _product_module_stems(clean)
    doc_surfaces = _doc_surface_keys(clean)
    has_test = bool(test_modules)
    has_prod = bool(product_modules)
    has_docs = bool(doc_surfaces)

    # Surface / concern pressure gates (D5 thresholds).
    multi_test = len(test_modules) >= 2
    multi_doc = len(doc_surfaces) >= 2
    multi_prod = len(product_modules) >= 2
    dual_prod_test = has_prod and has_test
    multi_concern = len(tags) >= 2 and (has_prod or dc.name in {DIFF_CLASS_PRODUCT, DIFF_CLASS_MIXED})
    # Single fixture/docs/ADR path alone: allow one stub only when ≥2 doc surfaces
    # or mixed with tests; pure single-surface single-concern → empty (no junk).
    top_level_surfaces = int(has_test) + int(has_prod) + int(has_docs)
    pressure = multi_test or multi_doc or multi_prod or dual_prod_test or multi_concern or top_level_surfaces >= 2
    # Still emit claim-tag inventory on multi-module tests even if gate misfires.
    if not pressure and not (claims and multi_test):
        return []

    stubs: list[Stub] = []
    seen_keys: set[str] = set()

    def _add(stub: Stub) -> None:
        key = f"{stub.role}|{stub.surface}|{(stub.note or '').lower()}|{stub.suggested_cc_type.value}"
        if key in seen_keys:
            return
        # Dedup identical surface+role with empty note collisions
        soft = f"{stub.role}|{stub.surface}|{stub.suggested_cc_type.value}"
        if stub.note is None and any(k.startswith(soft + "|") for k in seen_keys):
            return
        seen_keys.add(key)
        stubs.append(stub)

    # --- Concern-tag seeds first (concrete D20 / correctness inventory) ---
    # Skip generic umbrella tags when more specific seeds exist.
    specific_tags = tags - {"correctness", "safety"}
    ordered_tags = sorted(specific_tags) + sorted(tags & {"correctness", "safety"})
    for tag in ordered_tags:
        seed = _CONCERN_STUB_SEEDS.get(tag)
        if seed is None:
            continue
        role, surface, note = seed
        if pure_docs_or_tests and role in {"prod", "telemetry", "sentry", "perf", "refactor", "security"}:
            # TIP-G8/G12: never seed runtime/fix capability on pure test/docs.
            continue
        # Carry-through / dark-launch must not invent Phase/product-as-actor notes.
        if tag in CARRY_THROUGH_TAGS or tag in {"elevation"}:
            note = "carry preflight counters through plan"
            role = "prod"
            surface = "scoped-history"
        cc = _suggested_cc_for_role(role, tags=tags, pure_docs_or_tests=pure_docs_or_tests)
        if pure_docs_or_tests and cc in {CommitType.FEAT, CommitType.FIX}:
            cc = CommitType.TEST if has_test else CommitType.DOCS
        scope = _scope_for_stub(role, surface, clean)
        _add(
            Stub(
                role=role,
                surface=normalize_scope(surface) or surface,
                suggested_cc_type=cc,
                scope=scope,
                note=note,
                source="concern",
            )
        )

    # --- Product module surfaces ---
    if has_prod and not pure_docs_or_tests:
        for stem in product_modules:
            role = _path_role_for_product_stem(stem)
            surface = normalize_scope(stem) or stem
            # Avoid duplicate generic prod stub when concern seeds already cover surface.
            if any(s.surface == surface and s.source == "concern" for s in stubs):
                continue
            cc = _suggested_cc_for_role(role, tags=tags, pure_docs_or_tests=False)
            note = f"cover {surface} behaviour"
            if stem.lower() in {"main"} and tags & CARRY_THROUGH_TAGS:
                note = "thread preflight groups through main"
            elif stem.lower() in {"semantic"} and tags & DARK_LAUNCH_TAGS:
                note = "add free-harvest semantic helpers"
            elif stem.lower() in {"telemetry"}:
                note = "cover telemetry producer path"
            elif stem.lower() in {"sentry_config", "sentry"}:
                note = "cover sentry scrub configuration"
            elif stem.lower() in {"scoped_history"}:
                note = "cover scoped-history producer path"
            _add(
                Stub(
                    role=role,
                    surface=surface,
                    suggested_cc_type=cc,
                    scope=_scope_for_stub(role, surface, clean),
                    note=note,
                    source="path",
                )
            )

    # --- Test modules (each major module is a concern atom) ---
    if has_test:
        claim_tuple = claims
        for stem in test_modules:
            surface = normalize_scope(stem.removeprefix("test_")) or stem
            # Prefer behaviour scope on scoped-history tests.
            scope = _scope_for_stub("test", surface, clean)
            note = f"cover {stem} suite"
            if claim_tuple and stem in {
                "test_scoped_history",
                "test_scoped_history_telemetry",
                "test_main",
                "test_semantic",
            }:
                # Attach claim tags once on the first matching suite only.
                pass
            _add(
                Stub(
                    role="test",
                    surface=surface,
                    suggested_cc_type=CommitType.TEST,
                    scope=scope,
                    note=note,
                    claim_tags=(),
                    source="path",
                )
            )
        if claim_tuple:
            # Single claim-tag inventory stub (TIP-G1) — not one per module.
            _add(
                Stub(
                    role="test",
                    surface=_behaviour_scope_hint(clean) or "scoped-history",
                    suggested_cc_type=CommitType.TEST,
                    scope=_behaviour_scope_hint(clean) or "scoped-history",
                    note="lock claim tags " + ",".join(claim_tuple[:3]),
                    claim_tags=claim_tuple[:8],
                    source="claim",
                )
            )

    # --- Docs / ADR / fixtures ---
    for role, surface, note in doc_surfaces:
        # TIP-G12 / pure docs: docs-only inventory; never fix/runtime recovery.
        cc = CommitType.DOCS
        _add(
            Stub(
                role=role,
                surface=normalize_scope(surface) or surface,
                suggested_cc_type=cc,
                scope=_scope_for_stub(role, surface, clean),
                note=note,
                source="path",
            )
        )

    # Signal-driven rename hint when moves_or_renames_files and no rename concern yet.
    if (
        signals is not None
        and getattr(signals, "moves_or_renames_files", False)
        and not pure_docs_or_tests
        and not any(s.note and "rename" in s.note for s in stubs)
    ):
        _add(
            Stub(
                role="prod",
                surface=_behaviour_scope_hint(clean) or "main",
                suggested_cc_type=CommitType.FIX if tags & CORRECTNESS_CONCERN_TAGS else CommitType.REFACTOR,
                scope=_scope_for_stub("prod", "main", clean),
                note="cover staged rename discovery",
                source="signal",
            )
        )

    # Final safety: strip feat/fix suggestions on pure docs/tests classes.
    if pure_docs_or_tests:
        safe: list[Stub] = []
        for s in stubs:
            cc = s.suggested_cc_type
            if cc in {CommitType.FEAT, CommitType.FIX, CommitType.PERF}:
                cc = CommitType.TEST if s.role == "test" else CommitType.DOCS
            if s.role in {"prod", "telemetry", "sentry", "perf", "refactor", "security"} and not has_prod:
                # Drop runtime stubs with no product paths.
                continue
            safe.append(
                Stub(
                    role=s.role,
                    surface=s.surface,
                    suggested_cc_type=cc,
                    scope=s.scope,
                    note=s.note,
                    claim_tags=s.claim_tags,
                    source=s.source,
                )
            )
        stubs = safe

    return stubs


def format_included_change_stub_inventory(stubs: list[Stub]) -> str:
    """Render stubs as a directive-free prompt inventory block (D5).

    LLM may rephrase descriptions; surfaces/roles/cardinality must remain covered.
    """
    if not stubs:
        return ""
    lines = [
        "INCLUDED-CHANGES INVENTORY (planning coverage only — not final commit bullets):",
        "Cover these surfaces via secondary_intents so the renderer emits exactly one Included changes section.",
        "Final nested items MUST be Hybrid mini-subjects: `- <emoji> <cc_type>(<scope>): <subject>`.",
        "Do not copy bracketed `[role/surface]` inventory syntax into body_summary or Included changes.",
        "Do not put an Included changes heading inside body_summary.",
    ]
    for stub in stubs:
        scope = f" scope={stub.scope}" if stub.scope else ""
        note = stub.note or f"cover {stub.surface}"
        claims = f" claims={','.join(stub.claim_tags)}" if stub.claim_tags else ""
        lines.append(f"- [{stub.role}/{stub.surface}] {stub.suggested_cc_type.value}{scope}: {note}{claims}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Slice 5 — Low-confidence presentation posture (D7)
# ---------------------------------------------------------------------------

# Trigger set is exactly the four existing v1 ranking-confidence reason codes.
# Import lazily-safe constants; keep a local frozenset so this module never
# becomes a second confidence policy owner.
LOW_CONFIDENCE_TRIGGER_REASONS: frozenset[str] = frozenset(
    {
        "margin_below_low_threshold",
        "mixed_intent",
        "near_tie_top3",
        "exact_tie_top",
    }
)

# Forced path-roles where TrailerPriors win presentation under Low confidence (D3/D7).
_LOW_CONFIDENCE_PRIOR_ROLES: frozenset[str] = frozenset(
    {
        "tests",
        "docs",
        "adr",
        "fixtures",
        "config_ci",
    }
)

# Closed presentation fallback vocabulary (D9 / D26). Slice 5 emits only
# ``none`` / ``low_confidence``; remaining values are reserved for later slices.
PRESENTATION_FALLBACK_NONE = "none"
PRESENTATION_FALLBACK_LOW_CONFIDENCE = "low_confidence"
PRESENTATION_FALLBACK_REASONS: frozenset[str] = frozenset(
    {
        PRESENTATION_FALLBACK_NONE,
        "error",
        "blueprint",
        "path_class_gate",
        "semver_ceiling",
        "type_dominance",
        "hallucination_guard",
        "craft_guard",
        "inventory_guard",
        PRESENTATION_FALLBACK_LOW_CONFIDENCE,
    }
)


@dataclass(frozen=True)
class PresentationAdjustment:
    """Immutable low-confidence presentation posture (D7 / D22).

    Presentation-only. Never carries ranked ``intent_id`` rewrites.
    """

    active: bool = False
    fallback_reason: str = PRESENTATION_FALLBACK_NONE
    seed_presentation: bool = False
    cc_type: CommitType | None = None
    semver_impact: SemVerImpact | None = None
    changelog_group: str | None = None
    scope_hint: str | None = None
    body_skeleton: str = ""
    role: str = "mixed"


def is_low_confidence_posture(confidence: RankingConfidence | None) -> bool:
    """Return whether ranking confidence triggers Slice 5 low posture (D7)."""
    if confidence is None:
        return False
    reasons = getattr(confidence, "reasons", None) or ()
    return bool(set(reasons) & LOW_CONFIDENCE_TRIGGER_REASONS)


def is_generic_feature_presentation(plan_or_seed: CommitPlan | None) -> bool:
    """Return whether *plan_or_seed* is generic ``feat`` + ``MINOR`` (D7 tests).

    ``None`` is treated as generic (no matrix-high presentation support yet).
    """
    if plan_or_seed is None:
        return True
    primary = getattr(plan_or_seed, "primary_intent", None)
    if primary is None:
        return True
    cc = getattr(primary, "cc_type", None)
    semver = getattr(primary, "semver_impact", None)
    cc_val = cc.value if isinstance(cc, CommitType) else str(cc or "").lower()
    sem_val = semver.value if isinstance(semver, SemVerImpact) else str(semver or "").upper()
    return cc_val == CommitType.FEAT.value and sem_val == SemVerImpact.MINOR.value


def strip_included_changes_from_body_summary(body_summary: str | None) -> str | None:
    """Remove any ``Included changes:`` block leaked into body_summary.

    Final Hybrid nested bullets are owned exclusively by ``secondary_intents``
    via ``CommitPlan.render``. Prompt skeletons and inventory must never become
    a second Included-changes section inside the prose body.
    """
    if body_summary is None:
        return None
    raw = str(body_summary).replace("\\n", "\n")
    if not raw.strip():
        return None

    # Drop from the first Included-changes heading through contiguous bullet lines.
    pattern = re.compile(
        r"(?:\n[ \t]*)?Included changes:[ \t]*\n"
        r"(?:[ \t]*- .*\n?)*"
        r"(?:[ \t]*\n)?",
        flags=re.IGNORECASE,
    )
    cleaned = pattern.sub("\n", raw)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned or None


def build_low_confidence_body_skeleton(
    *,
    priors: TrailerPriors | None = None,
    stubs: list[Stub] | None = None,
) -> str:
    """Build a deterministic Context / Changes body skeleton (D7).

    Directive-free wording structure for ``body_summary`` only. Never sets
    preferred_type or rank steers.

    Does **not** embed a final-message ``Included changes:`` block or any
    hyphen bullets intended for that section. Nested Hybrid mini-subjects are
    owned by ``secondary_intents`` / ``CommitPlan.render``. Inventory stub
    syntax (``[role/surface] ...``) must never be copied into the commit body.
    """
    del stubs  # inventory remains prompt-only via format_included_change_stub_inventory
    role = getattr(priors, "role", None) or "mixed"
    scope = getattr(priors, "scope_hint", None) or ""
    scope_bit = f" (scope hint: {scope})" if scope else ""

    lines = [
        "BODY_SUMMARY STRUCTURE ONLY (Context/Changes prose — never final Included changes):",
        "Context:",
        f"- Ranking confidence is low for role `{role}`{scope_bit}.",
        "- Describe only staged evidence; do not invent operator-visible capability.",
        "",
        "Changes:",
        "- Summarise the behaviour or documentation delta grounded in the diff.",
        "- Prefer failure-mode / outcome verbs over vague improve/enhance wording.",
        "",
        "Do NOT put an `Included changes:` heading inside body_summary.",
        "Do NOT emit plain prose bullets or bracketed inventory bullets under Included changes.",
        "Emit exactly one final Included changes section via secondary_intents only.",
        "Every Included changes item MUST be a Hybrid mini-subject:",
        "`- <emoji> <cc_type>(<scope>): <subject>`",
        "Convert each inventory stub into that Hybrid shape; never copy `[role/surface]` syntax.",
    ]
    return "\n".join(lines)


def format_low_confidence_guidance(adjustment: PresentationAdjustment) -> str:
    """Render Slice 5 prompt guidance from a presentation adjustment (D7).

    Returns an empty string when the posture is inactive.
    """
    if not adjustment.active or not adjustment.body_skeleton:
        return ""
    lines = [
        "LOW-CONFIDENCE BODY SKELETON (wording structure only — does not change intent_id / gitmoji authority):",
        "Structure body_summary with Context/Changes prose only. Use staged evidence only.",
        "Do not invent generic feat+MINOR capability framing under uncertainty.",
        "Emit exactly one `Included changes:` section in the final message, owned by "
        "secondary_intents (never duplicated inside body_summary).",
        "Every item under Included changes MUST be a Hybrid mini-subject: `- <emoji> <cc_type>(<scope>): <subject>`.",
        "Never emit plain prose bullets, bracketed inventory bullets, or a second `Included changes:` heading.",
    ]
    if adjustment.seed_presentation:
        cc = adjustment.cc_type.value if adjustment.cc_type is not None else "chore"
        sem = adjustment.semver_impact.value if adjustment.semver_impact is not None else "NONE"
        group = adjustment.changelog_group or "Miscellaneous"
        scope = adjustment.scope_hint or "(none)"
        lines.append(
            "Path-role presentation seed (presentation fields only): "
            f"cc_type={cc}, semver_impact={sem}, changelog_group={group}, scope_hint={scope}."
        )
        lines.append(
            "When the alternative would be generic feat+MINOR on a forced path role "
            "or unsupported feature framing, keep the seed above for presentation."
        )
    lines.append("")
    lines.append(adjustment.body_skeleton)
    lines.append("")
    lines.append(
        "This block guides body structure only. It MUST NOT change intent_id or gitmoji, "
        "MUST NOT set preferred_type, and is not a ranking override."
    )
    return "\n".join(lines)


def apply_low_confidence_presentation(
    plan_or_seed: CommitPlan | None,
    confidence: RankingConfidence | None,
    priors: TrailerPriors,
    *,
    stubs: list[Stub] | None = None,
) -> PresentationAdjustment:
    """Compute low-confidence presentation posture without mutating authority (D7).

    Never mutates ``plan_or_seed``, ranked intent ids, rank scores, or confidence.
    Does not call ``rank_commit_intents``.
    """
    if not is_low_confidence_posture(confidence):
        return PresentationAdjustment(role=getattr(priors, "role", "mixed") or "mixed")

    role = getattr(priors, "role", "mixed") or "mixed"
    skeleton = build_low_confidence_body_skeleton(priors=priors, stubs=stubs)
    forced_role = role in _LOW_CONFIDENCE_PRIOR_ROLES
    generic = is_generic_feature_presentation(plan_or_seed)

    if forced_role:
        # Path-class priors fully own presentation under Low confidence (D3/D7/D11).
        return PresentationAdjustment(
            active=True,
            fallback_reason=PRESENTATION_FALLBACK_LOW_CONFIDENCE,
            seed_presentation=True,
            cc_type=priors.cc_type,
            semver_impact=priors.semver_impact,
            changelog_group=priors.changelog_group,
            scope_hint=priors.scope_hint,
            body_skeleton=skeleton,
            role=role,
        )

    if generic:
        # Product/mixed generic feat+MINOR: eliminate unearned MINOR without forcing
        # soft chore type (dark-launch/carry-through may keep feat at PATCH).
        return PresentationAdjustment(
            active=True,
            fallback_reason=PRESENTATION_FALLBACK_LOW_CONFIDENCE,
            seed_presentation=True,
            cc_type=None,
            semver_impact=SemVerImpact.PATCH,
            changelog_group=None,
            scope_hint=priors.scope_hint,
            body_skeleton=skeleton,
            role=role,
        )

    # Low confidence but matrix presentation already non-generic — skeleton only.
    return PresentationAdjustment(
        active=True,
        fallback_reason=PRESENTATION_FALLBACK_LOW_CONFIDENCE,
        seed_presentation=False,
        body_skeleton=skeleton,
        role=role,
    )


# ---------------------------------------------------------------------------
# Presentation overlay — post-rank / post-LLM (presentation fields only)
# ---------------------------------------------------------------------------

_SEMVER_RANK: dict[str, int] = {
    SemVerImpact.NONE.value: 0,
    SemVerImpact.PATCH.value: 1,
    SemVerImpact.MINOR.value: 2,
    SemVerImpact.MAJOR.value: 3,
}

# Default gitmoji for presentation-forced cc_types when matrix row is unavailable.
_CC_TYPE_GITMOJI: dict[str, str] = {
    "test": "✅",
    "docs": "📝",
    "fix": "🐛",
    "feat": "✨",
    "chore": "🔧",
    "ci": "👷",
    "build": "📦",
    "refactor": "♻️",
    "perf": "⚡️",
    "style": "🎨",
    "revert": "⏪️",
}


def _clamp_semver(current: SemVerImpact | str, ceiling: SemVerImpact) -> SemVerImpact:
    """Return *current* capped at *ceiling* (presentation only)."""
    cur = SemVerImpact(str(current))
    if _SEMVER_RANK[cur.value] > _SEMVER_RANK[ceiling.value]:
        return ceiling
    return cur


def apply_presentation_seed(plan: CommitPlan, adjustment: PresentationAdjustment) -> CommitPlan:
    """Apply low-confidence presentation seed fields onto *plan* (D1/D7).

    Preserves ranked ``intent_id`` and matrix ``gitmoji``. Safe no-op when the
    adjustment is inactive. When active, always strips any leaked
    ``Included changes:`` block from ``body_summary`` so nested Hybrid bullets
    remain owned by ``secondary_intents`` / ``CommitPlan.render``.
    """
    if not adjustment.active:
        return plan

    cleaned_body = strip_included_changes_from_body_summary(plan.body_summary)
    if cleaned_body != plan.body_summary:
        plan = plan.model_copy(update={"body_summary": cleaned_body})

    if not adjustment.seed_presentation:
        return plan

    primary = plan.primary_intent
    preserved_intent_id = primary.intent_id
    preserved_gitmoji = primary.gitmoji

    if adjustment.cc_type is not None:
        primary.cc_type = adjustment.cc_type
    if adjustment.semver_impact is not None:
        primary.semver_impact = adjustment.semver_impact
        for sec in plan.secondary_intents:
            # Keep secondaries from outranking the seeded ceiling.
            sec.semver_impact = _clamp_semver(sec.semver_impact, adjustment.semver_impact)
    if adjustment.changelog_group:
        primary.changelog_group = adjustment.changelog_group
    if adjustment.scope_hint and not primary.scope:
        primary.scope = normalize_scope(adjustment.scope_hint)

    primary.intent_id = preserved_intent_id
    primary.gitmoji = preserved_gitmoji
    return plan


def _presentation_gitmoji_for(cc_type: CommitType | str, current: str) -> str:
    """Return gitmoji for *new* presentation secondaries only.

    Existing ranked/enforced intents keep their matrix gitmoji (D1 / identity).
    This helper is intentionally unused for primary/secondary rewrites.
    """
    key = str(cc_type).lower()
    return _CC_TYPE_GITMOJI.get(key, current)


# Stable matrix intent_ids used only as construction seeds for presentation
# secondaries. Matrix validator may rewrite changelog_group on init; callers
# always re-assign presentation fields after construction.
_CC_TYPE_SEED_INTENT: dict[str, str] = {
    "test": "tests_update",
    "docs": "documentation_update",
    "fix": "bug_fix",
    "feat": "feature_addition",
    "chore": "configuration_update",
    "ci": "configuration_update",
    "build": "configuration_update",
    "refactor": "configuration_update",
    "perf": "configuration_update",
    "style": "configuration_update",
    "revert": "configuration_update",
}


def _ensure_secondary_for_type(
    plan: CommitPlan,
    *,
    cc_type: CommitType,
    changelog_group: str,
    scope: str | None,
    description: str,
    semver: SemVerImpact = SemVerImpact.NONE,
) -> None:
    """Append a minimal secondary intent when a required type/group is missing."""
    from git_cg.models import CommitIntent

    existing_types = {plan.primary_intent.cc_type.value, *(s.cc_type.value for s in plan.secondary_intents)}
    if cc_type.value in existing_types:
        # Repair changelog group on the matching intent if needed.
        if plan.primary_intent.cc_type == cc_type:
            plan.primary_intent.changelog_group = changelog_group
        for sec in plan.secondary_intents:
            if sec.cc_type == cc_type:
                sec.changelog_group = changelog_group
                sec.semver_impact = semver
        return

    seed_id = _CC_TYPE_SEED_INTENT.get(cc_type.value, "configuration_update")
    sec = CommitIntent(
        intent_id=seed_id,
        gitmoji=_CC_TYPE_GITMOJI.get(cc_type.value, "🔧"),
        cc_type=cc_type,
        scope=normalize_scope(scope) if scope else scope,
        description=description[:50],
        semver_impact=semver,
        changelog_group=changelog_group,
    )
    # Matrix validator may reset presentation fields to SOP row defaults —
    # re-assert presentation fields. New secondaries may use type-default gitmoji
    # (they are presentation inventory, not ranked identity). Existing matched
    # secondaries keep their gitmoji above.
    sec.cc_type = cc_type
    sec.semver_impact = semver
    sec.changelog_group = changelog_group
    if scope:
        sec.scope = normalize_scope(scope)
    plan.secondary_intents.append(sec)


def apply_presentation_overlay(
    plan: CommitPlan,
    *,
    paths: list[str] | None = None,
    signals: DiffSignals | None = None,
    priors: TrailerPriors | None = None,
    constraints: PresentationConstraints | None = None,
    concern_tags: frozenset[str] | set[str] | None = None,
    evidence_text: str = "",
    active_directives: dict[str, str] | None = None,
) -> CommitPlan:
    """Apply path-class / SemVer / type / changelog presentation overlays to *plan*.

    Presentation-only. **Never** mutates ``primary_intent.intent_id`` (D1) and must
    not call ``rank_commit_intents``. Safe to run after ``enforce_semantic_contract``.

    Precedence (D4 / Approval locks):
    path-class force/forbid → SemVer ceiling → type dominance → scope hints →
    changelog↔types allowlist repair → cardinality floor + stub inventory (D5/D18).
    """
    clean = _resolve_paths(list(paths or []), signals)
    tags = {t.lower() for t in (concern_tags or set())}
    base_priors = priors or derive_trailer_priors(clean, signals=signals)
    cons = constraints or presentation_constraints(classify_diff_class(clean))
    ceiling = semver_presentation_ceiling(
        clean,
        signals,
        concern_tags=tags,
        evidence_text=evidence_text,
    )
    # Path-class force_semver is a hard presentation lock (usually NONE).
    if cons.force_semver is not None:
        # Take the more restrictive of force_semver and computed ceiling.
        if _SEMVER_RANK[cons.force_semver.value] <= _SEMVER_RANK[ceiling.value]:
            ceiling = cons.force_semver
        else:
            # force asks higher than evidence ceiling — still honour evidence ceiling.
            pass

    primary = plan.primary_intent
    # Preserve ranked/locked identity — never rewrite intent_id or gitmoji.
    preserved_intent_id = primary.intent_id
    preserved_gitmoji = primary.gitmoji

    # --- 1. Primary type force / dominance (D11 / D17) ---
    forced_type = cons.force_cc_type
    if forced_type is None:
        forced_type = dominant_presentation_cc_type(
            clean,
            signals=signals,
            concern_tags=tags,
            priors=base_priors,
        )

    if forced_type is not None:
        primary.cc_type = forced_type
        # Identity lock: never rewrite ranked/enforced gitmoji (presentation owns
        # cc_type/SemVer/changelog/scope only).
        if cons.force_changelog_group is not None:
            primary.changelog_group = cons.force_changelog_group
        else:
            mapped = _TYPE_CHANGELOG_REQUIREMENTS.get(forced_type.value)
            if mapped:
                primary.changelog_group = mapped
        # Carry-through / stub-wiring feat is Changed-led, not Added-led (TIP-G11).
        if forced_type == CommitType.FEAT and tags & CARRY_THROUGH_TAGS:
            primary.changelog_group = "Changed"

    # Carry-through feat without a forced type still uses Changed presentation group.
    if primary.cc_type == CommitType.FEAT and tags & CARRY_THROUGH_TAGS:
        primary.changelog_group = "Changed"

    # Forbid illegal primary types (path-class).
    if primary.cc_type.value in cons.forbid_cc_types:
        fallback = cons.force_cc_type or base_priors.cc_type
        primary.cc_type = fallback
        if cons.force_changelog_group is not None:
            primary.changelog_group = cons.force_changelog_group
        else:
            mapped = _TYPE_CHANGELOG_REQUIREMENTS.get(fallback.value)
            if mapped:
                primary.changelog_group = mapped

    # Security primary forbid without path evidence (D13) — demote framing only.
    if cons.forbid_security_primary and (
        primary.changelog_group.lower() == "security" or primary.gitmoji in {"🔐", "🔒️"}
    ):
        if cons.force_cc_type is not None:
            primary.cc_type = cons.force_cc_type
        primary.changelog_group = cons.force_changelog_group or _TYPE_CHANGELOG_REQUIREMENTS.get(
            primary.cc_type.value, "Miscellaneous"
        )
        # Keep matrix gitmoji even when demoting Security framing; presentation
        # may change changelog_group/cc_type only.

    # --- 2. SemVer ceiling on primary + secondaries (D16) ---
    if cons.force_semver is not None:
        primary.semver_impact = cons.force_semver
    else:
        primary.semver_impact = _clamp_semver(primary.semver_impact, ceiling)
    for sec in plan.secondary_intents:
        if cons.force_semver is not None:
            sec.semver_impact = cons.force_semver
        else:
            sec.semver_impact = _clamp_semver(sec.semver_impact, ceiling)

    # --- 3. Scope (D11 force_scope / priors hint / directive) ---
    # Order (Approval locks §J simplified): force_scope > preferred_scope >
    # existing normalised scope > priors.scope_hint
    if cons.force_scope is not None:
        primary.scope = normalize_scope(cons.force_scope)
    elif active_directives and "preferred_scope" in active_directives:
        primary.scope = normalize_scope(active_directives["preferred_scope"])
    elif primary.scope:
        primary.scope = normalize_scope(primary.scope)
    elif base_priors.scope_hint:
        primary.scope = normalize_scope(base_priors.scope_hint)

    for sec in plan.secondary_intents:
        if sec.scope:
            sec.scope = normalize_scope(sec.scope)

    # --- 4. Changelog ↔ Change-Types allowlist repair (D19) ---
    change_types = [primary.cc_type.value, *(s.cc_type.value for s in plan.secondary_intents)]
    groups = [primary.changelog_group, *(s.changelog_group for s in plan.secondary_intents)]
    if not changelog_groups_allowlisted(change_types, groups, primary_cc_type=primary.cc_type):
        primary_req = _TYPE_CHANGELOG_REQUIREMENTS.get(primary.cc_type.value)
        if primary_req and not (
            primary.cc_type == CommitType.FEAT and primary.changelog_group == "Changed" and tags & CARRY_THROUGH_TAGS
        ):
            # Preserve carry-through Changed presentation for feat plumbing.
            primary.changelog_group = primary_req
        for sec in plan.secondary_intents:
            sec_req = _TYPE_CHANGELOG_REQUIREMENTS.get(sec.cc_type.value)
            if sec_req:
                sec.changelog_group = sec_req
        # Recompute and inject missing required groups as secondaries.
        change_types = [primary.cc_type.value, *(s.cc_type.value for s in plan.secondary_intents)]
        groups = [primary.changelog_group, *(s.changelog_group for s in plan.secondary_intents)]
        still_required = [
            g for g in required_changelog_groups(change_types, primary_cc_type=primary.cc_type) if g not in groups
        ]
        for group in still_required:
            type_for_group = next(
                (t for t, g in _TYPE_CHANGELOG_REQUIREMENTS.items() if g == group),
                "chore",
            )
            _ensure_secondary_for_type(
                plan,
                cc_type=CommitType(type_for_group),
                changelog_group=group,
                scope="test" if type_for_group == "test" else primary.scope,
                description=f"cover {group.lower()} surface",
                semver=SemVerImpact.NONE if cons.force_semver is None else cons.force_semver,
            )

    # Pure tests/docs force_group always wins on primary.
    if cons.force_changelog_group is not None and cons.force_cc_type is not None:
        primary.changelog_group = cons.force_changelog_group

    # Re-assert carry-through Changed after allowlist/force repairs (TIP-G11).
    if primary.cc_type == CommitType.FEAT and tags & CARRY_THROUGH_TAGS:
        primary.changelog_group = "Changed"

    # --- 5. Light cardinality floor (D18) + surface type coverage ---
    # Ensure required presentation types/groups for surfaces. Do not synthesise
    # repeated concern secondaries (TIP-G5/G7 junk inventory). Concrete stub
    # inventory is prompt-side via build_included_change_stubs (D5 lean default).
    min_bullets = min_included_change_bullets(clean, concern_tags=tags)
    has_test = any(_is_meaningful_test_path(p) for p in clean)
    has_docs = any((_is_docs_path(p) or _is_adr_path(p)) and not _is_fixtures_path(p) for p in clean)
    has_fixtures = any(_is_fixtures_path(p) for p in clean)
    present_types = {primary.cc_type.value, *(s.cc_type.value for s in plan.secondary_intents)}

    if has_test and "test" not in present_types:
        test_scope = _behaviour_scope_hint(clean) or "test"
        _ensure_secondary_for_type(
            plan,
            cc_type=CommitType.TEST,
            changelog_group="Tests",
            scope=test_scope,
            description="cover behaviour with tests",
            semver=SemVerImpact.NONE if cons.force_semver is None else cons.force_semver,
        )
        present_types.add("test")
    if (has_docs or has_fixtures) and "docs" not in present_types and primary.cc_type != CommitType.DOCS:
        _ensure_secondary_for_type(
            plan,
            cc_type=CommitType.DOCS,
            changelog_group="Documentation",
            scope=_docs_scope_hint(clean) or ("fixtures" if has_fixtures else "docs"),
            description="document the change",
            semver=SemVerImpact.NONE if cons.force_semver is None else cons.force_semver,
        )
        present_types.add("docs")

    # Cardinality floor retained for callers/tests; stub materialisation is
    # prompt inventory (format_included_change_stub_inventory), not silent
    # secondary invention that fights split_recommended.
    _ = min_bullets

    # Final SemVer re-clamp after any secondary injection.
    if cons.force_semver is not None:
        primary.semver_impact = cons.force_semver
        for sec in plan.secondary_intents:
            sec.semver_impact = cons.force_semver
    else:
        primary.semver_impact = _clamp_semver(primary.semver_impact, ceiling)
        for sec in plan.secondary_intents:
            sec.semver_impact = _clamp_semver(sec.semver_impact, ceiling)

    # Identity invariant (D1): ranked intent_id + matrix gitmoji stay put.
    primary.intent_id = preserved_intent_id
    primary.gitmoji = preserved_gitmoji
    return plan
