"""S4 config resolution tests (FIND-022 / git_cg_opik_config_v1 / P0-1 / S4-A)."""

from __future__ import annotations

import json
from pathlib import Path

import conftest as _cq
import pytest

from git_cg.eval.mirror.config import (
    DEFAULT_ENVIRONMENT,
    DEFAULT_FLUSH_TIMEOUT_MS,
    LaneSource,
    OpikConfigError,
    OpikEnvironment,
    OpikMode,
    mask_secret,
    mode_fallback_token,
    operator_config_health,
    public_config_view,
    resolve_lane_provenance,
    resolve_opik_config,
)
from git_cg.eval.mirror.health import EXPORT_HEALTH, ExportHealth
from git_cg.eval.mirror.result import (
    MirrorResult,
    build_mirror_result,
    evaluation_job_result,
    export_result,
)
from git_cg.eval.schema_pack import SchemaPackError, validate_instance

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def _load(name: str) -> dict:
    """Load a named JSON config fixture as a dict."""
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


# --- Mode / defaults -------------------------------------------------------


def test_mode_defaults_off_when_unset() -> None:
    cfg = resolve_opik_config(env={})
    assert cfg["mode"] == OpikMode.OFF
    assert cfg["environment"] == DEFAULT_ENVIRONMENT
    assert "projects" not in cfg
    assert "project_name" not in cfg


def test_unknown_mode_fails_closed_to_off_and_records() -> None:
    cfg = resolve_opik_config(env={"GIT_CG_OPIK_MODE": "bogus"})
    assert cfg["mode"] == "off"
    assert "mode_fallback" in cfg["meta"]
    assert "bogus" in cfg["meta"]["mode_fallback"]


def test_e12_invalid_mode_surfaces_config_error_health() -> None:
    """E12: unknown token remains capture-off, but operator health is config_error."""
    cfg = resolve_opik_config(env={"GIT_CG_OPIK_MODE": "bogus"})
    assert cfg["mode"] == "off"
    assert mode_fallback_token(cfg) == "bogus"
    assert operator_config_health(cfg) == ExportHealth.CONFIG_ERROR.value
    # Legitimate off (unset) stays skipped_off — not config_error.
    off = resolve_opik_config(env={})
    assert mode_fallback_token(off) is None
    assert operator_config_health(off) == ExportHealth.SKIPPED_OFF.value
    local = resolve_opik_config(env={"GIT_CG_OPIK_MODE": "local_only", "GIT_CG_OPIK_PROJECT_EVAL": "p"})
    assert operator_config_health(local) == ExportHealth.DEFERRED.value
    active = resolve_opik_config(env={"GIT_CG_OPIK_MODE": "mirror", "GIT_CG_OPIK_PROJECT_EVAL": "p"})
    assert operator_config_health(active) == ExportHealth.PENDING.value


def test_legacy_local_aliases_to_local_only() -> None:
    cfg = resolve_opik_config(env={"GIT_CG_OPIK_MODE": "local", "GIT_CG_OPIK_PROJECT_EVAL": "p"})
    assert cfg["mode"] == "local_only"
    assert cfg["meta"]["mode_aliased_from"] == "local"
    assert cfg["projects"]["eval"] == "p"


def test_legacy_dogfood_aliases_to_strict_mirror() -> None:
    cfg = resolve_opik_config(env={"GIT_CG_OPIK_MODE": "dogfood", "GIT_CG_OPIK_PROJECT_EVAL": "p"})
    assert cfg["mode"] == "strict_mirror"
    assert cfg["meta"]["mode_aliased_from"] == "dogfood"


def test_canonical_modes_accepted() -> None:
    for mode in ("off", "local_only", "mirror", "strict_mirror"):
        env: dict[str, str] = {"GIT_CG_OPIK_MODE": mode}
        if mode != "off":
            env["GIT_CG_OPIK_PROJECT_EVAL"] = "git-cg-eval"
        cfg = resolve_opik_config(env=env)
        assert cfg["mode"] == mode


