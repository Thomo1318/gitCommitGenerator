#!/usr/bin/env python3
"""Docstring insertion guard for git-cg (Contract Docstring Standard).

Placement law + per-file parse/compile write-if-green.

This tool hardens bulk docstring lifts after mid-signature insertion incidents.
It does **not** invent Google-style templates or coverage stubs.

Modes
------
check
    Report symbols missing docstrings and whether a safe insert is possible.
apply
    Insert explicit docstrings from --text/--symbol or a JSON manifest.
    Candidate source is ast.parse'd + compile()'d in memory; on failure the
    original file is left untouched and the symbol is reported as a miss.

Default scope: private names (``_foo``) under ``src/git_cg/**/*.py``,
excluding ``src/git_cg/evals/``.

Examples
--------
.. code-block:: bash

    uv run python tools/docstring_guard.py check src/git_cg/eval
    uv run python tools/docstring_guard.py check --include-public src/git_cg/eval/doctor.py
    uv run python tools/docstring_guard.py apply \\
        --path src/git_cg/eval/foo.py --symbol _helper \\
        --text "Fail closed when the pin is floating latest."
    uv run python tools/docstring_guard.py apply --manifest /tmp/docs.json
    just docstring-guard
    just docstring-guard-apply MANIFEST=/tmp/docs.json
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
import tokenize
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOTS = (REPO_ROOT / "src" / "git_cg",)
PACKAGE_ROOT = (REPO_ROOT / "src" / "git_cg").resolve()
EXCLUDED_PREFIXES = ((REPO_ROOT / "src" / "git_cg" / "evals").resolve(),)


@dataclass(frozen=True, slots=True)
class MissingSymbol:
    """One definition that lacks a docstring."""

    path: str
    qualname: str
    name: str
    kind: str  # function | async_function | class
    lineno: int
    private: bool
    insert_lineno: int | None
    insert_col: int | None
    status: str  # ok_to_insert | skip_same_line_ellipsis | skip_empty_body | skip_undecidable
    reason: str


@dataclass(frozen=True, slots=True)
class ApplyResult:
    """Outcome of one apply attempt."""

    path: str
    qualname: str
    ok: bool
    detail: str


def _is_private(name: str) -> bool:
    return name.startswith("_") and not (name.startswith("__") and name.endswith("__"))


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _is_excluded(path: Path) -> bool:
    resolved = path.resolve()
    return any(resolved == excl or excl in resolved.parents for excl in EXCLUDED_PREFIXES)


def _iter_py_files(paths: Sequence[Path]) -> Iterator[Path]:
    """Yield unique Python files.

    Explicit ``.py`` files are always honored (including tmp paths in tests).
    Directory walks are constrained under ``src/git_cg`` and skip ``evals/``.
    """
    seen: set[Path] = set()
    for raw in paths:
        path = raw if raw.is_absolute() else (REPO_ROOT / raw)
        path = path.resolve()

        if path.is_file() and path.suffix == ".py":
            if _is_excluded(path) or path in seen:
                continue
            seen.add(path)
            yield path
            continue

        if not path.is_dir():
            continue

        for file_path in sorted(path.rglob("*.py")):
            resolved = file_path.resolve()
            if resolved in seen or _is_excluded(resolved):
                continue
            try:
                resolved.relative_to(PACKAGE_ROOT)
            except ValueError:
                # Directory walks stay inside the package tree only.
                continue
            seen.add(resolved)
            yield resolved


def _is_ellipsis_stmt(node: ast.stmt) -> bool:
    if not isinstance(node, ast.Expr):
        return False
    val = node.value
    return isinstance(val, ast.Constant) and val.value is ...


def _line_has_same_line_def_ellipsis(lines: Sequence[str], lineno: int) -> bool:
    """True when the body's first ellipsis shares a physical line with ``: ...``."""
    if lineno < 1 or lineno > len(lines):
        return False
    line = lines[lineno - 1]
    # Heuristic: suite opener with ellipsis on the same physical line.
    return ": ..." in line or line.rstrip().endswith(":...")


