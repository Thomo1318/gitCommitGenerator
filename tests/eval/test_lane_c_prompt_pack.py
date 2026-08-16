"""S5b Lane C-prime — prompt pack identity (INT-26).

Covers prompt_pack_content_hash determinism, build_prompt_pack schema
validation, resolve_judge_pack convention mapping, and fail-closed paths
(missing/empty directories, invalid metric ids, schema violations).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from git_cg.eval.lane_c.prompt_pack import (
    DEFAULT_PROMPT_ROOT,
    PromptPackError,
    build_prompt_pack,
    prompt_pack_content_hash,
    resolve_judge_pack,
    validate_prompt_pack,
)
from git_cg.eval.schema_pack import is_valid

# ---------------------------------------------------------------------------
# prompt_pack_content_hash — determinism and sensitivity
# ---------------------------------------------------------------------------


class TestPromptPackContentHash:
    def test_deterministic(self) -> None:
        files = [("a.md", b"alpha"), ("b.md", b"beta")]
        assert prompt_pack_content_hash(files) == prompt_pack_content_hash(files)

    def test_order_independent(self) -> None:
        """Hash is the same regardless of input list order (sorted internally)."""
        f1 = [("b.md", b"beta"), ("a.md", b"alpha")]
        f2 = [("a.md", b"alpha"), ("b.md", b"beta")]
        assert prompt_pack_content_hash(f1) == prompt_pack_content_hash(f2)

    def test_content_change_changes_hash(self) -> None:
        f1 = [("a.md", b"alpha")]
        f2 = [("a.md", b"alpha-modified")]
        assert prompt_pack_content_hash(f1) != prompt_pack_content_hash(f2)

    def test_rename_changes_hash(self) -> None:
        f1 = [("a.md", b"alpha")]
        f2 = [("b.md", b"alpha")]
        assert prompt_pack_content_hash(f1) != prompt_pack_content_hash(f2)

    def test_empty_list_hashes(self) -> None:
        """Empty file list still produces a valid hex digest (no crash)."""
        result = prompt_pack_content_hash([])
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_matches_manual_sha256(self) -> None:
        """Verify the hash matches manual SHA-256 of the canonical form."""
        files = [("x.txt", b"hello")]
        h = hashlib.sha256()
        h.update(b"x.txt")
        h.update(b"\x00")
        h.update(b"hello")
        h.update(b"\x00")
        assert prompt_pack_content_hash(files) == h.hexdigest()


# ---------------------------------------------------------------------------
# build_prompt_pack — schema-valid construction from real files
# ---------------------------------------------------------------------------


class TestBuildPromptPack:
    def test_geval_craft_pack(self) -> None:
        pack = build_prompt_pack("lane_c_geval_craft")
        assert pack["schema_version"] == "prompt_pack_v1"
        assert pack["pack_id"] == "lane_c_geval_craft"
        assert pack["id"] == "ppack_lane_c_geval_craft"
        assert len(pack["content_sha256"]) == 64
        assert pack["schema_pack"].startswith("schema_pack_v0@")
        assert pack["metric_catalog"].startswith("metric_catalog_v0@")

    def test_geval_relevance_pack(self) -> None:
        pack = build_prompt_pack("lane_c_geval_relevance")
        assert pack["pack_id"] == "lane_c_geval_relevance"
        assert len(pack["content_sha256"]) == 64

    def test_craft_and_relevance_have_different_hashes(self) -> None:
        craft = build_prompt_pack("lane_c_geval_craft")
        relevance = build_prompt_pack("lane_c_geval_relevance")
        assert craft["content_sha256"] != relevance["content_sha256"]

    def test_deterministic_across_calls(self) -> None:
        p1 = build_prompt_pack("lane_c_geval_craft")
        p2 = build_prompt_pack("lane_c_geval_craft")
        assert p1["content_sha256"] == p2["content_sha256"]

    def test_with_notes_and_meta(self) -> None:
        pack = build_prompt_pack(
            "lane_c_geval_craft",
            notes="test pack",
            meta={"lane": "judge"},
        )
        assert pack["notes"] == "test pack"
        assert pack["meta"]["lane"] == "judge"

    def test_explicit_pack_dir(self, tmp_path: Path) -> None:
        d = tmp_path / "custom"
        d.mkdir()
        (d / "rubric.md").write_text("custom rubric", encoding="utf-8")
        pack = build_prompt_pack("lane_c_custom", pack_dir=d)
        assert pack["pack_id"] == "lane_c_custom"
        assert len(pack["content_sha256"]) == 64

    def test_schema_valid(self) -> None:
        """Built pack passes frozen schema validation."""
        pack = build_prompt_pack("lane_c_geval_craft")
        assert is_valid("prompt_pack_v1", pack)

    def test_empty_pack_id_raises(self) -> None:
        with pytest.raises(PromptPackError, match="pack_id"):
            build_prompt_pack("")

    def test_whitespace_pack_id_raises(self) -> None:
        with pytest.raises(PromptPackError, match="pack_id"):
            build_prompt_pack("   ")

    def test_missing_dir_raises(self, tmp_path: Path) -> None:
        with pytest.raises(PromptPackError, match="missing prompt pack directory"):
            build_prompt_pack("lane_c_nonexistent", pack_dir=tmp_path / "nope")

    def test_empty_dir_raises(self, tmp_path: Path) -> None:
        d = tmp_path / "empty"
        d.mkdir()
        with pytest.raises(PromptPackError, match="empty prompt pack directory"):
            build_prompt_pack("lane_c_empty", pack_dir=d)

    def test_dir_with_only_non_prompt_files_raises(self, tmp_path: Path) -> None:
        d = tmp_path / "json_only"
        d.mkdir()
        (d / "config.json").write_text("{}", encoding="utf-8")
        with pytest.raises(PromptPackError, match="empty prompt pack directory"):
            build_prompt_pack("lane_c_json", pack_dir=d)


# ---------------------------------------------------------------------------
# validate_prompt_pack — schema enforcement
# ---------------------------------------------------------------------------


class TestValidatePromptPack:
    def test_valid_pack_passes(self) -> None:
        pack = build_prompt_pack("lane_c_geval_craft")
        validate_prompt_pack(pack)  # must not raise

    def test_missing_schema_version_raises(self) -> None:
        pack = build_prompt_pack("lane_c_geval_craft")
        del pack["schema_version"]
        with pytest.raises(PromptPackError, match="validation failed"):
            validate_prompt_pack(pack)

    def test_wrong_schema_version_raises(self) -> None:
        pack = build_prompt_pack("lane_c_geval_craft")
        pack["schema_version"] = "prompt_pack_v2"
        with pytest.raises(PromptPackError, match="validation failed"):
            validate_prompt_pack(pack)

    def test_missing_content_hash_raises(self) -> None:
        pack = build_prompt_pack("lane_c_geval_craft")
        del pack["content_sha256"]
        with pytest.raises(PromptPackError, match="validation failed"):
            validate_prompt_pack(pack)

    def test_invalid_content_hash_format_raises(self) -> None:
        pack = build_prompt_pack("lane_c_geval_craft")
        pack["content_sha256"] = "not-a-sha256"
        with pytest.raises(PromptPackError, match="validation failed"):
            validate_prompt_pack(pack)

    def test_extra_key_raises(self) -> None:
        """additionalProperties: false — unknown keys must fail."""
        pack = build_prompt_pack("lane_c_geval_craft")
        pack["unknown_field"] = "nope"
        with pytest.raises(PromptPackError, match="validation failed"):
            validate_prompt_pack(pack)


# ---------------------------------------------------------------------------
# resolve_judge_pack — metric-to-pack convention
# ---------------------------------------------------------------------------


class TestResolveJudgePack:
    def test_geval_craft(self) -> None:
        pack = resolve_judge_pack("cprime.geval_craft")
        assert pack["pack_id"] == "lane_c_geval_craft"
        assert is_valid("prompt_pack_v1", pack)

    def test_geval_relevance(self) -> None:
        pack = resolve_judge_pack("cprime.geval_relevance")
        assert pack["pack_id"] == "lane_c_geval_relevance"
        assert is_valid("prompt_pack_v1", pack)

    def test_non_cprime_raises(self) -> None:
        with pytest.raises(PromptPackError, match="cprime"):
            resolve_judge_pack("a.final_bytes_stable")

    def test_empty_metric_raises(self) -> None:
        with pytest.raises(PromptPackError, match="cprime"):
            resolve_judge_pack("")

    def test_unresolvable_pack_raises(self) -> None:
        """A cprime.* metric with no on-disk pack directory fails closed."""
        with pytest.raises(PromptPackError, match="missing prompt pack directory"):
            resolve_judge_pack("cprime.usefulness")

    def test_explicit_prompt_root(self, tmp_path: Path) -> None:
        d = tmp_path / "geval_craft"
        d.mkdir()
        (d / "rubric.md").write_text("override rubric", encoding="utf-8")
        pack = resolve_judge_pack("cprime.geval_craft", prompt_root=tmp_path)
        assert pack["pack_id"] == "lane_c_geval_craft"


# ---------------------------------------------------------------------------
# DEFAULT_PROMPT_ROOT constant
# ---------------------------------------------------------------------------


class TestDefaultPromptRoot:
    def test_path_shape(self) -> None:
        expected = Path("prompts", "eval", "lane_c")
        assert expected == DEFAULT_PROMPT_ROOT

    def test_repo_packs_exist(self) -> None:
        """The committed geval_craft and geval_relevance packs exist on disk."""
        from git_cg.eval.paths import REPO_ROOT

        for name in ("geval_craft", "geval_relevance"):
            pack_dir = REPO_ROOT / DEFAULT_PROMPT_ROOT / name
            assert pack_dir.is_dir(), f"missing pack dir: {pack_dir}"
            rubric = pack_dir / "rubric.md"
            assert rubric.is_file(), f"missing rubric: {rubric}"
