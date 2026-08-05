"""
Tests for git_cg.telemetry covering the PR changes:
- GenerationTelemetry.trace_id is now str | None (was str)
- GenerationTelemetry gained a new thread_id: str | None = None field
- read_telemetry_state() applies backward-compatibility defaults for
  missing trace_id and thread_id keys in legacy JSON payloads.
"""

import json

import pytest

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
    assert redact_payload(payload) == "[REDACTION FAILED - PAYLOAD OMITTED FOR SAFETY]"


def test_redact_payload_timeout(monkeypatch):
    import subprocess

    from git_cg.telemetry import redact_payload

    def mock_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="betterleaks", timeout=5)

    monkeypatch.setattr(subprocess, "run", mock_run)
    payload = "No secrets here"
    assert redact_payload(payload) == "[REDACTION FAILED - PAYLOAD OMITTED FOR SAFETY]"


def test_redact_payload_non_zero_exit(monkeypatch):
    import subprocess

    from git_cg.telemetry import redact_payload

    def mock_run(*args, **kwargs):
        raise subprocess.CalledProcessError(returncode=1, cmd="betterleaks")

    monkeypatch.setattr(subprocess, "run", mock_run)
    payload = "No secrets here"
    assert redact_payload(payload) == "[REDACTION FAILED - PAYLOAD OMITTED FOR SAFETY]"


def test_write_telemetry_state_redact_failure(tmp_path, monkeypatch):
    import git_cg.telemetry
    from git_cg.telemetry import GenerationTelemetry, read_telemetry_state, write_telemetry_state

    def mock_redact_payload(payload):
        return "[REDACTION FAILED - PAYLOAD OMITTED FOR SAFETY]"

    monkeypatch.setattr(git_cg.telemetry, "redact_payload", mock_redact_payload)

    telemetry = GenerationTelemetry(
        trace_id="t1",
        thread_id="th1",
        diff_hash="dh1",
        diff_output="diff",
        repo_name="repo",
        engine="mlx",
        model_name="model",
        system_prompt_hash="ph1",
        generated_message="msg",
        commit_plan_json={"intent": "feat"},
        score_card={},
    )

    write_telemetry_state(str(tmp_path), telemetry)

    result = read_telemetry_state(str(tmp_path))
    assert result is not None
    assert result.commit_plan_json == {"_redaction": "failed"}
    assert result.diff_output == "[REDACTION FAILED - PAYLOAD OMITTED FOR SAFETY]"


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
    assert card.all_pass
    assert card.failed_checks == []

    card.header_length_ok = False
    assert not card.all_pass
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
    assert card.all_pass

    # Test failure mode
    plan.primary_intent.description = "x" * 60  # > 50 chars
    plan.breaking_change = True
    plan.breaking_change_description = ""  # Missing description
    card2 = run_deterministic_checks(plan)
    assert not card2.all_pass
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


# ---------------------------------------------------------------------------
# redact_payload - subprocess invocation contract
# ---------------------------------------------------------------------------


def test_redact_payload_invokes_betterleaks_with_expected_args(monkeypatch):
    """redact_payload must shell out to betterleaks with the documented CLI flags."""
    import json
    import subprocess
    from dataclasses import dataclass

    from git_cg.telemetry import redact_payload

    @dataclass
    class MockProcess:
        stdout: str

    captured = {}

    def mock_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return MockProcess(stdout=json.dumps([]))

    monkeypatch.setattr(subprocess, "run", mock_run)

    payload = "nothing secret here"
    result = redact_payload(payload)

    assert result == payload
    assert captured["cmd"] == ["betterleaks", "stdin", "-f", "json", "-r", "-", "--no-banner", "-l", "fatal"]
    assert captured["kwargs"]["input"] == payload
    assert captured["kwargs"]["text"] is True
    assert captured["kwargs"]["check"] is True
    assert captured["kwargs"]["timeout"] == 5


# ---------------------------------------------------------------------------
# redact_payload - finding-handling edge cases
# ---------------------------------------------------------------------------


def test_redact_payload_multiple_secrets(monkeypatch):
    """All secrets reported by betterleaks must be replaced, not just the first."""
    import json
    import subprocess
    from dataclasses import dataclass

    from git_cg.telemetry import redact_payload

    @dataclass
    class MockProcess:
        stdout: str

    def mock_run(*args, **kwargs):
        findings = [{"Secret": "aaa111"}, {"Secret": "bbb222"}]
        return MockProcess(stdout=json.dumps(findings))

    monkeypatch.setattr(subprocess, "run", mock_run)

    payload = "key1=aaa111 key2=bbb222"
    result = redact_payload(payload)
    assert result == "key1=[REDACTED] key2=[REDACTED]"


def test_redact_payload_finding_missing_secret_key(monkeypatch):
    """A finding without a 'Secret' key must be skipped without raising."""
    import json
    import subprocess
    from dataclasses import dataclass

    from git_cg.telemetry import redact_payload

    @dataclass
    class MockProcess:
        stdout: str

    def mock_run(*args, **kwargs):
        findings = [{"RuleID": "generic-api-key"}]
        return MockProcess(stdout=json.dumps(findings))

    monkeypatch.setattr(subprocess, "run", mock_run)

    payload = "no secret field on this finding"
    result = redact_payload(payload)
    assert result == payload


def test_redact_payload_secret_not_present_in_payload(monkeypatch):
    """A reported secret that doesn't literally appear in the payload must not alter the string."""
    import json
    import subprocess
    from dataclasses import dataclass

    from git_cg.telemetry import redact_payload

    @dataclass
    class MockProcess:
        stdout: str

    def mock_run(*args, **kwargs):
        findings = [{"Secret": "not_in_the_text"}]
        return MockProcess(stdout=json.dumps(findings))

    monkeypatch.setattr(subprocess, "run", mock_run)

    payload = "this string does not contain the flagged value"
    result = redact_payload(payload)
    assert result == payload


def test_redact_payload_empty_findings_list_returns_unmodified_payload(monkeypatch):
    """An empty findings list (no secrets detected) must return the payload untouched."""
    import json
    import subprocess
    from dataclasses import dataclass

    from git_cg.telemetry import redact_payload

    @dataclass
    class MockProcess:
        stdout: str

    def mock_run(*args, **kwargs):
        return MockProcess(stdout=json.dumps([]))

    monkeypatch.setattr(subprocess, "run", mock_run)

    payload = "perfectly clean payload"
    assert redact_payload(payload) == payload


