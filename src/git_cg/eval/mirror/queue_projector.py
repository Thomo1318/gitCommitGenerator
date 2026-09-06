"""Optional live Opik review-queue projector (S7-5 NTH, Issue #254).

Write-only, fail-open projection of local HITL review rows toward Opik.
Distinct from :mod:`git_cg.eval.mirror.queue_mirror`, which remains the
offline-safe no-op seam and must not import the Opik SDK at module scope.

Law:

* Local ``.eval/review_queue`` remains SoT.
* Never read remote data back into promote / doctor / gates / local queue.
* Explicit opt-in via ``enable_live=True`` (or config ``queue_mirror_live``).
* Network/auth failure → structured no-op / warn notes; never product-blocking.
* No module-scope Opik import.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final, Protocol, runtime_checkable

from git_cg.eval.mirror.queue_mirror import QUEUE_MIRROR_AUTHORITY, QueueMirrorResult, QueueMirrorStatus
from git_cg.eval.mirror.redaction import sanitize_export_tree
from git_cg.eval.mirror.transport import scrub_export_note

__all__ = [
    "LiveQueueProjector",
    "project_review_queue_live",
]

_MAX_ITEMS: Final = 200


@runtime_checkable
class LiveQueueProjector(Protocol):
    """Injectable write-only projector used by tests and live adapters."""

    def project_items(self, items: Sequence[Mapping[str, Any]], *, project: str) -> int:
        """Project items; return count successfully projected."""


def _resolve_mode(config: Mapping[str, Any] | None) -> str:
    if not isinstance(config, Mapping):
        return "off"
    mode = str(config.get("mode", "off") or "off").strip().lower()
    if mode in {"off", "local", "local_only", "mirror", "strict_mirror"}:
        return "local_only" if mode == "local" else mode
    return "off"


def _has_project_lane(config: Mapping[str, Any]) -> bool:
    projects = config.get("projects")
    if isinstance(projects, Mapping):
        for key in ("eval", "live", "ci", "import"):
            val = projects.get(key)
            if isinstance(val, str) and val.strip():
                return True
    legacy = config.get("project_name")
    return isinstance(legacy, str) and bool(legacy.strip())


def _offline_status(config: Mapping[str, Any] | None) -> QueueMirrorStatus:
    mode = _resolve_mode(config)
    if mode in {"off", "local_only"}:
        return "skipped_off"
    if not isinstance(config, Mapping) or not _has_project_lane(config):
        return "noop_unconfigured"
    return "noop_unreachable"


def _eval_project(config: Mapping[str, Any]) -> str | None:
    projects = config.get("projects")
    if isinstance(projects, Mapping):
        for key in ("eval", "live", "ci", "import"):
            val = projects.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    legacy = config.get("project_name")
    if isinstance(legacy, str) and legacy.strip():
        return legacy.strip()
    return None


def _live_enabled(config: Mapping[str, Any] | None, *, enable_live: bool) -> bool:
    if enable_live:
        return True
    if not isinstance(config, Mapping):
        return False
    flag = config.get("queue_mirror_live")
    if isinstance(flag, bool):
        return flag
    if isinstance(flag, str):
        return flag.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _review_item(row: Mapping[str, Any]) -> dict[str, Any] | None:
    """Normalize show_review/list payloads to the review item dict."""
    nested = row.get("item")
    if isinstance(nested, dict):
        return nested
    if "review_id" in row or "review" in row:
        return dict(row)
    return None


def _load_local_items(repo: Path | None, *, review_ids: list[str] | None) -> list[dict[str, Any]]:
    if repo is None:
        return []
    from git_cg.eval.review_queue import ReviewQueueError, list_reviews, show_review

    items: list[dict[str, Any]] = []

    if review_ids:
        for rid in review_ids[:_MAX_ITEMS]:
            try:
                row = show_review(repo, review_id=str(rid))
            except ReviewQueueError:
                continue
            if isinstance(row, dict):
                item = _review_item(row)
                if item is not None:
                    items.append(item)
        return items

    listing = list_reviews(repo)
    reviews = listing.get("reviews") if isinstance(listing, dict) else []
    if not isinstance(reviews, list):
        return []
    for summary in reviews[:_MAX_ITEMS]:
        if not isinstance(summary, dict):
            continue
        rid = summary.get("review_id")
        if not isinstance(rid, str) or not rid:
            continue
        try:
            row = show_review(repo, review_id=rid)
        except ReviewQueueError:
            continue
        if isinstance(row, dict):
            item = _review_item(row)
            if item is not None:
                items.append(item)
    return items


def _scalar_meta(value: Any, *, max_len: int = 128) -> str | None:
    """Coerce projection metadata to a bounded scalar string (or None)."""
    if value is None:
        return None
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, (int, float)):
        text = str(value)
    elif isinstance(value, str):
        text = value.strip()
    else:
        return None
    if not text:
        return None
    if len(text) > max_len:
        text = text[:max_len]
    return text


def _projection_payload(item: Mapping[str, Any]) -> dict[str, Any]:
    """Metadata-only projection (no raw diffs or free-text dumps).

    Accepts a raw review-queue row or an already-normalised projection dict.
    Prefers nested ``review`` / ``adjudication`` fields; falls back to top-level keys.
    """
    review = item.get("review") if isinstance(item.get("review"), dict) else {}
    adjudication = item.get("adjudication") if isinstance(item.get("adjudication"), dict) else {}

    def _pick(*keys: str) -> Any:
        for key in keys:
            if key in review and review.get(key) is not None:
                return review.get(key)
            if key in adjudication and adjudication.get(key) is not None:
                return adjudication.get(key)
            if key in item and item.get(key) is not None:
                return item.get(key)
        return None

    projected = {
        "review_id": _scalar_meta(_pick("review_id", "id"), max_len=128),
        "status": _scalar_meta(_pick("status"), max_len=64),
        "case_id": _scalar_meta(_pick("case_id"), max_len=128),
        "bundle_id": _scalar_meta(_pick("bundle_id"), max_len=128),
        "authority": _scalar_meta(_pick("authority"), max_len=64) or "advisory",
        "outcome": _scalar_meta(_pick("outcome"), max_len=64),
        "updated_at": _scalar_meta(_pick("updated_at", "created_at"), max_len=64),
        "mirror_authority": QUEUE_MIRROR_AUTHORITY,
        "read_back": False,
    }
    cleaned = sanitize_export_tree(projected)
    return cleaned if isinstance(cleaned, dict) else projected


def _default_live_projector_factory() -> LiveQueueProjector:
    """Lazy Opik-backed projector (SDK import only inside factory/call)."""
    from git_cg.eval.mirror.secrets import ensure_secure_opik_endpoint, resolve_opik_secrets

    secrets = resolve_opik_secrets(require_key=True)
    # Re-check after resolve so injectable/monkeypatched secrets stay fail-closed.
    ensure_secure_opik_endpoint(base_url=secrets.base_url, api_key=secrets.api_key)

    import opik  # lazy; allowlisted import site

    class _OpikLiveProjector:
        def project_items(self, items: Sequence[Mapping[str, Any]], *, project: str) -> int:
            client = opik.Opik(
                project_name=project,
                workspace=secrets.workspace,
                host=secrets.base_url,
                api_key=secrets.api_key or None,
            )
            projected = 0
            for item in items:
                # Normalised payloads pass through; raw review rows are projected once.
                if isinstance(item, Mapping) and (
                    "mirror_authority" in item or ("review" not in item and "review_id" in item)
                ):
                    payload = dict(item)
                else:
                    payload = _projection_payload(item)
                # Sink-side bound/sanitize on every path.
                payload = {
                    k: (_scalar_meta(v) if k != "read_back" else bool(v))
                    for k, v in payload.items()
                    if k
                    in {
                        "review_id",
                        "status",
                        "case_id",
                        "bundle_id",
                        "authority",
                        "outcome",
                        "updated_at",
                        "mirror_authority",
                        "read_back",
                    }
                }
                payload["mirror_authority"] = QUEUE_MIRROR_AUTHORITY
                payload["read_back"] = False
                cleaned = sanitize_export_tree(payload)
                if isinstance(cleaned, dict):
                    payload = cleaned
                try:
                    client.trace(
                        name=f"review-queue:{payload.get('review_id')}",
                        input={"review_id": payload.get("review_id")},
                        metadata={k: v for k, v in payload.items() if v is not None},
                        tags=["git-cg", "review_queue", "advisory_non_sot"],
                    )
                    projected += 1
                except Exception:
                    continue
            try:
                flush = getattr(client, "flush", None)
                if callable(flush):
                    flush(timeout=2)
            except Exception:
                pass
            return projected

    return _OpikLiveProjector()


def project_review_queue_live(
    repo: Path | None = None,
    *,
    config: Mapping[str, Any] | None = None,
    review_ids: list[str] | None = None,
    enable_live: bool = False,
    projector: LiveQueueProjector | None = None,
    projector_factory: Callable[[], LiveQueueProjector] | None = None,
) -> QueueMirrorResult:
    """Optionally project local review rows to Opik (write-only, fail-open).

    Without ``enable_live`` / config ``queue_mirror_live``, returns the same
    offline status classification used by :func:`mirror_review_queue`.
    """
    offline = _offline_status(config)
    attempted_hint = len(review_ids) if review_ids else 0

    if offline in {"skipped_off", "noop_unconfigured"}:
        notes = {
            "skipped_off": "queue mirror skipped: mode off/local_only or unset",
            "noop_unconfigured": "queue mirror no-op: Opik project lanes unconfigured",
        }
        return QueueMirrorResult(
            status=offline,
            attempted=attempted_hint,
            skipped=attempted_hint,
            notes=(notes[offline],),
        )

    if not _live_enabled(config, enable_live=enable_live):
        return QueueMirrorResult(
            status="noop_unreachable",
            attempted=attempted_hint,
            skipped=attempted_hint,
            notes=("queue mirror no-op: live Opik projection not enabled (optional/NTH)",),
        )

    if not isinstance(config, Mapping):
        return QueueMirrorResult(
            status="noop_unconfigured",
            attempted=attempted_hint,
            skipped=attempted_hint,
            notes=("queue mirror no-op: Opik project lanes unconfigured",),
        )

    project = _eval_project(config)
    if not project:
        return QueueMirrorResult(
            status="noop_unconfigured",
            attempted=attempted_hint,
            skipped=attempted_hint,
            notes=("queue mirror no-op: Opik project lanes unconfigured",),
        )

    items = _load_local_items(repo, review_ids=review_ids)
    attempted = len(items)
    if attempted == 0:
        return QueueMirrorResult(
            status="projected",
            attempted=0,
            projected=0,
            skipped=0,
            notes=("live queue projection: no local review rows to project",),
        )

    active = projector
    if active is None:
        factory = projector_factory or _default_live_projector_factory
        try:
            active = factory()
        except Exception as exc:
            msg = scrub_export_note(f"live projector unavailable: {exc}")
            return QueueMirrorResult(
                status="noop_unreachable",
                attempted=attempted,
                skipped=attempted,
                notes=(msg,),
            )

    try:
        payloads = []
        for item in items:
            payload = _projection_payload(item)
            cleaned = sanitize_export_tree(payload)
            payloads.append(cleaned if isinstance(cleaned, dict) else payload)
        projected = int(active.project_items(payloads, project=project))
    except Exception as exc:
        msg = scrub_export_note(f"live projection failed: {exc}")
        return QueueMirrorResult(
            status="noop_unreachable",
            attempted=attempted,
            skipped=attempted,
            notes=(msg,),
        )

    projected = max(0, min(projected, attempted))
    skipped = max(0, attempted - projected)
    status: QueueMirrorStatus = "projected" if projected > 0 else "noop_unreachable"
    note = (
        f"live queue projection wrote {projected}/{attempted} rows (advisory_non_sot)"
        if status == "projected"
        else "live queue projection produced zero rows (treated as unreachable)"
    )
    return QueueMirrorResult(
        status=status,
        attempted=attempted,
        projected=projected,
        skipped=skipped,
        notes=(note,),
    )
