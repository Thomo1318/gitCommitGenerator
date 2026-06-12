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


def test_build_generation_messages_includes_regeneration_guidance_when_present():
    test_diff = """diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1 +1 @@
-old
+new
"""
    prompt = build_system_prompt(test_diff)
    messages = build_generation_messages(prompt, test_diff, regeneration_guidance="This is a feature, not a fix.")

    assert len(messages) == 3
    assert messages[2]["role"] == "user"
    assert "Regeneration guidance for this retry only:" in messages[2]["content"]
    assert "This is a feature, not a fix." in messages[2]["content"]


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
    assert all("Regeneration guidance for this retry only:" not in message["content"] for message in messages)


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
    assert "If regeneration guidance is provided separately in a later user message" in prompt
