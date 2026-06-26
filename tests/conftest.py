"""
Shared pytest configuration and fixtures.

Stubs out sentry_sdk before any test modules import git_cg packages, since
sentry-sdk may not be installed in the test environment and telemetry.py
calls sentry_sdk.init() at import time.
"""

import sys
import types

# ---------------------------------------------------------------------------
# Stub sentry_sdk before any git_cg module is imported
# ---------------------------------------------------------------------------

if "sentry_sdk" not in sys.modules:
    _sentry_stub = types.ModuleType("sentry_sdk")
    _sentry_stub.init = lambda *args, **kwargs: None
    sys.modules["sentry_sdk"] = _sentry_stub
