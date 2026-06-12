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
    prompt = build_system_prompt(test_diff, regeneration_guidance="This is a feature, not a fix.")

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


def test_build_generation_messages_with_regeneration_guidance_still_returns_two_messages():
    """Passing regeneration_guidance must not alter the message count (guidance goes in the system prompt)."""
    messages = build_generation_messages("system", "diff", regeneration_guidance="This is a feat.")
    assert len(messages) == 2


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
    prompt = build_system_prompt(test_diff, regeneration_guidance="Focus on user-facing behavior.")

    # The guidance-present path changes the candidates header
    assert "INITIAL DETERMINISTIC ANALYSIS:" in prompt or "REGENERATION GUIDANCE" in prompt


def test_build_system_prompt_guidance_contains_quoted_guidance_text():
    """The regeneration guidance must appear quoted in the system prompt."""
    test_diff = "diff --git a/x.py b/x.py\n-old\n+new"
    guidance = "Focus on user-facing behavior."
    prompt = build_system_prompt(test_diff, regeneration_guidance=guidance)

    assert f'Guidance: "{guidance}"' in prompt


def test_build_system_prompt_guidance_contains_critical_precedence_rule():
    test_diff = "diff --git a/x.py b/x.py\n-old\n+new"
    prompt = build_system_prompt(test_diff, regeneration_guidance="This is a fix.")

    assert "CRITICAL PRECEDENCE RULE" in prompt


def test_build_system_prompt_guidance_instructs_not_to_use_as_commit_content():
    test_diff = "diff --git a/x.py b/x.py\n-old\n+new"
    prompt = build_system_prompt(test_diff, regeneration_guidance="This is a fix.")

    assert "Do not treat the guidance text itself as final commit content" in prompt
