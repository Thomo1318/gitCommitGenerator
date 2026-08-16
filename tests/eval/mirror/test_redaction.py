"""S4a R14 redaction ladder tests (plan §7.6)."""

from __future__ import annotations

import pytest

from git_cg.eval.enums import RedactionProfile
from git_cg.eval.mirror.redaction import (
    QUARANTINE_MARKER,
    RedactionError,
    redact_bundle_for_export,
)


def _bundle() -> dict:
    return {
        "schema_version": "ape_bundle_v1",
        "case_id": "case-1",
        "artifact_class": "final_accept",
        "bound": True,
        "final_message": "✨ feat(scope): subject",
        "expected_final_message": "✨ feat(scope): subject",
        "final_message_sha256": "a" * 64,
        "generation_task_input": {"diff_summary": "src/x.py changed", "ranked_intent_id": "feat"},
        "meta": {"score_card": {"d.header_length_ok": 1}},
        "session_thread_id": "thread-1",
    }


def test_public_ci_strips_message_and_task_input() -> None:
    out = redact_bundle_for_export(_bundle(), RedactionProfile.PUBLIC_CI)
    assert "final_message" not in out
    assert "expected_final_message" not in out
    assert "generation_task_input" not in out
    assert out["final_message_sha256"] == "a" * 64
    assert out["redaction_profile"] == "public_ci"


def test_message_only_keeps_final_message_not_task_input() -> None:
    out = redact_bundle_for_export(_bundle(), RedactionProfile.MESSAGE_ONLY)
    assert out["final_message"] == "✨ feat(scope): subject"
    assert "generation_task_input" not in out


def test_default_scrub_keeps_message_and_task_input() -> None:
    out = redact_bundle_for_export(_bundle(), RedactionProfile.DEFAULT_SCRUB)
    assert out["final_message"] == "✨ feat(scope): subject"
    assert out["generation_task_input"]["ranked_intent_id"] == "feat"


def test_input_bundle_never_mutated() -> None:
    bundle = _bundle()
    redact_bundle_for_export(bundle, RedactionProfile.PUBLIC_CI)
    assert "final_message" in bundle  # original intact
    assert "redaction_profile" not in bundle  # stamp only on the returned copy


def test_raw_dev_unsafe_refused() -> None:
    with pytest.raises(RedactionError, match="raw_dev_unsafe"):
        redact_bundle_for_export(_bundle(), RedactionProfile.RAW_DEV_UNSAFE)


def test_unknown_profile_fails_closed() -> None:
    with pytest.raises(RedactionError, match="unknown redaction profile"):
        redact_bundle_for_export(_bundle(), "not-a-profile")


def test_scrub_failure_quarantines_field(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force the scrubber to fail safe (omission sentinel) for the message.
    monkeypatch.setattr(
        "git_cg.eval.mirror.redaction.redact_payload",
        lambda _v: "[REDACTION FAILED - PAYLOAD OMITTED FOR SAFETY]",
    )
    out = redact_bundle_for_export(_bundle(), RedactionProfile.DEFAULT_SCRUB)
    # Field omitted, not emitted in the clear nor as the sentinel.
    assert "final_message" not in out
    assert "expected_final_message" not in out
    quarantine = out["meta"]["redaction_quarantine"]
    assert "final_message" in quarantine
    assert "expected_final_message" in quarantine
    assert out["meta"]["redaction_quarantine_marker"] == QUARANTINE_MARKER


def test_secret_scrubbed_from_retained_message(monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate betterleaks redacting a secret substring.
    monkeypatch.setattr(
        "git_cg.eval.mirror.redaction.redact_payload",
        lambda v: v.replace("sk-live", "[REDACTED]"),
    )
    bundle = _bundle()
    bundle["final_message"] = "token sk-live here"
    out = redact_bundle_for_export(bundle, RedactionProfile.DEFAULT_SCRUB)
    assert out["final_message"] == "token [REDACTED] here"


def test_task_input_secret_scrubbed_and_quarantined(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake(value: str) -> str:
        if "SECRET" in value:
            return "[REDACTION FAILED - PAYLOAD OMITTED FOR SAFETY]"
        return value

    monkeypatch.setattr("git_cg.eval.mirror.redaction.redact_payload", _fake)
    bundle = _bundle()
    bundle["generation_task_input"] = {"diff_summary": "SECRET diff", "ranked_intent_id": "feat"}
    out = redact_bundle_for_export(bundle, RedactionProfile.DEFAULT_SCRUB)
    assert "diff_summary" not in out["generation_task_input"]
    assert out["generation_task_input"]["ranked_intent_id"] == "feat"
    assert "generation_task_input.diff_summary" in out["meta"]["redaction_quarantine"]
