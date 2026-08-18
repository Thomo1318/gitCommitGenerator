"""``git_cg_opik_config_v1`` resolution (FIND-022 / INT-09, plan §7.2.14).

Fail-closed environment-driven config for the S4 mirror. The resolved record
validates against the frozen ``git_cg_opik_config_v1`` schema.

Law (plan §7.2.14 / §10.6 / P0-1):

* **Mode:** ``GIT_CG_OPIK_MODE`` ∈ ``off|local_only|mirror|strict_mirror``.
  Unset/empty ⇒ ``off``. Unknown token ⇒ fail closed to ``off`` **and**
  record the bad token in ``meta.mode_fallback`` (E12). Capture-off default
  stays safe, but operator surfaces (config show / export status / drain /
  composition) must treat ``meta.mode_fallback`` as ``ExportHealth.config_error``
  — never only a quiet ambient disable.
  Legacy parse aliases only: ``local`` → ``local_only``,
  ``dogfood`` → ``strict_mirror``. Canonical serialized form is plan vocabulary.
* **Environment:** ``development|dogfood|ci|eval|staging|production``
  (default ``development``). Unknown ⇒ default + ``meta.environment_fallback``.
* **Pinned projects (no Default Project):** when mode ≠ ``off``,
  ``projects.{live,eval,ci,import}`` are required. Resolution order for the
  eval lane: ``GIT_CG_OPIK_PROJECT_EVAL`` → ``OPIK_PROJECT_NAME``. Full lane
  set via ``GIT_CG_OPIK_PROJECT_{LIVE,EVAL,CI,IMPORT}``. Missing ⇒
  :class:`OpikConfigError` (``export_validation``) — never fall through to
  Opik's Default Project.
* **Redaction profile:** valid R14 ladder token; unset ⇒ ``default_scrub``.
  ``raw_dev_unsafe`` is **refused** here — owner-local debug only.
  Richer owner profiles (``private_message`` / ``train_rich`` /
  ``antipattern_vault``) require explicit ``GIT_CG_OPIK_OWNER_EXPORT=1`` and a
  non-CI environment (P1-6 / D14); otherwise fail closed to ``default_scrub``
  with a non-secret ``meta.redaction_profile_fallback`` diagnostic.
* **Flush bound:** positive int; default 5000 ms. Invalid ⇒ default.
* **Secrets:** never read into this record — transport resolves at runtime.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Final

from git_cg.eval.enums import RedactionProfile
from git_cg.eval.schema_pack import validate_instance

__all__ = [
    "CONFIG_SCHEMA",
    "DEFAULT_ENVIRONMENT",
    "DEFAULT_FLUSH_TIMEOUT_MS",
    "ENV_CHECK_TLS",
    "ENV_CONFIG_PATH",
    "ENV_ENDPOINT",
    "ENV_ENVIRONMENT",
    "ENV_FLUSH_TIMEOUT_MS",
    "ENV_MODE",
    "ENV_OWNER_EXPORT",
    "ENV_PROJECT_CI",
    "ENV_PROJECT_EVAL",
    "ENV_PROJECT_IMPORT",
    "ENV_PROJECT_LIVE",
    "ENV_REDACTION_PROFILE",
    "ENV_TRACK_DISABLE",
    "ENV_WORKSPACE",
    "OPIK_ENV_PROJECT_NAME",
    "OWNER_ONLY_REDACTION_PROFILES",
    "PROJECT_LANES",
    "OpikConfigError",
    "OpikEnvironment",
    "OpikMode",
    "mask_secret",
    "mode_fallback_token",
    "operator_config_health",
    "public_config_view",
    "resolve_opik_config",
]

CONFIG_SCHEMA: Final = "git_cg_opik_config_v1"

#: Env switches (document; never commit values — §7.2.14).
ENV_MODE = "GIT_CG_OPIK_MODE"
ENV_ENVIRONMENT = "GIT_CG_OPIK_ENVIRONMENT"
ENV_PROJECT_LIVE = "GIT_CG_OPIK_PROJECT_LIVE"
ENV_PROJECT_EVAL = "GIT_CG_OPIK_PROJECT_EVAL"
ENV_PROJECT_CI = "GIT_CG_OPIK_PROJECT_CI"
ENV_PROJECT_IMPORT = "GIT_CG_OPIK_PROJECT_IMPORT"
ENV_REDACTION_PROFILE = "GIT_CG_OPIK_REDACTION_PROFILE"
ENV_OWNER_EXPORT = "GIT_CG_OPIK_OWNER_EXPORT"
ENV_FLUSH_TIMEOUT_MS = "GIT_CG_OPIK_FLUSH_TIMEOUT_MS"
ENV_ENDPOINT = "GIT_CG_OPIK_ENDPOINT"
ENV_WORKSPACE = "GIT_CG_OPIK_WORKSPACE"
ENV_TRACK_DISABLE = "GIT_CG_OPIK_TRACK_DISABLE"
ENV_CHECK_TLS = "GIT_CG_OPIK_CHECK_TLS"
ENV_CONFIG_PATH = "GIT_CG_OPIK_CONFIG"
OPIK_ENV_PROJECT_NAME = "OPIK_PROJECT_NAME"

#: Default bounded flush for short-lived hook processes (FIND-022).
DEFAULT_FLUSH_TIMEOUT_MS = 5000
DEFAULT_ENVIRONMENT = "development"

PROJECT_LANES: Final[tuple[str, ...]] = ("live", "eval", "ci", "import")

#: Richer R14 profiles that require explicit owner export selection + non-CI (P1-6).
OWNER_ONLY_REDACTION_PROFILES: Final[frozenset[RedactionProfile]] = frozenset(
    {
        RedactionProfile.PRIVATE_MESSAGE,
        RedactionProfile.TRAIN_RICH,
        RedactionProfile.ANTIPATTERN_VAULT,
    }
)


# Legacy parse aliases → canonical plan vocabulary (P0-1).
_MODE_ALIASES: Final[Mapping[str, str]] = {
    "off": "off",
    "local": "local_only",
    "local_only": "local_only",
    "mirror": "mirror",
    "strict_mirror": "strict_mirror",
    "dogfood": "strict_mirror",
}


class OpikMode(StrEnum):
    """Canonical Opik integration modes (plan §10.6 / P0-1)."""

    OFF = "off"
    LOCAL_ONLY = "local_only"
    MIRROR = "mirror"
    STRICT_MIRROR = "strict_mirror"


class OpikEnvironment(StrEnum):
    """Closed environment vocabulary (plan §7.2.14)."""

    DEVELOPMENT = "development"
    DOGFOOD = "dogfood"
    CI = "ci"
    EVAL = "eval"
    STAGING = "staging"
    PRODUCTION = "production"


class OpikConfigError(ValueError):
    """Mirror config resolution failure (``export_validation`` class)."""


def _truthy(raw: str | None, default: bool) -> bool:
    """
    Parse an environment value as a boolean with a caller-provided fallback.
    
    Parameters:
        raw (str | None): The value to parse.
        default (bool): The value used when `raw` is missing, empty, or unrecognised.
    
    Returns:
        `True` for recognised true tokens, `False` for recognised false tokens, or `default` otherwise.
    """
    if raw is None or raw == "":
        return default
    token = raw.strip().lower()
    if token in {"1", "true", "yes", "on"}:
        return True
    if token in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_mode(raw: str | None) -> tuple[OpikMode, str | None, str | None]:
    """
    Parse a mode token into its canonical mode and diagnostic details.
    
    Parameters:
        raw (str | None): The raw mode value to parse.
    
    Returns:
        tuple[OpikMode, str | None, str | None]: The resolved mode, an unknown
        token when parsing fails, and the original token when a legacy alias was
        converted.
    """
    if raw is None:
        return OpikMode.OFF, None, None
    token = raw.strip().lower()
    if token == "":
        return OpikMode.OFF, None, None
    canonical = _MODE_ALIASES.get(token)
    if canonical is None:
        return OpikMode.OFF, token, None
    aliased_from = token if token != canonical else None
    return OpikMode(canonical), None, aliased_from


def _parse_environment(raw: str | None) -> tuple[OpikEnvironment, str | None]:
    """
    Parse an environment value and provide the configured default for blank or unknown input.
    
    Parameters:
    	raw (str | None): The environment value to parse.
    
    Returns:
    	tuple[OpikEnvironment, str | None]: The resolved environment and the unrecognised input token, or `None` when the input is valid or blank.
    """
    if raw is None or not str(raw).strip():
        return OpikEnvironment(DEFAULT_ENVIRONMENT), None
    token = str(raw).strip().lower()
    try:
        return OpikEnvironment(token), None
    except ValueError:
        return OpikEnvironment(DEFAULT_ENVIRONMENT), token


def _parse_redaction_profile(
    raw: str | None,
    *,
    owner_export: bool,
    environment: OpikEnvironment,
) -> tuple[RedactionProfile, str | None]:
    """
    Resolve a redaction profile while applying ownership and environment restrictions.
    
    Parameters:
    	raw (str | None): Requested redaction profile token.
    	owner_export (bool): Whether owner-only profiles are permitted.
    	environment (OpikEnvironment): Environment in which the profile will be used.
    
    Returns:
    	tuple[RedactionProfile, str | None]: The selected profile and a non-secret fallback reason, or ``None`` when no fallback was applied.
    """
    if raw is None:
        return RedactionProfile.DEFAULT_SCRUB, None
    token = raw.strip().lower()
    if token == "":
        return RedactionProfile.DEFAULT_SCRUB, None
    try:
        profile = RedactionProfile(token)
    except ValueError:
        return RedactionProfile.DEFAULT_SCRUB, f"unknown_profile:{token}"
    if profile is RedactionProfile.RAW_DEV_UNSAFE:
        return RedactionProfile.DEFAULT_SCRUB, "raw_dev_unsafe_refused"
    if profile in OWNER_ONLY_REDACTION_PROFILES:
        if not owner_export:
            return RedactionProfile.DEFAULT_SCRUB, f"owner_export_required:{profile.value}"
        if environment is OpikEnvironment.CI:
            return RedactionProfile.DEFAULT_SCRUB, f"owner_profile_blocked_in_ci:{profile.value}"
    return profile, None


def _parse_flush_timeout(raw: str | None) -> int:
    """
    Parse a flush timeout value with a safe default.
    
    Parameters:
    	raw (str | None): The configured timeout in milliseconds.
    
    Returns:
    	int: The positive timeout in milliseconds, or the default timeout when the value is missing, invalid, or less than one.
    """
    if raw is None or str(raw).strip() == "":
        return DEFAULT_FLUSH_TIMEOUT_MS
    try:
        value = int(str(raw).strip())
    except TypeError, ValueError:
        return DEFAULT_FLUSH_TIMEOUT_MS
    if value < 1:
        return DEFAULT_FLUSH_TIMEOUT_MS
    return value


def _resolve_projects(source: Mapping[str, str]) -> dict[str, str] | None:
    """
    Builds project assignments for the live, evaluation, CI, and import lanes.
    
    Parameters:
    	source (Mapping[str, str]): Environment-derived project settings.
    
    Returns:
    	dict[str, str] | None: A complete project-lane mapping, or `None` when no
    	projects are configured or the assignments are incomplete. A sole
    	evaluation project is assigned to all lanes.
    """
    live = (source.get(ENV_PROJECT_LIVE) or "").strip()
    eval_p = (source.get(ENV_PROJECT_EVAL) or source.get(OPIK_ENV_PROJECT_NAME) or "").strip()
    ci = (source.get(ENV_PROJECT_CI) or "").strip()
    import_p = (source.get(ENV_PROJECT_IMPORT) or "").strip()

    if eval_p and not any((live, ci, import_p)):
        return {"live": eval_p, "eval": eval_p, "ci": eval_p, "import": eval_p}

    projects = {"live": live, "eval": eval_p, "ci": ci, "import": import_p}
    if all(projects[lane] for lane in PROJECT_LANES):
        return projects
    if any(projects[lane] for lane in PROJECT_LANES):
        # Partial set is not enough — require full lanes or bootstrap.
        return None
    return None


def resolve_opik_config(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """
    Resolve the ``git_cg_opik_config_v1`` record from environment settings using fail-closed defaults.
    
    The returned record is suitable for schema validation, CLI rendering, and exporter consumption, and does not contain secrets.
    
    Raises:
        OpikConfigError: If an active mode lacks pinned project lanes.
    
    Returns:
        dict[str, Any]: The resolved configuration record.
    """
    source: Mapping[str, str] = env if env is not None else os.environ
    meta: dict[str, Any] = {}

    mode, bad_mode, aliased_from = _parse_mode(source.get(ENV_MODE))
    if bad_mode is not None:
        meta["mode_fallback"] = bad_mode
    if aliased_from is not None:
        meta["mode_aliased_from"] = aliased_from

    environment, bad_env = _parse_environment(source.get(ENV_ENVIRONMENT) or source.get("OPIK_ENVIRONMENT"))
    if bad_env is not None:
        meta["environment_fallback"] = bad_env

    owner_export = _truthy(source.get(ENV_OWNER_EXPORT), default=False)
    profile, profile_fallback = _parse_redaction_profile(
        source.get(ENV_REDACTION_PROFILE),
        owner_export=owner_export,
        environment=environment,
    )
    if profile_fallback is not None:
        meta["redaction_profile_fallback"] = profile_fallback
    if owner_export:
        meta["owner_export"] = True
    flush_timeout_ms = _parse_flush_timeout(source.get(ENV_FLUSH_TIMEOUT_MS))
    track_disable = _truthy(source.get(ENV_TRACK_DISABLE), default=False)
    # Default True when unset (safe TLS verify).
    check_tls = _truthy(source.get(ENV_CHECK_TLS), default=True)
    if source.get(ENV_CHECK_TLS) is None and source.get("OPIK_CHECK_TLS_CERTIFICATE") is not None:
        check_tls = _truthy(source.get("OPIK_CHECK_TLS_CERTIFICATE"), default=True)

    endpoint = (source.get(ENV_ENDPOINT) or source.get("OPIK_URL_OVERRIDE") or "").strip() or None
    workspace = (source.get(ENV_WORKSPACE) or source.get("OPIK_WORKSPACE") or "").strip() or None
    config_path = (source.get(ENV_CONFIG_PATH) or source.get("OPIK_CONFIG_PATH") or "").strip() or None

    record: dict[str, Any] = {
        "schema_version": CONFIG_SCHEMA,
        "id": CONFIG_SCHEMA,
        "mode": mode.value,
        "environment": environment.value,
        "redaction_profile": profile.value,
        "flush_timeout_ms": flush_timeout_ms,
        "track_disable": track_disable,
        "check_tls_certificate": check_tls,
    }
    if endpoint:
        record["endpoint"] = endpoint
    if workspace:
        record["workspace"] = workspace
    if config_path:
        record["config_path"] = config_path

    if mode is not OpikMode.OFF:
        projects = _resolve_projects(source)
        if projects is None:
            raise OpikConfigError(
                f"mode {mode.value!r} requires pinned projects.{{live,eval,ci,import}} "
                f"(set {ENV_PROJECT_EVAL} / {OPIK_ENV_PROJECT_NAME} or full lane env); "
                "no Default Project fallthrough"
            )
        record["projects"] = projects
        # Back-compat for drain/exporter call sites that still read project_name.
        record["project_name"] = projects["eval"]
    # else: off carries no projects (schema allOf only requires for active modes)

    if meta:
        record["meta"] = meta

    # Fail closed: the record we claim must validate.
    validate_instance(CONFIG_SCHEMA, {k: v for k, v in record.items() if k != "project_name"})
    # project_name is a non-schema convenience field for internal call sites;
    # strip it from the validated public shape is done above. Re-attach after.
    if "project_name" in record:
        # already present when active
        pass
    return record


def mode_fallback_token(record: Mapping[str, Any] | None) -> str | None:
    """
    Extracts the invalid mode token recorded during configuration resolution.
    
    Parameters:
    	record (Mapping[str, Any] | None): Configuration record to inspect.
    
    Returns:
    	str | None: The recorded mode token, or `None` when no fallback token is present.
    """
    if not isinstance(record, Mapping):
        return None
    meta = record.get("meta")
    if not isinstance(meta, Mapping):
        return None
    token = meta.get("mode_fallback")
    if token is None:
        return None
    text_token = str(token).strip()
    return text_token or None


def operator_config_health(record: Mapping[str, Any] | None) -> str:
    """
    Determine the operator-visible export health for a resolved configuration.
    
    Parameters:
        record (Mapping[str, Any] | None): Resolved configuration record, or ``None``.
    
    Returns:
        str: ``"config_error"`` for a mode fallback, ``"skipped_off"`` for disabled
            mode, ``"deferred"`` for local-only mode, or ``"pending"`` for other
            active modes.
    """
    # Local import keeps config free of hard health-module cycles at import time
    # for lightweight fixture helpers, while still returning stable §18.7 tokens.
    from git_cg.eval.mirror.health import ExportHealth

    if mode_fallback_token(record) is not None:
        return ExportHealth.CONFIG_ERROR.value
    mode = "off"
    if isinstance(record, Mapping):
        mode = str(record.get("mode") or "off")
    if mode == "off":
        return ExportHealth.SKIPPED_OFF.value
    if mode in {"local_only", "local"}:
        return ExportHealth.DEFERRED.value
    return ExportHealth.PENDING.value


def public_config_view(record: Mapping[str, Any]) -> dict[str, Any]:
    """
    Create a schema-shaped view containing only public configuration fields and metadata that does not appear secret-like.
    
    Parameters:
    	record (Mapping[str, Any]): Configuration record to filter.
    
    Returns:
    	dict[str, Any]: Public configuration fields with secret-like metadata keys excluded.
    """
    allowed = {
        "schema_version",
        "id",
        "mode",
        "environment",
        "projects",
        "endpoint",
        "workspace",
        "flush_timeout_ms",
        "track_disable",
        "check_tls_certificate",
        "config_path",
        "redaction_profile",
        "schema_pack",
        "metric_catalog",
        "notes",
        "meta",
    }
    out: dict[str, Any] = {}
    for key in allowed:
        if key not in record:
            continue
        value = record[key]
        if key == "meta" and isinstance(value, Mapping):
            out[key] = {k: v for k, v in value.items() if not _looks_like_secret_key(str(k))}
        else:
            out[key] = value
    return out


def _looks_like_secret_key(key: str) -> bool:
    """Identify metadata keys that suggest secret or credential values."""
    lowered = key.lower()
    return any(
        token in lowered
        for token in (
            "api_key",
            "apikey",
            "authorization",
            "password",
            "secret",
            "token",
            "credential",
        )
    )


def mask_secret(value: str | None) -> str | None:
    """
    Mask a secret while preserving its length for diagnostics.
    
    Parameters:
        value (str | None): Secret value to mask.
    
    Returns:
        str | None: A length-only mask, or `None` when `value` is `None`.
    """
    if value is None:
        return None
    return f"•••[len={len(value)}]"
