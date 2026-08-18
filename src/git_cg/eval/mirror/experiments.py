"""``experiment_v1`` naming + pin record (plan §7.2, §8.4 / P1-1 / P2-5 / P2-6).

Experiment names follow the locked convention::

    eval_<lane>_<catalog_version>_<gitsha>_<utc>

Every record carries the full pin set (``schema_pack`` + ``metric_catalog``
content pins + ``git_sha`` + typed :class:`ExperimentPins`) so an export is
reproducible against the frozen floor. Pure offline builder — no network, no
Opik.

P2-5: when two builds share the same UTC second, a deterministic content
suffix derived from identity inputs prevents name collisions without relying
on ambient clocks.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tomllib
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin
from git_cg.eval.schema_pack import validate_instance

__all__ = [
    "UNRESOLVED_GIT_SHA",
    "ExperimentPins",
    "ExportGitShaError",
    "build_experiment",
    "build_experiment_pins",
    "experiment_name",
    "is_unresolved_git_sha",
    "require_resolved_git_sha",
    "resolve_git_sha",
]

#: Name must be filesystem/URL safe and stable.
_NAME_SAFE = re.compile(r"[^a-z0-9_]+")

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

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[4]
_PYPROJECT: Final[Path] = _REPO_ROOT / "pyproject.toml"


def _slug(token: str) -> str:
    """Create a filesystem-safe lowercase slug from a text token."""
    return _NAME_SAFE.sub("_", token.strip().lower()).strip("_") or "unknown"


def _harness_version() -> str:
    """
    Determine the package version used for experiment pins.
    
    Returns:
    	str: The package version, or ``"0.0.0"`` when the version cannot be read or is unavailable.
    """
    try:
        data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    except OSError, tomllib.TOMLDecodeError, AttributeError:
        return "0.0.0"
    project = data.get("project") if isinstance(data, dict) else None
    if not isinstance(project, dict):
        return "0.0.0"
    version = str(project.get("version") or "").strip()
    return version or "0.0.0"


@dataclass(frozen=True, slots=True)
class ExperimentPins:
    """Full D15 pin set. Use explicit ``None`` for N/A — never silent omit (P2-6)."""

    harness_version: str | None
    schema_pack: str | None
    metric_catalog: str | None
    catalog_version: str | None
    git_sha: str | None
    lane: str | None
    environment: str | None
    project: str | None
    project_lane: str | None
    dataset_id: str | None
    suite_snapshot: str | None
    prompt_pack_hash: str | None
    engine: str | None
    model: str | None
    artifact_class: str | None
    redaction_profile: str | None

    def to_dict(self) -> dict[str, Any]:
        """Serialize with explicit nulls for absent optional pins."""
        return asdict(self)


def build_experiment_pins(
    *,
    lane: str,
    catalog_version: str = "v0",
    git_sha: str | None = None,
    environment: str | None = None,
    project: str | None = None,
    project_lane: str | None = None,
    dataset_id: str | None = None,
    suite_snapshot: str | None = None,
    prompt_pack_hash: str | None = None,
    engine: str | None = None,
    model: str | None = None,
    artifact_class: str | None = "export_batch",
    redaction_profile: str | None = None,
    harness_version: str | None = None,
    schema_pack: str | None = None,
    metric_catalog: str | None = None,
) -> ExperimentPins:
    """
    Build the complete set of metadata pins for an experiment record.
    
    Parameters:
    	lane (str): Evaluation lane associated with the experiment.
    	catalog_version (str): Version of the metric catalogue used by the experiment.
    	git_sha (str | None): Git commit identifier associated with the experiment.
    	project_lane (str | None): Project-specific lane; defaults to the evaluation lane when omitted.
    
    Returns:
    	ExperimentPins: Immutable pin set with explicit values for all supported fields.
    """
    return ExperimentPins(
        harness_version=harness_version if harness_version is not None else _harness_version(),
        schema_pack=schema_pack if schema_pack is not None else schema_pack_pin(),
        metric_catalog=metric_catalog if metric_catalog is not None else metric_catalog_pin(),
        catalog_version=catalog_version,
        git_sha=git_sha,
        lane=lane,
        environment=environment,
        project=project,
        project_lane=project_lane or project,
        dataset_id=dataset_id,
        suite_snapshot=suite_snapshot,
        prompt_pack_hash=prompt_pack_hash,
        engine=engine,
        model=model,
        artifact_class=artifact_class,
        redaction_profile=redaction_profile,
    )


class ExportGitShaError(ValueError):
    """Unresolved git SHA refused on a network-export path (``export_validation``)."""

    def __init__(self, message: str, *, error_class: str = "export_validation") -> None:
        """
        Initialise an error raised when a Git SHA cannot be resolved for export.
        
        Parameters:
        	message (str): Description of the export error.
        	error_class (str): Classification of the error.
        """
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
    """
    Ensure a Git SHA is suitable for the requested export context.
    
    Parameters:
    	git_sha (str | None): Git SHA to validate, or ``None`` to resolve it from
    		the repository.
    	repo_root (Any | None): Repository location used when resolving the SHA.
    	network_export (bool): Whether unresolved Git identity should be rejected.
    
    Returns:
    	str: The supplied or resolved Git SHA.
    
    Raises:
    	ExportGitShaError: If ``network_export`` is ``True`` and the Git SHA is
    		unresolved.
    """
    sha = str(git_sha).strip() if git_sha is not None else resolve_git_sha(repo_root=repo_root)
    if network_export and is_unresolved_git_sha(sha):
        raise ExportGitShaError(
            "unresolved git SHA refused for network export (export_validation); zeroed identity is local/diag only",
            error_class="export_validation",
        )
    return sha


def resolve_git_sha(repo_root: Any | None = None) -> str:
    """
    Resolve the current repository's Git commit identifier.
    
    Parameters:
    	repo_root (Any | None): Optional repository directory in which to resolve the commit.
    
    Returns:
    	str: The abbreviated Git SHA, or a 40-zero sentinel when the SHA cannot be resolved.
    """
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


def _collision_suffix(
    *,
    lane: str,
    catalog_version: str,
    git_sha: str,
    stamp: str,
    content_key: str | None,
) -> str:
    """
    Create a deterministic eight-character suffix for experiment name collisions.
    
    Parameters:
        lane (str): Experiment lane.
        catalog_version (str): Metric catalog version.
        git_sha (str): Git commit identifier.
        stamp (str): Timestamp component of the experiment name.
        content_key (str | None): Optional content key used to derive the suffix.
    
    Returns:
        str: The first eight hexadecimal characters of the content key or derived hash.
    """
    if content_key:
        token = content_key.strip().lower()
        if token and re.fullmatch(r"[a-f0-9]+", token) and len(token) >= 8:
            return token[:8]
        return hashlib.sha256(content_key.encode("utf-8")).hexdigest()[:8]
    material = json.dumps(
        {
            "catalog_version": catalog_version,
            "git_sha": git_sha,
            "lane": lane,
            "stamp": stamp,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:8]


def experiment_name(
    lane: str,
    catalog_version: str,
    git_sha: str,
    when: datetime | None = None,
    *,
    content_key: str | None = None,
    collide_guard: bool = False,
) -> str:
    """
    Constructs a deterministic experiment name from its lane, catalog version, Git SHA, and timestamp.
    
    Parameters:
    	lane (str): Experiment lane included in the name.
    	catalog_version (str): Catalog version included in the name.
    	git_sha (str): Git commit identifier included in the name.
    	when (datetime | None): Timestamp to include; uses the current UTC time when omitted.
    	content_key (str | None): Content identity used to derive the collision suffix.
    	collide_guard (bool): Whether to append a deterministic suffix for collision resistance.
    
    Returns:
    	str: An experiment name in the form `eval_<lane>_<catalog_version>_<gitsha>_<utc>`, optionally with a collision suffix.
    """
    stamp = (when or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    base = f"eval_{_slug(lane)}_{_slug(catalog_version)}_{git_sha}_{stamp}"
    if not collide_guard:
        return base
    return f"{base}_{_collision_suffix(lane=lane, catalog_version=catalog_version, git_sha=git_sha, stamp=stamp, content_key=content_key)}"


def build_experiment(
    lane: str,
    catalog_version: str = "v0",
    *,
    git_sha: str | None = None,
    when: datetime | None = None,
    meta: dict[str, Any] | None = None,
    network_export: bool = False,
    repo_root: Any | None = None,
    environment: str | None = None,
    project: str | None = None,
    project_lane: str | None = None,
    dataset_id: str | None = None,
    suite_snapshot: str | None = None,
    prompt_pack_hash: str | None = None,
    engine: str | None = None,
    model: str | None = None,
    artifact_class: str | None = "export_batch",
    redaction_profile: str | None = None,
    content_key: str | None = None,
    collide_guard: bool = True,
) -> dict[str, Any]:
    """
    Build a schema-valid ``experiment_v1`` experiment record with complete pin metadata.
    
    Parameters:
    	lane (str): Evaluation lane used in the experiment identity.
    	catalog_version (str): Metric catalogue version to pin.
    	git_sha (str | None): Git commit identifier; resolved from the repository when omitted.
    	network_export (bool): Whether unresolved Git identities must be rejected.
    	meta (dict[str, Any] | None): Additional metadata merged into the record.
    	content_key (str | None): Key used to generate a deterministic collision suffix.
    
    Returns:
    	dict[str, Any]: The validated ``experiment_v1`` record.
    """
    if git_sha is None:
        sha = require_resolved_git_sha(repo_root=repo_root, network_export=network_export)
    else:
        sha = require_resolved_git_sha(git_sha, network_export=network_export)

    pins = build_experiment_pins(
        lane=lane,
        catalog_version=catalog_version,
        git_sha=sha,
        environment=environment,
        project=project,
        project_lane=project_lane,
        dataset_id=dataset_id,
        suite_snapshot=suite_snapshot,
        prompt_pack_hash=prompt_pack_hash,
        engine=engine,
        model=model,
        artifact_class=artifact_class,
        redaction_profile=redaction_profile,
    )
    # Prefer idempotency/content key when provided; else hash the pin set so
    # same-second builds with different pins still diverge (P2-5).
    suffix_key = content_key or json.dumps(pins.to_dict(), sort_keys=True, separators=(",", ":"), default=str)
    name = experiment_name(
        lane,
        catalog_version,
        sha,
        when,
        content_key=suffix_key,
        collide_guard=collide_guard,
    )
    record: dict[str, Any] = {
        "schema_version": "experiment_v1",
        "id": name,
        "experiment_name": name,
        "lane": lane,
        "git_sha": sha,
        "catalog_pin": pins.metric_catalog,
        "schema_pack": pins.schema_pack,
        "metric_catalog": pins.metric_catalog,
        "meta": {
            "pins": pins.to_dict(),
        },
    }
    if meta:
        # Caller meta is additive; pins remain authoritative under meta.pins.
        merged = dict(meta)
        merged.setdefault("pins", pins.to_dict())
        record["meta"] = merged

    # Fail closed: the record we claim must validate against the frozen schema.
    validate_instance("experiment_v1", record)
    return record