def test_redact_payload_malformed_json_output(monkeypatch):
    """Non-JSON stdout from betterleaks must trigger the fail-safe path, not raise."""
    import subprocess
    from dataclasses import dataclass

    from git_cg.telemetry import redact_payload

    @dataclass
    class MockProcess:
        stdout: str

    def mock_run(*args, **kwargs):
        return MockProcess(stdout="this is not valid json {{{")

    monkeypatch.setattr(subprocess, "run", mock_run)

    payload = "sensitive payload"
    assert redact_payload(payload) == "[REDACTION FAILED - PAYLOAD OMITTED FOR SAFETY]"


def test_redact_payload_findings_not_a_list(monkeypatch):
    """A JSON object (dict) instead of a list from betterleaks must be treated as a failure."""
    import json
    import subprocess
    from dataclasses import dataclass

    from git_cg.telemetry import redact_payload

    @dataclass
    class MockProcess:
        stdout: str

    def mock_run(*args, **kwargs):
        return MockProcess(stdout=json.dumps({"unexpected": "shape"}))

    monkeypatch.setattr(subprocess, "run", mock_run)

    payload = "sensitive payload"
    assert redact_payload(payload) == "[REDACTION FAILED - PAYLOAD OMITTED FOR SAFETY]"


# ---------------------------------------------------------------------------
# write_telemetry_state - redaction integration (happy path)
# ---------------------------------------------------------------------------


def test_write_telemetry_state_redacts_diff_output_and_message(tmp_path, monkeypatch):
    """diff_output and generated_message must be passed through redaction before being persisted."""
    import subprocess
    from dataclasses import dataclass

    from git_cg.telemetry import GenerationTelemetry, read_telemetry_state, write_telemetry_state

    @dataclass
    class MockProcess:
        stdout: str

    def mock_run(cmd, input=None, **kwargs):
        secret = "sk-live-abcdef"
        findings = [{"Secret": secret}] if input is not None and secret in input else []
        return MockProcess(stdout=json.dumps(findings))

    monkeypatch.setattr(subprocess, "run", mock_run)

    telemetry = GenerationTelemetry(
        trace_id="t1",
        thread_id="th1",
        diff_hash="dh1",
        diff_output="diff --git a/x.py b/x.py\n+API_KEY=sk-live-abcdef",
        repo_name="repo",
        engine="mlx",
        model_name="model",
        system_prompt_hash="ph1",
        generated_message="feat: rotate sk-live-abcdef credential",
        commit_plan_json={"intent": "feat"},
        score_card={},
    )

    write_telemetry_state(str(tmp_path), telemetry)
    result = read_telemetry_state(str(tmp_path))
    assert result is not None

    assert "sk-live-abcdef" not in result.diff_output
    assert "[REDACTED]" in result.diff_output
    assert "sk-live-abcdef" not in result.generated_message
    assert "[REDACTED]" in result.generated_message


def test_write_telemetry_state_redacts_secrets_inside_commit_plan_json(tmp_path, monkeypatch):
    """Secrets embedded inside commit_plan_json must be redacted via the serialize/redact/deserialize path."""
    import subprocess
    from dataclasses import dataclass

    from git_cg.telemetry import GenerationTelemetry, read_telemetry_state, write_telemetry_state

    @dataclass
    class MockProcess:
        stdout: str

    def mock_run(cmd, input=None, **kwargs):
        secret = "ghp_supersecrettoken"
        findings = [{"Secret": secret}] if input is not None and secret in input else []
        return MockProcess(stdout=json.dumps(findings))

    monkeypatch.setattr(subprocess, "run", mock_run)

    telemetry = GenerationTelemetry(
        trace_id="t1",
        thread_id="th1",
        diff_hash="dh1",
        diff_output="diff --git a/x.py b/x.py",
        repo_name="repo",
        engine="mlx",
        model_name="model",
        system_prompt_hash="ph1",
        generated_message="chore: cleanup",
        commit_plan_json={"rationale": "found ghp_supersecrettoken in config"},
        score_card={},
    )

    write_telemetry_state(str(tmp_path), telemetry)
    result = read_telemetry_state(str(tmp_path))
    assert result is not None

    assert result.commit_plan_json == {"rationale": "found [REDACTED] in config"}


def test_write_telemetry_state_calls_redact_payload_for_each_field(tmp_path, monkeypatch):
    """write_telemetry_state must route diff_output, generated_message, and the serialized
    commit_plan_json through redact_payload exactly once each."""
    import git_cg.telemetry
    from git_cg.telemetry import GenerationTelemetry, write_telemetry_state

    seen_payloads = []

    def fake_redact_payload(payload):
        seen_payloads.append(payload)
        return payload

    monkeypatch.setattr(git_cg.telemetry, "redact_payload", fake_redact_payload)

    telemetry = GenerationTelemetry(
        trace_id="t1",
        thread_id="th1",
        diff_hash="dh1",
        diff_output="the-diff-output",
        repo_name="repo",
        engine="mlx",
        model_name="model",
        system_prompt_hash="ph1",
        generated_message="the-generated-message",
        commit_plan_json={"intent": "feat"},
        score_card={},
    )

    write_telemetry_state(str(tmp_path), telemetry)

    assert seen_payloads[0] == "the-diff-output"
    assert seen_payloads[1] == "the-generated-message"
    assert seen_payloads[2] == json.dumps({"intent": "feat"})
    assert len(seen_payloads) == 3


def test_generation_telemetry_graph_schema_version_defaults_to_unknown():
    """graph_schema_version is a newly added field that defaults to unknown."""
    from git_cg.telemetry import GenerationTelemetry

    tel = GenerationTelemetry(
        trace_id="t1",
        thread_id="th1",
        diff_hash="dh1",
        diff_output="diff",
        repo_name="repo",
        engine="mlx",
        model_name="model",
        system_prompt_hash="ph1",
        generated_message="msg",
        commit_plan_json={"intent": "feat"},
        score_card={},
    )
    assert tel.graph_schema_version == "unknown"


def test_generation_telemetry_graph_schema_version_accepts_string():
    """graph_schema_version must accept a string value."""
    from git_cg.telemetry import GenerationTelemetry

    tel = GenerationTelemetry(
        trace_id="t1",
        thread_id="th1",
        diff_hash="dh1",
        diff_output="diff",
        repo_name="repo",
        engine="mlx",
        model_name="model",
        system_prompt_hash="ph1",
        generated_message="msg",
        commit_plan_json={"intent": "feat"},
        score_card={},
        graph_schema_version="1.2.0",
    )
    assert tel.graph_schema_version == "1.2.0"


