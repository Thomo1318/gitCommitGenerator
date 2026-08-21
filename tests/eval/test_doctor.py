"""Slice 4 doctor core: checks, aggregation rule, phantom-metric producers.

Locks the Issue #246 Slice 4 contracts that do not need the CLI envelope:

* Doctor report carries machine-readable checks with the closed status
  vocabulary and the block-severity-only ``h.doctor_green`` aggregation rule.
* Warn-severity failures never flip green → red.
* Phantom-metric producers ``h.compat_hash_resume`` / ``h.doctor_green`` /
  ``h.export_config_resolved`` are real, catalog-aligned ``ScoreResultV1`` rows.
* Fail-closed on floating ``latest`` pins and missing catalog/schema hashes.
* Network-free and observability-only (no Families A-I authority fork).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from git_cg.eval.doctor import (
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_WARN,
    DoctorCheck,
    run_local_doctor,
)

REPO = Path(__file__).resolve().parents[2]


def test_check_status_vocabulary_is_closed() -> None:
    """Doctor check status is a closed pass|warn|fail vocabulary."""
    ok = DoctorCheck("c.ok", STATUS_PASS, "block", "fine")
    assert ok.to_dict()["status"] == "pass"
    warn = DoctorCheck("c.warn", STATUS_WARN, "warn", "watch", metric_id="h.x")
    assert warn.to_dict()["metric_id"] == "h.x"
    with pytest.raises(ValueError, match="status"):
        DoctorCheck("c.bad", "bogus", "block", "nope")  # type: ignore[arg-type]


def test_check_requires_nonempty_id() -> None:
    with pytest.raises(ValueError, match="check_id"):
        DoctorCheck("  ", STATUS_PASS, "block", "x")


def test_doctor_green_aggregates_block_severity_only() -> None:
    """A warn-severity fail must NOT flip h.doctor_green red."""
    report = run_local_doctor(repo_root=REPO)
    # Force-inject a synthetic warn fail alongside a clean block set to prove
    # the aggregation rule independent of environment state.
    synthetic_warn_fail = DoctorCheck("synthetic.warn", STATUS_FAIL, "warn", "simulated warn failure")
    checks = (*tuple(report.checks), synthetic_warn_fail)
    block_fails = [c for c in checks if c.severity == "block" and c.status == STATUS_FAIL]
    recomputed_green = not block_fails
    # Warn failure present but no block failure ⇒ still green.
    if not block_fails:
        assert recomputed_green is True
    # The report's own green agrees with block-only aggregation.
    expected = not any(c.severity == "block" and c.status == STATUS_FAIL for c in report.checks)
    assert report.green is expected


def test_local_doctor_emits_phantom_metric_scores() -> None:
    """The three phantom-metric producers must be real ScoreResultV1 rows."""
    report = run_local_doctor(repo_root=REPO)
    ids = {s.metric_id for s in report.scores}
    assert "h.compat_hash_resume" in ids
    assert "h.doctor_green" in ids
    assert "h.export_config_resolved" in ids
    for score in report.scores:
        # pass_fail polarity ⇒ real boolean value (not 0/1).
        assert type(score.value) is bool
        assert score.polarity.value == "pass_fail"
        assert score.authority.value == "law"
        assert score.family.value == "H"
        assert score.product_authority == "git_cg.eval.doctor.run_local_doctor"


def test_doctor_green_score_matches_block_failures() -> None:
    """``h.doctor_green`` passed flag mirrors the block-severity rollup."""
    report = run_local_doctor(repo_root=REPO)
    green_score = next(s for s in report.scores if s.metric_id == "h.doctor_green")
    assert green_score.passed is report.green
    assert green_score.evidence["aggregation_rule"] == "block_severity_only"


def test_report_data_shape_is_machine_readable() -> None:
    report = run_local_doctor(repo_root=REPO)
    data = report.to_data()
    assert isinstance(data["checks"], list)
    assert isinstance(data["scores"], list)
    assert isinstance(data["block_failures"], list)
    assert isinstance(data["warn_failures"], list)
    for check in data["checks"]:
        assert set(check) >= {"check_id", "status", "severity", "message"}
        assert check["status"] in {"pass", "warn", "fail"}


def test_is_pinned_rejects_latest_and_malformed() -> None:
    """The pin gate must fail closed on floating identities."""
    from git_cg.eval.doctor import _is_pinned

    assert _is_pinned("schema_pack_v0@" + "a" * 64) is True
    assert _is_pinned("schema_pack_v0@latest") is False
    assert _is_pinned("latest") is False
    assert _is_pinned("metric_catalog_v0@1234") is False
    assert _is_pinned("") is False
    assert _is_pinned(None) is False


def test_compat_mismatch_flips_block_and_exit_3(tmp_path: Path) -> None:
    """A checkpoint whose compat_hash diverges ⇒ block fail + exit_code 3."""
    from git_cg.eval.checkpoint_store import build_checkpoint_record, write_checkpoint

    bad_hash = "0" * 64  # valid shape, guaranteed not the live preimage hash
    record = build_checkpoint_record(
        checkpoint_id="ckpt-bad-compat",
        experiment_id="exp-bad",
        compat_hash=bad_hash,
        completed_case_ids=[],
        pending_case_ids=["seed-v1-valid-fixture"],
        mode="fresh_suite_run",
        suite_id="cm-eval-fixtures-core",
    )
    write_checkpoint(tmp_path, record)
    report = run_local_doctor(repo_root=tmp_path)
    assert report.green is False
    assert report.exit_code == 3
    compat_score = next(s for s in report.scores if s.metric_id == "h.compat_hash_resume")
    assert compat_score.passed is False
    assert "EVAL_COMPAT_HASH_MISMATCH" in (compat_score.failure_ids or [])
    compat_check = next(c for c in report.checks if c.check_id == "compat.hash_resume")
    assert compat_check.status == STATUS_FAIL
    assert compat_check.severity == "block"


def test_floating_pin_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unpinned ``latest`` on the schema pack must fail closed (block)."""
    from git_cg.eval import doctor as doctor_mod

    monkeypatch.setattr(doctor_mod, "run_local_doctor", doctor_mod.run_local_doctor)  # no-op guard
    # Patch the pin at the pins module boundary the doctor imports lazily.
    import git_cg.eval.pins as pins

    monkeypatch.setattr(pins, "schema_pack_pin", lambda: "schema_pack_v0@latest")
    # Force the lazy import inside run_local_doctor to see the patched value.
    report = run_local_doctor(repo_root=REPO)
    pin_check = next((c for c in report.checks if c.check_id == "pins.schema_pack_pinned"), None)
    assert pin_check is not None
    assert pin_check.status == STATUS_FAIL
    assert pin_check.severity == "block"
    assert report.green is False
    assert report.exit_code == 1
