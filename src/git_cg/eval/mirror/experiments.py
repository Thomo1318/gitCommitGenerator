"""``experiment_v1`` naming + pin record (plan §7.2, §8.4 deliverable 3).

Experiment names follow the locked convention::

    eval_<lane>_<catalog_version>_<gitsha>_<utc>

Every record carries the full pin set (``schema_pack`` + ``metric_catalog``
content pins + ``git_sha``) so an export is reproducible against the frozen
floor. Pure offline builder — no network, no Opik.
"""

from __future__ import annotations

import re
import subprocess
from datetime import UTC, datetime
from typing import Any

from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin
from git_cg.eval.schema_pack import validate_instance

__all__ = [
    "UNRESOLVED_GIT_SHA",
    "ExportGitShaError",
    "build_experiment",
    "experiment_name",
    "is_unresolved_git_sha",
    "require_resolved_git_sha",
    "resolve_git_sha",
]

#: Name must be filesystem/URL safe and stable.
_NAME_SAFE = re.compile(r"[^a-z0-9_]+")


def _slug(token: str) -> str:
    return _NAME_SAFE.sub("_", token.strip().lower()).strip("_") or "unknown"


#: Fallback when the git SHA cannot be resolved. Must satisfy the schema
#: ``^[a-f0-9]{7,64}$`` — a zeroed SHA is the honest "unresolvable" sentinel.
#: Allowed for local/offline diagnostics only (P1-12); network export must fail
#: closed before enqueue when this sentinel is present.
UNRESOLVED_GIT_SHA = "0" * 40

# Back-compat private alias used by existing tests/callers.
_UNRESOLVED_SHA = UNRESOLVED_GIT_SHA

# OSError + SubprocessError → zeroed SHA sentinel (never raises).
# Named tuple keeps the catch set explicit under ruff/py314 format,
# which rewrites bare `except (A, B)` into comma form.
_RESOLVE_GIT_SHA_ERRORS = (OSError, subprocess.SubprocessError)


class ExportGitShaError(ValueError):
    """Unresolved git SHA refused on a network-export path (``export_validation``)."""

    def __init__(self, message: str, *, error_class: str = "export_validation") -> None:
        self.error_class = error_class
        super().__init__(message)


def is_unresolved_git_sha(git_sha: str | None) -> bool:
    """True when ``git_sha`` is missing or the zeroed unresolvable sentinel."""
    sha = str(git_sha or "").strip().lower()
    return not sha or sha == UNRESOLVED_GIT_SHA or set(sha) == {"0"}


def require_resolved_git_sha(
    git_sha: str | None = None,
    *,
    repo_root: Any | None = None,
    network_export: bool = True,
) -> str:
    """Return a resolved git SHA, or fail closed for network export (P1-12).

    Local/offline diagnostics may still call :func:`resolve_git_sha` directly
    and accept the zeroed sentinel. Any network-export path must call this
    helper (or pass ``network_export=True`` at enqueue) so unresolved identity
    never reaches the queue.
    """
    sha = str(git_sha).strip() if git_sha is not None else resolve_git_sha(repo_root=repo_root)
    if network_export and is_unresolved_git_sha(sha):
        raise ExportGitShaError(
            "unresolved git SHA refused for network export (export_validation); zeroed identity is local/diag only",
            error_class="export_validation",
        )
    return sha


def resolve_git_sha(repo_root: Any | None = None) -> str:
    """Best-effort short git SHA; zeroed SHA when unresolvable (never raises)."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=str(repo_root) if repo_root is not None else None,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except _RESOLVE_GIT_SHA_ERRORS:
        return UNRESOLVED_GIT_SHA
    if proc.returncode != 0:
        return UNRESOLVED_GIT_SHA
    return proc.stdout.strip() or UNRESOLVED_GIT_SHA


def experiment_name(
    lane: str,
    catalog_version: str,
    git_sha: str,
    when: datetime | None = None,
) -> str:
    """Return ``eval_<lane>_<catalog_version>_<gitsha>_<utc>``.

    ``git_sha`` is used verbatim (it is already hex); only lane/catalog are
    slugged.
    """
    stamp = (when or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    return f"eval_{_slug(lane)}_{_slug(catalog_version)}_{git_sha}_{stamp}"


def build_experiment(
    lane: str,
    catalog_version: str = "v0",
    *,
    git_sha: str | None = None,
    when: datetime | None = None,
    meta: dict[str, Any] | None = None,
    network_export: bool = False,
    repo_root: Any | None = None,
) -> dict[str, Any]:
    """Build a schema-valid ``experiment_v1`` pin record.

    ``git_sha`` defaults to the live repo HEAD (best-effort). When
    ``network_export=True``, an unresolved SHA fails closed as
    ``export_validation`` (P1-12) instead of baking the zeroed sentinel into
    a network-bound identity. The record is validated against the frozen
    schema before return (fail closed).
    """
    if git_sha is None:
        sha = require_resolved_git_sha(repo_root=repo_root, network_export=network_export)
    else:
        sha = require_resolved_git_sha(git_sha, network_export=network_export)
    name = experiment_name(lane, catalog_version, sha, when)
    record: dict[str, Any] = {
        "schema_version": "experiment_v1",
        "id": name,
        "experiment_name": name,
        "lane": lane,
        "git_sha": sha,
        "catalog_pin": metric_catalog_pin(),
        "schema_pack": schema_pack_pin(),
        "metric_catalog": metric_catalog_pin(),
    }
    if meta:
        record["meta"] = dict(meta)

    # Fail closed: the record we claim must validate against the frozen schema.
    validate_instance("experiment_v1", record)
    return record