def test_reverse_parse_commit_message_full_structure():
    from git_cg.telemetry import reverse_parse_commit_message

    text = (
        "✨ feat(core)!: implement new telemetry pipeline\n"
        "\n"
        "This completely replaces the old telemetry system with a new\n"
        "structured approach.\n"
        "\n"
        "Included changes:\n"
        "- 🐛 fix(telemetry): resolve missing metadata in traces\n"
        "- ♻️ refactor: simplify opik context injection\n"
        "\n"
        "BREAKING CHANGE: The `record_telemetry` signature has changed.\n"
        "\n"
        "Refs: #123\n"
        "SemVer-Impact: MAJOR\n"
        "Changelog-Groups: core"
    )

    plan = reverse_parse_commit_message(text)

    assert plan["primary_intent"]["gitmoji"] == "✨"
    assert plan["primary_intent"]["cc_type"] == "feat"
    assert plan["primary_intent"]["scope"] == "core"
    assert plan["primary_intent"]["description"] == "implement new telemetry pipeline"
    assert plan["primary_intent"]["semver_impact"] == "MAJOR"
    assert plan["primary_intent"]["intent_id"] != "unknown"
    assert plan["primary_intent"]["intent_id"]  # resolved from matrix via emoji/type
    # Rendered trailers are authoritative for the final message; matrix fills only
    # when Changelog-Groups is absent. intent_id still comes from emoji/type lookup.
    assert plan["primary_intent"]["changelog_group"] == "core"

    assert plan["breaking_change"] is True
    assert plan["breaking_change_description"] == "The `record_telemetry` signature has changed."

    assert len(plan["secondary_intents"]) == 2
    assert plan["secondary_intents"][0]["cc_type"] == "fix"
    assert plan["secondary_intents"][0]["scope"] == "telemetry"
    assert plan["secondary_intents"][0]["gitmoji"] == "🐛"
    assert plan["secondary_intents"][0]["intent_id"] != "unknown"
    assert plan["secondary_intents"][1]["cc_type"] == "refactor"
    assert plan["secondary_intents"][1]["intent_id"] != "unknown"

    # Body reconstruction uses real newlines and excludes trailer metadata.
    assert plan["body_summary"] == (
        "This completely replaces the old telemetry system with a new\nstructured approach."
    )
    assert "Refs:" not in plan["body_summary"]
    assert "SemVer-Impact" not in plan["body_summary"]
    assert "\\n" not in plan["body_summary"]
    assert plan["split_recommended"] is False
    assert plan["rationale"] == ""
    assert plan["_partial"] is True


def test_reverse_parse_commit_message_simple():
    from git_cg.telemetry import reverse_parse_commit_message

    text = "fix: typos in docs\n\nFixed some typos."
    plan = reverse_parse_commit_message(text)

    assert plan["primary_intent"]["gitmoji"] == ""
    assert plan["primary_intent"]["cc_type"] == "fix"
    assert plan["primary_intent"]["scope"] is None
    assert plan["primary_intent"]["description"] == "typos in docs"
    # No emoji: still resolve a matrix intent via cc_type when possible.
    assert plan["primary_intent"]["intent_id"] != "unknown"
    assert plan["breaking_change"] is False
    assert len(plan["secondary_intents"]) == 0
    assert plan["body_summary"] == "Fixed some typos."
    assert plan["split_recommended"] is False
    assert plan["rationale"] == ""
    assert plan["_partial"] is True


# ---------------------------------------------------------------------------
# _resolve_intent_fields_from_matrix (private helper backing reverse-parsing)
#
# This function does a fresh ``from git_cg.sop import get_gitmoji_matrix``
# on every call, so it must be mocked via ``git_cg.sop.get_gitmoji_matrix``
# rather than the ``git_cg.telemetry`` module attribute.
# ---------------------------------------------------------------------------

_RESOLVE_MATRIX_FIXTURE = [
    {
        "intent_id": "feature_addition",
        "emoji": "✨",
        "cc_type": "feat",
        "semver_impact": "MINOR",
        "changelog_group": "Added",
    },
    {"intent_id": "bug_fix", "emoji": "🐛", "cc_type": "fix", "semver_impact": "PATCH", "changelog_group": "Fixed"},
    {
        "intent_id": "docs_only",
        "emoji": "📝",
        "cc_type": "docs",
        "semver_impact": "NONE",
        "changelog_group": "Documentation",
    },
    {"code": ":question:", "emoji": "❓", "cc_type": "chore", "semver_impact": "NONE", "changelog_group": "Misc"},
]


def test_resolve_intent_fields_from_matrix_exact_emoji_and_cc_type_match(monkeypatch):
    from git_cg.telemetry import _resolve_intent_fields_from_matrix

    monkeypatch.setattr("git_cg.sop.get_gitmoji_matrix", lambda: _RESOLVE_MATRIX_FIXTURE)

    result = _resolve_intent_fields_from_matrix(gitmoji="🐛", cc_type="fix")

    assert result == {"intent_id": "bug_fix", "semver_impact": "PATCH", "changelog_group": "Fixed"}


def test_resolve_intent_fields_from_matrix_emoji_wins_over_mismatched_cc_type(monkeypatch):
    """When emoji matches but the given cc_type has no row for that emoji, emoji match still wins."""
    from git_cg.telemetry import _resolve_intent_fields_from_matrix

    monkeypatch.setattr("git_cg.sop.get_gitmoji_matrix", lambda: _RESOLVE_MATRIX_FIXTURE)

    result = _resolve_intent_fields_from_matrix(gitmoji="🐛", cc_type="refactor")

    assert result["intent_id"] == "bug_fix"
    assert result["changelog_group"] == "Fixed"


def test_resolve_intent_fields_from_matrix_cc_type_only_when_no_emoji(monkeypatch):
    from git_cg.telemetry import _resolve_intent_fields_from_matrix

    monkeypatch.setattr("git_cg.sop.get_gitmoji_matrix", lambda: _RESOLVE_MATRIX_FIXTURE)

    result = _resolve_intent_fields_from_matrix(gitmoji="", cc_type="docs")

    assert result == {"intent_id": "docs_only", "semver_impact": "NONE", "changelog_group": "Documentation"}


def test_resolve_intent_fields_from_matrix_no_match_falls_back_to_provided_values(monkeypatch):
    from git_cg.telemetry import _resolve_intent_fields_from_matrix

    monkeypatch.setattr("git_cg.sop.get_gitmoji_matrix", lambda: _RESOLVE_MATRIX_FIXTURE)

    result = _resolve_intent_fields_from_matrix(
        gitmoji="🚀", cc_type="release", semver_impact="MAJOR", changelog_group="Released"
    )

    assert result == {"intent_id": "unknown", "semver_impact": "MAJOR", "changelog_group": "Released"}


