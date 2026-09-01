#!/usr/bin/env python3
"""Mechanical Naming Audit for deslop families A-D (identity role).

Skills cannot force models to rename. This scanner fails closed when branch
diffs introduce durable identifiers whose *shape* is stage / plan / governance
/ ceremony residue (any generation - not a per-slice or per-issue denylist).

Citation vs identity:
  - Citation: matrix/ADR/issue prose, markdown tables, comments, docstrings,
    bare taxonomy tokens (D31, E07, FIND-003, S7-DOG-04, S6-G02, RK-S6-02, S7/S8, ...),
    scratch lab paths, and plan/board version labels.
  - Identity: just recipes, .eval artifact paths, CLI-ish operator tokens,
    and code symbols (def/class/test names).

Default scope: justfile, src/, tools/, scripts/, docs/, config/, top-level
task/config files. Skill catalogs and this scanner are excluded.

Exit codes:
  0 - clean
  1 - usage / git / IO error
  2 - identity findings
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

_DEFAULT_BASE = "origin/main"

_DEFAULT_INCLUDE = (
    "justfile",
    "Justfile",
    "makefile",
    "Makefile",
    "mise.toml",
    "pyproject.toml",
    "usage.kdl",
    "src/",
    "tools/",
    "scripts/",
    "docs/",
    "config/",
)

_DEFAULT_EXCLUDE = (
    "tools/deslop_naming_scan.py",
    "tests/tools/test_deslop_naming_scan.py",
    ".agents/",
    "scratch/",
    "docs/assets/badges/",
)

_SCAN_SUFFIXES = frozenset(
    {
        ".py",
        ".sh",
        ".zsh",
        ".bash",
        ".mjs",
        ".js",
        ".ts",
        ".just",
        ".toml",
        ".yml",
        ".yaml",
        ".kdl",
        ".md",
        ".json",
    }
)

_SCAN_BASENAMES = frozenset({"justfile", "makefile", "mise.toml", "pyproject.toml", "usage.kdl"})

_TOKEN_RE = re.compile(
    r"""
    (?P<token>
        \.?[A-Za-z0-9]+(?:[/_-][A-Za-z0-9.]+)+
      | [A-Za-z][A-Za-z0-9]*\d[A-Za-z0-9_-]*
    )
    """,
    re.VERBOSE,
)

_RECIPE_HEADER_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*)\s*:")

_A: list[tuple[str, re.Pattern[str]]] = [
    (
        "A.sN_segment",
        re.compile(
            r"""(?ix)
            (?:^|[^a-z0-9])s\d{1,3}(?:[_-][a-z0-9]|$)
          | (?:^|[^a-z0-9])s\d{1,3}$
          | [_-]s\d{1,3}(?:[_-]|$)
            """
        ),
    ),
    ("A.sliceN", re.compile(r"(?i)(?:^|[^a-z0-9])slice[_-]?\d{1,3}(?:[^a-z0-9]|$)")),
    ("A.phaseN", re.compile(r"(?i)(?:^|[^a-z0-9])phase[_-]?\d{1,3}(?:[^a-z0-9]|$)")),
    ("A.waveN", re.compile(r"(?i)(?:^|[^a-z0-9])wave[_-]?\d{1,3}(?:[^a-z0-9]|$)")),
    (
        "A.milestone_sprint",
        re.compile(r"(?i)(?:^|[^a-z0-9])(?:milestone|sprint|epoch)[_-]?\d{1,3}(?:[^a-z0-9]|$)"),
    ),
]

_B: list[tuple[str, re.Pattern[str]]] = [
    (
        "B.finding",
        re.compile(r"(?i)(?:^|[^a-z0-9])findings?[_-]?\d{1,4}(?:[^a-z0-9]|$)"),
    ),
    ("B.FIND", re.compile(r"(?i)(?:^|[^a-z0-9])find[_-]?\d{1,4}(?:[^a-z0-9]|$)")),
    ("B.INT", re.compile(r"(?i)(?:^|[^a-z0-9])int[_-]?\d{1,4}(?:[^a-z0-9]|$)")),
    (
        "B.item_step_task",
        re.compile(r"(?i)(?:^|[^a-z0-9])(?:item|step|task)[_-]?\d{1,4}(?:[_-]\d{1,4})?(?:[^a-z0-9]|$)"),
    ),
]

_C: list[tuple[str, re.Pattern[str]]] = [
    ("C.D_compound", re.compile(r"(?i)(?:^|[^a-z0-9])d\d{1,3}[_-][a-z0-9]")),
    ("C.I_compound", re.compile(r"(?i)(?:^|[^a-z0-9])i\d{1,3}[_-][a-z0-9]")),
    ("C.R_compound", re.compile(r"(?i)(?:^|[^a-z0-9])r\d{1,3}[_-][a-z0-9]")),
    # Errors / eval evidence IDs (S4 E-matrix grammar): e07_gate, handle_e12, error_e07, run_error_e07
    (
        "C.E_compound",
        re.compile(
            r"""(?ix)
            (?:^|[^a-z0-9])e\d{1,3}[_-][a-z0-9]                                 # e07_gate, e12_report
          | (?:^|[^a-z0-9])(?:error|err)[_-]?e?\d{1,3}(?:[_-][a-z0-9]|$)         # error_e07, err_e12, errore07
          | (?:^|[^a-z0-9])(?:handle|run|test)[_-]e\d{1,3}(?:[_-]|$)              # handle_e07, test_e12_
            """
        ),
    ),
    ("C.F_S", re.compile(r"(?i)(?:^|[^a-z0-9])f[_-]?s\d{1,3}[_-]?\d{1,3}")),
    ("C.F_plain_compound", re.compile(r"(?i)(?:^|[^a-z0-9])f\d{1,3}[_-][a-z0-9]")),
    # Claim-matrix coordinates: S6-A04, S6-G02, S5-H, S7-DOG-05 as identity segments
    (
        "C.S_claim",
        re.compile(
            r"""(?ix)
            (?:^|[^a-z0-9])s\d{1,3}[_-]?[a-h]\d{0,3}(?:[_-][a-z0-9]|$)   # s6_a04_, s6g02_, s5_h_
          | (?:^|[^a-z0-9])s\d{1,3}[_-]?dog[_-]?\d{1,3}                   # s7_dog_05, s7-dog-05
            """
        ),
    ),
    ("C.S_A", re.compile(r"(?i)(?:^|[^a-z0-9])s\d{1,3}[_-]?a\d{1,3}")),  # kept for explicit A-contract hits
    ("C.AC_compound", re.compile(r"(?i)(?:^|[^a-z0-9])ac[_-]?\d{1,3}[_-][a-z0-9]")),
    ("C.RK", re.compile(r"(?i)(?:^|[^a-z0-9])rk[_-][a-z0-9]")),
    ("C.NTH", re.compile(r"(?i)(?:^|[^a-z0-9])nth[_-]?\d{1,3}")),
    ("C.P_priority", re.compile(r"(?i)(?:^|[^a-z0-9])p[012][_-][a-z0-9]")),
    # Work-package cites as identity: p2_8_runner, run_p0_5 (not bare P2-8 citations)
    ("C.P_workpkg", re.compile(r"(?i)(?:^|[^a-z0-9])p\d{1,2}[_-]\d{1,3}[_-][a-z0-9]")),
    ("C.DoD", re.compile(r"(?i)(?:^|[^a-z0-9])dod[_-]?\d{1,3}")),
]

_D: list[tuple[str, re.Pattern[str]]] = [
    (
        "D.proof_compound",
        re.compile(r"(?i)(?:^|[^a-z0-9])(?:[a-z0-9]+[_-])*proof(?:[_-][a-z0-9]+)*(?:[^a-z0-9]|$)"),
    ),
    (
        "D.scratch",
        re.compile(r"(?i)(?:^|[^a-z0-9])(?:wip|tmp|temp|final2|new2|leftover)(?:[_-][a-z0-9]+)*(?:[^a-z0-9]|$)"),
    ),
]

_ALL = _A + _B + _C + _D

_COMMENT_LINE_RE = re.compile(
    r"""(?x)
    ^\s*(?:\#|//|/\*|\*|\"\"\"|\'\'\'|:\#|<!--)
  | ^\s*\|
  | ^\s*>
    """
)

_PROOF_PROSE_OK = re.compile(r"(?i)\b(?:proof of concept|burden of proof|proof-of-concept|mathematical proof)\b")

# Single taxonomy / measurement citation atom.
_CITATION_ATOM = r"""
    d\d{1,3}
  | i\d{1,3}
  | r\d{1,3}
  | e\d{1,3}                                 # E07, E13 eval/error evidence cites
  | e[_-]\d{1,3}
  | p[012]
  | p\d{1,2}[_-]\d{1,3}                       # P0-5, P2-8 work-package cites (exact)
  | ac[_-]?\d{1,3}
  | find[_-]?\d{1,4}
  | findings?[_-]?\d{1,4}
  | int[_-]?\d{1,4}
  | nth[_-]?(?:s\d{1,3}[_-]?)?\d{1,3}         # NTH-03, NTH-S7-01 (not nth03_export)
  | dod[_-]?\d{1,3}
  | rr[_-]?\d{1,3}
  | rk[_-][a-z0-9]+(?:[_-][a-z0-9]+)?(?:[_-]\d{1,3})?
  | f[_-]?s\d{1,3}[_-]?\d{1,3}
  | f\d{1,3}                                  # F12, F01 failure taxonomy cites
  | s\d{1,3}[_-]?dog[_-]?\d{1,3}              # S7-DOG-05 (exact coordinate)
  | s\d{1,3}[_-]?[a-h]\d{0,3}                 # S6-A04, S6-G02, S4-A, S5-H (exact)
  | s\d{1,3}[_-]\d{1,3}[a-z]?                 # S7-2, S7-1a sub-slice cites (exact)
  | s\d{1,3}                                  # bare S6 / S7 cite
  | s\d{1,3}[a-z]                             # rare S6a-style short cite
  | slice[_-]?\d{1,3}
  | (?:pre|post)[_-]?s\d{1,3}
"""

_CITATION_ID_RE = re.compile(rf"(?ix)^(?:{_CITATION_ATOM})(?:/(?:{_CITATION_ATOM}))*$")

_PATHISH_RE = re.compile(r"(?i)(?:/|\.eval/|^\.)")
_KEBAB_OPERATOR_RE = re.compile(r"(?i)^[a-z][a-z0-9]*(?:-[a-z0-9]+)+$")
_SNAKE_SYMBOL_RE = re.compile(r"(?i)^[a-z_][a-z0-9_]*$")
_DEF_NAME_RE = re.compile(r"(?i)\b(?:def|class|async\s+def)\s+([A-Za-z_][A-Za-z0-9_]*)")
_BOARDISH_RE = re.compile(r"(?i)(?:board|findings-board|batch-[a-z])")


@dataclass(frozen=True)
class Finding:
    path: str
    line_no: int
    family: str
    token: str
    line: str
    role: str = "identity"


def _norm(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def _is_excluded(path: str, excludes: tuple[str, ...] | list[str]) -> bool:
    n = _norm(path)
    for ex in excludes:
        e = _norm(ex)
        if n == e or n.startswith(e.rstrip("/") + "/") or n.startswith(e):
            return True
    return False


def _is_included(path: str, includes: tuple[str, ...] | list[str]) -> bool:
    n = _norm(path)
    base = Path(n).name
    if base.lower() in {b.lower() for b in _SCAN_BASENAMES} and any(_norm(i).lower() == base.lower() for i in includes):
        return True
    for inc in includes:
        i = _norm(inc)
        if not i:
            return True
        if i.endswith("/"):
            if n.startswith(i):
                return True
        elif n == i or n.startswith(i + "/"):
            return True
    return False


def _should_scan_path(path: str, includes: list[str], excludes: list[str]) -> bool:
    if _is_excluded(path, excludes):
        return False
    if not _is_included(path, includes):
        return False
    p = Path(_norm(path))
    if p.name.lower() in {b.lower() for b in _SCAN_BASENAMES}:
        return True
    return p.suffix.lower() in _SCAN_SUFFIXES


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )


def _git_out(args: list[str], cwd: Path) -> str:
    proc = _run_git(args, cwd)
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(msg or f"git {' '.join(args)} failed ({proc.returncode})")
    return proc.stdout


def _changed_files(cwd: Path, base: str, include_working_tree: bool) -> list[str]:
    files: set[str] = set()
    files.update(
        line.strip()
        for line in _git_out(["diff", "--name-only", "--diff-filter=ACMR", f"{base}...HEAD"], cwd).splitlines()
        if line.strip()
    )
    if include_working_tree:
        for args in (
            ["diff", "--name-only", "--diff-filter=ACMR", "HEAD"],
            ["diff", "--name-only", "--diff-filter=ACMR", "--cached"],
            ["ls-files", "--others", "--exclude-standard"],
        ):
            files.update(line.strip() for line in _git_out(args, cwd).splitlines() if line.strip())
    return sorted(files)


def _parse_unified_added_lines(diff_text: str) -> list[tuple[int, str]]:
    added: list[tuple[int, str]] = []
    new_line = 0
    for line in diff_text.splitlines():
        if line.startswith("@@"):
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if m:
                new_line = int(m.group(1))
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added.append((new_line, line[1:]))
            new_line += 1
        elif line.startswith("-"):
            continue
        else:
            new_line += 1
    return added


def _added_lines_from_git(cwd: Path, path: str, base: str, include_working_tree: bool) -> list[tuple[int, str]]:
    """Return added lines for ``path`` relative to ``base``.

    When ``include_working_tree`` is true, build one effective diff from ``base``
    to the current worktree (index + unstaged + untracked) so replacements that
    remove a previously added residue line are not retained as findings.
    """
    if include_working_tree:
        proc = _run_git(["ls-files", "--others", "--exclude-standard", "--", path], cwd)
        if proc.returncode == 0 and proc.stdout.strip():
            # Untracked file: entire content is an addition vs base.
            text = (cwd / path).read_text(encoding="utf-8", errors="replace")
            return list(enumerate(text.splitlines(), start=1))

        # ``base`` .. worktree (includes staged + unstaged tracked edits).
        proc = _run_git(["diff", "-U0", base, "--", path], cwd)
        if proc.returncode == 0 and proc.stdout:
            return _parse_unified_added_lines(proc.stdout)
        return []

    proc = _run_git(["diff", "-U0", f"{base}...HEAD", "--", path], cwd)
    if proc.returncode == 0 and proc.stdout:
        return _parse_unified_added_lines(proc.stdout)
    return []


def _classify_token(token: str) -> list[str]:
    families: list[str] = []
    parts = {token, Path(token).name}
    if "/" in token:
        parts.update(p for p in token.split("/") if p)
    for cand in parts:
        for family, rx in _ALL:
            if rx.search(cand):
                families.append(family)
    seen: set[str] = set()
    out: list[str] = []
    for f in families:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def _tokens_for_line(line: str) -> list[str]:
    tokens: list[str] = [m.group("token") for m in _TOKEN_RE.finditer(line)]
    m = _RECIPE_HEADER_RE.match(line)
    if m:
        tokens.append(m.group(1))
    for bm in re.finditer(r"`([^`]+)`", line):
        raw = bm.group(1).strip()
        tokens.append(raw)
        jm = re.match(r"(?i)just\s+([A-Za-z0-9_-]+)", raw)
        if jm:
            tokens.append(jm.group(1))
    for dm in _DEF_NAME_RE.finditer(line):
        tokens.append(dm.group(1))
    return tokens


def _strip_token(token: str) -> str:
    t = token.strip().strip("`\"'")
    if t.lower().startswith("just "):
        t = t[5:].strip()
    return t


def _is_citation_id(token: str) -> bool:
    t = _strip_token(token)
    if not t or t.startswith("."):
        return False
    # slash-joined taxonomy only (S7/S8, FIND-069/073); real paths handled elsewhere
    if "/" in t and not t.startswith("scratch/"):
        parts = t.split("/")
        if all(_CITATION_ID_RE.match(p) for p in parts if p):
            return True
    return bool(_CITATION_ID_RE.match(t))


def _is_eval_path(token: str) -> bool:
    t = _strip_token(token)
    return t.startswith(".eval/") or "/.eval/" in t


def _is_operator_kebab(token: str) -> bool:
    t = _strip_token(token)
    if not _KEBAB_OPERATOR_RE.match(t):
        return False
    if _is_citation_id(t):
        return False
    if _BOARDISH_RE.search(t):
        return False
    # Prefer durable operator surfaces: recipe/cli prefixes or ceremony compounds.
    if re.search(r"(?i)(?:^|-)(?:proof|wip|tmp|temp|final2|new2|leftover)(?:-|$)", t):
        return True
    if re.search(
        r"(?i)^(?:eval|git|test|check|run|build|docs?|cov|lint|type|release|mirror|opik)(?:-|$)",
        t,
    ):
        return True
    # Generic kebab with embedded stage segment still counts in justfile/code.
    return bool(re.search(r"(?i)(?:^|-)s\d{1,3}(?:-|$)", t))


def _is_durable_identity_token(token: str, *, force_recipe: bool) -> bool:
    """Operator/code identity only - not prose taxonomy labels."""
    t = _strip_token(token)
    if not t:
        return False
    if force_recipe:
        return True
    if t.startswith("scratch/") or "/scratch/" in t:
        return False
    if _is_eval_path(t):
        return True
    if _is_operator_kebab(t):
        return True
    if _SNAKE_SYMBOL_RE.match(t):
        return not _is_citation_id(t)
    # Non-.eval pathish tokens are not treated as operator identity by default.
    return False


def scan_lines(path: str, lines: list[tuple[int, str]]) -> list[Finding]:
    findings: list[Finding] = []
    norm = _norm(path)
    is_just = Path(norm).name.lower() == "justfile" or norm.endswith(".just")
    is_md = norm.endswith(".md")

    for line_no, line in lines:
        force_recipe = bool(is_just and _RECIPE_HEADER_RE.match(line))
        commentish = bool(_COMMENT_LINE_RE.search(line))

        for token in _tokens_for_line(line):
            token_st = _strip_token(token)
            if not token_st:
                continue

            families = _classify_token(token_st)
            if not families:
                continue

            if _is_citation_id(token_st) and not force_recipe:
                continue

            if not _is_durable_identity_token(token_st, force_recipe=force_recipe):
                continue

            # Markdown: only taught operator surfaces (recipes / .eval paths).
            if is_md and not force_recipe and not (_is_eval_path(token_st) or _is_operator_kebab(token_st)):
                continue

            # Comment/table lines outside recipes: paths + operator kebabs only.
            if commentish and not force_recipe and not (_is_eval_path(token_st) or _is_operator_kebab(token_st)):
                continue

            for family in families:
                if (
                    family.startswith("D.proof")
                    and _PROOF_PROSE_OK.search(line)
                    and not (_is_eval_path(token_st) or re.search(r"(?i)[_-]proof|proof[_-]", token_st))
                ):
                    continue
                findings.append(
                    Finding(
                        path=norm,
                        line_no=line_no,
                        family=family,
                        token=token_st,
                        line=line.strip()[:240],
                        role="identity",
                    )
                )
    return _dedupe(findings)


def _dedupe(findings: list[Finding]) -> list[Finding]:
    seen: set[tuple[str, int, str, str]] = set()
    out: list[Finding] = []
    for f in findings:
        key = (f.path, f.line_no, f.family, f.token)
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def scan_repo(
    cwd: Path,
    base: str,
    include_working_tree: bool,
    includes: list[str],
    excludes: list[str],
    paths_filter: list[str] | None = None,
) -> list[Finding]:
    files = _changed_files(cwd, base, include_working_tree)
    if paths_filter:
        wanted = {_norm(p) for p in paths_filter}
        files = [f for f in files if _norm(f) in wanted]

    findings: list[Finding] = []
    for path in files:
        if not _should_scan_path(path, includes, excludes):
            continue
        try:
            lines = _added_lines_from_git(cwd, path, base, include_working_tree)
        except OSError as exc:
            print(f"warning: skip {path}: {exc}", file=sys.stderr)
            continue
        if not lines:
            continue
        findings.extend(scan_lines(path, lines))
    return findings


def _print_text(findings: list[Finding]) -> None:
    if not findings:
        print("deslop-naming-scan: clean - no family A-D identity residue on scanned added lines.")
        print("Families checked: A (stage), B (plan/FIND/INT), C (governance-as-identity), D (ceremony).")
        return
    print(f"deslop-naming-scan: {len(findings)} finding(s)")
    print()
    print("| Path | Line | Family | Token | Excerpt |")
    print("| --- | ---: | --- | --- | --- |")
    for f in findings:
        excerpt = f.line.replace("|", "\\|")
        print(f"| `{f.path}` | {f.line_no} | {f.family} | `{f.token}` | {excerpt} |")
    print()
    print("Rename identity to domain-first scope + behavior + entity.")
    print("Citations in matrices/comments may remain.")
    print("See .agents/skills/code-deslop/references/naming.md")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        default=_DEFAULT_BASE,
        help=f"Git base ref (default: {_DEFAULT_BASE})",
    )
    parser.add_argument(
        "--no-working-tree",
        action="store_true",
        help="Only scan base...HEAD (ignore unstaged/untracked/cached)",
    )
    parser.add_argument(
        "--path",
        dest="paths",
        action="append",
        default=[],
        help="Limit to repo-relative path (repeatable)",
    )
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        help="Extra include prefix (repeatable)",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Extra exclude prefix (repeatable)",
    )
    parser.add_argument(
        "--all-paths",
        action="store_true",
        help="Do not apply default include prefixes (still applies excludes)",
    )
    parser.add_argument(
        "--stdin-file",
        action="store_true",
        help="Read content from stdin; requires one --path label (unit tests)",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--cwd", type=Path, default=None)
    args = parser.parse_args(argv)
    cwd = (args.cwd or Path.cwd()).resolve()

    includes = list(_DEFAULT_INCLUDE)
    if args.all_paths:
        includes = [""]
    includes.extend(args.include)
    excludes = list(_DEFAULT_EXCLUDE) + list(args.exclude)

    if args.all_paths:

        def _should(path: str) -> bool:
            if _is_excluded(path, excludes):
                return False
            p = Path(_norm(path))
            return p.name.lower() in {b.lower() for b in _SCAN_BASENAMES} or p.suffix.lower() in _SCAN_SUFFIXES

    else:

        def _should(path: str) -> bool:
            return _should_scan_path(path, includes, excludes)

    try:
        if args.stdin_file:
            if len(args.paths) != 1:
                print(
                    "error: --stdin-file requires exactly one --path label",
                    file=sys.stderr,
                )
                return 1
            text = sys.stdin.read()
            findings = scan_lines(args.paths[0], list(enumerate(text.splitlines(), start=1)))
        else:
            files = _changed_files(cwd, args.base, not args.no_working_tree)
            if args.paths:
                wanted = {_norm(p) for p in args.paths}
                files = [f for f in files if _norm(f) in wanted]
            findings = []
            for path in files:
                if not _should(path):
                    continue
                lines = _added_lines_from_git(cwd, path, args.base, not args.no_working_tree)
                if not lines:
                    continue
                findings.extend(scan_lines(path, lines))
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        print(json.dumps({"findings": [asdict(f) for f in findings]}, indent=2))
    else:
        _print_text(findings)

    return 2 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