# --- Projects / no Default Project (S4-A02/A03) ----------------------------


def test_active_mode_requires_pinned_project() -> None:
    with pytest.raises(OpikConfigError, match="Default Project"):
        resolve_opik_config(env={"GIT_CG_OPIK_MODE": "mirror"})


def test_active_mode_uses_eval_project_env_bootstraps_lanes() -> None:
    cfg = resolve_opik_config(env={"GIT_CG_OPIK_MODE": "mirror", "GIT_CG_OPIK_PROJECT_EVAL": "git-cg-eval"})
    assert cfg["mode"] == "mirror"
    assert cfg["projects"] == {
        "live": "git-cg-eval",
        "eval": "git-cg-eval",
        "ci": "git-cg-eval",
        "import": "git-cg-eval",
    }
    assert cfg["project_name"] == "git-cg-eval"


def test_full_lane_env_respected() -> None:
    cfg = resolve_opik_config(
        env={
            "GIT_CG_OPIK_MODE": "mirror",
            "GIT_CG_OPIK_PROJECT_LIVE": "L",
            "GIT_CG_OPIK_PROJECT_EVAL": "E",
            "GIT_CG_OPIK_PROJECT_CI": "C",
            "GIT_CG_OPIK_PROJECT_IMPORT": "I",
        }
    )
    assert cfg["projects"] == {"live": "L", "eval": "E", "ci": "C", "import": "I"}


def test_active_mode_falls_back_to_opik_project_name() -> None:
    cfg = resolve_opik_config(env={"GIT_CG_OPIK_MODE": "local_only", "OPIK_PROJECT_NAME": "local-proj"})
    assert cfg["projects"]["eval"] == "local-proj"
    assert cfg["project_name"] == "local-proj"


def test_partial_lanes_do_not_silently_default() -> None:
    with pytest.raises(OpikConfigError, match="Default Project"):
        resolve_opik_config(
            env={
                "GIT_CG_OPIK_MODE": "mirror",
                "GIT_CG_OPIK_PROJECT_LIVE": "only-live",
            }
        )


# --- Environment -----------------------------------------------------------


def test_environment_default_and_override() -> None:
    assert resolve_opik_config(env={})["environment"] == "development"
    cfg = resolve_opik_config(env={"GIT_CG_OPIK_ENVIRONMENT": "ci"})
    assert cfg["environment"] == OpikEnvironment.CI


def test_unknown_environment_fails_closed() -> None:
    cfg = resolve_opik_config(env={"GIT_CG_OPIK_ENVIRONMENT": "lab"})
    assert cfg["environment"] == "development"
    assert cfg["meta"]["environment_fallback"] == "lab"


# --- Redaction / flush -----------------------------------------------------


def test_redaction_profile_defaults_to_default_scrub() -> None:
    cfg = resolve_opik_config(env={})
    assert cfg["redaction_profile"] == "default_scrub"


def test_raw_dev_unsafe_refused_on_export() -> None:
    cfg = resolve_opik_config(env={"GIT_CG_OPIK_REDACTION_PROFILE": "raw_dev_unsafe"})
    assert cfg["redaction_profile"] == "default_scrub"
    assert cfg["meta"]["redaction_profile_fallback"] == "raw_dev_unsafe_refused"


def test_unknown_profile_fails_closed() -> None:
    cfg = resolve_opik_config(env={"GIT_CG_OPIK_REDACTION_PROFILE": "yolo"})
    assert cfg["redaction_profile"] == "default_scrub"
    assert cfg["meta"]["redaction_profile_fallback"] == "unknown_profile:yolo"


def test_owner_profile_requires_owner_export_flag() -> None:
    """P1-6: richer profiles without owner flag fall closed to default_scrub."""
    cfg = resolve_opik_config(env={"GIT_CG_OPIK_REDACTION_PROFILE": "train_rich"})
    assert cfg["redaction_profile"] == "default_scrub"
    assert cfg["meta"]["redaction_profile_fallback"] == "owner_export_required:train_rich"


