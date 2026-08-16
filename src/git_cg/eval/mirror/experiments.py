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

__all__ = ["build_experiment", "experiment_name", "resolve_git_sha"]

#: Name must be filesystem/URL safe and stable.
_NAME_SAFE = re.compile(r"[^a-z0-9_]+")


def _slug(token: str) -> str:
    return _NAME_SAFE.sub("_", token.strip().lower()).strip("_") or "unknown"


#: Fallback when the git SHA cannot be resolved. Must satisfy the schema
#: ``^[a-f0-9]{7,64}$`` — a zeroed SHA is the honest "unresolvable" sentinel.
_UNRESOLVED_SHA = "0" * 40


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
    except OSError, subprocess.SubprocessError:
        return _UNRESOLVED_SHA
    if proc.returncode != 0:
        return _UNRESOLVED_SHA
    return proc.stdout.strip() or _UNRESOLVED_SHA


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
) -> dict[str, Any]:
    """Build a schema-valid ``experiment_v1`` pin record.

    ``git_sha`` defaults to the live repo HEAD (best-effort). The record is
    validated against the frozen schema before return (fail closed).
    """
    sha = git_sha or resolve_git_sha()
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
