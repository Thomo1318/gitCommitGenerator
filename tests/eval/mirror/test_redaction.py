"""S4a R14 redaction ladder tests (plan §7.6 / P0-5 / P1-7 / S4-B)."""

from __future__ import annotations

import copy

import pytest

from git_cg.eval.enums import RedactionProfile
from git_cg.eval.mirror.projections import (
    project_bundle_to_trace,
    project_score_card_to_feedback,
)
from git_cg.eval.mirror.redaction import (
    QUARANTINE_MARKER,
    RedactionError,
    redact_bundle_for_export,
)


def _bundle() -> dict:
    """Representative ape_bundle_v1 fixture for redaction tests."""
    return {
        "schema_version": "ape_bundle_v1",
        "id": "bundle_1",
        "case_id": "case-1",
        "artifact_class": "final_accept",
        "bound": True,
        "final_message": "✨ feat(scope): subject",
        "expected_final_message": "✨ feat(scope): subject",
        "final_message_sha256": "a" * 64,
        "generation_task_input": {
            "diff_summary": "src/x.py changed",
            "ranked_intent_id": "feat",
            "path_list": ["src/x.py"],
        },
        "gate": {"deterministic_pass": True, "notes": "ok"},
        "score_card": {"format_compliance": 1.0, "subject_length": 0.9, "label": "good"},
        "attempts": [
            {"final_message": "first", "scored_target": "final_message"},
            {
                "final_message": "✨ feat(scope): subject",
                "scored_target": "final_message",
                "artifact_class": "final_accept",
            },
        ],
        "meta": {
            "producer": "binder",
            "score_card": {"nested_score": 0.5},
            "binding": {"state": "bound", "trace_id": "t1"},
            "api_key": "should-never-export",
            "secret_note": "nope",
            "prompt_body": "full prompt text",
            "raw_diff": "@@ -1 +1 @@ secret",
            "accept_event": {"token": "evt-secret", "repo_root": "/tmp/repo"},
            "train_label": "hard_negative",
        },
        "session_thread_id": "thread-1",
    }


# --- Profile retention -----------------------------------------------------


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
    # default_scrub denies diff* keys (P1-7)
    assert "diff_summary" not in out["generation_task_input"]
    assert "generation_task_input.diff_summary" in out["meta"]["redaction_denied_keys"]


def test_input_bundle_never_mutated() -> None:
    bundle = _bundle()
    original = copy.deepcopy(bundle)
    redact_bundle_for_export(bundle, RedactionProfile.PUBLIC_CI)
    assert bundle == original
    assert "redaction_profile" not in bundle  # stamp only on the returned copy


def test_raw_dev_unsafe_refused() -> None:
    with pytest.raises(RedactionError, match="raw_dev_unsafe"):
        redact_bundle_for_export(_bundle(), RedactionProfile.RAW_DEV_UNSAFE)


def test_unknown_profile_fails_closed() -> None:
    with pytest.raises(RedactionError, match="unknown redaction profile"):
        redact_bundle_for_export(_bundle(), "not-a-profile")


# --- Scrub / quarantine (S4-B02/B03) --------------------------------------


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
    blob = str(out)
    assert "REDACTION FAILED" not in blob
    assert "sk-live" not in blob


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
    # Use a non-denied key so quarantine path is exercised (not deny-by-key).
    bundle["generation_task_input"] = {
        "summary_text": "SECRET diff",
        "ranked_intent_id": "feat",
    }
    out = redact_bundle_for_export(bundle, RedactionProfile.DEFAULT_SCRUB)
    assert "summary_text" not in out["generation_task_input"]
    assert out["generation_task_input"]["ranked_intent_id"] == "feat"
    assert "generation_task_input.summary_text" in out["meta"]["redaction_quarantine"]