def test_owner_profile_accepted_with_owner_export_non_ci() -> None:
    """P1-6: train_rich allowed with explicit owner export + non-CI env."""
    cfg = resolve_opik_config(
        env={
            "GIT_CG_OPIK_REDACTION_PROFILE": "train_rich",
            "GIT_CG_OPIK_OWNER_EXPORT": "1",
            "GIT_CG_OPIK_ENVIRONMENT": "dogfood",
        }
    )
    assert cfg["redaction_profile"] == "train_rich"
    assert cfg["meta"]["owner_export"] is True
    assert "redaction_profile_fallback" not in cfg.get("meta", {})


def test_owner_profile_blocked_in_ci_even_with_owner_flag() -> None:
    """P1-6: CI sinks stay thin — owner flag cannot unlock train_rich in ci."""
    cfg = resolve_opik_config(
        env={
            "GIT_CG_OPIK_REDACTION_PROFILE": "train_rich",
            "GIT_CG_OPIK_OWNER_EXPORT": "true",
            "GIT_CG_OPIK_ENVIRONMENT": "ci",
        }
    )
    assert cfg["redaction_profile"] == "default_scrub"
    assert cfg["meta"]["redaction_profile_fallback"] == "owner_profile_blocked_in_ci:train_rich"


def test_thin_profiles_available_without_owner() -> None:
    for profile in ("public_ci", "message_only", "default_scrub", "meta_eval_scrub"):
        cfg = resolve_opik_config(env={"GIT_CG_OPIK_REDACTION_PROFILE": profile})
        assert cfg["redaction_profile"] == profile, profile


def test_private_message_and_antipattern_also_owner_gated() -> None:
    for profile in ("private_message", "antipattern_vault"):
        cfg = resolve_opik_config(env={"GIT_CG_OPIK_REDACTION_PROFILE": profile})
        assert cfg["redaction_profile"] == "default_scrub", profile
        assert "owner_export_required" in cfg["meta"]["redaction_profile_fallback"]


def test_flush_timeout_default_and_override() -> None:
    assert resolve_opik_config(env={})["flush_timeout_ms"] == DEFAULT_FLUSH_TIMEOUT_MS
    assert resolve_opik_config(env={"GIT_CG_OPIK_FLUSH_TIMEOUT_MS": "12000"})["flush_timeout_ms"] == 12000


def test_flush_timeout_invalid_fails_closed() -> None:
    assert (
        resolve_opik_config(env={"GIT_CG_OPIK_FLUSH_TIMEOUT_MS": "abc"})["flush_timeout_ms"] == DEFAULT_FLUSH_TIMEOUT_MS
    )
    assert (
        resolve_opik_config(env={"GIT_CG_OPIK_FLUSH_TIMEOUT_MS": "0"})["flush_timeout_ms"] == DEFAULT_FLUSH_TIMEOUT_MS
    )


def test_record_validates_against_schema() -> None:
    cfg = resolve_opik_config(env={"GIT_CG_OPIK_MODE": "strict_mirror", "GIT_CG_OPIK_PROJECT_EVAL": "p"})
    assert cfg["schema_version"] == "git_cg_opik_config_v1"
    public = public_config_view(cfg)
    validate_instance("git_cg_opik_config_v1", public)


def test_off_and_local_only_never_require_network_fields() -> None:
    off = resolve_opik_config(env={"GIT_CG_OPIK_MODE": "off"})
    assert off["mode"] == "off"
    local = resolve_opik_config(env={"GIT_CG_OPIK_MODE": "local_only", "GIT_CG_OPIK_PROJECT_EVAL": "p"})
    assert local["mode"] == "local_only"
    # No endpoint required
    assert "endpoint" not in local


