"""S6 Slice 7 operator train export engine (Issue #246 / R14 / §7.5).

Consumes the **landed** S4 train projection (``mirror.train``) + redaction
(``mirror.redaction``) and emits a governed ``train_export_v1`` document plus
per-row ``train_row_v1`` files under ``.eval/train_export/``.

Row scrub-failure policy (locked Slice 7 decision):
* Field-level quarantine stays S4 — fields that fail the scrubber are recorded
  under ``meta.redaction_quarantine`` (never emitted clear).
* If a **row** cannot be emitted secret-safe (e.g. the scrubber quarantines a
  required payload field, or redaction raises), the row is **dropped** from
  the export batch, recorded in the export ``scrub_report``
  (``status=quarantined|omitted`` with ids/reasons), and the export
  **continues**. No cleartext is ever emitted; there is **no**
  ``.eval/quarantine/`` store.

Safeguards:
* ``filter_positive_gold`` / ``build_train_projection`` dual-axis law is
  preserved — antipattern / hard-negative rows never silent-merge into
  ``positive_gold`` (S6-G06).
* Export is advisory/corpus-retention only — never CI sole green, never
  product-accept authority.

Import law: import-light. Path / schema / pin helpers are lazy.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

SCHEMA_VERSION: Final[str] = "train_export_v1"
ROW_SCHEMA: Final[str] = "train_row_v1"
DEFAULT_PROFILE: Final[str] = "train_rich"
DEFAULT_CAPTURE_ON: Final[str] = "all"

#: Redaction profiles permitted for operator train export (never raw_dev_unsafe).
EXPORT_PROFILES: Final[frozenset[str]] = frozenset(
    {
        "public_ci",
        "default_scrub",
        "private_message",
        "train_rich",
        "antipattern_vault",
        "message_only",
        "meta_eval_scrub",
    }
)

_SAFE_ID: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_CAPTURE_ON: Final[frozenset[str]] = frozenset({"pass", "fail", "all"})

#: train_label vocabulary surfaced on train_row_v1 (schema-closed).
ROW_LABELS: Final[frozenset[str]] = frozenset(
    {"positive", "hard_negative", "preference_chosen", "preference_rejected", "unlabeled"}
)


class TrainExportError(ValueError):
    """Deterministic train-export failure (fail-closed)."""

    def __init__(self, message: str, *, code: str, exit_code: int, hint: str | None = None) -> None:
        """Attach machine-readable ``code``, process ``exit_code``, and optional hint."""
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code
        self.hint = hint


def _utc_now() -> str:
    """Return the current UTC timestamp as an ISO-8601 Zulu string."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _train_export_dir(repo: Path) -> Path:
    """Resolve the governed ``.eval/train_export/`` directory for ``repo``."""
    from git_cg.eval.binding.paths import LayerAPathError, train_export_dir

    try:
        return train_export_dir(repo)
    except LayerAPathError as exc:
        raise TrainExportError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc


def _vault_dir(repo: Path) -> Path:
    """Resolve the governed antipattern vault directory for ``repo``."""
    from git_cg.eval.binding.paths import LayerAPathError, antipattern_vault_dir

    try:
        return antipattern_vault_dir(repo)
    except LayerAPathError as exc:
        raise TrainExportError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc


def _bundles_dir(repo: Path) -> Path:
    """Resolve the accept-path bundles directory for ``repo``."""
    from git_cg.eval.binding.paths import LayerAPathError, acceptpath_bundles_dir

    try:
        return acceptpath_bundles_dir(repo)
    except LayerAPathError as exc:
        raise TrainExportError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc


def _atomic_write(path: Path, payload: dict[str, Any]) -> Path:
    """Atomically write JSON through the Layer-A path helper (fail closed)."""
    from git_cg.eval.binding.paths import LayerAPathError, atomic_write_json

    try:
        return atomic_write_json(path, payload)
    except LayerAPathError as exc:
        raise TrainExportError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc


