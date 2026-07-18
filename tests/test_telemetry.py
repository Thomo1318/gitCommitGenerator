"""
Tests for git_cg.telemetry covering the PR changes:
- GenerationTelemetry.trace_id is now str | None (was str)
- GenerationTelemetry gained a new thread_id: str | None = None field
- read_telemetry_state() applies backward-compatibility defaults for
  missing trace_id and thread_id keys in legacy JSON payloads.
"""

import json

from git_cg.telemetry import GenerationTelemetry, get_state_file_path, read_telemetry_state, write_telemetry_state

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_telemetry(**overrides) -> GenerationTelemetry:
    """
    Create a minimal `GenerationTelemetry` instance for tests.

    Parameters:
        overrides: Keyword values that replace the default telemetry fields.

    Returns:
        GenerationTelemetry: A telemetry object with the required fields populated.
    """
    defaults = dict(
        trace_id=None,
        diff_hash="abc123",
        diff_output="diff --git a/x.py b/x.py\n+new",
        repo_name="my-repo",
        engine="mtplx",
        model_name="gemma-3-4b",
        system_prompt_hash="deadbeef",
        generated_message="feat: add feature",
        commit_plan_json={"primary_intent": {}},
        score_card={"header_length_ok": True},
    )
    defaults.update(overrides)
    return GenerationTelemetry(**defaults)


# ---------------------------------------------------------------------------
# GenerationTelemetry dataclass - field typing
# ---------------------------------------------------------------------------


def test_generation_telemetry_trace_id_accepts_none():
    """trace_id must accept None (changed from str to str | None in this PR)."""
    tel = _minimal_telemetry(trace_id=None)
    assert tel.trace_id is None


def test_generation_telemetry_trace_id_accepts_string():
    """trace_id must still accept a string value."""
    tel = _minimal_telemetry(trace_id="01924abc-dead-beef-cafe-000000000001")
    assert tel.trace_id == "01924abc-dead-beef-cafe-000000000001"


def test_generation_telemetry_thread_id_defaults_to_none():
    """thread_id is a newly added field that defaults to None."""
    tel = _minimal_telemetry()
    assert tel.thread_id is None


def test_generation_telemetry_thread_id_accepts_string():
    """thread_id must accept a string value such as a repo-scoped key."""
    tel = _minimal_telemetry(thread_id="repo-my-project")
    assert tel.thread_id == "repo-my-project"


def test_generation_telemetry_thread_id_accepts_none_explicitly():
    """Explicitly passing thread_id=None must not raise."""
    tel = _minimal_telemetry(thread_id=None)
    assert tel.thread_id is None


def test_generation_telemetry_both_ids_can_be_set():
    """Both trace_id and thread_id can hold string values simultaneously."""
    tel = _minimal_telemetry(
        trace_id="trace-001",
        thread_id="repo-awesome",
    )
    assert tel.trace_id == "trace-001"
    assert tel.thread_id == "repo-awesome"


# ---------------------------------------------------------------------------
# write_telemetry_state / read_telemetry_state - round-trip (v2 format)
# ---------------------------------------------------------------------------


def test_write_then_read_preserves_trace_id(tmp_path):
    """write + read must round-trip a non-None trace_id."""
    tel = _minimal_telemetry(trace_id="trace-xyz-789")
    write_telemetry_state(str(tmp_path), tel)
    result = read_telemetry_state(str(tmp_path))

    assert result is not None
    assert result.trace_id == "trace-xyz-789"


def test_write_then_read_preserves_thread_id(tmp_path):
    """write + read must round-trip a non-None thread_id."""
    tel = _minimal_telemetry(thread_id="repo-my-repo")
    write_telemetry_state(str(tmp_path), tel)
    result = read_telemetry_state(str(tmp_path))

    assert result is not None
    assert result.thread_id == "repo-my-repo"


def test_write_then_read_preserves_null_trace_id(tmp_path):
    """write + read must round-trip trace_id=None without corruption."""
    tel = _minimal_telemetry(trace_id=None)
    write_telemetry_state(str(tmp_path), tel)
    result = read_telemetry_state(str(tmp_path))

    assert result is not None
    assert result.trace_id is None


def test_write_then_read_preserves_null_thread_id(tmp_path):
    """write + read must round-trip thread_id=None without corruption."""
    tel = _minimal_telemetry(thread_id=None)
    write_telemetry_state(str(tmp_path), tel)
    result = read_telemetry_state(str(tmp_path))

    assert result is not None
    assert result.thread_id is None


