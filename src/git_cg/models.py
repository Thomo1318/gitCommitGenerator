from __future__ import annotations

import enum

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
            raise ValueError(f"Intent '{self.intent_id}' or Emoji '{self.gitmoji}' is not in the GitOps SOP matrix.")

        self.gitmoji = entry["emoji"]

        # 2. Assert cc_type matches the matrix exactly
        if self.cc_type.value != entry.get("cc_type"):
            raise ValueError(
                f"Emoji / Type mismatch! According to the SOP matrix, the intent '{self.intent_id}' "
                f"MUST be paired with the type '{entry.get('cc_type')}'. You used '{self.cc_type.value}'."
            )
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
        if self.breaking_change and not self.breaking_change_description:
            raise ValueError("breaking_change_description must be provided if breaking_change is true")
        return self

    def render(self) -> str:
        """Render the structured commit plan into a standard Git commit message string."""
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