def test_resolve_intent_fields_from_matrix_no_match_defaults_when_no_fallback_values(monkeypatch):
    from git_cg.telemetry import _resolve_intent_fields_from_matrix

    monkeypatch.setattr("git_cg.sop.get_gitmoji_matrix", lambda: _RESOLVE_MATRIX_FIXTURE)

    result = _resolve_intent_fields_from_matrix(gitmoji="🚀", cc_type="release")

    assert result == {"intent_id": "unknown", "semver_impact": "NONE", "changelog_group": "Miscellaneous"}


def test_resolve_intent_fields_from_matrix_row_without_intent_id_uses_code_fallback(monkeypatch):
    """Rows with no intent_id must derive one from `code`, stripped of leading/trailing colons."""
    from git_cg.telemetry import _resolve_intent_fields_from_matrix

    monkeypatch.setattr("git_cg.sop.get_gitmoji_matrix", lambda: _RESOLVE_MATRIX_FIXTURE)

    result = _resolve_intent_fields_from_matrix(gitmoji="❓", cc_type="chore")

    assert result["intent_id"] == "question"


def test_resolve_intent_fields_from_matrix_empty_matrix_returns_unknown(monkeypatch):
    from git_cg.telemetry import _resolve_intent_fields_from_matrix

    monkeypatch.setattr("git_cg.sop.get_gitmoji_matrix", lambda: [])

    result = _resolve_intent_fields_from_matrix(gitmoji="🐛", cc_type="fix")

    assert result == {"intent_id": "unknown", "semver_impact": "NONE", "changelog_group": "Miscellaneous"}


def test_generation_telemetry_phase1_fields_default():
    """Phase 1 semantic metrics default to disabled/zero when omitted."""
    from git_cg.telemetry import GenerationTelemetry

    tel = GenerationTelemetry(
        trace_id="t1",
        thread_id="th1",
        diff_hash="dh1",
        diff_output="diff",
        repo_name="repo",
        engine="mlx",
        model_name="model",
        system_prompt_hash="ph1",
        generated_message="msg",
        commit_plan_json={"intent": "feat"},
        score_card={},
    )
    assert tel.semantic_enabled is False
    assert tel.parser_latency_ms == 0.0
    assert tel.graph_build_latency_ms == 0.0
    assert tel.graph_query_latency_ms == 0.0
    assert tel.semantic_parser_metrics is None


def test_generation_telemetry_phase1_fields_persist(tmp_path, monkeypatch):
    """Phase 1 fields round-trip through write/read telemetry state."""
    import git_cg.telemetry as telemetry_mod
    from git_cg.telemetry import GenerationTelemetry, read_telemetry_state, write_telemetry_state

    monkeypatch.setattr(telemetry_mod, "redact_payload", lambda payload: payload)

    tel = GenerationTelemetry(
        trace_id="t1",
        thread_id="th1",
        diff_hash="dh1",
        diff_output="diff",
        repo_name="repo",
        engine="mlx",
        model_name="model",
        system_prompt_hash="ph1",
        generated_message="msg",
        commit_plan_json={"intent": "feat"},
        score_card={},
        semantic_enabled=True,
        parser_latency_ms=1.25,
        graph_build_latency_ms=2.5,
        graph_query_latency_ms=3.75,
        semantic_parser_metrics={"semantic_parser_mode": "tree-sitter", "semantic_files_parsed": 2},
    )
    write_telemetry_state(str(tmp_path), tel)
    loaded = read_telemetry_state(str(tmp_path))
    assert loaded is not None
    assert loaded.semantic_enabled is True
    assert loaded.parser_latency_ms == 1.25
    assert loaded.graph_build_latency_ms == 2.5
    assert loaded.graph_query_latency_ms == 3.75
    assert loaded.semantic_parser_metrics is not None
    assert loaded.semantic_parser_metrics["semantic_files_parsed"] == 2


def test_read_legacy_json_backfills_phase1_fields(tmp_path):
    """Pre-Phase-1 state files must deserialize with semantic defaults."""
    from git_cg.telemetry import get_state_file_path, read_telemetry_state

    payload = {
        "diff_hash": "dh",
        "diff_output": "diff",
        "repo_name": "legacy-repo",
        "engine": "mlx",
        "model_name": "m",
        "system_prompt_hash": "ph",
        "generated_message": "msg",
        "commit_plan_json": {"intent": "feat"},
        "score_card": {},
    }
    state_file = get_state_file_path(str(tmp_path))
    state_file.write_text(__import__("json").dumps(payload), encoding="utf-8")
    loaded = read_telemetry_state(str(tmp_path))
    assert loaded is not None
    assert loaded.semantic_enabled is False
    assert loaded.parser_latency_ms == 0.0
    assert loaded.graph_build_latency_ms == 0.0
    assert loaded.graph_query_latency_ms == 0.0
    assert loaded.semantic_parser_metrics is None
    assert loaded.graph_schema_version == "unknown"


def test_write_telemetry_state_redacts_semantic_fallback_reasons(tmp_path, monkeypatch):
    """Path/error-bearing semantic_fallback_reasons must pass through betterleaks."""
    import git_cg.telemetry as telemetry_mod
    from git_cg.telemetry import GenerationTelemetry, read_telemetry_state, write_telemetry_state

    def fake_redact(payload: str) -> str:
        return payload.replace("secret-path.py", "[REDACTED]").replace("TOKEN123", "[REDACTED]")

    monkeypatch.setattr(telemetry_mod, "redact_payload", fake_redact)
    tel = GenerationTelemetry(
        trace_id="t1",
        thread_id="th1",
        diff_hash="dh1",
        diff_output="diff",
        repo_name="repo",
        engine="mlx",
        model_name="model",
        system_prompt_hash="ph1",
        generated_message="msg",
        commit_plan_json={"intent": "feat"},
        score_card={},
        semantic_enabled=True,
        semantic_parser_metrics={
            "semantic_parser_mode": "tree-sitter",
            "semantic_fallback_reasons": ["failed:secret-path.py:TOKEN123"],
        },
    )
    write_telemetry_state(str(tmp_path), tel)
    loaded = read_telemetry_state(str(tmp_path))
    assert loaded is not None
    assert loaded.semantic_parser_metrics is not None
    reasons = loaded.semantic_parser_metrics["semantic_fallback_reasons"]
    assert reasons == ["failed:[REDACTED]:[REDACTED]"]


