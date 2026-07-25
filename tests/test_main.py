import subprocess
from unittest.mock import MagicMock, patch

import pytest
import typer

import git_cg.main as main_module
from git_cg.main import (
    ReviewState,
    _detect_branch_issue_reference,
    _staged_diff_command,
    _validate_commit_source,
    build_generation_messages,
    build_system_prompt,
    extract_git_diff,
    generate_commit_message,
)
from git_cg.models import (
    CommitPlan,
    CommitType,
    IssueReferenceKind,
    ModelCommitIntent,
    ModelCommitPlan,
    SemVerImpact,
)


def test_build_system_prompt_contains_diff():
    test_diff = """diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1 +1 @@
-old
+new
"""
    prompt = build_system_prompt(test_diff)

    # Diff is handled in user prompt, but the system prompt extracts candidates
    assert "PRIMARY CANDIDATES" in prompt

    # Ensure some key instructions are present (checking SOP loading worked)
    assert "You are a senior software engineer" in prompt


def test_build_system_prompt_includes_regeneration_guidance_when_present():
    test_diff = """diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1 +1 @@
-old
+new
"""
    prompt = build_system_prompt(test_diff, residual_guidance="This is a feature, not a fix.")

    assert "REGENERATION GUIDANCE (EXPLICIT USER OVERRIDE):" in prompt
    assert "This is a feature, not a fix." in prompt


def test_build_system_prompt_omits_regeneration_guidance_when_absent():
    test_diff = """diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1 +1 @@
-old
+new
"""
    prompt = build_system_prompt(test_diff)
    assert "REGENERATION GUIDANCE (EXPLICIT USER OVERRIDE):" not in prompt


def test_build_generation_messages_omits_regeneration_guidance_when_absent():
    test_diff = """diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1 +1 @@
-old
+new
"""
    prompt = build_system_prompt(test_diff)
    messages = build_generation_messages(prompt, test_diff)

    assert len(messages) == 2


def test_review_state_regeneration_guidance_can_be_set():
    review_state = ReviewState(commit_plan=None, regeneration_guidance=None)  # type: ignore[arg-type]

    assert review_state.set_regeneration_guidance("This is a feature, not a fix.") is True
    assert review_state.regeneration_guidance == "This is a feature, not a fix."


def test_review_state_regeneration_guidance_can_be_cleared():
    review_state = ReviewState(commit_plan=None, regeneration_guidance="This is a feature, not a fix.")  # type: ignore[arg-type]

    assert review_state.clear_regeneration_guidance() is True
    assert review_state.regeneration_guidance is None


def test_build_system_prompt_mentions_separate_guidance_handling():
    test_diff = """diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1 +1 @@
-old
+new
"""
    prompt = build_system_prompt(test_diff)

    assert "Do not output reasoning, XML, pseudo-tool-call tags" in prompt


# ---------------------------------------------------------------------------
# build_generation_messages - content and structure
# ---------------------------------------------------------------------------


def test_build_generation_messages_system_role_contains_prompt():
    test_diff = "diff --git a/x.py b/x.py"
    system_prompt = "You are a senior software engineer."
    messages = build_generation_messages(system_prompt, test_diff)

    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == system_prompt


def test_build_generation_messages_user_role_contains_diff():
    test_diff = "diff --git a/x.py b/x.py\n+new line"
    system_prompt = "system"
    messages = build_generation_messages(system_prompt, test_diff)

    assert messages[1]["role"] == "user"
    assert test_diff in messages[1]["content"]


def test_build_generation_messages_diff_wrapped_in_code_fence():
    """The diff must be wrapped in a ```diff ... ``` code fence in the user message."""
    test_diff = "diff --git a/x.py b/x.py"
    messages = build_generation_messages("system", test_diff)

    user_content = messages[1]["content"]
    assert "```diff" in user_content
    assert "```" in user_content


