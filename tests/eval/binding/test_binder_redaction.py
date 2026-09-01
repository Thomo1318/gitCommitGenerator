"""Acceptpath bind redaction boundary and invalid UTF-8 ancillary fields.

Draft and score-card evidence are secret-safe; final accepted bytes remain
exact. Invalid UTF-8 records lossless base64 under meta only.

Refs: #257.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from git_cg.eval.binding.binder import BindInput, bind_final_accept, message_sha256_bytes
from git_cg.eval.corpus.canonical import message_sha256
from git_cg.eval.schema_pack import validate_instance

FINAL = (
    "✨ feat(eval): redaction boundary\n\n"
    "Refs: #257\n"
    "SemVer-Impact: PATCH\n"
    "Change-Types: fix\n"
    "Changelog-Groups: Fixed\n"
)

# Secret-shaped fixtures (offline detectors in evidence_scrub).
SK_TOKEN = "sk-abcdefghijklmnopqrstuvwxyz012345"
JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ.somesignaturevaluehere000"


@pytest.fixture(autouse=True)
def _capture_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CG_EVAL_CAPTURE", "on")
    monkeypatch.delenv("GIT_CG_EVAL_PROFILE", raising=False)


def _bind(tmp_path: Path, **overrides):
    kwargs = {
        "final_message": FINAL,
        "accept_event_token": "ae_redact",
    }
    kwargs.update(overrides)
    return bind_final_accept(BindInput(**kwargs), repo_root=tmp_path, write=True)


def test_secret_in_draft_field_redacted(tmp_path: Path) -> None:
    draft = f"draft with secret {SK_TOKEN} inside\n"
    result = _bind(tmp_path, generated_message=draft)
    assert result.bound is True
    stored = result.bundle["meta"].get("generated_message")
    assert stored is not None
    assert SK_TOKEN not in stored
    assert "•••" in stored or "len=" in stored


def test_secret_in_card_field_redacted(tmp_path: Path) -> None:
    card = {"total": 1, "note": f"token={SK_TOKEN}", "api_key": "should-drop"}
    result = _bind(tmp_path, score_card=card)
    assert result.bound is True
    stored = result.bundle["meta"]["score_card"]
    assert "api_key" not in stored
    assert SK_TOKEN not in json_dump(stored)
    assert stored.get("total") == 1


def test_jwt_in_draft_field_redacted(tmp_path: Path) -> None:
    draft = f"Authorization bearer {JWT}\n"
    result = _bind(tmp_path, generated_message=draft)
    stored = result.bundle["meta"]["generated_message"]
    assert JWT not in stored
    assert "eyJ" not in stored or "•••" in stored


def test_final_message_not_scrubbed(tmp_path: Path) -> None:
    # Even if final text contains a secret-shaped token, scored artifact is exact.
    final = FINAL.replace("redaction boundary", f"keep {SK_TOKEN} exact")
    result = _bind(tmp_path, final_message=final, generated_message=f"draft {SK_TOKEN}")
    assert result.bundle["final_message"] == final
    assert SK_TOKEN in result.bundle["final_message"]


def test_final_message_sha256_matches_exact_bytes(tmp_path: Path) -> None:
    raw = FINAL.encode("utf-8")
    result = _bind(tmp_path, final_message=raw)
    assert result.bundle["final_message_sha256"] == message_sha256_bytes(raw)
    assert result.bundle["final_message_sha256"] == message_sha256(FINAL)


def test_invalid_utf8_final_message_b64_ancillary(tmp_path: Path) -> None:
    raw = b"\xff\xfe invalid \x80 bytes\n"
    result = _bind(tmp_path, final_message=raw)
    meta = result.bundle["meta"]
    assert meta["final_message_encoding"] == "utf-8-replace"
    assert meta["final_message_byte_length"] == len(raw)
    assert "final_message_b64" in meta
    assert base64.b64decode(meta["final_message_b64"]) == raw
    # Hash authority remains original bytes, not b64/text projection.
    assert result.bundle["final_message_sha256"] == message_sha256_bytes(raw)
    validate_instance("ape_bundle_v1", result.bundle)


def test_valid_utf8_no_b64_field(tmp_path: Path) -> None:
    result = _bind(tmp_path, final_message=FINAL.encode("utf-8"))
    assert "final_message_b64" not in result.bundle["meta"]
    assert "final_message_encoding" not in result.bundle["meta"]


def test_b64_round_trip_lossless(tmp_path: Path) -> None:
    raw = bytes(range(256))  # includes invalid UTF-8 sequences
    result = _bind(tmp_path, final_message=raw)
    b64 = result.bundle["meta"]["final_message_b64"]
    assert base64.b64decode(b64) == raw
    assert result.bundle["final_message_sha256"] == message_sha256_bytes(raw)


def test_encoding_field_preserved(tmp_path: Path) -> None:
    raw = b"\x80 nope"
    result = _bind(tmp_path, final_message=raw)
    assert result.bundle["meta"]["final_message_encoding"] == "utf-8-replace"


def test_byte_length_field_preserved(tmp_path: Path) -> None:
    raw = b"\xff\xfe\xfd"
    result = _bind(tmp_path, final_message=raw)
    assert result.bundle["meta"]["final_message_byte_length"] == 3


def json_dump(value) -> str:
    import json

    return json.dumps(value)
