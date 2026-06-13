from git_cg.intent import (
    _is_ci_path,
    _is_docs_path,
    _is_hook_path,
    _is_security_path,
    _is_test_path,
    extract_diff_file_summary,
    extract_diff_signals,
)
from git_cg.models import CommitIntent, CommitType, SemVerImpact


def test_is_hook_path():
    assert _is_hook_path(".git/hooks/pre-commit") is True
    assert _is_hook_path("hk.pkl") is True
    assert _is_hook_path("src/main.py") is False


def test_is_security_path():
    assert _is_security_path("src/auth/jwt.py") is True
    assert _is_security_path("src/secrets/manager.py") is True
    assert _is_security_path("src/api/routes.py") is False


def test_is_docs_path():
    assert _is_docs_path("README.md") is True
    assert _is_docs_path("docs/api.rst") is True
    assert _is_docs_path("src/utils.py") is False


def test_is_test_path():
    assert _is_test_path("tests/test_intent.py") is True
    assert _is_test_path("src/components/button.spec.tsx") is True
    assert _is_test_path("src/main.py") is False


def test_is_ci_path():
    assert _is_ci_path(".github/workflows/test.yml") is True
    assert _is_ci_path("azure-pipelines.yml") is True
    assert _is_ci_path("src/utils.py") is False


def test_extract_diff_file_summary():
    diff = """diff --git a/old_name.py b/new_name.py
similarity index 100%
rename from old_name.py
rename to new_name.py
diff --git a/deleted.py b/deleted.py
deleted file mode 100644
diff --git a/added.py b/added.py
new file mode 100644
"""
    summary = extract_diff_file_summary(diff)
    assert "new_name.py" in summary.paths
    assert ("old_name.py", "new_name.py") in summary.renamed_paths
    assert "deleted.py" in summary.deleted_paths
    assert "added.py" in summary.added_paths


def test_extract_diff_signals_metrics_and_booleans():
    diff = """diff --git a/src/api.py b/src/api.py
--- a/src/api.py
+++ b/src/api.py
@@ -1,2 +1,4 @@
 def old_func(): pass
+def new_func(): pass
+    # BREAKING CHANGE: changed behavior
-def old_func2(): pass
"""
    signals = extract_diff_signals(diff)
    assert signals.lines_added == 2
    assert signals.lines_removed == 1
    assert signals.files_changed_count == 1
    assert "src/api.py" in signals.files
    assert signals.has_breaking_change is True
    assert signals.adds_public_api is True


def test_commit_intent_canonicalizes_semantics_for_matched_intent_id(monkeypatch):
    matrix = [
        {
            "intent_id": "feature_addition",
            "emoji": "✨",
            "code": ":sparkles:",
            "cc_type": "feat",
            "semver_impact": "MINOR",
            "changelog_group": "Added",
        }
    ]
    monkeypatch.setattr("git_cg.sop.get_gitmoji_matrix", lambda: matrix)

    intent = CommitIntent(
        intent_id="feature_addition",
        gitmoji="🧪",
        cc_type=CommitType.CHORE,
        description="add feature",
        semver_impact=SemVerImpact.NONE,
        changelog_group="Miscellaneous",
    )

    assert intent.intent_id == "feature_addition"
    assert intent.gitmoji == "✨"
    assert intent.cc_type == CommitType.FEAT
    assert intent.semver_impact == SemVerImpact.MINOR
    assert intent.changelog_group == "Added"


def test_commit_intent_canonicalizes_intent_id_when_resolved_by_emoji(monkeypatch):
    matrix = [
        {
            "intent_id": "feature_addition",
            "emoji": "✨",
            "code": ":sparkles:",
            "cc_type": "feat",
            "semver_impact": "MINOR",
            "changelog_group": "Added",
        }
    ]
    monkeypatch.setattr("git_cg.sop.get_gitmoji_matrix", lambda: matrix)

    intent = CommitIntent(
        intent_id="unknown_intent",
        gitmoji="✨",
        cc_type=CommitType.CHORE,
        description="add feature",
        semver_impact=SemVerImpact.NONE,
        changelog_group="Miscellaneous",
    )

    assert intent.intent_id == "feature_addition"
    assert intent.gitmoji == "✨"
    assert intent.cc_type == CommitType.FEAT
    assert intent.semver_impact == SemVerImpact.MINOR
    assert intent.changelog_group == "Added"


def test_commit_intent_unknown_intent_falls_back_to_wrench_entry(monkeypatch):
    """
    Verify that an unknown intent is resolved to the "configuration_update" (wrench) matrix entry and its semantic fields are canonicalised.

    When the provided `intent_id` is not found and the `gitmoji` does not match any matrix entry, the intent should fall back to the wrench/configuration_update entry from the gitmoji matrix and adopt that entry's `emoji`, `cc_type`, `semver_impact` and `changelog_group`.
    """
    matrix = [
        {
            "intent_id": "feature_addition",
            "emoji": "✨",
            "code": ":sparkles:",
            "cc_type": "feat",
            "semver_impact": "MINOR",
            "changelog_group": "Added",
        },
        {
            "intent_id": "configuration_update",
            "emoji": "🔧",
            "code": ":wrench:",
            "cc_type": "chore",
            "semver_impact": "NONE",
            "changelog_group": "Miscellaneous",
        },
    ]
    monkeypatch.setattr("git_cg.sop.get_gitmoji_matrix", lambda: matrix)

    intent = CommitIntent(
        intent_id="unknown_intent",
        gitmoji="❓",
        cc_type=CommitType.FEAT,
        description="mystery change",
        semver_impact=SemVerImpact.MAJOR,
        changelog_group="Added",
    )

    assert intent.intent_id == "configuration_update"
    assert intent.gitmoji == "🔧"
    assert intent.cc_type == CommitType.CHORE
    assert intent.semver_impact == SemVerImpact.NONE
    assert intent.changelog_group == "Miscellaneous"
