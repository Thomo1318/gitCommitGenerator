"""Lab CLI entrypoint contracts (nested under eval_app)."""

from __future__ import annotations

import json
import re

import pytest
from typer.main import get_command
from typer.testing import CliRunner

from git_cg.eval import lab as lab_mod
from git_cg.eval.api_map import walk_eval_tree
from git_cg.eval.cli import lab_app
from git_cg.eval.lab import FORBIDDEN_LAB_VERBS, assert_no_forbidden_lab_verbs
from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin
from git_cg.main import app

runner = CliRunner()

_SECRET_RE = re.compile(r"(?i)(sk-[a-z0-9]{10,}|api[_-]?key\s*[:=]\s*\S+|bearer\s+[a-z0-9._\-]+|password\s*[:=]\s*\S+)")


def test_lab_app_nested_under_eval_app() -> None:
    """lab_app is nested under eval; no top-level git-cg lab command."""
    root = runner.invoke(app, ["eval", "--help"])
    assert root.exit_code == 0, root.output
    assert "lab" in root.output

    nested = runner.invoke(app, ["eval", "lab", "--help"])
    assert nested.exit_code == 0, nested.output
    assert "status" in nested.output
    assert "pins" in nested.output
    assert "run" in nested.output

    top = runner.invoke(app, ["lab", "--help"])
    assert top.exit_code != 0
    assert "No such command" in top.output or "Usage" in top.output


def test_lab_status_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """status probes eligibility/availability without network side effects."""
    monkeypatch.delenv("GIT_CG_EVAL_JUDGE_API_KEY", raising=False)
    monkeypatch.delenv("GIT_CG_EVAL_JUDGE_MODEL", raising=False)
    monkeypatch.setenv("GIT_CG_EVAL_JUDGE_MODEL", "gpt-4o-2024-08-06")

    result = runner.invoke(
        app,
        [
            "eval",
            "lab",
            "status",
            "--json",
            "--allows-lane-c",
            "--deterministic-pass",
            "--judge-model",
            "gpt-4o-2024-08-06",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "eval lab status"
    assert payload["ok"] is True
    data = payload["data"]
    assert data["authority"] == "advisory"
    assert data["product_gate"] is False
    assert data["offline"] is True
    assert "eligibility" in data
    assert "availability" in data
    assert data["availability"]["evidence"].get("raw_key_echoed") is False


def test_lab_status_secret_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    """status never echoes raw credential material."""
    secret = "sk-secretLABSTATUS0001deadbeef"
    monkeypatch.setenv("GIT_CG_EVAL_JUDGE_API_KEY", secret)
    monkeypatch.setenv("GIT_CG_EVAL_JUDGE_MODEL", "gpt-4o-2024-08-06")

    result = runner.invoke(
        app,
        [
            "eval",
            "lab",
            "status",
            "--json",
            "--judge-model",
            "gpt-4o-2024-08-06",
        ],
    )
    assert result.exit_code == 0, result.output
    assert secret not in result.output
    assert _SECRET_RE.search(result.output) is None
    payload = json.loads(result.output)
    avail = payload["data"]["availability"]
    assert avail["credentials_present"] is True
    assert avail["evidence"]["raw_key_echoed"] is False
    blob = json.dumps(payload)
    assert secret not in blob


def test_lab_run_advisory_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """run stamps advisory_only and never claims product gate authority."""
    monkeypatch.delenv("GIT_CG_EVAL_JUDGE_API_KEY", raising=False)
    monkeypatch.setenv("GIT_CG_EVAL_JUDGE_MODEL", "gpt-4o-2024-08-06")

    result = runner.invoke(
        app,
        [
            "eval",
            "lab",
            "run",
            "--json",
            "--judge-model",
            "gpt-4o-2024-08-06",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "eval lab run"
    data = payload["data"]
    assert data["authority"] == "advisory"
    assert data["product_gate"] is False
    assert data["advisory_only"] is True
    assert data["never_auto_promote"] is True
    assert data["invoked"] is False
    assert isinstance(data["rows"], list)


def test_lab_pins_thin_surface() -> None:
    """pins leaf reuses frozen pin helpers without expanding pack detail."""
    result = runner.invoke(app, ["eval", "lab", "pins", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "eval lab pins"
    data = payload["data"]
    assert data["schema_pack_pin"] == schema_pack_pin()
    assert data["metric_catalog_pin"] == metric_catalog_pin()
    assert data["product_gate"] is False
    assert data["offline"] is True


def test_no_doctor_verbs() -> None:
    """lab_app must not register doctor."""
    cmd = get_command(lab_app)
    names = set(cmd.list_commands(None) or [])
    assert "doctor" not in names
    assert_no_forbidden_lab_verbs(sorted(names))


def test_no_amend_brief_verbs() -> None:
    """lab_app must not register amend-brief."""
    cmd = get_command(lab_app)
    names = set(cmd.list_commands(None) or [])
    assert "amend-brief" not in names
    assert "amend_brief" not in names


def test_no_review_queue_verbs() -> None:
    """lab_app must not register review-queue."""
    cmd = get_command(lab_app)
    names = set(cmd.list_commands(None) or [])
    assert "review-queue" not in names
    assert "review_queue" not in names
    assert not (names & FORBIDDEN_LAB_VERBS)


def test_api_map_includes_lab_commands() -> None:
    """Live Typer walk includes nested lab commands."""
    paths = {n.path for n in walk_eval_tree()}
    assert "eval lab" in paths
    assert "eval lab status" in paths
    assert "eval lab pins" in paths
    assert "eval lab run" in paths


def test_lab_module_helpers_secret_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    """Direct helpers never return raw key material."""
    secret = "sk-helperSECRET999xyz"
    monkeypatch.setenv("GIT_CG_EVAL_JUDGE_API_KEY", secret)
    data = lab_mod.build_lab_status(
        deterministic_pass=True,
        allows_lane_c=True,
        judge_model="gpt-4o-2024-08-06",
        environ={
            "GIT_CG_EVAL_JUDGE_API_KEY": secret,
            "GIT_CG_EVAL_JUDGE_MODEL": "gpt-4o-2024-08-06",
        },
    )
    blob = json.dumps(data)
    assert secret not in blob
    assert data["availability"]["credentials_present"] is True
