"""Edge-path coverage for git_cg.eval.corpus (S1 offline package).

Targets previously uncovered branches: lazy exports, load failures,
CLI mains, topology/counter/split/replay negatives, and suite pin errors.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import pytest

from git_cg.eval.corpus import encoder, materialize
from git_cg.eval.corpus.aliases import DatasetAliasError, canonicalize_dataset_id, resolve_dataset_id
from git_cg.eval.corpus.encoder import CorpusEncodeError, encode_fixture
from git_cg.eval.corpus.fixtures import FixtureLoadError, load_fixture_dict, load_suite_fixtures
from git_cg.eval.corpus.index import build_fixture_index, main as index_main, write_fixture_index
from git_cg.eval.corpus.materialize import (
    main as materialize_main,
    materialize_core_goldens,
)
from git_cg.eval.corpus.snapshots import SnapshotBuildError, build_core_snapshot, build_snapshot
from git_cg.eval.corpus.suites import SuiteLoadError, load_suite, materialize_suite
from git_cg.eval.corpus.task_input import TaskInputError, project_generation_task_input


def _minimal_fixture(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "case_id": "edge-case",
        "artifact_class": "fixture_expected",
        "bound": False,
        "provenance_label": "fixture",
        "redaction_profile": "default_scrub",
        "final_message": "✨ feat(eval): edge coverage seed",
        "generation_task_input": {
            "diff_summary": "add edge coverage",
            "path_class_gate": "tests",
            "ranked_intent_id": "feat",
        },
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Lazy package exports
# ---------------------------------------------------------------------------


def test_corpus_package_lazy_exports_and_unknown() -> None:
    pkg = importlib.import_module("git_cg.eval.corpus")
    assert callable(pkg.build_fixture_index)
    assert callable(pkg.write_fixture_index)
    assert callable(pkg.materialize_core_goldens)
    assert callable(pkg.materialize_suite_bundles)
    assert callable(pkg.materialize_suite_snapshot)
    with pytest.raises(AttributeError, match="has no attribute"):
        _ = pkg.definitely_not_an_export  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Aliases
# ---------------------------------------------------------------------------


def test_resolve_dataset_id_rejects_empty_and_unknown() -> None:
    with pytest.raises(DatasetAliasError, match="non-empty"):
        resolve_dataset_id("")
    with pytest.raises(DatasetAliasError, match="non-empty"):
        resolve_dataset_id("   ")
    with pytest.raises(DatasetAliasError, match="unknown dataset"):
        resolve_dataset_id("not-a-real-dataset")
    assert canonicalize_dataset_id("cm-eval-204-archive") == "204-archive"


# ---------------------------------------------------------------------------
# Fixtures loader edges
# ---------------------------------------------------------------------------


def test_load_fixture_dict_errors(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(FixtureLoadError, match="missing fixture"):
        load_fixture_dict(missing)

    bad = tmp_path / "bad.json"
    bad.write_text("{not-json", encoding="utf-8")
    with pytest.raises(FixtureLoadError, match="invalid fixture JSON"):
        load_fixture_dict(bad)

    arr = tmp_path / "arr.json"
    arr.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(FixtureLoadError, match="must be an object"):
        load_fixture_dict(arr)


def test_load_suite_fixtures_path_escape_and_fallbacks(tmp_path: Path) -> None:
    root = tmp_path / "fixtures"
    cases = root / "cases"
    cases.mkdir(parents=True)
    (cases / "only.json").write_text(json.dumps({"case_id": "only", "x": 1}), encoding="utf-8")
    (root / "cases" / "valid").mkdir()
    # bare case id under cases/
    (cases / "bare-id.json").write_text(json.dumps({"case_id": "bare-id"}), encoding="utf-8")

    # path escape
    # Create a path that resolves outside root via .. components
    with pytest.raises(FixtureLoadError, match="escapes fixture root"):
        # Resolve candidate = (root / rel).resolve() starts with root? using deep ..
        load_suite_fixtures(
            {
                "case_ids": ["evil"],
                "case_paths": {"evil": str(Path("..") / ".." / ".." / "etc" / "passwd")},
            },
            fixture_root=root,
        )

    # empty / invalid case_ids
    with pytest.raises(FixtureLoadError, match="non-empty list"):
        load_suite_fixtures({"case_ids": []}, fixture_root=root)
    with pytest.raises(FixtureLoadError, match="invalid case_id"):
        load_suite_fixtures({"case_ids": [""]}, fixture_root=root)
    with pytest.raises(FixtureLoadError, match="duplicate case_id"):
        load_suite_fixtures({"case_ids": ["only", "only"]}, fixture_root=root)
    with pytest.raises(FixtureLoadError, match="case_paths must be an object"):
        load_suite_fixtures({"case_ids": ["a"], "case_paths": ["nope"]}, fixture_root=root)

    # default lookup via rglob single match
    pairs = load_suite_fixtures({"case_ids": ["only"]}, fixture_root=root)
    assert pairs[0][0] == "only"

    # ambiguous matches
    nested = cases / "nested"
    nested.mkdir()
    (nested / "only.json").write_text(json.dumps({"case_id": "only"}), encoding="utf-8")
    with pytest.raises(FixtureLoadError, match="ambiguous"):
        load_suite_fixtures({"case_ids": ["only"]}, fixture_root=root)

    # missing case
    with pytest.raises(FixtureLoadError, match="missing case fixture"):
        load_suite_fixtures({"case_ids": ["nope"]}, fixture_root=root)

    # case_id mismatch
    (cases / "mismatch.json").write_text(json.dumps({"case_id": "other"}), encoding="utf-8")
    with pytest.raises(FixtureLoadError, match="!="):
        load_suite_fixtures(
            {"case_ids": ["mismatch"], "case_paths": {"mismatch": "cases/mismatch.json"}},
            fixture_root=root,
        )

    # extensionless / bare lookup under cases/
    pairs2 = load_suite_fixtures(
        {"case_ids": ["bare-id"], "case_paths": {"bare-id": "bare-id"}},
        fixture_root=root,
    )
    assert pairs2[0][0] == "bare-id"


def test_load_suite_fixtures_session_and_archive_defaults(tmp_path: Path) -> None:
    root = tmp_path / "fx"
    (root / "cases" / "session-12").mkdir(parents=True)
    (root / "cases" / "204-archive").mkdir(parents=True)
    (root / "cases" / "session-12" / "s12.json").write_text(json.dumps({"case_id": "s12"}), encoding="utf-8")
    (root / "cases" / "204-archive" / "a204.json").write_text(json.dumps({"case_id": "a204"}), encoding="utf-8")
    pairs = load_suite_fixtures({"case_ids": ["s12", "a204"]}, fixture_root=root)
    assert [c for c, _ in pairs] == ["s12", "a204"]


# ---------------------------------------------------------------------------
# Encoder fail-closed edges
# ---------------------------------------------------------------------------


def test_encode_fixture_type_and_enum_errors() -> None:
    with pytest.raises(CorpusEncodeError, match="fixture must be an object"):
        encode_fixture([])  # type: ignore[arg-type]
    with pytest.raises(CorpusEncodeError, match="case_id is required"):
        encode_fixture({})
    with pytest.raises(CorpusEncodeError, match="artifact_class must be a string"):
        encode_fixture(_minimal_fixture(artifact_class=1))
    with pytest.raises(CorpusEncodeError, match="unknown artifact_class"):
        encode_fixture(_minimal_fixture(artifact_class="not-real"))
    with pytest.raises(CorpusEncodeError, match="bound must be a boolean"):
        encode_fixture(_minimal_fixture(bound="yes"))  # type: ignore[arg-type]
    with pytest.raises(CorpusEncodeError, match="final_accept requires bound=true"):
        encode_fixture(_minimal_fixture(bound=False, provenance_label="final_accept"))
    with pytest.raises(CorpusEncodeError, match="incompatible with provenance_label=Opik-unbound"):
        encode_fixture(_minimal_fixture(bound=True, provenance_label="Opik-unbound", unbound_reason=None))
    with pytest.raises(CorpusEncodeError, match="redaction_profile must be a string"):
        encode_fixture(_minimal_fixture(redaction_profile=3))
    with pytest.raises(CorpusEncodeError, match="invalid regime"):
        encode_fixture(_minimal_fixture(regime="Z"))
    with pytest.raises(CorpusEncodeError, match="path_class_gate must be a string"):
        encode_fixture(_minimal_fixture(path_class_gate=1))
    with pytest.raises(CorpusEncodeError, match="must be a string when present"):
        encode_fixture(_minimal_fixture(final_message=12))
    with pytest.raises(CorpusEncodeError, match="array of strings"):
        encode_fixture(_minimal_fixture(expected_gold_codes=[1]))
    with pytest.raises(CorpusEncodeError, match="meta must be an object"):
        encoder._meta_with_producer(["nope"])  # type: ignore[arg-type]


def test_encode_fixture_204_archive_requirements() -> None:
    with pytest.raises(CorpusEncodeError, match="204_archive fixtures require regime"):
        encode_fixture(
            _minimal_fixture(
                regime="n/a",
                failure_ids=[],
                meta={"corpus_source": "204_archive"},
            )
        )
    with pytest.raises(CorpusEncodeError, match="require failure_ids"):
        encode_fixture(
            _minimal_fixture(
                regime="A",
                meta={"corpus_source": "204_archive"},
            )
        )
    with pytest.raises(CorpusEncodeError, match="session-12-seed"):
        encode_fixture(
            _minimal_fixture(
                regime="unknown",
                failure_ids=[],
                tags=["session-12-seed"],
                meta={"corpus_source": "204_archive"},
            )
        )


def test_encode_topology_counter_split_replay_negatives() -> None:
    with pytest.raises(CorpusEncodeError, match="unknown topology status"):
        encode_fixture(_minimal_fixture(meta={"topology": {"status": "broken", "require_complete_for_encode": True}}))
    with pytest.raises(CorpusEncodeError, match="required_spans must be an array"):
        encode_fixture(
            _minimal_fixture(meta={"topology": {"required_spans": "x", "require_complete_for_encode": True}})
        )
    with pytest.raises(CorpusEncodeError, match="observed_spans must be an array"):
        encode_fixture(
            _minimal_fixture(meta={"topology": {"observed_spans": "x", "require_complete_for_encode": True}})
        )
    with pytest.raises(CorpusEncodeError, match="missing_spans must be an array"):
        encode_fixture(_minimal_fixture(meta={"topology": {"missing_spans": "x", "require_complete_for_encode": True}}))
    with pytest.raises(CorpusEncodeError, match="status=incomplete"):
        encode_fixture(
            _minimal_fixture(meta={"topology": {"status": "incomplete", "require_complete_for_encode": True}})
        )
    with pytest.raises(CorpusEncodeError, match="missing required spans"):
        encode_fixture(
            _minimal_fixture(
                meta={
                    "topology": {
                        "status": "complete",
                        "required_spans": ["a", "b"],
                        "observed_spans": ["a"],
                        "require_complete_for_encode": True,
                    }
                }
            )
        )
    with pytest.raises(CorpusEncodeError, match="missing_spans non-empty"):
        encode_fixture(
            _minimal_fixture(
                meta={
                    "topology": {
                        "status": "complete",
                        "missing_spans": ["z"],
                        "require_complete_for_encode": True,
                    }
                }
            )
        )
    with pytest.raises(CorpusEncodeError, match="counters and span_counts"):
        encode_fixture(_minimal_fixture(meta={"evidence": {"require_counter_span_consistent": True}}))
    with pytest.raises(CorpusEncodeError, match="must be integers"):
        encode_fixture(
            _minimal_fixture(
                meta={
                    "evidence": {
                        "require_counter_span_consistent": True,
                        "counters": {"gold_regen_attempts": "x"},
                        "span_counts": {"regeneration": "y"},
                    }
                }
            )
        )
    with pytest.raises(CorpusEncodeError, match="regeneration span count is 0"):
        encode_fixture(
            _minimal_fixture(
                meta={
                    "evidence": {
                        "require_counter_span_consistent": True,
                        "counters": {"gold_regen_attempts": 2},
                        "span_counts": {"regeneration": 0},
                    }
                }
            )
        )
    with pytest.raises(CorpusEncodeError, match="gold_regen_attempts==0"):
        encode_fixture(
            _minimal_fixture(
                meta={
                    "evidence": {
                        "require_counter_span_consistent": True,
                        "counters": {"gold_regen_attempts": 0},
                        "span_counts": {"regeneration": 1},
                    }
                }
            )
        )
    with pytest.raises(CorpusEncodeError, match="split contamination"):
        encode_fixture(
            _minimal_fixture(
                meta={
                    "split": {
                        "forbid_train_and_gate_co_membership": True,
                        "train_lane": "train_pos",
                        "gate_lane": "gate_core",
                    }
                }
            )
        )
    with pytest.raises(CorpusEncodeError, match="replay lineage incomplete"):
        encode_fixture(
            _minimal_fixture(
                meta={
                    "replay": {
                        "require_lineage_fields": True,
                        "is_replay": True,
                        "parent_trace_id": "",
                    }
                }
            )
        )


def test_encode_provenance_defaults_and_gti_smuggle() -> None:
    # non-fixture artifact_class default provenance Opik-unbound when unbound
    fx = _minimal_fixture(artifact_class="export_batch")
    del fx["provenance_label"]
    out = encode_fixture(fx)
    assert out["bundle"]["provenance_label"] == "Opik-unbound"
    assert out["bundle"]["unbound_reason"] == "offline_fixture_seed"

    with pytest.raises(CorpusEncodeError, match="expected/gold"):
        encode_fixture(
            _minimal_fixture(
                generation_task_input={
                    "diff_summary": "x",
                    "expected_final_message": "leak",
                }
            )
        )

    # empty tags removed from case row
    out2 = encode_fixture(_minimal_fixture(tags=[]))
    assert "tags" not in out2["case"]


def test_encode_optional_field_type_errors() -> None:
    with pytest.raises(CorpusEncodeError, match="provenance_label must be a string"):
        encode_fixture(_minimal_fixture(provenance_label=1))  # type: ignore[arg-type]
    with pytest.raises(CorpusEncodeError, match="must be an object when present"):
        encode_fixture(_minimal_fixture(meta={"topology": ["nope"]}))


# ---------------------------------------------------------------------------
# Task input edges
# ---------------------------------------------------------------------------


def test_project_generation_task_input_edges() -> None:
    with pytest.raises(TaskInputError, match="must be an object"):
        project_generation_task_input("x")  # type: ignore[arg-type]
    assert project_generation_task_input({}) is None
    assert project_generation_task_input({"diff_summary": None}) is None
    with pytest.raises(TaskInputError, match="must be a string"):
        project_generation_task_input({"diff_summary": 1})
    # non-strict strips forbidden and unknowns
    out = project_generation_task_input(
        {"expected_final_message": "no", "diff_summary": "ok", "extra": "drop"},
        strict=False,
    )
    assert out == {"diff_summary": "ok"}


# ---------------------------------------------------------------------------
# Suites
# ---------------------------------------------------------------------------


def test_load_suite_errors_and_materialize_raw(tmp_path: Path) -> None:
    root = tmp_path / "fx"
    (root / "suites").mkdir(parents=True)
    with pytest.raises(SuiteLoadError, match="unknown dataset"):
        load_suite("nope-suite", fixture_root=root)
    with pytest.raises(SuiteLoadError, match="missing suite definition"):
        load_suite("cm-eval-fixtures-core", fixture_root=root)

    # alias filename path
    suite_body = {
        "suite_id": "cm-eval-fixtures-core",
        "case_ids": ["c1"],
        "case_paths": {"c1": "cases/c1.json"},
        "notes": "tmp",
    }
    (root / "suites" / "cm-eval-fixtures-core.json").write_text(json.dumps(suite_body), encoding="utf-8")
    # mismatch file id
    bad = dict(suite_body)
    bad["suite_id"] = "204-archive"
    (root / "suites" / "mismatch.json").write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(SuiteLoadError, match="does not match"):
        load_suite("cm-eval-fixtures-core", fixture_root=root, path=root / "suites" / "mismatch.json")

    # invalid suite json
    bad_json = root / "suites" / "bad.json"
    bad_json.write_text("{", encoding="utf-8")
    with pytest.raises(SuiteLoadError, match="invalid fixture JSON"):
        load_suite("cm-eval-fixtures-core", fixture_root=root, path=bad_json)

    # default meta when missing
    no_meta = dict(suite_body)
    no_meta.pop("notes", None)
    (root / "suites" / "cm-eval-fixtures-core.json").write_text(json.dumps(no_meta), encoding="utf-8")
    loaded = load_suite("cm-eval-fixtures-core", fixture_root=root)
    assert loaded["meta"]["network_policy"] == "offline_required"
    assert "case_paths" in loaded

    raw = materialize_suite("cm-eval-fixtures-core", fixture_root=root)
    assert raw["suite_id"] == "cm-eval-fixtures-core"
    with pytest.raises(SuiteLoadError, match="missing suite definition"):
        materialize_suite("204-archive", fixture_root=root)


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------


def test_snapshot_build_error_wrappers(tmp_path: Path) -> None:
    root = tmp_path / "fx"
    (root / "suites").mkdir(parents=True)
    with pytest.raises(SnapshotBuildError, match=r"missing suite|unknown dataset"):
        build_snapshot("cm-eval-fixtures-core", fixture_root=root)

    # suite ok but fixtures missing
    (root / "suites" / "cm-eval-fixtures-core.json").write_text(
        json.dumps({"suite_id": "cm-eval-fixtures-core", "case_ids": ["missing-case"]}),
        encoding="utf-8",
    )
    with pytest.raises(SnapshotBuildError, match=r"missing case|missing"):
        build_snapshot("cm-eval-fixtures-core", fixture_root=root)

    # encode failure surfaces as SnapshotBuildError
    cases = root / "cases" / "valid"
    cases.mkdir(parents=True)
    (cases / "bad-encode.json").write_text(
        json.dumps({"case_id": "bad-encode", "artifact_class": "not-real"}),
        encoding="utf-8",
    )
    (root / "suites" / "cm-eval-fixtures-core.json").write_text(
        json.dumps(
            {
                "suite_id": "cm-eval-fixtures-core",
                "case_ids": ["bad-encode"],
                "case_paths": {"bad-encode": "cases/valid/bad-encode.json"},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(SnapshotBuildError, match="bad-encode"):
        build_snapshot("cm-eval-fixtures-core", fixture_root=root)


def test_build_core_snapshot_live() -> None:
    snap = build_core_snapshot()
    assert snap["schema_version"] == "dataset_snapshot_v1"
    assert snap["item_count"] >= 3


# ---------------------------------------------------------------------------
# Materialize + index CLIs
# ---------------------------------------------------------------------------


def test_materialize_main_all_and_suite(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    # use live fixtures root for suite path; write outputs to tmp via --root? main only
    # supports root override for fixtures; write into temp by pointing root at a mini tree
    # easier: call main with suite all against live tree (writes goldens - already checked-in)
    rc = materialize_main(["--suite", "cm-eval-fixtures-core"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "bundles" in out
    assert "snapshot" in out

    rc2 = materialize_main(["--suite", "all"])
    assert rc2 == 0
    out2 = capsys.readouterr().out
    assert "core_snapshot" in out2
    assert "core_bundles" in out2


def test_materialize_core_goldens_archive_optional(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # force archive failure branch
    def boom(*_a: Any, **_k: Any) -> list[Path]:
        raise RuntimeError("no archive")

    monkeypatch.setattr(
        materialize,
        "materialize_suite_bundles",
        lambda suite_id, **kw: boom() if suite_id == "204-archive" else [tmp_path / "b.json"],
    )
    monkeypatch.setattr(
        materialize,
        "materialize_suite_snapshot",
        lambda suite_id, **kw: tmp_path / f"{suite_id}.json",
    )
    # ensure core path returns files
    (tmp_path / "b.json").write_text("{}", encoding="utf-8")
    (tmp_path / "cm-eval-fixtures-core.json").write_text("{}", encoding="utf-8")
    result = materialize_core_goldens(fixture_root=tmp_path)
    assert result["archive_bundles"] == []
    assert result["archive_snapshot"] is None


def test_index_main_write_and_print(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "fx"
    (root / "suites").mkdir(parents=True)
    (root / "cases" / "valid").mkdir(parents=True)
    (root / "suites" / "demo.json").write_text(
        json.dumps({"suite_id": "demo", "case_ids": ["c1"], "notes": "n|e\nline"}),
        encoding="utf-8",
    )
    (root / "cases" / "valid" / "c1.json").write_text(
        json.dumps(
            {
                "case_id": "c1",
                "regime": "A",
                "artifact_class": "fixture",
                "bound": False,
                "tags": ["t"],
                "meta": {"seed_id": "S"},
            }
        ),
        encoding="utf-8",
    )
    # empty trees short-circuit
    empty = tmp_path / "empty"
    empty.mkdir()
    assert "Suites" in build_fixture_index(fixture_root=empty)

    md = build_fixture_index(fixture_root=root)
    assert "`demo`" in md
    assert "`c1`" in md

    out_path = tmp_path / "INDEX.md"
    written = write_fixture_index(fixture_root=root, out_path=out_path)
    assert written == out_path
    assert out_path.is_file()

    rc = index_main(["--root", str(root)])
    assert rc == 0
    printed = capsys.readouterr().out
    assert "Eval fixture index" in printed

    rc2 = index_main(["--write", "--root", str(root)])
    assert rc2 == 0
    # default write path under root
    assert (root / "FIXTURE_INDEX.md").is_file()


def test_index_root_display_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # force relative_to failure branch
    root = tmp_path / "fx"
    root.mkdir()
    md = build_fixture_index(fixture_root=root)
    assert "Fixture root:" in md
