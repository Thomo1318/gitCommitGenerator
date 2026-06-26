"""
Tests for src/git_cg/sentry_config.py

Covers:
  - init_sentry: early return when GIT_CG_DISABLE_SENTRY=1
  - init_sentry: calls sentry_sdk.init with expected kwargs when enabled
  - init_sentry: version falls back to "dev" when package metadata is not found
  - init_sentry: suppresses exceptions raised by sentry_sdk.init
  - init_sentry: reads SENTRY_DSN from environment
  - init_sentry: reads SENTRY_ENVIRONMENT from environment, defaulting to "local"
  - scrub_data: redacts diff_output inside event["contexts"]["git_cg"]
  - scrub_data: leaves events without diff_output untouched
  - scrub_data: handles events with no "contexts" key
  - scrub_data: handles events with "contexts" but no "git_cg" key
  - scrub_data: handles events with "git_cg" but no "diff_output" key
  - scrub_data: always returns the event
"""

import importlib.metadata
from unittest.mock import MagicMock, patch


# ===========================================================================
# init_sentry – early exit
# ===========================================================================


class TestInitSentryEarlyExit:
    def test_does_not_call_sentry_init_when_disabled(self, monkeypatch):
        """init_sentry must return without calling sentry_sdk.init when GIT_CG_DISABLE_SENTRY=1."""
        monkeypatch.setenv("GIT_CG_DISABLE_SENTRY", "1")

        init_spy = MagicMock()
        with patch("sentry_sdk.init", init_spy):
            from git_cg.sentry_config import init_sentry

            init_sentry()

        init_spy.assert_not_called()

    def test_does_not_call_sentry_init_when_disabled_value_is_one(self, monkeypatch):
        """The exact string "1" must trigger the early return, not "true" or "yes"."""
        monkeypatch.setenv("GIT_CG_DISABLE_SENTRY", "1")

        init_spy = MagicMock()
        with patch("sentry_sdk.init", init_spy):
            from git_cg.sentry_config import init_sentry

            init_sentry()

        init_spy.assert_not_called()

    def test_proceeds_when_disabled_env_is_zero(self, monkeypatch):
        """When GIT_CG_DISABLE_SENTRY=0, init_sentry should attempt sentry_sdk.init."""
        monkeypatch.setenv("GIT_CG_DISABLE_SENTRY", "0")
        monkeypatch.delenv("SENTRY_DSN", raising=False)

        init_spy = MagicMock()
        with patch("sentry_sdk.init", init_spy):
            from git_cg.sentry_config import init_sentry

            init_sentry()

        init_spy.assert_called_once()

    def test_proceeds_when_disabled_env_is_absent(self, monkeypatch):
        """When GIT_CG_DISABLE_SENTRY is not set, init_sentry should attempt sentry_sdk.init."""
        monkeypatch.delenv("GIT_CG_DISABLE_SENTRY", raising=False)
        monkeypatch.delenv("SENTRY_DSN", raising=False)

        init_spy = MagicMock()
        with patch("sentry_sdk.init", init_spy):
            from git_cg.sentry_config import init_sentry

            init_sentry()

        init_spy.assert_called_once()


# ===========================================================================
# init_sentry – sentry_sdk.init kwargs
# ===========================================================================


