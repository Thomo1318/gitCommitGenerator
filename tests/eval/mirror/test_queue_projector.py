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


def test_projection_payload_is_idempotent(repo: Path) -> None:
    from git_cg.eval.mirror.queue_projector import _projection_payload
    from git_cg.eval.review_queue import show_review

    rid = enqueue(repo, case_id="case-live-idem", reviewer="rev-idem")["item"]["review_id"]
    raw = show_review(repo, review_id=rid)["item"]
    once = _projection_payload(raw)
    twice = _projection_payload(once)
    assert twice["case_id"] == once["case_id"] == "case-live-idem"
    assert twice["review_id"] == once["review_id"] == rid
    assert twice["authority"] in {"advisory", once["authority"]}
    assert twice["read_back"] is False


def test_projection_payload_bounds_and_drops_non_scalars() -> None:
    from git_cg.eval.mirror.queue_projector import _projection_payload

    payload = _projection_payload(
        {
            "review_id": "r1",
            "status": "open",
            "review": {
                "case_id": "c" * 200,
                "bundle_id": {"nested": True},
                "authority": "advisory",
            },
            "adjudication": {"outcome": "accept"},
        }
    )
    assert payload["case_id"] is not None and len(payload["case_id"]) == 128
    assert payload["bundle_id"] is None
    assert payload["outcome"] == "accept"


def test_resolve_mode_and_offline_status_matrix() -> None:
    from git_cg.eval.mirror.queue_projector import _offline_status, _resolve_mode

    assert _resolve_mode(None) == "off"
    assert _resolve_mode("x") == "off"  # type: ignore[arg-type]
    assert _resolve_mode({}) == "off"
    assert _resolve_mode({"mode": None}) == "off"
    assert _resolve_mode({"mode": "LOCAL"}) == "local_only"
    assert _resolve_mode({"mode": "local_only"}) == "local_only"
    assert _resolve_mode({"mode": "mirror"}) == "mirror"
    assert _resolve_mode({"mode": "strict_mirror"}) == "strict_mirror"
    assert _resolve_mode({"mode": "weird"}) == "off"

    assert _offline_status({"mode": "off"}) == "skipped_off"
    assert _offline_status({"mode": "local"}) == "skipped_off"
    assert _offline_status({"mode": "mirror"}) == "noop_unconfigured"
    assert _offline_status({"mode": "mirror", "projects": {"eval": "p"}}) == "noop_unreachable"
    assert _offline_status(None) == "skipped_off"


def test_has_project_lane_and_eval_project() -> None:
    from git_cg.eval.mirror.queue_projector import _eval_project, _has_project_lane

    assert _has_project_lane({}) is False
    assert _has_project_lane({"projects": "bad"}) is False
    assert _has_project_lane({"projects": {"eval": "  "}}) is False
    assert _has_project_lane({"projects": {"ci": "ci-p"}}) is True
    assert _has_project_lane({"project_name": "legacy"}) is True
    assert _has_project_lane({"project_name": "  "}) is False

    assert _eval_project({}) is None
    assert _eval_project({"projects": {"live": "  live-p "}}) == "live-p"
    assert _eval_project({"projects": {"eval": "", "import": "imp"}}) == "imp"
    assert _eval_project({"project_name": "  leg "}) == "leg"
    assert _eval_project({"project_name": ""}) is None


def test_live_enabled_flag_variants() -> None:
    from git_cg.eval.mirror.queue_projector import _live_enabled

    assert _live_enabled(None, enable_live=True) is True
    assert _live_enabled(None, enable_live=False) is False
    assert _live_enabled({"queue_mirror_live": True}, enable_live=False) is True
    assert _live_enabled({"queue_mirror_live": False}, enable_live=False) is False
    for token in ("1", "true", "YES", "on", " On "):
        assert _live_enabled({"queue_mirror_live": token}, enable_live=False) is True
    assert _live_enabled({"queue_mirror_live": "nope"}, enable_live=False) is False
    assert _live_enabled({"queue_mirror_live": 1}, enable_live=False) is False


def test_review_item_normalization() -> None:
    from git_cg.eval.mirror.queue_projector import _review_item

    assert _review_item({}) is None
    nested = _review_item({"item": {"review_id": "r1"}})
    assert nested == {"review_id": "r1"}
    top = _review_item({"review_id": "r2", "status": "open"})
    assert top is not None and top["review_id"] == "r2"
    via_review = _review_item({"review": {"x": 1}})
    assert via_review is not None


