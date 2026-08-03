import re
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
        repo_slug=None,
        github_target=None,
    )

    mock_execute_release.assert_called_once_with(
        dry_run=True,
        verbose=True,
        pre_release="alpha",
        theme="My Theme",
        notes_path="/tmp/notes.md",
        publish_github=True,
        github_prerelease=True,
        repo_slug=None,
        skip_github_notes=False,
        github_target=None,
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
        repo_slug=None,
        github_target=None,
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
        repo_slug=None,
        github_target=None,
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
        repo_slug=None,
        github_target=None,
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
        repo_slug=None,
        github_target=None,
    )

    _args, kwargs = mock_execute_release.call_args
    assert kwargs["notes_path"] is None
    assert kwargs["theme"] is None


@patch("git_cg.release.execute_release")
def test_release_command_maps_repo_slug_and_github_target(mock_execute_release):
    from git_cg.main import release

    release(
        dry_run=False,
        verbose=False,
        pre_release=None,
        theme=None,
        notes_file=None,
        publish_github=True,
        github_latest=False,
        skip_github_notes=False,
        repo_slug="acme/widget",
        github_target="HEAD",
    )

    _args, kwargs = mock_execute_release.call_args
    assert kwargs["repo_slug"] == "acme/widget"
    assert kwargs["github_target"] == "HEAD"


def test_release_command_rejects_publish_with_skip_github_notes():
    import pytest
    import typer

    from git_cg.main import release

    with pytest.raises(typer.BadParameter, match="--publish-github cannot be combined"):
        release(
            dry_run=False,
            verbose=False,
            pre_release=None,
            theme=None,
            notes_file=None,
            publish_github=True,
            github_latest=False,
            skip_github_notes=True,
            repo_slug=None,
            github_target=None,
        )


# --- Issue #182 Slice 2: GOLD RUBRIC + three-channel prompt assembly ---


def _minimal_diff():
    return "diff --git a/src/git_cg/release.py b/src/git_cg/release.py\n+def new_helper():\n"


def test_gold_rubric_present_with_anchors():
    """GOLD RUBRIC is additive and carries its pinned anchors."""
    prompt = build_system_prompt(_minimal_diff())
    assert "GOLD RUBRIC (WORDING QUALITY ONLY" in prompt
    assert "Do NOT open the body with:" in prompt
    assert "This commit introduces" in prompt
    assert "MUST NOT change intent_id, gitmoji, cc_type, semver_impact, or changelog_group" in prompt


def test_gold_rubric_does_not_weaken_contract_lock():
    """The deterministic contract CRITICAL field-lock sentences remain intact (additive only)."""
    from git_cg.regeneration import ResolvedCommitContract

    contract = ResolvedCommitContract(
        primary_intent_id="feature_addition",
        gitmoji="✨",
        cc_type="feat",
        semver_impact="MINOR",
        changelog_group="Added",
        secondary_intent_ids=[],
    )
    prompt = build_system_prompt(_minimal_diff(), contract=contract)
    assert "DETERMINISTIC SEMANTIC CONTRACT (LOCKED BEFORE GENERATION)" in prompt
    assert "MUST match this contract exactly" in prompt
    # Rubric appears after the contract block (additive, never in place of it).
    assert prompt.index("DETERMINISTIC SEMANTIC CONTRACT") < prompt.index("GOLD RUBRIC")


def test_a02_gold_only_no_override_header():
    """A_02: gold-only prompt emits no REGENERATION GUIDANCE (EXPLICIT USER OVERRIDE) header."""
    prompt = build_system_prompt(_minimal_diff(), gold_guidance="Lead with the outcome.")
    assert "REGENERATION GUIDANCE (EXPLICIT USER OVERRIDE):" not in prompt
    assert "GOLD FEEDBACK (WORDING / SECONDARY COVERAGE ONLY):" in prompt


def test_a03_gold_only_no_critical_precedence_tail():
    """A_03: gold-only prompt emits no CRITICAL PRECEDENCE ranking-override sentence."""
    prompt = build_system_prompt(_minimal_diff(), gold_guidance="Lead with the outcome.")
    assert "CRITICAL PRECEDENCE RULE" not in prompt


