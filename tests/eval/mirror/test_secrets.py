"""S4b runtime secret resolution (never persisted, fail-closed auth)."""

from __future__ import annotations

import pytest

from git_cg.eval.mirror import secrets as mirror_secrets
from git_cg.eval.mirror.secrets import MirrorSecretError, ensure_secure_opik_endpoint, resolve_opik_secrets


class TestResolveOpikSecrets:
    def test_resolves_api_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPIK_API_KEY", "test-key-123")
        monkeypatch.setenv("OPIK_WORKSPACE", "ws")
        secrets = resolve_opik_secrets()
        assert secrets.api_key == "test-key-123"
        assert secrets.workspace == "ws"

    def test_missing_key_raises_when_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPIK_API_KEY", raising=False)
        # Prevent 1Password cache from supplying it.
        monkeypatch.setattr(mirror_secrets, "resolve_secret", lambda k, d="": d)
        with pytest.raises(MirrorSecretError, match="export_auth"):
            resolve_opik_secrets(require_key=True)

    def test_missing_key_allowed_when_not_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(mirror_secrets, "resolve_secret", lambda k, d="": d)
        secrets = resolve_opik_secrets(require_key=False)
        assert secrets.api_key == ""

    def test_repr_never_leaks_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPIK_API_KEY", "super-secret-value")
        secrets = resolve_opik_secrets()
        assert "super-secret-value" not in repr(secrets)
        assert "<redacted>" in repr(secrets)

    def test_base_url_falls_back_to_url_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_resolve(key: str, default: str = "") -> str:
            """Return mocked values for supported Opik secret keys."""
            return {"OPIK_URL_OVERRIDE": "http://localhost:5173"}.get(key, default)

        monkeypatch.setattr(mirror_secrets, "resolve_secret", fake_resolve)
        secrets = resolve_opik_secrets(require_key=False)
        assert secrets.base_url == "http://localhost:5173"


class TestEnsureSecureOpikEndpoint:
    @pytest.mark.parametrize(
        "base_url",
        [
            "https://www.comet.com/opik/api",
            "http://localhost:5173/api",
            "http://127.0.0.1:5173",
            "http://[::1]:5173/api",
            None,
            "",
        ],
    )
    def test_allows_https_and_loopback(self, base_url: str | None) -> None:
        ensure_secure_opik_endpoint(base_url=base_url, api_key="k")

    @pytest.mark.parametrize(
        "base_url",
        [
            "http://remote.example/opik",
            "http://localhost.attacker.example/opik",
            "http://127.0.0.1.evil.test/opik",
            "http://example.com",
        ],
    )
    def test_rejects_cleartext_remote(self, base_url: str) -> None:
        with pytest.raises(RuntimeError, match="refusing non-HTTPS"):
            ensure_secure_opik_endpoint(base_url=base_url, api_key="k")

    def test_skips_without_api_key(self) -> None:
        ensure_secure_opik_endpoint(base_url="http://remote.example", api_key="")
        ensure_secure_opik_endpoint(base_url="http://remote.example", api_key=None)

    def test_resolve_rejects_cleartext_remote_with_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_resolve(key: str, default: str = "") -> str:
            return {
                "OPIK_API_KEY": "k",
                "OPIK_BASE_URL": "http://localhost.attacker.example/opik",
            }.get(key, default)

        monkeypatch.setattr(mirror_secrets, "resolve_secret", fake_resolve)
        with pytest.raises(RuntimeError, match="refusing non-HTTPS"):
            resolve_opik_secrets(require_key=True)
