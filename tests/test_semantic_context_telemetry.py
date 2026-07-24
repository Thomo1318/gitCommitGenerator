"""Phase 7 telemetry field persistence and redaction (#162)."""

from __future__ import annotations

from git_cg.telemetry import GenerationTelemetry, read_telemetry_state, write_telemetry_state


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


def test_phase7_telemetry_defaults():
    tel = _minimal()
    assert tel.blast_radius_size is None
    assert tel.affected_flows_count is None
    assert tel.test_coverage_gap is None
    assert tel.semantic_context_schema_version == ""
    assert tel.semantic_context_fallback_reasons is None


def test_phase7_telemetry_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr("git_cg.telemetry.redact_payload", lambda payload: payload)
    tel = _minimal(
        blast_radius_size=11,
        affected_flows_count=2,
        test_coverage_gap=True,
        semantic_context_schema_version="semantic_diff_summary_v1",
        semantic_context_fallback_reasons=["graph:unavailable"],
    )
    write_telemetry_state(str(tmp_path), tel)
    loaded = read_telemetry_state(str(tmp_path))
    assert loaded is not None
    assert loaded.blast_radius_size == 11
    assert loaded.affected_flows_count == 2
    assert loaded.test_coverage_gap is True
    assert loaded.semantic_context_schema_version == "semantic_diff_summary_v1"
    assert loaded.semantic_context_fallback_reasons == ["graph:unavailable"]


def test_phase7_telemetry_back_compat_missing_keys(tmp_path):
    import json

    path = tmp_path / "GIT_CG_OPIK_STATE.json"
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
    assert loaded.blast_radius_size is None
    assert loaded.test_coverage_gap is None
    assert loaded.semantic_context_schema_version == ""


def test_phase7_fallback_reasons_redacted(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "git_cg.telemetry.redact_payload",
        lambda payload: "REDACTED" if "secret" in payload else payload,
    )
    tel = _minimal(semantic_context_fallback_reasons=["ok", "path:/secret/file"])
    write_telemetry_state(str(tmp_path), tel)
    loaded = read_telemetry_state(str(tmp_path))
    assert loaded is not None
    assert loaded.semantic_context_fallback_reasons == ["ok", "REDACTED"]
