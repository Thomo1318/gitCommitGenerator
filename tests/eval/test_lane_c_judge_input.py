"""S5c Lane C-prime — judge input projection (C-INPUT / C-DIFF / S5-C).

Covers issue #233 Slice 3:
final_accept linkage, recursive gold-blind isolation, bounded path-scrubbed
diff_summary, empty/oversize host guards, and lab-only artifact classes.
No provider SDK, network, or runner wiring.
"""

from __future__ import annotations

from typing import Any

import pytest

from git_cg.eval.binding.binder import BindInput, BindResult, bind_final_accept, message_sha256_bytes
from git_cg.eval.corpus.canonical import message_sha256
from git_cg.eval.enums import ArtifactClass
from git_cg.eval.lane_c.judge_input import (
    DEFAULT_MAX_DIFF_SUMMARY_CHARS,
    DEFAULT_MAX_INPUT_CHARS,
    JudgeInput,
    JudgeInputError,
    classify_judge_input_size,
    project_diff_summary,
    project_judge_input,
)
from git_cg.eval.lane_c.taxonomy import EXEC_EMPTY_INPUT, EXEC_OVERSIZE_INPUT

FINAL_TEXT = (
    "✨ feat(eval): add judge input projection\n\n"
    "Refs: #233\n"
    "SemVer-Impact: MINOR\n"
    "Change-Types: feat\n"
    "Changelog-Groups: Added\n"
)


def _bundle(**overrides: Any) -> dict[str, Any]:
    bundle: dict[str, Any] = {
        "schema_version": "ape_bundle_v1",
        "case_id": "acceptpath:sess_test",
        "artifact_class": ArtifactClass.FINAL_ACCEPT.value,
        "bound": True,
        "final_message": FINAL_TEXT,
        "final_message_sha256": message_sha256_bytes(FINAL_TEXT),
        "session_thread_id": "sess_deadbeef",
        "redaction_profile": "default_scrub",
        "provenance_label": ArtifactClass.FINAL_ACCEPT.value,
        "meta": {"producer": "acceptpath_binder"},
    }
    meta_override = overrides.pop("meta", None)
    bundle.update(overrides)
    if meta_override is not None:
        bundle["meta"] = meta_override
    return bundle


def _bound_result(**overrides: Any) -> BindResult:
    """Create a bound result containing a bundle with the supplied field overrides.
    
    Parameters:
    	overrides (Any): Field values to override in the generated bundle.
    
    Returns:
    	BindResult: A bound result containing the configured bundle.
    """
    return BindResult(bound=True, bundle=_bundle(**overrides))


def _assert_allowlisted(projected: JudgeInput) -> dict[str, Any]:
    """
    Validate that a projected judge input contains only permitted fields and return its serialised payload.
    
    Parameters:
    	projected (JudgeInput): The projected judge input to validate.
    
    Returns:
    	dict[str, Any]: The validated serialised payload.
    """
    payload = projected.as_dict()
    allowed = {
        "artifact_class",
        "final_message_text",
        "final_message_sha256",
        "encoding",
        "session_thread_id",
        "diff_summary",
    }
    assert set(payload) <= allowed
    assert "bundle_id" not in payload
    assert "expected_final_message" not in payload
    assert "gold_codes" not in payload
    return payload


# ---------------------------------------------------------------------------
# Happy path / S5-C05 linkage
# ---------------------------------------------------------------------------


