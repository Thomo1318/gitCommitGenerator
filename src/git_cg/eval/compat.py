"""D9 compatibility hash for S6 suite resume (Issue #246 Slice 3).

Preimage (canonical JSON object, sorted keys → SHA-256 hex):

* ``schema_pack_pin``
* ``metric_catalog_pin``
* ``suite_id``
* ``snapshot_hash``
* ``gold_mode``
* ``network_policy``
* ``judge_pack_pin_or_none``  (missing/empty → canonical ``"none"``)

Mismatch is terminal: never silent-merge, never rewrite a checkpoint's hash.
Recovery is ``fresh_suite_run`` or ``recompute_scores`` over retained evidence.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, Final

__all__ = [
    "COMPAT_HASH_MISMATCH_CODE",
    "COMPAT_PREIMAGE_KEYS",
    "CompatHashMismatchError",
    "assert_compat_hash",
    "compat_preimage",
    "compute_compat_hash",
    "recovery_hint",
]

COMPAT_HASH_MISMATCH_CODE: Final[str] = "EVAL_COMPAT_HASH_MISMATCH"

COMPAT_PREIMAGE_KEYS: Final[tuple[str, ...]] = (
    "schema_pack_pin",
    "metric_catalog_pin",
    "suite_id",
    "snapshot_hash",
    "gold_mode",
    "network_policy",
    "judge_pack_pin_or_none",
)

_NONE_TOKEN: Final[str] = "none"


class CompatHashMismatchError(ValueError):
    """Terminal resume failure: checkpoint compat_hash diverges from live preimage."""

    code: str = COMPAT_HASH_MISMATCH_CODE

    def __init__(
        self,
        message: str,
        *,
        expected: str,
        actual: str,
        checkpoint_id: str | None = None,
    ) -> None:
        """Capture expected/actual compat hashes for resume recovery."""
        self.expected = expected
        self.actual = actual
        self.checkpoint_id = checkpoint_id
        super().__init__(message)

    def recovery_hint(self) -> str:
        """Operator recovery hint when a checkpoint compat hash mismatches."""
        return recovery_hint(checkpoint_id=self.checkpoint_id)


def recovery_hint(*, checkpoint_id: str | None = None) -> str:
    """Operator recovery path printed on ``EVAL_COMPAT_HASH_MISMATCH``."""
    ckpt = f" checkpoint_id={checkpoint_id}" if checkpoint_id else ""
    return (
        f"Checkpoint preserved read-only{ckpt}. "
        "Do not migrate or rewrite the checkpoint. "
        "Recover with `git-cg eval run` (fresh_suite_run) or "
        "`git-cg eval recompute-scores` over the retained evidence bundle."
    )


def _as_token(value: Any, *, field: str) -> str:
    """Normalize a pin/token string for exact compat comparisons."""
    if value is None:
        if field == "judge_pack_pin_or_none":
            return _NONE_TOKEN
        raise ValueError(f"compat preimage field {field!r} is required")
    text = str(value).strip()
    if not text:
        if field == "judge_pack_pin_or_none":
            return _NONE_TOKEN
        raise ValueError(f"compat preimage field {field!r} must be non-empty")
    if field == "judge_pack_pin_or_none" and text.lower() in {"none", "null", "nil"}:
        return _NONE_TOKEN
    return text


def compat_preimage(
    *,
    schema_pack_pin: str,
    metric_catalog_pin: str,
    suite_id: str,
    snapshot_hash: str,
    gold_mode: str = "strict",
    network_policy: str = "offline_required",
    judge_pack_pin_or_none: str | None = None,
) -> dict[str, str]:
    """Return the canonical D9 preimage object (insertion order = key order)."""
    raw = {
        "schema_pack_pin": schema_pack_pin,
        "metric_catalog_pin": metric_catalog_pin,
        "suite_id": suite_id,
        "snapshot_hash": snapshot_hash,
        "gold_mode": gold_mode,
        "network_policy": network_policy,
        "judge_pack_pin_or_none": judge_pack_pin_or_none,
    }
    return {key: _as_token(raw[key], field=key) for key in COMPAT_PREIMAGE_KEYS}


def compute_compat_hash(
    *,
    schema_pack_pin: str,
    metric_catalog_pin: str,
    suite_id: str,
    snapshot_hash: str,
    gold_mode: str = "strict",
    network_policy: str = "offline_required",
    judge_pack_pin_or_none: str | None = None,
    preimage: Mapping[str, Any] | None = None,
) -> str:
    """SHA-256 hex over canonical JSON of the D9 preimage."""
    if preimage is None:
        payload = compat_preimage(
            schema_pack_pin=schema_pack_pin,
            metric_catalog_pin=metric_catalog_pin,
            suite_id=suite_id,
            snapshot_hash=snapshot_hash,
            gold_mode=gold_mode,
            network_policy=network_policy,
            judge_pack_pin_or_none=judge_pack_pin_or_none,
        )
    else:
        # Re-normalize so callers cannot inject extra keys or alternate none tokens.
        payload = compat_preimage(
            schema_pack_pin=str(preimage.get("schema_pack_pin", schema_pack_pin)),
            metric_catalog_pin=str(preimage.get("metric_catalog_pin", metric_catalog_pin)),
            suite_id=str(preimage.get("suite_id", suite_id)),
            snapshot_hash=str(preimage.get("snapshot_hash", snapshot_hash)),
            gold_mode=str(preimage.get("gold_mode", gold_mode)),
            network_policy=str(preimage.get("network_policy", network_policy)),
            judge_pack_pin_or_none=preimage.get("judge_pack_pin_or_none", judge_pack_pin_or_none),  # type: ignore[arg-type]
        )
    material = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def assert_compat_hash(
    expected: str,
    actual: str,
    *,
    checkpoint_id: str | None = None,
) -> None:
    """Raise :class:`CompatHashMismatchError` when hashes diverge."""
    exp = str(expected or "").strip().lower()
    act = str(actual or "").strip().lower()
    if exp and act and exp == act:
        return
    raise CompatHashMismatchError(
        f"{COMPAT_HASH_MISMATCH_CODE}: checkpoint compat_hash diverges from live preimage",
        expected=exp,
        actual=act,
        checkpoint_id=checkpoint_id,
    )
