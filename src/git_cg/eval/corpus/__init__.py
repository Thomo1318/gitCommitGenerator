"""Offline fixture / corpus encoder (S1).

Lane A local SoT: committed fixtures → validated ape_bundle_v1 / eval_case_v1 /
dataset_snapshot_v1 artifacts. No Opik, network, or product-path scoring.
"""

from __future__ import annotations

from git_cg.eval.corpus.aliases import DATASET_ID_ALIASES, canonicalize_dataset_id, resolve_dataset_id
from git_cg.eval.corpus.encoder import CorpusEncodeError, encode_fixture
from git_cg.eval.corpus.fixtures import FixtureLoadError, default_fixture_root, load_fixture_dict, load_suite_fixtures
from git_cg.eval.corpus.snapshots import SnapshotBuildError, build_core_snapshot, build_snapshot
from git_cg.eval.corpus.suites import SuiteLoadError, load_suite, materialize_suite
from git_cg.eval.corpus.task_input import TaskInputError, project_generation_task_input

__all__ = [
    "DATASET_ID_ALIASES",
    "CorpusEncodeError",
    "FixtureLoadError",
    "SnapshotBuildError",
    "SuiteLoadError",
    "TaskInputError",
    "build_core_snapshot",
    "build_snapshot",
    "canonicalize_dataset_id",
    "default_fixture_root",
    "encode_fixture",
    "load_fixture_dict",
    "load_suite",
    "load_suite_fixtures",
    "materialize_suite",
    "project_generation_task_input",
    "resolve_dataset_id",
]
