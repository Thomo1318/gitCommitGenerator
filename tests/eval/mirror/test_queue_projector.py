"""S7-5 NTH: optional live queue projector (write-only, fail-open)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from git_cg.eval.mirror.queue_mirror import QUEUE_MIRROR_AUTHORITY, mirror_review_queue
from git_cg.eval.mirror.queue_projector import project_review_queue_live
from git_cg.eval.review_queue import enqueue


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    return tmp_path


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[dict[str, Any]]]] = []

    def project_items(self, items, *, project: str) -> int:
        payload = [dict(item) for item in items]
        self.calls.append((project, payload))
        return len(payload)


def test_live_disabled_matches_offline_contract() -> None:
    result = project_review_queue_live(
        config={"mode": "mirror", "projects": {"eval": "git-cg-eval"}},
        enable_live=False,
    )
    assert result.status == "noop_unreachable"
    assert result.authority == QUEUE_MIRROR_AUTHORITY
    assert result.read_back is False
    assert result.product_accept_blocked is False
    assert result.projected == 0


def test_live_projection_writes_metadata_only(repo: Path) -> None:
    rid = enqueue(repo, case_id="case-live-1", reviewer="rev-1")["item"]["review_id"]
    recorder = _Recorder()
    result = project_review_queue_live(
        repo,
        config={"mode": "mirror", "projects": {"eval": "git-cg-eval"}},
        review_ids=[rid],
        enable_live=True,
        projector=recorder,
    )
    assert result.status == "projected"
    assert result.projected == 1
    assert result.attempted == 1
    assert result.read_back is False
    assert result.authority == QUEUE_MIRROR_AUTHORITY
    assert recorder.calls and recorder.calls[0][0] == "git-cg-eval"
    payload = recorder.calls[0][1][0]
    assert payload["review_id"] == rid
    assert payload["read_back"] is False
    assert "diff" not in payload
    assert "notes" not in payload


def test_mirror_review_queue_enable_live_passthrough(repo: Path) -> None:
    rid = enqueue(repo, case_id="case-live-2", reviewer="rev-2")["item"]["review_id"]
    recorder = _Recorder()
    result = mirror_review_queue(
        repo,
        config={"mode": "mirror", "projects": {"eval": "git-cg-eval"}, "queue_mirror_live": True},
        review_ids=[rid],
        projector=recorder,
    )
    assert result.status == "projected"
    assert result.projected == 1
    assert result.read_back is False
    assert recorder.calls


def test_live_failure_is_fail_open(repo: Path) -> None:
    rid = enqueue(repo, case_id="case-live-3", reviewer="rev-3")["item"]["review_id"]

    class _Boom:
        def project_items(self, items, *, project: str) -> int:
            raise RuntimeError("network down token=super-secret")

    result = project_review_queue_live(
        repo,
        config={"mode": "mirror", "projects": {"eval": "p"}},
        review_ids=[rid],
        enable_live=True,
        projector=_Boom(),
    )
    assert result.status == "noop_unreachable"
    assert result.product_accept_blocked is False
    assert result.read_back is False
    assert result.projected == 0
    blob = str(result.to_dict())
    assert "super-secret" not in blob


def test_offline_path_still_ignores_live_flag_when_mode_off(repo: Path) -> None:
    result = mirror_review_queue(
        repo,
        config={"mode": "off", "queue_mirror_live": True, "projects": {"eval": "p"}},
        enable_live=True,
    )
    assert result.status == "skipped_off"
    assert result.projected == 0
