"""S1-E: offline / no-opik import boundary."""

from __future__ import annotations

import importlib
from pathlib import Path


def test_s1_e01_corpus_package_imports_without_opik() -> None:
    import git_cg.eval.corpus as corpus

    assert hasattr(corpus, "encode_fixture")
    assert hasattr(corpus, "build_core_snapshot")

    assert corpus.__file__ is not None
    package_dir = Path(corpus.__file__).parent
    sources = sorted(package_dir.glob("*.py"))
    assert sources, "no corpus modules found"
    for source in sources:
        mod_name = "git_cg.eval.corpus" if source.name == "__init__.py" else f"git_cg.eval.corpus.{source.stem}"
        importlib.import_module(mod_name)
        src = source.read_text(encoding="utf-8")
        assert "import opik" not in src
        assert "from opik" not in src
