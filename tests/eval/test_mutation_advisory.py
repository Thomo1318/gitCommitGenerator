"""Contract locks for the acceptpath binding mutation-testing advisory.

Advisory only. Does not run mutation testing. CI pytest jobs do not
install just, so these tests parse justfile text instead of invoking it.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ADVISORY_DOC = REPO_ROOT / "docs" / "eval" / "mutation-testing-advisory.md"
JUSTFILE = REPO_ROOT / "justfile"
RECIPE_NAME = "eval-mutation-advisory"
ADVISORY_RELPATH = "docs/eval/mutation-testing-advisory.md"

TARGET_AREAS = (
    "Identity checks",
    "v2 key versioning",
    "Redaction",
    "Timeout",
    "Final-byte hashing",
)

EXPECTED_SOURCES = (
    "src/git_cg/eval/binding/binder.py",
    "src/git_cg/eval/binding/lock.py",
    "src/git_cg/eval/evidence_scrub.py",
)

EXPECTED_TESTS = (
    "tests/eval/binding/test_binder.py",
    "tests/eval/binding/test_binder_cache.py",
    "tests/eval/binding/test_binder_redaction.py",
    "tests/eval/binding/test_binder_lock.py",
    "tests/eval/test_evidence_scrub.py",
)


def _advisory_text() -> str:
    return ADVISORY_DOC.read_text(encoding="utf-8")


def _recipe_body(just: str) -> str:
    match = re.search(rf"^{re.escape(RECIPE_NAME)}:\n((?:[ \t]+.*\n)+)", just, re.M)
    assert match is not None, f"missing {RECIPE_NAME} recipe"
    return match.group(1)


def test_advisory_doc_exists() -> None:
    assert ADVISORY_DOC.is_file()


def test_advisory_doc_names_target_areas() -> None:
    content = _advisory_text()
    for area in TARGET_AREAS:
        assert area in content, f"missing target area: {area}"


def test_advisory_doc_states_tooling_not_installed() -> None:
    content = _advisory_text()
    assert "mutmut" in content
    assert "cosmic-ray" in content
    assert "Not installed" in content
    assert "no new dependencies" in content.lower()


def test_advisory_doc_is_non_gating() -> None:
    content = _advisory_text().lower()
    assert "advisory" in content
    assert "close-bar" in content
    assert "never gate ci" in content
    assert "product-accept" in content or "acceptance criterion" in content


def test_advisory_doc_has_future_adoption_path() -> None:
    assert "Future Adoption Path" in _advisory_text()


def test_advisory_doc_does_not_claim_coverage_or_tooling_noop() -> None:
    content = _advisory_text().lower()
    assert "prints this advisory and the current" not in content
    assert "does not measure coverage" in content
    assert "no-op when mutation-testing tooling is not installed" not in content


def test_advisory_mapped_paths_exist() -> None:
    content = _advisory_text()
    sources = re.findall(r"`(src/git_cg/eval/[^`]+\.[A-Za-z0-9]+)`", content)
    tests = re.findall(r"`(tests/eval/[^`]+\.[A-Za-z0-9]+)`", content)
    assert sources, "advisory must cite binding source files"
    assert tests, "advisory must map target areas to test files"
    missing_expected_sources = [path for path in EXPECTED_SOURCES if path not in sources]
    missing_expected_tests = [path for path in EXPECTED_TESTS if path not in tests]
    assert not missing_expected_sources, f"advisory missing source files: {missing_expected_sources}"
    assert not missing_expected_tests, f"advisory missing test files: {missing_expected_tests}"
    cited = [*sources, *tests]
    missing = [rel for rel in cited if not (REPO_ROOT / rel).is_file()]
    assert not missing, f"advisory maps missing files: {missing}"
    assert "`src/git_cg/eval/binding/profiles.py`" not in content


def test_justfile_contains_recipe() -> None:
    assert f"{RECIPE_NAME}:" in JUSTFILE.read_text(encoding="utf-8")


def test_recipe_prints_advisory_document() -> None:
    body = _recipe_body(JUSTFILE.read_text(encoding="utf-8"))
    assert f"cat {ADVISORY_RELPATH}" in body


def test_recipe_does_not_run_mutation_or_coverage() -> None:
    body = _recipe_body(JUSTFILE.read_text(encoding="utf-8"))
    lowered = body.lower()
    assert "mutmut" not in lowered
    assert "cosmic-ray" not in lowered
    assert "pytest" not in lowered
    assert "--co" not in body
    assert "head " not in lowered
    assert "coverage" not in lowered
