"""Lane C' execution availability — credentials ≠ authorization (D4' / C-AVAIL).

``judge_execution_available``::

    judge_execution_available =
        eligible
        AND credentials_present
        AND provider_client_constructible

Missing ``GIT_CG_EVAL_JUDGE_API_KEY`` emits ``unavailable_creds`` and must **not**
flip eligibility false. This module may resolve secrets via
``secrets.resolve_secret`` but never returns raw key material in evidence.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from git_cg.eval.lane_c.taxonomy import (
    EXEC_CLIENT_UNCONSTRUCTIBLE,
    EXEC_UNAVAILABLE_CREDS,
    GATE_JUDGE_UNAVAILABLE,
)

ENV_JUDGE_API_KEY: Final = "GIT_CG_EVAL_JUDGE_API_KEY"
ENV_JUDGE_BASE_URL: Final = "GIT_CG_EVAL_JUDGE_BASE_URL"

# Injectable secret resolver type (tests). Default uses project secrets helper.
SecretResolver = Callable[[str, str], str]


def _default_secret_resolver(secret_key: str, default_value: str = "") -> str:
    """Resolve via ``git_cg.secrets.resolve_secret`` (lazy import; no SDK)."""
    from git_cg.secrets import resolve_secret

    return resolve_secret(secret_key, default_value)


def credentials_present(
    *,
    judge_api_key: str | None = None,
    environ: Mapping[str, str] | None = None,
    secret_resolver: SecretResolver | None = None,
) -> bool:
    """Return True when a non-empty judge API key is available.

    Resolution order:
    1. explicit ``judge_api_key`` argument (tests/lab injection)
    2. ``environ[GIT_CG_EVAL_JUDGE_API_KEY]`` when ``environ`` is provided
    3. ``secret_resolver`` / ``resolve_secret`` against process env + 1P cache
    """
    if judge_api_key is not None:
        return bool(judge_api_key.strip())

    if environ is not None:
        return bool(str(environ.get(ENV_JUDGE_API_KEY, "")).strip())

    resolver = secret_resolver or _default_secret_resolver
    # When environ is None, consult resolver (env / 1P) without echoing value.
    try:
        val = resolver(ENV_JUDGE_API_KEY, "")
    except Exception:
        return False
    return bool(str(val or "").strip())


def provider_client_constructible(
    *,
    credentials_ok: bool,
    base_url: str | None = None,
    environ: Mapping[str, str] | None = None,
    client_factory_ok: bool | None = None,
) -> bool:
    """Return True when a provider client could be constructed offline-safe.

    Spine rule: credentials must be present. Optional ``base_url`` is an
    enhancement only — empty/missing URL does not fail constructibility.
    ``client_factory_ok`` lets tests force a constructibility failure without
    importing a provider SDK.
    """
    if not credentials_ok:
        return False
    if client_factory_ok is False:
        return False
    # base_url / environ are accepted for API symmetry with availability callers
    # but do not affect constructibility: empty/missing URL uses the provider
    # default endpoint. Keep parameters so call sites stay stable.
    _ = (base_url, environ)
    return True


@dataclass(frozen=True, slots=True)
class LaneCAvailability:
    """Frozen availability verdict (separate from authorization)."""

    eligible: bool
    credentials_present: bool
    client_constructible: bool
    available: bool
    reason: str | None
    gate_disposition: str | None
    execution_code: str | None
    evidence: dict[str, Any] = field(default_factory=dict)


def evaluate_judge_availability(
    *,
    eligible: bool,
    judge_api_key: str | None = None,
    base_url: str | None = None,
    environ: Mapping[str, str] | None = None,
    secret_resolver: SecretResolver | None = None,
    client_factory_ok: bool | None = None,
) -> LaneCAvailability:
    """Evaluate execution availability without mutating eligibility (D4')."""
    creds_ok = credentials_present(
        judge_api_key=judge_api_key,
        environ=environ,
        secret_resolver=secret_resolver,
    )
    client_ok = provider_client_constructible(
        credentials_ok=creds_ok,
        base_url=base_url,
        environ=environ,
        client_factory_ok=client_factory_ok,
    )
    available = bool(eligible and creds_ok and client_ok)

    reason: str | None = None
    gate_disposition: str | None = None
    execution_code: str | None = None
    if not eligible:
        # Availability is defined only on the eligible path; keep reason empty
        # so callers stamp cohort_ineligible from eligibility instead.
        reason = None
    elif not creds_ok:
        reason = EXEC_UNAVAILABLE_CREDS
        execution_code = EXEC_UNAVAILABLE_CREDS
        gate_disposition = GATE_JUDGE_UNAVAILABLE
    elif not client_ok:
        reason = EXEC_CLIENT_UNCONSTRUCTIBLE
        execution_code = EXEC_CLIENT_UNCONSTRUCTIBLE
        gate_disposition = GATE_JUDGE_UNAVAILABLE
    else:
        reason = None

    env = environ if environ is not None else os.environ
    base = base_url if base_url is not None else env.get(ENV_JUDGE_BASE_URL, "")
    evidence = {
        "eligible": bool(eligible),
        "credentials_present": creds_ok,
        "client_constructible": client_ok,
        "available": available,
        "base_url_configured": bool(str(base or "").strip()),
        # Never include raw secrets / key material.
        "secret_env": ENV_JUDGE_API_KEY,
        "raw_key_echoed": False,
    }
    return LaneCAvailability(
        eligible=bool(eligible),
        credentials_present=creds_ok,
        client_constructible=client_ok,
        available=available,
        reason=reason,
        gate_disposition=gate_disposition,
        execution_code=execution_code,
        evidence=evidence,
    )
