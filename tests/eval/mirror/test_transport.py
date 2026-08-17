"""S4b transport: classification, mock double, lazy Opik import, flush adapter (P0-4/P1-3/E5)."""

from __future__ import annotations

import ast
import math
import sys
import time
from pathlib import Path

import pytest

from git_cg.eval.mirror.secrets import OpikRuntimeSecrets
from git_cg.eval.mirror.transport import (
    EXPORT_ERROR_CLASSES,
    LAZY_OPIK_IMPORT_ALLOWLIST,
    ExportTransportError,
    MockTransport,
    OpikSdkTransport,
    _classify,
    classify_export_error,
    flush_timeout_seconds,
    scrub_export_note,
)

SECRETS = OpikRuntimeSecrets(api_key="k", workspace="w", base_url=None)
REPO_ROOT = Path(__file__).resolve().parents[3]


class TestFlushTimeoutSeconds:
    @pytest.mark.parametrize(
        ("ms", "expected"),
        [
            (1, 1),
            (999, 1),
            (1000, 1),
            (1001, 2),
            (5000, 5),
        ],
    )
    def test_ms_to_seconds_ceil(self, ms: int, expected: int) -> None:
        assert flush_timeout_seconds(ms) == expected
        assert flush_timeout_seconds(ms) == max(1, math.ceil(ms / 1000))

    def test_non_positive_clamped(self) -> None:
        assert flush_timeout_seconds(0) == 1
        assert flush_timeout_seconds(-5) == 1


class TestScrubExportNote:
    def test_strips_urls_and_auth_headers(self) -> None:
        raw = "failed Authorization: Bearer super-secret https://opik.example/v1/traces?x=1"
        cleaned = scrub_export_note(raw)
        assert "super-secret" not in cleaned
        assert "https://" not in cleaned
        assert "opik.example" not in cleaned
        assert "<redacted-url>" in cleaned or "<redacted-path>" in cleaned

    def test_bounded(self) -> None:
        assert len(scrub_export_note("x" * 500, limit=40)) <= 40


class TestClassify:
    def test_auth(self) -> None:
        err = _classify(PermissionError("denied"))
        assert err.error_class == "export_auth"

    def test_network_timeout(self) -> None:
        err = _classify(TimeoutError("timed out"))
        assert err.error_class == "export_network"

    def test_network_connection(self) -> None:
        err = _classify(ConnectionError("refused"))
        assert err.error_class == "export_network"

    def test_validation(self) -> None:
        err = _classify(ValueError("bad shape"))
        assert err.error_class == "export_validation"

    def test_unknown_defaults_to_network(self) -> None:
        err = _classify(RuntimeError("weird"))
        assert err.error_class == "export_network"

    def test_error_class_always_in_vocabulary(self) -> None:
        for exc in (Exception("x"), KeyError("k"), OSError("io")):
            assert _classify(exc).error_class in EXPORT_ERROR_CLASSES

    def test_invalid_class_falls_back(self) -> None:
        err = ExportTransportError("not_a_class", "msg")
        assert err.error_class == "export_network"

    def test_status_code_auth(self) -> None:
        class HttpError(Exception):
            status_code = 401

        err = classify_export_error(HttpError("nope"))
        assert err.error_class == "export_auth"

    def test_status_code_forbidden(self) -> None:
        class HttpError(Exception):
            status_code = 403

        assert classify_export_error(HttpError("nope")).error_class == "export_auth"

    def test_status_code_size(self) -> None:
        class HttpError(Exception):
            status_code = 413

        assert classify_export_error(HttpError("too big")).error_class == "export_size"

    def test_status_code_validation(self) -> None:
        class HttpError(Exception):
            status_code = 422

        assert classify_export_error(HttpError("schema")).error_class == "export_validation"

    def test_status_code_network_429_and_5xx(self) -> None:
        class Status429Error(Exception):
            status_code = 429

        class Status503Error(Exception):
            status_code = 503

        assert classify_export_error(Status429Error("slow down")).error_class == "export_network"
        assert classify_export_error(Status503Error("down")).error_class == "export_network"

    def test_message_does_not_retain_url(self) -> None:
        err = classify_export_error(RuntimeError("boom https://secret.example/v1/x token=abc"))
        text = str(err)
        assert "https://" not in text
        assert "secret.example" not in text


class TestMockTransport:
    def test_records_calls(self) -> None:
        t = MockTransport()
        t.upload(
            project="p",
            experiment_name="e",
            payload={"a": 1},
            secrets=SECRETS,
            timeout_ms=5000,
        )
        assert len(t.calls) == 1
        assert t.calls[0]["project"] == "p"
        assert t.calls[0]["experiment_name"] == "e"
        assert t.calls[0]["payload"] == {"a": 1}
        assert t.calls[0]["timeout_ms"] == 5000

    def test_primed_failure(self) -> None:
        t = MockTransport(fail_with=ExportTransportError("export_network", "boom"))
        with pytest.raises(ExportTransportError, match="export_network"):
            t.upload(
                project="p",
                experiment_name="e",
                payload={},
                secrets=SECRETS,
                timeout_ms=5000,
            )
        # Call still recorded before the raise.
        assert len(t.calls) == 1