def test_gold_guidance_never_introduces_type_scope_directives():
    """A_01-adjacent: gold guidance does not surface as preferred_type/preferred_scope."""
    prompt = build_system_prompt(_minimal_diff(), gold_guidance="make it a feat, use scope core")
    assert "DETERMINISTIC OVERRIDES (LOCKED SEMANTICS):" not in prompt
    assert "preferred_type" not in prompt
    assert "preferred_scope" not in prompt


def test_previous_plan_only_uses_neutral_header():
    """Previous-plan-only path uses neutral delta framing, not explicit user override."""
    from git_cg.models import CommitIntent, CommitPlan, CommitType, SemVerImpact

    plan = CommitPlan(
        primary_intent=CommitIntent(
            intent_id="feature_addition",
            gitmoji="✨",
            cc_type=CommitType.FEAT,
            description="add thing",
            semver_impact=SemVerImpact.MINOR,
            changelog_group="Added",
        ),
        rationale="test",
    )
    prompt = build_system_prompt(_minimal_diff(), previous_plan=plan)
    assert "PREVIOUS COMMIT PLAN (DELTA CONTEXT):" in prompt
    assert "REGENERATION GUIDANCE (EXPLICIT USER OVERRIDE):" not in prompt
    assert "CRITICAL PRECEDENCE RULE" not in prompt


def test_user_directive_path_still_emits_override_and_precedence():
    """User/directive channel retains OVERRIDE + CRITICAL PRECEDENCE (unchanged authority)."""
    prompt = build_system_prompt(_minimal_diff(), active_directives={"preferred_type": "feat"})
    assert "REGENERATION GUIDANCE (EXPLICIT USER OVERRIDE):" in prompt
    assert "CRITICAL PRECEDENCE RULE" in prompt


# --- Issue #182 Slice 3b: gold wiring integration (mocked generation path) ---


def _gold_harness_mocks(monkeypatch, plans):
    """Drive _run_commit_generation with a mocked LLM returning `plans` in sequence.

    Patches all LLM/diff/telemetry seams (no live model). Clears GIT_CG_GOLD_MODE so
    each gold test starts from a deterministic default regardless of the ambient env.

    Returns the list of written commit-message strings (`writes`).
    """
    import git_cg.main as main_mod

    monkeypatch.delenv("GIT_CG_GOLD_MODE", raising=False)
    writes: list[str] = []
    plans_iter = iter(plans)

    monkeypatch.setattr(main_mod, "_validate_commit_source", lambda *a, **k: None)
    monkeypatch.setattr(
        main_mod,
        "_collect_semantic_producer_metrics",
        lambda *a, **k: {
            "semantic_enabled": False,
            "parser_latency_ms": 0.0,
            "graph_build_latency_ms": 0.0,
            "graph_query_latency_ms": 0.0,
            "semantic_parser_metrics": None,
            "body_similarity_min": None,
            "body_similarity_avg": None,
            "fingerprint_files_compared": 0,
            "fingerprint_latency_ms": 0.0,
            "fingerprint_class_counts": None,
            "fingerprint_grammar_version": "unknown",
            "fingerprint_markers": None,
            "blast_radius_size": None,
            "affected_flows_count": None,
            "test_coverage_gap": None,
            "test_gaps_count": None,
            "graph_enrichment": None,
            "risk_assessment": None,
        },
    )
    monkeypatch.setattr(
        main_mod,
        "extract_git_diff",
        lambda **k: "diff --git a/src/git_cg/release.py b/src/git_cg/release.py\n+def helper():\n",
    )
    monkeypatch.setattr(main_mod, "pack_prompt_diff", lambda d: (d, []))
    monkeypatch.setattr(main_mod, "get_ai_client", lambda engine: object())
    monkeypatch.setattr(main_mod, "resolve_model_name", lambda client, preferred, verbose=False: "test-model")
    monkeypatch.setattr(main_mod, "_detect_branch_issue_reference", lambda verbose: [])
    monkeypatch.setattr(main_mod, "generate_commit_message", lambda *a, **k: next(plans_iter))
    monkeypatch.setattr(main_mod, "_write_commit_message", lambda f, s, strict, verbose: writes.append(s))
    monkeypatch.setattr(main_mod, "_write_telemetry_state_safe", lambda **k: None)

    monkeypatch.setattr(main_mod.opik_context, "update_current_trace", lambda *a, **k: None)
    monkeypatch.setattr(main_mod.opik_context, "get_current_trace_data", lambda: None)
    monkeypatch.setattr(main_mod.opik, "flush_tracker", lambda: None)
    monkeypatch.setattr(main_mod.sentry_sdk, "flush", lambda *a, **k: None)
    return writes


