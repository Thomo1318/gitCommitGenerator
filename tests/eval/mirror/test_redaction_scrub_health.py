"""Live betterleaks scrub-health probe for CI/runtime readiness.

These tests intentionally call the real ``betterleaks`` binary through
``git_cg.telemetry.redact_payload`` (no monkeypatch). They exist to catch the
CI footgun where the test job lacks betterleaks and every string fails closed
to the omission sentinel, cascading into mass redaction quarantine.
"""

from __future__ import annotations

import shutil

import pytest

from git_cg.eval.mirror.redaction import (
    QUARANTINE_MARKER,
    RedactionProfile,
    redact_bundle_for_export,
)
from git_cg.telemetry import redact_payload

_OMISSION = "[REDACTION FAILED - PAYLOAD OMITTED FOR SAFETY]"


def _require_betterleaks() -> None:
    """Require the `betterleaks` executable to be available on `PATH`."""
    if shutil.which("betterleaks") is None:
        pytest.fail(
            "betterleaks is not on PATH. CI test-and-coverage must install it via mise "
            "(see .github/workflows/ci.yml Install betterleaks via mise). Locally: "
            "`mise install betterleaks`."
        )


def test_betterleaks_binary_is_resolvable() -> None:
    """Hard gate: scanner must be installed and executable in this environment."""
    _require_betterleaks()
    path = shutil.which("betterleaks")
    assert path
    assert "betterleaks" in path


def test_live_redact_payload_identity_for_clean_text() -> None:
    """Clean ordinary text must round-trip (not omit) when betterleaks is healthy."""
    _require_betterleaks()
    samples = [
        "ordinary commit message subject",
        "feat(scope): add non-secret thing",
        '{"id":"bundle_1","final_message":"hello world"}',
        "path_list: src/git_cg/eval/mirror/redaction.py",
    ]
    for sample in samples:
        out = redact_payload(sample)
        assert out == sample, f"clean payload was altered/omitted: {sample!r} -> {out!r}"
        assert _OMISSION not in out
        assert "REDACTION FAILED" not in out


def test_live_default_scrub_does_not_mass_quarantine_clean_bundle() -> None:
    """End-to-end: a secret-free bundle must not be mass-quarantined under live scrub."""
    _require_betterleaks()
    bundle = {
        "id": "bundle_scrub_health_1",
        "final_message": "feat(mirror): keep clean export paths",
        "expected_final_message": "feat(mirror): keep clean export paths",
        "gate": {"deterministic_pass": True, "reason": "ok"},
        "score_card": {"format_compliance": 1.0},
        "attempts": [
            {"final_message": "feat(mirror): draft one", "scored_target": "final_message"},
        ],
        "generation_task_input": {
            "ranked_intent_id": "feat",
            "path_list": ["src/git_cg/eval/mirror/redaction.py"],
            "summary_text": "clean summary without secrets",
        },
        "meta": {
            "producer": "scrub-health-probe",
            "train_label": "hard_negative",
            "binding": {"state": "bound"},
        },
    }
    out = redact_bundle_for_export(bundle, RedactionProfile.DEFAULT_SCRUB)
    # Retained free-text must survive live scrub.
    assert out["final_message"] == bundle["final_message"]
    assert out["expected_final_message"] == bundle["expected_final_message"]
    assert out["gate"]["reason"] == "ok"
    assert out["attempts"][0]["final_message"] == "feat(mirror): draft one"
    assert out["generation_task_input"]["summary_text"] == "clean summary without secrets"
    # Quarantine may exist as an empty/absent structure, but clean fields must not land there.
    quarantine = out.get("meta", {}).get("redaction_quarantine") or []
    leaked_paths = {
        "final_message",
        "expected_final_message",
        "gate.reason",
        "attempts.0.final_message",
        "generation_task_input.summary_text",
    }
    assert leaked_paths.isdisjoint(set(quarantine)), quarantine
    blob = str(out)
    assert _OMISSION not in blob
    assert "REDACTION FAILED" not in blob
    # Marker key may be present only when quarantine occurred.
    if quarantine:
        assert out["meta"].get("redaction_quarantine_marker") == QUARANTINE_MARKER
