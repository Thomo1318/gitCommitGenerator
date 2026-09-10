"""Best-effort acceptpath binder counters.

Optional diagnostics for verbose inspection and
``.eval/diagnostics/binder_counters.json``. Counters are never a product
gate: corrupt, missing, stale, or unwritable diagnostics must not block
bind. Persistence is best-effort atomic read-modify-write; every failure
is swallowed.

No network. No Opik. Refs: #257.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from git_cg.eval.binding import paths

__all__ = [
    "COUNTERS_FILENAME",
    "COUNTER_NAMES",
    "binder_counters_path",
    "increment_binder_counters",
]

#: Closed counter key set persisted in ``binder_counters.json``.
COUNTER_NAMES: tuple[str, ...] = (
    "bind_attempts",
    "bind_success",
    "cache_hits",
    "cache_misses",
    "lock_fallbacks",
)

COUNTERS_FILENAME = "binder_counters.json"

_ZEROED: dict[str, int] = {name: 0 for name in COUNTER_NAMES}


def binder_counters_path(repo_root: Path) -> Path:
    """Return contained ``.eval/diagnostics/binder_counters.json`` (not created)."""
    return paths.diagnostics_dir(repo_root) / COUNTERS_FILENAME


def increment_binder_counters(repo_root: Path | None, **deltas: int) -> None:
    """Increment named counters on disk. Never raises.

    Unknown names, non-ints, booleans, and non-positive amounts are ignored.
    Positive amounts are added as-is so a caller may batch (for example a
    recovered file or a test). Production bind events pass ``1``. Missing
    or corrupt files recover to zeroed counters. Persistence uses
    :func:`paths.atomic_write_json` and is fully swallowed on failure.
    """
    try:
        if repo_root is None or not deltas:
            return
        root = Path(repo_root).resolve()
        path = binder_counters_path(root)
        current = _load_counters(path)
        changed = False
        for name, amount in deltas.items():
            if name not in current:
                continue
            if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
                continue
            current[name] += amount
            changed = True
        if not changed:
            return
        payload = {name: current[name] for name in COUNTER_NAMES}
        paths.atomic_write_json(path, payload)
    except Exception:
        return


def _load_counters(path: Path) -> dict[str, int]:
    """Return the closed counter set, recovering to zeros on any read failure."""
    values = dict(_ZEROED)
    try:
        if path.is_symlink() or not path.is_file():
            return values
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except OSError, UnicodeError, json.JSONDecodeError, ValueError:
        return values
    if not isinstance(data, dict):
        return values
    for name in COUNTER_NAMES:
        raw = data.get(name, 0)
        if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
            continue
        values[name] = raw
    return values
