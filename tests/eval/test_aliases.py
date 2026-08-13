"""S1 alias resolution — offline only."""

from __future__ import annotations

import pytest

from git_cg.eval.corpus.aliases import DatasetAliasError, canonicalize_dataset_id, resolve_dataset_id
from git_cg.eval.corpus.suites import SuiteLoadError, load_suite


def test_s1_alias_204_archive() -> None:
    assert resolve_dataset_id("cm-eval-204-archive") == "204-archive"
    assert canonicalize_dataset_id("204-archive") == "204-archive"


def test_s1_alias_core_stable() -> None:
    assert resolve_dataset_id("cm-eval-fixtures-core") == "cm-eval-fixtures-core"


def test_s1_f03_unknown_alias_fails_clearly() -> None:
    with pytest.raises(DatasetAliasError, match="unknown dataset id"):
        resolve_dataset_id("cm-eval-does-not-exist")


def test_suite_loader_accepts_core_alias_identity() -> None:
    suite = load_suite("cm-eval-fixtures-core")
    assert suite["suite_id"] == "cm-eval-fixtures-core"


def test_suite_loader_unknown_alias() -> None:
    with pytest.raises(SuiteLoadError, match="unknown dataset id"):
        load_suite("not-a-suite")
