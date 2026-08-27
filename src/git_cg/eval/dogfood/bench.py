"""S6 Slice 7 dogfood bench harness helpers (S6-G02b).

Maintainer-run only (``just dogfood-bench``); never a CI gate, never blocks
the commit path. Compares the real commit-path latency with dogfood async
mode on vs off using hyperfine, and reports the latency delta plus confidence
interval overlap. "+0ms" is shorthand for these two claims (structural
never-awaited seam + empirical evidence), not a literal zero wall time.

Offline: drives ``git-cg commit --dry-run`` in a fixture repo; no network.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Final

HYPERFINE_MIN_RUNS: Final[int] = 20


class DogfoodBenchError(ValueError):
    """Dogfood bench harness failure (fail-closed)."""


def hyperfine_available() -> bool:
    """True when ``hyperfine`` is on PATH (maintainer prerequisite)."""
    return shutil.which("hyperfine") is not None


def parse_hyperfine_json(path: Path) -> dict[str, Any]:
    """Parse one hyperfine ``--export-json`` file (one or more results).

    Note: ``just dogfood-bench`` exports one file *per command*, so a file
    usually holds exactly one result; the >=2 constraint was wrong for that
    layout. Use ``summarise_delta`` across two parsed files.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DogfoodBenchError(f"cannot parse hyperfine export {path.name}: {exc}") from exc
    results = data.get("results")
    if not isinstance(results, list) or not results:
        raise DogfoodBenchError(f"hyperfine export {path.name} has no results")
    return data


def summarise_delta(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute mean latency delta + CI overlap between async-on and async-off.

    The claim is: async dogfood adds no *measurable* commit-path latency —
    i.e. the confidence intervals overlap and the mean delta is within noise.
    """
    if len(results) < 2:
        raise DogfoodBenchError("need async-off and async-on results")
    off, on = results[0], results[1]
    mean_off = float(off.get("mean", 0.0))
    mean_on = float(on.get("mean", 0.0))
    stddev_off = float(off.get("stddev") or 0.0)
    stddev_on = float(on.get("stddev") or 0.0)
    delta_ms = (mean_on - mean_off) * 1000.0
    # 95% CI half-widths (normal approx; hyperfine already reports stddev).
    ci_off = 1.96 * stddev_off
    ci_on = 1.96 * stddev_on
    overlap = not ((mean_on - ci_on) > (mean_off + ci_off) or (mean_off - ci_off) > (mean_on + ci_on))
    return {
        "mean_off_ms": round(mean_off * 1000.0, 3),
        "mean_on_ms": round(mean_on * 1000.0, 3),
        "delta_ms": round(delta_ms, 3),
        "ci_overlap": overlap,
        "claim": "no measurable commit-path latency from async dogfood" if overlap else "investigate: CI disjoint",
        "shorthand": "+0ms is shorthand for structural-never-await + CI-overlap evidence",
    }


__all__ = [
    "HYPERFINE_MIN_RUNS",
    "DogfoodBenchError",
    "hyperfine_available",
    "main",
    "parse_hyperfine_json",
    "summarise_delta",
]


def main(argv: list[str] | None = None) -> int:
    """CLI: summarise two hyperfine exports (off, on). Maintainer evidence only."""
    import sys

    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) != 2:
        print("usage: python -m git_cg.eval.dogfood.bench OFF.json ON.json", file=sys.stderr)
        return 2
    off_path, on_path = (Path(a) for a in args)
    try:
        data_off = parse_hyperfine_json(off_path)
        data_on = parse_hyperfine_json(on_path)
        off = data_off["results"][0]
        on = data_on["results"][0]
        report = summarise_delta([off, on])
    except DogfoodBenchError as exc:
        print(f"dogfood-bench: {exc}", file=sys.stderr)
        return 1
    print(
        "dogfood-bench: mean_off={mean_off_ms}ms mean_on={mean_on_ms}ms "
        "delta={delta_ms}ms ci_overlap={ci_overlap} ({claim})".format(**report)
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
