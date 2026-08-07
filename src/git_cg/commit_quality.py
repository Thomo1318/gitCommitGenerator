"""Pure presentation-quality policy (Issue #204 · Phase 7.30).

Owns path-role TrailerPriors, diff-class gates, SemVer/type ceilings,
craft/hallucination/inventory guards, claim-tag harvest, and blueprint apply helpers.

Authority boundaries:
* Matrix ranker remains sole ranking / SemVer / intent authority.
* This module must not call ``rank_commit_intents`` or mutate rank scores.
* No git I/O, LLM calls, or hook interactivity.
* Reuses intent path classifiers and gold ``_file_groups`` — does not fork them.
* ``scope_canon`` may be imported; gold may consume outputs of this module.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from git_cg.commit_gold import BANNED_BODY_OPENERS, _file_groups, _is_title_case_subject
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
from git_cg.models import (
    CommitBlueprint,
    CommitType,
    SemVerImpact,
    TrailerPriors,
)
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

# Package/root and epic-noun scopes are never final when a module/behaviour
# slug dominates (V12-A26 / TIP-G7 / TIP-G16 / Session 6 module-scope law).
INVALID_FINAL_SCOPES: frozenset[str] = frozenset(
    {
        "git_cg",
        "git-cg",
        "src",
        "commit-plan",
        "commit_plan",
        "lifecycle",
        "contract-lifecycle",
        "contract_lifecycle",
    }
)


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
    hits: list[str] = []
    for tok in sorted(SECURITY_CLAIM_TOKENS, key=len, reverse=True):
        matched = tok in lowered if " " in tok else re.search(rf"\b{re.escape(tok)}\b", lowered) is not None
        if not matched:
            continue
        # Prefer longer token; skip shorter token fully covered by an already-hit longer one.
        if any(tok != prev and tok in prev for prev in hits):
            continue
        hits.append(tok)
    return sorted(hits)


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

# Operator-visible capability / schema-add tags → feat presentation when not
# correctness-dominated (Session 6 / TIP-G13 · V12-A39).
CAPABILITY_CONCERN_TAGS: frozenset[str] = frozenset(
    {
        "new_capability",
        "operator_visible_capability",
        "lifecycle_fields",
        "schema_add",
        "score_boundary",
        "telemetry_schema",
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
    # (MINOR only when explicit operator-visible / schema-add capability tags fire).
    if tags & CAPABILITY_CONCERN_TAGS:
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

    # Schema/capability adds on product paths → feat over fix/chore validate framing
    # (Session 6 / TIP-G13). Correctness tags above still win when both present.
    if tags & CAPABILITY_CONCERN_TAGS and base.role in {"product_src", "mixed"}:
        return CommitType.FEAT

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
# Slice 6 — Contract-aware high-risk body checklist (D6 / D20)
# ---------------------------------------------------------------------------

# Exact high-risk product paths (Slice 6 MVP). Basename/suffix matchers below
# keep fixtures and nested copies aligned without treating docs prose as evidence.
HIGH_RISK_PATH_EXACT: frozenset[str] = frozenset(
    {
        "src/git_cg/main.py",
        "src/git_cg/telemetry.py",
        "src/git_cg/sentry_config.py",
        "src/git_cg/scoped_history.py",
        "src/git_cg/intent.py",
        "src/git_cg/regeneration.py",
        "src/git_cg/secrets.py",
    }
)

HIGH_RISK_PATH_SUFFIXES: tuple[str, ...] = (
    "/main.py",
    "/telemetry.py",
    "/sentry_config.py",
    "/scoped_history.py",
    "/intent.py",
    "/regeneration.py",
    "/secrets.py",
)

# Closed surface keys used for theme selection (presentation-only).
HIGH_RISK_SURFACE_MAIN = "main"
HIGH_RISK_SURFACE_TELEMETRY = "telemetry"
HIGH_RISK_SURFACE_SENTRY = "sentry_config"
HIGH_RISK_SURFACE_SCOPED_HISTORY = "scoped_history"
HIGH_RISK_SURFACE_INTENT = "intent"
HIGH_RISK_SURFACE_REGENERATION = "regeneration"
HIGH_RISK_SURFACE_SECRETS = "secrets"

_HIGH_RISK_BASENAME_TO_SURFACE: dict[str, str] = {
    "main.py": HIGH_RISK_SURFACE_MAIN,
    "telemetry.py": HIGH_RISK_SURFACE_TELEMETRY,
    "sentry_config.py": HIGH_RISK_SURFACE_SENTRY,
    "scoped_history.py": HIGH_RISK_SURFACE_SCOPED_HISTORY,
    "intent.py": HIGH_RISK_SURFACE_INTENT,
    "regeneration.py": HIGH_RISK_SURFACE_REGENERATION,
    "secrets.py": HIGH_RISK_SURFACE_SECRETS,
}

# Stable theme ids → directive-free must-cover bullets (D6/D20).
# Wording deliberately avoids preferred_type / rank steers and Channel-4
# directive verbs (consider whether / prefer / must / should as steers).
_HIGH_RISK_THEME_BULLETS: dict[str, str] = {
    "telemetry_fallback_transitions": (
        "fallback-reason transitions, including overwrite of a pre-populated `none` "
        "when a later stage observes a real error or presentation fallback"
    ),
    "telemetry_closed_enum_tags": (
        "closed-enum / closed-vocabulary tags skip free-text redaction paths; "
        "hash-only or enum tags stay in the closed set"
    ),
    "telemetry_scrub_list_deltas": ("scrub allow/deny and frame-variable list deltas when redaction coverage changes"),
    "telemetry_redaction_failure_token": (
        "redaction failure yields the literal token `[REDACTED]`, never Python `None` or an empty stand-in"
    ),
    "telemetry_no_secret_leakage": (
        "no secret material, tokens, or raw plan-bearing locals in telemetry/Sentry payloads"
    ),
    "main_channel4_directive_free": (
        "Channel-4 / scoped-history guidance stays directive-free: no `consider whether`, "
        "prefer/must/should steers, and no `preferred_type` from the scoped-history channel"
    ),
    "main_fallback_error_visibility": (
        "graph/outer-stage fallback does not mask real errors as presentation fallback reason `none`"
    ),
    "scoped_history_policy_b_lifetime": (
        "Policy B shadow lifetime spans refresh and stats/product collection; flag-off defaults remain explicit"
    ),
    "intent_closed_enrichment_markers": (
        "intent enrichment uses closed markers only; presentation pressure is not a second ranker"
    ),
    "regeneration_contract_lock_visibility": (
        "regeneration / contract-lock fallthrough remains visible; lock rejection is not silent success"
    ),
    "secrets_path_handling": (
        "secrets-path handling never treats docs/ADR mentions of authority or redaction as security path evidence"
    ),
}

_SURFACE_THEMES: dict[str, tuple[str, ...]] = {
    HIGH_RISK_SURFACE_TELEMETRY: (
        "telemetry_fallback_transitions",
        "telemetry_closed_enum_tags",
        "telemetry_scrub_list_deltas",
        "telemetry_redaction_failure_token",
        "telemetry_no_secret_leakage",
    ),
    HIGH_RISK_SURFACE_SENTRY: (
        "telemetry_closed_enum_tags",
        "telemetry_scrub_list_deltas",
        "telemetry_redaction_failure_token",
        "telemetry_no_secret_leakage",
    ),
    HIGH_RISK_SURFACE_MAIN: (
        "main_channel4_directive_free",
        "main_fallback_error_visibility",
        "telemetry_fallback_transitions",
        "telemetry_closed_enum_tags",
        "telemetry_redaction_failure_token",
    ),
    HIGH_RISK_SURFACE_SCOPED_HISTORY: (
        "scoped_history_policy_b_lifetime",
        "main_channel4_directive_free",
        "main_fallback_error_visibility",
    ),
    HIGH_RISK_SURFACE_INTENT: ("intent_closed_enrichment_markers",),
    HIGH_RISK_SURFACE_REGENERATION: (
        "regeneration_contract_lock_visibility",
        "main_channel4_directive_free",
    ),
    HIGH_RISK_SURFACE_SECRETS: (
        "secrets_path_handling",
        "telemetry_no_secret_leakage",
    ),
}


def _high_risk_surface_for_path(path: str) -> str | None:
    """Return closed high-risk surface key for *path*, or None.

    Matches exact product paths, ``*/<basename>`` suffixes, bare basenames
    used in unit fixtures, and ``git_cg/<basename>`` package-relative forms.
    Docs/ADR prose paths are not security evidence (D13) and only match when
    the path itself is one of the closed high-risk modules.
    """
    norm = _norm_path(path).lstrip("./")
    if not norm:
        return None

    base = PurePosixPath(norm).name
    surface = _HIGH_RISK_BASENAME_TO_SURFACE.get(base)
    if surface is None:
        return None

    if norm in HIGH_RISK_PATH_EXACT:
        return surface
    if any(norm.endswith(suffix) for suffix in HIGH_RISK_PATH_SUFFIXES):
        return surface
    # Bare basename fixtures (e.g. ``telemetry.py`` in unit tests).
    if "/" not in norm:
        return surface
    # Package-relative forms without src/ prefix.
    if norm.startswith("git_cg/") or "/git_cg/" in f"/{norm}":
        return surface
    return None


def detect_high_risk_surfaces(paths: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    """Return sorted unique high-risk surface keys present in *paths* (D6)."""
    found: set[str] = set()
    for raw in paths or ():
        if not raw or not str(raw).strip():
            continue
        surface = _high_risk_surface_for_path(str(raw))
        if surface:
            found.add(surface)
    return tuple(sorted(found))


def is_high_risk_path_set(paths: list[str] | tuple[str, ...] | None) -> bool:
    """Return whether any staged path is a Slice 6 high-risk surface."""
    return bool(detect_high_risk_surfaces(paths))


def build_high_risk_checklist_themes(
    paths: list[str] | tuple[str, ...] | None,
) -> tuple[str, ...]:
    """Map staged paths → ordered unique must-cover theme ids (D6/D20).

    Presentation-only. Does not inspect hunk prose and does not treat
    docs/ADR mentions as security path evidence (D13).
    """
    themes: list[str] = []
    seen: set[str] = set()
    for surface in detect_high_risk_surfaces(paths):
        for theme_id in _SURFACE_THEMES.get(surface, ()):
            if theme_id in seen:
                continue
            if theme_id not in _HIGH_RISK_THEME_BULLETS:
                continue
            seen.add(theme_id)
            themes.append(theme_id)
    return tuple(themes)


def format_high_risk_body_checklist(
    paths: list[str] | tuple[str, ...] | None = None,
    *,
    themes: tuple[str, ...] | list[str] | None = None,
) -> str:
    """Render directive-free high-risk must-cover checklist for the prompt (D6).

    Returns empty string when no high-risk surfaces are present. Checklist
    language must never set ``preferred_type`` or rank steers (Channel-4).
    """
    theme_ids = tuple(themes) if themes is not None else build_high_risk_checklist_themes(paths)
    if not theme_ids:
        return ""

    surfaces = detect_high_risk_surfaces(paths) if paths is not None else ()
    surface_bit = f" surfaces={','.join(surfaces)}" if surfaces else ""

    lines = [
        "HIGH-RISK BODY CHECKLIST (must-cover themes — wording pressure only):",
        f"Staged high-risk paths require body coverage of the themes below{surface_bit}.",
        "Cover each applicable theme in body_summary and/or Hybrid Included-changes mini-subjects.",
        "This block is presentation pressure only. It does not change intent_id, gitmoji,",
        "cc_type, semver_impact, or changelog_group authority, does not set preferred_type,",
        "and is not a ranking override.",
    ]
    for theme_id in theme_ids:
        bullet = _HIGH_RISK_THEME_BULLETS.get(theme_id)
        if not bullet:
            continue
        lines.append(f"- [{theme_id}] {bullet}")
    lines.append(
        "Omit themes that have no staged evidence. Do not invent secrets, credentials, "
        "or runtime claims from docs/ADR prose alone."
    )
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
    """Return whether *plan_or_seed* is generic ``feat`` presentation (D7 tests).

    Generic means ``feat`` paired with ``MINOR`` or ``NONE``. ``NONE`` is
    included because the model may over-demote SemVer after reading the
    low-confidence guidance; the presentation seed then repairs it to the
    deterministic ``PATCH`` posture. ``None`` is treated as generic (no
    matrix-high presentation support yet).
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
    return cc_val == CommitType.FEAT.value and sem_val in {
        SemVerImpact.MINOR.value,
        SemVerImpact.NONE.value,
    }


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
        "Do not choose NONE merely because ranking confidence is low; the presentation "
        "layer applies the deterministic SemVer posture.",
        "For every distinct evidence-backed staged responsibility (test, docs, fix, "
        "implementation), keep a corresponding secondary_intent; do not collapse a "
        "multi-surface diff into one intent solely because confidence is low.",
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
    # Package/root and epic-noun scopes never final when module/behaviour dominates.
    if cons.force_scope is not None:
        primary.scope = normalize_scope(cons.force_scope)
    elif active_directives and "preferred_scope" in active_directives:
        primary.scope = normalize_scope(active_directives["preferred_scope"])
    elif primary.scope:
        primary.scope = normalize_scope(primary.scope)
    elif base_priors.scope_hint:
        primary.scope = normalize_scope(base_priors.scope_hint)

    scope_now = normalize_scope(primary.scope) if primary.scope else None
    raw_scope = str(primary.scope or "").lower().replace("_", "-")
    if scope_now in INVALID_FINAL_SCOPES or raw_scope in INVALID_FINAL_SCOPES:
        replacement = None
        if cons.force_scope is not None:
            cand = normalize_scope(cons.force_scope)
            if cand not in INVALID_FINAL_SCOPES:
                replacement = cand
        if replacement is None and active_directives and "preferred_scope" in active_directives:
            cand = normalize_scope(active_directives["preferred_scope"])
            if cand not in INVALID_FINAL_SCOPES:
                replacement = cand
        if replacement is None and base_priors.scope_hint:
            cand = normalize_scope(base_priors.scope_hint)
            if cand not in INVALID_FINAL_SCOPES:
                replacement = cand
        if replacement is None:
            # Prefer a single dominant product module; only then behaviour slug
            # derived from product paths (ignore test/docs filename tokens).
            replacement = _dominant_product_scope(clean)
        if replacement is None:
            product_only = [
                p for p in clean if not _is_test_path(p) and not _is_docs_path(p) and not _is_fixtures_path(p)
            ]
            replacement = _behaviour_scope_hint(product_only or clean)
        if replacement is None:
            # Tests/docs-only residual: prefer behaviour slug, else test/docs hint.
            replacement = _behaviour_scope_hint(clean)
            if replacement is None:
                roles = _classify_path_roles(clean)
                if "tests" in roles:
                    replacement = "test"
                elif "adr" in roles:
                    replacement = "adr"
                elif "docs" in roles:
                    replacement = _docs_scope_hint(clean) or "docs"
                elif "fixtures" in roles:
                    replacement = "fixtures"
        if replacement and normalize_scope(replacement) not in INVALID_FINAL_SCOPES:
            primary.scope = normalize_scope(replacement)

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