def _gold_plan(body: str | None = None):
    from git_cg.models import CommitIntent, CommitPlan, CommitType, SemVerImpact

    intent = CommitIntent.model_construct(
        intent_id="feature_addition",
        gitmoji="✨",
        cc_type=CommitType.FEAT,
        scope=None,
        description="add helper",
        semver_impact=SemVerImpact.MINOR,
        changelog_group="Added",
    )
    return CommitPlan.model_construct(
        primary_intent=intent,
        secondary_intents=[],
        split_recommended=False,
        rationale="r",
        body_summary=body,
        breaking_change=False,
        breaking_change_description=None,
    )


def test_gold_warn_mode_writes_and_does_not_block(monkeypatch, capsys, tmp_path):
    """Hook/warn default: a gold-failing body still writes; no non-zero exit."""
    writes = _gold_harness_mocks(monkeypatch, [_gold_plan(body="This commit adds a helper.")])
    import git_cg.main as main_mod

    result = main_mod._run_commit_generation(
        str(tmp_path / "COMMIT_EDITMSG"),
        None,
        None,
        engine="mtplx",
        dry_run=False,
        verbose=False,
        amend_regenerate=False,
        strict=False,
        interactive=False,
    )
    assert result is True
    assert len(writes) == 1  # message written despite gold finding
    assert "Gold lint" in capsys.readouterr().out


def test_gold_strict_mode_blocks_with_nonzero_exit(monkeypatch, capsys, tmp_path):
    """A_05: strict gold fail aborts non-zero via _abort(report=False); no write."""
    import typer

    # Both attempts fail gold (banned opener persists) so the single regen is exhausted.
    writes = _gold_harness_mocks(
        monkeypatch,
        [_gold_plan(body="This commit adds a helper."), _gold_plan(body="This commit adds a helper.")],
    )
    import git_cg.main as main_mod

    try:
        main_mod._run_commit_generation(
            str(tmp_path / "COMMIT_EDITMSG"),
            None,
            None,
            engine="mtplx",
            dry_run=False,
            verbose=False,
            amend_regenerate=False,
            strict=True,
            interactive=False,
        )
        raised = None
    except typer.Exit as e:
        raised = e
    assert raised is not None, "strict gold fail must raise typer.Exit"
    assert raised.exit_code != 0
    assert len(writes) == 0  # never write a gold-failing message in strict
    out = capsys.readouterr().out
    assert "gold lint" in out.lower() or "Gold lint" in out


def test_gold_surface_mode_prints_findings_before_review_menu(monkeypatch, capsys, tmp_path):
    """Surface mode: gold findings print before the interactive review menu.

    Close bar (#182): in surface mode the user must see gold findings *before* the
    existing interactive review menu renders — no new checklist, ordering only.
    """
    import git_cg.main as main_mod

    writes = _gold_harness_mocks(monkeypatch, [_gold_plan(body="This commit adds a helper.")])
    monkeypatch.setenv("GIT_CG_GOLD_MODE", "surface")
    monkeypatch.setattr(main_mod, "can_open_tty", lambda: True)
    monkeypatch.setattr(main_mod, "_interactive_review", lambda *a, **k: console_print_menu_marker() or "Accept")

    from git_cg.main import console

    def console_print_menu_marker():
        console.print("REVIEW-MENU-MARKER")
        return None

    result = main_mod._run_commit_generation(
        str(tmp_path / "COMMIT_EDITMSG"),
        None,
        None,
        engine="mtplx",
        dry_run=False,
        verbose=False,
        amend_regenerate=False,
        strict=False,
        interactive=True,
    )
    assert result is True
    assert len(writes) == 1
    out = capsys.readouterr().out
    gold_pos = out.find("Gold lint (surface)")
    menu_pos = out.find("REVIEW-MENU-MARKER")
    assert gold_pos != -1, "gold findings must print in surface mode"
    assert menu_pos != -1, "interactive review menu must render in surface mode"
    assert gold_pos < menu_pos, "gold findings must print before the interactive review menu"