def test_scalar_meta_coercion_matrix() -> None:
    from git_cg.eval.mirror.queue_projector import _scalar_meta

    assert _scalar_meta(None) is None
    assert _scalar_meta(True) == "true"
    assert _scalar_meta(False) == "false"
    assert _scalar_meta(12) == "12"
    assert _scalar_meta(1.5) == "1.5"
    assert _scalar_meta("  hi  ") == "hi"
    assert _scalar_meta("   ") is None
    assert _scalar_meta("") is None
    assert _scalar_meta({"a": 1}) is None
    assert _scalar_meta([1, 2]) is None
    assert len(_scalar_meta("x" * 200) or "") == 128
    assert _scalar_meta("abc", max_len=2) == "ab"


def test_projection_payload_top_level_and_nested_precedence() -> None:
    from git_cg.eval.mirror.queue_projector import _projection_payload

    top = _projection_payload(
        {
            "review_id": "r-top",
            "status": "open",
            "case_id": "c1",
            "bundle_id": "b1",
            "outcome": "accept",
            "updated_at": "t1",
            "created_at": "t0",
        }
    )
    assert top["review_id"] == "r-top"
    assert top["status"] == "open"
    assert top["case_id"] == "c1"
    assert top["updated_at"] == "t1"
    assert top["authority"] == "advisory"
    assert top["mirror_authority"] == QUEUE_MIRROR_AUTHORITY
    assert top["read_back"] is False

    nested = _projection_payload(
        {
            "review_id": "top-id",
            "review": {"review_id": "rev-id", "status": "reviewed", "authority": "human"},
            "adjudication": {"status": "adj-status", "outcome": "reject", "created_at": "ca"},
        }
    )
    assert nested["review_id"] == "rev-id"
    assert nested["status"] == "reviewed"
    assert nested["authority"] == "human"
    assert nested["outcome"] == "reject"
    assert nested["updated_at"] == "ca"

    alias = _projection_payload({"id": "alias-id"})
    assert alias["review_id"] == "alias-id"