# ---------------------------------------------------------------------------
# Slice 7 — CommitBlueprint parse / validate / apply (Issue #204 · §I / D23)
# ---------------------------------------------------------------------------

BLUEPRINT_MAX_BYTES = 64 * 1024

PRESENTATION_FALLBACK_ERROR = "error"
PRESENTATION_FALLBACK_BLUEPRINT = "blueprint"


class BlueprintError(ValueError):
    """Operator blueprint parse / IO / legality failure (Issue #204 · D23).

    Raised for hard-fail paths. CLI boundary maps this to ``typer.Exit(code=2)``
    when the invocation is interactive/standalone; hook / non-TTY paths catch it
    and fall closed to deterministic priors.
    """

    def __init__(self, message: str, *, kind: str = "blueprint") -> None:
        super().__init__(message)
        self.kind = kind  # "blueprint" | "error" (parse/IO)


@dataclass(frozen=True)
class PresentationState:
    """Frozen presentation snapshot for pure blueprint apply (D22 internal).

    Holds the mutable ``CommitPlan`` reference plus closed telemetry flags.
    Policy helpers never mutate ranked ``intent_id``.
    """

    plan: object  # CommitPlan (runtime); typed loosely to avoid import cycles
    blueprint_applied: bool = False
    fallback_reason: str = PRESENTATION_FALLBACK_NONE
    subject_hint: str | None = None
    body_skeleton: tuple[str, ...] = ()


def load_blueprint_source(
    raw: str,
    *,
    repo_root: str | os.PathLike[str] | None = None,
    cwd: str | os.PathLike[str] | None = None,
) -> tuple[dict, str]:
    """Load blueprint JSON from inline text or ``@path`` (Approval locks §I).

    Returns ``(payload_dict, source_label)``. Never returns raw file bytes to
    callers beyond the parsed object. Enforces local regular file, 64 KiB cap,
    and path-escape rejection relative to *repo_root* (preferred) or *cwd*.
    """
    if raw is None:
        raise BlueprintError("blueprint source is required", kind="error")
    text = str(raw).strip()
    if not text:
        raise BlueprintError("blueprint source is empty", kind="error")

    if text.startswith("@"):
        rel = text[1:].strip()
        if not rel:
            raise BlueprintError("blueprint @path is empty", kind="error")
        # Reject obvious escapes / NUL before resolution.
        if "\x00" in rel:
            raise BlueprintError("blueprint path contains NUL", kind="error")
        base = Path(repo_root) if repo_root is not None else Path(cwd or os.getcwd())
        try:
            base_resolved = base.resolve(strict=True)
        except OSError as exc:
            raise BlueprintError(f"blueprint root unreadable: {type(exc).__name__}", kind="error") from exc
        candidate = Path(rel)
        if not candidate.is_absolute():
            candidate = Path(cwd or os.getcwd()) / candidate
        try:
            # Do not follow the final path via open until containment is proven.
            # resolve(strict=True) canonicalises symlink targets for the root check.
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise BlueprintError(f"blueprint file not found or unreadable: {type(exc).__name__}", kind="error") from exc
        try:
            resolved.relative_to(base_resolved)
        except ValueError as exc:
            raise BlueprintError("blueprint path escapes repository root", kind="error") from exc
        # Reject non-files (dirs, devices). Symlinks are allowed only when the
        # resolved target remains inside the repository root (checked above).
        if not resolved.is_file():
            raise BlueprintError("blueprint path must be a local regular file", kind="error")
        # Also reject if the user-supplied path is a symlink whose *immediate*
        # link target (before full resolve) points outside root — belt-and-braces
        # for platforms where resolve behaviour differs.
        check_path = candidate
        if check_path.is_symlink():
            try:
                link_target = check_path.readlink()
                abs_link = (check_path.parent / link_target).resolve(strict=False)
                abs_link.relative_to(base_resolved)
            except (OSError, ValueError) as exc:
                raise BlueprintError("blueprint symlink escapes repository root", kind="error") from exc
        try:
            size = resolved.stat().st_size
        except OSError as exc:
            raise BlueprintError(f"blueprint stat failed: {type(exc).__name__}", kind="error") from exc
        if size > BLUEPRINT_MAX_BYTES:
            raise BlueprintError(
                f"blueprint file exceeds {BLUEPRINT_MAX_BYTES} bytes",
                kind="error",
            )
        try:
            payload_text = resolved.read_text(encoding="utf-8")
        except OSError as exc:
            raise BlueprintError(f"blueprint read failed: {type(exc).__name__}", kind="error") from exc
        if len(payload_text.encode("utf-8")) > BLUEPRINT_MAX_BYTES:
            raise BlueprintError(
                f"blueprint payload exceeds {BLUEPRINT_MAX_BYTES} bytes",
                kind="error",
            )
        source_label = "file"
    else:
        payload_text = text
        if len(payload_text.encode("utf-8")) > BLUEPRINT_MAX_BYTES:
            raise BlueprintError(
                f"blueprint payload exceeds {BLUEPRINT_MAX_BYTES} bytes",
                kind="error",
            )
        source_label = "inline"

    try:
        data = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise BlueprintError(f"blueprint JSON parse error: {exc.msg}", kind="error") from exc
    if not isinstance(data, dict):
        raise BlueprintError("blueprint JSON must be an object", kind="error")
    return data, source_label


