from __future__ import annotations

import enum
from dataclasses import dataclass

from pydantic import BaseModel, Field, model_validator


class CommitType(enum.StrEnum):
    """Conventional Commit types matching the GitOps SOP."""

    FEAT = "feat"
    FIX = "fix"
    DOCS = "docs"
    STYLE = "style"
    REFACTOR = "refactor"
    PERF = "perf"
    TEST = "test"
    BUILD = "build"
    CI = "ci"
    CHORE = "chore"
    REVERT = "revert"
    INIT = "init"
    RELEASE = "release"


class SemVerImpact(enum.StrEnum):
    """Semantic Versioning impact levels."""

    MAJOR = "MAJOR"
    MINOR = "MINOR"
    PATCH = "PATCH"
    NONE = "NONE"


class IssueReferenceKind(enum.StrEnum):
    """Supported structured issue-reference verbs for review-time insertion."""

    RESOLVES = "Resolves"
    REFS = "Refs"
    CLOSES = "Closes"
    FIXES = "Fixes"


@dataclass(frozen=True)
class IssueReference:
    """Python-owned structured issue reference inserted during interactive review."""

    kind: IssueReferenceKind
    issue_number: int

    def __post_init__(self) -> None:
        if not isinstance(self.issue_number, int):
            raise TypeError("issue_number must be an integer")
        if self.issue_number <= 0:
            raise ValueError("issue_number must be greater than zero")

    def __str__(self) -> str:
        """
        Format this issue reference as text.

        Returns:
            str: The rendered issue reference in the form `{kind.value}: #{issue_number}`.
        """
        return f"{self.kind.value}: #{self.issue_number}"


class CommitIntent(BaseModel):
    """A single structured commit intent."""

    intent_id: str = Field(description="The intent_id from the ranked candidates list")
    gitmoji: str = Field(description="The literal unicode emoji character (e.g., ✨)")
    cc_type: CommitType = Field(description="The Conventional Commit type")
    scope: str | None = Field(
        default=None,
        description="The scope of the commit, typically the module or file affected. Keep it short (e.g., 'ui', 'api').",
    )
    description: str = Field(description="The imperative description. Must be VERY concise (maximum 50 characters).")
    semver_impact: SemVerImpact = Field(description="The SemVer impact from the candidate list")
    changelog_group: str = Field(description="The changelog group from the candidate list")

    @model_validator(mode="after")
    def validate_and_correct_matrix(self) -> CommitIntent:
        """
        Align this CommitIntent to the canonical gitmoji SOP matrix, or apply a safe fallback.

        Looks up a matrix entry (from git_cg.sop.get_gitmoji_matrix) in this order: matching `intent_id`, then `emoji`, then `code`. If the matrix is unavailable, returns the instance unchanged. If no matching entry is found, selects the entry with `code == ":wrench:"` when present or the first matrix entry as a fallback. In both matched and fallback cases, replaces the matrix-owned fields `intent_id`, `gitmoji`, `cc_type`, `semver_impact`, and `changelog_group` with the values from the chosen matrix entry and returns the instance. Does not raise on missing matrix data.

        Returns:
            CommitIntent: The same instance after canonicalisation or fallback application.
        """
        from git_cg.sop import get_gitmoji_matrix

        matrix = get_gitmoji_matrix()
        if not matrix:
            # SOP genuinely unavailable — cannot enforce; skip rather than crash.
            return self

        # 1. Lookup by intent_id or fallback to emoji/code
        entry = next((item for item in matrix if item.get("intent_id") == self.intent_id), None)
        if not entry:
            entry = next((item for item in matrix if item.get("emoji") == self.gitmoji), None)
        if not entry:
            entry = next((item for item in matrix if item.get("code") == self.gitmoji), None)

        if not entry:
            # Graceful fallback: If the LLM hallucinates an intent (especially for secondary changes
            # where it doesn't have the full matrix in the prompt), coerce it to a safe default
            # rather than crashing the commit loop.
            entry = next((item for item in matrix if item.get("code") == ":wrench:"), matrix[0])

            fallback_intent_id = entry.get("intent_id")
            if not fallback_intent_id:
                fallback_code = entry.get("code")
                fallback_intent_id = str(fallback_code or "fallback_chore").strip(":")

            self.intent_id = fallback_intent_id
            self.gitmoji = entry["emoji"]
            self.cc_type = CommitType(entry["cc_type"])
            self.semver_impact = SemVerImpact(entry["semver_impact"])
            self.changelog_group = entry["changelog_group"]
            return self

        # Canonicalize all matrix-owned semantic fields for matched rows.
        intent_id = entry.get("intent_id")
        if not intent_id:
            code = entry.get("code")
            intent_id = str(code or "unknown").strip(":")

        self.intent_id = intent_id
        self.gitmoji = entry["emoji"]
        self.cc_type = CommitType(entry["cc_type"])
        self.semver_impact = SemVerImpact(entry["semver_impact"])
        self.changelog_group = entry["changelog_group"]

        return self