class TestInitSentryKwargs:
    def _call_init_sentry_and_capture_kwargs(self, monkeypatch, **env_overrides):
        """Helper that runs init_sentry() with a mocked sentry_sdk.init and returns kwargs."""
        monkeypatch.setenv("GIT_CG_DISABLE_SENTRY", "0")
        for key, value in env_overrides.items():
            if value is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, value)

        captured_kwargs = {}

        def fake_init(**kwargs):
            captured_kwargs.update(kwargs)

        with patch("sentry_sdk.init", fake_init):
            from git_cg.sentry_config import init_sentry

            init_sentry()

        return captured_kwargs

    def test_dsn_is_read_from_env(self, monkeypatch):
        """init_sentry must pass SENTRY_DSN from env to sentry_sdk.init."""
        kwargs = self._call_init_sentry_and_capture_kwargs(
            monkeypatch, SENTRY_DSN="https://example@sentry.io/123"
        )
        assert kwargs.get("dsn") == "https://example@sentry.io/123"

    def test_dsn_is_none_when_env_absent(self, monkeypatch):
        """init_sentry passes None as dsn when SENTRY_DSN is not set."""
        kwargs = self._call_init_sentry_and_capture_kwargs(monkeypatch, SENTRY_DSN=None)
        assert kwargs.get("dsn") is None

    def test_environment_is_read_from_env(self, monkeypatch):
        """SENTRY_ENVIRONMENT value must be forwarded to sentry_sdk.init."""
        kwargs = self._call_init_sentry_and_capture_kwargs(monkeypatch, SENTRY_ENVIRONMENT="production")
        assert kwargs.get("environment") == "production"

    def test_environment_defaults_to_local(self, monkeypatch):
        """When SENTRY_ENVIRONMENT is not set, the environment must default to 'local'."""
        kwargs = self._call_init_sentry_and_capture_kwargs(monkeypatch, SENTRY_ENVIRONMENT=None)
        assert kwargs.get("environment") == "local"

    def test_send_default_pii_is_false(self, monkeypatch):
        """send_default_pii must be False to avoid leaking PII."""
        kwargs = self._call_init_sentry_and_capture_kwargs(monkeypatch)
        assert kwargs.get("send_default_pii") is False

    def test_traces_sample_rate_is_zero(self, monkeypatch):
        """traces_sample_rate must be 0.0 to disable performance tracing."""
        kwargs = self._call_init_sentry_and_capture_kwargs(monkeypatch)
        assert kwargs.get("traces_sample_rate") == 0.0

    def test_before_send_is_callable(self, monkeypatch):
        """init_sentry must supply a callable before_send hook."""
        kwargs = self._call_init_sentry_and_capture_kwargs(monkeypatch)
        assert callable(kwargs.get("before_send"))

    def test_release_contains_package_name(self, monkeypatch):
        """The release string must be prefixed with 'gitCommitGenerator@'."""
        kwargs = self._call_init_sentry_and_capture_kwargs(monkeypatch)
        release = kwargs.get("release", "")
        assert release.startswith("gitCommitGenerator@")


# ===========================================================================
# init_sentry – version resolution
# ===========================================================================


class TestInitSentryVersion:
    def test_version_falls_back_to_dev_when_package_not_found(self, monkeypatch):
        """When the package is not installed, version must be 'dev'."""
        monkeypatch.setenv("GIT_CG_DISABLE_SENTRY", "0")

        captured = {}

        def fake_init(**kwargs):
            captured.update(kwargs)

        def raise_not_found(name):
            raise importlib.metadata.PackageNotFoundError(name)

        with patch("sentry_sdk.init", fake_init), patch("importlib.metadata.version", raise_not_found):
            from git_cg.sentry_config import init_sentry

            init_sentry()

        assert captured.get("release") == "gitCommitGenerator@dev"

    def test_version_uses_installed_package_metadata(self, monkeypatch):
        """When metadata is found, the real version should appear in the release string."""
        monkeypatch.setenv("GIT_CG_DISABLE_SENTRY", "0")

        captured = {}

        def fake_init(**kwargs):
            captured.update(kwargs)

        with patch("sentry_sdk.init", fake_init), patch("importlib.metadata.version", return_value="1.2.3"):
            from git_cg.sentry_config import init_sentry

            init_sentry()

        assert captured.get("release") == "gitCommitGenerator@1.2.3"


# ===========================================================================
# init_sentry – exception suppression
# ===========================================================================


class TestInitSentryExceptionSuppression:
    def test_exception_from_sentry_init_is_suppressed(self, monkeypatch):
        """If sentry_sdk.init raises any exception, init_sentry must not propagate it."""
        monkeypatch.setenv("GIT_CG_DISABLE_SENTRY", "0")

        def exploding_init(**kwargs):
            raise RuntimeError("sentry is down")

        with patch("sentry_sdk.init", exploding_init):
            from git_cg.sentry_config import init_sentry

            # Must not raise
            init_sentry()

    def test_value_error_from_sentry_init_is_suppressed(self, monkeypatch):
        """ValueError from sentry_sdk.init must also be suppressed."""
        monkeypatch.setenv("GIT_CG_DISABLE_SENTRY", "0")

        def broken_init(**kwargs):
            raise ValueError("bad dsn")

        with patch("sentry_sdk.init", broken_init):
            from git_cg.sentry_config import init_sentry

            init_sentry()