def test_generation_telemetry_phase2_fields_default():
    """Phase 2 fingerprint metrics default to empty/unknown when omitted."""
    from git_cg.telemetry import GenerationTelemetry

    tel = GenerationTelemetry(
        trace_id="t1",
        thread_id="th1",
        diff_hash="dh1",
        diff_output="diff",
        repo_name="repo",
        engine="mlx",
        model_name="model",
        system_prompt_hash="ph1",
        generated_message="msg",
        commit_plan_json={"intent": "feat"},
        score_card={},
    )
    assert tel.body_similarity_min is None
    assert tel.body_similarity_avg is None
    assert tel.fingerprint_files_compared == 0
    assert tel.fingerprint_latency_ms == 0.0
    assert tel.fingerprint_class_counts is None
    assert tel.fingerprint_grammar_version == "unknown"
    assert tel.fingerprint_markers is None


def test_generation_telemetry_phase2_fields_persist(tmp_path, monkeypatch):
    """Phase 2 fields round-trip through write/read telemetry state."""
    import git_cg.telemetry as telemetry_mod
    from git_cg.telemetry import GenerationTelemetry, read_telemetry_state, write_telemetry_state

    monkeypatch.setattr(telemetry_mod, "redact_payload", lambda payload: payload)

    tel = GenerationTelemetry(
        trace_id="t1",
        thread_id="th1",
        diff_hash="dh1",
        diff_output="diff",
        repo_name="repo",
        engine="mlx",
        model_name="model",
        system_prompt_hash="ph1",
        generated_message="msg",
        commit_plan_json={"intent": "feat"},
        score_card={},
        body_similarity_min=0.81,
        body_similarity_avg=0.9,
        fingerprint_files_compared=3,
        fingerprint_latency_ms=4.5,
        fingerprint_class_counts={"comments_only": 1, "structural": 2},
        fingerprint_grammar_version="tree-sitter-language-pack==test",
        fingerprint_markers=["comments_only"],
    )
    write_telemetry_state(str(tmp_path), tel)
    loaded = read_telemetry_state(str(tmp_path))
    assert loaded is not None
    assert loaded.body_similarity_min == 0.81
    assert loaded.body_similarity_avg == 0.9
    assert loaded.fingerprint_files_compared == 3
    assert loaded.fingerprint_latency_ms == 4.5
    assert loaded.fingerprint_class_counts == {"comments_only": 1, "structural": 2}
    assert loaded.fingerprint_grammar_version == "tree-sitter-language-pack==test"
    assert loaded.fingerprint_markers == ["comments_only"]


def test_read_legacy_json_backfills_phase2_fields(tmp_path):
    """Pre-Phase-2 state files must deserialize with fingerprint defaults."""
    import json

    from git_cg.telemetry import get_state_file_path, read_telemetry_state

    payload = {
        "diff_hash": "dh",
        "diff_output": "diff",
        "repo_name": "legacy-repo",
        "engine": "mlx",
        "model_name": "m",
        "system_prompt_hash": "ph",
        "generated_message": "msg",
        "commit_plan_json": {"intent": "feat"},
        "score_card": {},
        "semantic_enabled": False,
    }
    state_file = get_state_file_path(str(tmp_path))
    state_file.write_text(json.dumps(payload), encoding="utf-8")
    loaded = read_telemetry_state(str(tmp_path))
    assert loaded is not None
    assert loaded.body_similarity_min is None
    assert loaded.body_similarity_avg is None
    assert loaded.fingerprint_files_compared == 0
    assert loaded.fingerprint_latency_ms == 0.0
    assert loaded.fingerprint_class_counts is None
    assert loaded.fingerprint_grammar_version == "unknown"
    assert loaded.fingerprint_markers is None


def test_generation_telemetry_preflight_fields_default():
    """Phase 3 preflight fields default to skipped / 0 / empty."""
    from git_cg.telemetry import GenerationTelemetry, PreflightMode

    tel = GenerationTelemetry(
        trace_id="t1",
        thread_id="th1",
        diff_hash="dh1",
        diff_output="diff",
        repo_name="repo",
        engine="mlx",
        model_name="model",
        system_prompt_hash="ph1",
        generated_message="msg",
        commit_plan_json={"intent": "feat"},
        score_card={},
    )
    assert tel.preflight_mode == PreflightMode.SKIPPED.value
    assert tel.preflight_groups_count == 0
    assert tel.preflight_fallback_reason == ""


def test_generation_telemetry_preflight_fields_persist(tmp_path, monkeypatch):
    """Phase 3 preflight fields round-trip through write/read telemetry state."""
    import git_cg.telemetry as telemetry_mod
    from git_cg.telemetry import GenerationTelemetry, PreflightMode, read_telemetry_state, write_telemetry_state

    monkeypatch.setattr(telemetry_mod, "redact_payload", lambda payload: payload)

    tel = GenerationTelemetry(
        trace_id="t1",
        thread_id="th1",
        diff_hash="dh1",
        diff_output="diff",
        repo_name="repo",
        engine="mlx",
        model_name="model",
        system_prompt_hash="ph1",
        generated_message="msg",
        commit_plan_json={"intent": "feat"},
        score_card={},
        preflight_mode=PreflightMode.HEURISTIC.value,
        preflight_groups_count=3,
        preflight_fallback_reason="llm_unavailable",
    )
    write_telemetry_state(str(tmp_path), tel)
    loaded = read_telemetry_state(str(tmp_path))
    assert loaded is not None
    assert loaded.preflight_mode == "heuristic"
    assert loaded.preflight_groups_count == 3
    assert loaded.preflight_fallback_reason == "llm_unavailable"


def test_read_legacy_json_backfills_preflight_fields(tmp_path):
    """Pre-Phase-3 state files deserialize with skipped preflight defaults."""
    import json

    from git_cg.telemetry import get_state_file_path, read_telemetry_state

    payload = {
        "diff_hash": "dh",
        "diff_output": "diff",
        "repo_name": "legacy-repo",
        "engine": "mlx",
        "model_name": "m",
        "system_prompt_hash": "ph",
        "generated_message": "msg",
        "commit_plan_json": {},
        "score_card": {},
    }
    path = get_state_file_path(str(tmp_path))
    path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = read_telemetry_state(str(tmp_path))
    assert loaded is not None
    assert loaded.preflight_mode == "skipped"
    assert loaded.preflight_groups_count == 0
    assert loaded.preflight_fallback_reason == ""