class CommitPlan(BaseModel):
    """
    A structured commit plan replacing the flat Commit model.
    Handles multiple intents, split detection, and trailers.
    """

    primary_intent: CommitIntent = Field(description="The dominant, primary reason for this commit.")
    secondary_intents: list[CommitIntent] = Field(
        default_factory=list,
        description="Other distinct intents included in this diff (e.g., docs, chores, side-fixes).",
    )
    split_recommended: bool = Field(
        default=False,
        description="True if the changes are unrelated and should ideally be split into multiple atomic commits.",
    )
    rationale: str = Field(
        description="Brief explanation of why the primary intent was chosen over others, and why a split is or isn't recommended."
    )
    body_summary: str | None = Field(
        default=None, description="Detailed explanation of the changes. Explain the 'why' and 'how'."
    )
    breaking_change: bool = Field(
        default=False, description="Whether this commit introduces a backwards-incompatible breaking change."
    )
    breaking_change_description: str | None = Field(
        default=None, description="Explanation of the breaking change. Required if breaking_change is true."
    )

    @model_validator(mode="after")
    def validate_breaking_change(self) -> CommitPlan:
        """
        Validate that a breaking-change description is present when breaking_change is True.

        Raises:
            ValueError: If `breaking_change` is True and `breaking_change_description` is missing or empty.

        Returns:
            CommitPlan: The same CommitPlan instance (`self`).
        """
        if self.breaking_change and not self.breaking_change_description:
            raise ValueError("breaking_change_description must be provided if breaking_change is true")
        return self

    def render(self, issue_references: list[IssueReference] | None = None) -> str:
        """
        Render the commit plan as a complete Git commit message.

        Parameters:
            issue_references (list[IssueReference] | None): Optional list of issue references to append immediately above the machine-readable trailers; pass None or omit to exclude issue reference lines.

        Returns:
            commit_message (str): The full commit message including header, optional body summary, included changes, issue reference lines (if provided), machine-readable trailers (SemVer-Impact, Change-Types, Changelog-Groups), and an optional breaking change footer.
        """
        # Header
        scope_str = f"({self.primary_intent.scope})" if self.primary_intent.scope else ""
        breaking_indicator = "!" if self.breaking_change else ""
        header = f"{self.primary_intent.gitmoji} {self.primary_intent.cc_type.value}{scope_str}{breaking_indicator}: {self.primary_intent.description}"

        lines = [header]

        # Body Summary
        if self.body_summary:
            lines.append("")
            # Fix literal escaped newlines output by the LLM in JSON strings
            clean_body = self.body_summary.replace("\\n", "\n")
            lines.append(clean_body)

        # Included Changes (Secondary Intents)
        if self.secondary_intents:
            lines.append("")
            lines.append("Included changes:")
            for sec in self.secondary_intents:
                sec_scope = f"({sec.scope})" if sec.scope else ""
                lines.append(f"- {sec.gitmoji} {sec.cc_type.value}{sec_scope}: {sec.description}")

        # Structured issue references must render above machine-readable trailers.
        if issue_references:
            lines.append("")
            lines.extend(str(issue_reference) for issue_reference in issue_references)

        # Machine-readable Trailers
        all_intents = [self.primary_intent, *self.secondary_intents]

        impact_weights = {"MAJOR": 3, "MINOR": 2, "PATCH": 1, "NONE": 0}
        max_impact_val = max(impact_weights[intent.semver_impact.value] for intent in all_intents)
        if self.breaking_change:
            max_impact_val = 3

        val_to_impact = {3: "MAJOR", 2: "MINOR", 1: "PATCH", 0: "NONE"}
        overall_impact = val_to_impact[max_impact_val]

        cc_types = []
        changelog_groups = []
        types_seen = set()
        groups_seen = set()

        for intent in all_intents:
            if intent.cc_type.value not in types_seen:
                types_seen.add(intent.cc_type.value)
                cc_types.append(intent.cc_type.value)
            if intent.changelog_group not in groups_seen:
                groups_seen.add(intent.changelog_group)
                changelog_groups.append(intent.changelog_group)

        lines.extend(
            [
                "",
                f"SemVer-Impact: {overall_impact}",
                f"Change-Types: {', '.join(cc_types)}",
                f"Changelog-Groups: {', '.join(changelog_groups)}",
            ]
        )

        # Footer (Breaking Change)
        if self.breaking_change and self.breaking_change_description:
            lines.append("")
            lines.append(f"BREAKING CHANGE: {self.breaking_change_description}")

        return "\n".join(lines)
