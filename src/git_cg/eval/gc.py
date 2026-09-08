"""Operator GC for acceptpath debris.

Retention helper for ``.eval/bundles/acceptpath/``. Stdlib-only at import
time so ``git_cg.eval.cli`` stays binder/Opik-free. Path helpers are
imported lazily inside functions.

Normal mode deletes stale *non-authoritative* debris only
(``index.json``, ``.bind.lock``, leftover ``.*.tmp`` files, unadoptable JSON).
Authoritative ``sess_<32-hex>.json`` names required for reuse identity
are preserved unless ``force=True``. ``dry_run`` selects without deleting.

Duration syntax is a positive integer plus ``s`` / ``m`` / ``h`` / ``d``.
No default age. Age is file mtime. Symlinks and unsafe/non-regular files
are skipped. Malformed JSON never blocks the command.

No network. No Opik. No binder import. Refs: #257.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

__all__ = [
    "DURATION_UNITS",
    "GcError",
    "GcFile",
    "GcResult",
    "gc_acceptpath",
    "parse_duration",
]

#: Duration unit suffixes in seconds.
DURATION_UNITS: dict[str, int] = {"s": 1, "m": 60, "h": 3600, "d": 86400}

_DURATION_RE = re.compile(r"^([1-9][0-9]*)([smhd])$")
_SESSION_ID_RE = re.compile(r"^sess_[0-9a-f]{32}$")
_LOCK_NAME = ".bind.lock"
_INDEX_NAME = "index.json"


class GcError(ValueError):
    """Deterministic acceptpath GC failure (fail-closed)."""

    def __init__(self, message: str, *, code: str, exit_code: int, hint: str | None = None) -> None:
        """Attach GC failure code, exit class, and operator hint."""
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code
        self.hint = hint


GcKind = Literal["authoritative", "debris"]


@dataclass(frozen=True, slots=True)
class GcFile:
    """One selected or skipped acceptpath file."""

    path: str
    kind: GcKind
    age_seconds: float
    reason: str


@dataclass(frozen=True, slots=True)
class GcResult:
    """Closed acceptpath GC summary."""

    older_than: str
    older_than_seconds: int
    force: bool
    dry_run: bool
    selected: tuple[GcFile, ...]
    deleted: tuple[GcFile, ...]
    preserved: tuple[GcFile, ...]
    skipped: tuple[GcFile, ...]

    def to_data(self) -> dict[str, Any]:
        """Closed ``cli_output_envelope_v1.data`` payload for ``eval gc``."""
        return {
            "acceptpath": True,
            "older_than": self.older_than,
            "older_than_seconds": self.older_than_seconds,
            "force": self.force,
            "dry_run": self.dry_run,
            "selected": [item.path for item in self.selected],
            "deleted": [item.path for item in self.deleted],
            "preserved": [item.path for item in self.preserved],
            "skipped": [item.path for item in self.skipped],
            "selected_count": len(self.selected),
            "deleted_count": len(self.deleted),
            "preserved_count": len(self.preserved),
            "skipped_count": len(self.skipped),
        }


def parse_duration(value: str) -> int:
    """Parse a required positive duration such as ``30s``, ``15m``, ``2h``, ``7d``.

    Raises:
        GcError: when ``value`` is missing, zero, or not a known unit suffix.
    """
    raw = (value or "").strip()
    match = _DURATION_RE.fullmatch(raw)
    if match is None:
        raise GcError(
            f"invalid --older-than {value!r}; expected a positive integer plus s/m/h/d",
            code="EVAL_USAGE",
            exit_code=2,
            hint="Examples: 30s, 15m, 2h, 7d",
        )
    amount = int(match.group(1))
    unit = match.group(2)
    return amount * DURATION_UNITS[unit]


def gc_acceptpath(
    repo_root: Path,
    *,
    older_than: str,
    force: bool = False,
    dry_run: bool = False,
) -> GcResult:
    """Select and optionally delete stale acceptpath files under ``repo_root``.

    Never deletes outside the contained acceptpath directory. Authoritative
    session-named bundles are preserved unless ``force`` is true.
    """
    seconds = parse_duration(older_than)
    from git_cg.eval.binding.paths import (
        LayerAPathError,
        acceptpath_bundles_dir,
        acceptpath_index_file,
    )

    try:
        root = Path(repo_root).resolve()
        bundles_dir = acceptpath_bundles_dir(root)
        index_path = acceptpath_index_file(root)
    except LayerAPathError as exc:
        raise GcError(
            str(exc),
            code="EVAL_STORE_INTEGRITY",
            exit_code=4,
            hint="Refuse paths that escape .eval/bundles/acceptpath/",
        ) from exc

    now = time.time()
    selected: list[GcFile] = []
    preserved: list[GcFile] = []
    skipped: list[GcFile] = []

    if not bundles_dir.is_dir() or bundles_dir.is_symlink():
        return GcResult(
            older_than=older_than.strip(),
            older_than_seconds=seconds,
            force=force,
            dry_run=dry_run,
            selected=(),
            deleted=(),
            preserved=(),
            skipped=(),
        )

    try:
        children = sorted(bundles_dir.iterdir(), key=lambda item: item.name)
    except OSError as exc:
        raise GcError(
            f"cannot list acceptpath directory: {exc}",
            code="EVAL_STORE_INTEGRITY",
            exit_code=4,
        ) from exc

    bundles_resolved = bundles_dir.resolve()
    for child in children:
        file, eligible = _classify_child(
            child,
            bundles_resolved=bundles_resolved,
            index_path=index_path,
            now=now,
            cutoff=seconds,
        )
        if not eligible:
            skipped.append(file)
            continue
        if file.kind == "authoritative" and not force:
            preserved.append(file)
            continue
        selected.append(file)

    deleted: list[GcFile] = []
    if not dry_run:
        for item in selected:
            target = bundles_dir / Path(item.path).name
            if not _safe_to_unlink(target, bundles_resolved):
                skipped.append(
                    GcFile(
                        path=item.path,
                        kind=item.kind,
                        age_seconds=item.age_seconds,
                        reason="unsafe_unlink",
                    )
                )
                continue
            try:
                target.unlink()
            except OSError as exc:
                skipped.append(
                    GcFile(
                        path=item.path,
                        kind=item.kind,
                        age_seconds=item.age_seconds,
                        reason=f"unlink_failed:{exc}",
                    )
                )
                continue
            deleted.append(item)

    return GcResult(
        older_than=older_than.strip(),
        older_than_seconds=seconds,
        force=force,
        dry_run=dry_run,
        selected=tuple(selected),
        deleted=tuple(deleted),
        preserved=tuple(preserved),
        skipped=tuple(skipped),
    )


def _classify_child(
    child: Path,
    *,
    bundles_resolved: Path,
    index_path: Path,
    now: float,
    cutoff: int,
) -> tuple[GcFile, bool]:
    """Return ``(file, eligible_by_age)``."""
    rel = child.name
    try:
        if child.resolve().parent != bundles_resolved:
            return (
                GcFile(path=rel, kind="debris", age_seconds=0.0, reason="escaped_path"),
                False,
            )
    except OSError:
        return (
            GcFile(path=rel, kind="debris", age_seconds=0.0, reason="unresolvable"),
            False,
        )
    if child.is_symlink() or child.is_dir() or not child.is_file():
        return (
            GcFile(path=rel, kind="debris", age_seconds=0.0, reason="non_regular"),
            False,
        )
    try:
        age = now - child.stat().st_mtime
    except OSError:
        return (
            GcFile(path=rel, kind="debris", age_seconds=0.0, reason="unreadable_mtime"),
            False,
        )
    kind: GcKind = "authoritative" if _is_protected_session_file(child) else "debris"
    if kind == "debris" and not _is_acceptpath_debris(child, index_path=index_path):
        return (
            GcFile(path=rel, kind="debris", age_seconds=age, reason="unmanaged"),
            False,
        )
    if age < float(cutoff):
        return (
            GcFile(path=rel, kind=kind, age_seconds=age, reason="too_new"),
            False,
        )
    reason = "authoritative_bundle" if kind == "authoritative" else "stale_debris"
    return GcFile(path=rel, kind=kind, age_seconds=age, reason=reason), True


def _is_acceptpath_debris(path: Path, *, index_path: Path) -> bool:
    """True for rebuildable cache, lock, leftover .*.tmp files, or unadoptable JSON."""
    name = path.name
    if name == _INDEX_NAME or path == index_path:
        return True
    if name == _LOCK_NAME:
        return True
    if name.startswith(".") and name.endswith(".tmp"):
        return True
    return name.endswith(".json")


def _is_protected_session_file(path: Path) -> bool:
    """True for valid-looking ``sess_<32-hex>.json`` reuse-identity names."""
    if path.suffix != ".json" or path.is_symlink() or not path.is_file():
        return False
    return _SESSION_ID_RE.fullmatch(path.stem) is not None


def _safe_to_unlink(path: Path, bundles_resolved: Path) -> bool:
    """Refuse to unlink escaped, missing, or non-regular targets."""
    try:
        resolved = path.resolve()
        if resolved.parent != bundles_resolved:
            return False
        if path.is_symlink() or path.is_dir() or not path.is_file():
            return False
    except OSError:
        return False
    return True
