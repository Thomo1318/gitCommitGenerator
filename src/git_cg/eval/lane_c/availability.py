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
    """
    Determine whether a judge API key is available.
    
    Parameters:
        judge_api_key (str | None): Explicit API key to check before other sources.
        environ (Mapping[str, str] | None): Environment mapping containing the configured judge API key.
        secret_resolver (SecretResolver | None): Resolver used when no explicit key or environment mapping is supplied.
    
    Returns:
        bool: `True` if a non-empty key is available, `False` otherwise. Resolver errors are treated as unavailable credentials.
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
    """
    Determine whether a provider client is constructible.
    
    Parameters:
        credentials_ok (bool): Whether the required provider credentials are present.
        base_url (str | None): Optional provider endpoint; it does not affect constructibility.
        environ (Mapping[str, str] | None): Optional environment settings; they do not affect constructibility.
        client_factory_ok (bool | None): Explicitly forces failure when set to ``False``.
    
    Returns:
        bool: ``True`` if credentials are present and client construction is permitted, ``False`` otherwise.
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
    """
    Evaluate judge execution availability without changing eligibility.
    
    Parameters:
    	eligible (bool): Whether the input is eligible for judge execution.
    	judge_api_key (str | None): Optional API key to use for credential detection.
    	base_url (str | None): Optional judge service base URL.
    	environ (Mapping[str, str] | None): Optional environment mapping used for configuration.
    	secret_resolver (SecretResolver | None): Optional resolver for retrieving the API key.
    	client_factory_ok (bool | None): Optional result controlling client constructibility.
    
    Returns:
    	(LaneCAvailability): Execution availability, gate disposition, reason codes, and non-secret evidence.
    """
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