def parse_commit_blueprint(
    raw: str | dict | CommitBlueprint,
    *,
    repo_root: str | os.PathLike[str] | None = None,
    cwd: str | os.PathLike[str] | None = None,
) -> CommitBlueprint:
    """Parse and schema-validate a CommitBlueprint (strict; unknown keys rejected)."""
    if isinstance(raw, CommitBlueprint):
        return raw
    if isinstance(raw, dict):
        data = raw
    else:
        data, _src = load_blueprint_source(str(raw), repo_root=repo_root, cwd=cwd)
    try:
        return CommitBlueprint.model_validate(data)
    except Exception as exc:  # pydantic ValidationError
        raise BlueprintError(f"blueprint schema invalid: {exc}", kind="blueprint") from exc


def validate_blueprint_against_constraints(
    blueprint: CommitBlueprint,
    constraints: PresentationConstraints,
    *,
    ceiling: SemVerImpact | None = None,
) -> None:
    """Hard-fail when blueprint violates path-class force/forbid or D16 ceilings.

    Raises:
        BlueprintError: illegal combination (kind=``blueprint``).
    """
    # Primary type legality
    if blueprint.cc_type is not None:
        cc = blueprint.cc_type.value
        if cc in constraints.forbid_cc_types:
            raise BlueprintError(
                f"blueprint cc_type {cc!r} forbidden by path-class gate {constraints.diff_class!r}",
                kind="blueprint",
            )
        if constraints.force_cc_type is not None and blueprint.cc_type != constraints.force_cc_type:
            raise BlueprintError(
                f"blueprint cc_type {cc!r} conflicts with forced path-class type {constraints.force_cc_type.value!r}",
                kind="blueprint",
            )

    # change_types legality
    if blueprint.change_types:
        for ct in blueprint.change_types:
            if ct.value in constraints.forbid_cc_types:
                raise BlueprintError(
                    f"blueprint change_types entry {ct.value!r} forbidden by path-class gate",
                    kind="blueprint",
                )

    # SemVer legality
    eff_ceiling = ceiling
    if constraints.force_semver is not None and (
        eff_ceiling is None or _SEMVER_RANK[constraints.force_semver.value] <= _SEMVER_RANK[eff_ceiling.value]
    ):
        eff_ceiling = constraints.force_semver
    if blueprint.semver_impact is not None:
        if constraints.force_semver is not None and blueprint.semver_impact != constraints.force_semver:
            raise BlueprintError(
                f"blueprint semver_impact {blueprint.semver_impact.value!r} conflicts with "
                f"forced path-class semver {constraints.force_semver.value!r}",
                kind="blueprint",
            )
        if eff_ceiling is not None and _SEMVER_RANK[blueprint.semver_impact.value] > _SEMVER_RANK[eff_ceiling.value]:
            raise BlueprintError(
                f"blueprint semver_impact {blueprint.semver_impact.value!r} exceeds D16 ceiling {eff_ceiling.value!r}",
                kind="blueprint",
            )
        if blueprint.semver_impact.value in constraints.forbid_semver:
            raise BlueprintError(
                f"blueprint semver_impact {blueprint.semver_impact.value!r} forbidden by path-class gate",
                kind="blueprint",
            )

    # Changelog groups vs force group / security forbid
    if blueprint.changelog_groups:
        groups = [g.value for g in blueprint.changelog_groups]
        if constraints.forbid_security_primary and any(g.lower() == "security" for g in groups):
            raise BlueprintError(
                "blueprint changelog_groups may not include Security without path evidence",
                kind="blueprint",
            )
        if constraints.force_changelog_group is not None and groups:
            # Pure forced classes: reject groups that are clearly product-only when docs/tests forced.
            forced = constraints.force_changelog_group
            if forced in {"Documentation", "Tests"} and "Security" in groups:
                raise BlueprintError(
                    f"blueprint changelog_groups include Security under forced {forced}",
                    kind="blueprint",
                )
            if forced == "Documentation" and "Added" in groups and constraints.force_cc_type == CommitType.DOCS:
                raise BlueprintError(
                    "blueprint changelog_groups include Added under docs-only path-class",
                    kind="blueprint",
                )
            if forced == "Tests" and "Added" in groups and constraints.force_cc_type == CommitType.TEST:
                raise BlueprintError(
                    "blueprint changelog_groups include Added under tests-only path-class",
                    kind="blueprint",
                )

    # Scope force
    if blueprint.scope is not None and constraints.force_scope is not None:
        norm_bp = normalize_scope(blueprint.scope)
        norm_force = normalize_scope(constraints.force_scope)
        if norm_bp and norm_force and norm_bp != norm_force:
            # Soft: allow more specific behaviour scope under same family? Hard-fail per lock.
            # Docs/ADR force_scope is authoritative.
            raise BlueprintError(
                f"blueprint scope {norm_bp!r} conflicts with forced path-class scope {norm_force!r}",
                kind="blueprint",
            )

    # Combined change_types + changelog allowlist when both provided
    if blueprint.change_types and blueprint.changelog_groups:
        cts = [c.value for c in blueprint.change_types]
        groups = [g.value for g in blueprint.changelog_groups]
        primary = blueprint.cc_type.value if blueprint.cc_type is not None else (cts[0] if cts else None)
        if not changelog_groups_allowlisted(cts, groups, primary_cc_type=primary):
            raise BlueprintError(
                "blueprint change_types/changelog_groups fail D19 allowlist",
                kind="blueprint",
            )


