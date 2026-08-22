"""S6 Slice 7 contract tests (Issue #246).

Covers:
* dogfood deterministic sample reproducibility (schema pin + membership hash).
* async structural seam: async mode never awaits the judge (never blocks).
* train-export row scrub-failure policy: drop + report + continue; no
  .eval/quarantine/; hard_negative never enters positive_gold.
* CLI envelope shape for the five Slice 7 commands.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Dogfood: deterministic sample reproducibility
# ---------------------------------------------------------------------------


def test_dogfood_sample_deterministic_membership() -> None:
    from git_cg.eval.dogfood.capture import select_sample_members

    pop = ["a", "b", "c", "d"]
    a = select_sample_members(pop, rate=0.5, seed="seed-fixed-1")
    b = select_sample_members(pop, rate=0.5, seed="seed-fixed-1")
    assert a == b  # stable across runs
    assert len(a) == 2  # rate*N
    assert set(a) <= set(pop)  # membership within population


def test_dogfood_sample_schema_requires_repro_fields() -> None:
    import hashlib

    from git_cg.eval.dogfood.capture import DOGFoodError, build_attachment

    sha = hashlib.sha256(b"m").hexdigest()
    with pytest.raises(DOGFoodError):
        build_attachment(message_sha256=sha, mode="sample")  # missing seed/rate/population


def test_dogfood_async_never_awaits_judge() -> None:
    """Structural seam: async mode marks never-await; product never blocks."""
    import hashlib

    from git_cg.eval.dogfood.capture import capture_dogfood

    sha = hashlib.sha256(b"feat: x").hexdigest()
    data = capture_dogfood(
        Path.cwd(),
        message_sha256=sha,
        mode="async",
        write=False,
    )
    assert data["product_block"] is False
    assert data["async_never_awaits_judge"] is True
    assert data["authority"] == "advisory"


def test_dogfood_attachment_reproduces_membership() -> None:
    from git_cg.eval.dogfood.capture import attachment_reproduces_membership

    att = {
        "mode": "sample",
        "sample_seed": "s",
        "sample_rate": 0.5,
        "population_id": "pop",
        "selected_ids": ["a"],
        "selected_set_hash": "0" * 64,
    }
    # Current helper verifies recorded metadata/hash consistency only.
    assert attachment_reproduces_membership(att) is False  # hash is fake → mismatch


# ---------------------------------------------------------------------------
# Train export: row scrub-failure policy
# ---------------------------------------------------------------------------


def _write_bundle(root: Path, bid: str, label: str, message: str) -> None:
    bundles = root / ".eval" / "bundles" / "acceptpath"
    bundles.mkdir(parents=True, exist_ok=True)
    (bundles / f"{bid}.json").write_text(
        json.dumps(
            {
                "schema_version": "acceptpath_bundle_v1",
                "id": bid,
                "train_label": label,
                "final_message": message,
                "gate": {"deterministic_pass": label == "positive"},
                "meta": {"train_label": label},
            }
        )
    )


def test_train_export_empty_repo_ok(tmp_path: Path) -> None:
    from git_cg.eval.train_export import build_train_export

    result = build_train_export(tmp_path, redaction_profile="train_rich")
    assert result["export"]["schema_version"] == "train_export_v1"
    assert result["row_ids"] == []
    assert result["dropped_row_ids"] == []


def test_train_export_unlabeled_dropped_not_positive(tmp_path: Path) -> None:
    from git_cg.eval.train_export import build_train_export

    _write_bundle(tmp_path, "b-unlabeled", "", "feat: no label")
    result = build_train_export(tmp_path, redaction_profile="train_rich")
    # Unlabeled rows are excluded from export rows (never silent positive).
    assert result["positive_gold_count"] == 0
    assert "b-unlabeled" in result["dropped_row_ids"]


def test_train_export_no_quarantine_store(tmp_path: Path) -> None:
    from git_cg.eval.train_export import train_export

    _write_bundle(tmp_path, "b-pos", "positive", "feat: ok")
    train_export(tmp_path, redaction_profile="train_rich")
    assert not (tmp_path / ".eval" / "quarantine").exists()


def test_train_export_rejects_raw_dev_unsafe(tmp_path: Path) -> None:
    from git_cg.eval.train_export import TrainExportError, train_export

    with pytest.raises(TrainExportError) as ei:
        train_export(tmp_path, redaction_profile="raw_dev_unsafe", write=False)
    assert ei.value.exit_code == 2


# ---------------------------------------------------------------------------
# Sessions: usage vs integrity exit classes
# ---------------------------------------------------------------------------


def test_session_not_found_is_usage(tmp_path: Path) -> None:
    from git_cg.eval.sessions import SessionsError, show_session

    with pytest.raises(SessionsError) as ei:
        show_session(tmp_path, "sess_missing")
    assert ei.value.exit_code == 2
    assert ei.value.code == "EVAL_USAGE"


def test_session_invalid_id_is_usage(tmp_path: Path) -> None:
    from git_cg.eval.sessions import SessionsError, show_session

    with pytest.raises(SessionsError) as ei:
        show_session(tmp_path, "not-a-sess-id")
    assert ei.value.exit_code == 2


# ---------------------------------------------------------------------------
# CLI envelope: five Slice 7 commands emit cli_output_envelope_v1
# ---------------------------------------------------------------------------


def _cli(args: list[str]) -> dict:
    from typer.testing import CliRunner

    from git_cg.main import app

    r = CliRunner().invoke(app, args)
    return json.loads(r.stdout), r.exit_code


def test_cli_dogfood_envelope() -> None:
    payload, code = _cli(["eval", "dogfood", "--commit-message", "feat: x", "--mode", "always", "--no-write", "--json"])
    assert code == 0
    assert payload["schema_version"] == "cli_output_envelope_v1"
    assert payload["command"] == "eval dogfood"
    assert payload["ok"] is True
    assert payload["data"]["product_block"] is False


def test_cli_train_export_envelope_empty() -> None:
    payload, code = _cli(["eval", "train-export", "--no-write", "--json"])
    assert code == 0
    assert payload["command"] == "eval train-export"
    assert payload["data"]["scrub_report"]["status"] == "ok"


def test_cli_session_show_missing_usage() -> None:
    payload, code = _cli(["eval", "session", "show", "--id", "sess_missing", "--json"])
    assert code == 2
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "EVAL_USAGE"


def test_cli_thread_show_missing_usage() -> None:
    payload, code = _cli(["eval", "thread", "show", "--id", "sess_missing", "--json"])
    assert code == 2
    assert payload["ok"] is False


def test_cli_amend_brief_missing_run_is_usage() -> None:
    # Repo experiments store exists but run id is absent → usage (exit 2).
    payload, code = _cli(["eval", "amend-brief", "rs_missing", "--no-write", "--json"])
    assert code in (2, 4)  # 2 when store exists, 4 when store missing (fail-closed)
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] in {"EVAL_USAGE", "EVAL_STORE_INTEGRITY"}
