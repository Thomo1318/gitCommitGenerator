"""S4 export orchestration: queue drain, classification, F4 fail-open (Slice 3 durability)."""

from __future__ import annotations

from pathlib import Path

import pytest

from git_cg.eval.mirror.batch import build_export_batches
from git_cg.eval.mirror.exporter import DrainSummary, drain_queue, list_pending_items
from git_cg.eval.mirror.payload import export_payloads_dir
from git_cg.eval.mirror.queue import enqueue_export_batch, load_queue_item
from git_cg.eval.mirror.secrets import OpikRuntimeSecrets
from git_cg.eval.mirror.transport import ExportTransportError, MockTransport

SECRETS = OpikRuntimeSecrets(api_key="k", workspace="w", base_url=None)
CONFIG = {
    "schema_version": "git_cg_opik_config_v1",
    "id": "git_cg_opik_config_v1",
    "mode": "mirror",
    "environment": "eval",
    "redaction_profile": "default_scrub",
    "flush_timeout_ms": 5000,
    "track_disable": False,
    "check_tls_certificate": True,
    "projects": {
        "live": "eval-project",
        "eval": "eval-project",
        "ci": "eval-project",
        "import": "eval-project",
    },
    "project_name": "eval-project",
}


def _enqueue(repo: Path, item_id: str, payload: dict) -> str:
    """Enqueue one minimal export payload for drain tests."""
    batches = build_export_batches([(item_id, payload)], "default_scrub", project="eval-project")
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

    def test_successful_export_marks_sent_and_uploads_payload(self, tmp_path: Path) -> None:
        qid = _enqueue(tmp_path, "item_1", {"x": 1})
        transport = MockTransport()
        summary = drain_queue(CONFIG, transport=transport, repo_root=tmp_path, secrets=SECRETS)
        assert summary.exported == 1
        assert summary.failed == 0
        row = load_queue_item(qid, repo_root=tmp_path)
        assert row["status"] == "sent"
        assert row["envelope_status"] == "ok"
        assert transport.calls[0]["project"] == "eval-project"
        uploaded = transport.calls[0]["payload"]
        assert isinstance(uploaded, dict)
        assert "items" in uploaded
        assert uploaded["items"][0]["payload"] == {"x": 1}
        assert any(export_payloads_dir(tmp_path).glob("*.json"))

    def test_transport_failure_marks_failed_and_classifies(self, tmp_path: Path) -> None:
        qid = _enqueue(tmp_path, "item_1", {"x": 1})
        transport = MockTransport(fail_with=ExportTransportError("export_network", "boom"))
        summary = drain_queue(CONFIG, transport=transport, repo_root=tmp_path, secrets=SECRETS)
        assert summary.failed == 1
        assert summary.exported == 0
        assert "export_network" in summary.error_classes
        row = load_queue_item(qid, repo_root=tmp_path)
        assert row["status"] == "failed"
        assert row["last_error_class"] == "export_network"
        assert "export_network" in row.get("notes", "")

    def test_missing_payload_artifact_is_export_validation(self, tmp_path: Path) -> None:
        qid = _enqueue(tmp_path, "item_1", {"x": 1})
        row = load_queue_item(qid, repo_root=tmp_path)
        for path in export_payloads_dir(tmp_path).glob("*.json"):
            path.unlink()
        summary = drain_queue(CONFIG, transport=MockTransport(), repo_root=tmp_path, secrets=SECRETS)
        assert summary.failed == 1
        assert "export_validation" in summary.error_classes
        failed = load_queue_item(qid, repo_root=tmp_path)
        assert failed["status"] == "failed"
        assert failed["last_error_class"] == "export_validation"
        assert failed["payload_ref"] == row["payload_ref"]

    def test_unexpected_exception_never_propagates(self, tmp_path: Path) -> None:
        class BadTransport:
            def upload(self, **kwargs):  # type: ignore[no-untyped-def]
                raise RuntimeError("totally unexpected")

        qid = _enqueue(tmp_path, "item_1", {"x": 1})
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
        _enqueue(tmp_path, "item_1", {"x": 1})
        transport = MockTransport(fail_with=ExportTransportError("export_auth", "denied"))
        summary = drain_queue(CONFIG, transport=transport, repo_root=tmp_path, secrets=SECRETS)
        assert isinstance(summary, DrainSummary)


class TestResolveSecretsModeGate:
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
        exporter_mod._resolve_secrets({**CONFIG, "mode": "self_hosted_noauth"})
        assert seen == [True]


class TestTerminalMarkGuards:
    def test_terminal_mark_failure_is_fail_open_and_honest(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        qid = _enqueue(tmp_path, "item_1", {"x": 1})
        transport = MockTransport()

        import git_cg.eval.mirror.queue as queue_mod

        real_mark = queue_mod.mark_queue_item

        def flaky_mark(queue_id: str, status: str, *args, **kwargs):  # type: ignore[no-untyped-def]
            if status in {"sent", "failed"}:
                raise queue_mod.ExportQueueError("simulated terminal write failure")
            return real_mark(queue_id, status, *args, **kwargs)

        monkeypatch.setattr(queue_mod, "mark_queue_item", flaky_mark)
        summary = drain_queue(CONFIG, transport=transport, repo_root=tmp_path, secrets=SECRETS)
        assert summary.attempted == 1
        # Upload may have succeeded, but terminal transition failed ⇒ not counted exported.
        assert summary.exported == 0
        assert "export_validation" in summary.error_classes
        assert any("terminal_mark_failed" in n for n in summary.notes)
        # Row remains non-terminal under flaky terminal writes (still sending/pending).
        row = load_queue_item(qid, repo_root=tmp_path)
        assert row["status"] in {"sending", "pending"}
