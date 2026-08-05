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

from dataclasses import dataclass, field
from pathlib import PurePosixPath

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
    if roles == {"adr"}:
        name = DIFF_CLASS_ADR
    elif roles == {"fixtures"}:
        name = DIFF_CLASS_FIXTURES
    elif roles == {"tests"}:
        name = DIFF_CLASS_TESTS
    elif roles == {"docs"} or roles == {"docs", "release"}:
        name = DIFF_CLASS_DOCS
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
        force_scope = "test"
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
            scope_hint=normalize_scope("test"),
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

    if roles == {"docs"} or roles == {"docs", "release"}:
        # docs-only, including CHANGELOG-as-docs (+ release dual-label)
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
        "fallback_none_overwrite",
        "closed_enum",
        "rename_harden",
        "error_signal",
        "masking_none",
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
    return all(req in groups for req in required)


def min_included_change_bullets(
    paths: list[str],
    *,
    concern_tags: frozenset[str] | set[str] | None = None,
) -> int:
    """Minimum Included-changes bullet count from path surfaces + concerns (D18 light).

    Full stub generation is Slice 4; this is the cardinality floor only.
    """
    clean = [p for p in paths if p and str(p).strip()]
    if not clean:
        return 0

    tags = {t.lower() for t in (concern_tags or set())}
    surfaces = 0
    if any(_is_test_path(p) for p in clean):
        surfaces += 1
    if any(_is_docs_path(p) or _is_adr_path(p) for p in clean):
        surfaces += 1
    if any(not _is_test_path(p) and not _is_docs_path(p) and not _is_fixtures_path(p) for p in clean):
        surfaces += 1

    concern_count = len(tags) if tags else 0
    # Multi-concern product diffs: required_bullets = max(surfaces, concern_count)
    floor = max(surfaces, concern_count, 1 if clean else 0)
    # tests with product → at least 2 (prod + test)
    has_test = any(_is_test_path(p) for p in clean)
    has_prod = any(not _is_test_path(p) and not _is_docs_path(p) and not _is_fixtures_path(p) for p in clean)
    if has_test and has_prod:
        floor = max(floor, 2)
    return floor
