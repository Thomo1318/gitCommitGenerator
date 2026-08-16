"""message_versions hook tests (D12 / M7).

Covers the locked item shape (``kind`` / ``message`` / ``message_sha256`` /
``source``), chronological ordering (generated → edited → final_accept),
inclusion law (only real evidence; never invent intermediate versions), and
fail-closed validation.
"""

from __future__ import annotations

import pytest

from git_cg.eval.binding.binder import message_sha256_bytes
from git_cg.eval.binding.message_versions import (
    MESSAGE_VERSION_KINDS,
    MESSAGE_VERSION_SOURCES,
    build_message_versions,
)

DRAFT = "fix: draft subject"
FINAL = "🦺 fix(scope): final accepted subject"


def test_empty_when_no_evidence() -> None:
    assert build_message_versions() == []


def test_generated_only() -> None:
    versions = build_message_versions(generated_message=DRAFT)
    assert [v["kind"] for v in versions] == ["generated"]
    assert versions[0]["source"] == "telemetry_state"
    assert versions[0]["message_sha256"] == message_sha256_bytes(DRAFT)


def test_final_only() -> None:
    versions = build_message_versions(final_message=FINAL)
    assert [v["kind"] for v in versions] == ["final_accept"]
    assert versions[0]["source"] == "commit_editmsg"


def test_draft_equals_final_is_not_an_edit() -> None:
    # draft == final ⇒ no edited version invented (M7)
    versions = build_message_versions(generated_message=FINAL, final_message=FINAL)
    assert [v["kind"] for v in versions] == ["generated", "final_accept"]


def test_draft_differs_from_final_yields_edited() -> None:
    versions = build_message_versions(generated_message=DRAFT, final_message=FINAL, edited=True)
    assert [v["kind"] for v in versions] == ["generated", "edited", "final_accept"]
    assert versions[1]["source"] == "classify_edit"


def test_explicit_edited_message() -> None:
    versions = build_message_versions(generated_message=DRAFT, edited_message="fix: tweaked", final_message=FINAL)
    kinds = [v["kind"] for v in versions]
    assert kinds == ["generated", "edited", "final_accept"]
    assert versions[1]["message"] == "fix: tweaked"


def test_edited_flag_without_difference_is_not_invented() -> None:
    # edited=True but draft == final ⇒ no real edit evidence ⇒ no edited row
    versions = build_message_versions(generated_message=FINAL, final_message=FINAL, edited=True)
    assert [v["kind"] for v in versions] == ["generated", "final_accept"]


def test_blank_messages_skipped() -> None:
    versions = build_message_versions(generated_message="   ", final_message=FINAL)
    assert [v["kind"] for v in versions] == ["final_accept"]


def test_vocab_locked() -> None:
    assert frozenset({"generated", "edited", "final_accept"}) == MESSAGE_VERSION_KINDS
    assert frozenset({"telemetry_state", "commit_editmsg", "classify_edit"}) == MESSAGE_VERSION_SOURCES


def test_item_shape_keys() -> None:
    versions = build_message_versions(generated_message=DRAFT, final_message=FINAL)
    for v in versions:
        assert set(v.keys()) == {"kind", "message", "message_sha256", "source"}
        assert len(v["message_sha256"]) == 64


def test_item_unknown_kind_fails_closed() -> None:
    from git_cg.eval.binding.message_versions import MessageVersionError, _item

    with pytest.raises(MessageVersionError, match="kind must be one of"):
        _item("draft", FINAL, "telemetry_state")


def test_item_unknown_source_fails_closed() -> None:
    from git_cg.eval.binding.message_versions import MessageVersionError, _item

    with pytest.raises(MessageVersionError, match="source must be one of"):
        _item("final_accept", FINAL, "hand_waved")


def test_item_blank_message_fails_closed() -> None:
    from git_cg.eval.binding.message_versions import MessageVersionError, _item

    with pytest.raises(MessageVersionError, match="non-empty message text"):
        _item("final_accept", "   ", "commit_editmsg")
    with pytest.raises(MessageVersionError, match="non-empty message text"):
        _item("final_accept", None, "commit_editmsg")  # type: ignore[arg-type]
