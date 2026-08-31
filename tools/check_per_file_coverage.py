#!/usr/bin/env python3
"""Fail if any named coverage file is below a per-file threshold.

pytest-cov ``--cov-fail-under`` only enforces the *combined* total. This
helper reads a coverage.py JSON report and enforces a minimum percent on
each requested file path (repo-relative or absolute suffix match).

Exit codes:
  0 — all files meet threshold (or were omitted with --allow-missing)
  1 — usage / IO error
  2 — one or more files below threshold (coverage-style fail)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _pct(covered: float, total: float) -> float:
    """Compute coverage percentage; return 100.0 when total is zero."""
    if total <= 0:
        return 100.0
    return (100.0 * covered) / total


def _match_file(files: dict[str, dict], wanted: str) -> tuple[str, dict] | None:
    """Return (key, data) for the best path match of *wanted*."""
    wanted_norm = wanted.replace("\\", "/")
    # Exact / suffix match preferred.
    candidates: list[tuple[int, str, dict]] = []
    for key, data in files.items():
        key_norm = key.replace("\\", "/")
        if key_norm == wanted_norm or key_norm.endswith("/" + wanted_norm) or key_norm.endswith(wanted_norm):
            candidates.append((len(key_norm), key, data))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])  # shortest path wins (most specific suffix)
    _, key, data = candidates[0]
    return key, data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        dest="json_path",
        type=Path,
        required=True,
        help="Path to coverage.py JSON report (coverage.json)",
    )
    parser.add_argument(
        "--fail-under",
        type=float,
        default=80.0,
        help="Minimum percent coverage required per file (default: 80)",
    )
    parser.add_argument(
        "--file",
        dest="files",
        action="append",
        default=[],
        help="Repo-relative source file to gate (repeatable)",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Treat missing files as a soft skip instead of a hard failure",
    )
    args = parser.parse_args(argv)

    if not args.files:
        print("error: pass at least one --file", file=sys.stderr)
        return 1
    if not args.json_path.is_file():
        print(f"error: coverage JSON not found: {args.json_path}", file=sys.stderr)
        return 1

    payload = json.loads(args.json_path.read_text(encoding="utf-8"))
    files = payload.get("files") or {}
    if not isinstance(files, dict):
        print("error: coverage JSON missing 'files' object", file=sys.stderr)
        return 1

    rows: list[tuple[str, float, str]] = []
    failures: list[str] = []
    missing: list[str] = []

    for wanted in args.files:
        matched = _match_file(files, wanted)
        if matched is None:
            missing.append(wanted)
            rows.append((wanted, 0.0, "MISSING"))
            continue
        key, data = matched
        summary = data.get("summary") or {}
        # Prefer branch-aware totals when present; fall back to statement lines.
        covered = float(summary.get("covered_lines", 0))
        total = float(summary.get("num_statements", 0))
        # If branch data exists, fold it into the denominator the same way
        # coverage percent is commonly presented (stmts + branches).
        if "covered_branches" in summary and "num_branches" in summary:
            covered += float(summary["covered_branches"])
            total += float(summary["num_branches"])
        pct = _pct(covered, total)
        rows.append((key, pct, "ok" if pct + 1e-9 >= args.fail_under else "BELOW"))
        if pct + 1e-9 < args.fail_under:
            failures.append(f"{key}: {pct:.2f}% < {args.fail_under:.2f}%")

    width = max(len(path) for path, _, _ in rows)
    print(f"Per-file coverage gate (fail-under={args.fail_under:.2f}%)")
    print("-" * (width + 18))
    for path, pct, status in rows:
        print(f"{path:<{width}}  {pct:6.2f}%  {status}")
    print("-" * (width + 18))

    if missing and not args.allow_missing:
        print("error: missing coverage entries:", file=sys.stderr)
        for path in missing:
            print(f"  - {path}", file=sys.stderr)
        return 2
    if missing and args.allow_missing:
        print(f"warning: skipped missing files: {', '.join(missing)}", file=sys.stderr)

    if failures:
        print("error: per-file coverage below threshold:", file=sys.stderr)
        for line in failures:
            print(f"  - {line}", file=sys.stderr)
        return 2

    print("OK: all gated files meet per-file threshold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