def test_gold_surface_checklist_displayed_in_review_status(monkeypatch, capsys, tmp_path):
    """Optional -i checklist: surface mode shows gold findings as a checklist in the review status_text.

    Nice-to-have (#182): the interactive review menu surfaces gold findings as a
    "[ ] CODE: message" checklist inside status_text, so the user sees them in the
    menu itself, not only in the pre-menu console print.
    """
    import git_cg.main as main_mod

    captured: dict[str, str] = {}
    _gold_harness_mocks(monkeypatch, [_gold_plan(body="This commit adds a helper.")])
    monkeypatch.setenv("GIT_CG_GOLD_MODE", "surface")
    monkeypatch.setattr(main_mod, "can_open_tty", lambda: True)

    def fake_prompt_with_gum(title, body, *, status_text=None):
        captured["status_text"] = status_text or ""
        return "Commit"

    monkeypatch.setattr(main_mod, "prompt_with_gum", fake_prompt_with_gum)

    result = main_mod._run_commit_generation(
        str(tmp_path / "COMMIT_EDITMSG"),
        None,
        None,
        engine="mtplx",
        dry_run=False,
        verbose=False,
        amend_regenerate=False,
        strict=False,
        interactive=True,
    )
    assert result is True
    status = captured["status_text"]
    assert "Gold lint checklist:" in status
    assert "[ ] GOLD_BODY_INVENTORY:" in status


def test_arbitration_abort_exits_nonzero_when_strict_false(monkeypatch, capsys, tmp_path):
    """Issue #195 / Qodo: Cancel→Abort must exit non-zero even when CLI strict=False.

    Hook mode defaults to strict=False so _abort(... strict=strict) would otherwise
    raise typer.Exit(0) and let git complete the commit after an explicit Abort.
    """
    from dataclasses import replace

    import typer

    import git_cg.main as main_mod
    from git_cg.intent import RankedIntent
    from git_cg.intent_arbitrate import ArbitrationResult
    from git_cg.ranking_confidence import RankingConfidence

    writes = _gold_harness_mocks(monkeypatch, [_gold_plan(body="Add helper after arbitration abort.")])
    monkeypatch.setattr(main_mod, "can_open_tty", lambda: True)

    real_build = main_mod._build_generation_context

    def fake_build(*args, **kwargs):
        ctx = real_build(*args, **kwargs)
        low = RankingConfidence(
            level="low",
            margin=2.0,
            top_intent_id="feature_addition",
            runner_up_intent_id="feature_refinement",
            reasons=["margin_below_low_threshold"],
        )
        ranked = [
            RankedIntent(
                intent_id="feature_addition",
                emoji="✨",
                code=":sparkles:",
                cc_type="feat",
                description="feature",
                semver_impact="MINOR",
                changelog_group="Added",
                intent_group="feature",
                score=100.0,
                priority=100,
                specificity=100,
                split_weight=100,
            ),
            RankedIntent(
                intent_id="feature_refinement",
                emoji="✨",
                code=":sparkles:",
                cc_type="feat",
                description="refine",
                semver_impact="PATCH",
                changelog_group="Changed",
                intent_group="feature",
                score=98.0,
                priority=90,
                specificity=90,
                split_weight=90,
            ),
        ]
        return replace(ctx, ranking_confidence=low, ranked_intents=ranked)

    monkeypatch.setattr(main_mod, "_build_generation_context", fake_build)
    monkeypatch.setattr(
        "git_cg.intent_arbitrate.run_intent_arbitration",
        lambda **kwargs: ArbitrationResult(
            action="aborted",
            locked_intent_id=None,
            guidance=None,
            re_rank_requested=False,
            choice_path="cancel_abort",
            override=False,
            aborted=True,
        ),
    )

    telemetry: dict = {}

    def capture_telemetry(**kwargs):
        telemetry.update(kwargs)

    monkeypatch.setattr(main_mod, "_write_telemetry_state_safe", capture_telemetry)

    try:
        main_mod._run_commit_generation(
            str(tmp_path / "COMMIT_EDITMSG"),
            None,
            None,
            engine="mtplx",
            dry_run=False,
            verbose=False,
            amend_regenerate=False,
            strict=False,  # hook default — Abort must still fail closed
            interactive=True,
            rank_arbitrate=True,
        )
        raised = None
    except typer.Exit as e:
        raised = e

    assert raised is not None, "arbitration Abort must raise typer.Exit"
    assert raised.exit_code == 1
    assert len(writes) == 0
    assert telemetry.get("ranking_choice_path") == "cancel_abort"
    out = capsys.readouterr().out
    assert "aborted during intent arbitration" in out.lower()


