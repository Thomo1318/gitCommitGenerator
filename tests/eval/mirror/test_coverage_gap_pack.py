"""Targeted coverage for PR #236 patch gaps (health/result/composition/exporter/queue/payload/transport/projections).

Keeps each changed mirror module ≥80% statement coverage without product-path coupling.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from git_cg.eval.enums import RedactionProfile
from git_cg.eval.mirror.batch import ExportSizeError, build_export_batches
from git_cg.eval.mirror.composition import (
    ExportPlanError,
    ExportPlanResult,
    LayerAObjects,
    build_export_plan,
)
from git_cg.eval.mirror.exporter import (
    DrainSummary,
    _project_from_config,
    _row_experiment_name,
    _row_project,
    drain_queue,
    mirror_result_from_drain,
)
from git_cg.eval.mirror.health import (
    ExportHealth,
    derive_export_health_rollup,
    map_error_class_to_health,
)
from git_cg.eval.mirror.payload import (
    ExportPayloadError,
    load_payload_artifact,
    payload_ref_for_sha,
    persist_payload_artifact,
    verify_payload_object,
)
from git_cg.eval.mirror.projections import (
    ProjectionError,
    project_score_card_to_feedback,
    project_session_thread,
    select_final_attempt,
)
from git_cg.eval.mirror.queue import (
    ExportQueueError,
    claim_queue_item,
    enqueue_export_batch,
    export_queue_dir,
    list_claimable_items,
    load_queue_item,
    mark_queue_item,
    release_stale_leases,
)
from git_cg.eval.mirror.result import (
    MirrorResult,
    build_mirror_result,
    evaluation_job_result,
    export_result,
)
from git_cg.eval.mirror.secrets import OpikRuntimeSecrets
from git_cg.eval.mirror.transport import (
    ExportTransportError,
    MockTransport,
    OpikSdkTransport,
    classify_export_error,
    scrub_export_note,
)

SECRETS = OpikRuntimeSecrets(api_key="k", workspace="w", base_url=None)
CONFIG = {
    "schema_version": "git_cg_opik_config_v1",
    "id": "git_cg_opik_config_v1",
    "mode": "mirror",
    "environment": "eval",
    "redaction_profile": "default_scrub",
    "flush_timeout_ms": 5000,
    "track_disable": False,
    "check_tls_certificate": True,
    "projects": {
        "live": "eval-project",
        "eval": "eval-project",
        "ci": "eval-project",
        "import": "eval-project",
    },
    "project_name": "eval-project",
}


def _batch(items: list[tuple[str, dict]] | None = None) -> dict:
    return build_export_batches(items or [("i-1", {"pad": "x" * 20})], RedactionProfile.DEFAULT_SCRUB)[0]


def _bundle(**overrides: Any) -> dict[str, Any]:
    base = {
        "id": "bundle_gap_1",
        "schema_version": "ape_bundle_v1",
        "artifact_class": "final_accept",
        "gate": {"deterministic_pass": True, "authority": "product"},
        "score_card": {"format_compliance": 1.0, "flag": True},
        "attempts": [
            {
                "final_message": "✨ feat(scope): subject",
                "scored_target": "final_message",
                "artifact_class": "final_accept",
            }
        ],
        "meta": {"redaction_profile": "default_scrub"},
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# health.py
# ---------------------------------------------------------------------------


class TestExportHealthMapAndRollup:
    def test_map_error_class_empty_and_unknown(self) -> None:
        assert map_error_class_to_health(None) is ExportHealth.NETWORK_ERROR
        assert map_error_class_to_health("") is ExportHealth.NETWORK_ERROR
        assert map_error_class_to_health("nope") is ExportHealth.NETWORK_ERROR

    def test_map_error_class_closed_vocabulary(self) -> None:
        assert map_error_class_to_health("export_auth") is ExportHealth.AUTH_ERROR
        assert map_error_class_to_health("export_network") is ExportHealth.NETWORK_ERROR
        assert map_error_class_to_health("export_validation") is ExportHealth.CONFIG_ERROR
        assert map_error_class_to_health("export_size") is ExportHealth.CONFIG_ERROR
        assert map_error_class_to_health("export_timeout") is ExportHealth.TIMEOUT

    def test_rollup_all_branches(self) -> None:
        assert derive_export_health_rollup(ExportHealth.SUCCESS) == "healthy"
        assert derive_export_health_rollup("success") == "healthy"
        assert derive_export_health_rollup(ExportHealth.SKIPPED_OFF) == "idle"
        assert derive_export_health_rollup(ExportHealth.DEFERRED) == "idle"
        assert derive_export_health_rollup(ExportHealth.PENDING) == "idle"
        assert derive_export_health_rollup(ExportHealth.PARTIAL) == "degraded"
        assert derive_export_health_rollup(ExportHealth.REPLAY_NEEDED) == "replay"
        assert derive_export_health_rollup(ExportHealth.AUTH_ERROR) == "unhealthy"
        assert derive_export_health_rollup(ExportHealth.NETWORK_ERROR) == "unhealthy"
        assert derive_export_health_rollup(ExportHealth.TIMEOUT) == "unhealthy"
        assert derive_export_health_rollup(ExportHealth.CONFIG_ERROR) == "unhealthy"


# ---------------------------------------------------------------------------
# result.py
# ---------------------------------------------------------------------------


class TestMirrorResultInference:
    def test_scrub_notes_filters_blanks_and_caps(self) -> None:
        notes = ["", "  ", "ok", "a\nb", "x" * 300] + [f"n{i}" for i in range(40)]
        result = build_mirror_result(mode="mirror", health=ExportHealth.SUCCESS, notes=notes)
        assert "" not in result.notes
        assert all("\n" not in n for n in result.notes)
        assert all(len(n) <= 200 for n in result.notes)
        assert len(result.notes) <= 32
        assert result.notes[0] == "ok"
        assert "a b" in result.notes

    def test_health_string_coercion_in_post_init(self) -> None:
        result = MirrorResult(mode="mirror", health="partial")  # type: ignore[arg-type]
        assert result.health is ExportHealth.PARTIAL
        assert result.product_accept_blocked is False

    def test_infer_health_branches(self) -> None:
        assert build_mirror_result(mode="off").health is ExportHealth.SKIPPED_OFF
        assert build_mirror_result(mode="mirror", notes=("mode_off",)).health is ExportHealth.SKIPPED_OFF
        assert build_mirror_result(mode="mirror", notes=("skipped_off",)).health is ExportHealth.SKIPPED_OFF
        assert (
            build_mirror_result(mode="mirror", notes=("secret_resolution_failed: x",)).health is ExportHealth.AUTH_ERROR
        )
        assert build_mirror_result(mode="mirror", notes=("config_error",)).health is ExportHealth.CONFIG_ERROR
        assert (
            build_mirror_result(mode="mirror", notes=("schema_validation_error",)).health is ExportHealth.CONFIG_ERROR
        )
        assert build_mirror_result(mode="mirror", deferred=2, attempted=0, failed=0).health is ExportHealth.DEFERRED
        assert build_mirror_result(mode="mirror").health is ExportHealth.PENDING
        assert build_mirror_result(mode="dogfood").health is ExportHealth.SKIPPED_OFF
        assert build_mirror_result(mode="mirror", attempted=2, succeeded=1, failed=1).health is ExportHealth.PARTIAL
        assert (
            build_mirror_result(
                mode="mirror",
                attempted=1,
                failed=1,
                error_classes=("export_auth",),
            ).health
            is ExportHealth.AUTH_ERROR
        )
        assert build_mirror_result(mode="mirror", attempted=1, failed=1).health is ExportHealth.NETWORK_ERROR
        assert build_mirror_result(mode="mirror", attempted=1, succeeded=1).health is ExportHealth.SUCCESS

    def test_export_and_eval_axis_views(self) -> None:
        result = build_mirror_result(
            mode="strict_mirror",
            attempted=1,
            failed=1,
            error_classes=("export_network",),
        )
        assert result.strict_mirror_failed is True
        er = export_result(result)
        assert er["axis"] == "export_result"
        assert er["product_accept_blocked"] is False
        ej = evaluation_job_result(result)
        assert ej["axis"] == "evaluation_job_result"
        assert ej["ok"] is False
        # mapping path
        er2 = export_result(result.to_dict())
        assert er2["mode"] == "strict_mirror"
        ej2 = evaluation_job_result(result.to_dict())
        assert ej2["strict_mirror_failed"] is True


# ---------------------------------------------------------------------------
# composition.py
# ---------------------------------------------------------------------------


class TestCompositionCoverage:
    def test_export_plan_error_carries_class(self) -> None:
        exc = ExportPlanError("boom", error_class="export_size")
        assert exc.error_class == "export_size"
        assert "boom" in str(exc)

    def test_layer_a_from_mapping_variants(self) -> None:
        assert LayerAObjects.from_mapping(None).bundles == ()
        single = LayerAObjects.from_mapping({"bundle": {"id": "b1"}, "sessions": {"session_thread_id": "s1"}})
        assert len(single.bundles) == 1
        assert len(single.session_threads) == 1
        multi = LayerAObjects.from_mapping(
            {"bundles": [{"id": "b1"}, "skip", {"id": "b2"}], "session_threads": [{"id": "s1"}], "include_train": True}
        )
        assert len(multi.bundles) == 2
        assert multi.include_train is True

    def test_export_plan_result_to_dict_and_mirror(self) -> None:
        plan = ExportPlanResult(mode="mirror", health="pending", notes=("x",), error_classes=("export_network", ""))  # type: ignore[arg-type]
        d = plan.to_dict()
        assert d["product_accept_blocked"] is False
        assert d["health"] == "pending"
        assert plan.error_classes == ("export_network",)
        mr = plan.as_mirror_result()
        assert mr.mode == "mirror"

    def test_build_export_plan_none_config_and_empty_objects(self, tmp_path: Path) -> None:
        plan = build_export_plan(None, None, repo_root=tmp_path)
        assert plan.mode == "off"
        assert plan.health is ExportHealth.SKIPPED_OFF

    def test_build_export_plan_local_only_short_circuit(self, tmp_path: Path) -> None:
        plan = build_export_plan([_bundle()], {**CONFIG, "mode": "local_only"}, repo_root=tmp_path)
        assert plan.health is ExportHealth.DEFERRED
        assert plan.skipped >= 1

    def test_build_export_plan_bare_bundle_and_sequence(self, tmp_path: Path) -> None:
        plan = build_export_plan(_bundle(), CONFIG, repo_root=tmp_path, git_sha="abc1234", enqueue=False)
        assert plan.projected == 1
        assert plan.health is ExportHealth.PENDING
        plan2 = build_export_plan([_bundle(id="b2")], CONFIG, repo_root=tmp_path, git_sha="abc1234", enqueue=False)
        assert plan2.projected == 1

    def test_build_export_plan_item_ref_fallback_index(self, tmp_path: Path) -> None:
        hollow = {
            "schema_version": "ape_bundle_v1",
            "attempts": [{"final_message": "x", "artifact_class": "final_accept"}],
        }
        plan = build_export_plan(hollow, CONFIG, repo_root=tmp_path, git_sha="abc1234", enqueue=False)
        assert plan.projected == 1
        assert any(ref.startswith("bundle_") for ref in plan.item_refs)

    def test_projection_failure_is_counted(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from git_cg.eval.mirror import composition as composition_mod

        def boom(*_a, **_k):
            raise ProjectionError("nope")

        monkeypatch.setattr(composition_mod, "project_bundle_to_trace", boom)
        plan = build_export_plan(_bundle(), CONFIG, repo_root=tmp_path, git_sha="abc1234")
        assert plan.failed == 1
        assert plan.health is ExportHealth.CONFIG_ERROR
        assert "export_validation" in plan.error_classes

    def test_orphan_session_and_session_projection_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        orphan = {"message_versions": [{"role": "user", "content": "hi"}], "meta": {"lifecycle": "open"}}
        plan = build_export_plan(
            {"bundles": [], "session_threads": [orphan]},
            CONFIG,
            repo_root=tmp_path,
            git_sha="abc1234",
            enqueue=False,
        )
        assert plan.projected == 1

        from git_cg.eval.mirror import composition as composition_mod

        def boom(*_a, **_k):
            raise ProjectionError("sess fail")

        monkeypatch.setattr(composition_mod, "project_session_thread", boom)
        plan2 = build_export_plan(
            {"bundles": [], "session_threads": [orphan]},
            CONFIG,
            repo_root=tmp_path,
            git_sha="abc1234",
        )
        assert plan2.failed == 1
        assert any("sess fail" in n for n in plan2.notes)

    def test_train_projection_failure_is_soft(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from git_cg.eval.mirror import composition as composition_mod

        def boom(*_a, **_k):
            raise RuntimeError("train blew up")

        monkeypatch.setattr(composition_mod, "build_train_projection", boom)
        plan = build_export_plan(
            {"bundles": [_bundle()], "include_train": True},
            CONFIG,
            repo_root=tmp_path,
            git_sha="abc1234",
            enqueue=False,
            include_train=True,
        )
        assert plan.projected == 1
        assert any("train_projection" in n for n in plan.notes)
        assert "export_validation" in plan.error_classes

    def test_export_size_error_on_batch(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from git_cg.eval.mirror import composition as composition_mod

        def boom(*_a, **_k):
            raise ExportSizeError("too big")

        monkeypatch.setattr(composition_mod, "build_export_batches", boom)
        plan = build_export_plan(_bundle(), CONFIG, repo_root=tmp_path, git_sha="abc1234")
        assert plan.health is ExportHealth.CONFIG_ERROR
        assert "export_size" in plan.error_classes

    def test_enqueue_failures_partial_and_total(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from git_cg.eval.mirror import composition as composition_mod

        calls = {"n": 0}

        def flaky(*_a, **_k):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ExportQueueError("q fail", error_class="export_validation")
            raise RuntimeError("weird")

        # Force two batches by low ceiling through monkeypatch after projection.
        monkeypatch.setattr(composition_mod, "enqueue_export_batch", flaky)

        # Build two bundles → typically one batch, so force two enqueue calls via two batches.
        def two_batches(items, *a, **k):
            return [
                {
                    "batch_id": "b1",
                    "idempotency_key": "k1",
                    "redaction_profile": "default_scrub",
                    "project": "eval-project",
                    "experiment_id": "e1",
                    "item_refs": ["i1"],
                    "status": "pending",
                    "meta": {
                        "transport_body": {"items": []},
                        "environment": "eval",
                        "dataset_id": "d",
                        "project_lane": "eval",
                    },
                },
                {
                    "batch_id": "b2",
                    "idempotency_key": "k2",
                    "redaction_profile": "default_scrub",
                    "project": "eval-project",
                    "experiment_id": "e2",
                    "item_refs": ["i2"],
                    "status": "pending",
                    "meta": {
                        "transport_body": {"items": []},
                        "environment": "eval",
                        "dataset_id": "d",
                        "project_lane": "eval",
                    },
                },
            ]

        monkeypatch.setattr(composition_mod, "build_export_batches", two_batches)
        plan = build_export_plan([_bundle(), _bundle(id="b2")], CONFIG, repo_root=tmp_path, git_sha="abc1234")
        assert plan.failed >= 2
        assert plan.health is ExportHealth.CONFIG_ERROR

    def test_project_name_fallback_default(self, tmp_path: Path) -> None:
        plan = build_export_plan(
            _bundle(),
            {**CONFIG, "mode": "mirror", "projects": {"eval": "p"}},
            repo_root=tmp_path,
            git_sha="abcdef0",
            enqueue=False,
        )
        assert plan.projected == 1


# ---------------------------------------------------------------------------
# exporter.py
# ---------------------------------------------------------------------------


class TestExporterCoverage:
    def test_drain_summary_succeeded_alias(self) -> None:
        s = DrainSummary(exported=3)
        assert s.succeeded == 3

    def test_project_and_experiment_helpers(self) -> None:
        assert _project_from_config({"projects": {"eval": "e1"}, "project_name": "legacy"}) == "e1"
        assert _project_from_config({"projects": {"eval": "  "}, "project_name": "legacy"}) == "legacy"
        assert _project_from_config({"project_name": "legacy"}) == "legacy"
        assert _row_project({"project": "queued"}, CONFIG) == "queued"
        assert _row_project({}, {"projects": {"eval": "from-cfg"}}) == "from-cfg"
        assert _row_experiment_name({"experiment_id": "exp"}, "qid") == "exp"
        assert _row_experiment_name({"meta": {"batch_id": "b1"}}, "qid") == "b1"
        assert _row_experiment_name({}, "qid") == "qid"
        assert _row_experiment_name({"meta": "bad"}, "qid") == "qid"

    def test_mode_off_short_circuit(self, tmp_path: Path) -> None:
        summary = drain_queue({**CONFIG, "mode": "off"}, transport=MockTransport(), repo_root=tmp_path, secrets=SECRETS)
        assert summary.notes == ("skipped_off",)
        assert summary.attempted == 0

    def test_mirror_result_from_drain(self) -> None:
        summary = DrainSummary(
            attempted=2, exported=1, failed=1, skipped=0, error_classes=("export_network",), notes=("n",)
        )
        result = mirror_result_from_drain(CONFIG, summary)
        assert result.attempted == 2
        assert result.succeeded == 1
        assert result.failed == 1
        assert result.product_accept_blocked is False

    def test_secret_failure_claim_mark_guards(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import git_cg.eval.mirror.exporter as exporter_mod
        import git_cg.eval.mirror.queue as queue_mod

        batch = _batch([("a", {"x": 1})])
        enqueue_export_batch(batch, repo_root=tmp_path)

        def boom(*, require_key: bool = True):
            from git_cg.eval.mirror.secrets import MirrorSecretError

            raise MirrorSecretError("no key")

        real_claim = queue_mod.claim_queue_item
        real_mark = queue_mod.mark_queue_item

        def claim_none(*a, **k):
            return None

        def mark_flaky(queue_id, status, *a, **k):
            if status == "sending":
                raise queue_mod.ExportQueueError("cannot mark sending")
            if status == "failed":
                raise queue_mod.ExportQueueError("cannot mark failed")
            return real_mark(queue_id, status, *a, **k)

        monkeypatch.setattr(exporter_mod, "resolve_opik_secrets", boom)
        monkeypatch.setattr(queue_mod, "claim_queue_item", claim_none)
        monkeypatch.setattr(queue_mod, "mark_queue_item", mark_flaky)
        summary = drain_queue(CONFIG, transport=MockTransport(), repo_root=tmp_path)
        assert "secret_resolution_failed" in summary.notes
        assert any("claim_or_mark_sending_failed" in n or "terminal_mark_failed" in n for n in summary.notes)
        # ensure original helpers still importable
        assert real_claim is not None


# ---------------------------------------------------------------------------
# payload.py
# ---------------------------------------------------------------------------


class TestPayloadCoverage:
    def test_invalid_sha_and_ref_mismatch(self, tmp_path: Path) -> None:
        with pytest.raises(ExportPayloadError, match="invalid payload sha256"):
            payload_ref_for_sha("not-a-sha")
        art = persist_payload_artifact({"ok": True}, repo_root=tmp_path)
        with pytest.raises(ExportPayloadError, match="!="):
            load_payload_artifact(art["payload_ref"], repo_root=tmp_path, expected_sha256="b" * 64)

    def test_persist_rejects_non_object_and_repairs_corrupt(self, tmp_path: Path) -> None:
        with pytest.raises(ExportPayloadError, match="object"):
            persist_payload_artifact(["x"], repo_root=tmp_path)  # type: ignore[arg-type]
        body = {"repair": True}
        art = persist_payload_artifact(body, repo_root=tmp_path)
        art["path"].write_text("{not-json", encoding="utf-8")
        art2 = persist_payload_artifact(body, repo_root=tmp_path)
        assert art2["payload_sha256"] == art["payload_sha256"]
        loaded = load_payload_artifact(art2["payload_ref"], repo_root=tmp_path)
        assert loaded == body

    def test_unreadable_and_non_object_artifact(self, tmp_path: Path) -> None:
        art = persist_payload_artifact({"z": 1}, repo_root=tmp_path)
        art["path"].write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        with pytest.raises(ExportPayloadError, match=r"not an object|mismatch"):
            load_payload_artifact(art["payload_ref"], repo_root=tmp_path, expected_sha256=art["payload_sha256"])

        # unreadable path via directory masquerade
        bad_sha = "c" * 64
        bad_path = tmp_path / ".eval" / "export_payloads" / f"{bad_sha}.json"
        bad_path.parent.mkdir(parents=True, exist_ok=True)
        bad_path.write_text("{", encoding="utf-8")
        with pytest.raises(ExportPayloadError, match="unreadable"):
            load_payload_artifact(f"sha256:{bad_sha}", repo_root=tmp_path)

    def test_verify_size_and_digest_mismatch(self) -> None:
        digest, size = verify_payload_object({"a": 1})
        with pytest.raises(ExportPayloadError, match="sha256 mismatch"):
            verify_payload_object({"a": 1}, expected_sha256="0" * 64)
        with pytest.raises(ExportPayloadError, match="size mismatch"):
            verify_payload_object({"a": 1}, expected_size=size + 5)
        assert len(digest) == 64


# ---------------------------------------------------------------------------
# projections.py
# ---------------------------------------------------------------------------


class TestProjectionCoverage:
    def test_attempts_non_list_and_meta_artifact_class(self) -> None:
        assert select_final_attempt({"attempts": "bad"}) is None
        attempt = {"final_message": "x", "meta": {"artifact_class": "final_accept"}}
        selected = select_final_attempt({"attempts": [attempt]})
        assert selected is attempt

    def test_bundle_level_final_accept_without_attempts(self) -> None:
        selected = select_final_attempt(
            {
                "artifact_class": "final_accept",
                "final_message": "msg",
                "final_message_sha256": "abc",
                "attempts": [],
            }
        )
        assert selected is not None
        assert selected["final_message"] == "msg"

    def test_multiple_explicit_final_accept_fails(self) -> None:
        with pytest.raises(ProjectionError, match="multiple attempts claim"):
            select_final_attempt(
                {
                    "attempts": [
                        {"artifact_class": "final_accept", "final_message": "a"},
                        {"artifact_class": "final_accept", "final_message": "b"},
                    ]
                }
            )

    def test_sha_and_message_identity_matching(self) -> None:
        a1 = {"final_message": "m1", "final_message_sha256": "s1"}
        a2 = {"final_message": "m2", "final_message_sha256": "s2"}
        assert select_final_attempt({"final_message_sha256": "s2", "attempts": [a1, a2]}) is a2
        with pytest.raises(ProjectionError, match="final_message_sha256"):
            select_final_attempt(
                {
                    "final_message_sha256": "s1",
                    "attempts": [
                        {"final_message": "a", "final_message_sha256": "s1"},
                        {"final_message": "b", "final_message_sha256": "s1"},
                    ],
                }
            )
        assert select_final_attempt({"final_message": "m1", "attempts": [a1, a2]}) is a1
        with pytest.raises(ProjectionError, match="final_message identity"):
            select_final_attempt(
                {
                    "final_message": "dup",
                    "attempts": [
                        {"final_message": "dup"},
                        {"final_message": "dup"},
                    ],
                }
            )

    def test_session_thread_non_dict_meta(self) -> None:
        thread = project_session_thread(
            {
                "session_thread_id": "s1",
                "message_versions": [{"role": "assistant", "content": "hi"}],
                "meta": "not-a-dict",
            },
            experiment_name="exp",
        )
        assert thread["thread_id"] == "s1"
        assert thread["lifecycle"] is None
        assert thread["metadata"]["authority"] == "projection"

    def test_score_card_non_dict_and_skips_strings(self) -> None:
        assert project_score_card_to_feedback({"score_card": "nope"}, experiment_name="e") == []
        feedback = project_score_card_to_feedback(
            {
                "score_card": {"format_compliance": 1.0, "label": "skip-me", "notes": "x"},
                "attempts": [{"final_message": "m", "artifact_class": "final_accept"}],
            },
            experiment_name="e",
        )
        names = {f["name"] for f in feedback}
        assert "label" not in names
        assert "notes" not in names


# ---------------------------------------------------------------------------
# queue.py
# ---------------------------------------------------------------------------


class TestQueueCoverage:
    def test_parse_iso_and_lease_edges(self, tmp_path: Path) -> None:
        from git_cg.eval.mirror import queue as q

        assert q._parse_iso(None) is None
        assert q._parse_iso("not-a-date") is None
        naive = q._parse_iso("2026-01-01T00:00:00")
        assert naive is not None and naive.tzinfo is not None
        zulu = q._parse_iso("2026-01-01T00:00:00Z")
        assert zulu is not None

        batch = _batch()
        enqueue_export_batch(batch, repo_root=tmp_path)
        qid = batch["idempotency_key"]
        mark_queue_item(qid, "sending", repo_root=tmp_path, claimed_by="w", lease_seconds=30)
        row = load_queue_item(qid, repo_root=tmp_path)
        row.pop("lease_expires_at", None)
        (export_queue_dir(tmp_path) / f"{qid}.json").write_text(json.dumps(row), encoding="utf-8")
        assert q._lease_expired(load_queue_item(qid, repo_root=tmp_path)) is True
        reclaimed = release_stale_leases(repo_root=tmp_path)
        assert qid in reclaimed

    def test_load_unreadable_and_non_object(self, tmp_path: Path) -> None:
        qdir = export_queue_dir(tmp_path)
        qdir.mkdir(parents=True, exist_ok=True)
        bad = qdir / "bad1.json"
        bad.write_text("{", encoding="utf-8")
        with pytest.raises(ExportQueueError, match="unreadable"):
            load_queue_item("bad1", repo_root=tmp_path)
        arr = qdir / "bad2.json"
        arr.write_text("[1]", encoding="utf-8")
        with pytest.raises(ExportQueueError, match="not an object"):
            load_queue_item("bad2", repo_root=tmp_path)

        # list/release skip unreadable
        assert release_stale_leases(repo_root=tmp_path) == []
        assert list_claimable_items(repo_root=tmp_path) == []

    def test_enqueue_corrupt_existing_and_payload_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        batch = _batch()
        qid = batch["idempotency_key"]
        path = export_queue_dir(tmp_path) / f"{qid}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{", encoding="utf-8")
        # corrupt existing is ignored and rewritten
        out = enqueue_export_batch(batch, repo_root=tmp_path)
        assert out.is_file()

        from git_cg.eval.mirror import queue as q

        def boom(*_a, **_k):
            raise ExportPayloadError("persist failed", error_class="export_validation")

        monkeypatch.setattr(q, "persist_payload_artifact", boom)
        with pytest.raises(ExportQueueError, match="persist failed") as ei:
            enqueue_export_batch(_batch([("other", {"z": 1})]), repo_root=tmp_path)
        assert ei.value.error_class == "export_validation"

    def test_enqueue_schema_validation_failure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from git_cg.eval.mirror import queue as q

        def boom(*_a, **_k):
            raise ValueError("schema no")

        monkeypatch.setattr(q, "validate_instance", boom)
        with pytest.raises(ExportQueueError, match="schema validation"):
            enqueue_export_batch(_batch([("schema-fail", {"a": 1})]), repo_root=tmp_path)

    def test_claim_lock_held_and_stale_break(self, tmp_path: Path) -> None:
        batch = _batch([("lock", {"a": 1})])
        path = enqueue_export_batch(batch, repo_root=tmp_path)
        qid = path.stem
        lock = (export_queue_dir(tmp_path) / f"{qid}.json").with_suffix(".json.claim")
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text("other", encoding="utf-8")
        # fresh lock => cannot claim
        assert claim_queue_item(qid, repo_root=tmp_path, claimed_by="me", lease_seconds=30) is None
        # age the lock
        old = time.time() - 3600
        os.utime(lock, (old, old))
        claimed = claim_queue_item(qid, repo_root=tmp_path, claimed_by="me", lease_seconds=30)
        assert claimed is not None
        assert claimed["status"] == "sending"

    def test_claim_none_when_missing_or_sent(self, tmp_path: Path) -> None:
        assert claim_queue_item("missing", repo_root=tmp_path) is None
        batch = _batch([("sentrow", {"a": 1})])
        path = enqueue_export_batch(batch, repo_root=tmp_path)
        qid = path.stem
        mark_queue_item(qid, "sending", repo_root=tmp_path, claimed_by="t")
        mark_queue_item(qid, "sent", repo_root=tmp_path, clear_lease=True)
        assert claim_queue_item(qid, repo_root=tmp_path) is None

    def test_mark_schema_validation_failure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from git_cg.eval.mirror import queue as q

        batch = _batch([("markfail", {"a": 1})])
        path = enqueue_export_batch(batch, repo_root=tmp_path)
        qid = path.stem

        def boom(*_a, **_k):
            raise ValueError("bad schema")

        monkeypatch.setattr(q, "validate_instance", boom)
        with pytest.raises(ExportQueueError, match="schema validation"):
            mark_queue_item(qid, "pending", repo_root=tmp_path)


# ---------------------------------------------------------------------------
# transport.py
# ---------------------------------------------------------------------------


class TestTransportCoverage:
    def test_scrub_truncation(self) -> None:
        # After URL/secret scrub, pad with plain text so the length clamp fires.
        text = "https://example.com/path " + ("plain " * 80)
        scrubbed = scrub_export_note(text, limit=40)
        assert "example.com" not in scrubbed
        assert scrubbed.endswith("…")
        assert len(scrubbed) <= 40

    def test_status_code_extraction(self) -> None:
        from git_cg.eval.mirror import transport as t

        class EError(Exception):
            pass

        e = EError("nope")
        e.status_code = "401"  # type: ignore[attr-defined]
        assert t._status_code_of(e) == 401
        e2 = EError("x")
        e2.response = SimpleNamespace(status_code=413)  # type: ignore[attr-defined]
        assert t._status_code_of(e2) == 413
        e3 = EError("HTTP 422 unprocessable")
        assert t._status_code_of(e3) == 422

    def test_classify_size_and_passthrough(self) -> None:
        original = ExportTransportError("export_auth", "nope")
        assert classify_export_error(original) is original

        class TooLargeError(Exception):
            pass

        err = classify_export_error(TooLargeError("payload too large"))
        assert err.error_class == "export_size"

        class SizeError(Exception):
            status_code = 413

        assert classify_export_error(SizeError("big")).error_class == "export_size"

    def test_bounded_flush_no_flush_and_timeout_ms_fallback(self) -> None:
        # no flush attr
        OpikSdkTransport._bounded_flush(SimpleNamespace(), timeout_ms=1000, deadline=time.monotonic() + 5)

        calls: list[Any] = []

        # first signature TypeError on timeout=, then timeout_ms path
        state = {"n": 0}

        def flush(**kwargs):
            state["n"] += 1
            if "timeout" in kwargs:
                raise TypeError("no timeout")
            calls.append(kwargs)
            return True

        OpikSdkTransport._bounded_flush(SimpleNamespace(flush=flush), timeout_ms=1500, deadline=time.monotonic() + 5)
        assert calls and "timeout_ms" in calls[0]

    def test_bounded_flush_exception_and_false(self) -> None:
        def flush_err(*, timeout: int):
            raise RuntimeError("network down")

        with pytest.raises(ExportTransportError) as ei:
            OpikSdkTransport._bounded_flush(
                SimpleNamespace(flush=flush_err), timeout_ms=1000, deadline=time.monotonic() + 5
            )
        assert ei.value.error_class in {"export_network", "export_validation"}

        def flush_false(*, timeout: int):
            return False

        with pytest.raises(ExportTransportError, match="flush returned false"):
            OpikSdkTransport._bounded_flush(
                SimpleNamespace(flush=flush_false), timeout_ms=1000, deadline=time.monotonic() + 5
            )

    def test_send_projects_thread_fields(self) -> None:
        recorded: list[dict] = []

        class Client:
            def trace(self, **kwargs):
                recorded.append(kwargs)

        payload = {
            "items": [
                {
                    "payload": {
                        "thread": {
                            "thread_id": "t1",
                            "messages": [{"role": "user", "content": "hi"}],
                            "metadata": {"x": 1},
                        }
                    }
                }
            ]
        }
        OpikSdkTransport._send(Client(), experiment_name="exp", payload=payload)
        assert len(recorded) == 1
        call = recorded[0]
        # Thread-only rows synthesize input/output from the thread surface.
        assert call["input"]["thread_id"] == "t1"
        assert call["output"]["messages"] == [{"role": "user", "content": "hi"}]
        assert call["metadata"]["thread"]["thread_id"] == "t1"
        assert call["metadata"]["thread"]["messages"] == [{"role": "user", "content": "hi"}]
        assert call["name"] == "exp"