class TestOpikSdkTransport:
    def test_missing_opik_package_raises_validation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Simulate opik not installed.
        monkeypatch.setitem(sys.modules, "opik", None)
        t = OpikSdkTransport()
        with pytest.raises(ExportTransportError) as exc_info:
            t.upload(
                project="p",
                experiment_name="e",
                payload={},
                secrets=SECRETS,
                timeout_ms=5000,
            )
        assert exc_info.value.error_class == "export_validation"
        assert "opik package not installed" in str(exc_info.value)

    def test_sdk_exception_is_classified(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeOpik:
            def __init__(self, **kwargs: object) -> None:
                pass

            def trace(self, **kwargs: object) -> None:
                raise ConnectionError("connection refused")

        class FakeModule:
            Opik = FakeOpik

        monkeypatch.setitem(sys.modules, "opik", FakeModule())
        t = OpikSdkTransport()
        with pytest.raises(ExportTransportError) as exc_info:
            t.upload(
                project="p",
                experiment_name="e",
                payload={},
                secrets=SECRETS,
                timeout_ms=5000,
            )
        assert exc_info.value.error_class == "export_network"

    def test_no_trace_surface_raises_validation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeOpik:
            def __init__(self, **kwargs: object) -> None:
                pass

        class FakeModule:
            Opik = FakeOpik

        monkeypatch.setitem(sys.modules, "opik", FakeModule())
        t = OpikSdkTransport()
        with pytest.raises(ExportTransportError) as exc_info:
            t.upload(
                project="p",
                experiment_name="e",
                payload={},
                secrets=SECRETS,
                timeout_ms=5000,
            )
        assert exc_info.value.error_class == "export_validation"

    def test_flush_adapter_uses_seconds_and_ctor_kwargs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen: dict[str, object] = {}

        class FakeOpik:
            def __init__(self, **kwargs: object) -> None:
                seen["ctor"] = kwargs

            def trace(self, **kwargs: object) -> None:
                seen["trace"] = kwargs

            def flush(self, timeout: int | None = None) -> bool:
                seen["flush_timeout"] = timeout
                return True

        class FakeModule:
            Opik = FakeOpik

        monkeypatch.setitem(sys.modules, "opik", FakeModule())
        OpikSdkTransport().upload(
            project="proj-eval",
            experiment_name="exp-1",
            payload={"input": {"a": 1}, "output": {}, "metadata": {}},
            secrets=SECRETS,
            timeout_ms=5000,
        )
        assert seen["ctor"] == {
            "project_name": "proj-eval",
            "workspace": "w",
            "host": None,
            "api_key": "k",
        }
        assert seen["flush_timeout"] == 5

    @pytest.mark.parametrize("timeout_ms", [1, 999, 1000, 5000])
    def test_flush_timeout_conversion_matrix(self, monkeypatch: pytest.MonkeyPatch, timeout_ms: int) -> None:
        seen: list[int | None] = []

        class FakeOpik:
            def __init__(self, **kwargs: object) -> None:
                pass

            def trace(self, **kwargs: object) -> None:
                return None

            def flush(self, timeout: int | None = None) -> bool:
                seen.append(timeout)
                return True

        class FakeModule:
            Opik = FakeOpik

        monkeypatch.setitem(sys.modules, "opik", FakeModule())
        OpikSdkTransport().upload(
            project="p",
            experiment_name="e",
            payload={},
            secrets=SECRETS,
            timeout_ms=timeout_ms,
        )
        assert seen == [flush_timeout_seconds(timeout_ms)]

    def test_flush_false_is_export_network(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeOpik:
            def __init__(self, **kwargs: object) -> None:
                pass

            def trace(self, **kwargs: object) -> None:
                return None

            def flush(self, timeout: int | None = None) -> bool:
                return False

        class FakeModule:
            Opik = FakeOpik

        monkeypatch.setitem(sys.modules, "opik", FakeModule())
        with pytest.raises(ExportTransportError) as ei:
            OpikSdkTransport().upload(
                project="p",
                experiment_name="e",
                payload={},
                secrets=SECRETS,
                timeout_ms=1000,
            )
        assert ei.value.error_class == "export_network"
        assert "false" in str(ei.value).lower()

    def test_flush_hang_past_deadline(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeOpik:
            def __init__(self, **kwargs: object) -> None:
                pass

            def trace(self, **kwargs: object) -> None:
                return None

            def flush(self, timeout: int | None = None) -> bool:
                # Simulate wall-clock overrun relative to outer deadline.
                time.sleep(0.05)
                return True

        class FakeModule:
            Opik = FakeOpik

        monkeypatch.setitem(sys.modules, "opik", FakeModule())
        # Force deadline into the past before flush returns.
        real_monotonic = time.monotonic
        state = {"n": 0}

        def fake_monotonic() -> float:
            state["n"] += 1
            # First calls establish deadline; later call after flush exceeds it.
            if state["n"] >= 4:
                return real_monotonic() + 10.0
            return real_monotonic()

        monkeypatch.setattr(time, "monotonic", fake_monotonic)
        with pytest.raises(ExportTransportError) as ei:
            OpikSdkTransport().upload(
                project="p",
                experiment_name="e",
                payload={},
                secrets=SECRETS,
                timeout_ms=1,
            )
        assert ei.value.error_class == "export_network"


class TestExportBatchTransportProjection:
    def test_send_projects_export_batch_transport_body(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Durable export_batch body must project nested item payload, not empty top-level fields."""
        seen: dict[str, object] = {}

        class FakeOpik:
            def __init__(self, **kwargs: object) -> None:
                pass

            def trace(self, **kwargs: object) -> None:
                seen["trace"] = kwargs

            def flush(self, timeout: int | None = None) -> bool:
                return True

        class FakeModule:
            Opik = FakeOpik

        monkeypatch.setitem(sys.modules, "opik", FakeModule())

        payload = {
            "items": [
                {
                    "item_ref": "bundle_comp_1",
                    "payload": {
                        "trace": {
                            "input": {"bundle_id": "bundle_comp_1", "attempt_count": 1},
                            "output": {"final_message": "ok", "scored_target": "final_message"},
                            "metadata": {
                                "experiment_name": "exp-real",
                                "authority": {"source": "local_wrapper", "cloud_rescore_forbidden": True},
                                "gate": {"deterministic_pass": True},
                            },
                        },
                        "thread": {
                            "thread_id": "sess_comp_1",
                            "messages": [{"role": "user", "content": "hi"}],
                        },
                        "feedback": [{"name": "format_compliance", "value": 1.0}],
                        "experiment": {"experiment_name": "exp-real"},
                        "authority": {"source": "local_wrapper"},
                        "bundle_id": "bundle_comp_1",
                        "artifact_class": "final_accept",
                        "gate": {"deterministic_pass": True},
                        "score_card": {"format_compliance": 1.0},
                    },
                }
            ],
            "schema_pack": "schema_pack_v0@" + ("a" * 64),
            "metric_catalog": "metric_catalog_v0@" + ("b" * 64),
            "redaction_profile": "default_scrub",
        }

        OpikSdkTransport().upload(
            project="proj-eval",
            experiment_name="exp-real",
            payload=payload,
            secrets=SECRETS,
            timeout_ms=1000,
        )
        trace = seen["trace"]
        assert isinstance(trace, dict)
        assert trace["name"] == "exp-real"
        assert trace["input"]["bundle_id"] == "bundle_comp_1"
        assert trace["output"]["final_message"] == "ok"
        metadata = trace["metadata"]
        assert metadata["authority"]["cloud_rescore_forbidden"] is True
        assert metadata["thread"]["thread_id"] == "sess_comp_1"
        assert metadata["feedback"][0]["name"] == "format_compliance"
        assert metadata["schema_pack"].startswith("schema_pack_v0@")
        assert metadata["metric_catalog"].startswith("metric_catalog_v0@")
        assert metadata["redaction_profile"] == "default_scrub"
        assert metadata["item_ref"] == "bundle_comp_1"
        assert metadata["bundle_id"] == "bundle_comp_1"


class TestE5ImportIsolation:
    def test_static_no_module_level_opik_import(self) -> None:
        mirror_root = REPO_ROOT / "src" / "git_cg" / "eval" / "mirror"
        lazy_sites: list[str] = []
        for path in sorted(mirror_root.rglob("*.py")):
            rel = path.relative_to(REPO_ROOT).as_posix()
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in tree.body:  # module body only
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "opik" or alias.name.startswith("opik."):
                            pytest.fail(f"module-level import opik in {rel}:{node.lineno}")
                if isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    if mod == "opik" or mod.startswith("opik."):
                        pytest.fail(f"module-level from opik import in {rel}:{node.lineno}")
            # Collect lazy import sites anywhere in the file.
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "opik" or alias.name.startswith("opik."):
                            lazy_sites.append(f"{rel}:{node.lineno}")
                if isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    if mod == "opik" or mod.startswith("opik."):
                        lazy_sites.append(f"{rel}:{node.lineno}")
        assert set(lazy_sites) == set(LAZY_OPIK_IMPORT_ALLOWLIST), (
            f"lazy opik import sites {lazy_sites} != allowlist {sorted(LAZY_OPIK_IMPORT_ALLOWLIST)}"
        )

    def test_package_imports_with_opik_masked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Mask opik; package import must still succeed (lazy only).
        monkeypatch.setitem(sys.modules, "opik", None)
        for name in list(sys.modules):
            if name == "git_cg.eval.mirror" or name.startswith("git_cg.eval.mirror."):
                monkeypatch.delitem(sys.modules, name, raising=False)
        import git_cg.eval.mirror as mirror

        assert mirror is not None
        assert hasattr(mirror, "OpikSdkTransport")