def _indent_of_line(line: str) -> str:
    return line[: len(line) - len(line.lstrip(" \t"))]


def _format_docstring(text: str, indent: str) -> list[str]:
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("docstring text must be non-empty")
    # Reject Google-theatre bulk templates and coverage stubs.
    if cleaned.lower() in {"todo", "fixme", "pass", "documented", "docstring"}:
        raise ValueError(f"refusing coverage stub docstring: {cleaned!r}")
    if cleaned.startswith(("Args:", "Returns:", "Raises:", "Attributes:")):
        raise ValueError(
            "refusing Google section block as the entire docstring; "
            "use a contract one-liner (optional Google sections only when warranted)"
        )
    has_triple_double = '"""' in cleaned
    has_triple_single = "'''" in cleaned
    if has_triple_double and has_triple_single:
        raise ValueError(
            "docstring text contains both triple-double and triple-single quotes; "
            "rewrite the wording so one triple-quote style remains available"
        )
    # Prefer triple-double quotes unless the body already contains them.
    if has_triple_double:
        body = cleaned
        quote = "'''"
    else:
        body = cleaned
        quote = '"""'
    if "\n" in body:
        inner_lines = body.splitlines()
        out = [f"{indent}{quote}{inner_lines[0]}"]
        for part in inner_lines[1:]:
            out.append(f"{indent}{part}" if part else "")
        out.append(f"{indent}{quote}")
        return out
    return [f"{indent}{quote}{body}{quote}"]


def _walk_defs(
    tree: ast.AST,
    *,
    private_only: bool,
    include_public: bool,
    include_dunder: bool,
) -> Iterator[tuple[str, ast.AST, list[ast.stmt]]]:
    """Yield (qualname, node, body) for class/function definitions."""

    def allow(name: str) -> bool:
        if name.startswith("__") and name.endswith("__"):
            return include_dunder
        if _is_private(name):
            return True
        return include_public or not private_only

    def walk(node: ast.AST, prefix: str) -> Iterator[tuple[str, ast.AST, list[ast.stmt]]]:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                qn = f"{prefix}.{child.name}" if prefix else child.name
                if allow(child.name):
                    yield qn, child, child.body
                yield from walk(child, qn)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qn = f"{prefix}.{child.name}" if prefix else child.name
                if allow(child.name):
                    yield qn, child, child.body
                # Nested defs: walk with function prefix so nested helpers are found.
                yield from walk(child, qn)
            else:
                yield from walk(child, prefix)

    yield from walk(tree, "")