def test_public_config_view_strips_separator_secret_key_variants() -> None:
    """Hyphen/space secret meta keys must not appear in public config show."""
    from git_cg.eval.mirror.config import _looks_like_secret_key

    for key in ("x-api-key", "api-key", "api_key", "API Key", "x_api_key"):
        assert _looks_like_secret_key(key), key
    assert not _looks_like_secret_key("schema_pack")
    assert not _looks_like_secret_key("project_lane")

    view = public_config_view(
        {
            "schema_version": "git_cg_opik_config_v1",
            "id": "cfg_test",
            "mode": "off",
            "meta": {
                "x-api-key": "should-never-show",
                "api-key": "also-hidden",
                "note": "safe",
            },
        }
    )
    meta = view["meta"]
    assert "x-api-key" not in meta
    assert "api-key" not in meta
    assert meta["note"] == "safe"
    blob = json.dumps(view)
    assert "should-never-show" not in blob
    assert "also-hidden" not in blob


def test_public_config_view_strips_internal_project_name() -> None:
    """Public view must omit internal project/API key material."""
    cfg = resolve_opik_config(env={"GIT_CG_OPIK_MODE": "mirror", "GIT_CG_OPIK_PROJECT_EVAL": "p"})
    view = public_config_view(cfg)
    assert "project_name" not in view
    assert "projects" in view
    assert "api_key" not in json.dumps(view)


def test_mask_secret_never_leaks_prefix() -> None:
    masked = mask_secret("sk-super-secret-value")
    assert masked == "•••[len=21]"
    assert "sk-" not in masked
    assert mask_secret(None) is None


# --- Schema fixtures (S4-A01/A05 / E3) --------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "git_cg_opik_config.good.off.json",
        "git_cg_opik_config.good.mirror.json",
        "git_cg_opik_config.good.local_only.json",
        "git_cg_opik_config.good.strict_mirror.json",
    ],
)
def test_s4_a01_valid_config_fixtures(name: str) -> None:
    record = _load(name)
    validate_instance("git_cg_opik_config_v1", record)
    # Secret-bearing fields never in committed fixtures (S4-A05).
    blob = json.dumps(record)
    for bad in ("api_key", "OPIK_API_KEY", "password", "authorization"):
        assert bad not in blob


def test_s4_a02_missing_project_fails_schema() -> None:
    with pytest.raises(SchemaPackError):
        validate_instance(
            "git_cg_opik_config_v1",
            _load("git_cg_opik_config.bad.missing_project.json"),
        )


def test_e3_schema_keeps_additional_properties_false_and_blocks_raw_dev() -> None:
    schema_path = Path(__file__).resolve().parents[3] / "schemas" / "eval" / "git_cg_opik_config_v1.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema.get("additionalProperties") is False
    # redaction_profile exclusion survives re-freeze
    redaction = schema["properties"]["redaction_profile"]
    assert "not" in redaction or (
        isinstance(redaction, dict)
        and any("not" in (clause if isinstance(clause, dict) else {}) for clause in redaction.get("allOf", []))
    )
    with pytest.raises(SchemaPackError):
        validate_instance(
            "git_cg_opik_config_v1",
            _load("git_cg_opik_config.bad.raw_dev_unsafe.json"),
        )


# --- ExportHealth + MirrorResult (E1 / P0-7 / P1-5) -------------------------


def test_e1_export_health_closed_vocabulary() -> None:
    expected = {
        "skipped_off",
        "deferred",
        "pending",
        "success",
        "config_error",
        "auth_error",
        "network_error",
        "timeout",
        "partial",
        "replay_needed",
    }
    assert set(EXPORT_HEALTH) == expected
    assert len(EXPORT_HEALTH) == len(set(EXPORT_HEALTH))


def test_p0_7_mirror_result_product_accept_never_blocked() -> None:
    result = build_mirror_result(
        mode="strict_mirror",
        health=ExportHealth.AUTH_ERROR,
        attempted=1,
        failed=1,
        error_classes=("export_auth",),
        notes=("secret_resolution_failed",),
    )
    assert isinstance(result, MirrorResult)
    assert result.product_accept_blocked is False
    assert result.strict_mirror_failed is True
    payload = result.to_dict()
    assert payload["product_accept_blocked"] is False
    assert payload["strict_mirror_failed"] is True
    assert payload["health"] == "auth_error"


