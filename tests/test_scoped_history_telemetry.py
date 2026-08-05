"""Phase 9 scoped-history telemetry persistence + redaction (Issue #163)."""

from __future__ import annotations

import json

from git_cg.telemetry import GenerationTelemetry, get_state_file_path, read_telemetry_state, write_telemetry_state


def _minimal(**overrides) -> GenerationTelemetry:
    base = dict(
        trace_id=None,
        diff_hash="abc",
        diff_output="diff",
        repo_name="repo",
        engine="mtplx",
        model_name="m",
        system_prompt_hash="h",
        generated_message="msg",
        commit_plan_json={},
        score_card={},
    )
    base.update(overrides)
    return GenerationTelemetry(**base)


def test_phase9_telemetry_defaults():
    """P9-A05: scoped-history telemetry fields default safely."""
    tel = _minimal()
    assert tel.scoped_history_fallback_reason == "none"
    assert tel.scoped_history_latency_ms == 0.0
    assert tel.rename_confidence == "none"
    assert tel.scoped_history_split_high_confidence is False
    assert tel.scoped_history_guidance is None
    assert tel.scoped_history_split_rationale == ""
    assert tel.scoped_history_rename_rationale == ""
    assert tel.structural_error_handling is False
    assert tel.structural_public_api is False
    assert tel.structural_new_command is False


def test_phase9_telemetry_round_trip(tmp_path, monkeypatch):
    """P9-A05: scoped-history telemetry fields persist across write/read."""
    monkeypatch.setattr("git_cg.telemetry.redact_payload", lambda payload: payload)
    tel = _minimal(
        scoped_history_fallback_reason="partial",
        scoped_history_latency_ms=12.5,
        rename_confidence="high",
        scoped_history_split_high_confidence=True,
        scoped_history_guidance="Split evidence: disjoint flows.",
        scoped_history_split_rationale="flow-disjoint partition",
        scoped_history_rename_rationale="corroborated rename pairs=1/1",
        structural_error_handling=True,
        structural_public_api=True,
        structural_new_command=False,
    )
    write_telemetry_state(str(tmp_path), tel)
    loaded = read_telemetry_state(str(tmp_path))
    assert loaded is not None
    assert loaded.scoped_history_fallback_reason == "partial"
    assert loaded.scoped_history_latency_ms == 12.5
    assert loaded.rename_confidence == "high"
    assert loaded.scoped_history_split_high_confidence is True
    assert loaded.scoped_history_guidance == "Split evidence: disjoint flows."
    assert loaded.scoped_history_split_rationale == "flow-disjoint partition"
    assert loaded.scoped_history_rename_rationale == "corroborated rename pairs=1/1"
    assert loaded.structural_error_handling is True
    assert loaded.structural_public_api is True
    assert loaded.structural_new_command is False


def test_phase9_telemetry_back_compat_missing_keys(tmp_path):
    """P9-A05: missing Phase 9 keys coerce to safe defaults (back-compat)."""
    path = get_state_file_path(str(tmp_path))
    path.write_text(
        json.dumps(
            {
                "trace_id": None,
                "diff_hash": "x",
                "diff_output": "d",
                "repo_name": "r",
                "engine": "e",
                "model_name": "m",
                "system_prompt_hash": "h",
                "generated_message": "g",
                "commit_plan_json": {},
                "score_card": {},
            }
        ),
        encoding="utf-8",
    )
    loaded = read_telemetry_state(str(tmp_path))
    assert loaded is not None
    assert loaded.scoped_history_fallback_reason == "none"
    assert loaded.rename_confidence == "none"
    assert loaded.scoped_history_guidance is None


def test_phase9_write_redacts_guidance_and_rationales(tmp_path, monkeypatch):
    """P9-A05: free-text guidance/rationales are redacted on telemetry write."""

    def fake_redact(payload: str) -> str:
        return (
            payload.replace("secret-path.py", "[REDACTED]")
            .replace("TOKEN123", "[REDACTED]")
            .replace("/Users/admin/secret", "[REDACTED]")
        )

    monkeypatch.setattr("git_cg.telemetry.redact_payload", fake_redact)
    tel = _minimal(
        scoped_history_fallback_reason="error",
        scoped_history_guidance="Split evidence involving secret-path.py TOKEN123",
        scoped_history_split_rationale="failed at /Users/admin/secret",
        scoped_history_rename_rationale="blob TOKEN123",
        rename_confidence="medium",
    )
    write_telemetry_state(str(tmp_path), tel)
    loaded = read_telemetry_state(str(tmp_path))
    assert loaded is not None
    assert loaded.scoped_history_guidance is not None
    assert "secret-path.py" not in loaded.scoped_history_guidance
    assert "TOKEN123" not in loaded.scoped_history_guidance
    assert "[REDACTED]" in loaded.scoped_history_guidance
    assert "TOKEN123" not in loaded.scoped_history_rename_rationale
    assert "/Users/admin/secret" not in loaded.scoped_history_split_rationale
    assert loaded.scoped_history_fallback_reason == "error"
    assert loaded.rename_confidence == "medium"


def test_phase9_read_coerces_unknown_enums(tmp_path):
    """P9-A05: unknown closed-vocab enums coerce on telemetry read."""
    path = get_state_file_path(str(tmp_path))
    path.write_text(
        json.dumps(
            {
                "trace_id": None,
                "diff_hash": "x",
                "diff_output": "d",
                "repo_name": "r",
                "engine": "e",
                "model_name": "m",
                "system_prompt_hash": "h",
                "generated_message": "g",
                "commit_plan_json": {},
                "score_card": {},
                "scoped_history_fallback_reason": "not-a-real-reason",
                "rename_confidence": "SUPER",
                "scoped_history_split_high_confidence": "true",
                "structural_error_handling": 1,
            }
        ),
        encoding="utf-8",
    )
    loaded = read_telemetry_state(str(tmp_path))
    assert loaded is not None
    assert loaded.scoped_history_fallback_reason == "none"
    assert loaded.rename_confidence == "none"
    assert loaded.scoped_history_split_high_confidence is True
    assert loaded.structural_error_handling is True
