"""Evidence scrub breadth for promote/review free text (Issue #254).

Covers all ``_SECRET_VALUE_PATTERNS`` entries, short-segment JWTs, mask-to-empty
fallback, and the false-positive suite.
"""

from __future__ import annotations

import re

import pytest

from git_cg.eval.evidence_scrub import (
    _SECRET_VALUE_PATTERNS,
    mask_optional_operator_text,
    mask_secrets_in_text,
    project_secret_safe,
    scrub_evidence_mapping,
)


def _jwt_pattern() -> re.Pattern[str]:
    for pat in _SECRET_VALUE_PATTERNS:
        if "eyJ" in pat.pattern:
            return pat
    raise AssertionError("JWT secret pattern missing from _SECRET_VALUE_PATTERNS")


@pytest.mark.parametrize(
    ("raw", "must_keep_fragment"),
    [
        ("sk-live-H65probeTokenABCDEFGHIJKLMNOP", None),
        ("AKIAIOSFODNN7EXAMPLE", None),
        ("ghp_H65probeTokenABCDEFGHIJKLMNOPQRSTUVWXYZ12", None),
        ("github_pat_11ABCDEFGHIJKLMNOPQRSTUV_0123456789abcdef", None),
        ("xoxb-1234567890-abcdefghij", None),
        ("Bearer eyJhbGciOiJIUzI1NiJ9.aGVsbG93b3JsZA.signature1234", None),
        ("Bearer eyJhbGciOiJIUzI1NiJ9.h65probe.signature", None),
        # Pattern matches the BEGIN marker line only (existing scrub law).
        ("-----BEGIN RSA PRIVATE KEY-----", None),
        ("found -----BEGIN RSA PRIVATE KEY----- in dump", None),
        ("api_key=h65secretvalue", "api_key="),
        ("password=supersecretpassword123", "password="),
        ("token: abcdefgh12345678", "token"),
    ],
)
def test_secret_patterns_are_masked(raw: str, must_keep_fragment: str | None) -> None:
    masked = mask_secrets_in_text(raw)
    assert masked is not None
    assert masked != raw
    assert "•••" in masked
    # Assignment prefixes may remain; secret payload must not.
    if must_keep_fragment is None:
        assert raw not in masked
    else:
        assert must_keep_fragment in masked
        if "=" in raw or ":" in raw:
            secret = re.split(r"[:=]\s*", raw, maxsplit=1)[-1].strip().strip("'\"")
            assert secret not in masked


def test_short_segment_jwt_masked() -> None:
    """Short-middle-segment Bearer JWTs are masked."""
    short_jwt = "Bearer eyJhbGciOiJIUzI1NiJ9.h65probe.signature"
    full_jwt = "Bearer eyJhbGciOiJIUzI1NiJ9.aGVsbG93b3JsZA.signature1234"
    for token in (short_jwt, full_jwt):
        masked = mask_secrets_in_text(token)
        assert token not in (masked or "")
        assert "•••" in (masked or "")


def test_jwt_quantifier_pin_and_no_trailing_word_boundary() -> None:
    """JWT pin: header{5,}/payload{1,}/sig{5,}; lookarounds; no trailing \\b."""
    pat = _jwt_pattern()
    source = pat.pattern
    assert source.count(r"{5,}") >= 2
    assert r"{1,}" in source
    assert not source.rstrip().endswith(r"\b")
    assert "(?<!" in source
    assert "(?!" in source
    assert "eyJ" in source

    # Token ending in base64url non-word chars must still match.
    ending_dash = "eyJhbGciOiJIUzI1NiJ9.h65probe.signature-"
    ending_us = "eyJhbGciOiJIUzI1NiJ9.h65probe.signat_ure"
    assert pat.search(ending_dash) is not None
    assert pat.search(ending_us) is not None

    masked_dash = mask_secrets_in_text(f"token {ending_dash}")
    masked_us = mask_secrets_in_text(f"token {ending_us}")
    assert ending_dash not in (masked_dash or "")
    assert ending_us not in (masked_us or "")
    assert "•••" in (masked_dash or "")
    assert "•••" in (masked_us or "")


def test_jwt_false_positive_suite_not_masked() -> None:
    """Ordinary dotted text and non-token eyJ shapes must not be masked."""
    benign = [
        "see docs/v1.2.3 release notes",
        "package.module.function",
        "eyJabc.def.ghi",  # too-short header/signature under {5,} pin
        "version 1.0.0-rc.1",
        "plain operator note without secrets",
    ]
    for value in benign:
        assert mask_secrets_in_text(value) == value


def test_mask_to_empty_never_restores_raw(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mask-to-empty stores redacted empty — never the raw operator text."""
    import git_cg.eval.evidence_scrub as scrub

    monkeypatch.setattr(scrub, "mask_secrets_in_text", lambda _value: "")
    raw = "sk-live-H65probeTokenABCDEFGHIJKLMNOP"
    assert scrub.mask_optional_operator_text(raw) == ""


def test_notes_masked_no_raw_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mask-to-empty never falls back to raw operator notes."""
    test_mask_to_empty_never_restores_raw(monkeypatch)


def test_mask_optional_operator_text_blank_and_none() -> None:
    assert mask_optional_operator_text(None) is None
    assert mask_optional_operator_text("   ") is None
    assert mask_optional_operator_text("safe note") == "safe note"


def test_scrub_evidence_mapping_drops_secret_keys() -> None:
    payload = {
        "ok": "value",
        "api_key": "sk-should-drop",
        "nested": {"token": "drop-me", "keep": "yes"},
        "list": [{"password": "x"}, "plain"],
    }
    scrubbed = scrub_evidence_mapping(payload)
    assert scrubbed == {"ok": "value", "nested": {"keep": "yes"}, "list": [{}, "plain"]}


def test_project_secret_safe_masks_string_leaves() -> None:
    payload = {
        "note": "found sk-live-H65probeTokenABCDEFGHIJKLMNOP here",
        "api_key": "should-drop",
        "items": ["Bearer eyJhbGciOiJIUzI1NiJ9.h65probe.signature"],
    }
    projected = project_secret_safe(payload)
    assert "api_key" not in projected
    assert "sk-live-H65probeTokenABCDEFGHIJKLMNOP" not in projected["note"]
    assert "•••" in projected["note"]
    assert "eyJhbGciOiJIUzI1NiJ9.h65probe.signature" not in projected["items"][0]
    assert "•••" in projected["items"][0]


def test_secret_pattern_count_is_eight() -> None:
    assert len(_SECRET_VALUE_PATTERNS) == 8