def test_p1_5_dual_axis_names() -> None:
    ok = build_mirror_result(mode="mirror", health=ExportHealth.SUCCESS, succeeded=2, attempted=2)
    er = export_result(ok)
    ej = evaluation_job_result(ok)
    assert er["axis"] == "export_result"
    assert er["product_accept_blocked"] is False
    assert ej["axis"] == "evaluation_job_result"
    assert ej["ok"] is True

    bad = build_mirror_result(
        mode="strict_mirror",
        health=ExportHealth.NETWORK_ERROR,
        attempted=1,
        failed=1,
        error_classes=("export_network",),
    )
    ej_bad = evaluation_job_result(bad)
    assert ej_bad["ok"] is False
    assert ej_bad["strict_mirror_failed"] is True
    # mirror mode never fails eval job axis solely from export noise if not strict
    mirror_fail = build_mirror_result(
        mode="mirror",
        health=ExportHealth.NETWORK_ERROR,
        attempted=1,
        failed=1,
        error_classes=("export_network",),
    )
    assert evaluation_job_result(mirror_fail)["ok"] is True


def test_off_mode_mirror_result_skipped() -> None:
    result = build_mirror_result(mode="off", notes=("skipped_off",))
    assert result.health is ExportHealth.SKIPPED_OFF
    assert result.strict_mirror_failed is False


def test_build_mirror_result_preserves_generator_notes() -> None:
    """Generator notes must survive health inference and result storage."""

    def note_gen():
        """Yield diagnostic notes (generator materialization tests)."""
        yield "diag_one"
        yield "diag_two"

    result = build_mirror_result(
        mode="mirror",
        attempted=1,
        succeeded=1,
        notes=note_gen(),
    )
    assert result.notes == ("diag_one", "diag_two")
    assert "diag_one" in export_result(result)["notes"]
    assert "diag_two" in evaluation_job_result(result)["notes"]


# --- Boolean env parsing ---------------------------------------------------


def test_truthy_unknown_token_keeps_default_true_for_tls() -> None:
    """Unknown non-empty tokens must not silently disable TLS (default True)."""
    cfg = resolve_opik_config(env={"GIT_CG_OPIK_CHECK_TLS": "garbage"})
    assert cfg["check_tls_certificate"] is True


def test_truthy_explicit_false_tokens() -> None:
    for token in ("0", "false", "no", "off", "FALSE", " Off "):
        cfg = resolve_opik_config(env={"GIT_CG_OPIK_CHECK_TLS": token})
        assert cfg["check_tls_certificate"] is False, token


def test_truthy_explicit_true_tokens() -> None:
    for token in ("1", "true", "yes", "on", "TRUE", " Yes "):
        cfg = resolve_opik_config(env={"GIT_CG_OPIK_CHECK_TLS": token})
        assert cfg["check_tls_certificate"] is True, token


def test_truthy_empty_keeps_default() -> None:
    cfg = resolve_opik_config(env={"GIT_CG_OPIK_CHECK_TLS": ""})
    assert cfg["check_tls_certificate"] is True


# --- S7-1a: per-lane project-pin provenance (diagnostic-only) -------------

# Lane-pin env scrubbing is shared via tests/conftest.py (scrub_opik_project_lanes).