def apply_blueprint(
    presentation_state: PresentationState | CommitPlan,
    blueprint: CommitBlueprint,
    constraints: PresentationConstraints,
    *,
    ceiling: SemVerImpact | None = None,
    paths: list[str] | None = None,
    signals: DiffSignals | None = None,
) -> PresentationState:
    """Overlay legal blueprint fields onto rendered presentation only.

    Descriptive return is ``PresentationState`` (success). Illegal combinations
    raise ``BlueprintError`` (HardError). Never mutates ranked ``intent_id``.
    """
    from git_cg.models import CommitPlan

    if isinstance(presentation_state, PresentationState):
        plan = presentation_state.plan
        if not isinstance(plan, CommitPlan):
            raise BlueprintError("presentation_state.plan must be a CommitPlan", kind="error")
        prior_reason = presentation_state.fallback_reason
    else:
        plan = presentation_state
        if not isinstance(plan, CommitPlan):
            raise BlueprintError("presentation_state must be CommitPlan or PresentationState", kind="error")
        prior_reason = PRESENTATION_FALLBACK_NONE

    # Validate first (fail closed before mutation).
    eff_ceiling = ceiling
    if eff_ceiling is None and paths is not None:
        eff_ceiling = semver_presentation_ceiling(paths, signals)
    validate_blueprint_against_constraints(blueprint, constraints, ceiling=eff_ceiling)

    primary = plan.primary_intent
    preserved_intent_id = primary.intent_id
    preserved_gitmoji = primary.gitmoji

    # cc_type overlay (presentation only)
    if blueprint.cc_type is not None:
        # Path-class force already validated equal; still honour force if present.
        primary.cc_type = constraints.force_cc_type or blueprint.cc_type
        mapped = _TYPE_CHANGELOG_REQUIREMENTS.get(primary.cc_type.value)
        if mapped and not blueprint.changelog_groups:
            primary.changelog_group = mapped

    # SemVer overlay
    if constraints.force_semver is not None:
        primary.semver_impact = constraints.force_semver
        for sec in plan.secondary_intents:
            sec.semver_impact = constraints.force_semver
    elif blueprint.semver_impact is not None:
        primary.semver_impact = blueprint.semver_impact
        for sec in plan.secondary_intents:
            sec.semver_impact = _clamp_semver(sec.semver_impact, blueprint.semver_impact)

    # Scope overlay (§J): force_scope > blueprint scope > existing
    if constraints.force_scope is not None:
        primary.scope = normalize_scope(constraints.force_scope)
    elif blueprint.scope is not None:
        primary.scope = normalize_scope(blueprint.scope)
    elif primary.scope:
        primary.scope = normalize_scope(primary.scope)

    # Changelog groups overlay
    if blueprint.changelog_groups:
        groups = [g.value for g in blueprint.changelog_groups]
        if constraints.force_changelog_group is not None:
            primary.changelog_group = constraints.force_changelog_group
        else:
            primary.changelog_group = groups[0]
        # Ensure remaining required groups exist as secondaries when change_types provided.
        if blueprint.change_types:
            present_types = {primary.cc_type.value, *(s.cc_type.value for s in plan.secondary_intents)}
            for ct in blueprint.change_types:
                if ct.value == primary.cc_type.value:
                    continue
                if ct.value in present_types:
                    continue
                group = _TYPE_CHANGELOG_REQUIREMENTS.get(ct.value, "Miscellaneous")
                # Prefer matching blueprint group when present.
                for g in groups:
                    if g == group or (ct.value == "feat" and g in {"Added", "Changed"}):
                        group = g
                        break
                _ensure_secondary_for_type(
                    plan,
                    cc_type=ct,
                    changelog_group=group,
                    scope=primary.scope,
                    description=(blueprint.subject_hint or f"cover {ct.value} surface")[:50],
                    semver=primary.semver_impact,
                )
                present_types.add(ct.value)

    # change_types without groups: ensure secondary coverage only
    if blueprint.change_types and not blueprint.changelog_groups:
        present_types = {primary.cc_type.value, *(s.cc_type.value for s in plan.secondary_intents)}
        for ct in blueprint.change_types:
            if ct.value in present_types:
                continue
            group = _TYPE_CHANGELOG_REQUIREMENTS.get(ct.value, "Miscellaneous")
            _ensure_secondary_for_type(
                plan,
                cc_type=ct,
                changelog_group=group,
                scope=primary.scope,
                description=(blueprint.subject_hint or f"cover {ct.value} surface")[:50],
                semver=primary.semver_impact,
            )
            present_types.add(ct.value)

    # Included-change stubs → presentation secondaries (inventory seeds)
    if blueprint.included_changes_stubs:
        present_types = {primary.cc_type.value, *(s.cc_type.value for s in plan.secondary_intents)}
        for stub in blueprint.included_changes_stubs:
            role = stub.role
            suggested = {
                "test": CommitType.TEST,
                "docs": CommitType.DOCS,
                "adr": CommitType.DOCS,
                "fixtures": CommitType.DOCS,
                "perf": CommitType.PERF,
                "refactor": CommitType.REFACTOR,
                "security": CommitType.FIX,
                "telemetry": CommitType.FIX,
                "sentry": CommitType.FIX,
                "prod": primary.cc_type,
                "other": CommitType.CHORE,
            }.get(role, CommitType.CHORE)
            if suggested.value in constraints.forbid_cc_types:
                continue
            group = _TYPE_CHANGELOG_REQUIREMENTS.get(suggested.value, "Miscellaneous")
            if role in {"docs", "adr", "fixtures"}:
                group = "Documentation"
            elif role == "test":
                group = "Tests"
            note = (stub.note or stub.surface or suggested.value).strip()
            if stub.claim_tags:
                note = f"{note} ({', '.join(stub.claim_tags)})"
            scope = normalize_scope(stub.surface) or primary.scope
            if suggested.value == primary.cc_type.value and not plan.secondary_intents:
                # Keep primary; optionally refine description from subject_hint only.
                pass
            elif suggested.value not in present_types or role in {"test", "docs", "adr"}:
                # Always materialise distinct surface secondaries for inventory roles.
                already = False
                for sec in plan.secondary_intents:
                    if sec.cc_type == suggested and normalize_scope(sec.scope) == scope:
                        already = True
                        break
                if not already and not (
                    suggested.value == primary.cc_type.value and normalize_scope(primary.scope) == scope
                ):
                    _ensure_secondary_for_type(
                        plan,
                        cc_type=suggested,
                        changelog_group=group,
                        scope=scope,
                        description=note[:50],
                        semver=SemVerImpact.NONE if constraints.force_semver is None else constraints.force_semver,
                    )
                    present_types.add(suggested.value)

    # Subject hint → primary description (presentation craft seed only)
    subject_hint = None
    if blueprint.subject_hint:
        subject_hint = blueprint.subject_hint.strip()
        if subject_hint:
            primary.description = subject_hint[:50]

    body_skel: tuple[str, ...] = ()
    if blueprint.body_skeleton:
        body_skel = tuple(line.strip() for line in blueprint.body_skeleton if str(line).strip())
        if body_skel and not (plan.body_summary and plan.body_summary.strip()):
            plan.body_summary = "\n".join(body_skel)

    # Final path-class force re-assert (envelope always wins)
    if constraints.force_cc_type is not None:
        primary.cc_type = constraints.force_cc_type
    if constraints.force_semver is not None:
        primary.semver_impact = constraints.force_semver
        for sec in plan.secondary_intents:
            sec.semver_impact = constraints.force_semver
    if constraints.force_changelog_group is not None:
        primary.changelog_group = constraints.force_changelog_group
    if constraints.force_scope is not None:
        primary.scope = normalize_scope(constraints.force_scope)

    if eff_ceiling is not None and constraints.force_semver is None:
        primary.semver_impact = _clamp_semver(primary.semver_impact, eff_ceiling)
        for sec in plan.secondary_intents:
            sec.semver_impact = _clamp_semver(sec.semver_impact, eff_ceiling)

    primary.intent_id = preserved_intent_id
    primary.gitmoji = preserved_gitmoji

    return PresentationState(
        plan=plan,
        blueprint_applied=True,
        fallback_reason=prior_reason if prior_reason != PRESENTATION_FALLBACK_NONE else PRESENTATION_FALLBACK_NONE,
        subject_hint=subject_hint,
        body_skeleton=body_skel,
    )


