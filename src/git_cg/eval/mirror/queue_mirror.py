"""Optional cloud review-queue mirror (non-SoT, Issue #254 / S7-E).

Write-only projection seam for the local HITL review queue toward Opik.

Law:

* **Non-SoT:** never accept, promote, doctor, or gate authority. Local Layer-A
  review rows remain the sole source of truth.
* **Write-only by construction:** public surface is a single push entry point.
  No fetch/list/load/read API and no reverse path into promote/doctor/gates.
* **Offline-first close bar:** unconfigured mode, ``off``/``local_only``, or
  unreachable network → safe structured no-op; never raises into the product
  path.
* **Live projection is optional/NTH:** a real Opik upload may land later behind
  explicit configuration; it is not required to close S7-E and must stay
  fail-open / non-authoritative.
* **No Opik import at module scope:** offline core and product accept path must
  never import the Opik SDK from this module.

Distinct from :mod:`git_cg.eval.mirror.queue` (local export-queue Layer-A).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

__all__ = [
    "QUEUE_MIRROR_AUTHORITY",
    "QueueMirrorResult",
    "QueueMirrorStatus",
    "mirror_review_queue",
]

#: Structural authority stamp — cloud projection is never accept authority.
QUEUE_MIRROR_AUTHORITY: Final[str] = "advisory_non_sot"

_MAX_NOTES: Final = 32
_MAX_NOTE_LEN: Final = 200

QueueMirrorStatus = Literal["skipped_off", "noop_unconfigured", "noop_unreachable", "projected"]


def _scrub_notes(notes: Iterable[str] | None) -> tuple[str, ...]:
    """Bound and sanitize operator notes (max count/length; no multi-line dumps)."""
    if not notes:
        return ()
    out: list[str] = []
    for note in notes:
        text = str(note).replace("\n", " ").strip()
        if not text:
            continue
        out.append(text[:_MAX_NOTE_LEN])
        if len(out) >= _MAX_NOTES:
            break
    return tuple(out)


@dataclass(frozen=True, slots=True)
class QueueMirrorResult:
    """Structured outcome of a review-queue mirror attempt.

    Invariants:

    * ``authority`` is always ``advisory_non_sot``.
    * ``product_accept_blocked`` is always ``False``.
    * ``read_back`` is always ``False`` (write-only seam; never feeds gates).
    """

    status: QueueMirrorStatus
    attempted: int = 0
    projected: int = 0
    skipped: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)
    authority: str = field(default=QUEUE_MIRROR_AUTHORITY, init=False)
    product_accept_blocked: bool = field(default=False, init=False)
    read_back: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Clamp non-SoT / write-only invariants after initialization."""
        object.__setattr__(self, "authority", QUEUE_MIRROR_AUTHORITY)
        object.__setattr__(self, "product_accept_blocked", False)
        object.__setattr__(self, "read_back", False)
        object.__setattr__(self, "attempted", max(0, int(self.attempted)))
        object.__setattr__(self, "projected", max(0, int(self.projected)))
        object.__setattr__(self, "skipped", max(0, int(self.skipped)))
        object.__setattr__(self, "notes", _scrub_notes(self.notes))

    def to_dict(self) -> dict[str, Any]:
        """Public machine-readable view (always non-blocking / non-SoT)."""
        return {
            "status": self.status,
            "authority": QUEUE_MIRROR_AUTHORITY,
            "attempted": int(self.attempted),
            "projected": int(self.projected),
            "skipped": int(self.skipped),
            "product_accept_blocked": False,
            "read_back": False,
            "notes": list(self.notes),
        }


def _resolve_mode(config: Mapping[str, Any] | None) -> str:
    """Return canonical mode token; default ``off`` when absent/invalid."""
    if not isinstance(config, Mapping):
        return "off"
    mode = str(config.get("mode", "off") or "off").strip().lower()
    if mode in {"off", "local", "local_only", "mirror", "strict_mirror"}:
        # Plan alias: local → local_only skip semantics.
        return "local_only" if mode == "local" else mode
    return "off"


def _has_project_lane(config: Mapping[str, Any]) -> bool:
    """True when any four-lane pin or legacy project_name is non-empty."""
    projects = config.get("projects")
    if isinstance(projects, Mapping):
        for key in ("eval", "live", "ci", "import"):
            val = projects.get(key)
            if isinstance(val, str) and val.strip():
                return True
    legacy = config.get("project_name")
    return isinstance(legacy, str) and bool(legacy.strip())


def _offline_status(config: Mapping[str, Any] | None) -> QueueMirrorStatus:
    """Classify the offline/no-op status for the required S7-E close bar.

    Live Opik projection remains optional/NTH. Even an active configured mode
    no-ops as ``noop_unreachable`` until an explicit online projector lands.
    """
    mode = _resolve_mode(config)
    if mode in {"off", "local_only"}:
        return "skipped_off"
    if not isinstance(config, Mapping) or not _has_project_lane(config):
        return "noop_unconfigured"
    return "noop_unreachable"


def mirror_review_queue(
    repo: Path | None = None,
    *,
    config: Mapping[str, Any] | None = None,
    review_ids: list[str] | None = None,
    enable_live: bool = False,
    projector: Any | None = None,
    projector_factory: Any | None = None,
) -> QueueMirrorResult:
    """Optionally project local HITL review rows to Opik (write-only).

    Offline / unconfigured / unreachable → safe no-op result.
    Never raises for transport or configuration reasons.
    Never reads cloud state back into local gates.

    Live projection is opt-in via ``enable_live=True`` or config key
    ``queue_mirror_live``. The live path lives in
    :mod:`git_cg.eval.mirror.queue_projector` so this module stays free of
    Opik SDK imports (structural offline guarantee).
    """
    live_flag = bool(enable_live)
    if not live_flag and isinstance(config, Mapping):
        raw = config.get("queue_mirror_live")
        if isinstance(raw, bool):
            live_flag = raw
        elif isinstance(raw, str):
            live_flag = raw.strip().lower() in {"1", "true", "yes", "on"}

    if live_flag:
        from git_cg.eval.mirror.queue_projector import project_review_queue_live

        return project_review_queue_live(
            repo,
            config=config,
            review_ids=review_ids,
            enable_live=True,
            projector=projector,
            projector_factory=projector_factory,
        )

    del repo  # API symmetry only; offline path is filesystem-free
    attempted = len(review_ids) if review_ids else 0
    status = _offline_status(config)
    notes_by_status: dict[QueueMirrorStatus, str] = {
        "skipped_off": "queue mirror skipped: mode off/local_only or unset",
        "noop_unconfigured": "queue mirror no-op: Opik project lanes unconfigured",
        "noop_unreachable": "queue mirror no-op: live Opik projection not enabled (optional/NTH)",
        "projected": "queue mirror projected",  # reserved; live path is NTH
    }
    return QueueMirrorResult(
        status=status,
        attempted=attempted,
        skipped=attempted,
        notes=(notes_by_status[status],),
    )