def test_gold_blocked_telemetry_uses_strict_fail_codes(monkeypatch, tmp_path):
    """gold_blocked must track commit_gold via gold_report.ok_for_mode("strict").

    Integration regression for Qodo observability drift: final telemetry must not
    hardcode a local finding-code subset. Strict failure membership stays
    single-sourced in ``STRICT_FAIL_CODES`` inside ``GoldReport.ok_for_mode``.
    """
    import inspect

    import typer

    import git_cg.main as main_mod
    from git_cg.commit_gold import STRICT_FAIL_CODES, GoldFinding, GoldReport

    # Source contract: final gold_blocked uses gold_report.ok_for_mode("strict").
    src = inspect.getsource(main_mod._run_commit_generation)
    parts = src.split("gold_blocked=bool(")
    assert len(parts) >= 2
    blocked_expr = parts[-1].split("),", 1)[0]
    assert "gold_report" in blocked_expr
    assert 'ok_for_mode("strict")' in blocked_expr or "ok_for_mode('strict')" in blocked_expr
    for legacy_code in (
        "GOLD_BODY_INVENTORY",
        "GOLD_INCLUDED_CHANGES_MISSING",
        "GOLD_GROUP_PRIMARY_MISMATCH",
        "GOLD_TYPE_GROUP_INCOHERENT",
    ):
        assert legacy_code not in blocked_expr
    assert "STRICT_FAIL_CODES" in inspect.getsource(GoldReport.ok_for_mode)

    for code in (
        "GOLD_SEMVER_MATRIX_MISMATCH",
        "GOLD_SCOPE_FILENAME",
        "GOLD_SUBJECT_TITLE_CASE",
    ):
        assert code in STRICT_FAIL_CODES

    # Behavioral: expanded strict-fail codes from gold_report block generation.
    _gold_harness_mocks(monkeypatch, [_gold_plan(body="Add helper for gold_blocked telemetry.")])
    telemetry: dict = {}

    def capture_telemetry(**kwargs):
        telemetry.update(kwargs)

    monkeypatch.setattr(main_mod, "_write_telemetry_state_safe", capture_telemetry)
    monkeypatch.setattr(
        "git_cg.commit_gold.check_commit_gold",
        lambda *a, **k: GoldReport(
            findings=[
                GoldFinding(code="GOLD_SEMVER_MATRIX_MISMATCH", message="semver drift"),
                GoldFinding(code="GOLD_SCOPE_FILENAME", message="scope is filename"),
                GoldFinding(code="GOLD_SUBJECT_TITLE_CASE", message="title case"),
            ]
        ),
    )

    raised: typer.Exit | None = None
    try:
        main_mod._run_commit_generation(
            str(tmp_path / "COMMIT_EDITMSG"),
            None,
            None,
            engine="mtplx",
            dry_run=False,
            verbose=False,
            amend_regenerate=False,
            strict=True,  # gold_mode=strict
            interactive=False,
        )
    except typer.Exit as e:
        raised = e

    assert raised is not None, "strict gold failures must abort generation"
    assert raised.exit_code == 1
    # ok_for_mode("strict") is False for these codes (single-sourced STRICT_FAIL_CODES).
    assert not GoldReport(
        findings=[
            GoldFinding(code="GOLD_SEMVER_MATRIX_MISMATCH", message="semver drift"),
            GoldFinding(code="GOLD_SCOPE_FILENAME", message="scope is filename"),
            GoldFinding(code="GOLD_SUBJECT_TITLE_CASE", message="title case"),
        ]
    ).ok_for_mode("strict")


