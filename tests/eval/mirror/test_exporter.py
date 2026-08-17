"""S4b export orchestration: queue drain, classification, F4 fail-open."""

from __future__ import annotations

from pathlib import Path

import pytest

from git_cg.eval.mirror.batch import build_export_batches
from git_cg.eval.mirror.exporter import DrainSummary, drain_queue, list_pending_items
from git_cg.eval.mirror.queue import enqueue_export_batch, load_queue_item
from git_cg.eval.mirror.secrets import OpikRuntimeSecrets
from git_cg.eval.mirror.transport import ExportTransportError, MockTransport

SECRETS = OpikRuntimeSecrets(api_key="k", workspace="w", base_url=None)
CONFIG = {
    "schema_version": "git_cg_opik_config_v1",
    "id": "git_cg_opik_config_v1",
    "mode": "mirror",
    "redaction_profile": "default_scrub",
    "flush_timeout_ms": 5000,
    "project_name": "eval-project",
}


def _enqueue(repo: Path, item_id: str, payload: dict) -> str:
    """Build + enqueue a batch; return its queue_id."""
    batches = build_export_batches([(item_id, payload)], "default_scrub")
    path = enqueue_export_batch(batches[0], repo_root=repo)
    return path.stem


class TestListPendingItems:
    def test_empty_queue(self, tmp_path: Path) -> None:
        assert list_pending_items(repo_root=tmp_path) == []

    def test_lists_pending_only(self, tmp_path: Path) -> None:
        qid = _enqueue(tmp_path, "item_1", {"x": 1})
        pending = list_pending_items(repo_root=tmp_path)
        assert len(pending) == 1
        assert pending[0]["queue_id"] == qid
        assert pending[0]["status"] == "pending"


class TestDrainQueue:
    def test_empty_queue_returns_note(self, tmp_path: Path) -> None:
        summary = drain_queue(CONFIG, transport=MockTransport(), repo_root=tmp_path, secrets=SECRETS)
        assert summary.attempted == 0
        assert "queue_empty" in summary.notes

    def test_successful_export_marks_sent(self, tmp_path: Path) -> None:
        qid = _enqueue(tmp_path, "item_1", {"x": 1})
        transport = MockTransport()
        summary = drain_queue(CONFIG, transport=transport, repo_root=tmp_path, secrets=SECRETS)
        assert summary.exported == 1
        assert summary.failed == 0
        assert load_queue_item(qid, repo_root=tmp_path)["status"] == "sent"
        assert transport.calls[0]["project"] == "eval-project"

    def test_transport_failure_marks_failed_and_classifies(self, tmp_path: Path) -> None:
        qid = _enqueue(tmp_path, "item_1", {"x": 1})
        transport = MockTransport(fail_with=ExportTransportError("export_network", "boom"))
        summary = drain_queue(CONFIG, transport=transport, repo_root=tmp_path, secrets=SECRETS)
        assert summary.failed == 1
        assert summary.exported == 0
        assert "export_network" in summary.error_classes
        row = load_queue_item(qid, repo_root=tmp_path)
        assert row["status"] == "failed"
        assert "export_network" in row.get("notes", "")

    def test_unexpected_exception_never_propagates(self, tmp_path: Path) -> None:
        class BadTransport:
            def upload(self, **kwargs):  # type: ignore[no-untyped-def]
                raise RuntimeError("totally unexpected")

        qid = _enqueue(tmp_path, "item_1", {"x": 1})
        # Must not raise (F4).
        summary = drain_queue(CONFIG, transport=BadTransport(), repo_root=tmp_path, secrets=SECRETS)  # type: ignore[arg-type]
        assert summary.failed == 1
        assert "export_network" in summary.error_classes
        assert load_queue_item(qid, repo_root=tmp_path)["status"] == "failed"

    def test_secret_resolution_failure_marks_all_failed(self, tmp_path: Path) -> None:
        _enqueue(tmp_path, "item_1", {"x": 1})
        _enqueue(tmp_path, "item_2", {"y": 2})

        class NoSecrets:
            def upload(self, **kwargs):  # type: ignore[no-untyped-def]
                raise AssertionError("should not be called")

        # Force secret resolution to fail by monkeypatching resolve.
        import git_cg.eval.mirror.exporter as exporter_mod

        def boom(*, require_key: bool = True):  # type: ignore[no-untyped-def]
            from git_cg.eval.mirror.secrets import MirrorSecretError

            raise MirrorSecretError("no key")

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(exporter_mod, "resolve_opik_secrets", boom)
        try:
            summary = drain_queue(CONFIG, transport=NoSecrets(), repo_root=tmp_path)  # type: ignore[arg-type]
        finally:
            monkeypatch.undo()

        assert summary.failed == 2
        assert "export_auth" in summary.error_classes
        assert "secret_resolution_failed" in summary.notes

    def test_max_items_caps_drain(self, tmp_path: Path) -> None:
        _enqueue(tmp_path, "item_1", {"x": 1})
        _enqueue(tmp_path, "item_2", {"y": 2})
        _enqueue(tmp_path, "item_3", {"z": 3})
        transport = MockTransport()
        summary = drain_queue(CONFIG, transport=transport, repo_root=tmp_path, secrets=SECRETS, max_items=2)
        assert summary.attempted == 2
        assert len(transport.calls) == 2
        # One row remains pending.
        assert len(list_pending_items(repo_root=tmp_path)) == 1

    def test_mixed_outcomes(self, tmp_path: Path) -> None:
        _enqueue(tmp_path, "ok", {"x": 1})
        _enqueue(tmp_path, "bad", {"y": 2})

        class FlakyTransport:
            def __init__(self) -> None:
                self.n = 0

            def upload(self, **kwargs):  # type: ignore[no-untyped-def]
                self.n += 1
                if self.n == 2:
                    raise ExportTransportError("export_validation", "bad payload")

        summary = drain_queue(CONFIG, transport=FlakyTransport(), repo_root=tmp_path, secrets=SECRETS)  # type: ignore[arg-type]
        assert summary.attempted == 2
        assert summary.exported == 1
        assert summary.failed == 1
        assert "export_validation" in summary.error_classes

    def test_summary_is_never_product_blocking(self, tmp_path: Path) -> None:
        # Even total failure returns a DrainSummary, never raises.
        _enqueue(tmp_path, "item_1", {"x": 1})
        transport = MockTransport(fail_with=ExportTransportError("export_auth", "denied"))
        summary = drain_queue(CONFIG, transport=transport, repo_root=tmp_path, secrets=SECRETS)
        assert isinstance(summary, DrainSummary)