def test_write_serializes_thread_id_to_json(tmp_path):
    """The state file written by write_telemetry_state must contain thread_id as a JSON key."""
    tel = _minimal_telemetry(thread_id="repo-serialized")
    write_telemetry_state(str(tmp_path), tel)

    state_file = get_state_file_path(str(tmp_path))
    raw = json.loads(state_file.read_text())
    assert "thread_id" in raw
    assert raw["thread_id"] == "repo-serialized"


def test_write_serializes_trace_id_to_json(tmp_path):
    """The state file must contain trace_id as a JSON key."""
    tel = _minimal_telemetry(trace_id="trace-in-json")
    write_telemetry_state(str(tmp_path), tel)

    state_file = get_state_file_path(str(tmp_path))
    raw = json.loads(state_file.read_text())
    assert "trace_id" in raw
    assert raw["trace_id"] == "trace-in-json"


# ---------------------------------------------------------------------------
# read_telemetry_state - backward compatibility for legacy (v1) JSON
# ---------------------------------------------------------------------------


def _write_legacy_json(git_dir: str, payload: dict) -> None:
    """Write a raw JSON payload to the state file path, bypassing write_telemetry_state."""
    state_file = get_state_file_path(git_dir)
    state_file.write_text(json.dumps(payload), encoding="utf-8")


def _base_v1_payload() -> dict:
    """A minimal legacy v1 state payload that predates trace_id / thread_id fields."""
    return {
        "diff_hash": "v1hashval",
        "diff_output": "diff --git a/x.py b/x.py",
        "repo_name": "legacy-repo",
        "engine": "omlx",
        "model_name": "mistral-7b",
        "system_prompt_hash": "cafebabe",
        "generated_message": "chore: update deps",
        "commit_plan_json": {},
        "score_card": {},
    }


def test_read_legacy_json_without_trace_id_returns_none_for_trace_id(tmp_path):
    """Legacy payloads lacking 'trace_id' must deserialize with trace_id=None."""
    payload = _base_v1_payload()
    assert "trace_id" not in payload
    _write_legacy_json(str(tmp_path), payload)

    result = read_telemetry_state(str(tmp_path))

    assert result is not None
    assert result.trace_id is None


def test_read_legacy_json_without_thread_id_returns_none_for_thread_id(tmp_path):
    """Legacy payloads lacking 'thread_id' must deserialize with thread_id=None."""
    payload = _base_v1_payload()
    assert "thread_id" not in payload
    _write_legacy_json(str(tmp_path), payload)

    result = read_telemetry_state(str(tmp_path))

    assert result is not None
    assert result.thread_id is None


def test_read_legacy_json_missing_both_ids_still_succeeds(tmp_path):
    """A v1 payload missing both trace_id and thread_id must load without error."""
    payload = _base_v1_payload()
    _write_legacy_json(str(tmp_path), payload)

    result = read_telemetry_state(str(tmp_path))

    assert result is not None
    assert isinstance(result, GenerationTelemetry)


def test_read_legacy_json_preserves_existing_trace_id(tmp_path):
    """If a payload already contains 'trace_id', the existing value must be kept."""
    payload = _base_v1_payload()
    payload["trace_id"] = "pre-existing-trace"
    _write_legacy_json(str(tmp_path), payload)

    result = read_telemetry_state(str(tmp_path))

    assert result is not None
    assert result.trace_id == "pre-existing-trace"


def test_read_legacy_json_preserves_existing_thread_id(tmp_path):
    """If a payload already contains 'thread_id', the existing value must be kept."""
    payload = _base_v1_payload()
    payload["thread_id"] = "pre-existing-thread"
    _write_legacy_json(str(tmp_path), payload)

    result = read_telemetry_state(str(tmp_path))

    assert result is not None
    assert result.thread_id == "pre-existing-thread"


def test_read_legacy_json_missing_only_trace_id(tmp_path):
    """Payload with thread_id present but trace_id absent must infer trace_id=None."""
    payload = _base_v1_payload()
    payload["thread_id"] = "has-thread"
    # trace_id deliberately absent
    _write_legacy_json(str(tmp_path), payload)

    result = read_telemetry_state(str(tmp_path))

    assert result is not None
    assert result.trace_id is None
    assert result.thread_id == "has-thread"


