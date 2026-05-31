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


class Commit(BaseModel):
    """
    A structured representation of a Conventional Commit message.
    The LLM must generate responses matching this schema.
    """

    gitmoji: str = Field(
        description="The literal unicode emoji character (e.g., ✨). Do NOT use markdown shortcodes like :sparkles:."
    )
    cc_type: CommitType = Field(description="The Conventional Commit type.")
    scope: str | None = Field(
        default=None,
        description="The scope of the commit, typically the module or file affected. Keep it short (e.g., 'ui', 'api').",
    )
    description: str = Field(
        description="The imperative description of what this commit does (e.g., 'add new feature'). Must be VERY concise (maximum 50 characters) so the entire subject line stays strictly under 72 characters."
    )
    body: str | None = Field(
        default=None, description="Detailed explanation of the changes. Explain the 'why' and 'how'."
    )
    breaking_change: bool = Field(
        default=False, description="Whether this commit introduces a backwards-incompatible breaking change."
    )
    breaking_change_description: str | None = Field(
        default=None, description="Explanation of the breaking change. Required if breaking_change is true."
    )

    @model_validator(mode="after")
    def validate_breaking_change(self) -> Commit:
        if self.breaking_change and not self.breaking_change_description:
            raise ValueError("breaking_change_description must be provided if breaking_change is true")
        return self

    @model_validator(mode="after")
    def validate_and_correct_matrix(self) -> Commit:
        import json
        import os

        sop_path = os.path.join(os.getcwd(), "config", "gitops_agent_sop.json")
        if not os.path.exists(sop_path):
            sop_path = os.path.join(os.getcwd(), "config", "gitCommitGenerator", "config", "gitops_agent_sop.json")

        if os.path.exists(sop_path):
            try:
                with open(sop_path) as f:
                    sop_data = json.load(f)
                    matrix = sop_data.get("gitmoji_reference_matrix", [])

                    # 1. Ensure the emoji is valid
                    entry = next((item for item in matrix if item.get("emoji") == self.gitmoji), None)
                    if not entry:
                        # Try fallback matching by code (e.g. :sparkles:)
                        entry = next((item for item in matrix if item.get("code") == self.gitmoji), None)
                        if entry:
                            self.gitmoji = entry["emoji"]
                        else:
                            raise ValueError(
                                f"Emoji '{self.gitmoji}' is not in the GitOps SOP matrix. Please select a valid literal unicode emoji."
                            )

                    # 2. Assert cc_type matches the matrix exactly
                    if entry and self.cc_type.value != entry.get("cc_type"):
                        raise ValueError(
                            f"Emoji / Type mismatch! According to the SOP matrix, the emoji '{self.gitmoji}' MUST be paired with the type '{entry.get('cc_type')}'. You used '{self.cc_type.value}'. Please correct either the emoji or the type to match the SOP."
                        )
            except ValueError:
                raise
            except Exception:
                pass
        return self

    def render(self) -> str:
        """Render the structured commit into a standard Git commit message string."""
        # Header
        scope_str = f"({self.scope})" if self.scope else ""
        breaking_indicator = "!" if self.breaking_change else ""
        header = f"{self.gitmoji} {self.cc_type.value}{scope_str}{breaking_indicator}: {self.description}"

        lines = [header]

        # Body
        if self.body:
            lines.append("")
            lines.append(self.body)

        # Footer (Breaking Change)
        if self.breaking_change and self.breaking_change_description:
            lines.append("")
            lines.append(f"BREAKING CHANGE: {self.breaking_change_description}")

        return "\n".join(lines)