def format_blueprint_guidance(blueprint: CommitBlueprint | None) -> str:
    """Render pre-LLM presentation pressure from a legal blueprint (no JSON dump)."""
    if blueprint is None:
        return ""
    lines = [
        "OPERATOR BLUEPRINT (presentation overlay only — does not change intent_id / gitmoji authority):",
    ]
    if blueprint.cc_type is not None:
        lines.append(f"- preferred presentation cc_type: {blueprint.cc_type.value}")
    if blueprint.scope is not None:
        lines.append(f"- preferred presentation scope: {normalize_scope(blueprint.scope) or blueprint.scope}")
    if blueprint.semver_impact is not None:
        lines.append(f"- preferred presentation SemVer: {blueprint.semver_impact.value}")
    if blueprint.change_types:
        lines.append("- Change-Types overlay: " + ", ".join(ct.value for ct in blueprint.change_types))
    if blueprint.changelog_groups:
        lines.append("- Changelog-Groups overlay: " + ", ".join(g.value for g in blueprint.changelog_groups))
    if blueprint.subject_hint:
        lines.append(f"- subject seed: {blueprint.subject_hint.strip()[:72]}")
    if blueprint.body_skeleton:
        lines.append("- body skeleton seeds:")
        for entry in blueprint.body_skeleton[:12]:
            lines.append(f"  - {entry.strip()[:120]}")
    if blueprint.included_changes_stubs:
        lines.append("- included-change inventory seeds (emit as Hybrid mini-subjects via secondary_intents):")
        for stub in blueprint.included_changes_stubs[:16]:
            tags = f" tags={list(stub.claim_tags)}" if stub.claim_tags else ""
            note = f" note={stub.note}" if stub.note else ""
            lines.append(f"  - role={stub.role} surface={stub.surface}{tags}{note}")
    lines.append(
        "Path-class envelope and SemVer ceilings still win over this block. "
        "Do not invent Security framing without path evidence. "
        "Never treat this block as a ranking override."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Slice 8 — Hallucination guard · subject craft · claim-tag harvest (D14/D21)
# ---------------------------------------------------------------------------

CLAIM_TAG_RE = re.compile(r"\bP9-[AB]\d{2}\b")

# Runtime / recovery verbs that require runtime path evidence on docs/ADR/fixtures.
DOCS_RUNTIME_VERBS: frozenset[str] = frozenset(
    {
        "handle",
        "handles",
        "handled",
        "handling",
        "recover",
        "recovers",
        "recovered",
        "recovery",
        "runtime",
        "fail-open",
        "fail open",
        "fallback errors",
    }
)

# Vague subject openers banned when an outcome/failure-mode verb fits (D21).
VAGUE_SUBJECT_VERBS: frozenset[str] = frozenset(
    {
        "improve",
        "improves",
        "improved",
        "enhance",
        "enhances",
        "enhanced",
        "update",
        "updates",
        "updated",
        "clean",
        "cleans",
        "cleaned",
        "cleanup",
        "clean up",
        "hygiene",
        "streamline",
        "streamlines",
        "streamlined",
    }
)

# Unearned capability patterns on wording-only / claim-lock tips (D21 / F24).
_UNEARNED_CAPABILITY_RE = re.compile(
    r"\badds?\b.{0,40}\b(guard|assertion|feature|guidance)\b",
    flags=re.IGNORECASE,
)

# Unshipped product-as-actor claims (D14 / F26 / S5-G2).
_UNSHIPPED_PRODUCT_ACTOR_RE = re.compile(
    r"\b(?:from\s+the\s+)?phase\s*0\.5\s+product\b"
    r"|\bphase\s*0\.5\s+ships\b"
    r"|\bphase\s*0\.5\s+product\b",
    flags=re.IGNORECASE,
)

# Preferred class verbs (prompt pressure / craft findings only — D14).
DOCS_PREFERRED_VERBS: tuple[str, ...] = (
    "document",
    "record",
    "accept",
    "index",
    "align",
    "note",
    "diagram",
    "annotate",
)
TEST_PREFERRED_VERBS: tuple[str, ...] = (
    "cover",
    "claim",
    "pin",
    "close",
    "guard",
    "lock",
)
CORRECTNESS_PREFERRED_VERBS: tuple[str, ...] = (
    "preserve",
    "fix",
    "lock",
    "cover",
    "pin",
    "drop",
    "ban",
    "redact",
)

# Fallback reason precedence (Approval locks §G). Lower index = higher priority.
_FALLBACK_PRECEDENCE: tuple[str, ...] = (
    "error",
    "blueprint",
    "path_class_gate",
    "semver_ceiling",
    "type_dominance",
    "hallucination_guard",
    "craft_guard",
    "inventory_guard",
    "low_confidence",
    "none",
)

PRESENTATION_FALLBACK_HALLUCINATION = "hallucination_guard"
PRESENTATION_FALLBACK_CRAFT = "craft_guard"
PRESENTATION_FALLBACK_INVENTORY = "inventory_guard"


@dataclass(frozen=True)
class GuardFinding:
    """Single presentation guard hit (Slice 8 · D14/D21)."""

    code: str
    message: str
    kind: str  # "hallucination" | "craft"
    token: str = ""


@dataclass(frozen=True)
class GuardReport:
    """Aggregated hallucination + craft findings for one candidate message."""

    findings: tuple[GuardFinding, ...] = ()
    hallucination_guard_fired: bool = False
    craft_guard_fired: bool = False
    fallback_reason: str = PRESENTATION_FALLBACK_NONE

    @property
    def dirty(self) -> bool:
        return bool(self.findings)

    def codes(self) -> frozenset[str]:
        return frozenset(f.code for f in self.findings)


def merge_presentation_fallback_reason(current: str | None, incoming: str | None) -> str:
    """Return the higher-precedence closed fallback reason (Approval locks §G)."""
    cur = str(current or PRESENTATION_FALLBACK_NONE).strip().lower() or PRESENTATION_FALLBACK_NONE
    inc = str(incoming or PRESENTATION_FALLBACK_NONE).strip().lower() or PRESENTATION_FALLBACK_NONE
    if cur not in PRESENTATION_FALLBACK_REASONS:
        cur = PRESENTATION_FALLBACK_NONE
    if inc not in PRESENTATION_FALLBACK_REASONS:
        inc = PRESENTATION_FALLBACK_NONE
    rank = {name: idx for idx, name in enumerate(_FALLBACK_PRECEDENCE)}
    # Unknowns already coerced to none; pick lower rank index.
    return cur if rank.get(cur, 99) <= rank.get(inc, 99) else inc


def harvest_claim_tags(
    texts: list[str] | tuple[str, ...] | None = None,
    *,
    paths: list[str] | tuple[str, ...] | None = None,
    max_tags: int = 8,
) -> list[str]:
    """Harvest ``P9-A##`` / ``P9-B##`` claim tags from staged test/docs text (D14).

    Pure: does not read the filesystem. Callers supply file contents as *texts*.
    Order is first-seen stable; capped at *max_tags* (default 8).
    """
    del paths  # reserved for future path-role filtering; harvest is text-driven
    found: list[str] = []
    seen: set[str] = set()
    for blob in texts or ():
        if not blob:
            continue
        for match in CLAIM_TAG_RE.finditer(str(blob)):
            tag = match.group(0)
            if tag in seen:
                continue
            seen.add(tag)
            found.append(tag)
            if len(found) >= max_tags:
                return found
    return found


def _plan_subject_body(plan: CommitPlan | None) -> tuple[str, str]:
    if plan is None:
        return "", ""
    primary = getattr(plan, "primary_intent", None)
    subject = str(getattr(primary, "description", "") or "")
    body = str(getattr(plan, "body_summary", "") or "")
    # Include secondary descriptions — capability claims often land there.
    secs = getattr(plan, "secondary_intents", None) or []
    sec_bits = " ".join(str(getattr(s, "description", "") or "") for s in secs)
    return subject, f"{body}\n{sec_bits}".strip()


def _message_blob(plan: CommitPlan | None) -> str:
    subject, body = _plan_subject_body(plan)
    return f"{subject}\n{body}".strip()


def _docs_only_class(diff_class_name: str | None, paths: list[str]) -> bool:
    if diff_class_name in {DIFF_CLASS_DOCS, DIFF_CLASS_ADR, DIFF_CLASS_FIXTURES}:
        return True
    if not paths:
        return False
    roles = _classify_path_roles(paths)
    return (
        bool(roles)
        and roles <= {"docs", "adr", "fixtures", "release"}
        and not (roles & {"product_src", "tests", "config_ci"})
    )


def _tests_only_class(diff_class_name: str | None, paths: list[str]) -> bool:
    if diff_class_name == DIFF_CLASS_TESTS:
        return True
    if not paths:
        return False
    roles = _classify_path_roles(paths)
    return roles == {"tests"} or roles == {"tests", "fixtures"}


def check_hallucination_guard(
    plan: CommitPlan | None,
    *,
    paths: list[str] | None = None,
    signals: DiffSignals | None = None,
    evidence_text: str = "",
    constraints: PresentationConstraints | None = None,
) -> list[GuardFinding]:
    """Return hallucination findings for unevidenced high-risk claims (D14).

    Classes:
    * security nouns without security-path evidence
    * runtime/recovery verbs on docs/ADR/fixtures-only diffs
    * unshipped product-as-actor claims without product evidence
    * unearned \"adds … guard/assertion/feature/guidance\" capability claims
    """
    clean = _resolve_paths(list(paths or []), signals)
    cons = constraints or presentation_constraints(classify_diff_class(clean))
    subject, _body = _plan_subject_body(plan)
    blob = _message_blob(plan)
    if not blob:
        return []

    findings: list[GuardFinding] = []
    evidence_blob = " ".join(
        [
            " ".join(clean),
            evidence_text or "",
            " ".join(getattr(signals, "evidence", None) or []) if signals is not None else "",
        ]
    ).lower()

    # 1) Security nouns without path evidence.
    for tok in security_claims_without_path_evidence(blob, clean):
        findings.append(
            GuardFinding(
                code="GUARD_SECURITY_NOUN",
                message=(
                    f"Subject/body claims {tok!r} without security path evidence; "
                    "drop secrets/credentials framing or stage a security path."
                ),
                kind="hallucination",
                token=tok,
            )
        )

    # 2) Runtime/recovery verbs on docs-only classes (word-boundary; multi-word OK).
    if _docs_only_class(cons.diff_class, clean):
        lowered = blob.lower()
        for verb in sorted(DOCS_RUNTIME_VERBS, key=len, reverse=True):
            if " " in verb or "-" in verb:
                hit = verb in lowered
            else:
                hit = re.search(rf"\b{re.escape(verb)}\b", lowered) is not None
            if hit:
                findings.append(
                    GuardFinding(
                        code="GUARD_DOCS_RUNTIME_VERB",
                        message=(
                            f"Docs/ADR/fixtures-only message uses runtime verb {verb!r}; "
                            "prefer document/record/diagram/align wording."
                        ),
                        kind="hallucination",
                        token=verb,
                    )
                )

    # 3) Unshipped product-as-actor.
    actor_hit = _UNSHIPPED_PRODUCT_ACTOR_RE.search(blob)
    # Allow only when evidence explicitly implements that product surface.
    if actor_hit and "phase 0.5" not in evidence_blob and "phase0.5" not in evidence_blob:
        findings.append(
            GuardFinding(
                code="GUARD_UNSHIPPED_PRODUCT_ACTOR",
                message=(
                    f"Message claims unshipped product actor {actor_hit.group(0)!r} "
                    "without staged product evidence (D14)."
                ),
                kind="hallucination",
                token=actor_hit.group(0),
            )
        )

    # 4) Pure evaluator / snapshot bodies must not claim enforce/lift/mutate (TIP-G14).
    if _tests_only_class(cons.diff_class, clean) or (
        any(_is_test_path(p) for p in clean)
        and not any((not _is_test_path(p) and not _is_docs_path(p) and not _is_fixtures_path(p)) for p in clean)
    ):
        for verb in ("enforce", "enforces", "enforced", "lift", "lifts", "lifted", "mutate", "mutates", "mutated"):
            if re.search(rf"\b{re.escape(verb)}\b", blob.lower()):
                findings.append(
                    GuardFinding(
                        code="GUARD_EVALUATOR_MUTATION_VERB",
                        message=(
                            f"Evaluator/snapshot body claims mutation verb {verb!r}; "
                            "describe coverage only (no enforce/lift/mutate plan verbs)."
                        ),
                        kind="hallucination",
                        token=verb,
                    )
                )

    # 5) Competing Context:/Changes: body templates (Session 6 / TIP-G16).
    # Hybrid commits use Included changes via secondaries — not marketing essays.
    body_only = str(getattr(plan, "body_summary", "") or "") if plan is not None else ""
    if body_only:
        has_context = bool(re.search(r"(?m)^Context:\s*$", body_only) or body_only.lstrip().startswith("Context:"))
        has_changes = bool(re.search(r"(?m)^Changes:\s*$", body_only) or re.search(r"(?m)^Changes:\s+", body_only))
        if has_context and has_changes:
            findings.append(
                GuardFinding(
                    code="GUARD_CONTEXT_CHANGES_TEMPLATE",
                    message=(
                        "Body uses banned Context:/Changes: template; prefer Hybrid "
                        "`Included changes:` via secondary_intents (Session 6)."
                    ),
                    kind="hallucination",
                    token="Context:/Changes:",
                )
            )

    # 6) Tests-only / tests+docs bodies must not claim whole-product implementation
    # (Session 6 / TIP-G17 attribution bleed).
    roles = _classify_path_roles(clean)
    tests_docs_only = roles and roles <= {"tests", "fixtures", "docs", "adr"}
    if tests_docs_only and not (roles & {"product_src"}):
        bleed = re.search(
            r"\b(implement(?:s|ed|ing)?|wir(?:e|es|ed|ing)|ship(?:s|ped|ping)?|land(?:s|ed|ing)?)\b"
            r".{0,40}\b(lifecycle|telemetry|contract|schema|slice|feature|product)\b"
            r"|\b(whole|entire)\s+(slice|feature|implementation)\b"
            r"|\battribut(?:e|es|ed|ing)\b",
            blob,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if bleed:
            findings.append(
                GuardFinding(
                    code="GUARD_ATTRIBUTION_BLEED",
                    message=(
                        "Tests/docs-only body claims product implementation/wiring; "
                        "assert coverage only (Session 6 / TIP-G17)."
                    ),
                    kind="hallucination",
                    token=bleed.group(0)[:48],
                )
            )

    # 7) Unearned capability "adds … guard/assertion/feature/guidance".
    # Fire when primary is feat OR when wording-only correctness diffs invent capability.
    cap_hit = _UNEARNED_CAPABILITY_RE.search(subject) or _UNEARNED_CAPABILITY_RE.search(blob)
    if cap_hit:
        primary = getattr(plan, "primary_intent", None) if plan is not None else None
        cc = getattr(primary, "cc_type", None)
        cc_val = cc.value if isinstance(cc, CommitType) else str(cc or "").lower()
        # Always reject on docs/tests-only; on product, reject feat framing of add-guard.
        if (
            _docs_only_class(cons.diff_class, clean)
            or _tests_only_class(cons.diff_class, clean)
            or cc_val == CommitType.FEAT.value
        ):
            findings.append(
                GuardFinding(
                    code="GUARD_UNEARNED_CAPABILITY",
                    message=(
                        f"Unearned capability claim {cap_hit.group(0)!r}; prefer outcome "
                        "verbs (drop/ban/lock/cover) over invented guard/feature nouns."
                    ),
                    kind="hallucination",
                    token=cap_hit.group(0),
                )
            )

    # De-dupe by code+token while preserving order.
    out: list[GuardFinding] = []
    seen: set[tuple[str, str]] = set()
    for f in findings:
        key = (f.code, f.token.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def check_craft_guard(
    plan: CommitPlan | None,
    *,
    paths: list[str] | None = None,
    signals: DiffSignals | None = None,
    constraints: PresentationConstraints | None = None,
) -> list[GuardFinding]:
    """Return subject-craft findings (D14/D21 · Title Case · vague verbs · openers).

    Reuses ``commit_gold._is_title_case_subject`` and ``BANNED_BODY_OPENERS`` (I-13).
    Pre-LLM use is prompt pressure; this function is the post-LLM evaluator.
    """
    if plan is None:
        return []
    clean = _resolve_paths(list(paths or []), signals)
    cons = constraints or presentation_constraints(classify_diff_class(clean))
    subject, body = _plan_subject_body(plan)
    findings: list[GuardFinding] = []

    if subject and _is_title_case_subject(subject):
        findings.append(
            GuardFinding(
                code="GUARD_TITLE_CASE_SUBJECT",
                message=(
                    f"Subject looks Title Case ({subject!r}); use imperative lowercase "
                    "(e.g. 'cover claim locks' / 'document blueprint overlay')."
                ),
                kind="craft",
                token=subject.split()[0] if subject.split() else subject,
            )
        )

    # Title Case inventory default "Add … unit tests" / SOP passthrough on test/docs.
    first = _first_subject_token(subject)
    docs_or_tests = _docs_only_class(cons.diff_class, clean) or _tests_only_class(cons.diff_class, clean)
    if docs_or_tests and first.lower() in {"add", "adds", "added"}:
        findings.append(
            GuardFinding(
                code="GUARD_TEST_DOCS_ADD_OPENER",
                message=(
                    "Test/docs path-class subject opens with Add/Adds inventory default; "
                    "prefer cover/claim/pin/document/record outcome verbs."
                ),
                kind="craft",
                token=first,
            )
        )

    # Vague verbs when outcome verbs fit (D21) — always craft pressure on correctness-ish.
    if first.lower() in VAGUE_SUBJECT_VERBS:
        findings.append(
            GuardFinding(
                code="GUARD_VAGUE_SUBJECT_VERB",
                message=(
                    f"Subject opens with vague verb {first!r}; prefer failure-mode / "
                    "outcome verbs (preserve/fix/lock/cover/pin/drop/ban/document)."
                ),
                kind="craft",
                token=first,
            )
        )

    # Banned body openers (import gold source — I-13).
    body_first = ""
    if body:
        for line in body.replace("\\n", "\n").splitlines():
            if line.strip():
                body_first = line.strip()
                break
    if body_first:
        for opener in BANNED_BODY_OPENERS:
            if body_first.startswith(opener):
                findings.append(
                    GuardFinding(
                        code="GUARD_BANNED_BODY_OPENER",
                        message=(
                            f"Body opens with banned inventory/marketing opener {opener!r}; "
                            "state the behaviour delta directly."
                        ),
                        kind="craft",
                        token=opener.strip(),
                    )
                )
                break

    out: list[GuardFinding] = []
    seen: set[tuple[str, str]] = set()
    for f in findings:
        key = (f.code, f.token.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def _first_subject_token(subject: str) -> str:
    words = [w for w in (subject or "").strip().split() if any(ch.isalpha() for ch in w)]
    if not words:
        return ""
    # Strip leading non-alpha from token (e.g. quotes).
    token = words[0]
    return re.sub(r"^[^A-Za-z]+", "", token)


def evaluate_presentation_guards(
    plan: CommitPlan | None,
    *,
    paths: list[str] | None = None,
    signals: DiffSignals | None = None,
    evidence_text: str = "",
    constraints: PresentationConstraints | None = None,
) -> GuardReport:
    """Run hallucination + craft guards and pick a single primary fallback reason."""
    hall = check_hallucination_guard(
        plan,
        paths=paths,
        signals=signals,
        evidence_text=evidence_text,
        constraints=constraints,
    )
    craft = check_craft_guard(
        plan,
        paths=paths,
        signals=signals,
        constraints=constraints,
    )
    findings = tuple(hall + craft)
    hall_fired = bool(hall)
    craft_fired = bool(craft)
    reason = PRESENTATION_FALLBACK_NONE
    if hall_fired:
        reason = PRESENTATION_FALLBACK_HALLUCINATION
    elif craft_fired:
        reason = PRESENTATION_FALLBACK_CRAFT
    return GuardReport(
        findings=findings,
        hallucination_guard_fired=hall_fired,
        craft_guard_fired=craft_fired,
        fallback_reason=reason,
    )


def format_guard_guidance(report: GuardReport | None) -> str:
    """Render directive-free guard findings for a shared regen attempt (I-14)."""
    if report is None or not report.findings:
        return ""
    lines = [
        "PRESENTATION GUARD FINDINGS (wording only — does not change intent_id / gitmoji authority):",
        "Repair subject/body against staged evidence. Do not invent secrets, runtime recovery,",
        "unshipped product actors, or unearned capability nouns. Prefer outcome/failure-mode verbs.",
    ]
    for finding in report.findings[:12]:
        lines.append(f"- [{finding.code}] {finding.message}")
    lines.append("This block guides wording only. It MUST NOT change intent_id, gitmoji, or ranking.")
    return "\n".join(lines)


def apply_guard_skeleton_fallback(
    plan: CommitPlan,
    *,
    paths: list[str] | None = None,
    signals: DiffSignals | None = None,
    priors: TrailerPriors | None = None,
    constraints: PresentationConstraints | None = None,
    claim_tags: list[str] | tuple[str, ...] | None = None,
    report: GuardReport | None = None,
) -> CommitPlan:
    """Replace dirty subject/body with deterministic priors + stub skeleton (D14).

    Presentation-only. Preserves ranked ``intent_id`` and matrix ``gitmoji``.
    Used when shared ``gold_regen_attempts`` budget is exhausted (I-14).
    """
    clean = _resolve_paths(list(paths or []), signals)
    base_priors = priors or derive_trailer_priors(clean, signals=signals)
    cons = constraints or presentation_constraints(classify_diff_class(clean))

    primary = plan.primary_intent
    preserved_intent_id = primary.intent_id
    preserved_gitmoji = primary.gitmoji

    # Prefer path-class force, else priors.
    if cons.force_cc_type is not None:
        primary.cc_type = cons.force_cc_type
    else:
        primary.cc_type = base_priors.cc_type
    if cons.force_semver is not None:
        primary.semver_impact = cons.force_semver
    else:
        primary.semver_impact = base_priors.semver_impact
    if cons.force_changelog_group is not None:
        primary.changelog_group = cons.force_changelog_group
    else:
        primary.changelog_group = base_priors.changelog_group
    if cons.force_scope is not None:
        primary.scope = normalize_scope(cons.force_scope)
    elif base_priors.scope_hint:
        primary.scope = normalize_scope(base_priors.scope_hint)

    # Deterministic subject from path-class / preferred verbs.
    if _docs_only_class(cons.diff_class, clean):
        primary.description = "document staged documentation changes"[:50]
    elif _tests_only_class(cons.diff_class, clean):
        tag_bit = ""
        tags = [t for t in (claim_tags or ()) if t][:3]
        if tags:
            tag_bit = f" ({', '.join(tags)})"
        primary.description = f"cover staged claim locks{tag_bit}"[:50]
    elif primary.cc_type == CommitType.FIX:
        primary.description = "fix staged correctness regressions"[:50]
    else:
        primary.description = "apply staged presentation-safe changes"[:50]

    # Body: short evidence-grounded skeleton; never Context:/Changes: marketing.
    body_lines = [
        "Deterministic presentation fallback after guard exhaustion.",
        "Wording constrained to staged paths and path-class priors.",
    ]
    if report is not None and report.findings:
        codes = ", ".join(sorted({f.code for f in report.findings})[:6])
        body_lines.append(f"Cleared guard codes: {codes}.")
    if claim_tags:
        body_lines.append("Claim tags: " + ", ".join(list(claim_tags)[:8]) + ".")
    plan.body_summary = "\n".join(body_lines)

    primary.intent_id = preserved_intent_id
    primary.gitmoji = preserved_gitmoji

    # Ensure inventory secondaries from stubs when multi-surface.
    stubs = build_included_change_stubs(
        clean,
        signals,
        claim_tags=claim_tags,
    )
    pure_docs_or_tests = _docs_only_class(cons.diff_class, clean) or _tests_only_class(cons.diff_class, clean)
    for stub in stubs[:8]:
        cc = _suggested_cc_for_role(
            stub.role,
            tags=set(),
            pure_docs_or_tests=pure_docs_or_tests,
        )
        group = _TYPE_CHANGELOG_REQUIREMENTS.get(cc.value, primary.changelog_group)
        note = stub.note or stub.surface
        if stub.claim_tags:
            note = f"{note} ({', '.join(stub.claim_tags[:4])})"
        scope = stub.surface if stub.surface else primary.scope
        _ensure_secondary_for_type(
            plan,
            cc_type=cc,
            changelog_group=group,
            scope=scope,
            description=str(note)[:50],
            semver=SemVerImpact.NONE if primary.semver_impact == SemVerImpact.NONE else primary.semver_impact,
        )

    return plan


# ---------------------------------------------------------------------------
# Slice 9 - Pure A-N characterisation gates (issue #204)
# ---------------------------------------------------------------------------
# Ordered, CI-able evaluation of candidate commit plans against path-class
# priors. No live LLM and no rank_commit_intents. Gate order is frozen:
# path_class → type → semver → no_hallucination → inventory → craft.

SLICE9_GATE_ORDER: tuple[str, ...] = (
    "path_class",
    "type",
    "semver",
    "no_hallucination",
    "inventory",
    "craft",
)

SEMVER_RANK: dict[str, int] = {
    SemVerImpact.NONE.value: 0,
    SemVerImpact.PATCH.value: 1,
    SemVerImpact.MINOR.value: 2,
    SemVerImpact.MAJOR.value: 3,
}


@dataclass(frozen=True)
class GateFinding:
    """Single ordered-gate failure for Slice 9 pure evaluation."""

    gate: str
    code: str
    message: str
    token: str = ""


@dataclass(frozen=True)
class GateReport:
    """Ordered gate evaluation result (first failure wins)."""

    findings: tuple[GateFinding, ...] = ()
    first_fail_gate: str | None = None
    passed: bool = True
    codes: tuple[str, ...] = ()
    gate_status: tuple[tuple[str, str], ...] = ()  # (gate, pass|fail|skip)

    def codeset(self) -> frozenset[str]:
        return frozenset(self.codes)


def _enum_val(value: object) -> str:
    if value is None:
        return ""
    return str(value.value if hasattr(value, "value") else value)


def _plan_types_groups(plan: CommitPlan | None) -> tuple[list[str], list[str], list[str]]:
    if plan is None:
        return [], [], []
    primary = plan.primary_intent
    types = [_enum_val(primary.cc_type)]
    groups = [str(primary.changelog_group or "")]
    scopes = [str(primary.scope or "")]
    for sec in plan.secondary_intents or []:
        types.append(_enum_val(sec.cc_type))
        groups.append(str(sec.changelog_group or ""))
        scopes.append(str(sec.scope or ""))
    return types, groups, scopes


def _inventory_blob(plan: CommitPlan | None, included_changes: list[str] | None = None) -> str:
    bits: list[str] = []
    if included_changes:
        bits.extend(str(x) for x in included_changes)
    if plan is None:
        return "\n".join(bits)
    subject, body = _plan_subject_body(plan)
    bits.append(subject)
    bits.append(body)
    for sec in plan.secondary_intents or []:
        bits.append(str(getattr(sec, "description", "") or ""))
    return "\n".join(bits)


def _check_path_class_gate(
    plan: CommitPlan,
    *,
    paths: list[str],
    constraints: PresentationConstraints,
) -> list[GateFinding]:
    """Path-class agreement only (security primary + forced scope).

    Type/SemVer/group mismatches are owned by later gates so the frozen
    order path_class → type → semver → … stays informative.
    """
    findings: list[GateFinding] = []
    primary = plan.primary_intent
    cc = _enum_val(primary.cc_type)
    group = str(primary.changelog_group or "")
    scope = normalize_scope(primary.scope) if primary.scope else primary.scope
    blob = f"{primary.description or ''} {plan.body_summary or ''}".lower()

    # Security primary banned without security path evidence.
    if constraints.forbid_security_primary:
        if group.lower() == "security":
            findings.append(
                GateFinding(
                    gate="path_class",
                    code="GATE_PATH_SECURITY_PRIMARY",
                    message=("Path class forbids Security primary without security path evidence."),
                    token=group,
                )
            )
        # chore framed as security on fixtures/docs/ADR.
        if cc == CommitType.CHORE.value and ("security" in blob or "secret" in blob or "credential" in blob):
            findings.append(
                GateFinding(
                    gate="path_class",
                    code="GATE_PATH_SECURITY_CHORE",
                    message="Path class rejects security-framed chore without path evidence.",
                    token="chore",
                )
            )

    # Forced scope from path class (fixtures/adr/usage/scoped-history).
    if constraints.force_scope:
        forced = normalize_scope(constraints.force_scope) or constraints.force_scope
        got = scope or ""
        # Only flag clear package-scope / wrong-family disagreements.
        if got and got != forced and got in {"git_cg", "src", "main"}:
            findings.append(
                GateFinding(
                    gate="path_class",
                    code="GATE_PATH_SCOPE_MISMATCH",
                    message=(f"Path-class force_scope {forced!r} disagrees with plan scope {got!r}."),
                    token=str(got),
                )
            )

    return findings


def _check_type_gate(
    plan: CommitPlan,
    *,
    paths: list[str],
    signals: DiffSignals | None,
    constraints: PresentationConstraints,
    concern_tags: set[str] | frozenset[str] | None,
    priors: TrailerPriors | None,
) -> list[GateFinding]:
    findings: list[GateFinding] = []
    primary = plan.primary_intent
    cc = _enum_val(primary.cc_type)
    types, groups, _scopes = _plan_types_groups(plan)

    if constraints.force_cc_type is not None and cc != _enum_val(constraints.force_cc_type):
        findings.append(
            GateFinding(
                gate="type",
                code="GATE_TYPE_FORCE_MISMATCH",
                message=(f"Primary type {cc!r} violates force_cc_type {_enum_val(constraints.force_cc_type)!r}."),
                token=cc,
            )
        )

    if cc in set(constraints.forbid_cc_types or ()):
        findings.append(
            GateFinding(
                gate="type",
                code="GATE_TYPE_FORBIDDEN",
                message=f"Primary type {cc!r} is forbidden for this path class.",
                token=cc,
            )
        )

    dominant = dominant_presentation_cc_type(
        paths,
        signals=signals,
        concern_tags=concern_tags,
        priors=priors,
    )
    # Dominant is advisory when force_cc_type already set; still enforce when free.
    if dominant is not None and cc != _enum_val(dominant) and constraints.force_cc_type is None:
        findings.append(
            GateFinding(
                gate="type",
                code="GATE_TYPE_DOMINANT_MISMATCH",
                message=(f"Primary type {cc!r} disagrees with dominant type {_enum_val(dominant)!r}."),
                token=cc,
            )
        )

    # Required groups from the candidate's declared change-types.
    required_groups = required_changelog_groups(types, primary_cc_type=primary.cc_type)

    # If path class forced a primary group, ensure it is present.
    if constraints.force_changelog_group and constraints.force_changelog_group not in groups:
        findings.append(
            GateFinding(
                gate="type",
                code="GATE_TYPE_GROUP_MISSING",
                message=(f"Missing forced changelog group {constraints.force_changelog_group!r}."),
                token=constraints.force_changelog_group,
            )
        )

    # Dual-surface path pressure: tests+docs without runtime need both groups.
    dc = classify_diff_class(paths)
    has_tests = bool(_test_module_stems(paths))
    has_docs = bool(_doc_surface_keys(paths))
    has_prod = bool(_product_module_stems(paths))
    expected_multi: list[str] = []
    if has_tests and has_docs and not dc.has_runtime_surface:
        expected_multi = ["Tests", "Documentation"]
    elif has_prod and has_tests:
        # Product+test dual surface should not collapse to a single non-Tests group
        # when primary is feat/fix; Tests should appear.
        if "Tests" not in groups and CommitType.TEST.value in types:
            pass
        elif (
            has_tests
            and "Tests" not in groups
            and _enum_val(primary.cc_type)
            in {
                CommitType.FEAT.value,
                CommitType.FIX.value,
                CommitType.TEST.value,
            }
        ):
            expected_multi = [groups[0], "Tests"] if groups else ["Tests"]

    for req in expected_multi:
        if req and req not in groups:
            findings.append(
                GateFinding(
                    gate="type",
                    code="GATE_TYPE_REQUIRED_GROUP_MISSING",
                    message=f"Missing required changelog group {req!r}.",
                    token=req,
                )
            )

    # Reject single-group collapse when dual-surface expected.
    if expected_multi and len(set(g for g in groups if g)) == 1:
        findings.append(
            GateFinding(
                gate="type",
                code="GATE_TYPE_SINGLE_GROUP_ONLY",
                message=f"Multi-surface plan collapsed to single group {groups[0]!r}.",
                token=groups[0] if groups else "",
            )
        )

    # Candidate change-types must cover their required changelog mapping.
    # feat may legally render as Added (new capability) or Changed (carry-through /
    # dark-launch wiring without a user-facing MINOR bump story).
    for req in required_groups:
        if req not in groups:
            if req == "Added" and "Changed" in groups and CommitType.FEAT.value in types:
                continue
            findings.append(
                GateFinding(
                    gate="type",
                    code="GATE_TYPE_REQUIRED_GROUP_MISSING",
                    message=f"Change-Types require changelog group {req!r}.",
                    token=req,
                )
            )

    return findings


def _check_semver_gate(
    plan: CommitPlan,
    *,
    paths: list[str],
    signals: DiffSignals | None,
    constraints: PresentationConstraints,
    concern_tags: set[str] | frozenset[str] | None,
) -> list[GateFinding]:
    findings: list[GateFinding] = []
    primary = plan.primary_intent
    sem = _enum_val(primary.semver_impact)
    ceiling = semver_presentation_ceiling(paths, signals, concern_tags=concern_tags)
    ceil_v = _enum_val(ceiling)

    if constraints.force_semver is not None and sem != _enum_val(constraints.force_semver):
        findings.append(
            GateFinding(
                gate="semver",
                code="GATE_SEMVER_FORCE_MISMATCH",
                message=(f"SemVer {sem!r} violates force_semver {_enum_val(constraints.force_semver)!r}."),
                token=sem,
            )
        )

    if sem in set(constraints.forbid_semver or ()):
        findings.append(
            GateFinding(
                gate="semver",
                code="GATE_SEMVER_FORBIDDEN",
                message=f"SemVer {sem!r} is forbidden for this path class.",
                token=sem,
            )
        )

    if SEMVER_RANK.get(sem, 99) > SEMVER_RANK.get(ceil_v, 0):
        findings.append(
            GateFinding(
                gate="semver",
                code="GATE_SEMVER_CEILING",
                message=f"SemVer {sem!r} exceeds presentation ceiling {ceil_v!r}.",
                token=sem,
            )
        )

    # Secondaries must not exceed ceiling either.
    for sec in plan.secondary_intents or []:
        ssem = _enum_val(sec.semver_impact)
        if SEMVER_RANK.get(ssem, 99) > SEMVER_RANK.get(ceil_v, 0):
            findings.append(
                GateFinding(
                    gate="semver",
                    code="GATE_SEMVER_SECONDARY_CEILING",
                    message=f"Secondary SemVer {ssem!r} exceeds ceiling {ceil_v!r}.",
                    token=ssem,
                )
            )
            break

    return findings


def _check_inventory_gate(
    plan: CommitPlan,
    *,
    paths: list[str],
    signals: DiffSignals | None,
    concern_tags: set[str] | frozenset[str] | None,
    claim_tags: list[str] | tuple[str, ...] | None,
    included_changes: list[str] | None,
    require_stub_note_tokens: list[str] | tuple[str, ...] | None = None,
) -> list[GateFinding]:
    findings: list[GateFinding] = []
    min_bullets = min_included_change_bullets(paths, concern_tags=concern_tags)
    stubs = build_included_change_stubs(
        paths,
        signals,
        concern_tags=concern_tags,
        claim_tags=claim_tags,
    )

    # Candidate inventory: explicit included_changes win; else secondary descriptions.
    inv_items: list[str] = []
    if included_changes is not None:
        inv_items = [str(x).strip() for x in included_changes if str(x).strip()]
    else:
        for sec in plan.secondary_intents or []:
            desc = str(getattr(sec, "description", "") or "").strip()
            if desc:
                inv_items.append(desc)

    # Cardinality: multi-surface pressure requires enough bullets.
    # Allow stub-count floor when candidate omitted explicit inventory but
    # secondaries under-count; still fail empty multi-surface inventory.
    if min_bullets >= 2 and (len(inv_items) == 0 or len(inv_items) < min(2, min_bullets)):
        findings.append(
            GateFinding(
                gate="inventory",
                code="GATE_INVENTORY_CARDINALITY",
                message=(f"Inventory has {len(inv_items)} bullet(s); path pressure requires >= {min_bullets}."),
                token=str(len(inv_items)),
            )
        )

    blob = _inventory_blob(plan, inv_items).lower()

    # Required note tokens (e.g. gpg/signing for S9-H).
    if require_stub_note_tokens:
        # Prefer candidate inventory; fall back to deterministic stubs as oracle.
        stub_blob = " ".join(f"{s.note or ''} {s.surface or ''} {s.role or ''}" for s in stubs).lower()
        for tok in require_stub_note_tokens:
            t = str(tok).lower()
            if t not in blob and t not in stub_blob:
                findings.append(
                    GateFinding(
                        gate="inventory",
                        code="GATE_INVENTORY_MISSING_TOKEN",
                        message=f"Inventory/stubs missing required token {tok!r}.",
                        token=str(tok),
                    )
                )
            elif t not in blob and t in stub_blob:
                # Candidate omitted a token the pure stubs require.
                findings.append(
                    GateFinding(
                        gate="inventory",
                        code="GATE_INVENTORY_MISSING_TOKEN",
                        message=(f"Candidate inventory omits required token {tok!r} present in deterministic stubs."),
                        token=str(tok),
                    )
                )

    # Claim tags must appear when provided on multi-test cases.
    if claim_tags and len(_test_module_stems(paths)) >= 2:
        missing = [t for t in claim_tags if t not in _inventory_blob(plan, inv_items)]
        if missing:
            findings.append(
                GateFinding(
                    gate="inventory",
                    code="GATE_INVENTORY_MISSING_CLAIMS",
                    message=f"Inventory missing claim tags {missing!r}.",
                    token=",".join(missing),
                )
            )

    # Thin single-bullet inventory on multi-concern product correctness.
    tags = {t.lower() for t in (concern_tags or set())}
    if len(tags) >= 3 and len(inv_items) == 1:
        findings.append(
            GateFinding(
                gate="inventory",
                code="GATE_INVENTORY_THIN",
                message="Multi-concern product inventory collapsed to one bullet.",
                token="1",
            )
        )

    # Docs-only inventory on mixed test+docs path when tests are staged.
    test_modules = _test_module_stems(paths)
    if test_modules and inv_items:
        testish = any(("test(" in x.lower()) or x.strip().startswith("✅") or "cover " in x.lower() for x in inv_items)
        if not testish and constraints_force_test(paths, plan):
            findings.append(
                GateFinding(
                    gate="inventory",
                    code="GATE_INVENTORY_TEST_SURFACE_MISSING",
                    message="Test-bearing path class inventory lacks test bullets.",
                    token="test",
                )
            )

    return findings


def constraints_force_test(paths: list[str], plan: CommitPlan) -> bool:
    """Helper: true when path class / plan primary expects test inventory."""
    dc = classify_diff_class(paths)
    cons = presentation_constraints(dc)
    if cons.force_cc_type == CommitType.TEST:
        return True
    return _enum_val(plan.primary_intent.cc_type) == CommitType.TEST.value


def evaluate_presentation_gates(
    plan: CommitPlan | None,
    *,
    paths: list[str] | None = None,
    signals: DiffSignals | None = None,
    priors: TrailerPriors | None = None,
    constraints: PresentationConstraints | None = None,
    concern_tags: set[str] | frozenset[str] | None = None,
    claim_tags: list[str] | tuple[str, ...] | None = None,
    evidence_text: str = "",
    included_changes: list[str] | None = None,
    require_stub_note_tokens: list[str] | tuple[str, ...] | None = None,
) -> GateReport:
    """Evaluate a candidate plan through Slice 9 ordered pure gates.

    Gate order (first failure wins):
    path_class → type → semver → no_hallucination → inventory → craft.

    Pure and deterministic: never calls rank_commit_intents or a live LLM.
    """
    if plan is None:
        finding = GateFinding(
            gate="path_class",
            code="GATE_MISSING_PLAN",
            message="Candidate plan is missing.",
        )
        return GateReport(
            findings=(finding,),
            first_fail_gate="path_class",
            passed=False,
            codes=(finding.code,),
            gate_status=tuple((g, "fail" if g == "path_class" else "skip") for g in SLICE9_GATE_ORDER),
        )

    clean = _resolve_paths(list(paths or []), signals)
    base_priors = priors or derive_trailer_priors(clean, signals=signals)
    cons = constraints or presentation_constraints(classify_diff_class(clean))
    tags = set(concern_tags or set())

    checkers: dict[str, list[GateFinding]] = {}

    # 1) path_class
    checkers["path_class"] = _check_path_class_gate(plan, paths=clean, constraints=cons)

    # 2) type
    checkers["type"] = _check_type_gate(
        plan,
        paths=clean,
        signals=signals,
        constraints=cons,
        concern_tags=tags,
        priors=base_priors,
    )

    # 3) semver
    checkers["semver"] = _check_semver_gate(
        plan,
        paths=clean,
        signals=signals,
        constraints=cons,
        concern_tags=tags,
    )

    # 4) no_hallucination (reuse Slice 8 hallucination findings only)
    hall = check_hallucination_guard(
        plan,
        paths=clean,
        signals=signals,
        evidence_text=evidence_text,
        constraints=cons,
    )
    checkers["no_hallucination"] = [
        GateFinding(
            gate="no_hallucination",
            code=f.code,
            message=f.message,
            token=f.token,
        )
        for f in hall
    ]

    # 5) inventory
    checkers["inventory"] = _check_inventory_gate(
        plan,
        paths=clean,
        signals=signals,
        concern_tags=tags,
        claim_tags=claim_tags,
        included_changes=included_changes,
        require_stub_note_tokens=require_stub_note_tokens,
    )

    # 6) craft (reuse Slice 8 craft findings)
    craft = check_craft_guard(
        plan,
        paths=clean,
        signals=signals,
        constraints=cons,
    )
    checkers["craft"] = [
        GateFinding(
            gate="craft",
            code=f.code,
            message=f.message,
            token=f.token,
        )
        for f in craft
    ]

    ordered_findings: list[GateFinding] = []
    status: list[tuple[str, str]] = []
    first_fail: str | None = None
    for gate in SLICE9_GATE_ORDER:
        hits = checkers.get(gate) or []
        if first_fail is None:
            if hits:
                first_fail = gate
                status.append((gate, "fail"))
                ordered_findings.extend(hits)
            else:
                status.append((gate, "pass"))
        else:
            # Still record later findings for diagnostics, but mark skip for first-fail semantics.
            if hits:
                status.append((gate, "skip"))
                ordered_findings.extend(hits)
            else:
                status.append((gate, "skip"))

    codes = tuple(dict.fromkeys(f.code for f in ordered_findings))
    return GateReport(
        findings=tuple(ordered_findings),
        first_fail_gate=first_fail,
        passed=first_fail is None,
        codes=codes,
        gate_status=tuple(status),
    )


def slice9_letter_map(corpus_eval_harness: dict | None = None) -> dict[str, str]:
    """Return the frozen A-N letter map (optionally from corpus eval_harness)."""
    default = {
        "A": "TIP-G2",
        "B": "TIP-G3",
        "C": "TIP-G4",
        "D": "TIP-G1",
        "E": "S9-E",
        "F": "TIP-G5",
        "G": "TIP-G6",
        "H": "S9-H",
        "I": "TIP-G7",
        "J": "TIP-G8",
        "K": "TIP-G9",
        "L": "TIP-G10",
        "M": "TIP-G11",
        "N": "TIP-G12",
    }
    if not corpus_eval_harness:
        return default
    raw = corpus_eval_harness.get("letter_map") or {}
    out = dict(default)
    out.update({str(k): str(v) for k, v in raw.items()})
    return out
