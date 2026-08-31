"""Runtime secret resolution for the S4 mirror (§7.2.14).

Secrets are resolved **only here, only at transport time**, via the product
:func:`git_cg.secrets.resolve_secret` pathway (environment → 1Password cache).
They are never read into ``git_cg_opik_config_v1``, never written to queue
rows, never logged, and never persisted under ``.eval/``.

Fail-closed law: a missing required secret raises :class:`MirrorSecretError`
(``export_auth`` class) so the exporter marks the queue row ``failed`` and
moves on — the product accept path is never touched.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from git_cg.secrets import resolve_secret

__all__ = [
    "MirrorSecretError",
    "OpikRuntimeSecrets",
    "ensure_secure_opik_endpoint",
    "resolve_opik_secrets",
]

#: Exact hostnames permitted for cleartext HTTP when an API key is present.
_LOCAL_HTTP_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


class MirrorSecretError(ValueError):
    """Required Opik secret could not be resolved (``export_auth`` class)."""


def ensure_secure_opik_endpoint(*, base_url: str | None, api_key: str | None) -> None:
    """Refuse cleartext remote Opik hosts when an API key is configured (CWE-319).

    HTTPS is always accepted. HTTP is allowed only when the *parsed hostname*
    is exactly ``localhost``, ``127.0.0.1``, or ``::1``. Substring matches such
    as ``http://localhost.attacker.example`` are rejected.
    """
    key = (api_key or "").strip()
    base = (base_url or "").strip()
    if not key or not base:
        return

    parsed = urlparse(base)
    scheme = (parsed.scheme or "").lower()
    host = (parsed.hostname or "").lower()
    if scheme == "https":
        return
    if scheme == "http" and host in _LOCAL_HTTP_HOSTS:
        return
    raise RuntimeError(
        "refusing non-HTTPS Opik endpoint while API key is configured "
        f"(base_url={base!r}); use HTTPS or a local http://localhost endpoint"
    )


@dataclass(frozen=True)
class OpikRuntimeSecrets:
    """Resolved runtime secrets. Never serialise, log, or persist."""

    api_key: str
    workspace: str | None
    base_url: str | None

    def __repr__(self) -> str:  # never leak the key into repr/logs
        """Secret-safe repr - never includes the API key material."""
        return "OpikRuntimeSecrets(api_key=<redacted>, workspace=..., base_url=...)"


def resolve_opik_secrets(*, require_key: bool = True) -> OpikRuntimeSecrets:
    """Resolve Opik runtime secrets via the product secret pathway.

    Parameters:
        require_key: when True (default), a missing ``OPIK_API_KEY`` raises
            :class:`MirrorSecretError` (``export_auth``). When False the key
            may be empty (e.g. local no-auth Opik).

    Returns an :class:`OpikRuntimeSecrets` holder. The caller must treat the
    values as ephemeral: pass to the transport, never store.
    """
    api_key = resolve_secret("OPIK_API_KEY", "")
    workspace = resolve_secret("OPIK_WORKSPACE", "") or None
    base_url = resolve_secret("OPIK_BASE_URL", "") or resolve_secret("OPIK_URL_OVERRIDE", "") or None

    if require_key and not api_key:
        raise MirrorSecretError(
            "OPIK_API_KEY could not be resolved (env / 1Password); export_auth — mirror cannot authenticate"
        )
    ensure_secure_opik_endpoint(base_url=base_url, api_key=api_key)
    return OpikRuntimeSecrets(api_key=api_key, workspace=workspace, base_url=base_url)