def _load_json(path: Path, *, code: str = "EVAL_STORE_INTEGRITY", exit_code: int = 4) -> dict[str, Any]:
    """Load a JSON object from ``path``; map I/O and decode failures to TrainExportError."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise TrainExportError(f"cannot read {path.name}: {exc}", code=code, exit_code=exit_code) from exc
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TrainExportError(f"{path.name} is not valid JSON: {exc}", code=code, exit_code=exit_code) from exc
    if not isinstance(obj, dict):
        raise TrainExportError(f"{path.name} must contain a JSON object", code=code, exit_code=exit_code)
    return obj


def _load_bundles(repo: Path, bundle_ids: list[str] | None) -> list[dict[str, Any]]:
    """Load accept-path bundles (all when ``bundle_ids`` is None)."""
    root = _bundles_dir(repo)
    if not root.is_dir():
        return []
    paths: list[Path]
    if bundle_ids is None:
        paths = sorted(root.glob("*.json"))
    else:
        paths = []
        for bid in bundle_ids:
            if not _SAFE_ID.fullmatch(bid):
                raise TrainExportError(f"invalid bundle id: {bid!r}", code="EVAL_USAGE", exit_code=2)
            path = root / f"{bid}.json"
            if not path.is_file():
                raise TrainExportError(
                    f"bundle not found: {bid!r}",
                    code="EVAL_USAGE",
                    exit_code=2,
                    hint="Pass a bundle id from .eval/bundles/acceptpath/.",
                )
            paths.append(path)
    return [_load_json(p) for p in paths]


def _row_label(bundle: Mapping[str, Any]) -> str | None:
    """Map bundle/train labels onto the train_row_v1 closed enum (bridge).

    S4 projector law is ``positive|negative``; the export row schema widens to
    the R14 vocabulary. Negatives/antipatterns map to ``hard_negative`` so they
    can never silent-merge into ``positive_gold``.
    """
    from git_cg.eval.mirror.train import normalize_train_label

    raw = (
        bundle.get("train_label")
        or (bundle.get("meta") or {}).get("train_label")
        or (bundle.get("meta") or {}).get("label")
        or bundle.get("label")
    )
    closed = normalize_train_label(raw)
    if closed == "positive":
        return "positive"
    if closed == "negative":
        return "hard_negative"
    return None  # unlabeled → excluded from export rows


def _project_row(
    redacted: dict[str, Any],
    *,
    label: str,
    export_profile: str,
) -> dict[str, Any]:
    """Project one redacted bundle into a schema-valid ``train_row_v1``."""
    from git_cg.eval.mirror.train import project_train_row

    proj = project_train_row(redacted)
    row_id = str(redacted.get("id") or redacted.get("bundle_id") or f"row-{uuid.uuid4().hex[:12]}")
    gate = redacted.get("gate") if isinstance(redacted.get("gate"), dict) else {}
    gate_pass = gate.get("deterministic_pass")
    row: dict[str, Any] = {
        "schema_version": ROW_SCHEMA,
        "id": row_id,
        "train_label": label,
        "redaction_profile": export_profile,
        "artifact_class": "train_row",
        "gate_pass": bool(gate_pass) if isinstance(gate_pass, bool) else False,
    }
    message = redacted.get("final_message")
    if isinstance(message, str) and message.strip():
        row["final_message"] = message
    split = None
    if proj is not None:
        split = proj.get("split_group_id") or proj.get("split")
    if split:
        row["split_group_id"] = str(split)
    quarantine = (redacted.get("meta") or {}).get("redaction_quarantine")
    if quarantine:
        row["scrub_report"] = {
            "status": "quarantined",
            "fields_quarantined": sorted(str(q) for q in quarantine),
            "fields_omitted": [],
            "notes": "field-level S4 quarantine carried on row (never emitted clear).",
        }
    from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin

    row["schema_pack"] = schema_pack_pin()
    row["metric_catalog"] = metric_catalog_pin()

    from git_cg.eval.evidence_scrub import project_secret_safe
    from git_cg.eval.schema_pack import SchemaPackError, validate_instance

    row = project_secret_safe(row)

    try:
        validate_instance(ROW_SCHEMA, row)
    except SchemaPackError as exc:
        raise TrainExportError(
            f"train_row_v1 validation failed: {exc}",
            code="EVAL_STORE_INTEGRITY",
            exit_code=4,
        ) from exc
    return row


def build_train_export(
    repo: Path,
    *,
    bundle_ids: list[str] | None = None,
    redaction_profile: str = DEFAULT_PROFILE,
    capture_on: str = DEFAULT_CAPTURE_ON,
    split_group_id: str | None = None,
    notes: str | None = None,
    export_id: str | None = None,
    redact_bundle: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Project → redact → row-policy → assemble a ``train_export_v1`` document.

    Row scrub-fail policy (locked): drop + report + continue; never cleartext;
    never ``.eval/quarantine/``.

    ``redact_bundle`` is an injectable seam for tests; production callers leave
    it ``None`` so the canonical export redactor is used.
    """
    if redaction_profile not in EXPORT_PROFILES:
        raise TrainExportError(
            f"invalid redaction profile for export: {redaction_profile!r}",
            code="EVAL_USAGE",
            exit_code=2,
            hint=f"Allowed: {'|'.join(sorted(EXPORT_PROFILES))} (raw_dev_unsafe is never an export profile).",
        )
    if capture_on not in _CAPTURE_ON:
        raise TrainExportError(f"invalid capture_on: {capture_on!r}", code="EVAL_USAGE", exit_code=2)

    bundles = _load_bundles(repo, bundle_ids)

    from git_cg.eval.mirror.redaction import RedactionError, redact_bundle_for_export
    from git_cg.eval.mirror.train import build_train_projection, filter_positive_gold

    redact = redact_bundle if redact_bundle is not None else redact_bundle_for_export

    rows: list[dict[str, Any]] = []
    row_ids: list[str] = []
    dropped: list[str] = []
    quarantined_fields: list[str] = []
    omitted_fields: list[str] = []
    scrub_status = "ok"

    for bundle in bundles:
        bundle_id = str(bundle.get("id") or bundle.get("session_thread_id") or "?")
        label = _row_label(bundle)
        if label is None:
            # Unlabeled rows are excluded (never silently positive).
            dropped.append(bundle_id)
            omitted_fields.append(f"{bundle_id}:train_label")
            continue
        # capture_on gate (corpus eligibility only; never product accept).
        gate = bundle.get("gate") if isinstance(bundle.get("gate"), dict) else {}
        gate_pass = gate.get("deterministic_pass")
        if capture_on == "pass" and gate_pass is False:
            dropped.append(bundle_id)
            continue
        try:
            redacted = redact(bundle, profile=redaction_profile)
        except RedactionError as exc:
            # Row cannot be emitted secret-safe → drop + report + continue.
            dropped.append(bundle_id)
            scrub_status = "quarantined"
            quarantined_fields.append(f"{bundle_id}:<row>")
            omitted_fields.append(f"{bundle_id}:<row> ({exc})")
            continue

        quarantine = (redacted.get("meta") or {}).get("redaction_quarantine") or []
        if quarantine:
            scrub_status = "quarantined"
            quarantined_fields.extend(f"{bundle_id}:{q}" for q in quarantine)

        try:
            row = _project_row(redacted, label=label, export_profile=redaction_profile)
        except TrainExportError:
            dropped.append(bundle_id)
            omitted_fields.append(f"{bundle_id}:<row_projection>")
            continue

        rows.append(row)
        row_ids.append(row["id"])

    # Dual-axis safeguard: positives never merge with negatives/antipatterns.
    projection = build_train_projection([dict(r, label=r["train_label"], bundle_id=r["id"]) for r in rows])
    positives = filter_positive_gold(projection["rows"])
    pos_ids = {r.get("bundle_id") for r in positives}
    for row in rows:
        if row["train_label"] == "hard_negative" and row["id"] in pos_ids:
            raise TrainExportError(
                f"antipattern/hard_negative row {row['id']!r} would enter positive_gold",
                code="EVAL_STORE_INTEGRITY",
                exit_code=4,
                hint="S6-G06: antipattern rows never silently join positive_gold.",
            )

    eid = export_id or f"export-{uuid.uuid4().hex[:12]}"
    if not _SAFE_ID.fullmatch(eid):
        raise TrainExportError(f"invalid export_id: {eid!r}", code="EVAL_USAGE", exit_code=2)

    if dropped and scrub_status == "ok":
        scrub_status = "omitted"

    from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin

    export: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "id": eid,
        "export_id": eid,
        "redaction_profile": redaction_profile,
        "capture_on": capture_on,
        "row_ids": row_ids,
        "schema_pack": schema_pack_pin(),
        "metric_catalog": metric_catalog_pin(),
    }
    if split_group_id:
        export["split_group_id"] = split_group_id
    if notes:
        from git_cg.eval.evidence_scrub import mask_secrets_in_text

        export["notes"] = mask_secrets_in_text(notes) or notes
    scrub_report: dict[str, Any] = {"status": scrub_status}
    if quarantined_fields:
        scrub_report["fields_quarantined"] = sorted(set(quarantined_fields))
    if omitted_fields:
        scrub_report["fields_omitted"] = sorted(set(omitted_fields))
    if dropped:
        scrub_report["notes"] = f"dropped {len(dropped)} row(s); export continued (Slice 7 row policy)."
    if scrub_report["status"] != "ok" or dropped:
        export["scrub_report"] = scrub_report
    if any(r["train_label"] == "hard_negative" for r in rows):
        export["vault_destination"] = "antipattern_vault"

    from git_cg.eval.schema_pack import SchemaPackError, validate_instance

    try:
        validate_instance(SCHEMA_VERSION, export)
    except SchemaPackError as exc:
        raise TrainExportError(
            f"train_export_v1 validation failed: {exc}",
            code="EVAL_STORE_INTEGRITY",
            exit_code=4,
        ) from exc

    from git_cg.eval.evidence_scrub import project_secret_safe

    return project_secret_safe(
        {
            "export": export,
            "rows": rows,
            "row_ids": row_ids,
            "dropped_row_ids": dropped,
            "scrub_report": export.get("scrub_report", {"status": "ok"}),
            "positive_gold_count": len(positives),
            "negative_count": len(projection["negatives"]),
            "excluded_unlabeled": projection["excluded_unlabeled"],
        }
    )


