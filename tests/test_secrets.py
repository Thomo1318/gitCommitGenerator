"""Tests for git_cg.secrets - covering the _populate_cache and resolve_secret changes."""

import unittest.mock as mock

# ---------------------------------------------------------------------------
# _populate_cache - early-exit paths (no SDK, no token)
# ---------------------------------------------------------------------------


def test_populate_cache_sets_empty_dict_when_client_unavailable(monkeypatch):
    """When onepassword Client is unavailable (None), _populate_cache must still set _op_cache to {}."""
    import git_cg.secrets as secrets_module

    monkeypatch.setattr(secrets_module, "Client", None)
    monkeypatch.setattr(secrets_module, "_op_cache", None)

    secrets_module._populate_cache()

    assert secrets_module._op_cache == {}


def test_populate_cache_sets_empty_dict_when_no_op_token(monkeypatch):
    """When OP_SERVICE_ACCOUNT_TOKEN is absent, _populate_cache must return early with an empty cache."""
    import git_cg.secrets as secrets_module

    # Provide a mock Client so the SDK branch is entered, but remove the token
    monkeypatch.setattr(secrets_module, "Client", mock.MagicMock())
    monkeypatch.setattr(secrets_module, "_op_cache", None)
    monkeypatch.delenv("OP_SERVICE_ACCOUNT_TOKEN", raising=False)

    secrets_module._populate_cache()

    assert secrets_module._op_cache == {}


def test_populate_cache_is_idempotent_without_sdk(monkeypatch):
    """Calling _populate_cache twice without a Client must leave _op_cache as an empty dict."""
    import git_cg.secrets as secrets_module

    monkeypatch.setattr(secrets_module, "Client", None)
    monkeypatch.setattr(secrets_module, "_op_cache", None)

    secrets_module._populate_cache()
    secrets_module._populate_cache()

    assert secrets_module._op_cache == {}


# ---------------------------------------------------------------------------
# resolve_secret - env lookup, cache lookup, default value
# ---------------------------------------------------------------------------


def test_resolve_secret_returns_env_value_when_set(monkeypatch):
    """resolve_secret must return the environment variable value when it exists."""
    import git_cg.secrets as secrets_module

    monkeypatch.setenv("MY_TEST_KEY", "env_value_123")
    result = secrets_module.resolve_secret("MY_TEST_KEY", "default")
    assert result == "env_value_123"


def test_resolve_secret_returns_default_when_not_in_env_or_cache(monkeypatch):
    """When the key is absent from env and cache, the default value must be returned."""
    import git_cg.secrets as secrets_module

    monkeypatch.delenv("NONEXISTENT_SECRET_KEY", raising=False)
    monkeypatch.setattr(secrets_module, "_op_cache", {})

    result = secrets_module.resolve_secret("NONEXISTENT_SECRET_KEY", "my_default")
    assert result == "my_default"


def test_resolve_secret_returns_empty_string_as_default_when_no_args(monkeypatch):
    """The default value for resolve_secret must be an empty string when not supplied."""
    import git_cg.secrets as secrets_module

    monkeypatch.delenv("ABSENT_KEY_XYZ", raising=False)
    monkeypatch.setattr(secrets_module, "_op_cache", {})

    result = secrets_module.resolve_secret("ABSENT_KEY_XYZ")
    assert result == ""


def test_resolve_secret_uses_cache_when_env_not_set(monkeypatch):
    """resolve_secret must fall back to the _op_cache after a failed env lookup."""
    import git_cg.secrets as secrets_module

    monkeypatch.delenv("CACHED_SECRET_KEY", raising=False)
    monkeypatch.setattr(secrets_module, "_op_cache", {"CACHED_SECRET_KEY": "cached_value"})

    result = secrets_module.resolve_secret("CACHED_SECRET_KEY", "default")
    assert result == "cached_value"


def test_resolve_secret_prefers_env_over_cache(monkeypatch):
    """Environment variable must take precedence over the _op_cache value."""
    import git_cg.secrets as secrets_module

    monkeypatch.setenv("PRIORITY_KEY", "env_wins")
    monkeypatch.setattr(secrets_module, "_op_cache", {"PRIORITY_KEY": "cache_value"})

    result = secrets_module.resolve_secret("PRIORITY_KEY", "default")
    assert result == "env_wins"


def test_resolve_secret_triggers_populate_cache_when_cache_is_none(monkeypatch):
    """resolve_secret must call _populate_cache when _op_cache is None."""
    import git_cg.secrets as secrets_module

    monkeypatch.delenv("TRIGGER_TEST_KEY", raising=False)
    monkeypatch.setattr(secrets_module, "_op_cache", None)
    monkeypatch.setattr(secrets_module, "Client", None)  # so _populate_cache is a no-op

    # After calling resolve_secret, _op_cache must no longer be None
    secrets_module.resolve_secret("TRIGGER_TEST_KEY", "default")
    assert secrets_module._op_cache is not None