def test_write_telemetry_state_redacts_preflight_fallback_reason(tmp_path, monkeypatch):
    """preflight_fallback_reason must pass through redact_payload on write."""
    import git_cg.telemetry as telemetry_mod
    from git_cg.telemetry import GenerationTelemetry, read_telemetry_state, write_telemetry_state

    seen: list[str] = []

    def fake_redact(payload: str) -> str:
        """Replace the test token with its redacted representation and record each payload received."""
        seen.append(payload)
        if payload == "secret-token-reason":
            return "found [REDACTED]"
        return payload

    monkeypatch.setattr(telemetry_mod, "redact_payload", fake_redact)

    tel = GenerationTelemetry(
        trace_id="t1",
        thread_id="th1",
        diff_hash="dh1",
        diff_output="diff",
        repo_name="repo",
        engine="mlx",
        model_name="model",
        system_prompt_hash="ph1",
        generated_message="msg",
        commit_plan_json={"intent": "feat"},
        score_card={},
        preflight_mode="skipped",
        preflight_groups_count=0,
        preflight_fallback_reason="secret-token-reason",
    )
    write_telemetry_state(str(tmp_path), tel)
    assert "secret-token-reason" in seen
    loaded = read_telemetry_state(str(tmp_path))
    assert loaded is not None
    assert loaded.preflight_fallback_reason == "found [REDACTED]"


def test_preflight_mode_enum_values():
    from git_cg.telemetry import PreflightMode

    assert set(PreflightMode) == {
        PreflightMode.LLM,
        PreflightMode.HEURISTIC,
        PreflightMode.SKIPPED,
    }
    assert PreflightMode.LLM.value == "llm"
    assert PreflightMode.HEURISTIC.value == "heuristic"
    assert PreflightMode.SKIPPED.value == "skipped"


def test_reverse_parse_resolves_intent_id_from_emoji():
    from git_cg.sop import get_gitmoji_matrix
    from git_cg.telemetry import reverse_parse_commit_message

    matrix = get_gitmoji_matrix()
    sparkles = next(row for row in matrix if row.get("emoji") == "✨")
    expected = sparkles.get("intent_id") or str(sparkles.get("code", "")).strip(":")

    plan = reverse_parse_commit_message("✨ feat(core): add endpoint\n\nBody.\n\nSemVer-Impact: MINOR\n")
    assert plan["primary_intent"]["intent_id"] == expected
    assert plan["_partial"] is True  # rationale/split still unrecoverable


# ---------------------------------------------------------------------------
# Phase 7.5 (#180): shadow isolation telemetry fields
# ---------------------------------------------------------------------------


def _git_dir(tmp_path):
    """Return the tmp_path as a git_dir (telemetry state lives at GIT_CG_OPIK_STATE.json inside it)."""
    return str(tmp_path)


def test_shadow_fields_default_off(tmp_path):
    """Shadow fields default to off/skipped/none when not provided."""
    from git_cg.telemetry import read_telemetry_state, write_telemetry_state

    telemetry = _minimal_telemetry()
    write_telemetry_state(_git_dir(tmp_path), telemetry)

    loaded = read_telemetry_state(_git_dir(tmp_path))
    assert loaded.shadow_workspace_used is False
    assert loaded.semantic_refresh_graph == "skipped"
    assert loaded.shadow_fail_open_reason == "none"


def test_shadow_fields_roundtrip(tmp_path):
    """Shadow fields survive write → read round-trip."""
    from git_cg.telemetry import read_telemetry_state, write_telemetry_state

    telemetry = _minimal_telemetry(
        shadow_workspace_used=True,
        semantic_refresh_graph="ran",
        shadow_fail_open_reason="none",
    )
    write_telemetry_state(_git_dir(tmp_path), telemetry)

    loaded = read_telemetry_state(_git_dir(tmp_path))
    assert loaded.shadow_workspace_used is True
    assert loaded.semantic_refresh_graph == "ran"
    assert loaded.shadow_fail_open_reason == "none"


def test_shadow_fields_enum_coercion(tmp_path):
    """Enum members are coerced to plain strings on write/read."""
    from git_cg.telemetry import (
        SemanticRefreshGraph,
        ShadowFailOpenReason,
        read_telemetry_state,
        write_telemetry_state,
    )

    telemetry = _minimal_telemetry(
        shadow_workspace_used=True,
        semantic_refresh_graph=SemanticRefreshGraph.RAN,
        shadow_fail_open_reason=ShadowFailOpenReason.REFRESH_FAILED,
    )
    write_telemetry_state(_git_dir(tmp_path), telemetry)

    loaded = read_telemetry_state(_git_dir(tmp_path))
    assert isinstance(loaded.semantic_refresh_graph, str)
    assert loaded.semantic_refresh_graph == "ran"
    assert isinstance(loaded.shadow_fail_open_reason, str)
    assert loaded.shadow_fail_open_reason == "refresh_failed"


def test_shadow_fields_invalid_values_normalised(tmp_path):
    """Invalid shadow field values are normalised to safe defaults on read."""
    import json

    from git_cg.telemetry import read_telemetry_state

    state_path = tmp_path / "GIT_CG_OPIK_STATE.json"
    state_path.write_text(
        json.dumps(
            {
                "trace_id": None,
                "diff_hash": "abc123",
                "diff_output": "diff",
                "repo_name": "test",
                "engine": "mtplx",
                "model_name": "m",
                "system_prompt_hash": "h",
                "generated_message": "msg",
                "commit_plan_json": {},
                "score_card": {},
                "shadow_workspace_used": "yes",
                "semantic_refresh_graph": "bogus",
                "shadow_fail_open_reason": "also_bogus",
            }
        )
    )

    loaded = read_telemetry_state(_git_dir(tmp_path))
    assert loaded.shadow_workspace_used is True  # bool() coerces truthy string
    assert loaded.semantic_refresh_graph == "skipped"
    assert loaded.shadow_fail_open_reason == "none"


def test_shadow_fields_backward_compat_missing(tmp_path):
    """State files written before Phase 7.5 (missing shadow keys) default safely."""
    import json

    from git_cg.telemetry import read_telemetry_state

    state_path = tmp_path / "GIT_CG_OPIK_STATE.json"
    state_path.write_text(
        json.dumps(
            {
                "trace_id": None,
                "diff_hash": "abc123",
                "diff_output": "diff",
                "repo_name": "test",
                "engine": "mtplx",
                "model_name": "m",
                "system_prompt_hash": "h",
                "generated_message": "msg",
                "commit_plan_json": {},
                "score_card": {},
                "semantic_enabled": True,
            }
        )
    )

    loaded = read_telemetry_state(_git_dir(tmp_path))
    assert loaded.shadow_workspace_used is False
    assert loaded.semantic_refresh_graph == "skipped"
    assert loaded.shadow_fail_open_reason == "none"


def test_shadow_fail_open_all_reasons_valid(tmp_path):
    """All five ShadowFailOpenReason values survive round-trip."""
    from git_cg.telemetry import ShadowFailOpenReason, read_telemetry_state, write_telemetry_state

    for reason in ShadowFailOpenReason:
        telemetry = _minimal_telemetry(shadow_fail_open_reason=reason)
        write_telemetry_state(_git_dir(tmp_path), telemetry)
        loaded = read_telemetry_state(_git_dir(tmp_path))
        assert loaded.shadow_fail_open_reason == reason.value


