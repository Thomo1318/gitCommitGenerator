"""S4b transport: classification, mock double, lazy Opik import."""

from __future__ import annotations

import sys

import pytest

from git_cg.eval.mirror.secrets import OpikRuntimeSecrets
from git_cg.eval.mirror.transport import (
    EXPORT_ERROR_CLASSES,
    ExportTransportError,
    MockTransport,
    OpikSdkTransport,
    _classify,
)

SECRETS = OpikRuntimeSecrets(api_key="k", workspace="w", base_url=None)


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