class TestFinalAcceptLinkage:
    def test_bundle_mapping_projects_required_fields(self) -> None:
        projected = project_judge_input(_bundle())
        payload = _assert_allowlisted(projected)
        assert payload["artifact_class"] == ArtifactClass.FINAL_ACCEPT.value
        assert payload["final_message_text"] == FINAL_TEXT
        assert payload["final_message_sha256"] == message_sha256_bytes(FINAL_TEXT)
        assert payload["encoding"] == "utf-8"
        assert payload["session_thread_id"] == "sess_deadbeef"
        assert "diff_summary" not in payload

    def test_bind_result_projects_required_fields(self) -> None:
        projected = project_judge_input(_bound_result())
        assert projected.artifact_class == ArtifactClass.FINAL_ACCEPT.value
        assert projected.final_message_sha256 == message_sha256_bytes(FINAL_TEXT)
        assert projected.encoding == "utf-8"

    def test_real_bind_result_is_consumed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GIT_CG_EVAL_CAPTURE", "on")
        result = bind_final_accept(
            BindInput(final_message=FINAL_TEXT, accept_event_token="ae_s5c"),
            write=False,
        )
        assert result.bound is True
        assert result.bundle is not None
        projected = project_judge_input(result)
        assert projected.artifact_class == ArtifactClass.FINAL_ACCEPT.value
        assert projected.final_message_text == result.bundle["final_message"]
        assert projected.final_message_sha256 == result.bundle["final_message_sha256"]
        assert projected.session_thread_id == result.bundle["session_thread_id"]
        assert projected.encoding == "utf-8"
        assert "bundle_id" not in projected.as_dict()

    def test_invalid_utf8_keeps_original_byte_hash_and_replace_stamp(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GIT_CG_EVAL_CAPTURE", "on")
        raw = b"\xff\xfe invalid \x80 bytes\n"
        result = bind_final_accept(
            BindInput(final_message=raw, accept_event_token="ae_s5c_utf8"),
            write=False,
        )
        assert result.bound is True
        assert result.bundle is not None
        projected = project_judge_input(result)
        assert projected.encoding == "utf-8-replace"
        assert projected.final_message_sha256 == message_sha256_bytes(raw)
        assert projected.final_message_sha256 != message_sha256(raw.decode("utf-8", errors="replace"))
        assert projected.final_message_text == result.bundle["final_message"]

    def test_commit_text_may_contain_expected_word(self) -> None:
        text = "✨ fix(eval): document expected behavior\n"
        projected = project_judge_input(_bundle(final_message=text, final_message_sha256=message_sha256_bytes(text)))
        assert "expected behavior" in projected.final_message_text


# ---------------------------------------------------------------------------
# Ordinary path rejects free / unbound message (F14)
# ---------------------------------------------------------------------------


class TestOrdinaryPathRejectsUnbound:
    def test_free_message_mapping_rejected(self) -> None:
        with pytest.raises(JudgeInputError, match="message"):
            project_judge_input({"message": FINAL_TEXT})

    def test_message_without_linkage_rejected(self) -> None:
        with pytest.raises(JudgeInputError, match=r"linkage|final_accept|unbound"):
            project_judge_input({"message": FINAL_TEXT, "artifact_class": "final_accept"})

    def test_unbound_bind_result_rejected(self) -> None:
        result = BindResult(bound=False, unbound_reason="capture_disabled")
        with pytest.raises(JudgeInputError, match=r"unbound|final_accept"):
            project_judge_input(result)

    def test_unbound_bundle_rejected(self) -> None:
        with pytest.raises(JudgeInputError, match=r"unbound|final_accept"):
            project_judge_input(_bundle(bound=False, artifact_class=ArtifactClass.OPIK_UNBOUND.value))

    def test_lab_class_without_override_rejected(self) -> None:
        with pytest.raises(JudgeInputError, match="lab_override"):
            project_judge_input(
                _bundle(
                    artifact_class=ArtifactClass.FIXTURE.value,
                    bound=False,
                )
            )

    def test_gold_final_rejected_even_with_override(self) -> None:
        with pytest.raises(JudgeInputError, match="artifact_class"):
            project_judge_input(
                _bundle(artifact_class=ArtifactClass.GOLD_FINAL.value, bound=True),
                lab_override=True,
            )

    def test_unbound_final_accept_rejected_even_with_override(self) -> None:
        with pytest.raises(JudgeInputError, match="final_accept"):
            project_judge_input(_bundle(bound=False), lab_override=True)

    def test_non_mapping_evidence_rejected(self) -> None:
        with pytest.raises(JudgeInputError):
            project_judge_input(FINAL_TEXT)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Recursive isolation (S5-C01 / S5-C02)
# ---------------------------------------------------------------------------


class TestRecursiveIsolation:
    def test_top_level_expected_rejected(self) -> None:
        poisoned = _bundle()
        poisoned["expected_final_message"] = "LEAK"
        with pytest.raises(JudgeInputError, match="expected"):
            project_judge_input(poisoned)

    def test_nested_expected_rejected(self) -> None:
        poisoned = _bundle(meta={"producer": "x", "nested": {"expected_gold_codes": ["LEAK"]}})
        with pytest.raises(JudgeInputError, match="expected"):
            project_judge_input(poisoned)

    def test_nested_gold_prefix_rejected(self) -> None:
        poisoned = _bundle(meta={"producer": "x", "notes": [{"gold_codes": ["LEAK"]}]})
        with pytest.raises(JudgeInputError, match="gold"):
            project_judge_input(poisoned)

    def test_assert_key_rejected(self) -> None:
        poisoned = _bundle(meta={"producer": "x", "assert": {"pass": True}})
        with pytest.raises(JudgeInputError, match="assert"):
            project_judge_input(poisoned)

    def test_gate_sole_green_hint_rejected(self) -> None:
        poisoned = _bundle(meta={"producer": "x", "gate_deterministic_pass": True})
        with pytest.raises(JudgeInputError, match="gate_deterministic_pass"):
            project_judge_input(poisoned)

    def test_judge_labels_and_target_rejected(self) -> None:
        poisoned = _bundle()
        poisoned["context"] = {"judge_labels": ["craft"], "judge_target": "gold"}
        with pytest.raises(JudgeInputError, match="judge_"):
            project_judge_input(poisoned)

    def test_poisoned_context_rejected(self) -> None:
        with pytest.raises(JudgeInputError, match="expected"):
            project_judge_input(_bundle(), context={"diff_summary": "ok", "expected_output": "LEAK"})

    def test_strict_false_strips_never_returns_expected(self) -> None:
        poisoned = _bundle()
        poisoned["expected_final_message"] = "LEAK"
        poisoned["meta"] = {"producer": "x", "gold_target": "LEAK"}
        projected = project_judge_input(poisoned, strict=False)
        payload = _assert_allowlisted(projected)
        dumped = repr(payload)
        assert "LEAK" not in dumped
        assert "expected_final_message" not in payload
        assert "gold_target" not in payload

    def test_output_omits_forbidden_carriers(self) -> None:
        projected = project_judge_input(_bundle())
        payload = projected.as_dict()
        assert all(not key.startswith(("expected", "gold", "assert")) for key in payload)


# ---------------------------------------------------------------------------
# Empty / oversize host guards (S5-C04 / D12)
# ---------------------------------------------------------------------------


class TestEmptyOversizeGuards:
    def test_empty_text_raises_empty_input(self) -> None:
        with pytest.raises(JudgeInputError, match="empty_input") as ei:
            project_judge_input(_bundle(final_message="", final_message_sha256=message_sha256_bytes("")))
        assert ei.value.code == EXEC_EMPTY_INPUT

    def test_whitespace_text_raises_empty_input(self) -> None:
        text = "   \n\t  "
        with pytest.raises(JudgeInputError, match="empty_input") as ei:
            project_judge_input(_bundle(final_message=text, final_message_sha256=message_sha256_bytes(text)))
        assert ei.value.code == EXEC_EMPTY_INPUT

    def test_oversize_text_raises_oversize_input(self) -> None:
        text = "a" * (DEFAULT_MAX_INPUT_CHARS + 1)
        with pytest.raises(JudgeInputError, match="oversize_input") as ei:
            project_judge_input(_bundle(final_message=text, final_message_sha256=message_sha256_bytes(text)))
        assert ei.value.code == EXEC_OVERSIZE_INPUT

    def test_combined_message_and_summary_oversize(self) -> None:
        text = "a" * (DEFAULT_MAX_INPUT_CHARS - 10)
        with pytest.raises(JudgeInputError, match="oversize_input") as ei:
            project_judge_input(
                _bundle(final_message=text, final_message_sha256=message_sha256_bytes(text)),
                context={"diff_summary": "b" * 20},
            )
        assert ei.value.code == EXEC_OVERSIZE_INPUT

    def test_classify_helper_matches_taxonomy(self) -> None:
        assert classify_judge_input_size("") == EXEC_EMPTY_INPUT
        assert classify_judge_input_size("   ") == EXEC_EMPTY_INPUT
        assert classify_judge_input_size("ok") is None
        assert classify_judge_input_size("x" * (DEFAULT_MAX_INPUT_CHARS + 1)) == EXEC_OVERSIZE_INPUT

    def test_exact_limit_is_allowed(self) -> None:
        text = "a" * DEFAULT_MAX_INPUT_CHARS
        projected = project_judge_input(_bundle(final_message=text, final_message_sha256=message_sha256_bytes(text)))
        assert len(projected.final_message_text) == DEFAULT_MAX_INPUT_CHARS


# ---------------------------------------------------------------------------
# C-DIFF — allowlisted / bounded / path-scrubbed / gold-blind
# ---------------------------------------------------------------------------


class TestDiffSummaryProjection:
    def test_relative_summary_preserved(self) -> None:
        summary = "src/git_cg/eval/lane_c/judge_input.py (+12/-3)"
        projected = project_judge_input(_bundle(), context={"diff_summary": summary})
        assert projected.diff_summary is not None
        assert "judge_input.py" in projected.diff_summary
        assert projected.diff_summary.count("+12") == 1

    def test_absolute_paths_are_scrubbed(self) -> None:
        summary = "Updated /Users/admin/dev/activeProjects/gitCommitGenerator/src/git_cg/main.py (+3/-1)"
        out = project_diff_summary(summary)
        assert out is not None
        assert "/Users/" not in out
        assert "main.py" in out

    def test_windows_and_file_urls_are_scrubbed(self) -> None:
        summary = r"Changed C:\Users\admin\repo\src\git_cg\intent.py and file:///home/admin/repo/sop.py"
        out = project_diff_summary(summary)
        assert out is not None
        assert "C:\\Users" not in out
        assert "file://" not in out
        assert "intent.py" in out
        assert "sop.py" in out

    def test_raw_patch_rejected(self) -> None:
        patch = "diff --git a/foo.py b/foo.py\n--- a/foo.py\n+++ b/foo.py\n@@ -1,2 +1,2 @@\n-old\n+new\n"
        with pytest.raises(JudgeInputError, match="raw patch"):
            project_diff_summary(patch)
        with pytest.raises(JudgeInputError, match="raw patch"):
            project_judge_input(_bundle(), context={"diff_summary": patch})

    def test_summary_is_bounded(self) -> None:
        out = project_diff_summary("x" * (DEFAULT_MAX_DIFF_SUMMARY_CHARS + 50))
        assert out is not None
        assert len(out) <= DEFAULT_MAX_DIFF_SUMMARY_CHARS

    def test_unknown_context_key_rejected(self) -> None:
        with pytest.raises(JudgeInputError, match="unsupported keys"):
            project_judge_input(_bundle(), context={"diff_summary": "ok", "secret_sauce": "nope"})

    def test_empty_summary_omitted(self) -> None:
        projected = project_judge_input(_bundle(), context={"diff_summary": "   "})
        assert projected.diff_summary is None
        assert "diff_summary" not in projected.as_dict()

    def test_non_string_summary_rejected(self) -> None:
        with pytest.raises(JudgeInputError, match="diff_summary"):
            project_diff_summary({"text": "nope"})  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Lab override (explicit lab class + still gold-blind / linked)
# ---------------------------------------------------------------------------


class TestLabOverride:
    def test_fixture_class_allowed_with_override(self) -> None:
        projected = project_judge_input(
            _bundle(artifact_class=ArtifactClass.FIXTURE.value, bound=False),
            lab_override=True,
        )
        assert projected.artifact_class == ArtifactClass.FIXTURE.value
        assert projected.final_message_sha256 == message_sha256_bytes(FINAL_TEXT)

    def test_live_regen_and_opik_unbound_allowed(self) -> None:
        for cls in (ArtifactClass.LIVE_REGEN.value, ArtifactClass.OPIK_UNBOUND.value):
            projected = project_judge_input(_bundle(artifact_class=cls, bound=False), lab_override=True)
            assert projected.artifact_class == cls

    def test_lab_path_still_requires_hash(self) -> None:
        bundle = _bundle(artifact_class=ArtifactClass.FIXTURE.value, bound=False)
        del bundle["final_message_sha256"]
        with pytest.raises(JudgeInputError, match=r"sha256|linkage"):
            project_judge_input(bundle, lab_override=True)

    def test_lab_path_still_gold_blind(self) -> None:
        poisoned = _bundle(artifact_class=ArtifactClass.FIXTURE.value, bound=False)
        poisoned["judge_target"] = "LEAK"
        with pytest.raises(JudgeInputError, match="judge_target"):
            project_judge_input(poisoned, lab_override=True)


# ---------------------------------------------------------------------------
# Import isolation
# ---------------------------------------------------------------------------


class TestImportIsolation:
    def test_judge_input_does_not_import_providers(self) -> None:
        import subprocess
        import sys as _sys

        code = (
            "import sys\n"
            "banned = {'openai', 'anthropic', 'httpx', 'opik', 'requests'}\n"
            "before = {m for m in sys.modules if m.split('.', 1)[0] in banned}\n"
            "import git_cg.eval.lane_c.judge_input as judge_input\n"
            "after = {m for m in sys.modules if m.split('.', 1)[0] in banned}\n"
            "leaked = sorted(after - before)\n"
            "assert not leaked, leaked\n"
            "assert hasattr(judge_input, 'project_judge_input')\n"
        )
        proc = subprocess.run(
            [_sys.executable, "-c", code],
            check=False,
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
