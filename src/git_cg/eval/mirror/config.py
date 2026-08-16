"""``git_cg_opik_config_v1`` resolution (FIND-022 / INT-09, plan §7.2.14).

Fail-closed environment-driven config for the S4 mirror. The resolved record
validates against the frozen ``git_cg_opik_config_v1`` schema.

Law:

* **Mode (D-mode):** ``GIT_CG_OPIK_MODE`` ∈ ``off|local|mirror|dogfood``
  (schema enum). Unset/empty ⇒ ``off``. Unknown token ⇒ fail closed to
  ``off`` **and** record the bad token in ``meta.mode_fallback`` so operators
  can diagnose misconfiguration without the mirror ever coming up ambiently.
* **Pinned project (no Default Project):** when mode is ``local``/``mirror``/
  ``dogfood`` a project name is **required** (schema ``allOf``). Resolution
  order: ``GIT_CG_OPIK_PROJECT_EVAL`` → ``OPIK_PROJECT_NAME``. Missing ⇒
  :class:`OpikConfigError` (``export_validation`` class) — never fall through
  to Opik's Default Project.
* **Redaction profile:** ``GIT_CG_OPIK_REDACTION_PROFILE`` must be a valid R14
  ladder token; unset ⇒ ``default_scrub`` (the non-owner export ceiling,
  §7.6). ``raw_dev_unsafe`` is **refused** here — it is owner-local debug only
  and never a valid export profile.
* **Flush bound:** ``GIT_CG_OPIK_FLUSH_TIMEOUT_MS`` positive int; default
  5000 ms. Invalid ⇒ fail closed to default (never hang a short-lived proc).
* **Secrets:** ``OPIK_API_KEY`` etc. are *never* read into this record — they
  are resolved at runtime by the transport layer (S4b) only. This record
  carries no secret material.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from git_cg.eval.enums import RedactionProfile
from git_cg.eval.schema_pack import validate_instance

__all__ = [
    "DEFAULT_FLUSH_TIMEOUT_MS",
    "ENV_FLUSH_TIMEOUT_MS",
    "ENV_MODE",
    "ENV_PROJECT_CI",
    "ENV_PROJECT_EVAL",
    "ENV_PROJECT_IMPORT",
    "ENV_PROJECT_LIVE",
    "ENV_REDACTION_PROFILE",
    "OPIK_ENV_PROJECT_NAME",
    "OpikConfigError",
    "OpikMode",
    "resolve_opik_config",
]

from enum import StrEnum


class OpikMode(StrEnum):
    """Schema-closed mirror modes (``git_cg_opik_config_v1``)."""

    OFF = "off"
    LOCAL = "local"
    MIRROR = "mirror"
    DOGFOOD = "dogfood"


#: Env switches (document; never commit values — §7.2.14).
ENV_MODE = "GIT_CG_OPIK_MODE"
ENV_PROJECT_LIVE = "GIT_CG_OPIK_PROJECT_LIVE"
ENV_PROJECT_EVAL = "GIT_CG_OPIK_PROJECT_EVAL"
ENV_PROJECT_CI = "GIT_CG_OPIK_PROJECT_CI"
ENV_PROJECT_IMPORT = "GIT_CG_OPIK_PROJECT_IMPORT"
ENV_REDACTION_PROFILE = "GIT_CG_OPIK_REDACTION_PROFILE"
ENV_FLUSH_TIMEOUT_MS = "GIT_CG_OPIK_FLUSH_TIMEOUT_MS"
OPIK_ENV_PROJECT_NAME = "OPIK_PROJECT_NAME"

#: Default bounded flush for short-lived hook processes (FIND-022).
DEFAULT_FLUSH_TIMEOUT_MS = 5000

#: Modes that require a pinned project (schema ``allOf``).
_PROJECT_REQUIRED_MODES = frozenset({OpikMode.LOCAL, OpikMode.MIRROR, OpikMode.DOGFOOD})

#: Profiles allowed on the export path. ``raw_dev_unsafe`` is owner-local
#: debug only and is refused here (plan §7.6: never default export).
_EXPORT_PROFILES = frozenset(p for p in RedactionProfile if p is not RedactionProfile.RAW_DEV_UNSAFE)


class OpikConfigError(ValueError):
    """Mirror config resolution failure (``export_validation`` class)."""


def _parse_mode(raw: str | None) -> tuple[OpikMode, str | None]:
    """Parse the mode token fail-closed.

    Returns ``(mode, bad_token)``; ``bad_token`` is the unrecognised raw value
    when we fell back to ``off`` so callers can surface it in ``meta``.
    """
    if raw is None:
        return OpikMode.OFF, None
    token = raw.strip().lower()
    if token == "":
        return OpikMode.OFF, None
    try:
        return OpikMode(token), None
    except ValueError:
        return OpikMode.OFF, token


def _parse_redaction_profile(raw: str | None) -> RedactionProfile:
    """Parse the R14 profile fail-closed to ``default_scrub``.

    ``raw_dev_unsafe`` and unknown tokens both fail closed — the export path
    ceiling for non-owner sinks is ``default_scrub`` (§7.6).
    """
    if raw is None:
        return RedactionProfile.DEFAULT_SCRUB
    token = raw.strip().lower()
    if token == "":
        return RedactionProfile.DEFAULT_SCRUB
    try:
        profile = RedactionProfile(token)
    except ValueError:
        return RedactionProfile.DEFAULT_SCRUB
    if profile not in _EXPORT_PROFILES:
        return RedactionProfile.DEFAULT_SCRUB
    return profile


def _parse_flush_timeout(raw: str | None) -> int:
    """Parse the flush bound fail-closed to the default (never hang)."""
    if raw is None:
        return DEFAULT_FLUSH_TIMEOUT_MS
    token = raw.strip()
    if token == "":
        return DEFAULT_FLUSH_TIMEOUT_MS
    try:
        value = int(token)
    except ValueError:
        return DEFAULT_FLUSH_TIMEOUT_MS
    return value if value >= 1 else DEFAULT_FLUSH_TIMEOUT_MS


def resolve_opik_config(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Resolve a schema-valid ``git_cg_opik_config_v1`` record from env.

    Parameters:
        env: Environment mapping to read; defaults to :data:`os.environ`.
            Tests pass an explicit mapping for determinism.

    Returns a validated config dict. When mode resolves to ``off`` the record
    carries no ``project_name`` (schema allows this; ``allOf`` only requires
    the project for active modes).

    Raises:
        OpikConfigError: an active mode (``local``/``mirror``/``dogfood``)
            resolved without a pinned project — ``export_validation`` class.
            This is fail-closed: we never fall through to Default Project.
    """
    source = os.environ if env is None else env

    mode, bad_token = _parse_mode(source.get(ENV_MODE))
    profile = _parse_redaction_profile(source.get(ENV_REDACTION_PROFILE))
    flush_timeout_ms = _parse_flush_timeout(source.get(ENV_FLUSH_TIMEOUT_MS))

    record: dict[str, Any] = {
        "schema_version": "git_cg_opik_config_v1",
        "id": "git_cg_opik_config_v1",
        "mode": mode.value,
        "redaction_profile": profile.value,
        "flush_timeout_ms": flush_timeout_ms,
    }

    meta: dict[str, Any] = {}
    if bad_token is not None:
        meta["mode_fallback"] = f"unrecognised {ENV_MODE}={bad_token!r}; fail-closed to off"
    if meta:
        record["meta"] = meta

    if mode in _PROJECT_REQUIRED_MODES:
        project = (source.get(ENV_PROJECT_EVAL) or source.get(OPIK_ENV_PROJECT_NAME) or "").strip()
        if not project:
            raise OpikConfigError(
                f"mode {mode.value!r} requires a pinned project "
                f"({ENV_PROJECT_EVAL} or {OPIK_ENV_PROJECT_NAME}); "
                "Default Project fallthrough is forbidden (FIND-022)"
            )
        record["project_name"] = project

    # Fail closed: the record we claim must validate against the frozen schema.
    validate_instance("git_cg_opik_config_v1", record)
    return record
