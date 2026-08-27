"""D9 compatibility hash unit tests (Issue #246 Slice 3)."""

from __future__ import annotations

import pytest

from git_cg.eval.compat import (
    COMPAT_HASH_MISMATCH_CODE,
    COMPAT_PREIMAGE_KEYS,
    CompatHashMismatchError,
    assert_compat_hash,
    compat_preimage,
    compute_compat_hash,
    recovery_hint,
)


def _base(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_pack_pin": "schema_pack_v0@" + ("a" * 64),
        "metric_catalog_pin": "metric_catalog_v0@" + ("b" * 64),
        "suite_id": "cm-eval-fixtures-core",
        "snapshot_hash": "c" * 64,
        "gold_mode": "strict",
        "network_policy": "offline_required",
        "judge_pack_pin_or_none": None,
    }
    payload.update(overrides)
    return payload


def test_preimage_key_order_and_none_token() -> None:
    pre = compat_preimage(**_base())  # type: ignore[arg-type]
    assert list(pre.keys()) == list(COMPAT_PREIMAGE_KEYS)
    assert pre["judge_pack_pin_or_none"] == "none"


def test_hash_stable_and_sensitive() -> None:
    h1 = compute_compat_hash(**_base())  # type: ignore[arg-type]
    h2 = compute_compat_hash(**_base())  # type: ignore[arg-type]
    assert h1 == h2
    assert len(h1) == 64
    h3 = compute_compat_hash(**_base(gold_mode="lenient"))  # type: ignore[arg-type]
    assert h3 != h1
    h4 = compute_compat_hash(**_base(judge_pack_pin_or_none="judge_pack_v0@" + ("d" * 64)))  # type: ignore[arg-type]
    assert h4 != h1


def test_assert_mismatch_terminal_and_recovery() -> None:
    with pytest.raises(CompatHashMismatchError) as ei:
        assert_compat_hash("a" * 64, "b" * 64, checkpoint_id="ckpt-1")
    err = ei.value
    assert err.code == COMPAT_HASH_MISMATCH_CODE
    assert "ckpt-1" in err.recovery_hint()
    assert "fresh_suite_run" in recovery_hint(checkpoint_id="ckpt-1")
    assert_compat_hash("A" * 64, "a" * 64)  # case-insensitive match
