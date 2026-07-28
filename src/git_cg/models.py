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
    NULL = "Null"


@dataclass(frozen=True)
class IssueReference:
    """Python-owned structured issue reference inserted during interactive review."""

    kind: IssueReferenceKind
    issue_number: int

    def __post_init__(self) -> None:
        if not isinstance(self.issue_number, int):
            raise TypeError("issue_number must be an integer")
        if self.issue_number < 0:
            raise ValueError("issue_number must be zero or greater")

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
        Align the intent with the canonical SOP matrix or apply a safe fallback.

        If the matrix is unavailable, the intent is returned unchanged. Otherwise, matching or fallback matrix values replace its matrix-owned fields.

        Returns:
                CommitIntent: The canonicalised or fallback-adjusted intent.
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


class ModelCommitIntent(BaseModel):
    """LLM-facing commit intent: unknown matrix ids fail validation (no coerce).

    Internal/deterministic paths continue to use ``CommitIntent``, which may
    canonicalise or fall back to a safe matrix row. Instructor reask surfaces
    failures from this model-facing schema.
    """

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
    def reject_unknown_matrix_intent(self) -> ModelCommitIntent:
        """
        Validate that the intent identifier exists in the live SOP matrix.

        Returns:
                ModelCommitIntent: This model when its intent identifier is present or the SOP matrix is unavailable.

        Raises:
                ValueError: If the intent identifier is absent from the available SOP matrix.
        """
        from git_cg.sop import get_gitmoji_matrix

        matrix = get_gitmoji_matrix()
        if not matrix:
            # Cannot enforce without SOP; allow through (contract enforcement still applies).
            return self

        entry = next((item for item in matrix if item.get("intent_id") == self.intent_id), None)
        if entry is None:
            known = sorted(
                {
                    str(item.get("intent_id") or str(item.get("code") or "").strip(":"))
                    for item in matrix
                    if item.get("intent_id") or item.get("code")
                }
            )
            preview = ", ".join(known[:12])
            more = "" if len(known) <= 12 else f", … ({len(known)} total)"
            raise ValueError(
                f"Unknown intent_id {self.intent_id!r} is not present in the SOP matrix. "
                f"Select an intent_id from the ranked candidates or matrix vocabulary "
                f"(examples: {preview}{more})."
            )
        return self

    def to_commit_intent(self) -> CommitIntent:
        """
        Convert the model-facing intent into an internal commit intent.

        Returns:
                CommitIntent: The corresponding internal intent, with matrix canonicalisation applied when applicable.
        """
        return CommitIntent(
            intent_id=self.intent_id,
            gitmoji=self.gitmoji,
            cc_type=self.cc_type,
            scope=self.scope,
            description=self.description,
            semver_impact=self.semver_impact,
            changelog_group=self.changelog_group,
        )


def _require_breaking_change_description(*, breaking_change: bool, breaking_change_description: str | None) -> None:
    """Raise if a breaking change is marked without a description.

    Shared by CommitPlan and ModelCommitPlan validators so the error contract stays identical.
    """
    if breaking_change and not breaking_change_description:
        raise ValueError("breaking_change_description must be provided if breaking_change is true")


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
        _require_breaking_change_description(
            breaking_change=self.breaking_change,
            breaking_change_description=self.breaking_change_description,
        )
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

        # Machine-readable trailers (and optional issue refs) form one contiguous
        # block: no blank lines between issue refs and SemVer/Change-Types/Changelog.
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

        trailer_block: list[str] = []
        if issue_references:
            trailer_block.extend(str(issue_reference) for issue_reference in issue_references)
        trailer_block.extend(
            [
                f"SemVer-Impact: {overall_impact}",
                f"Change-Types: {', '.join(cc_types)}",
                f"Changelog-Groups: {', '.join(changelog_groups)}",
            ]
        )
        # Exactly one blank line separates body/included-changes from the trailer block.
        lines.append("")
        lines.extend(trailer_block)

        # Footer (Breaking Change)
        if self.breaking_change and self.breaking_change_description:
            lines.append("")
            lines.append(f"BREAKING CHANGE: {self.breaking_change_description}")

        return "\n".join(lines)


class ModelCommitPlan(BaseModel):
    """LLM-facing commit plan using strict ModelCommitIntent validation."""

    primary_intent: ModelCommitIntent = Field(description="The dominant, primary reason for this commit.")
    secondary_intents: list[ModelCommitIntent] = Field(
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
    def validate_breaking_change(self) -> ModelCommitPlan:
        """
        Validate that a breaking-change description is provided when required.

        Returns:
                ModelCommitPlan: This model after validation.

        Raises:
                ValueError: If `breaking_change` is true and no description is provided.
        """
        _require_breaking_change_description(
            breaking_change=self.breaking_change,
            breaking_change_description=self.breaking_change_description,
        )
        return self

    def to_commit_plan(self) -> CommitPlan:
        """Convert a validated model-facing plan into the internal CommitPlan."""
        return CommitPlan(
            primary_intent=self.primary_intent.to_commit_intent(),
            secondary_intents=[item.to_commit_intent() for item in self.secondary_intents],
            split_recommended=self.split_recommended,
            rationale=self.rationale,
            body_summary=self.body_summary,
            breaking_change=self.breaking_change,
            breaking_change_description=self.breaking_change_description,
        )