def test_load_local_items_paths(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.eval.review_queue as rq
    from git_cg.eval.mirror import queue_projector as qp
    from git_cg.eval.review_queue import ReviewQueueError, enqueue

    assert qp._load_local_items(None, review_ids=["x"]) == []

    rid = enqueue(repo, case_id="case-load-1", reviewer="rev")["item"]["review_id"]
    items = qp._load_local_items(repo, review_ids=[rid, "missing-id"])
    assert len(items) == 1
    assert items[0]["review_id"] == rid

    listed = qp._load_local_items(repo, review_ids=None)
    assert any(i.get("review_id") == rid for i in listed)

    def boom_show(repo_arg, *, review_id: str):
        raise ReviewQueueError("missing", code="not_found", exit_code=2)

    monkeypatch.setattr(rq, "show_review", boom_show)
    assert qp._load_local_items(repo, review_ids=[rid]) == []

    monkeypatch.setattr(rq, "list_reviews", lambda _repo: {"reviews": "bad"})
    assert qp._load_local_items(repo, review_ids=None) == []

    monkeypatch.setattr(
        rq,
        "list_reviews",
        lambda _repo: {
            "reviews": [
                None,
                "x",
                {"review_id": ""},
                {"review_id": 1},
                {"no_id": True},
                {"review_id": rid},
            ]
        },
    )
    assert qp._load_local_items(repo, review_ids=None) == []

    def ok_show(repo_arg, *, review_id: str):
        if review_id == "nested":
            return {"item": {"review_id": "nested", "status": "open"}}
        if review_id == "top":
            return {"review_id": "top", "status": "open"}
        if review_id == "skip-shape":
            return {"unrelated": True}
        raise ReviewQueueError("missing", code="not_found", exit_code=2)

    monkeypatch.setattr(
        rq,
        "list_reviews",
        lambda _repo: {
            "reviews": [
                {"review_id": "nested"},
                {"review_id": "top"},
                {"review_id": "skip-shape"},
                {"review_id": "missing"},
            ]
        },
    )
    monkeypatch.setattr(rq, "show_review", ok_show)
    loaded = qp._load_local_items(repo, review_ids=None)
    assert {i["review_id"] for i in loaded} == {"nested", "top"}

    monkeypatch.setattr(rq, "show_review", ok_show)
    explicit = qp._load_local_items(repo, review_ids=["nested", "skip-shape", "missing"])
    assert [i["review_id"] for i in explicit] == ["nested"]


def test_project_live_offline_and_unconfigured_branches(repo: Path) -> None:
    off = project_review_queue_live(repo, config={"mode": "off"}, enable_live=True)
    assert off.status == "skipped_off"

    unconf = project_review_queue_live(
        repo,
        config={"mode": "mirror"},
        enable_live=True,
        review_ids=["r1"],
    )
    assert unconf.status == "noop_unconfigured"

    disabled = project_review_queue_live(
        repo,
        config={"mode": "mirror", "projects": {"eval": "p"}},
        enable_live=False,
    )
    assert disabled.status == "noop_unreachable"
    assert "not enabled" in disabled.notes[0]

    bad_cfg = project_review_queue_live(
        repo,
        config=None,  # offline status skipped_off first
        enable_live=True,
    )
    assert bad_cfg.status == "skipped_off"


def test_project_live_empty_queue_and_factory_failure(repo: Path) -> None:
    empty = project_review_queue_live(
        repo,
        config={"mode": "mirror", "projects": {"eval": "p"}},
        review_ids=["does-not-exist"],
        enable_live=True,
        projector=_Recorder(),
    )
    assert empty.status == "projected"
    assert empty.attempted == 0
    assert empty.projected == 0

    def boom_factory():
        raise RuntimeError("factory token=factory-secret")

    rid = enqueue(repo, case_id="case-factory", reviewer="r")["item"]["review_id"]
    failed = project_review_queue_live(
        repo,
        config={"mode": "mirror", "projects": {"eval": "p"}},
        review_ids=[rid],
        enable_live=True,
        projector_factory=boom_factory,
    )
    assert failed.status == "noop_unreachable"
    assert "factory-secret" not in str(failed.to_dict())


def test_project_live_zero_projected_treated_unreachable(repo: Path) -> None:
    rid = enqueue(repo, case_id="case-zero", reviewer="r")["item"]["review_id"]

    class _Zero:
        def project_items(self, items, *, project: str) -> int:
            return 0

    result = project_review_queue_live(
        repo,
        config={"mode": "mirror", "projects": {"eval": "p"}},
        review_ids=[rid],
        enable_live=True,
        projector=_Zero(),
    )
    assert result.status == "noop_unreachable"
    assert result.projected == 0
    assert result.skipped == 1


def test_project_live_clamps_over_report(repo: Path) -> None:
    rid = enqueue(repo, case_id="case-clamp", reviewer="r")["item"]["review_id"]

    class _Over:
        def project_items(self, items, *, project: str) -> int:
            return 99

    result = project_review_queue_live(
        repo,
        config={"mode": "mirror", "projects": {"eval": "p"}},
        review_ids=[rid],
        enable_live=True,
        projector=_Over(),
    )
    assert result.status == "projected"
    assert result.projected == 1
    assert result.skipped == 0


def test_project_live_config_string_flag(repo: Path) -> None:
    rid = enqueue(repo, case_id="case-flag", reviewer="r")["item"]["review_id"]
    recorder = _Recorder()
    result = project_review_queue_live(
        repo,
        config={
            "mode": "mirror",
            "projects": {"eval": "p"},
            "queue_mirror_live": "yes",
        },
        review_ids=[rid],
        enable_live=False,
        projector=recorder,
    )
    assert result.status == "projected"
    assert recorder.calls


def test_project_live_legacy_project_name(repo: Path) -> None:
    rid = enqueue(repo, case_id="case-legacy", reviewer="r")["item"]["review_id"]
    recorder = _Recorder()
    result = project_review_queue_live(
        repo,
        config={"mode": "mirror", "project_name": "legacy-proj"},
        review_ids=[rid],
        enable_live=True,
        projector=recorder,
    )
    assert result.status == "projected"
    assert recorder.calls[0][0] == "legacy-proj"


def test_default_live_projector_rejects_spoofed_localhost_http(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTP hosts that merely contain 'localhost' must not bypass the HTTPS guard."""
    import git_cg.eval.mirror.queue_projector as qp
    from git_cg.eval.mirror.secrets import OpikRuntimeSecrets

    monkeypatch.setattr(
        "git_cg.eval.mirror.secrets.resolve_opik_secrets",
        lambda require_key=True: OpikRuntimeSecrets(
            api_key="secret-key",
            workspace="ws",
            base_url="http://localhost.attacker.example/opik",
        ),
    )
    with pytest.raises(RuntimeError, match="refusing non-HTTPS"):
        qp._default_live_projector_factory()


def test_default_live_projector_factory_https_guard_and_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    import git_cg.eval.mirror.queue_projector as qp
    from git_cg.eval.mirror.secrets import OpikRuntimeSecrets

    monkeypatch.setattr(
        "git_cg.eval.mirror.secrets.resolve_opik_secrets",
        lambda require_key=True: OpikRuntimeSecrets(
            api_key="secret-key",
            workspace="ws",
            base_url="http://remote.example/opik",
        ),
    )
    with pytest.raises(RuntimeError, match="refusing non-HTTPS"):
        qp._default_live_projector_factory()

    traces: list[dict[str, Any]] = []

    class _Client:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.flushed = False

        def trace(self, **kwargs):
            if kwargs.get("name", "").endswith("boom"):
                raise RuntimeError("trace failed")
            traces.append(kwargs)

        def flush(self, timeout: int = 2) -> None:
            self.flushed = True
            if timeout < 0:
                raise RuntimeError("flush fail")

    fake_opik = types.ModuleType("opik")
    fake_opik.Opik = _Client
    monkeypatch.setitem(sys.modules, "opik", fake_opik)
    monkeypatch.setattr(
        "git_cg.eval.mirror.secrets.resolve_opik_secrets",
        lambda require_key=True: OpikRuntimeSecrets(
            api_key="secret-key",
            workspace="ws",
            base_url="http://localhost:5173",
        ),
    )

    projector = qp._default_live_projector_factory()
    count = projector.project_items(
        [
            {
                "review_id": "r-norm",
                "status": "open",
                "mirror_authority": "stale",
                "read_back": True,
                "case_id": "c",
                "extra": "drop-me",
                "bundle_id": {"nested": True},
            },
            {
                "review": {"review_id": "r-raw", "status": "open", "case_id": "c2"},
                "adjudication": {"outcome": "accept"},
            },
            {
                "review_id": "boom",
                "status": "open",
                "mirror_authority": QUEUE_MIRROR_AUTHORITY,
            },
        ],
        project="proj",
    )
    assert count == 2
    assert len(traces) == 2
    meta0 = traces[0]["metadata"]
    assert meta0["mirror_authority"] == QUEUE_MIRROR_AUTHORITY
    assert meta0["read_back"] is False
    assert "extra" not in meta0
    assert meta0.get("bundle_id") is None


def test_default_live_projector_flush_failure_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    import git_cg.eval.mirror.queue_projector as qp
    from git_cg.eval.mirror.secrets import OpikRuntimeSecrets

    class _Client:
        def __init__(self, **kwargs):
            pass

        def trace(self, **kwargs):
            return None

        def flush(self, timeout: int = 2):
            raise RuntimeError("flush broken")

    fake_opik = types.ModuleType("opik")
    fake_opik.Opik = _Client
    monkeypatch.setitem(sys.modules, "opik", fake_opik)
    monkeypatch.setattr(
        "git_cg.eval.mirror.secrets.resolve_opik_secrets",
        lambda require_key=True: OpikRuntimeSecrets(
            api_key="",
            workspace=None,
            base_url="https://example.test",
        ),
    )
    projector = qp._default_live_projector_factory()
    assert projector.project_items([{"review_id": "r1", "mirror_authority": "x"}], project="p") == 1


def test_default_live_projector_allows_loopback_http(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    import git_cg.eval.mirror.queue_projector as qp
    from git_cg.eval.mirror.secrets import OpikRuntimeSecrets

    class _Client:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def trace(self, **kwargs):
            return None

    fake_opik = types.ModuleType("opik")
    fake_opik.Opik = _Client
    monkeypatch.setitem(sys.modules, "opik", fake_opik)
    monkeypatch.setattr(
        "git_cg.eval.mirror.secrets.resolve_opik_secrets",
        lambda require_key=True: OpikRuntimeSecrets(
            api_key="k",
            workspace="ws",
            base_url="http://127.0.0.1:5173",
        ),
    )
    projector = qp._default_live_projector_factory()
    assert projector.project_items([], project="p") == 0


def test_project_live_no_project_after_live_enabled(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.eval.mirror.queue_projector as qp

    monkeypatch.setattr(qp, "_offline_status", lambda _cfg: "noop_unreachable")
    monkeypatch.setattr(qp, "_live_enabled", lambda _cfg, enable_live=False: True)
    monkeypatch.setattr(qp, "_eval_project", lambda _cfg: None)

    result = project_review_queue_live(
        repo,
        config={"mode": "mirror", "projects": {"eval": "p"}},
        enable_live=True,
    )
    assert result.status == "noop_unconfigured"


def test_project_live_non_mapping_config_after_live(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.eval.mirror.queue_projector as qp

    monkeypatch.setattr(qp, "_offline_status", lambda _cfg: "noop_unreachable")
    monkeypatch.setattr(qp, "_live_enabled", lambda _cfg, enable_live=False: True)

    result = project_review_queue_live(
        repo,
        config="not-a-mapping",  # type: ignore[arg-type]
        enable_live=True,
    )
    assert result.status == "noop_unconfigured"