def test_read_legacy_json_missing_only_thread_id(tmp_path):
    """Payload with trace_id present but thread_id absent must infer thread_id=None."""
    payload = _base_v1_payload()
    payload["trace_id"] = "has-trace"
    # thread_id deliberately absent
    _write_legacy_json(str(tmp_path), payload)

    result = read_telemetry_state(str(tmp_path))

    assert result is not None
    assert result.trace_id == "has-trace"
    assert result.thread_id is None


# ---------------------------------------------------------------------------
# read_telemetry_state - failure / absence cases
# ---------------------------------------------------------------------------


def test_read_returns_none_when_state_file_absent(tmp_path):
    """read_telemetry_state must return None when no state file exists."""
    result = read_telemetry_state(str(tmp_path))
    assert result is None


def test_read_returns_none_for_malformed_json(tmp_path):
    """read_telemetry_state must return None (not raise) for invalid JSON."""
    state_file = get_state_file_path(str(tmp_path))
    state_file.write_text("{this is not valid json!!!}", encoding="utf-8")

    result = read_telemetry_state(str(tmp_path))
    assert result is None


def test_read_returns_none_for_empty_file(tmp_path):
    """read_telemetry_state must return None (not raise) for an empty file."""
    state_file = get_state_file_path(str(tmp_path))
    state_file.write_text("", encoding="utf-8")

    result = read_telemetry_state(str(tmp_path))
    assert result is None


def test_read_returns_none_for_json_with_missing_required_field(tmp_path):
    """JSON that is valid but missing required fields must not crash — returns None."""
    # 'diff_hash' is a required field; omitting it means GenerationTelemetry(**data) will raise
    bad_payload = {"trace_id": "t1", "thread_id": "th1"}
    state_file = get_state_file_path(str(tmp_path))
    state_file.write_text(json.dumps(bad_payload), encoding="utf-8")

    result = read_telemetry_state(str(tmp_path))
    assert result is None


def test_redact_payload_no_payload():
    from git_cg.telemetry import redact_payload

    assert redact_payload("") == ""


def test_redact_payload_success(monkeypatch):
    import json
    import subprocess
    from dataclasses import dataclass

    from git_cg.telemetry import redact_payload

    @dataclass
    class MockProcess:
        stdout: str

    def mock_run(*args, **kwargs):
        # Simulate betterleaks output
        findings = [{"Secret": "super_secret_key"}]
        return MockProcess(stdout=json.dumps(findings))

    monkeypatch.setattr(subprocess, "run", mock_run)

    payload = "Here is my super_secret_key that should be hidden."
    result = redact_payload(payload)
    assert result == "Here is my [REDACTED] that should be hidden."


def test_redact_payload_fail_safe(monkeypatch):
    import subprocess

    from git_cg.telemetry import redact_payload

    def mock_run(*args, **kwargs):
        raise FileNotFoundError("betterleaks not found")

    monkeypatch.setattr(subprocess, "run", mock_run)

    payload = "Here is my super_secret_key that should be hidden."
    result = redact_payload(payload)
    assert result == "[REDACTION FAILED - PAYLOAD OMITTED FOR SAFETY]"


def test_redact_payload_null_output(monkeypatch):
    import subprocess
    from dataclasses import dataclass

    from git_cg.telemetry import redact_payload

    @dataclass
    class MockProcess:
        stdout: str

    def mock_run(*args, **kwargs):
        return MockProcess(stdout="null")

    monkeypatch.setattr(subprocess, "run", mock_run)
    payload = "No secrets here"
    assert redact_payload(payload) == payload


def test_scorecard_properties():
    from git_cg.telemetry import DeterministicScoreCard

    card = DeterministicScoreCard(
        header_length_ok=True,
        description_length_ok=True,
        type_valid=True,
        emoji_matrix_aligned=True,
        semver_consistent=True,
        breaking_change_complete=True,
    )
    assert card.all_pass is True
    assert card.failed_checks == []

    card.header_length_ok = False
    assert card.all_pass is False
    assert card.failed_checks == ["header_length_ok"]


def test_compute_hashes():
    from git_cg.telemetry import compute_diff_hash, compute_prompt_hash

    p_hash = compute_prompt_hash("test prompt")
    d_hash = compute_diff_hash("test diff")
    assert len(p_hash) == 16
    assert len(d_hash) == 16
    assert isinstance(p_hash, str)
    assert isinstance(d_hash, str)