def test_medium_ranking_confidence_status_in_post_gold_review(monkeypatch, tmp_path):
    """Issue #195 nice-to-have: Medium confidence appears on post-gold review status_text."""
    import git_cg.main as main_mod
    from git_cg.intent import RankedIntent
    from git_cg.ranking_confidence import RankingConfidence

    captured: dict[str, str] = {}
    _gold_harness_mocks(monkeypatch, [_gold_plan(body="Add helper for ranking confidence status.")])
    monkeypatch.setattr(main_mod, "can_open_tty", lambda: True)

    def fake_prompt_with_gum(title, body, *, status_text=None):
        captured["status_text"] = status_text or ""
        return "Commit"

    monkeypatch.setattr(main_mod, "prompt_with_gum", fake_prompt_with_gum)

    # Force a Medium confidence snapshot through GenerationContext construction.
    real_build = main_mod._build_generation_context

    def fake_build(*args, **kwargs):
        from dataclasses import replace

        ctx = real_build(*args, **kwargs)
        medium = RankingConfidence(
            level="medium",
            margin=12.0,
            top_intent_id="feature_addition",
            runner_up_intent_id="feature_refinement",
            reasons=[],
        )
        # Preserve ranked list shape if empty so contract still works.
        ranked = (
            list(ctx.ranked_intents)
            if ctx.ranked_intents
            else [
                RankedIntent(
                    intent_id="feature_addition",
                    emoji="✨",
                    code=":sparkles:",
                    cc_type="feat",
                    description="feature",
                    semver_impact="MINOR",
                    changelog_group="Added",
                    intent_group="feature",
                    score=100.0,
                    priority=100,
                    specificity=100,
                    split_weight=100,
                ),
                RankedIntent(
                    intent_id="feature_refinement",
                    emoji="✨",
                    code=":sparkles:",
                    cc_type="feat",
                    description="refine",
                    semver_impact="PATCH",
                    changelog_group="Changed",
                    intent_group="feature",
                    score=88.0,
                    priority=90,
                    specificity=90,
                    split_weight=90,
                ),
            ]
        )
        return replace(ctx, ranking_confidence=medium, ranked_intents=ranked)

    monkeypatch.setattr(main_mod, "_build_generation_context", fake_build)

    result = main_mod._run_commit_generation(
        str(tmp_path / "COMMIT_EDITMSG"),
        None,
        None,
        engine="mtplx",
        dry_run=False,
        verbose=False,
        amend_regenerate=False,
        strict=False,
        interactive=True,
    )
    assert result is True
    status = captured["status_text"]
    assert "Ranking confidence: medium" in status
    assert "margin=12.0" in status
    assert "top=feature_addition vs feature_refinement" in status


def test_gold_strict_flag_blocks_without_general_strict(monkeypatch, capsys, tmp_path):
    """--gold-strict: gold fails strict (non-zero exit) while strict=False for non-gold paths."""
    import typer

    writes = _gold_harness_mocks(
        monkeypatch,
        [_gold_plan(body="This commit adds a helper."), _gold_plan(body="This commit adds a helper.")],
    )
    import git_cg.main as main_mod

    try:
        main_mod._run_commit_generation(
            str(tmp_path / "COMMIT_EDITMSG"),
            None,
            None,
            engine="mtplx",
            dry_run=False,
            verbose=False,
            amend_regenerate=False,
            strict=False,  # general strictness OFF
            interactive=False,
            gold_strict=True,  # gold strictness ON
        )
        raised = None
    except typer.Exit as e:
        raised = e
    assert raised is not None, "--gold-strict gold fail must raise typer.Exit"
    assert raised.exit_code != 0
    assert len(writes) == 0
    out = capsys.readouterr().out
    assert "gold lint" in out.lower() or "Gold lint" in out


