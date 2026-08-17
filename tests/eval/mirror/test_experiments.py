"""S4b experiment_v1 naming + pin records (incl. P1-12 network SHA gate)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

# Back-compat private alias still exported via module attribute.
from git_cg.eval.mirror import experiments as exp_mod
from git_cg.eval.mirror.experiments import (
    UNRESOLVED_GIT_SHA,
    ExperimentPins,
    ExportGitShaError,
    build_experiment,
    build_experiment_pins,
    experiment_name,
    is_unresolved_git_sha,
    require_resolved_git_sha,
    resolve_git_sha,
)
from git_cg.eval.schema_pack import validate_instance

_UNRESOLVED_SHA = exp_mod._UNRESOLVED_SHA


class TestExperimentName:
    def test_format(self) -> None:
        when = datetime(2026, 8, 16, 12, 0, 0, tzinfo=UTC)
        name = experiment_name("mirror", "v0", "abc1234", when)
        assert name == "eval_mirror_v0_abc1234_20260816T120000Z"

    def test_slugifies_lane_and_catalog(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=UTC)
        name = experiment_name("My Lane!", "V 1.2", "deadbeef", when)
        assert name.startswith("eval_my_lane_v_1_2_deadbeef_")

    def test_git_sha_used_verbatim(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=UTC)
        name = experiment_name("lane", "v0", "ABCdef123", when)
        assert "ABCdef123" in name


class TestResolveGitSha:
    def test_returns_hex_in_repo(self) -> None:
        sha = resolve_git_sha()
        # In the real repo this is a hex SHA; the zeroed sentinel is also hex.
        assert all(c in "0123456789abcdef" for c in sha)
        assert 7 <= len(sha) <= 64

    def test_unresolvable_returns_zeroed_sentinel(self, tmp_path) -> None:
        # A non-repo directory → git fails → zeroed sentinel (never raises).
        sha = resolve_git_sha(repo_root=tmp_path)
        assert sha == _UNRESOLVED_SHA
        assert sha == UNRESOLVED_GIT_SHA
        assert all(c in "0123456789abcdef" for c in sha)


class TestUnresolvedGitShaGate:
    def test_is_unresolved_detects_zeroed_and_empty(self) -> None:
        assert is_unresolved_git_sha(UNRESOLVED_GIT_SHA)
        assert is_unresolved_git_sha("0" * 12)
        assert is_unresolved_git_sha("")
        assert is_unresolved_git_sha(None)
        assert not is_unresolved_git_sha("abc1234")

    def test_require_allows_local_diag_zeroed(self, tmp_path) -> None:
        sha = require_resolved_git_sha(repo_root=tmp_path, network_export=False)
        assert sha == UNRESOLVED_GIT_SHA

    def test_require_refuses_network_export_zeroed(self, tmp_path) -> None:
        with pytest.raises(ExportGitShaError, match="export_validation") as ei:
            require_resolved_git_sha(repo_root=tmp_path, network_export=True)
        assert ei.value.error_class == "export_validation"

    def test_require_refuses_explicit_zeroed_for_network(self) -> None:
        with pytest.raises(ExportGitShaError, match="unresolved git SHA"):
            require_resolved_git_sha(UNRESOLVED_GIT_SHA, network_export=True)

    def test_require_accepts_resolved_for_network(self) -> None:
        assert require_resolved_git_sha("deadbeefcafebabe", network_export=True) == "deadbeefcafebabe"

    def test_build_experiment_network_export_refuses_unresolved(self, tmp_path) -> None:
        with pytest.raises(ExportGitShaError, match="export_validation"):
            build_experiment("mirror", "v0", repo_root=tmp_path, network_export=True)

    def test_build_experiment_local_still_accepts_zeroed(self, tmp_path) -> None:
        record = build_experiment("mirror", "v0", repo_root=tmp_path, network_export=False)
        assert record["git_sha"] == UNRESOLVED_GIT_SHA


class TestBuildExperiment:
    def test_schema_valid(self) -> None:
        record = build_experiment("mirror", "v0", git_sha="abc1234")
        validate_instance("experiment_v1", record)
        assert record["schema_version"] == "experiment_v1"
        assert record["lane"] == "mirror"
        assert record["git_sha"] == "abc1234"

    def test_carries_pin_set(self) -> None:
        record = build_experiment("mirror", "v0", git_sha="abc1234")
        assert "@" in record["catalog_pin"]
        assert "@" in record["metric_catalog"]
        assert "@" in record["schema_pack"]

    def test_id_matches_experiment_name(self) -> None:
        record = build_experiment("mirror", "v0", git_sha="abc1234")
        assert record["id"] == record["experiment_name"]

    def test_meta_additive(self) -> None:
        record = build_experiment("mirror", "v0", git_sha="abc1234", meta={"k": "v"})
        assert record["meta"]["k"] == "v"
        assert "pins" in record["meta"]
        assert record["meta"]["pins"]["git_sha"] == "abc1234"

    def test_default_git_sha_resolves(self) -> None:
        record = build_experiment("mirror", "v0")
        assert all(c in "0123456789abcdef" for c in record["git_sha"])


class TestExperimentsModuleSyntax:
    def test_module_imports_cleanly(self) -> None:
        """P0-6 — invalid except syntax must not prevent import."""
        import git_cg.eval.mirror.experiments as exp

        assert callable(exp.resolve_git_sha)
        assert callable(exp.build_experiment)
        assert callable(exp.require_resolved_git_sha)


class TestExperimentPins:
    def test_build_pins_explicit_nulls(self) -> None:
        pins = build_experiment_pins(lane="mirror", catalog_version="v0", git_sha="abc1234")
        assert isinstance(pins, ExperimentPins)
        data = pins.to_dict()
        # N/A optional fields are present keys with null, not omitted.
        assert "prompt_pack_hash" in data
        assert data["prompt_pack_hash"] is None
        assert data["engine"] is None
        assert data["model"] is None
        assert data["lane"] == "mirror"
        assert data["git_sha"] == "abc1234"
        assert data["schema_pack"] and "@" in data["schema_pack"]
        assert data["metric_catalog"] and "@" in data["metric_catalog"]
        assert data["harness_version"]

    def test_build_experiment_embeds_pins(self) -> None:
        record = build_experiment(
            "mirror",
            "v0",
            git_sha="abc1234",
            environment="eval",
            project="git-cg-eval",
            dataset_id="corpus",
            redaction_profile="default_scrub",
        )
        pins = record["meta"]["pins"]
        assert pins["environment"] == "eval"
        assert pins["project"] == "git-cg-eval"
        assert pins["dataset_id"] == "corpus"
        assert pins["redaction_profile"] == "default_scrub"
        assert pins["artifact_class"] == "export_batch"
        assert pins["prompt_pack_hash"] is None


class TestExperimentNameCollisionGuard:
    def test_same_second_different_content_diverges(self) -> None:
        when = datetime(2026, 8, 16, 12, 0, 0, tzinfo=UTC)
        a = build_experiment("mirror", "v0", git_sha="abc1234", when=when, content_key="one")
        b = build_experiment("mirror", "v0", git_sha="abc1234", when=when, content_key="two")
        assert a["experiment_name"] != b["experiment_name"]
        assert a["experiment_name"].startswith("eval_mirror_v0_abc1234_20260816T120000Z_")
        assert b["experiment_name"].startswith("eval_mirror_v0_abc1234_20260816T120000Z_")

    def test_same_content_same_second_stable(self) -> None:
        when = datetime(2026, 8, 16, 12, 0, 0, tzinfo=UTC)
        a = build_experiment("mirror", "v0", git_sha="abc1234", when=when, content_key="same")
        b = build_experiment("mirror", "v0", git_sha="abc1234", when=when, content_key="same")
        assert a["experiment_name"] == b["experiment_name"]

    def test_bare_experiment_name_without_guard(self) -> None:
        when = datetime(2026, 8, 16, 12, 0, 0, tzinfo=UTC)
        assert experiment_name("mirror", "v0", "abc1234", when) == "eval_mirror_v0_abc1234_20260816T120000Z"

    def test_same_second_json_like_content_keys_do_not_collide_after_hex_strip(self) -> None:
        """Non-hex content keys must hash fully — stripping non-hex can collide."""
        when = datetime(2026, 8, 16, 12, 0, 0, tzinfo=UTC)
        a = build_experiment(
            "mirror",
            "v0",
            git_sha="abc1234",
            when=when,
            content_key='{"a":1,"b":2}',
        )
        b = build_experiment(
            "mirror",
            "v0",
            git_sha="abc1234",
            when=when,
            content_key='{"a":12,"b":""}',
        )
        assert a["experiment_name"] != b["experiment_name"]

    def test_pins_json_content_keys_diverge_without_explicit_content_key(self) -> None:
        when = datetime(2026, 8, 16, 12, 0, 0, tzinfo=UTC)
        a = build_experiment(
            "mirror",
            "v0",
            git_sha="abc1234",
            when=when,
            dataset_id="ds-a",
            project="proj-a",
        )
        b = build_experiment(
            "mirror",
            "v0",
            git_sha="abc1234",
            when=when,
            dataset_id="ds-b",
            project="proj-b",
        )
        assert a["experiment_name"] != b["experiment_name"]

    def test_pure_hex_content_key_passthrough_prefix(self) -> None:
        when = datetime(2026, 8, 16, 12, 0, 0, tzinfo=UTC)
        key = "abcdef0123456789"
        rec = build_experiment("mirror", "v0", git_sha="abc1234", when=when, content_key=key)
        assert rec["experiment_name"].endswith("_abcdef01")