def analyze_source(
    source: str,
    *,
    path: Path,
    private_only: bool = True,
    include_public: bool = False,
    include_dunder: bool = False,
) -> list[MissingSymbol]:
    """Return missing-docstring symbols with insertion feasibility."""
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [
            MissingSymbol(
                path=_rel(path),
                qualname="<file>",
                name="<file>",
                kind="file",
                lineno=exc.lineno or 1,
                private=False,
                insert_lineno=None,
                insert_col=None,
                status="skip_undecidable",
                reason=f"syntax error: {exc.msg}",
            )
        ]

    lines = source.splitlines()
    missing: list[MissingSymbol] = []

    for qualname, node, body in _walk_defs(
        tree,
        private_only=private_only,
        include_public=include_public,
        include_dunder=include_dunder,
    ):
        if ast.get_docstring(node, clean=False) is not None:
            continue
        name = getattr(node, "name", "?")
        if isinstance(node, ast.AsyncFunctionDef):
            kind = "async_function"
        elif isinstance(node, ast.FunctionDef):
            kind = "function"
        else:
            kind = "class"
        lineno = getattr(node, "lineno", 1)
        private = _is_private(name)

        if not body:
            missing.append(
                MissingSymbol(
                    path=_rel(path),
                    qualname=qualname,
                    name=name,
                    kind=kind,
                    lineno=lineno,
                    private=private,
                    insert_lineno=None,
                    insert_col=None,
                    status="skip_empty_body",
                    reason="definition has empty body",
                )
            )
            continue

        first = body[0]
        insert_lineno = getattr(first, "lineno", None)
        insert_col = getattr(first, "col_offset", 0)

        if insert_lineno is None:
            missing.append(
                MissingSymbol(
                    path=_rel(path),
                    qualname=qualname,
                    name=name,
                    kind=kind,
                    lineno=lineno,
                    private=private,
                    insert_lineno=None,
                    insert_col=None,
                    status="skip_undecidable",
                    reason="missing body lineno",
                )
            )
            continue

        if _is_ellipsis_stmt(first) and _line_has_same_line_def_ellipsis(lines, insert_lineno):
            missing.append(
                MissingSymbol(
                    path=_rel(path),
                    qualname=qualname,
                    name=name,
                    kind=kind,
                    lineno=lineno,
                    private=private,
                    insert_lineno=None,
                    insert_col=None,
                    status="skip_same_line_ellipsis",
                    reason="body is same-line ': ...' — rewrite to multiline before inserting",
                )
            )
            continue

        # Guard: insertion line must not sit inside the parameter list.
        # body[0].lineno is after a complete header for valid Python ASTs; still
        # reject if that line looks like a parameter (trailing comma, no suite).
        target_line = lines[insert_lineno - 1] if insert_lineno <= len(lines) else ""
        stripped = target_line.strip()
        looks_like_param = (
            stripped.endswith(",")
            and not stripped.startswith(
                ("return", "yield", "raise", "pass", "assert", "...", "class ", "def ", "async ")
            )
            and "(" not in stripped
            and "=" not in stripped
        )
        if looks_like_param:
            missing.append(
                MissingSymbol(
                    path=_rel(path),
                    qualname=qualname,
                    name=name,
                    kind=kind,
                    lineno=lineno,
                    private=private,
                    insert_lineno=None,
                    insert_col=None,
                    status="skip_undecidable",
                    reason="refusing insert on parameter-like line",
                )
            )
            continue

        missing.append(
            MissingSymbol(
                path=_rel(path),
                qualname=qualname,
                name=name,
                kind=kind,
                lineno=lineno,
                private=private,
                insert_lineno=insert_lineno,
                insert_col=insert_col,
                status="ok_to_insert",
                reason="insert before first body statement (complete header required)",
            )
        )
    return missing


def insert_docstring(
    source: str,
    *,
    insert_lineno: int,
    text: str,
) -> str:
    """Return source with a docstring inserted before ``insert_lineno`` (1-based)."""
    lines = source.splitlines(keepends=True)
    if insert_lineno < 1 or insert_lineno > len(lines) + 1:
        raise ValueError(f"insert_lineno out of range: {insert_lineno}")

    # Determine indentation from the first body line (or previous non-empty).
    indent = _indent_of_line(lines[insert_lineno - 1]) if insert_lineno <= len(lines) else ""
    if not indent:
        # Class/function body should be indented; fall back when target is EOF.
        indent = "    "

    doc_lines = _format_docstring(text, indent)
    # Preserve newline style from the file.
    nl = "\n"
    if lines:
        if lines[0].endswith("\r\n"):
            nl = "\r\n"
        elif lines[0].endswith("\n"):
            nl = "\n"
    rendered = [f"{d}{nl}" for d in doc_lines]

    out = lines[: insert_lineno - 1] + rendered + lines[insert_lineno - 1 :]
    return "".join(out)


def validate_source(source: str, *, filename: str) -> None:
    """Raise if source does not parse/compile."""
    tree = ast.parse(source, filename=filename)
    compile(tree, filename=filename, mode="exec")
    # Tokenize as a second cheap syntax signal (catches some oddities early).
    tokenize.generate_tokens(iter(source.splitlines(keepends=True)).__next__)