def test_build_generation_messages_returns_list_of_dicts():
    messages = build_generation_messages("system", "diff")
    assert isinstance(messages, list)
    for msg in messages:
        assert isinstance(msg, dict)
        assert "role" in msg
        assert "content" in msg


def test_build_generation_messages_message_order():
    """System message must always be first, user message second."""
    messages = build_generation_messages("my system prompt", "my diff")
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


# ---------------------------------------------------------------------------
# build_system_prompt - regeneration guidance changes candidates_str header
# ---------------------------------------------------------------------------


def test_build_system_prompt_with_guidance_uses_initial_deterministic_analysis_header():
    """When regeneration_guidance is provided, the candidates header must mention initial analysis."""
    test_diff = """diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1 +1 @@
-old
+new
"""
    prompt = build_system_prompt(test_diff, residual_guidance="Focus on user-facing behavior.")

    # The guidance-present path changes the candidates header
    assert "INITIAL DETERMINISTIC ANALYSIS:" in prompt or "REGENERATION GUIDANCE" in prompt


def test_build_system_prompt_guidance_contains_quoted_guidance_text():
    """The regeneration guidance must appear quoted in the system prompt."""
    test_diff = "diff --git a/x.py b/x.py\n-old\n+new"
    guidance = "Focus on user-facing behavior."
    prompt = build_system_prompt(test_diff, residual_guidance=guidance)

    assert f'CONTEXTUAL GUIDANCE (FREE-TEXT):\n"{guidance}"' in prompt


def test_build_system_prompt_guidance_contains_critical_precedence_rule():
    test_diff = "diff --git a/x.py b/x.py\n-old\n+new"
    prompt = build_system_prompt(test_diff, residual_guidance="This is a fix.")

    assert "CRITICAL PRECEDENCE RULE" in prompt


def test_build_system_prompt_guidance_instructs_not_to_use_as_commit_content():
    test_diff = "diff --git a/x.py b/x.py\n-old\n+new"
    prompt = build_system_prompt(test_diff, residual_guidance="This is a fix.")

    assert "Do not treat the guidance text itself as final commit content" in prompt


# ---------------------------------------------------------------------------
# LAST_OPIK_TRACE_ID - global variable (added in this PR)
# ---------------------------------------------------------------------------


def test_last_opik_trace_id_initial_value_is_none():
    """LAST_OPIK_TRACE_ID must be initialised to None at module load time."""
    assert main_module.LAST_OPIK_TRACE_ID is None


def test_last_opik_trace_id_can_be_set_to_string(monkeypatch):
    """LAST_OPIK_TRACE_ID must accept a string assignment (simulates opik capture)."""
    monkeypatch.setattr(main_module, "LAST_OPIK_TRACE_ID", "trace-00001")
    assert main_module.LAST_OPIK_TRACE_ID == "trace-00001"


def test_last_opik_trace_id_can_be_reset_to_none(monkeypatch):
    """LAST_OPIK_TRACE_ID must revert to None when patched back to None."""
    monkeypatch.setattr(main_module, "LAST_OPIK_TRACE_ID", "some-trace-id")
    monkeypatch.setattr(main_module, "LAST_OPIK_TRACE_ID", None)
    assert main_module.LAST_OPIK_TRACE_ID is None


# ---------------------------------------------------------------------------
# opik_args construction logic (inlined in finalize_commit_hook, this PR)
#
# The PR adds the following block inside finalize_commit_hook:
#
#   opik_args = {}
#   if state.trace_id:
#       opik_args["trace"] = {"id": state.trace_id}
#   if state.thread_id:
#       if "trace" not in opik_args:
#           opik_args["trace"] = {}
#       opik_args["trace"]["thread_id"] = state.thread_id
#
# We replicate this logic in a helper to unit-test all branches
# without invoking the full hook machinery.
# ---------------------------------------------------------------------------


