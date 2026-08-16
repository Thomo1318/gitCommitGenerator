"""S4a config resolution tests (FIND-022 / git_cg_opik_config_v1)."""

from __future__ import annotations

import pytest

from git_cg.eval.mirror.config import (
    DEFAULT_FLUSH_TIMEOUT_MS,
    OpikConfigError,
    resolve_opik_config,
)


def test_mode_defaults_off_when_unset() -> None:
    cfg = resolve_opik_config(env={})
    assert cfg["mode"] == "off"
    assert "project_name" not in cfg  # off mode needs no project


def test_unknown_mode_fails_closed_to_off_and_records() -> None:
    cfg = resolve_opik_config(env={"GIT_CG_OPIK_MODE": "bogus"})
    assert cfg["mode"] == "off"
    assert "mode_fallback" in cfg["meta"]
    assert "bogus" in cfg["meta"]["mode_fallback"]


def test_active_mode_requires_pinned_project() -> None:
    with pytest.raises(OpikConfigError, match="Default Project"):
        resolve_opik_config(env={"GIT_CG_OPIK_MODE": "mirror"})


def test_active_mode_uses_eval_project_env() -> None:
    cfg = resolve_opik_config(env={"GIT_CG_OPIK_MODE": "mirror", "GIT_CG_OPIK_PROJECT_EVAL": "git-cg-eval"})
    assert cfg["mode"] == "mirror"
    assert cfg["project_name"] == "git-cg-eval"


def test_active_mode_falls_back_to_opik_project_name() -> None:
    cfg = resolve_opik_config(env={"GIT_CG_OPIK_MODE": "local", "OPIK_PROJECT_NAME": "local-proj"})
    assert cfg["project_name"] == "local-proj"


def test_redaction_profile_defaults_to_default_scrub() -> None:
    cfg = resolve_opik_config(env={})
    assert cfg["redaction_profile"] == "default_scrub"


def test_raw_dev_unsafe_refused_on_export() -> None:
    cfg = resolve_opik_config(env={"GIT_CG_OPIK_REDACTION_PROFILE": "raw_dev_unsafe"})
    assert cfg["redaction_profile"] == "default_scrub"  # fail closed


def test_unknown_profile_fails_closed() -> None:
    cfg = resolve_opik_config(env={"GIT_CG_OPIK_REDACTION_PROFILE": "yolo"})
    assert cfg["redaction_profile"] == "default_scrub"


def test_owner_profile_accepted() -> None:
    cfg = resolve_opik_config(env={"GIT_CG_OPIK_REDACTION_PROFILE": "train_rich"})
    assert cfg["redaction_profile"] == "train_rich"


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
    # resolve_opik_config validates internally; a valid return implies schema ok.
    cfg = resolve_opik_config(env={"GIT_CG_OPIK_MODE": "dogfood", "GIT_CG_OPIK_PROJECT_EVAL": "p"})
    assert cfg["schema_version"] == "git_cg_opik_config_v1"
