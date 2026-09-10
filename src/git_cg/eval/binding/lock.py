"""Short-lived acceptpath bind lock for reuse-scan-plus-write.

Best-effort concurrency hygiene around acceptpath bind. Lock failure or a
stale lock never blocks bind or product accept — callers fall back to the
unlocked atomic-replace path.

A holder releases only its own lock: the payload carries an ownership nonce
and :meth:`BindLock.release` unlinks only on an exact nonce match.

No network. No Opik. Diagnostics-only contention control.

Refs: #257.
"""

from __future__ import annotations

import contextlib
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "BIND_LOCK_NAME",
    "STALE_LOCK_SECONDS",
    "BindLock",
    "acquire_bind_lock",
]

#: Lock file name under the acceptpath bundles directory.
BIND_LOCK_NAME = ".bind.lock"

#: Locks older than this many seconds are treated as stale and reclaimable.
STALE_LOCK_SECONDS = 30.0

#: Default acquisition poll budget (seconds).
_DEFAULT_TIMEOUT = 0.25

#: Poll interval while waiting for a live lock (seconds).
_POLL_INTERVAL = 0.05


@dataclass(slots=True)
class BindLock:
    """Held short-lived bind lock. Call :meth:`release` when the critical section ends."""

    path: Path
    nonce: str
    _released: bool = False

    def release(self) -> None:
        """Best-effort unlock. Never raises.

        Unlinks only when the on-disk payload still carries this holder's
        ownership nonce. Missing, unreadable, malformed, legacy, or replaced
        payloads are a no-op. The residual read-then-unlink TOCTOU window is
        accepted (NTH-B07).
        """
        if self._released:
            return
        self._released = True
        with contextlib.suppress(OSError, UnicodeError, ValueError):
            current = _parse_lock_nonce(self.path.read_bytes())
            if current == self.nonce:
                self.path.unlink(missing_ok=True)

    def __enter__(self) -> BindLock:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.release()


def _lock_mtime_age(path: Path) -> float | None:
    """Return lock age in seconds, or ``None`` when unreadable."""
    try:
        return time.time() - path.stat().st_mtime
    except OSError:
        return None


def _parse_lock_nonce(payload: bytes) -> str | None:
    """Return the ownership nonce from a lock payload, or ``None``."""
    for part in payload.decode("utf-8").split():
        if part.startswith("nonce="):
            nonce = part.removeprefix("nonce=")
            return nonce or None
    return None


def _try_create_lock(path: Path) -> BindLock | None:
    """Attempt O_EXCL create of ``path``. Returns lock or ``None``."""
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(str(path), flags, 0o600)
    except FileExistsError:
        return None
    except OSError:
        return None
    nonce = secrets.token_hex(16)
    try:
        payload = f"pid={os.getpid()} t={time.time():.6f} nonce={nonce}\n".encode()
        os.write(fd, payload)
    except OSError:
        with contextlib.suppress(OSError):
            os.close(fd)
        with contextlib.suppress(OSError):
            path.unlink(missing_ok=True)
        return None
    finally:
        with contextlib.suppress(OSError):
            os.close(fd)
    return BindLock(path=path, nonce=nonce)


def acquire_bind_lock(
    bundles_dir: Path,
    timeout: float = _DEFAULT_TIMEOUT,
    *,
    stale_after: float = STALE_LOCK_SECONDS,
) -> BindLock | None:
    """Acquire a short-lived bind lock under ``bundles_dir``.

    Returns:
        :class:`BindLock` on success, or ``None`` on timeout / unrecoverable
        failure. **Never raises.** Callers must treat ``None`` as permission to
        proceed on the unlocked atomic-replace path.

    Stale locks (mtime age ``> stale_after``) are unlinked best-effort and
    re-attempted within the timeout budget.
    """
    try:
        bundles_dir = Path(bundles_dir)
        bundles_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError:
        return None

    lock_path = bundles_dir / BIND_LOCK_NAME
    deadline = time.monotonic() + max(0.0, float(timeout))
    reclaimed_stale = False

    while True:
        held = _try_create_lock(lock_path)
        if held is not None:
            return held

        age = _lock_mtime_age(lock_path)
        if age is not None and age > stale_after and not reclaimed_stale:
            # One stale reclaim attempt; if another writer wins the race,
            # fall through to timeout/None rather than spinning forever.
            with contextlib.suppress(OSError):
                lock_path.unlink(missing_ok=True)
            reclaimed_stale = True
            continue

        if time.monotonic() >= deadline:
            return None
        time.sleep(_POLL_INTERVAL)