# ---------------------------------------------------------------------------
# _populate_cache - async error handling
# ---------------------------------------------------------------------------


def test_populate_cache_handles_async_exception_gracefully(monkeypatch, capsys):
    """If the async fetch raises an exception, _populate_cache must not propagate it."""
    import git_cg.secrets as secrets_module

    fake_token = "op_service_account_test_token"
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", fake_token)
    monkeypatch.delenv("OPIK_API_KEY", raising=False)
    monkeypatch.setattr(secrets_module, "_op_cache", None)

    # Provide a mock Client whose authenticate raises
    async def _failing_authenticate(*args, **kwargs):
        raise RuntimeError("Authentication failed")

    mock_client_class = mock.MagicMock()
    mock_client_class.authenticate = _failing_authenticate
    monkeypatch.setattr(secrets_module, "Client", mock_client_class)

    # Must not raise
    secrets_module._populate_cache()
    assert secrets_module._op_cache == {}


def test_populate_cache_prints_debug_message_on_failure(monkeypatch, capsys):
    """A failed 1Password fetch must print a [Debug] message to stderr."""
    import git_cg.secrets as secrets_module

    fake_token = "op_service_account_test_token"
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", fake_token)
    monkeypatch.delenv("OPIK_API_KEY", raising=False)
    monkeypatch.setattr(secrets_module, "_op_cache", None)

    async def _failing_authenticate(*args, **kwargs):
        raise RuntimeError("Network error")

    mock_client_class = mock.MagicMock()
    mock_client_class.authenticate = _failing_authenticate
    monkeypatch.setattr(secrets_module, "Client", mock_client_class)

    secrets_module._populate_cache()

    captured = capsys.readouterr()
    assert "[Debug]" in captured.err


# ---------------------------------------------------------------------------
# ENV_EXPORT_ALLOWLIST – sentry keys added in this PR
# ---------------------------------------------------------------------------


def test_sentry_dsn_is_in_env_export_allowlist():
    """SENTRY_DSN must be in the ENV_EXPORT_ALLOWLIST so 1Password can export it."""
    from git_cg.secrets import ENV_EXPORT_ALLOWLIST

    assert "SENTRY_DSN" in ENV_EXPORT_ALLOWLIST


def test_sentry_environment_is_in_env_export_allowlist():
    """SENTRY_ENVIRONMENT must be in the ENV_EXPORT_ALLOWLIST."""
    from git_cg.secrets import ENV_EXPORT_ALLOWLIST

    assert "SENTRY_ENVIRONMENT" in ENV_EXPORT_ALLOWLIST


def test_sentry_release_is_in_env_export_allowlist():
    """SENTRY_RELEASE must be in the ENV_EXPORT_ALLOWLIST."""
    from git_cg.secrets import ENV_EXPORT_ALLOWLIST

    assert "SENTRY_RELEASE" in ENV_EXPORT_ALLOWLIST


def test_sentry_keys_are_all_present_in_allowlist():
    """All three sentry keys must be present together, not just individually."""
    from git_cg.secrets import ENV_EXPORT_ALLOWLIST

    sentry_keys = {"SENTRY_DSN", "SENTRY_ENVIRONMENT", "SENTRY_RELEASE"}
    assert sentry_keys.issubset(ENV_EXPORT_ALLOWLIST)


# ---------------------------------------------------------------------------
# resolve_secret – _op_cache is None guard (PR fix)
# ---------------------------------------------------------------------------


def test_resolve_secret_returns_default_when_cache_is_none_after_populate(monkeypatch):
    """
    If _populate_cache somehow leaves _op_cache as None (edge case), resolve_secret
    must not raise TypeError and must return the default value instead.

    This tests the defensive guard: `if _op_cache is not None and secret_key in _op_cache`.
    """
    import git_cg.secrets as secrets_module

    monkeypatch.delenv("EDGE_CASE_KEY", raising=False)
    monkeypatch.setattr(secrets_module, "_op_cache", None)

    # Override _populate_cache to intentionally leave _op_cache as None
    def populate_that_leaves_none():
        pass  # deliberately does NOT set _op_cache

    monkeypatch.setattr(secrets_module, "_populate_cache", populate_that_leaves_none)

    # Must not raise TypeError; must return the default
    result = secrets_module.resolve_secret("EDGE_CASE_KEY", "safe_default")
    assert result == "safe_default"


def test_resolve_secret_returns_empty_default_when_cache_is_none_after_populate(monkeypatch):
    """The None guard must work with the default empty-string fallback as well."""
    import git_cg.secrets as secrets_module

    monkeypatch.delenv("EDGE_CASE_KEY_2", raising=False)
    monkeypatch.setattr(secrets_module, "_op_cache", None)

    def populate_that_leaves_none():
        pass

    monkeypatch.setattr(secrets_module, "_populate_cache", populate_that_leaves_none)

    result = secrets_module.resolve_secret("EDGE_CASE_KEY_2")
    assert result == ""
