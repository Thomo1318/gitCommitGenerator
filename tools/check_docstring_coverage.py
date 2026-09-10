#!/usr/bin/env python3
"""Fail if public docstring coverage for a package directory is below threshold.

Walks ``*.py`` files that are *direct children* of the given path (no
recursion) using stdlib ``ast`` only. Counts:

* one module item per file
* public top-level classes, functions, and async functions
* public methods of public top-level classes

Private names (``_`` prefix) and dunders are excluded. Nested classes and
nested functions are excluded. Empty, missing, or unreadable scopes fail
closed. Symlinked ``.py`` files are skipped so the walk cannot leave the
given directory.

Exit codes:
  0 — public coverage meets threshold
  1 — usage / IO / parse / empty-scope error
  2 — coverage below threshold
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCOPE = REPO_ROOT / "src" / "git_cg" / "eval" / "binding"


@dataclass(frozen=True, slots=True)
class CoverageItem:
    """One counted public symbol."""

    name: str
    documented: bool


@dataclass(frozen=True, slots=True)
class CoverageReport:
    """Public-docstring coverage for a path."""

    path: Path
    items: tuple[CoverageItem, ...]
    threshold: float

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def documented_count(self) -> int:
        return sum(1 for item in self.items if item.documented)

    @property
    def missing(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.items if not item.documented)

    @property
    def percent(self) -> float:
        if self.total <= 0:
            return 0.0
        return (100.0 * self.documented_count) / self.total

    def meets_threshold(self) -> bool:
        return self.total > 0 and self.percent + 1e-9 >= self.threshold


def _is_public(name: str) -> bool:
    return not name.startswith("_")


def _documented(node: ast.AST) -> bool:
    doc = ast.get_docstring(node, clean=False)
    return bool(doc and doc.strip())


def analyze_source(source: str, *, module_name: str, filename: str = "<string>") -> list[CoverageItem]:
    """Return public coverage items for one module source."""
    tree = ast.parse(source, filename=filename)
    items = [CoverageItem(module_name, _documented(tree))]
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _is_public(node.name):
                items.append(CoverageItem(f"{module_name}.{node.name}", _documented(node)))
            continue
        if not isinstance(node, ast.ClassDef) or not _is_public(node.name):
            continue
        items.append(CoverageItem(f"{module_name}.{node.name}", _documented(node)))
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_public(child.name):
                items.append(CoverageItem(f"{module_name}.{node.name}.{child.name}", _documented(child)))
    return items


def _python_files(path: Path) -> list[Path]:
    if path.is_symlink():
        raise ValueError(f"refusing symlinked path: {path}")
    if path.is_file():
        if path.suffix != ".py":
            raise ValueError(f"not a Python file: {path}")
        return [path]
    if not path.is_dir():
        raise ValueError(f"not a directory or Python file: {path}")
    files: list[Path] = []
    for child in sorted(path.iterdir(), key=lambda item: item.name):
        if child.is_symlink():
            continue
        if child.is_file() and child.suffix == ".py":
            files.append(child)
    return files


def analyze_path(path: Path, *, threshold: float = 80.0) -> CoverageReport:
    """Analyze public docstring coverage for ``path``.

    ``path`` may be a ``.py`` file or a directory of direct-child ``.py``
    files. Raises ``ValueError`` when the scope is empty or invalid.
    """
    if threshold < 0:
        raise ValueError("threshold must be >= 0")
    resolved = path.expanduser()
    if not resolved.exists():
        raise ValueError(f"path does not exist: {path}")
    files = _python_files(resolved)
    if not files:
        raise ValueError(f"no Python files in scope: {path}")
    items: list[CoverageItem] = []
    for file_path in files:
        source = file_path.read_text(encoding="utf-8")
        items.extend(analyze_source(source, module_name=file_path.stem, filename=str(file_path)))
    return CoverageReport(path=resolved, items=tuple(items), threshold=threshold)


def _print_report(report: CoverageReport) -> None:
    print(f"Public docstring coverage (threshold={report.threshold:.2f}%)")
    print(f"  path: {report.path}")
    print(f"  documented: {report.documented_count}/{report.total} ({report.percent:.2f}%)")
    if report.missing:
        print("missing:")
        for name in report.missing:
            print(f"  - {name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        type=Path,
        nargs="?",
        default=DEFAULT_SCOPE,
        help="Package directory (or single .py file) to gate (default: src/git_cg/eval/binding)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=80.0,
        help="Minimum public docstring coverage percent (default: 80)",
    )
    args = parser.parse_args(argv)
    if args.threshold < 0:
        print("error: --threshold must be >= 0", file=sys.stderr)
        return 1
    try:
        report = analyze_path(args.path, threshold=args.threshold)
    except SyntaxError as exc:
        where = exc.filename or args.path
        print(f"error: cannot parse {where}: {exc.msg} (line {exc.lineno})", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    _print_report(report)
    if not report.meets_threshold():
        print("error: public docstring coverage below threshold", file=sys.stderr)
        return 2
    print("OK: public docstring coverage meets threshold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
