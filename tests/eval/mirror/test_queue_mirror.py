"""S7-E: optional cloud review-queue mirror — offline no-op + never-read-back."""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import pytest

from git_cg.eval.mirror import queue_mirror
from git_cg.eval.mirror.queue_mirror import (
    QUEUE_MIRROR_AUTHORITY,
    QueueMirrorResult,
    mirror_review_queue,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src" / "git_cg"

# Authority consumers that must never import the cloud queue mirror (S7-E).
_NEVER_READ_BACK_SOURCES = (
    SRC_ROOT / "eval" / "promote.py",
    SRC_ROOT / "eval" / "doctor.py",
    SRC_ROOT / "eval" / "scoring" / "gates.py",
    SRC_ROOT / "eval" / "review_queue.py",
)

_FORBIDDEN_MIRROR_TOKENS = frozenset(
    {
        "queue_mirror",
        "mirror_review_queue",
        "QueueMirrorResult",
    }
)


def _assert_non_sot(result: QueueMirrorResult) -> None:
    """Shared non-SoT / write-only invariants on every result."""
    assert result.authority == QUEUE_MIRROR_AUTHORITY
    assert result.product_accept_blocked is False
    assert result.read_back is False
    assert result.projected == 0
    view = result.to_dict()
    assert view["authority"] == QUEUE_MIRROR_AUTHORITY
    assert view["product_accept_blocked"] is False
    assert view["read_back"] is False
    assert view["projected"] == 0


def test_mirror_offline_noop() -> None:
    """Unconfigured / off / unreachable Opik → safe offline no-op."""
    bare = mirror_review_queue(repo=REPO_ROOT, config=None)
    assert bare.status == "skipped_off"
    _assert_non_sot(bare)

    off = mirror_review_queue(config={"mode": "off"})
    assert off.status == "skipped_off"
    _assert_non_sot(off)

    local_only = mirror_review_queue(config={"mode": "local_only", "projects": {"eval": "p"}})
    assert local_only.status == "skipped_off"
    _assert_non_sot(local_only)

    unconfigured = mirror_review_queue(config={"mode": "mirror"})
    assert unconfigured.status == "noop_unconfigured"
    _assert_non_sot(unconfigured)

    # Active + configured still no-ops until optional live projector lands.
    configured = mirror_review_queue(
        config={"mode": "mirror", "projects": {"eval": "git-cg-eval"}},
        review_ids=["hr-deadbeef"],
    )
    assert configured.status == "noop_unreachable"
    assert configured.attempted == 1
    assert configured.skipped == 1
    _assert_non_sot(configured)

    assert "opik" not in dir(queue_mirror)


def test_mirror_never_read_back() -> None:
    """Promote / doctor / gates / review_queue never import queue_mirror."""
    for path in _NEVER_READ_BACK_SOURCES:
        source = path.read_text(encoding="utf-8")
        for token in _FORBIDDEN_MIRROR_TOKENS:
            assert token not in source, f"{path.relative_to(REPO_ROOT)} must not reference {token!r}"

        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "queue_mirror" not in alias.name, f"import {alias.name} in {path.name}"
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert "queue_mirror" not in mod, f"from {mod} import … in {path.name}"
                for alias in node.names:
                    assert alias.name not in _FORBIDDEN_MIRROR_TOKENS, f"from {mod} import {alias.name} in {path.name}"


def test_queue_mirror_is_write_only_by_construction() -> None:
    """Public API is push-only: no fetch/list/load/read surface."""
    assert set(queue_mirror.__all__) == {
        "QUEUE_MIRROR_AUTHORITY",
        "QueueMirrorResult",
        "QueueMirrorStatus",
        "mirror_review_queue",
    }
    result = QueueMirrorResult(status="skipped_off")
    assert result.read_back is False
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.read_back = True  # type: ignore[misc]
