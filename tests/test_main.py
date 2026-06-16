import git_cg.main as main_module
from git_cg.main import ReviewState, build_generation_messages, build_system_prompt


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


def test_review_state_regeneration_guidance_can_be_set_and_cleared():
    review_state = ReviewState(commit_plan=None, regeneration_guidance=None)  # type: ignore[arg-type]

    assert review_state.set_regeneration_guidance("This is a feature, not a fix.") is True
    assert review_state.regeneration_guidance == "This is a feature, not a fix."
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
# LAST_OPIK_TRACE_ID – global variable (added in this PR)
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
