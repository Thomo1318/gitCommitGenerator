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
    Build a minimal `GenerationTelemetry` instance for tests.
    
    Parameters:
        overrides: Keyword values that replace the default telemetry fields.
    
    Returns:
        GenerationTelemetry: A telemetry object with all required fields populated.
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