# ===========================================================================
# scrub_data – the before_send hook
# ===========================================================================


class TestScrubData:
    """Tests for the scrub_data closure captured via sentry_sdk.init's before_send kwarg."""

    def _get_scrub_data(self, monkeypatch):
        """Extract the scrub_data callable from init_sentry's sentry_sdk.init call."""
        monkeypatch.setenv("GIT_CG_DISABLE_SENTRY", "0")
        captured = {}

        def fake_init(**kwargs):
            captured.update(kwargs)

        with patch("sentry_sdk.init", fake_init):
            from git_cg.sentry_config import init_sentry

            init_sentry()

        return captured["before_send"]

    def test_scrubs_diff_output_when_present(self, monkeypatch):
        """diff_output inside event['contexts']['git_cg'] must be replaced with '[SCRUBBED]'."""
        scrub_data = self._get_scrub_data(monkeypatch)

        event = {"contexts": {"git_cg": {"diff_output": "very large diff content"}}}
        result = scrub_data(event, {})

        assert result["contexts"]["git_cg"]["diff_output"] == "[SCRUBBED]"

    def test_returns_event_after_scrubbing(self, monkeypatch):
        """scrub_data must return the (mutated) event object."""
        scrub_data = self._get_scrub_data(monkeypatch)

        event = {"contexts": {"git_cg": {"diff_output": "some diff"}}}
        result = scrub_data(event, {})

        assert result is event

    def test_returns_event_when_no_diff_output(self, monkeypatch):
        """When 'diff_output' is absent, scrub_data must return the event unchanged."""
        scrub_data = self._get_scrub_data(monkeypatch)

        event = {"contexts": {"git_cg": {"other_key": "value"}}}
        result = scrub_data(event, {})

        assert result is event
        assert "diff_output" not in result["contexts"]["git_cg"]

    def test_returns_event_when_no_git_cg_context(self, monkeypatch):
        """When 'git_cg' context is absent, scrub_data must return the event unchanged."""
        scrub_data = self._get_scrub_data(monkeypatch)

        event = {"contexts": {"other_service": {"data": "value"}}}
        result = scrub_data(event, {})

        assert result is event
        assert "git_cg" not in result["contexts"]

    def test_returns_event_when_no_contexts_key(self, monkeypatch):
        """When 'contexts' is absent from the event, scrub_data must return the event unchanged."""
        scrub_data = self._get_scrub_data(monkeypatch)

        event = {"exception": {"values": []}}
        result = scrub_data(event, {})

        assert result is event
        assert "contexts" not in result

    def test_does_not_modify_other_context_fields(self, monkeypatch):
        """scrub_data must not modify fields other than diff_output."""
        scrub_data = self._get_scrub_data(monkeypatch)

        event = {
            "contexts": {
                "git_cg": {
                    "diff_output": "large diff",
                    "diff_size": 12345,
                    "engine": "omlx",
                }
            }
        }
        result = scrub_data(event, {})

        assert result["contexts"]["git_cg"]["diff_size"] == 12345
        assert result["contexts"]["git_cg"]["engine"] == "omlx"
        assert result["contexts"]["git_cg"]["diff_output"] == "[SCRUBBED]"

    def test_scrubs_empty_diff_output(self, monkeypatch):
        """An empty string diff_output should also be scrubbed."""
        scrub_data = self._get_scrub_data(monkeypatch)

        event = {"contexts": {"git_cg": {"diff_output": ""}}}
        result = scrub_data(event, {})

        assert result["contexts"]["git_cg"]["diff_output"] == "[SCRUBBED]"

    def test_hint_is_passed_through_to_scrub_data(self, monkeypatch):
        """scrub_data must accept any hint value without error."""
        scrub_data = self._get_scrub_data(monkeypatch)

        event = {}
        hint = {"exc_info": (ValueError, ValueError("test"), None)}
        result = scrub_data(event, hint)

        assert result is event

    def test_empty_event_returns_unchanged(self, monkeypatch):
        """An empty event dict must pass through scrub_data without errors."""
        scrub_data = self._get_scrub_data(monkeypatch)

        event = {}
        result = scrub_data(event, {})

        assert result == {}