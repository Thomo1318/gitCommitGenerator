"""
Phase 7.5 (#180) R9 — template-drift guard for issue templates.

Heading-presence only (not body prose). Prevents silent section drift of the
📡 Telemetry (Opik / Sentry) contract blocks across `.github/ISSUE_TEMPLATE/*.md`.
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