def test_gold_strict_regen_recovers_and_writes(monkeypatch, capsys, tmp_path):
    """Strict: first plan fails gold, regen (clean body) passes, message writes."""
    writes = _gold_harness_mocks(
        monkeypatch,
        [_gold_plan(body="This commit adds a helper."), _gold_plan(body=None)],
    )
    import git_cg.main as main_mod

    result = main_mod._run_commit_generation(
        str(tmp_path / "COMMIT_EDITMSG"),
        None,
        None,
        engine="mtplx",
        dry_run=False,
        verbose=False,
        amend_regenerate=False,
        strict=True,
        interactive=False,
    )
    assert result is True
    assert len(writes) == 1


def test_gold_dry_run_runs_but_does_not_write(monkeypatch, capsys, tmp_path):
    """--dry-run: gold runs on the generation path; no commit-msg write occurs."""
    writes = _gold_harness_mocks(monkeypatch, [_gold_plan(body=None)])
    import git_cg.main as main_mod

    result = main_mod._run_commit_generation(
        str(tmp_path / "COMMIT_EDITMSG"),
        None,
        None,
        engine="mtplx",
        dry_run=True,
        verbose=False,
        amend_regenerate=False,
        strict=True,
        interactive=False,
    )
    assert result is True
    assert len(writes) == 0  # dry-run never writes


def test_gold_off_mode_suppresses_findings(monkeypatch, capsys, tmp_path):
    """GIT_CG_GOLD_MODE=off: findings suppressed; generation proceeds silently."""
    writes = _gold_harness_mocks(monkeypatch, [_gold_plan(body="This commit adds a helper.")])
    # Harness clears GIT_CG_GOLD_MODE for determinism; apply the off-mode override after.
    monkeypatch.setenv("GIT_CG_GOLD_MODE", "off")
    import git_cg.main as main_mod

    result = main_mod._run_commit_generation(
        str(tmp_path / "COMMIT_EDITMSG"),
        None,
        None,
        engine="mtplx",
        dry_run=False,
        verbose=False,
        amend_regenerate=False,
        strict=False,
        interactive=False,
    )
    assert result is True
    assert len(writes) == 1
    assert "Gold lint" not in capsys.readouterr().out


def test_recover_path_skips_gold(monkeypatch, tmp_path):
    """--recover is a gold no-op (O-P0.1): no structured plan, gold never runs."""
    import git_cg.main as main_mod

    called = {"gold": False, "applied": False}

    def _no_gold(*a, **k):
        called["gold"] = True
        raise AssertionError("check_commit_gold must not run on the recover path")

    # check_commit_gold is imported inside _run_commit_generation; patch at the source.
    import git_cg.commit_gold as gold_mod

    monkeypatch.setattr(gold_mod, "check_commit_gold", _no_gold)
    monkeypatch.setattr(main_mod, "_apply_standalone_commit", lambda f, strict: called.__setitem__("applied", True))

    from git_cg.main import app

    msg_file = tmp_path / "COMMIT_EDITMSG"
    msg_file.write_text("existing message", encoding="utf-8")

    # main_callback resolves COMMIT_EDITMSG via `git rev-parse --git-dir`; force it.
    def _fake_check_output(cmd, *a, **k):
        if isinstance(cmd, (list, tuple)) and "git-dir" in cmd:
            return str(tmp_path)  # --git-dir -> COMMIT_EDITMSG dir
        if isinstance(cmd, (list, tuple)) and "--show-toplevel" in cmd:
            return str(tmp_path)
        return str(tmp_path)

    monkeypatch.setattr(main_mod.subprocess, "check_output", _fake_check_output)

    from typer.testing import CliRunner

    runner = CliRunner()
    runner.invoke(app, ["--recover"])
    # Recover applied the standalone commit and exited; gold was never consulted.
    assert called["applied"] is True
    assert called["gold"] is False