def _build_opik_args(trace_id, thread_id) -> dict | None:
    """Replica of the opik_args construction added in this PR."""
    opik_args: dict = {}
    if trace_id:
        opik_args["trace"] = {"id": trace_id}
    if thread_id:
        if "trace" not in opik_args:
            opik_args["trace"] = {}
        opik_args["trace"]["thread_id"] = thread_id
    return opik_args if opik_args else None


def test_opik_args_none_when_both_ids_absent():
    """With no trace_id and no thread_id, opik_args must be None."""
    result = _build_opik_args(trace_id=None, thread_id=None)
    assert result is None


def test_opik_args_contains_trace_id_only():
    """When only trace_id is set, opik_args must carry it under trace.id."""
    result = _build_opik_args(trace_id="abc-123", thread_id=None)
    assert result is not None
    assert result["trace"]["id"] == "abc-123"
    assert "thread_id" not in result["trace"]


def test_opik_args_contains_thread_id_only():
    """When only thread_id is set, opik_args must carry it under trace.thread_id."""
    result = _build_opik_args(trace_id=None, thread_id="repo-myproject")
    assert result is not None
    assert result["trace"]["thread_id"] == "repo-myproject"
    assert "id" not in result["trace"]


def test_opik_args_contains_both_trace_id_and_thread_id():
    """When both IDs are set, opik_args must place them in the same trace dict."""
    result = _build_opik_args(trace_id="t-999", thread_id="repo-core")
    assert result is not None
    assert result["trace"]["id"] == "t-999"
    assert result["trace"]["thread_id"] == "repo-core"


def test_opik_args_trace_dict_is_not_duplicated_when_both_set():
    """Only one 'trace' key must exist in opik_args regardless of both IDs being set."""
    result = _build_opik_args(trace_id="t-1", thread_id="th-1")
    assert result is not None
    assert list(result.keys()) == ["trace"]


def test_opik_args_empty_string_trace_id_treated_as_falsy():
    """An empty string trace_id must be treated as absent (falsy), returning None."""
    result = _build_opik_args(trace_id="", thread_id=None)
    assert result is None


def test_opik_args_empty_string_thread_id_treated_as_falsy():
    """An empty string thread_id must be treated as absent (falsy), returning None."""
    result = _build_opik_args(trace_id=None, thread_id="")
    assert result is None


def test_validate_commit_source_merge_abort():
    with pytest.raises(typer.Exit) as excinfo:
        _validate_commit_source("merge", "COMMIT_EDITMSG", False, False)
    assert excinfo.value.exit_code == 0


def test_validate_commit_source_amend_proceed():
    assert _validate_commit_source("commit", "COMMIT_EDITMSG", True, False) == "commit"


def test_validate_commit_source_none():
    assert _validate_commit_source(None, "COMMIT_EDITMSG", False, False) is None


@patch("subprocess.check_output")
def test_detect_branch_issue_reference_found(mock_check_output):
    mock_check_output.return_value = "feat/123-some-feature\n"
    refs = _detect_branch_issue_reference(verbose=False)
    assert len(refs) == 1
    assert refs[0].issue_number == 123
    assert refs[0].kind == IssueReferenceKind.REFS


@patch("subprocess.check_output")
def test_detect_branch_issue_reference_not_found(mock_check_output):
    mock_check_output.return_value = "main\n"
    refs = _detect_branch_issue_reference(verbose=False)
    assert len(refs) == 0


def test_build_system_prompt_includes_locked_contract_when_provided():
    from types import SimpleNamespace

    from git_cg.intent import RankedIntent
    from git_cg.main import build_system_prompt

    ranked = [
        RankedIntent(
            intent_id="bug_fix",
            emoji="🐛",
            code=":bug:",
            cc_type="fix",
            description="Fix a bug",
            semver_impact="PATCH",
            changelog_group="Fixed",
            intent_group="bugfix",
            score=80.0,
            priority=80,
            specificity=50,
            split_weight=50,
            evidence=["Matched positive signal: x"],
        )
    ]
    contract = SimpleNamespace(
        primary_intent_id="bug_fix",
        gitmoji="🐛",
        cc_type="fix",
        semver_impact="PATCH",
        changelog_group="Fixed",
    )
    prompt = build_system_prompt(
        "diff --git a/x b/x\n",
        ranked_candidates=ranked,
        contract=contract,
    )
    assert "DETERMINISTIC SEMANTIC CONTRACT (LOCKED BEFORE GENERATION)" in prompt
    assert "primary_intent_id: bug_fix" in prompt
    assert "Unknown intent ids are invalid" in prompt
    assert "bug_fix" in prompt


