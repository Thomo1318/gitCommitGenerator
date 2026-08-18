"""S4b runtime secret resolution (never persisted, fail-closed auth)."""

from __future__ import annotations

import pytest

from git_cg.eval.mirror import secrets as mirror_secrets
from git_cg.eval.mirror.secrets import MirrorSecretError, resolve_opik_secrets


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
            """Return the mocked value for a supported Opik secret key.
            
            Parameters:
            	key (str): The secret key to resolve.
            	default (str): The value to return for unsupported keys.
            
            Returns:
            	str: The configured mock value or the provided default.
            """
            return {"OPIK_URL_OVERRIDE": "http://localhost:5173"}.get(key, default)

        monkeypatch.setattr(mirror_secrets, "resolve_secret", fake_resolve)
        secrets = resolve_opik_secrets(require_key=False)
        assert secrets.base_url == "http://localhost:5173"