def _usage_kdl_flags(section: str) -> list[str]:
    """Parse flag long-names from usage.kdl for the root app or a named cmd.

    section:
      - "root" → top-level flags before the first nested ``cmd`` block
      - any other string → flags under ``cmd "<section>" { ... }``
    """
    from pathlib import Path

    text = Path("usage.kdl").read_text(encoding="utf-8")
    if section == "root":
        # Root flags sit at file scope before the first `cmd "..."` block.
        nested = re.search(r'^cmd\s+"', text, flags=re.M)
        body = text[: nested.start()] if nested else text
    else:
        m = re.search(
            rf'^cmd\s+"{re.escape(section)}"\s*\{{(.*?)\n\}}',
            text,
            flags=re.M | re.S,
        )
        body = m.group(1) if m else ""

    flags: list[str] = []
    for raw in re.findall(r'flag\s+"([^"]+)"', body):
        # usage.kdl may use "-i --interactive" or "--engine"
        parts = raw.split()
        long_flags = [p for p in parts if p.startswith("--")]
        if long_flags:
            flags.extend(long_flags)
        elif raw.startswith("-") and not raw.startswith("--"):
            continue
        else:
            flags.append(raw if raw.startswith("--") else f"--{raw}")
    seen: set[str] = set()
    out: list[str] = []
    for f in flags:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def test_root_help_includes_usage_kdl_flags():
    """Root `git-cg --help` must surface every root flag declared in usage.kdl.

    usage.kdl is the completion/docs source of truth for the public CLI surface.
    Typer help must not lag behind it (regression: --gold-strict was documented
    and completable but missing from main_callback / --help).
    """
    from typer.testing import CliRunner

    from git_cg.main import app

    required = _usage_kdl_flags("root")
    assert required, "usage.kdl root flags failed to parse"
    assert "--engine" in required

    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    missing = [flag for flag in required if flag not in result.output]
    assert not missing, f"root --help missing usage.kdl flags: {missing}\n{result.output}"


def test_commit_help_includes_usage_kdl_flags():
    """`git-cg commit --help` must surface every commit flag declared in usage.kdl."""
    from typer.testing import CliRunner

    from git_cg.main import app

    required = _usage_kdl_flags("commit")
    assert required, "usage.kdl commit flags failed to parse"
    assert "--engine" in required

    result = CliRunner().invoke(app, ["commit", "--help"])
    assert result.exit_code == 0, result.output
    missing = [flag for flag in required if flag not in result.output]
    assert not missing, f"commit --help missing usage.kdl flags: {missing}\n{result.output}"


def test_a01_gold_guidance_bypasses_directive_extraction():
    """A_01: gold-authored guidance never introduces preferred_type/preferred_scope.

    The gold channel feeds ``build_system_prompt(gold_guidance=...)`` directly and
    must not pass through ``ReviewState.set_regeneration_guidance`` / ``_extract_directives``;
    type/scope steers embedded in gold-like text must not surface as directives.
    """
    # Gold-authored text containing directive-shaped phrases must not become directives.
    prompt = build_system_prompt(
        _minimal_diff(),
        gold_guidance="Tighten the body. (Not a user steer: make it a feat, use scope core.)",
    )
    assert "DETERMINISTIC OVERRIDES (LOCKED SEMANTICS):" not in prompt
    assert "preferred_type" not in prompt
    assert "preferred_scope" not in prompt

    # And the gold path never calls the directive-extraction machinery.
    from git_cg.main import ReviewState

    state = ReviewState(commit_plan=_gold_plan(body=None))
    assert state.active_directives == {}  # gold does not touch ReviewState guidance


def test_previous_plan_shown_with_user_directives() -> None:
    """Finding 3: user-guided regeneration retains the prior plan as delta context.

    When user directives (or residual guidance) are active, the previous commit plan
    must still be emitted (channel 2, neutral) so the regeneration updates the plan
    rather than rewriting from scratch — while the override channel keeps its own
    authoritative framing.
    """
    from git_cg.models import CommitIntent, CommitPlan, CommitType, SemVerImpact

    plan = CommitPlan(
        primary_intent=CommitIntent(
            intent_id="feature_addition",
            gitmoji="✨",
            cc_type=CommitType.FEAT,
            description="add thing",
            semver_impact=SemVerImpact.MINOR,
            changelog_group="Added",
        ),
        rationale="test",
    )
    prompt = build_system_prompt(_minimal_diff(), previous_plan=plan, active_directives={"preferred_scope": "core"})
    # User-override channel active AND previous plan still present as neutral delta context.
    assert "REGENERATION GUIDANCE (EXPLICIT USER OVERRIDE):" in prompt
    assert "PREVIOUS COMMIT PLAN (DELTA CONTEXT):" in prompt