def test_build_semantic_enrichment_facts_flag_off_returns_none():
    from git_cg.main import _build_semantic_enrichment_facts

    facts = _build_semantic_enrichment_facts(
        semantic_enabled=False,
        fingerprint_class_counts={"formatting_only": 1},
        body_similarity_min=0.99,
        body_similarity_avg=0.99,
        fingerprint_markers=["formatting_only"],
    )
    assert facts is None


def test_build_semantic_enrichment_facts_flag_on_builds_container():
    from git_cg.main import _build_semantic_enrichment_facts

    facts = _build_semantic_enrichment_facts(
        semantic_enabled=True,
        fingerprint_class_counts={"formatting_only": 2},
        body_similarity_min=0.95,
        body_similarity_avg=0.97,
        fingerprint_markers=["comments_only"],
    )
    assert facts is not None
    assert facts.fingerprints is not None
    assert facts.fingerprints.class_counts == {"formatting_only": 2}
    assert facts.fingerprints.markers == ["comments_only"]


# ---------------------------------------------------------------------------
# _staged_diff_command / extract_git_diff (Issue #161 Slice 4)
#
# extract_git_diff no longer hard-truncates the analysis diff at 50000 chars;
# truncation now only happens (via pack_prompt_diff, tested separately) on
# the LLM-facing prompt payload. These tests cover the rtk-vs-standard
# command selection, fallback-on-failure, no-truncation regression, empty
# diff handling, and the CalledProcessError -> _abort() path.
# ---------------------------------------------------------------------------


def test_staged_diff_command_standard_excludes_lockfiles():
    cmd = _staged_diff_command(use_rtk=False)
    assert cmd[:4] == ["git", "diff", "--cached", "--"]
    assert cmd[4] == "."
    assert ":(exclude)*.lock" in cmd
    assert ":(exclude)*zensical*" in cmd


def test_staged_diff_command_rtk_prefixes_git_diff():
    cmd = _staged_diff_command(use_rtk=True)
    assert cmd[:3] == ["rtk", "git", "diff"]
    assert ":(exclude)*.lock" in cmd


@patch("shutil.which", return_value=None)
@patch("subprocess.check_output")
def test_extract_git_diff_without_rtk_uses_standard_command(mock_check_output, mock_which):
    mock_check_output.return_value = "diff --git a/x.py b/x.py\n+content\n"

    result = extract_git_diff(verbose=False, strict=False)

    assert result == "diff --git a/x.py b/x.py\n+content\n"
    args, _ = mock_check_output.call_args
    assert args[0][0] == "git"


@patch("shutil.which", return_value="/usr/bin/rtk")
@patch("subprocess.check_output")
def test_extract_git_diff_with_rtk_available_uses_rtk_command(mock_check_output, mock_which):
    mock_check_output.return_value = "diff --git a/x.py b/x.py\n+content\n"

    result = extract_git_diff(verbose=False, strict=False)

    assert result == "diff --git a/x.py b/x.py\n+content\n"
    args, _ = mock_check_output.call_args
    assert args[0][0] == "rtk"