class TestResolveSecretsModeGate:
    """HYGIENE-1 / P0-1b — key requirement by resolved mode (Slice 0 stop-bleed)."""

    def test_key_optional_for_off_and_local_tokens(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import git_cg.eval.mirror.exporter as exporter_mod

        seen: list[bool] = []

        def capture(*, require_key: bool = True):  # type: ignore[no-untyped-def]
            seen.append(require_key)
            return OpikRuntimeSecrets(api_key="", workspace=None, base_url=None)

        monkeypatch.setattr(exporter_mod, "resolve_opik_secrets", capture)
        for mode in ("off", "local", "local_only"):
            seen.clear()
            exporter_mod._resolve_secrets({**CONFIG, "mode": mode})
            assert seen == [False], mode

    def test_key_required_for_network_modes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import git_cg.eval.mirror.exporter as exporter_mod

        seen: list[bool] = []

        def capture(*, require_key: bool = True):  # type: ignore[no-untyped-def]
            seen.append(require_key)
            return SECRETS

        monkeypatch.setattr(exporter_mod, "resolve_opik_secrets", capture)
        for mode in ("mirror", "dogfood", "strict_mirror"):
            seen.clear()
            exporter_mod._resolve_secrets({**CONFIG, "mode": mode})
            assert seen == [True], mode

    def test_invented_key_bypass_token_still_requires_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import git_cg.eval.mirror.exporter as exporter_mod

        seen: list[bool] = []

        def capture(*, require_key: bool = True):  # type: ignore[no-untyped-def]
            seen.append(require_key)
            return SECRETS

        monkeypatch.setattr(exporter_mod, "resolve_opik_secrets", capture)
        # Former non-vocabulary bypass must NOT be key-optional.
        exporter_mod._resolve_secrets({**CONFIG, "mode": "self_hosted_noauth"})
        assert seen == [True]