def test_shadow_bounded_fields_skip_redact_payload(tmp_path, monkeypatch):
    """T4 — bounded Phase 7.5 fields are not sent through redact_payload on write."""
    import git_cg.telemetry as telemetry_mod
    from git_cg.telemetry import read_telemetry_state, write_telemetry_state

    seen: list[str] = []

    def tracking_redact(payload):
        seen.append(payload if isinstance(payload, str) else str(payload))
        return payload

    monkeypatch.setattr(telemetry_mod, "redact_payload", tracking_redact)

    telemetry = _minimal_telemetry(
        shadow_workspace_used=True,
        semantic_refresh_graph="ran",
        shadow_fail_open_reason="refresh_failed",
        diff_output="diff-secret-marker",
        generated_message="msg-secret-marker",
    )
    write_telemetry_state(_git_dir(tmp_path), telemetry)

    # Free-text fields are redacted; closed enums/bools are not handed to redact_payload alone.
    joined = "\n".join(seen)
    assert "diff-secret-marker" in joined
    assert "msg-secret-marker" in joined
    assert "refresh_failed" not in seen
    assert "ran" not in seen

    loaded = read_telemetry_state(_git_dir(tmp_path))
    assert loaded.shadow_workspace_used is True
    assert loaded.semantic_refresh_graph == "ran"
    assert loaded.shadow_fail_open_reason == "refresh_failed"


def test_write_telemetry_state_safe_accepts_shadow_kwargs(tmp_path, monkeypatch):
    """_write_telemetry_state_safe must accept and persist the three Phase 7.5 fields."""
    import git_cg.main as main_mod
    import git_cg.telemetry as telemetry_mod
    from git_cg.models import CommitIntent, CommitPlan, CommitType, SemVerImpact
    from git_cg.telemetry import read_telemetry_state

    monkeypatch.setattr(telemetry_mod, "redact_payload", lambda payload: payload)

    plan = CommitPlan(
        primary_intent=CommitIntent(
            intent_id="feature_addition",
            gitmoji="✨",
            cc_type=CommitType.FEAT,
            scope="core",
            description="shadow kwargs",
            semver_impact=SemVerImpact.MINOR,
            changelog_group="Added",
        ),
        rationale="test",
        body_summary="test body",
    )
    review_state = main_mod.ReviewState(commit_plan=plan)

    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    def fake_check_output(cmd, *args, **kwargs):
        if isinstance(cmd, list) and "--git-dir" in cmd:
            return str(git_dir) if kwargs.get("text") else str(git_dir).encode()
        return "." if kwargs.get("text") else b"."

    monkeypatch.setattr(main_mod.subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(main_mod, "LAST_OPIK_TRACE_ID", "trace-shadow")

    main_mod._write_telemetry_state_safe(
        review_state=review_state,
        diff_output="diff --git a/x.py b/x.py\n",
        engine="mtplx",
        model_name="test-model",
        system_prompt="sys",
        repo_name="repo",
        thread_id="thread-1",
        verbose=False,
        shadow_workspace_used=True,
        semantic_refresh_graph="ran",
        shadow_fail_open_reason="none",
    )

    loaded = read_telemetry_state(str(git_dir))
    assert loaded is not None
    assert loaded.shadow_workspace_used is True
    assert loaded.semantic_refresh_graph == "ran"
    assert loaded.shadow_fail_open_reason == "none"


# ---------------------------------------------------------------------------
# Issue #195 ranking confidence telemetry (Slice 2)
# ---------------------------------------------------------------------------


def test_ranking_override_is_bool_not_float():
    """A_07 type boundary: metadata field is bool; never store 1.0/0.0 here."""
    tel = _minimal_telemetry(ranking_override=True)
    assert tel.ranking_override is True
    assert isinstance(tel.ranking_override, bool)


def test_ranking_override_feedback_score_derived_at_boundary():
    from git_cg.telemetry import ranking_override_feedback_score

    assert ranking_override_feedback_score(True) == 1.0
    assert ranking_override_feedback_score(False) == 0.0


def test_write_then_read_preserves_ranking_confidence_fields(tmp_path, monkeypatch):
    """A_07: ranking fields round-trip through write/read with redaction gateway."""
    import git_cg.telemetry as telemetry_mod

    monkeypatch.setattr(telemetry_mod, "redact_payload", lambda payload: payload)

    tel = _minimal_telemetry(
        ranking_confidence_level="low",
        ranking_confidence_margin=6.2,
        ranking_confidence_reasons=["margin_below_low_threshold", "mixed_intent"],
        ranking_choice_path="ni_top_rank",
        ranking_override=False,
        ranking_arbitrate_effective="skipped_ni",
        lock_resolution="absent",
        gold_mode="warn",
        gold_findings_count=1,
        gold_finding_codes=["GOLD_BODY_INVENTORY"],
        gold_blocked=False,
        gold_regen_attempts=0,
        gold_self_correction_attempts=0,
        gold_self_correction_outcome="not_needed",
        gold_split_recommendation=False,
    )
    write_telemetry_state(str(tmp_path), tel)
    result = read_telemetry_state(str(tmp_path))

    assert result is not None
    assert result.ranking_confidence_level == "low"
    assert result.ranking_confidence_margin == pytest.approx(6.2)
    assert result.ranking_confidence_reasons == ["margin_below_low_threshold", "mixed_intent"]
    assert result.ranking_choice_path == "ni_top_rank"
    assert result.ranking_override is False
    assert isinstance(result.ranking_override, bool)
    assert result.ranking_arbitrate_effective == "skipped_ni"
    assert result.lock_resolution == "absent"
    assert result.gold_mode == "warn"
    assert result.gold_findings_count == 1
    assert result.gold_finding_codes == ["GOLD_BODY_INVENTORY"]
    assert result.gold_blocked is False
    assert result.gold_regen_attempts == 0
    assert result.gold_self_correction_attempts == 0
    assert result.gold_self_correction_outcome == "not_needed"
    assert result.gold_split_recommendation is False


def test_read_telemetry_state_defaults_ranking_fields_for_legacy_payload(tmp_path):
    """Legacy state files without ranking fields load with safe defaults."""
    state_path = get_state_file_path(str(tmp_path))
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "trace_id": None,
        "diff_hash": "abc",
        "diff_output": "diff",
        "repo_name": "r",
        "engine": "mtplx",
        "model_name": "m",
        "system_prompt_hash": "h",
        "generated_message": "feat: x",
        "commit_plan_json": {},
        "score_card": {},
    }
    state_path.write_text(json.dumps(payload), encoding="utf-8")
    result = read_telemetry_state(str(tmp_path))
    assert result is not None
    assert result.ranking_confidence_level is None
    assert result.ranking_override is False
    assert result.lock_resolution == "absent"
    assert result.gold_mode == "off"
    assert result.gold_self_correction_attempts == 0
    assert result.gold_self_correction_outcome == "not_needed"
    assert result.gold_split_recommendation is False


