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

from git_cg.secrets import resolve_secret

__all__ = ["MirrorSecretError", "OpikRuntimeSecrets", "resolve_opik_secrets"]


class MirrorSecretError(ValueError):
    """Required Opik secret could not be resolved (``export_auth`` class)."""


@dataclass(frozen=True)
class OpikRuntimeSecrets:
    """Resolved runtime secrets. Never serialise, log, or persist."""

    api_key: str
    workspace: str | None
    base_url: str | None

    def __repr__(self) -> str:  # never leak the key into repr/logs
        """
        Return a redacted representation of the runtime Opik secrets.
        
        Returns:
        	str: A representation that omits the API key value.
        """
        return "OpikRuntimeSecrets(api_key=<redacted>, workspace=..., base_url=...)"


def resolve_opik_secrets(*, require_key: bool = True) -> OpikRuntimeSecrets:
    """
    Resolve the runtime credentials and connection details used to access Opik.
    
    Parameters:
        require_key (bool): Whether an API key is required. When true, raises
            MirrorSecretError if OPIK_API_KEY cannot be resolved.
    
    Returns:
        OpikRuntimeSecrets: The resolved API key, workspace, and base URL.
    
    Raises:
        MirrorSecretError: If require_key is true and OPIK_API_KEY is unavailable.
    """
    api_key = resolve_secret("OPIK_API_KEY", "")
    workspace = resolve_secret("OPIK_WORKSPACE", "") or None
    base_url = resolve_secret("OPIK_BASE_URL", "") or resolve_secret("OPIK_URL_OVERRIDE", "") or None

    if require_key and not api_key:
        raise MirrorSecretError(
            "OPIK_API_KEY could not be resolved (env / 1Password); export_auth — mirror cannot authenticate"
        )
    return OpikRuntimeSecrets(api_key=api_key, workspace=workspace, base_url=base_url)