def test_levenshtein_ratio():
    from git_cg.telemetry import _levenshtein_ratio

    assert _levenshtein_ratio("kitten", "kitten") == 1.0
    assert _levenshtein_ratio("kitten", "sitting") < 1.0
    assert _levenshtein_ratio("", "") == 1.0
    assert _levenshtein_ratio("a", "") == 0.0


def test_strip_trailers():
    from git_cg.telemetry import _strip_trailers

    text = "Fix bug\n\nRefs: #123\nSigned-off-by: me"
    assert _strip_trailers(text) == "Fix bug"


def test_classify_edit():
    from git_cg.telemetry import Provenance, classify_edit

    assert classify_edit("test", "test") == Provenance.AI_ACCEPTED
    assert classify_edit("test", "test\nRefs: #1") == Provenance.AI_ACCEPTED_REFS_ONLY
    assert classify_edit("test this", "test thin") == Provenance.AI_EDITED_MINOR
    assert classify_edit("hello world", "completely different") == Provenance.AI_EDITED_SUBSTANTIVE


def test_run_deterministic_checks():
    from git_cg.models import CommitIntent, CommitPlan, CommitType, SemVerImpact
    from git_cg.telemetry import run_deterministic_checks

    plan = CommitPlan(
        primary_intent=CommitIntent(
            intent_id="feat",
            gitmoji="✨",
            cc_type=CommitType.FEAT,
            scope="core",
            description="add new feature",
            semver_impact=SemVerImpact.MINOR,
            changelog_group="Features",
        ),
        rationale="test rationale",
        breaking_change=False,
        breaking_change_description="",
    )

    card = run_deterministic_checks(plan)
    assert card.all_pass is True

    # Test failure mode
    plan.primary_intent.description = "x" * 60  # > 50 chars
    plan.breaking_change = True
    plan.breaking_change_description = ""  # Missing description
    card2 = run_deterministic_checks(plan)
    assert card2.all_pass is False
    assert "description_length_ok" in card2.failed_checks
    assert "breaking_change_complete" in card2.failed_checks


def test_run_deterministic_checks_no_matrix(monkeypatch):
    import git_cg.telemetry
    from git_cg.models import CommitIntent, CommitPlan, CommitType, SemVerImpact
    from git_cg.telemetry import run_deterministic_checks

    monkeypatch.setattr(git_cg.telemetry, "get_gitmoji_matrix", lambda: None)

    plan = CommitPlan(
        primary_intent=CommitIntent(
            intent_id="unknown_intent",
            gitmoji="🐛",
            cc_type=CommitType.FIX,
            scope="core",
            description="fix bug",
            semver_impact=SemVerImpact.PATCH,
            changelog_group="Bug Fixes",
        ),
        rationale="test rationale",
        breaking_change=False,
        breaking_change_description="",
    )
    card = run_deterministic_checks(plan)
    assert card.emoji_matrix_aligned is True
    assert card.semver_consistent is True


def test_run_deterministic_checks_matrix_entry_missing(monkeypatch):
    import git_cg.telemetry
    from git_cg.models import CommitIntent, CommitPlan, CommitType, SemVerImpact
    from git_cg.telemetry import run_deterministic_checks

    # Mock matrix with a different intent so "unknown_intent" is not found
    monkeypatch.setattr(git_cg.telemetry, "get_gitmoji_matrix", lambda: [{"intent_id": "feat", "emoji": "✨"}])

    plan = CommitPlan(
        primary_intent=CommitIntent(
            intent_id="unknown_intent",
            gitmoji="🐛",
            cc_type=CommitType.FIX,
            scope="core",
            description="fix bug",
            semver_impact=SemVerImpact.PATCH,
            changelog_group="Bug Fixes",
        ),
        rationale="test rationale",
        breaking_change=False,
        breaking_change_description="",
    )
    card = run_deterministic_checks(plan)
    assert card.emoji_matrix_aligned is False
    assert card.semver_consistent is True


def test_clear_telemetry_state(tmp_path):
    from git_cg.telemetry import clear_telemetry_state, get_state_file_path

    state_file = get_state_file_path(str(tmp_path))
    state_file.write_text("{}", encoding="utf-8")
    assert state_file.exists()

    clear_telemetry_state(str(tmp_path))
    assert not state_file.exists()
