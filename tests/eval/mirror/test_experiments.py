"""S4b experiment_v1 naming + pin records."""

from __future__ import annotations

from datetime import UTC, datetime

from git_cg.eval.mirror.experiments import (
    _UNRESOLVED_SHA,
    build_experiment,
    experiment_name,
    resolve_git_sha,
)
from git_cg.eval.schema_pack import validate_instance


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
        assert all(c in "0123456789abcdef" for c in sha)


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
        assert record["meta"] == {"k": "v"}

    def test_default_git_sha_resolves(self) -> None:
        record = build_experiment("mirror", "v0")
        assert all(c in "0123456789abcdef" for c in record["git_sha"])


class TestExperimentsModuleSyntax:
    def test_module_imports_cleanly(self) -> None:
        """P0-6 — invalid except syntax must not prevent import."""
        import git_cg.eval.mirror.experiments as exp

        assert callable(exp.resolve_git_sha)
        assert callable(exp.build_experiment)
