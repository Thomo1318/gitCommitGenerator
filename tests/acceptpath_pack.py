"""Shared accept-path fixture pack for Issue #212 and future engine bakeoffs.

Canonical frozen evidence lives under ``tests/fixtures/acceptpath/``.
This module is the stable import surface for:

* deterministic APC-A/B/C tests
* informational LMLX compare twins
* future engine bakeoffs that must reuse the same staged envelopes

It does **not** run live models. Callers supply their own engine runner.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

PACK_ROOT: Final[Path] = Path(__file__).resolve().parent / "fixtures" / "acceptpath"

# Close-gate cases for #212 / APC-D. Order is stable for bakeoff matrices.
CLOSE_GATE_CASES: Final[tuple[str, ...]] = (
    "docs-only",
    "product-source",
    "tests-only",
    "gold-trigger",
)

# Informational twins — never block #212 close.
INFO_CASES: Final[tuple[str, ...]] = ("lmlx-docs-compare",)

ALL_CASES: Final[tuple[str, ...]] = CLOSE_GATE_CASES + INFO_CASES

# Minimum artifact names required for a close-gate case.
REQUIRED_CLOSE_GATE_FILES: Final[tuple[str, ...]] = (
    "staged.diff",
    "COMMIT_EDITMSG",
    "GIT_CG_OPIK_STATE.json",
    "summary.txt",
    "meta.txt",
    "status.txt",
    "telemetry-extract.txt",
)

# LMLX / informational parity core (aligned with close-gate minus optional CLI split).
REQUIRED_INFO_FILES: Final[tuple[str, ...]] = (
    "staged.diff",
    "COMMIT_EDITMSG",
    "GIT_CG_OPIK_STATE.json",
    "summary.txt",
    "meta.txt",
    "status.txt",
    "telemetry-extract.txt",
)

# Expected post-#212 law triples (gate / type family / SemVer ceiling intent).
EXPECTED_ENVELOPES: Final[Mapping[str, Mapping[str, str]]] = {
    "docs-only": {
        "diff_class": "docs_only",
        "cc_type": "docs",
        "semver": "NONE",
        "forbidden_intent": "secrets_update",
    },
    "product-source": {
        "diff_class": "product_src",
        "cc_type": "feat",
        "semver": "MINOR",
        "forbidden_intent": "breaking_change",
    },
    "tests-only": {
        "diff_class": "tests_only",
        "cc_type": "test",
        "semver": "NONE",
        "forbidden_intent": "breaking_change",
    },
    "gold-trigger": {
        "diff_class": "product_src",
        "cc_type": "feat",
        "semver": "not_MAJOR",
        "forbidden_intent": "breaking_change",
    },
    "lmlx-docs-compare": {
        "diff_class": "docs_only",
        "cc_type": "docs",
        "semver": "NONE",
        "forbidden_intent": "secrets_update",
    },
}


@dataclass(frozen=True, slots=True)
class AcceptpathCase:
    """One frozen accept-path case directory."""

    name: str
    root: Path

    @property
    def staged_diff_path(self) -> Path:
        return self.root / "staged.diff"

    def staged_diff(self) -> str:
        path = self.staged_diff_path
        if not path.is_file():
            raise FileNotFoundError(f"missing staged.diff for acceptpath case {self.name!r}: {path}")
        return path.read_text(encoding="utf-8")

    def _artifact_path(self, name: str) -> Path:
        """Resolve an artifact path and reject escapes outside this case root."""
        root = self.root.resolve()
        path = (root / name).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"acceptpath artifact escapes case root for {self.name!r}: {name!r}")
        return path

    def read_text(self, name: str) -> str:
        path = self._artifact_path(name)
        if not path.is_file():
            raise FileNotFoundError(f"missing {name!r} for acceptpath case {self.name!r}: {path}")
        return path.read_text(encoding="utf-8")

    def optional_text(self, name: str) -> str | None:
        path = self._artifact_path(name)
        if not path.is_file():
            return None
        return path.read_text(encoding="utf-8")

    def expected_envelope(self) -> Mapping[str, str]:
        return EXPECTED_ENVELOPES[self.name]

    def is_close_gate(self) -> bool:
        return self.name in CLOSE_GATE_CASES

    def required_files(self) -> tuple[str, ...]:
        return REQUIRED_CLOSE_GATE_FILES if self.is_close_gate() else REQUIRED_INFO_FILES

    def missing_required_files(self) -> list[str]:
        return [name for name in self.required_files() if not (self.root / name).is_file()]


def case_dir(name: str) -> Path:
    """Return the directory for a named acceptpath case.

    Paths are resolved and must remain under ``PACK_ROOT`` so bakeoff callers
    cannot escape the committed fixture pack via ``..`` or absolute segments.
    """
    if name not in ALL_CASES and name not in {"_suite"}:
        # Allow unknown names for forward-compatible bakeoff extensions, but
        # still resolve under the pack root.
        pass
    pack_root = PACK_ROOT.resolve()
    path = (pack_root / name).resolve()
    if not path.is_relative_to(pack_root):
        raise ValueError(f"acceptpath case escapes fixture pack: {name!r}")
    if not path.is_dir():
        raise FileNotFoundError(f"acceptpath case directory missing: {path}")
    return path


def load_case(name: str) -> AcceptpathCase:
    """Load one acceptpath case by directory name."""
    return AcceptpathCase(name=name, root=case_dir(name))


def iter_close_gate_cases() -> Iterator[AcceptpathCase]:
    """Yield the four #212 / APC-D close-gate cases in stable order."""
    for name in CLOSE_GATE_CASES:
        yield load_case(name)


def iter_info_cases() -> Iterator[AcceptpathCase]:
    """Yield informational twins (LMLX compare, etc.)."""
    for name in INFO_CASES:
        yield load_case(name)


def iter_all_cases() -> Iterator[AcceptpathCase]:
    """Yield close-gate then informational cases."""
    yield from iter_close_gate_cases()
    yield from iter_info_cases()


def staged_diff(case: str) -> str:
    """Convenience: read ``staged.diff`` for ``case``."""
    return load_case(case).staged_diff()


def assert_pack_integrity(*, include_info: bool = True) -> None:
    """Raise ``AssertionError`` if required pack files are missing.

    Intended for bakeoff harnesses and drift guards. Does not execute models.
    """
    cases = list(iter_all_cases()) if include_info else list(iter_close_gate_cases())
    missing: list[str] = []
    for case in cases:
        for name in case.missing_required_files():
            missing.append(f"{case.name}/{name}")
    if missing:
        raise AssertionError("acceptpath pack missing required files: " + ", ".join(missing))


__all__ = [
    "ALL_CASES",
    "CLOSE_GATE_CASES",
    "EXPECTED_ENVELOPES",
    "INFO_CASES",
    "PACK_ROOT",
    "REQUIRED_CLOSE_GATE_FILES",
    "REQUIRED_INFO_FILES",
    "AcceptpathCase",
    "assert_pack_integrity",
    "case_dir",
    "iter_all_cases",
    "iter_close_gate_cases",
    "iter_info_cases",
    "load_case",
    "staged_diff",
]