def apply_one(
    path: Path,
    *,
    qualname: str | None,
    symbol: str | None,
    text: str,
    private_only: bool,
    include_public: bool,
    dry_run: bool,
) -> ApplyResult:
    """Apply one docstring insertion with write-if-green semantics."""
    original = path.read_text(encoding="utf-8")
    try:
        validate_source(original, filename=str(path))
    except SyntaxError as exc:
        return ApplyResult(_rel(path), qualname or symbol or "?", False, f"original unparseable: {exc}")

    missing = analyze_source(
        original,
        path=path,
        private_only=private_only,
        include_public=include_public or not private_only,
    )
    target: MissingSymbol | None = None
    for item in missing:
        if qualname and item.qualname == qualname:
            target = item
            break
        if symbol and item.name == symbol and (qualname is None):
            # Prefer unique match by bare name.
            matches = [m for m in missing if m.name == symbol]
            if len(matches) != 1:
                return ApplyResult(
                    _rel(path),
                    symbol,
                    False,
                    f"symbol {symbol!r} is ambiguous ({len(matches)} matches); use qualname",
                )
            target = matches[0]
            break

    if target is None:
        return ApplyResult(
            _rel(path),
            qualname or symbol or "?",
            False,
            "symbol not missing a docstring (or not in scope filters)",
        )
    if target.status != "ok_to_insert" or target.insert_lineno is None:
        return ApplyResult(
            _rel(path),
            target.qualname,
            False,
            f"{target.status}: {target.reason}",
        )

    try:
        candidate = insert_docstring(original, insert_lineno=target.insert_lineno, text=text)
        validate_source(candidate, filename=str(path))
    except (SyntaxError, ValueError, tokenize.TokenError) as exc:
        return ApplyResult(_rel(path), target.qualname, False, f"candidate rejected: {exc}")

    if dry_run:
        return ApplyResult(_rel(path), target.qualname, True, "dry-run ok (not written)")

    path.write_text(candidate, encoding="utf-8")
    return ApplyResult(_rel(path), target.qualname, True, "written")


def apply_manifest(
    manifest_path: Path,
    *,
    private_only: bool,
    include_public: bool,
    dry_run: bool,
) -> list[ApplyResult]:
    """Apply a JSON manifest of docstring insertions.

    Manifest formats accepted:
      1. list of objects:
         {"path": "src/...", "qualname": "Class._foo", "text": "..."}
         {"path": "src/...", "symbol": "_foo", "text": "..."}
      2. object mapping "path::qualname" -> "text"
    """
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    items: list[dict[str, str]] = []
    if isinstance(data, list):
        for row in data:
            if not isinstance(row, dict):
                raise ValueError("manifest list entries must be objects")
            items.append({k: str(v) for k, v in row.items()})
    elif isinstance(data, dict):
        for key, text in data.items():
            if "::" not in key:
                raise ValueError(f"manifest key {key!r} must be 'path::qualname' in mapping form")
            path_s, qn = key.split("::", 1)
            items.append({"path": path_s, "qualname": qn, "text": str(text)})
    else:
        raise ValueError("manifest must be a list or object")

    results: list[ApplyResult] = []
    for row in items:
        path = Path(row["path"])
        if not path.is_absolute():
            path = REPO_ROOT / path
        results.append(
            apply_one(
                path,
                qualname=row.get("qualname"),
                symbol=row.get("symbol"),
                text=row["text"],
                private_only=private_only,
                include_public=include_public,
                dry_run=dry_run,
            )
        )
    return results


