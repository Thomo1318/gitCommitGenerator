"""Offline lab pins helper contracts (secret-safe pin envelope)."""

from __future__ import annotations

import json
import re

import pytest
from typer.testing import CliRunner

from git_cg.eval import lab as lab_mod
from git_cg.eval.lane_c.eligibility import (
    DEFAULT_OUTPUT_CONTRACT_IDENTITY,
    DEFAULT_PACK_IDENTITY,
    DEFAULT_SAMPLING_IDENTITY,
)
from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin
from git_cg.main import app

runner = CliRunner()

_SECRET_RE = re.compile(r"(?i)(sk-[a-z0-9]{10,}|api[_-]?key\s*[:=]\s*\S+|bearer\s+[a-z0-9._\-]+|password\s*[:=]\s*\S+)")
_PROMPT_BODY_MARKERS = (
    "You are",
    "expected_gold",
    "score the commit",
    "system prompt",
)


def test_show_pins_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """pins stays offline: no network client construction, pure local pins."""
    monkeypatch.delenv("GIT_CG_EVAL_JUDGE_API_KEY", raising=False)
    monkeypatch.delenv("GIT_CG_EVAL_JUDGE_MODEL", raising=False)

    result = runner.invoke(app, ["eval", "lab", "pins", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    data = payload["data"]
    assert payload["ok"] is True
    assert data["offline"] is True
    assert data["authority"] == "advisory"
    assert data["product_gate"] is False
    assert data["secrets_consulted"] is False


def test_show_pins_secret_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    """pins never echoes credential material from the environment."""
    secret = "sk-secretLABPINS0001deadbeef"
    monkeypatch.setenv("GIT_CG_EVAL_JUDGE_API_KEY", secret)
    monkeypatch.setenv("GIT_CG_EVAL_JUDGE_MODEL", "gpt-4o-2024-08-06")

    result = runner.invoke(app, ["eval", "lab", "pins", "--json"])
    assert result.exit_code == 0, result.output
    assert secret not in result.output
    assert _SECRET_RE.search(result.output) is None
    payload = json.loads(result.output)
    blob = json.dumps(payload)
    assert secret not in blob
    assert payload["data"]["secrets_consulted"] is False
    assert payload["data"]["model_pin"] == "gpt-4o-2024-08-06"


def test_show_pins_json_envelope() -> None:
    """--json emits cli_output_envelope_v1 with pin data payload."""
    result = runner.invoke(app, ["eval", "lab", "pins", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["schema_version"] == "cli_output_envelope_v1"
    assert payload["command"] == "eval lab pins"
    assert payload["ok"] is True
    data = payload["data"]
    for key in (
        "schema_pack_pin",
        "metric_catalog_pin",
        "prompt_pack_pin",
        "model_pin",
        "sampling_pin",
        "schema_pack",
        "metric_catalog",
        "prompt_pack",
        "model",
        "sampling",
    ):
        assert key in data


def test_show_pins_human_line() -> None:
    """Human mode prints the compact summary and explicit pin rows."""
    result = runner.invoke(app, ["eval", "lab", "pins"])
    assert result.exit_code == 0, result.output
    out = result.output
    assert "schema_pack:" in out
    assert "metric_catalog:" in out
    assert "schema_pack_pin=" in out
    assert "metric_catalog_pin=" in out
    assert "prompt_pack_pin=" in out
    assert "sampling_pin=" in out
    assert "model_pin=" in out


def test_show_pins_includes_schema_pack() -> None:
    """Envelope includes the live schema_pack pin from pins.py."""
    result = runner.invoke(app, ["eval", "lab", "pins", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)["data"]
    expected = schema_pack_pin()
    assert data["schema_pack_pin"] == expected
    assert data["schema_pack"] == expected
    assert expected.startswith("schema_pack_v0@")


def test_show_pins_includes_metric_catalog() -> None:
    """Envelope includes the live metric_catalog pin from pins.py."""
    result = runner.invoke(app, ["eval", "lab", "pins", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)["data"]
    expected = metric_catalog_pin()
    assert data["metric_catalog_pin"] == expected
    assert data["metric_catalog"] == expected
    assert expected.startswith("metric_catalog_v0@")


def test_show_pins_includes_prompt_and_sampling_defaults() -> None:
    """Prompt-pack and sampling identities default to Lane C offline pins."""
    data = lab_mod.build_lab_pins(environ={})
    assert data["prompt_pack_pin"] == DEFAULT_PACK_IDENTITY
    assert data["sampling_pin"] == DEFAULT_SAMPLING_IDENTITY
    assert data["output_contract_pin"] == DEFAULT_OUTPUT_CONTRACT_IDENTITY
    assert data["prompt_pack"] == DEFAULT_PACK_IDENTITY
    assert data["sampling"] == DEFAULT_SAMPLING_IDENTITY


def test_show_pins_model_override_and_local_packs() -> None:
    """Explicit model override wins; local pack pins are pin-tokens only."""
    data = lab_mod.build_lab_pins(
        judge_model="gpt-4o-2024-08-06",
        environ={},
    )
    assert data["model_pin"] == "gpt-4o-2024-08-06"
    assert data["model"] == "gpt-4o-2024-08-06"
    available = data["available_prompt_pack_pins"]
    assert isinstance(available, dict)
    for metric_id, pin in available.items():
        assert metric_id.startswith("cprime.")
        assert pin.startswith("prompt_pack_v1@")
        assert len(pin.split("@", 1)[1]) == 64
    blob = json.dumps(data)
    for marker in _PROMPT_BODY_MARKERS:
        assert marker not in blob


def test_show_pins_no_prompt_body_in_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI output never includes prompt-pack file bodies."""
    monkeypatch.setenv("GIT_CG_EVAL_JUDGE_MODEL", "gpt-4o-2024-08-06")
    result = runner.invoke(app, ["eval", "lab", "pins", "--json"])
    assert result.exit_code == 0, result.output
    for marker in _PROMPT_BODY_MARKERS:
        assert marker not in result.output