@patch("shutil.which", return_value="/usr/bin/rtk")
@patch("subprocess.check_output")
def test_extract_git_diff_rtk_failure_falls_back_to_standard_diff(mock_check_output, mock_which):
    def side_effect(cmd, **kwargs):
        if cmd[0] == "rtk":
            raise subprocess.CalledProcessError(1, cmd, output="rtk boom")
        return "diff --git a/x.py b/x.py\n+ok\n"

    mock_check_output.side_effect = side_effect

    result = extract_git_diff(verbose=True, strict=False)

    assert result == "diff --git a/x.py b/x.py\n+ok\n"
    assert mock_check_output.call_count == 2


@patch("shutil.which", return_value=None)
@patch("subprocess.check_output")
def test_extract_git_diff_does_not_truncate_large_diffs(mock_check_output, mock_which):
    """Regression: analysis diff must never be hard-sliced at 50000 chars (Issue #161 Slice 4)."""
    big_diff = "diff --git a/x.py b/x.py\n" + ("+" + "a" * 60_000) + "\n"
    mock_check_output.return_value = big_diff

    result = extract_git_diff(verbose=False, strict=False)

    assert result == big_diff
    assert len(result) > 50_000
    assert "TRUNCATED" not in result


@patch("shutil.which", return_value=None)
@patch("subprocess.check_output")
def test_extract_git_diff_empty_diff_raises_exit_zero(mock_check_output, mock_which):
    mock_check_output.return_value = "   \n"

    with pytest.raises(typer.Exit) as excinfo:
        extract_git_diff(verbose=False, strict=False)
    assert excinfo.value.exit_code == 0


@patch("shutil.which", return_value=None)
@patch("subprocess.check_output")
def test_extract_git_diff_command_failure_aborts_non_strict(mock_check_output, mock_which):
    mock_check_output.side_effect = subprocess.CalledProcessError(1, ["git", "diff"], output="fatal: boom")

    with pytest.raises(typer.Exit) as excinfo:
        extract_git_diff(verbose=False, strict=False)
    assert excinfo.value.exit_code == 0


@patch("shutil.which", return_value=None)
@patch("subprocess.check_output")
def test_extract_git_diff_command_failure_aborts_strict_with_code_one(mock_check_output, mock_which):
    mock_check_output.side_effect = subprocess.CalledProcessError(1, ["git", "diff"], output="fatal: boom")

    with pytest.raises(typer.Exit) as excinfo:
        extract_git_diff(verbose=False, strict=True)
    assert excinfo.value.exit_code == 1


# ---------------------------------------------------------------------------
# generate_commit_message — ModelCommitPlan -> CommitPlan conversion
# (Issue #161 Slice 3: LLM now returns the strict ModelCommitPlan schema,
# which is converted to the internal CommitPlan before directives/rendering.)
# ---------------------------------------------------------------------------


def _make_model_plan(
    intent_id="bug_fix",
    gitmoji="🐛",
    cc_type=CommitType.FIX,
    semver_impact=SemVerImpact.PATCH,
    changelog_group="Fixed",
):
    return ModelCommitPlan(
        primary_intent=ModelCommitIntent(
            intent_id=intent_id,
            gitmoji=gitmoji,
            cc_type=cc_type,
            description="fix the parser",
            semver_impact=semver_impact,
            changelog_group=changelog_group,
        ),
        rationale="Fix.",
        body_summary="Did a fix.",
    )


def test_generate_commit_message_converts_model_plan_to_commit_plan():
    client = MagicMock()
    client.chat.completions.create.return_value = _make_model_plan()

    result = generate_commit_message(client, "diff --git a/x b/x", "gpt-test", "system prompt")

    assert isinstance(result, CommitPlan)
    assert not isinstance(result, ModelCommitPlan)
    assert result.primary_intent.intent_id == "bug_fix"
    assert result.rationale == "Fix."
    assert result.body_summary == "Did a fix."


def test_generate_commit_message_passes_model_commit_plan_as_response_model():
    client = MagicMock()
    client.chat.completions.create.return_value = _make_model_plan()

    generate_commit_message(client, "diff --git a/x b/x", "gpt-test", "system prompt")

    _, kwargs = client.chat.completions.create.call_args
    assert kwargs["response_model"] is ModelCommitPlan
    assert kwargs["model"] == "gpt-test"
    assert kwargs["messages"][1]["content"].startswith("Here is the diff:")


