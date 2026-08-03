"""
Template-drift guards for GitHub issue + PR templates.

Heading-presence only (not body prose). Prevents silent section drift of the
📡 Telemetry (Opik / Sentry) contract blocks across `.github/ISSUE_TEMPLATE/*.md`,
and locks the PR template's required Architecture / Flow state diagram.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / ".github" / "ISSUE_TEMPLATE"

REQUIRED_HEADINGS = (
    "## 📡 Telemetry (Opik / Sentry)",
    "### Field tables",
    "### Non-goals",
    "### Acceptance hooks",
)


def _template_files() -> list[Path]:
    return sorted(TEMPLATE_DIR.glob("*.md"))


@pytest.mark.parametrize("template_path", _template_files(), ids=lambda p: p.name)
def test_issue_template_has_telemetry_contract_headings(template_path: Path):
    """Each issue template must retain the telemetry contract headings."""
    text = template_path.read_text(encoding="utf-8")
    missing = [h for h in REQUIRED_HEADINGS if h not in text]
    assert not missing, f"{template_path.name} missing headings: {missing}"


def test_issue_templates_exist():
    """Guard against accidental deletion of the whole template set."""
    files = _template_files()
    assert files, "expected at least one .github/ISSUE_TEMPLATE/*.md file"
    names = {p.name for p in files}
    for required in (
        "architectural_task.md",
        "bug_report.md",
        "feature_request.md",
        "implementation_task.md",
    ):
        assert required in names


PR_TEMPLATE = REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"


def test_pr_template_exists():
    """Guard against accidental deletion of the PR template."""
    assert PR_TEMPLATE.is_file()


def test_pr_template_requires_state_diagram():
    """PR Architecture / Flow must always require a Mermaid stateDiagram-v2."""
    text = PR_TEMPLATE.read_text(encoding="utf-8")
    assert "## 🗺️ Architecture / Flow" in text
    start = text.index("## 🗺️ Architecture / Flow")
    # Next top-level section after Architecture / Flow
    rest = text[start + 1 :]
    next_heading_idx = rest.find("\n## ")
    section = text[start : start + 1 + next_heading_idx] if next_heading_idx != -1 else text[start:]
    assert "stateDiagram-v2" in section
    assert "```mermaid" in section
    fence_body = section.split("```mermaid", 1)[1].split("```", 1)[0]
    assert "stateDiagram-v2" in fence_body
    lowered = section.lower()
    assert "delete this entire section if n/a" not in lowered
    assert "optional." not in lowered
