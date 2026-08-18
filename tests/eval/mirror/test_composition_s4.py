"""S4/S5 composition / drain-path proofs (claims S4-D/E/F path, P0-5 join).

Leaf unit tests are necessary but not sufficient. This module joins:
redact → project → experiment pins → batch → enqueue → drain(mock)
and asserts dual-axis / fail-open invariants on the composition path.

``build_export_plan`` is the sole merge-evidence composition API (E8).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from git_cg.eval.enums import RedactionProfile
from git_cg.eval.mirror.batch import build_export_batches
from git_cg.eval.mirror.composition import build_export_plan
from git_cg.eval.mirror.experiments import build_experiment
from git_cg.eval.mirror.exporter import drain_queue, mirror_result_from_drain
from git_cg.eval.mirror.health import ExportHealth
from git_cg.eval.mirror.projections import (
    FEEDBACK_SOURCE,
    project_bundle_to_trace,
    project_score_card_to_feedback,
    project_session_thread,
)
from git_cg.eval.mirror.queue import enqueue_export_batch, load_queue_item, load_queue_payload
from git_cg.eval.mirror.redaction import redact_bundle_for_export
from git_cg.eval.mirror.result import evaluation_job_result, export_result
from git_cg.eval.mirror.secrets import OpikRuntimeSecrets
from git_cg.eval.mirror.train import build_train_projection
from git_cg.eval.mirror.transport import ExportTransportError, MockTransport

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


def _bundle() -> dict:
    return {
        "id": "bundle_comp_1",
        "schema_version": "ape_bundle_v1",
        "artifact_class": "final_accept",
        "gate": {"deterministic_pass": True, "authority": "product"},
        "score_card": {
            "format_compliance": 1.0,
            "subject_length": 0.9,
            "deterministic_flag": True,
        },
        "attempts": [
            {
                "final_message": "✨ feat(scope): subject",
                "scored_target": "final_message",
                "artifact_class": "final_accept",
                "diff": "@@ forbidden @@",
                "prompt": "full prompt text",
                "api_key": "should-never-export",
            }
        ],
        "meta": {
            "redaction_profile": "default_scrub",
            "train_label": "positive",
            "split_group_id": "sg-comp-1",
            "provenance_label": "acceptpath-live",
            "regime": "A",
            "api_key": "evt-secret",
        },
        "session_thread_id": "sess_comp_1",
    }


def _session() -> dict:
    """Create a representative closed session thread fixture for composition tests."""
    return {
        "schema_version": "commit_session_thread_v1",
        "session_thread_id": "sess_comp_1",
        "message_versions": [{"role": "assistant", "content": "draft"}],
        "attempt_ids": ["a1"],
        "redaction_profile": "default_scrub",
        "meta": {"lifecycle": "closed", "trace_id": "t1"},
    }


class TestCompositionDrainPath:
    def test_redact_project_batch_enqueue_drain_preserves_authority(self, tmp_path: Path) -> None:
        redacted = redact_bundle_for_export(_bundle(), RedactionProfile.DEFAULT_SCRUB)
        blob = str(redacted).lower()
        assert "should-never-export" not in blob
        assert "full prompt text" not in blob
        assert "@@ forbidden @@" not in blob

        exp = build_experiment(
            "mirror",
            "v0",
            git_sha="abc1234",
            when=datetime(2026, 8, 16, 12, 0, 0, tzinfo=UTC),
            environment="eval",
            project="eval-project",
            dataset_id="cm-eval-fixtures-core",
            redaction_profile="default_scrub",
            content_key=str(redacted.get("id") or "bundle_comp_1"),
        )
        assert exp["experiment_name"].startswith("eval_mirror_v0_abc1234_")
        pins = exp["meta"]["pins"]
        assert pins["schema_pack"] and "@" in pins["schema_pack"]
        assert pins["metric_catalog"] and "@" in pins["metric_catalog"]
        assert pins["git_sha"] == "abc1234"

        trace = project_bundle_to_trace(redacted, experiment_name=exp["experiment_name"])
        feedback = project_score_card_to_feedback(redacted, experiment_name=exp["experiment_name"])
        thread = project_session_thread(_session(), experiment_name=exp["experiment_name"])

        assert trace["metadata"]["deterministic_pass"] is True
        assert trace["metadata"]["score_card"]["format_compliance"] == 1.0
        feedback_names = {f["name"] for f in feedback}
        feedback_metric_ids = {f.get("metric_id") for f in feedback}
        feedback_keys = {(f.get("authority") or {}).get("score_card_key") for f in feedback}
        # Catalog may promote bare keys (e.g. subject_length -> b.subject_length).
        assert {"format_compliance", "deterministic_flag"} <= (feedback_names | feedback_metric_ids | feedback_keys)
        assert any(
            n == "subject_length" or str(n).endswith("subject_length")
            for n in (feedback_names | feedback_metric_ids | feedback_keys)
        )
        assert all(f["source"] == FEEDBACK_SOURCE for f in feedback)
        bool_row = next(
            f for f in feedback if f.get("metric_id") == "deterministic_flag" or f["name"] == "deterministic_flag"
        )
        assert bool_row["value"] == 1.0
        assert bool_row["polarity"] == "pass_fail"
        assert thread["thread_id"] == "sess_comp_1"
        assert trace["metadata"]["authority"]["cloud_rescore_forbidden"] is True

        # Transport payload body is the projected local evidence (not re-scored).
        transport_payload = {
            "trace": trace,
            "feedback": feedback,
            "thread": thread,
            "experiment": exp,
            "gate": redacted.get("gate"),
            "score_card": redacted.get("score_card"),
        }
        batches = build_export_batches(
            [("bundle_comp_1", transport_payload)],
            RedactionProfile.DEFAULT_SCRUB,
            project="eval-project",
            experiment_id=exp["experiment_name"],
            environment="eval",
            dataset_id="cm-eval-fixtures-core",
            project_lane="eval",
        )
        assert len(batches) == 1
        batch = batches[0]
        assert batch["redaction_profile"] == "default_scrub"
        assert batch["project"] == "eval-project"

        path = enqueue_export_batch(batch, repo_root=tmp_path)
        qid = path.stem

        transport = MockTransport()
        summary = drain_queue(CONFIG, transport=transport, repo_root=tmp_path, secrets=SECRETS)
        assert summary.exported >= 1
        assert summary.failed == 0
        assert len(transport.calls) >= 1

        row = load_queue_item(qid, repo_root=tmp_path)
        assert row["status"] == "sent"
        # Sent rows must not retain an export_* failure class.
        assert not str(row.get("last_error_class") or "").startswith("export_")

        uploaded = transport.calls[0]["payload"]
        assert isinstance(uploaded, dict)
        # Authority markers survive the composition path.
        items = uploaded.get("items") or []
        assert items, uploaded
        body = items[0].get("payload") or items[0]
        assert body.get("gate", {}).get("deterministic_pass") is True
        assert body.get("score_card", {}).get("format_compliance") == 1.0

        result = mirror_result_from_drain(CONFIG, summary)
        assert result.product_accept_blocked is False
        er = export_result(result)
        assert er["product_accept_blocked"] is False
        ej = evaluation_job_result(result)
        assert ej["product_accept_blocked"] is False

        train = build_train_projection([redacted])
        assert train["positive_gold"]
        assert train["ci_sole_green"] is False
        assert train["product_accept_authority"] is False

    def test_build_export_plan_is_sole_join_path(self, tmp_path: Path) -> None:
        plan = build_export_plan(
            {"bundles": [_bundle()], "session_threads": [_session()], "include_train": True},
            CONFIG,
            repo_root=tmp_path,
            git_sha="abc1234",
            when=datetime(2026, 8, 16, 12, 0, 0, tzinfo=UTC),
        )
        assert plan.product_accept_blocked is False
        assert plan.enqueued >= 1
        assert plan.queue_row_refs
        assert plan.health.value in {"pending", "partial", "success"}
        assert plan.train is not None
        assert plan.train["ci_sole_green"] is False

        transport = MockTransport()
        summary = drain_queue(CONFIG, transport=transport, repo_root=tmp_path, secrets=SECRETS)
        assert summary.exported >= 1
        assert summary.failed == 0
        uploaded = transport.calls[0]["payload"]
        items = uploaded.get("items") or []
        body = items[0].get("payload") or items[0]
        assert body.get("gate", {}).get("deterministic_pass") is True
        assert body.get("score_card", {}).get("format_compliance") == 1.0
        assert body.get("trace", {}).get("metadata", {}).get("authority", {}).get("source") == FEEDBACK_SOURCE
        feedback = body.get("feedback") or []
        assert feedback and all(f.get("source") == FEEDBACK_SOURCE for f in feedback)
        assert body.get("thread", {}).get("thread_id") == "sess_comp_1"

        for qid in plan.queue_row_refs:
            row = load_queue_item(qid, repo_root=tmp_path)
            assert row["status"] == "sent"

    def test_build_export_plan_mode_off_short_circuits(self, tmp_path: Path) -> None:
        plan = build_export_plan(_bundle(), {**CONFIG, "mode": "off"}, repo_root=tmp_path)
        assert plan.enqueued == 0
        assert plan.health.value == "skipped_off"
        assert plan.product_accept_blocked is False

    def test_transport_failure_is_fail_open_on_product_axis(self, tmp_path: Path) -> None:
        redacted = redact_bundle_for_export(_bundle(), RedactionProfile.DEFAULT_SCRUB)
        exp = build_experiment("mirror", "v0", git_sha="abc1234", content_key="fail-path")
        payload = {
            "trace": project_bundle_to_trace(redacted, experiment_name=exp["experiment_name"]),
            "feedback": project_score_card_to_feedback(redacted, experiment_name=exp["experiment_name"]),
            "experiment": exp,
            "gate": redacted.get("gate"),
            "score_card": redacted.get("score_card"),
        }
        batches = build_export_batches(
            [("bundle_fail", payload)],
            "default_scrub",
            project="eval-project",
            experiment_id=exp["experiment_name"],
        )
        path = enqueue_export_batch(batches[0], repo_root=tmp_path)
        qid = path.stem

        transport = MockTransport(fail_with=ExportTransportError("export_network", "boom"))
        summary = drain_queue(CONFIG, transport=transport, repo_root=tmp_path, secrets=SECRETS)
        assert summary.failed >= 1
        assert "export_network" in summary.error_classes

        row = load_queue_item(qid, repo_root=tmp_path)
        assert row["status"] == "failed"
        assert row["last_error_class"] == "export_network"

        result = mirror_result_from_drain(CONFIG, summary)
        assert result.product_accept_blocked is False
        assert export_result(result)["product_accept_blocked"] is False
        # Offline local evidence remains green after export throw.
        assert redacted["gate"]["deterministic_pass"] is True


def test_e12_invalid_mode_fallback_is_config_error_on_composition(tmp_path: Path) -> None:
    """E12: mode_fallback must not short-circuit as silent skipped_off only."""
    from git_cg.eval.mirror.config import resolve_opik_config

    cfg = resolve_opik_config(env={"GIT_CG_OPIK_MODE": "not-a-mode"})
    plan = build_export_plan([_bundle()], cfg, repo_root=tmp_path, enqueue=False)
    assert plan.mode == "off"
    assert plan.health is ExportHealth.CONFIG_ERROR
    assert plan.product_accept_blocked is False
    assert "export_validation" in plan.error_classes
    assert any("config_error" in n for n in plan.notes)
    mirror = plan.as_mirror_result()
    assert mirror.health is ExportHealth.CONFIG_ERROR
    assert mirror.product_accept_blocked is False


class TestCompositionAuthorityAndSessionFallback:
    def test_standalone_session_authority_is_nested(self, tmp_path: Path) -> None:
        plan = build_export_plan(
            {"bundles": [], "session_threads": [_session()], "include_train": False},
            CONFIG,
            repo_root=tmp_path,
            git_sha="abc1234",
            when=datetime(2026, 8, 16, 12, 0, 0, tzinfo=UTC),
        )
        assert plan.enqueued >= 1, plan.notes
        qid = plan.queue_row_refs[0]
        body = load_queue_payload(qid, repo_root=tmp_path)
        items = body.get("items") or []
        assert items
        payload = items[0].get("payload") or {}
        # Nested authority only — never the entire metadata map.
        assert payload.get("authority") == "projection"
        thread = payload.get("thread") or {}
        assert (thread.get("metadata") or {}).get("authority") == "projection"
        # Authority is the nested scalar, never the metadata map.
        assert not isinstance(payload.get("authority"), dict)

    def test_session_correlation_prefers_source_bundle_id(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Even if redaction dropped session_thread_id, source correlation still joins."""
        from git_cg.eval.mirror import composition as composition_mod

        bundle = _bundle()
        session = _session()
        assert bundle["session_thread_id"] == session["session_thread_id"]

        real_redact = composition_mod.redact_bundle_for_export

        def drop_session(bundle_in, profile):  # type: ignore[no-untyped-def]
            """Redacts a bundle and removes session thread identifiers from the result."""
            out = real_redact(bundle_in, profile)
            out = dict(out)
            out.pop("session_thread_id", None)
            meta = dict(out.get("meta") or {})
            meta.pop("session_thread_id", None)
            out["meta"] = meta
            return out

        monkeypatch.setattr(composition_mod, "redact_bundle_for_export", drop_session)
        plan = build_export_plan(
            {"bundles": [bundle], "session_threads": [session], "include_train": False},
            CONFIG,
            repo_root=tmp_path,
            git_sha="abc1234",
            when=datetime(2026, 8, 16, 12, 0, 0, tzinfo=UTC),
        )
        assert plan.projected >= 1
        assert plan.enqueued >= 1, plan.notes
        body = load_queue_payload(plan.queue_row_refs[0], repo_root=tmp_path)
        item_payloads = [entry.get("payload") for entry in body.get("items", []) if isinstance(entry, dict)]
        assert any(isinstance(p, dict) and "thread" in p for p in item_payloads)