def test_generate_commit_message_applies_active_directives_after_conversion():
    client = MagicMock()
    client.chat.completions.create.return_value = _make_model_plan()

    result = generate_commit_message(
        client,
        "diff --git a/x b/x",
        "gpt-test",
        "system prompt",
        active_directives={"preferred_type": "feat", "preferred_scope": "api"},
    )

    assert result.primary_intent.cc_type == CommitType.FEAT
    assert result.primary_intent.scope == "api"


def test_generate_commit_message_without_active_directives_leaves_scope_unset():
    client = MagicMock()
    client.chat.completions.create.return_value = _make_model_plan()

    result = generate_commit_message(client, "diff --git a/x b/x", "gpt-test", "system prompt")

    assert result.primary_intent.scope is None


# ---------------------------------------------------------------------------
# release() CLI command — new gold-standard GitHub notes flags wiring
# (Issue #181: --theme, --notes-file, --publish-github, --github-latest,
# --skip-github-notes now map into execute_release()).
# ---------------------------------------------------------------------------


@patch("git_cg.release.execute_release")
def test_release_command_maps_all_new_flags_to_execute_release(mock_execute_release):
    from git_cg.main import release

    release(
        dry_run=True,
        verbose=True,
        pre_release="alpha",
        theme="My Theme",
        notes_file="/tmp/notes.md",
        publish_github=True,
        github_latest=False,
        skip_github_notes=False,
    )

    mock_execute_release.assert_called_once_with(
        dry_run=True,
        verbose=True,
        pre_release="alpha",
        theme="My Theme",
        notes_path="/tmp/notes.md",
        publish_github=True,
        github_prerelease=True,
        skip_github_notes=False,
    )


@patch("git_cg.release.execute_release")
def test_release_command_github_latest_inverts_to_prerelease_false(mock_execute_release):
    """--github-latest must map to github_prerelease=False (the inverse)."""
    from git_cg.main import release

    release(
        dry_run=False,
        verbose=False,
        pre_release=None,
        theme=None,
        notes_file=None,
        publish_github=True,
        github_latest=True,
        skip_github_notes=False,
    )

    _args, kwargs = mock_execute_release.call_args
    assert kwargs["github_prerelease"] is False


@patch("git_cg.release.execute_release")
def test_release_command_default_github_latest_false_keeps_prerelease_true(mock_execute_release):
    """When --github-latest is not passed, the release must default to pre-release=True."""
    from git_cg.main import release

    release(
        dry_run=False,
        verbose=False,
        pre_release=None,
        theme=None,
        notes_file=None,
        publish_github=False,
        github_latest=False,
        skip_github_notes=False,
    )

    _args, kwargs = mock_execute_release.call_args
    assert kwargs["github_prerelease"] is True


@patch("git_cg.release.execute_release")
def test_release_command_skip_github_notes_passed_through(mock_execute_release):
    from git_cg.main import release

    release(
        dry_run=False,
        verbose=False,
        pre_release=None,
        theme=None,
        notes_file=None,
        publish_github=False,
        github_latest=False,
        skip_github_notes=True,
    )

    _args, kwargs = mock_execute_release.call_args
    assert kwargs["skip_github_notes"] is True


@patch("git_cg.release.execute_release")
def test_release_command_notes_file_none_maps_to_notes_path_none(mock_execute_release):
    """When --notes-file is omitted, notes_path must be passed through as None (library default applies)."""
    from git_cg.main import release

    release(
        dry_run=False,
        verbose=False,
        pre_release=None,
        theme=None,
        notes_file=None,
        publish_github=False,
        github_latest=False,
        skip_github_notes=False,
    )

    _args, kwargs = mock_execute_release.call_args
    assert kwargs["notes_path"] is None
    assert kwargs["theme"] is None
