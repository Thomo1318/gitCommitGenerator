"""S1-E: offline / no-opik import boundary."""

from __future__ import annotations

from pathlib import Path


def test_s1_e01_corpus_package_imports_without_opik() -> None:
    import git_cg.eval.corpus as corpus
    import git_cg.eval.corpus.aliases as aliases
    import git_cg.eval.corpus.encoder as encoder
    import git_cg.eval.corpus.fixtures as fixtures
    import git_cg.eval.corpus.snapshots as snapshots
    import git_cg.eval.corpus.suites as suites
    import git_cg.eval.corpus.task_input as task_input

    assert hasattr(corpus, "encode_fixture")
    assert hasattr(corpus, "build_core_snapshot")
    for mod in (corpus, aliases, encoder, fixtures, snapshots, suites, task_input):
        assert mod.__file__ is not None
        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert "import opik" not in src
        assert "from opik" not in src
