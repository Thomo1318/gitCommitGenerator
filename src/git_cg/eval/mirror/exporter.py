"""S4b export orchestration (F4 fail-open, FIND-022 bounded flush).

Drains the Layer-A export queue through a :class:`Transport`. Every failure is
classified (``export_network`` / ``export_auth`` / ``export_validation`` /
``export_size``), recorded on the queue row, and **never** propagates to the
product accept path — :func:`drain_queue` always returns a summary and never
raises for transport reasons.

Queue rows transition ``pending → sending → sent | failed`` under the queue's
atomic state machine. A bounded flush timeout is honoured so a short-lived
hook process cannot hang (FIND-022).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from git_cg.eval.mirror import queue as export_queue
from git_cg.eval.mirror.health import ExportHealth
from git_cg.eval.mirror.result import MirrorResult, build_mirror_result
from git_cg.eval.mirror.secrets import MirrorSecretError, OpikRuntimeSecrets, resolve_opik_secrets
from git_cg.eval.mirror.transport import ExportTransportError, Transport

__all__ = [
    "DrainSummary",
    "drain_queue",
    "list_pending_items",
    "mirror_result_from_drain",
]


@dataclass(frozen=True)
class DrainSummary:
    """Outcome of a queue drain. Never product-blocking."""

    attempted: int = 0
    exported: int = 0
    failed: int = 0
    skipped: int = 0
    error_classes: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def succeeded(self) -> int:
        """Alias used by MirrorResult field naming."""
        return self.exported


def list_pending_items(repo_root: Path | None = None) -> list[dict[str, Any]]:
    """Return all ``pending`` queue rows (fail-open: unreadable rows skipped)."""
    root = repo_root if repo_root is not None else export_queue.resolve_repo_root()
    qdir = export_queue.export_queue_dir(root)
    if not qdir.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(qdir.glob("*.json")):
        try:
            item = export_queue.load_queue_item(path.stem, repo_root=root)
        except export_queue.ExportQueueError:
            continue
        if item.get("status") == "pending":
            out.append(item)
    return out


def _resolve_secrets(config: Mapping[str, Any]) -> OpikRuntimeSecrets:
    """Resolve secrets; ``require_key`` only when the mode needs network auth.

    Key-optional modes (local durability / off):
      * ``off`` — export skipped
      * ``local`` — shipped legacy local durability token (pre P0-1 alias)
      * ``local_only`` — plan vocabulary (post P0-1)

    Every other resolved mode (``mirror``, ``strict_mirror``, …) requires a
    resolved Opik API key. Invented key-bypass mode tokens are not recognised
    — unknown or network modes fail closed at secret resolution.
    """
    mode = str(config.get("mode", "off") or "off")
    require_key = mode not in {"off", "local", "local_only"}
    return resolve_opik_secrets(require_key=require_key)


def _project_from_config(config: Mapping[str, Any]) -> str:
    """Prefer projects.eval; fall back to legacy project_name."""
    projects = config.get("projects")
    if isinstance(projects, Mapping):
        eval_p = str(projects.get("eval") or "").strip()
        if eval_p:
            return eval_p
    return str(config.get("project_name") or "").strip()


def drain_queue(
    config: Mapping[str, Any],
    *,
    transport: Transport,
    repo_root: Path | None = None,
    secrets: OpikRuntimeSecrets | None = None,
    max_items: int | None = None,
) -> DrainSummary:
    """Drain queued export rows through ``transport``. Never raises.

    Parameters:
        config: resolved ``git_cg_opik_config_v1`` dict (fail-closed).
        transport: the upload transport (real SDK or mock).
        repo_root: repo root for the queue dir (defaults to discovery).
        secrets: pre-resolved secrets; resolved on demand when omitted.
        max_items: optional cap on rows processed this drain.

    Returns a :class:`DrainSummary`. All transport/secret failures are
    classified and recorded on the row; the function itself never raises for
    export reasons (F4).
    """
    root = repo_root if repo_root is not None else export_queue.resolve_repo_root()
    mode = str(config.get("mode", "off") or "off")
    if mode == "off":
        return DrainSummary(notes=("skipped_off",))

    rows = list_pending_items(repo_root=root)
    if max_items is not None:
        rows = rows[: max(0, max_items)]

    if not rows:
        return DrainSummary(notes=("queue_empty",))

    project = _project_from_config(config)
    flush_timeout_ms = int(config.get("flush_timeout_ms", 5000))

    try:
        resolved = secrets if secrets is not None else _resolve_secrets(config)
    except MirrorSecretError as exc:
        # Auth failure: mark every pending row failed with export_auth and stop.
        for row in rows:
            qid = row["queue_id"]
            export_queue.mark_queue_item(qid, "sending", repo_root=root)
            export_queue.mark_queue_item(qid, "failed", repo_root=root, notes=f"export_auth: {str(exc)[:160]}")
        return DrainSummary(
            attempted=0,
            failed=len(rows),
            error_classes=("export_auth",),
            notes=("secret_resolution_failed",),
        )

    attempted = exported = failed = 0
    classes: list[str] = []
    for row in rows:
        qid = row["queue_id"]
        export_queue.mark_queue_item(qid, "sending", repo_root=root)
        attempted += 1
        try:
            transport.upload(
                project=project,
                experiment_name=row.get("meta", {}).get("batch_id") or qid,
                payload=row.get("payload") or {"item_ids": row.get("meta", {}).get("item_ids", [])},
                secrets=resolved,
                timeout_ms=flush_timeout_ms,
            )
        except ExportTransportError as exc:
            failed += 1
            classes.append(exc.error_class)
            export_queue.mark_queue_item(qid, "failed", repo_root=root, notes=str(exc)[:200])
        except Exception as exc:  # last-resort: never propagate (F4)
            failed += 1
            classes.append("export_network")
            export_queue.mark_queue_item(
                qid,
                "failed",
                repo_root=root,
                notes=f"export_network: {type(exc).__name__}: {str(exc)[:140]}",
            )
        else:
            exported += 1
            export_queue.mark_queue_item(qid, "sent", repo_root=root)

    return DrainSummary(
        attempted=attempted,
        exported=exported,
        failed=failed,
        error_classes=tuple(dict.fromkeys(classes)),
    )


def mirror_result_from_drain(
    config: Mapping[str, Any],
    summary: DrainSummary,
    *,
    health: ExportHealth | str | None = None,
) -> MirrorResult:
    """Build the P0-7 MirrorResult from a drain summary + resolved config."""
    mode = str(config.get("mode", "off") or "off")
    return build_mirror_result(
        mode=mode,
        health=health,
        attempted=summary.attempted,
        succeeded=summary.exported,
        failed=summary.failed,
        deferred=summary.skipped,
        error_classes=summary.error_classes,
        notes=summary.notes,
    )