def write_train_export(
    repo: Path,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Persist the export doc + rows; route hard-negatives to the vault copy."""
    export = result["export"]
    rows = result["rows"]
    eid = str(export["export_id"])

    export_root = _train_export_dir(repo)
    export_path = export_root / f"{eid}.json"
    _atomic_write(export_path, {k: v for k, v in export.items() if v is not None})

    rows_dir = export_root / eid
    written_rows: list[str] = []
    for row in rows:
        rid = str(row["id"])
        row_path = rows_dir / f"{rid}.json"
        _atomic_write(row_path, {k: v for k, v in row.items() if v is not None})
        written_rows.append(row_path.as_posix())

    vault_paths: list[str] = []
    if export.get("vault_destination") == "antipattern_vault":
        vault = _vault_dir(repo) / eid
        for row in rows:
            if row["train_label"] == "hard_negative":
                vp = vault / f"{row['id']}.json"
                _atomic_write(vp, {k: v for k, v in row.items() if v is not None})
                vault_paths.append(vp.as_posix())

    return {
        "export_path": export_path.as_posix(),
        "row_paths": written_rows,
        "vault_paths": vault_paths,
        "row_count": len(written_rows),
    }


def train_export(
    repo: Path,
    *,
    bundle_ids: list[str] | None = None,
    redaction_profile: str = DEFAULT_PROFILE,
    capture_on: str = DEFAULT_CAPTURE_ON,
    split_group_id: str | None = None,
    notes: str | None = None,
    write: bool = True,
    dry_run: bool | None = None,
) -> dict[str, Any]:
    """Build + (optionally) persist a train export; return CLI data payload.

    ``dry_run=True`` is the NTH-03 alias for ``write=False``: fully build and
    validate the export projection without mutating the train-export store.
    When both are provided, ``dry_run=True`` wins (forces no write).
    """
    if dry_run is True:
        write = False
    result = build_train_export(
        repo,
        bundle_ids=bundle_ids,
        redaction_profile=redaction_profile,
        capture_on=capture_on,
        split_group_id=split_group_id,
        notes=notes,
    )
    persisted = write_train_export(repo, result) if write else None
    dry = not write
    would_write = None
    if dry:
        eid = str(result["export"]["export_id"])
        export_root = _train_export_dir(repo)
        would_write = {
            "export_path": (export_root / f"{eid}.json").as_posix(),
            "rows_dir": (export_root / eid).as_posix(),
            "row_count": len(result["row_ids"]),
            "export_id": eid,
        }
    return {
        "export": result["export"],
        "export_id": result["export"]["export_id"],
        "row_ids": result["row_ids"],
        "row_count": len(result["row_ids"]),
        "dropped_row_ids": result["dropped_row_ids"],
        "scrub_report": result["scrub_report"],
        "positive_gold_count": result["positive_gold_count"],
        "negative_count": result["negative_count"],
        "excluded_unlabeled": result["excluded_unlabeled"],
        "written": persisted is not None,
        "paths": persisted,
        "authority": "corpus_retention",
        "ci_sole_green": False,
        "product_accept_authority": False,
        "dry_run": dry,
        "would_write": would_write,
    }


__all__ = [
    "EXPORT_PROFILES",
    "ROW_LABELS",
    "SCHEMA_VERSION",
    "TrainExportError",
    "build_train_export",
    "train_export",
    "write_train_export",
]