class TestLaneProvenance:
    """resolve_lane_provenance mirrors _resolve_projects precedence."""

    def test_empty_env_all_missing(self, monkeypatch) -> None:
        _cq.scrub_opik_project_lanes(monkeypatch)
        pins = resolve_lane_provenance()
        assert set(pins) == {"live", "eval", "ci", "import"}
        for lane, pin in pins.items():
            assert pin.lane == lane
            assert pin.source is LaneSource.MISSING
            assert pin.value is None
            assert pin.origin_env_var is None
            assert pin.env_var == f"GIT_CG_OPIK_PROJECT_{lane.upper()}"

    def test_eval_only_bootstraps_all_lanes(self, monkeypatch) -> None:
        _cq.scrub_opik_project_lanes(monkeypatch)
        monkeypatch.setenv("GIT_CG_OPIK_PROJECT_EVAL", "  proj-x  ")
        pins = resolve_lane_provenance()
        assert all(p.source is LaneSource.BOOTSTRAP_EVAL for p in pins.values())
        assert all(p.value == "proj-x" for p in pins.values())  # stripped
        assert all(p.origin_env_var == "GIT_CG_OPIK_PROJECT_EVAL" for p in pins.values())

    def test_legacy_only_bootstraps_all_lanes(self, monkeypatch) -> None:
        _cq.scrub_opik_project_lanes(monkeypatch)
        monkeypatch.setenv("OPIK_PROJECT_NAME", "legacy-proj")
        pins = resolve_lane_provenance()
        assert all(p.source is LaneSource.BOOTSTRAP_LEGACY for p in pins.values())
        assert all(p.value == "legacy-proj" for p in pins.values())
        assert all(p.origin_env_var == "OPIK_PROJECT_NAME" for p in pins.values())

    def test_full_explicit_lanes(self, monkeypatch) -> None:
        _cq.scrub_opik_project_lanes(monkeypatch)
        monkeypatch.setenv("GIT_CG_OPIK_PROJECT_LIVE", "l")
        monkeypatch.setenv("GIT_CG_OPIK_PROJECT_EVAL", "e")
        monkeypatch.setenv("GIT_CG_OPIK_PROJECT_CI", "c")
        monkeypatch.setenv("GIT_CG_OPIK_PROJECT_IMPORT", "i")
        pins = resolve_lane_provenance()
        for lane, pin in pins.items():
            assert pin.source is LaneSource.EXPLICIT
            assert pin.value == lane[0]  # l/e/c/i
            assert pin.origin_env_var == pin.env_var

    def test_partial_marks_unset_lanes_missing(self, monkeypatch) -> None:
        _cq.scrub_opik_project_lanes(monkeypatch)
        monkeypatch.setenv("GIT_CG_OPIK_PROJECT_LIVE", "l")
        monkeypatch.setenv("GIT_CG_OPIK_PROJECT_EVAL", "e")
        pins = resolve_lane_provenance()
        assert pins["live"].source is LaneSource.EXPLICIT
        assert pins["eval"].source is LaneSource.EXPLICIT
        assert pins["ci"].source is LaneSource.MISSING
        assert pins["import"].source is LaneSource.MISSING

    def test_legacy_fills_eval_lane_in_partial_mix(self, monkeypatch) -> None:
        _cq.scrub_opik_project_lanes(monkeypatch)
        monkeypatch.setenv("GIT_CG_OPIK_PROJECT_LIVE", "l")
        monkeypatch.setenv("OPIK_PROJECT_NAME", "legacy-proj")
        pins = resolve_lane_provenance()
        assert pins["live"].source is LaneSource.EXPLICIT
        assert pins["eval"].source is LaneSource.LEGACY
        assert pins["eval"].value == "legacy-proj"
        assert pins["eval"].origin_env_var == "OPIK_PROJECT_NAME"
        assert pins["ci"].source is LaneSource.MISSING

    def test_explicit_mapping_does_not_touch_os_environ(self, monkeypatch) -> None:
        """Explicit source mapping is used verbatim (pure, testable)."""
        _cq.scrub_opik_project_lanes(monkeypatch)
        monkeypatch.setenv("GIT_CG_OPIK_PROJECT_LIVE", "from-os-environ")
        pins = resolve_lane_provenance({"GIT_CG_OPIK_PROJECT_EVAL": "mapped"})
        assert all(p.value == "mapped" for p in pins.values())
        assert all(p.source is LaneSource.BOOTSTRAP_EVAL for p in pins.values())
