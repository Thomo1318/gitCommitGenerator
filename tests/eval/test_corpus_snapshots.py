"""S1-B: dataset_snapshot_v1 determinism — offline only."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from git_cg.eval.corpus import fixtures as fixtures_mod, snapshots as snapshots_mod, suites as suites_mod
from git_cg.eval.corpus.canonical import canonical_json_text
from git_cg.eval.corpus.snapshots import build_core_snapshot, build_snapshot
from git_cg.eval.schema_pack import validate_instance


def test_s1_b01_reencode_identical_bundle_bytes() -> None:
    a = build_snapshot("cm-eval-fixtures-core")
    b = build_snapshot("cm-eval-fixtures-core")
    assert a["bundles"] == b["bundles"]
    for left, right in zip(a["bundles"], b["bundles"], strict=True):
        assert canonical_json_text(left) == canonical_json_text(right)


def test_s1_b02_reencode_identical_case_identities() -> None:
    a = build_snapshot("cm-eval-fixtures-core")
    b = build_snapshot("cm-eval-fixtures-core")
    assert a["items"] == b["items"]
    assert [c["bundle_ref"] for c in a["cases"]] == [c["bundle_ref"] for c in b["cases"]]


def test_s1_b03_snapshot_hash_stable_across_two_builds() -> None:
    a = build_core_snapshot()
    b = build_core_snapshot()
    assert a == b
    assert a["snapshot_hash"] == b["snapshot_hash"]
    assert len(a["snapshot_hash"]) == 64
    validate_instance("dataset_snapshot_v1", a)


def test_s1_b04_content_change_changes_snapshot_hash(tmp_path, monkeypatch) -> None:
    src = Path("tests/fixtures/eval")
    dst = tmp_path / "eval"
    shutil.copytree(src, dst)
    target = dst / "cases/valid/seed-v1-valid-fixture.json"
    data = target.read_text(encoding="utf-8")
    target.write_text(
        data.replace("add offline fixture seed", "CHANGED offline fixture seed"),
        encoding="utf-8",
    )

    monkeypatch.setattr(fixtures_mod, "DEFAULT_FIXTURE_ROOT", dst)
    monkeypatch.setattr(suites_mod, "default_fixture_root", lambda: dst)
    monkeypatch.setattr(snapshots_mod, "default_fixture_root", lambda: dst)
    changed = build_core_snapshot()

    monkeypatch.setattr(fixtures_mod, "DEFAULT_FIXTURE_ROOT", src)
    monkeypatch.setattr(suites_mod, "default_fixture_root", lambda: src)
    monkeypatch.setattr(snapshots_mod, "default_fixture_root", lambda: src)
    original = build_core_snapshot()
    assert changed["snapshot_hash"] != original["snapshot_hash"]


def test_s1_b05_order_swap_changes_snapshot_hash(tmp_path, monkeypatch) -> None:
    src = Path("tests/fixtures/eval")
    dst = tmp_path / "eval"
    shutil.copytree(src, dst)
    suite_path = dst / "suites/cm-eval-fixtures-core.json"
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    suite["case_ids"] = list(reversed(suite["case_ids"]))
    suite_path.write_text(json.dumps(suite, indent=2) + "\n", encoding="utf-8")

    monkeypatch.setattr(fixtures_mod, "DEFAULT_FIXTURE_ROOT", dst)
    monkeypatch.setattr(suites_mod, "default_fixture_root", lambda: dst)
    monkeypatch.setattr(snapshots_mod, "default_fixture_root", lambda: dst)
    swapped = build_core_snapshot()

    monkeypatch.setattr(fixtures_mod, "DEFAULT_FIXTURE_ROOT", src)
    monkeypatch.setattr(suites_mod, "default_fixture_root", lambda: src)
    monkeypatch.setattr(snapshots_mod, "default_fixture_root", lambda: src)
    original = build_core_snapshot()
    assert swapped["snapshot_hash"] != original["snapshot_hash"]
    assert swapped["meta"]["case_ids"] == list(reversed(original["meta"]["case_ids"]))


def test_build_snapshot_result_includes_valid_suite_pin_view() -> None:
    result = build_snapshot("cm-eval-fixtures-core")
    assert result["snapshot_hash"] == result["snapshot"]["snapshot_hash"]
    assert result["snapshot"]["item_count"] == 3
