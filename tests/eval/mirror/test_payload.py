"""S4 Slice 3 — content-addressed payload artifacts (P0-3 / E10 / E11)."""

from __future__ import annotations

import json
import stat

import pytest

from git_cg.eval.corpus.canonical import content_sha256
from git_cg.eval.mirror.payload import (
    EXPORT_PAYLOADS_DIRNAME,
    ExportPayloadError,
    export_payloads_dir,
    load_payload_artifact,
    payload_ref_for_sha,
    persist_payload_artifact,
    verify_payload_object,
)


def test_persist_and_load_roundtrip(tmp_path) -> None:
    body = {"items": [{"item_ref": "i-1", "payload": {"x": 1}}], "redaction_profile": "default_scrub"}
    art = persist_payload_artifact(body, repo_root=tmp_path)
    assert art["payload_ref"].startswith("sha256:")
    assert art["payload_sha256"] == content_sha256(body)
    assert art["path"].parent == export_payloads_dir(tmp_path)
    assert EXPORT_PAYLOADS_DIRNAME in str(art["path"])

    loaded = load_payload_artifact(
        art["payload_ref"],
        repo_root=tmp_path,
        expected_sha256=art["payload_sha256"],
        expected_size=art["payload_size_bytes"],
    )
    assert loaded == body


def test_persist_is_idempotent(tmp_path) -> None:
    body = {"k": "v"}
    a1 = persist_payload_artifact(body, repo_root=tmp_path)
    a2 = persist_payload_artifact(body, repo_root=tmp_path)
    assert a1["payload_sha256"] == a2["payload_sha256"]
    assert a1["path"] == a2["path"]


def test_missing_artifact_is_export_validation(tmp_path) -> None:
    ref = payload_ref_for_sha("a" * 64)
    with pytest.raises(ExportPayloadError, match="missing") as ei:
        load_payload_artifact(ref, repo_root=tmp_path)
    assert ei.value.error_class == "export_validation"


def test_corrupt_artifact_fails_hash_verify(tmp_path) -> None:
    body = {"ok": True}
    art = persist_payload_artifact(body, repo_root=tmp_path)
    art["path"].write_text(json.dumps({"tampered": True}), encoding="utf-8")
    with pytest.raises(ExportPayloadError, match="mismatch") as ei:
        load_payload_artifact(art["payload_ref"], repo_root=tmp_path, expected_sha256=art["payload_sha256"])
    assert ei.value.error_class == "export_validation"


def test_size_mismatch_fails_closed(tmp_path) -> None:
    body = {"ok": True}
    art = persist_payload_artifact(body, repo_root=tmp_path)
    with pytest.raises(ExportPayloadError, match="size mismatch"):
        load_payload_artifact(
            art["payload_ref"],
            repo_root=tmp_path,
            expected_sha256=art["payload_sha256"],
            expected_size=art["payload_size_bytes"] + 1,
        )


def test_verify_rejects_non_object() -> None:
    with pytest.raises(ExportPayloadError, match="object"):
        verify_payload_object(["not", "an", "object"])  # type: ignore[arg-type]


def test_artifact_permissions_are_restrictive(tmp_path) -> None:
    art = persist_payload_artifact({"z": 1}, repo_root=tmp_path)
    mode = art["path"].stat().st_mode & 0o777
    assert mode & stat.S_IRWXO == 0
    assert mode & stat.S_IWGRP == 0
