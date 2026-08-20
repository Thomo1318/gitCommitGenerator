"""Lane C' R5 dirty-overlay provenance guard.

Dirty overlays (prompt/model/param lab overlays) are research-only. They must
never ride accept-path, hooks, or CI green paths. When an overlay path is
explicitly supplied, this module:

* requires lab-only mode
* stamps dirty provenance metadata
* rejects accept-path / CI / green-path contexts
* never exports raw overlay file contents

If no overlay path is supplied, callers may treat R5 as inactive. The existence
criterion for committed overlays is :func:`overlays_exist_in_tree`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from git_cg.eval.evidence_scrub import scrub_evidence_mapping
from git_cg.eval.paths import REPO_ROOT

__all__ = [
    "DEFAULT_OVERLAY_DIR",
    "DIRTY_PROVENANCE_LABEL",
    "DirtyOverlayError",
    "DirtyOverlayProvenance",
    "activate_dirty_overlay",
    "assert_overlay_not_on_green_path",
    "overlays_exist_in_tree",
    "stamp_dirty_provenance",
]

DEFAULT_OVERLAY_DIR: Final = REPO_ROOT / ".eval" / "overlays"
DIRTY_PROVENANCE_LABEL: Final = "config_dirty_overlay"


class DirtyOverlayError(ValueError):
    """Dirty-overlay activation or green-path violation."""


@dataclass(frozen=True, slots=True)
class DirtyOverlayProvenance:
    """Secret-free dirty overlay stamp (no raw overlay body)."""

    active: bool
    lab_only: bool
    overlay_path: str | None
    overlay_name: str | None
    provenance: str
    accept_path_forbidden: bool = True
    ci_green_forbidden: bool = True
    hooks_forbidden: bool = True
    product_authority: None = None
    diagnostic_only: bool = True
    non_gating: bool = True

    def as_dict(self) -> dict[str, Any]:
        """JSON-friendly provenance stamp."""
        return {
            "active": self.active,
            "lab_only": self.lab_only,
            "overlay_path": self.overlay_path,
            "overlay_name": self.overlay_name,
            "provenance": self.provenance,
            "accept_path_forbidden": self.accept_path_forbidden,
            "ci_green_forbidden": self.ci_green_forbidden,
            "hooks_forbidden": self.hooks_forbidden,
            "product_authority": self.product_authority,
            "diagnostic_only": self.diagnostic_only,
            "non_gating": self.non_gating,
            "residual": "R5",
            "raw_overlay_exported": False,
        }


def overlays_exist_in_tree(*, root: Path | None = None) -> bool:
    """D19 existence test: committed ``.eval/overlays/`` content present?"""
    base = (root or REPO_ROOT) / ".eval" / "overlays"
    if not base.is_dir():
        return False
    try:
        for path in base.rglob("*"):
            if path.is_file() and not path.name.startswith("."):
                return True
    except OSError:
        return False
    return False


def stamp_dirty_provenance(
    *,
    overlay_path: str | Path | None,
    lab_only: bool = True,
) -> DirtyOverlayProvenance:
    """Build a dirty provenance stamp without reading overlay contents."""
    if overlay_path is None:
        return DirtyOverlayProvenance(
            active=False,
            lab_only=True,
            overlay_path=None,
            overlay_name=None,
            provenance="clean",
        )
    if not lab_only:
        raise DirtyOverlayError("dirty overlay stamp requires lab_only=True when overlay_path is set")
    path = Path(overlay_path)
    name = path.name or "overlay"
    # Never retain absolute host paths beyond basename for export safety.
    safe_path = name
    return DirtyOverlayProvenance(
        active=True,
        lab_only=bool(lab_only),
        overlay_path=safe_path,
        overlay_name=name,
        provenance=DIRTY_PROVENANCE_LABEL,
    )


def assert_overlay_not_on_green_path(
    *,
    accept_path: bool = False,
    ci_green: bool = False,
    hooks: bool = False,
    context: Mapping[str, Any] | None = None,
) -> None:
    """Fail closed when dirty overlays would touch green/accept/hook contexts."""
    ctx = context or {}
    flagged = accept_path or ci_green or hooks
    # Also honor explicit context keys.
    for key in ("accept_path", "ci_green", "hooks", "golden_promotion", "first_ci"):
        val = ctx.get(key)
        if val is True:
            flagged = True
    if flagged:
        raise DirtyOverlayError("dirty overlays are lab-only and forbidden on accept-path/hooks/CI green paths")


def activate_dirty_overlay(
    overlay_path: str | Path,
    *,
    lab_only: bool = False,
    accept_path: bool = False,
    ci_green: bool = False,
    hooks: bool = False,
    context: Mapping[str, Any] | None = None,
    require_exists: bool = True,
) -> DirtyOverlayProvenance:
    """Activate a dirty overlay under lab-only constraints.

    Does **not** load or return overlay file bytes — only provenance metadata.
    """
    if not lab_only:
        raise DirtyOverlayError("dirty overlay activation requires lab_only=True")
    assert_overlay_not_on_green_path(
        accept_path=accept_path,
        ci_green=ci_green,
        hooks=hooks,
        context=context,
    )
    path = Path(overlay_path)
    if require_exists and not path.exists():
        raise DirtyOverlayError(f"overlay path does not exist: {path.name}")
    stamp = stamp_dirty_provenance(overlay_path=path, lab_only=True)
    # Scrub any accidental rich context keys if callers attach later.
    _ = scrub_evidence_mapping(stamp.as_dict())
    return stamp
