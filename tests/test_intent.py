from git_cg.intent import (
    _is_ci_path,
    _is_docs_path,
    _is_hook_path,
    _is_security_path,
    _is_test_path,
    extract_diff_file_summary,
    extract_diff_signals,
)


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