def test_train_rich_still_scrubs_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """S4-B02: train_rich still scrubs secrets."""
    monkeypatch.setattr(
        "git_cg.eval.mirror.redaction.redact_payload",
        lambda v: v.replace("sk-live", "[REDACTED]"),
    )
    bundle = _bundle()
    bundle["final_message"] = "pair sk-live"
    bundle["generation_task_input"] = {"diff_summary": "body sk-live", "ranked_intent_id": "feat"}
    out = redact_bundle_for_export(bundle, RedactionProfile.TRAIN_RICH)
    assert out["final_message"] == "pair [REDACTED]"
    # train_rich may retain diff_summary keys, but values are scrubbed
    assert out["generation_task_input"]["diff_summary"] == "body [REDACTED]"
    assert "sk-live" not in str(out)


# --- P1-7 recursive scrub + typed meta ------------------------------------


def test_p1_7_forbidden_meta_keys_stripped() -> None:
    out = redact_bundle_for_export(_bundle(), RedactionProfile.DEFAULT_SCRUB)
    meta = out["meta"]
    for bad in ("api_key", "secret_note", "prompt_body", "raw_diff"):
        assert bad not in meta
    denied = meta["redaction_denied_keys"]
    assert "meta.api_key" in denied
    assert "meta.secret_note" in denied
    assert "meta.prompt_body" in denied
    assert "meta.raw_diff" in denied
    # Accept-event token never retained
    assert "token" not in (meta.get("accept_event") or {})
    assert "meta.accept_event.token" in denied
    # Allowed keys retained
    assert meta["producer"] == "binder"
    assert meta["train_label"] == "hard_negative"
    assert meta["binding"]["state"] == "bound"


def test_p1_7_nested_string_scrub_recursive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "git_cg.eval.mirror.redaction.redact_payload",
        lambda v: v.replace("SECRET", "[REDACTED]"),
    )
    bundle = _bundle()
    bundle["gate"] = {"deterministic_pass": True, "reason": "contains SECRET"}
    bundle["attempts"] = [
        {"final_message": "SECRET draft", "scored_target": "final_message"},
    ]
    bundle["meta"]["binding"] = {"state": "bound", "note": "SECRET nested"}
    out = redact_bundle_for_export(bundle, RedactionProfile.DEFAULT_SCRUB)
    assert out["gate"]["reason"] == "contains [REDACTED]"
    assert out["attempts"][0]["final_message"] == "[REDACTED] draft"
    assert out["meta"]["binding"]["note"] == "[REDACTED] nested"