def test_read_telemetry_state_coerces_legacy_float_override(tmp_path):
    """If a legacy payload stored 1.0/0.0, coerce to bool metadata."""
    state_path = get_state_file_path(str(tmp_path))
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "trace_id": None,
        "diff_hash": "abc",
        "diff_output": "diff",
        "repo_name": "r",
        "engine": "mtplx",
        "model_name": "m",
        "system_prompt_hash": "h",
        "generated_message": "feat: x",
        "commit_plan_json": {},
        "score_card": {},
        "ranking_override": 1.0,
    }
    state_path.write_text(json.dumps(payload), encoding="utf-8")
    result = read_telemetry_state(str(tmp_path))
    assert result is not None
    assert result.ranking_override is True
    assert isinstance(result.ranking_override, bool)


def test_v11_gold_self_correction_fields_round_trip(tmp_path, monkeypatch):
    """Issue #191: v1.1 self-correction + P6 fields round-trip with closed outcome enum."""
    import git_cg.telemetry as telemetry_mod
    from git_cg.telemetry import GoldSelfCorrectionOutcome

    monkeypatch.setattr(telemetry_mod, "redact_payload", lambda payload: payload)

    tel = _minimal_telemetry(
        gold_mode="strict",
        gold_findings_count=2,
        gold_finding_codes=["GOLD_BODY_INVENTORY", "GOLD_SUBJECT_INVENTORY"],
        gold_blocked=True,
        gold_regen_attempts=1,
        gold_self_correction_attempts=1,
        gold_self_correction_outcome=GoldSelfCorrectionOutcome.ABORTED_STALL.value,
        gold_split_recommendation=True,
    )
    write_telemetry_state(str(tmp_path), tel)
    result = read_telemetry_state(str(tmp_path))
    assert result is not None
    assert result.gold_self_correction_attempts == 1
    assert result.gold_self_correction_outcome == "aborted_stall"
    assert result.gold_split_recommendation is True
    assert result.gold_finding_codes == ["GOLD_BODY_INVENTORY", "GOLD_SUBJECT_INVENTORY"]


def test_v11_gold_self_correction_invalid_outcome_defaults(tmp_path):
    """Unknown outcome values coerce to not_needed on read."""
    state_path = get_state_file_path(str(tmp_path))
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "trace_id": None,
        "diff_hash": "abc",
        "diff_output": "diff",
        "repo_name": "r",
        "engine": "mtplx",
        "model_name": "m",
        "system_prompt_hash": "h",
        "generated_message": "feat: x",
        "commit_plan_json": {},
        "score_card": {},
        "gold_self_correction_outcome": "not_a_real_outcome",
        "gold_self_correction_attempts": "2",
        "gold_split_recommendation": 1,
    }
    state_path.write_text(json.dumps(payload), encoding="utf-8")
    result = read_telemetry_state(str(tmp_path))
    assert result is not None
    assert result.gold_self_correction_outcome == "not_needed"
    assert result.gold_self_correction_attempts == 2
    assert result.gold_split_recommendation is True


def test_v11_gold_self_correction_non_numeric_attempts_defaults(tmp_path):
    """Non-numeric attempt counts coerce to 0 on read."""
    state_path = get_state_file_path(str(tmp_path))
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "trace_id": None,
        "diff_hash": "abc",
        "diff_output": "diff",
        "repo_name": "r",
        "engine": "mtplx",
        "model_name": "m",
        "system_prompt_hash": "h",
        "generated_message": "feat: x",
        "commit_plan_json": {},
        "score_card": {},
        "gold_self_correction_attempts": "not-a-number",
    }
    state_path.write_text(json.dumps(payload), encoding="utf-8")
    result = read_telemetry_state(str(tmp_path))
    assert result is not None
    assert result.gold_self_correction_attempts == 0


def test_v11_gold_split_recommendation_string_false_coerces(tmp_path):
    """Legacy string \"false\" must not become True via bare bool()."""
    state_path = get_state_file_path(str(tmp_path))
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "trace_id": None,
        "diff_hash": "abc",
        "diff_output": "diff",
        "repo_name": "r",
        "engine": "mtplx",
        "model_name": "m",
        "system_prompt_hash": "h",
        "generated_message": "feat: x",
        "commit_plan_json": {},
        "score_card": {},
        "gold_split_recommendation": "false",
    }
    state_path.write_text(json.dumps(payload), encoding="utf-8")
    result = read_telemetry_state(str(tmp_path))
    assert result is not None
    assert result.gold_split_recommendation is False


# ---------------------------------------------------------------------------
# Issue #204 Slice 5 presentation_fallback_reason
# ---------------------------------------------------------------------------


def test_presentation_fallback_reason_defaults_to_none():
    tel = _minimal_telemetry()
    assert tel.presentation_fallback_reason == "none"


def test_write_then_read_preserves_presentation_fallback_reason(tmp_path, monkeypatch):
    import git_cg.telemetry as telemetry_mod

    monkeypatch.setattr(telemetry_mod, "redact_payload", lambda payload: payload)

    tel = _minimal_telemetry(presentation_fallback_reason="low_confidence")
    write_telemetry_state(str(tmp_path), tel)
    result = read_telemetry_state(str(tmp_path))
    assert result is not None
    assert result.presentation_fallback_reason == "low_confidence"


def test_read_telemetry_state_defaults_presentation_fallback_for_legacy(tmp_path):
    state_path = get_state_file_path(str(tmp_path))
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "trace_id": None,
        "diff_hash": "abc",
        "diff_output": "diff",
        "repo_name": "r",
        "engine": "mtplx",
        "model_name": "m",
        "system_prompt_hash": "h",
        "generated_message": "msg",
        "commit_plan_json": {},
        "score_card": {},
    }
    state_path.write_text(json.dumps(payload), encoding="utf-8")
    result = read_telemetry_state(str(tmp_path))
    assert result is not None
    assert result.presentation_fallback_reason == "none"


def test_coerce_unknown_presentation_fallback_to_none():
    from git_cg.telemetry import coerce_presentation_fallback_reason

    assert coerce_presentation_fallback_reason("not-real") == "none"
    assert coerce_presentation_fallback_reason("LOW_CONFIDENCE") == "low_confidence"
    assert coerce_presentation_fallback_reason(None) == "none"