def cmd_check(args: argparse.Namespace) -> int:
    paths = [Path(p) for p in args.paths] if args.paths else list(DEFAULT_ROOTS)
    all_missing: list[MissingSymbol] = []
    for file_path in _iter_py_files(paths):
        source = file_path.read_text(encoding="utf-8")
        all_missing.extend(
            analyze_source(
                source,
                path=file_path,
                private_only=not args.include_public,
                include_public=args.include_public,
                include_dunder=args.include_dunder,
            )
        )

    insertable = [m for m in all_missing if m.status == "ok_to_insert"]
    skipped = [m for m in all_missing if m.status != "ok_to_insert"]

    if args.json:
        payload = {
            "missing": [asdict(m) for m in all_missing],
            "insertable_count": len(insertable),
            "skipped_count": len(skipped),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        scope = "all names" if args.include_public else "private names only"
        print(f"docstring_guard check ({scope})")
        print(f"  missing:     {len(all_missing)}")
        print(f"  insertable:  {len(insertable)}")
        print(f"  skipped:     {len(skipped)}")
        if all_missing:
            print()
            for item in all_missing:
                loc = f"insert@{item.insert_lineno}" if item.insert_lineno is not None else "no-insert"
                print(
                    f"  [{item.status}] {item.path}:{item.lineno} {item.kind} {item.qualname} ({loc}) — {item.reason}"
                )
        print()
        print(
            "Apply only with explicit --text/--manifest (no auto stubs). "
            "See docs/docstring-standard.md § Bulk insertion guard."
        )

    if args.fail_on_missing and all_missing:
        return 1
    if any(m.kind == "file" for m in all_missing):
        return 2
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    results: list[ApplyResult]
    if args.manifest:
        results = apply_manifest(
            Path(args.manifest),
            private_only=not args.include_public,
            include_public=args.include_public,
            dry_run=args.dry_run,
        )
    else:
        if not args.path or not args.text:
            print(
                "apply requires --manifest, or --path plus --text and --symbol/--qualname",
                file=sys.stderr,
            )
            return 2
        if not args.symbol and not args.qualname:
            print("apply requires --symbol or --qualname", file=sys.stderr)
            return 2
        path = Path(args.path)
        if not path.is_absolute():
            path = REPO_ROOT / path
        results = [
            apply_one(
                path,
                qualname=args.qualname,
                symbol=args.symbol,
                text=args.text,
                private_only=not args.include_public,
                include_public=args.include_public,
                dry_run=args.dry_run,
            )
        ]

    ok_n = sum(1 for r in results if r.ok)
    bad = [r for r in results if not r.ok]
    for r in results:
        flag = "OK" if r.ok else "FAIL"
        print(f"[{flag}] {r.path} :: {r.qualname} — {r.detail}")
    print(f"apply summary: {ok_n}/{len(results)} ok")
    return 0 if not bad else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="docstring_guard",
        description=(
            "Safe docstring insertion guard: placement law + parse/compile "
            "write-if-green (Contract Docstring Standard)."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Report missing docstrings / insertability")
    check.add_argument(
        "paths",
        nargs="*",
        help="Files or directories (default: src/git_cg)",
    )
    check.add_argument(
        "--include-public",
        action="store_true",
        help="Include public names (default: private-only)",
    )
    check.add_argument(
        "--include-dunder",
        action="store_true",
        help="Include __dunder__ methods/attrs",
    )
    check.add_argument(
        "--fail-on-missing",
        action="store_true",
        help="Exit 1 when any missing docstring is found",
    )
    check.add_argument("--json", action="store_true", help="Machine-readable output")
    check.add_argument("--verbose", "-v", action="store_true")
    check.set_defaults(func=cmd_check)

    apply = sub.add_parser(
        "apply",
        help="Insert explicit docstring text with write-if-green semantics",
    )
    apply.add_argument("--path", help="Target file for single apply")
    apply.add_argument("--symbol", help="Bare symbol name (unique in file)")
    apply.add_argument("--qualname", help="Qualified name (Class.method or nested)")
    apply.add_argument("--text", help="Docstring body (no surrounding quotes)")
    apply.add_argument(
        "--manifest",
        help="JSON manifest of {path,qualname|symbol,text} rows",
    )
    apply.add_argument(
        "--include-public",
        action="store_true",
        help="Allow public symbol targets",
    )
    apply.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate candidate but do not write",
    )
    apply.set_defaults(func=cmd_apply)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