def test_p1_7_nested_quarantine_exact_path(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake(value: str) -> str:
        if "BOOM" in value:
            return "[REDACTION FAILED - PAYLOAD OMITTED FOR SAFETY]"
        return value

    monkeypatch.setattr("git_cg.eval.mirror.redaction.redact_payload", _fake)
    bundle = _bundle()
    bundle["gate"] = {"deterministic_pass": True, "reason": "BOOM"}
    bundle["score_card"] = {"format_compliance": 1.0, "note": "ok"}
    out = redact_bundle_for_export(bundle, RedactionProfile.DEFAULT_SCRUB)
    assert "reason" not in out["gate"]
    assert "gate.reason" in out["meta"]["redaction_quarantine"]
    assert out["score_card"]["format_compliance"] == 1.0


def test_default_scrub_denies_diff_keys_but_keeps_path_list() -> None:
    out = redact_bundle_for_export(_bundle(), RedactionProfile.DEFAULT_SCRUB)
    gti = out["generation_task_input"]
    assert "diff_summary" not in gti
    assert gti["path_list"] == ["src/x.py"]
    assert gti["ranked_intent_id"] == "feat"


# --- P0-5 authority surfaces + projection join ----------------------------


def test_p0_5_authority_surfaces_retained_on_every_export_profile() -> None:
    for profile in (
        RedactionProfile.PUBLIC_CI,
        RedactionProfile.MESSAGE_ONLY,
        RedactionProfile.DEFAULT_SCRUB,
        RedactionProfile.PRIVATE_MESSAGE,
        RedactionProfile.TRAIN_RICH,
        RedactionProfile.ANTIPATTERN_VAULT,
        RedactionProfile.META_EVAL_SCRUB,
    ):
        out = redact_bundle_for_export(_bundle(), profile)
        assert out.get("id") == "bundle_1", profile
        assert out.get("gate", {}).get("deterministic_pass") is True, profile
        assert out.get("score_card", {}).get("format_compliance") == 1.0, profile
        assert isinstance(out.get("attempts"), list), profile
        assert len(out["attempts"]) == 2, profile


def test_p0_5_promote_score_card_from_meta_when_top_level_absent() -> None:
    """P0-5: promote nested score_card from meta when top-level card is absent."""
    bundle = _bundle()
    del bundle["score_card"]
    # nested remains under meta
    out = redact_bundle_for_export(bundle, RedactionProfile.DEFAULT_SCRUB)
    assert out["score_card"]["nested_score"] == 0.5


def test_p0_5_redact_then_project_preserves_authority() -> None:
    """Redaction→projection join: gate + score_card + final message survive."""
    redacted = redact_bundle_for_export(_bundle(), RedactionProfile.DEFAULT_SCRUB)
    trace = project_bundle_to_trace(redacted, experiment_name="exp")
    assert trace["metadata"]["deterministic_pass"] is True
    assert trace["metadata"]["score_card"]["format_compliance"] == 1.0
    assert trace["metadata"]["gate"]["deterministic_pass"] is True
    assert trace["input"]["bundle_id"] == "bundle_1"
    assert trace["input"]["attempt_count"] == 2
    assert trace["output"]["final_message"] == "✨ feat(scope): subject"

    feedback = project_score_card_to_feedback(redacted, experiment_name="exp")
    names = {f["name"] for f in feedback}
    keys = {(f.get("authority") or {}).get("score_card_key") for f in feedback}
    metric_ids = {f.get("metric_id") for f in feedback}
    surface = names | keys | metric_ids
    assert "format_compliance" in surface
    assert any(str(n) == "subject_length" or str(n).endswith("subject_length") for n in surface)


def test_p0_5_public_ci_retains_authority_but_not_message_bodies() -> None:
    out = redact_bundle_for_export(_bundle(), RedactionProfile.PUBLIC_CI)
    assert "final_message" not in out
    assert out["gate"]["deterministic_pass"] is True
    assert out["score_card"]["format_compliance"] == 1.0
    # Attempt structure retained; free-text leaves still scrubbed/kept as
    # structure carriers for count/final selection under P0-5.
    assert len(out["attempts"]) == 2
    # Scrubbed attempt messages still present as hashes/structure are allowed;
    # free-text attempt bodies remain scrubbed strings (secrets handled elsewhere).
    assert out["attempts"][-1]["scored_target"] == "final_message"


def test_no_ambient_forbidden_payload_by_default() -> None:
    """S4-B01 ambient leak negative: default path never emits deny-key payloads."""
    out = redact_bundle_for_export(_bundle(), RedactionProfile.DEFAULT_SCRUB)
    blob = str(out).lower()
    assert "should-never-export" not in blob
    assert "full prompt text" not in blob
    assert "@@ -1 +1 @@" not in blob
    assert "evt-secret" not in blob
    assert "api_key" not in out.get("meta", {})


def test_meta_allow_retains_split_and_provenance_labels() -> None:
    """Train/split provenance keys are intentional non-secret meta allowlist entries."""
    bundle = _bundle()
    bundle["meta"] = {
        **bundle.get("meta", {}),
        "split": "train",
        "split_group_id": "sg-allow-1",
        "provenance_label": "Gold-final",
        "api_key": "should-still-deny",
    }
    out = redact_bundle_for_export(bundle, RedactionProfile.DEFAULT_SCRUB)
    meta = out["meta"]
    assert meta["split"] == "train"
    assert meta["split_group_id"] == "sg-allow-1"
    assert meta["provenance_label"] == "Gold-final"
    assert "api_key" not in meta
    assert "meta.api_key" in meta["redaction_denied_keys"]
