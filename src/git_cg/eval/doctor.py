"""S6 Slice 4 offline doctors (Issue #246).

Two distinct, network-free operator surfaces:

* :func:`run_local_doctor` — ``git-cg eval doctor``: local suite / fixture /
  schema-pin / metric-catalog / prompt-pack consistency doctor. Fail-closed on
  unpinned ``latest`` identities and missing catalog/schema hashes. Emits the
  phantom-metric producers ``h.compat_hash_resume``, ``h.doctor_green``, and
  ``h.export_config_resolved`` as catalog-aligned ``ScoreResultV1`` rows.
* :func:`run_opik_doctor` — ``git-cg eval opik doctor``: secret-safe Opik /
  export / queue health inspection. No transport, no network, no raw token
  values or prefixes (``mask_secret()`` only).

Doctor is observability-only. It never mutates product accept, ranking, golden
promotion, or Families A-I authority. ``h.doctor_green`` aggregates
**block-severity** checks only; warn-severity failures never flip green to red.

Import law: this module is import-light. Heavy helpers (scoring, mirror,
prompt-pack, checkpoint store) are imported lazily inside functions so the CLI
import graph stays clean and offline tests never touch the network or Opik SDK.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

# Closed check status vocabulary (doctor report contract, plan §S6-C).
STATUS_PASS: Final[str] = "pass"
STATUS_WARN: Final[str] = "warn"
STATUS_FAIL: Final[str] = "fail"

_DOCTOR_STATUSES: Final[tuple[str, ...]] = (STATUS_PASS, STATUS_WARN, STATUS_FAIL)

# Catalog-aligned severities used by the doctor checks.
SEVERITY_BLOCK: Final[str] = "block"
SEVERITY_WARN: Final[str] = "warn"

# ``name@<64-hex>`` pin shape; ``latest`` (or any non-hex suffix) is floating.
_PIN_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9_]+@[0-9a-f]{64}$")

# Deterministic remediation hints (closed copy map; never model output).
# Failure-class hints include static offline deep-links to `eval explain` /
# `eval failures` (NTH-01 / Slice 4 L742). Never Ollie/LLM RCA.
_DEEP_LINK_EXPLAIN: Final[str] = "git-cg eval explain --experiment-id <experiment-id> --case <case-id>"
_DEEP_LINK_FAILURES: Final[str] = "git-cg eval failures --experiment-id <experiment-id>"
_DEEP_LINKS: Final[str] = f"Deep-links: `{_DEEP_LINK_EXPLAIN}`; `{_DEEP_LINK_FAILURES}`."

_HINTS: Final[dict[str, str]] = {
    "EVAL_PIN_FLOATING": (
        f"Freeze the catalog/schema pack to a content pin; never run eval on 'latest'. {_DEEP_LINKS}"
    ),
    "EVAL_SUITE_PIN_MISMATCH": (
        f"Re-pin the suite to the live schema/catalog pins and rebuild the snapshot. {_DEEP_LINKS}"
    ),
    "EVAL_INPUT_EMPTY": (
        f"FIND-026: bind a non-empty scored artifact (final_message or product/score card). {_DEEP_LINKS}"
    ),
    "EVAL_INPUT_OVERSIZE": (f"FIND-026: reduce the scored artifact below the eval byte budget. {_DEEP_LINKS}"),
    "EVAL_COMPAT_HASH_MISMATCH": (
        f"Recover with `git-cg eval run` (fresh) or `git-cg eval recompute-scores`. {_DEEP_LINKS}"
    ),
    "EVAL_PROMPT_PACK_DRIFT": (f"FIND-028: re-pin the suite snapshot against the current prompt pack. {_DEEP_LINKS}"),
    "EVAL_CONFIG_ERROR": (f"Resolve Opik mode/projects; see `git-cg eval opik config show`. {_DEEP_LINKS}"),
}


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    """One machine-readable doctor check row (plan §S6-C report contract).

    ``metric_id`` is optional: checks that back a phantom metric producer carry
    it; pure structural checks (pin format, fixture load) may omit it.
    """

    check_id: str
    status: str
    severity: str
    message: str
    metric_id: str | None = None
    hint: str | None = None

    def __post_init__(self) -> None:
        """Validate dataclass invariants after initialization."""
        if self.status not in _DOCTOR_STATUSES:
            raise ValueError(f"doctor check status must be one of {_DOCTOR_STATUSES}: {self.status!r}")
        if not self.check_id.strip():
            raise ValueError("doctor check_id must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        """Serialize one doctor check row for envelope and report output."""
        out: dict[str, Any] = {
            "check_id": self.check_id,
            "status": self.status,
            "severity": self.severity,
            "message": self.message,
        }
        if self.metric_id is not None:
            out["metric_id"] = self.metric_id
        if self.hint is not None:
            out["hint"] = self.hint
        return out


@dataclass(frozen=True, slots=True)
class DoctorReport:
    """Aggregated doctor result: checks + phantom-metric score rows.

    ``green`` is the ``h.doctor_green`` rollup: True unless a **block-severity**
    check failed. Warn-severity failures never affect ``green``.
    """

    green: bool
    checks: tuple[DoctorCheck, ...]
    scores: tuple[Any, ...] = field(default_factory=tuple)  # ScoreResultV1 rows
    suite_id: str | None = None
    exit_code: int = 0
    extra: dict[str, Any] = field(default_factory=dict)  # command-specific payload

    def to_data(self) -> dict[str, Any]:
        """Envelope ``data`` payload (machine-readable)."""
        out: dict[str, Any] = {
            "green": self.green,
            "exit_code": self.exit_code,
            "suite_id": self.suite_id,
            "checks": [c.to_dict() for c in self.checks],
            "scores": [s.model_dump(mode="json") for s in self.scores],
            "block_failures": [
                c.check_id for c in self.checks if c.severity == SEVERITY_BLOCK and c.status == STATUS_FAIL
            ],
            "warn_failures": [
                c.check_id for c in self.checks if c.severity == SEVERITY_WARN and c.status == STATUS_FAIL
            ],
        }
        out.update(self.extra)
        return out


# --------------------------------------------------------------------------
# Internal helpers
# --------------------------------------------------------------------------


def _is_pinned(pin: Any) -> bool:
    """True when ``pin`` is a well-formed content pin (not floating/latest)."""
    return isinstance(pin, str) and bool(_PIN_RE.fullmatch(pin.strip()))


def _check(
    check_id: str,
    *,
    ok: bool,
    severity: str,
    pass_message: str,
    fail_message: str,
    metric_id: str | None = None,
    hint_code: str | None = None,
    warn_only: bool = False,
) -> DoctorCheck:
    """Build a check row; warn_only failures surface as ``warn`` not ``fail``."""
    if ok:
        return DoctorCheck(check_id, STATUS_PASS, severity, pass_message, metric_id=metric_id)
    status = STATUS_WARN if warn_only else STATUS_FAIL
    hint = _HINTS.get(hint_code or "") if hint_code else None
    return DoctorCheck(check_id, status, severity, fail_message, metric_id=metric_id, hint=hint)


# --------------------------------------------------------------------------
# Local doctor (git-cg eval doctor)
# --------------------------------------------------------------------------


def run_local_doctor(
    *,
    repo_root: Path,
    suite_id: str = "cm-eval-fixtures-core",
    fixture_root: Path | None = None,
    max_eval_bytes: int | None = None,
) -> DoctorReport:
    """Offline local doctor. Network-free; fail-closed on floating pins.

    Produces checks across five families: pin integrity, suite/fixture load,
    FIND-026 input guards, FIND-027 scored-target binding, FIND-028 prompt-pack
    freshness, and Slice-3 checkpoint compatibility. Then projects the three
    phantom metrics as ``ScoreResultV1`` rows and aggregates ``h.doctor_green``.
    """
    from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin

    checks: list[DoctorCheck] = []

    # ---- 1. Pin integrity (fail closed on latest / missing hashes) --------
    try:
        schema_pin = schema_pack_pin()
    except Exception as exc:  # schema pack unreadable → fail closed
        schema_pin = None
        checks.append(
            _check(
                "pins.schema_pack_resolvable",
                ok=False,
                severity=SEVERITY_BLOCK,
                pass_message="",
                fail_message=f"schema pack pin unresolvable: {exc}",
                metric_id="h.pin_integrity",
                hint_code="EVAL_PIN_FLOATING",
            )
        )
    try:
        catalog_pin = metric_catalog_pin()
    except Exception as exc:
        catalog_pin = None
        checks.append(
            _check(
                "pins.metric_catalog_resolvable",
                ok=False,
                severity=SEVERITY_BLOCK,
                pass_message="",
                fail_message=f"metric catalog pin unresolvable: {exc}",
                metric_id="h.catalog_pinned",
                hint_code="EVAL_PIN_FLOATING",
            )
        )

    if schema_pin is not None:
        checks.append(
            _check(
                "pins.schema_pack_pinned",
                ok=_is_pinned(schema_pin),
                severity=SEVERITY_BLOCK,
                pass_message=f"schema pack pinned: {schema_pin[:24]}…",
                fail_message=f"schema pack pin is floating/unpinned: {schema_pin!r}",
                metric_id="h.pin_integrity",
                hint_code="EVAL_PIN_FLOATING",
            )
        )
    if catalog_pin is not None:
        checks.append(
            _check(
                "pins.metric_catalog_pinned",
                ok=_is_pinned(catalog_pin),
                severity=SEVERITY_BLOCK,
                pass_message=f"metric catalog pinned: {catalog_pin[:24]}…",
                fail_message=f"metric catalog pin is floating/unpinned: {catalog_pin!r}",
                metric_id="h.catalog_pinned",
                hint_code="EVAL_PIN_FLOATING",
            )
        )

    # ---- 2. Suite load + live pin match -----------------------------------
    suite: dict[str, Any] | None = None
    prepared: Any | None = None
    suite_snapshot_pin: str | None = None
    load_error: str | None = None
    try:
        from git_cg.eval.scoring.runner import prepare_suite_cases

        prepared = prepare_suite_cases(suite_id, fixture_root=fixture_root)
        suite = prepared.suite_doc
        suite_snapshot_pin = prepared.suite_snapshot_pin
    except Exception as exc:
        load_error = str(exc)

    checks.append(
        _check(
            "suite.load",
            ok=load_error is None,
            severity=SEVERITY_BLOCK,
            pass_message=f"suite {suite_id!r} loaded with snapshot pin",
            fail_message=f"suite {suite_id!r} failed to load: {load_error}",
            metric_id="h.pin_integrity",
        )
    )

    if suite is not None:
        suite_schema = suite.get("schema_pack") or suite.get("schema_pack_pin")
        suite_catalog = suite.get("metric_catalog") or suite.get("metric_catalog_pin")
        checks.append(
            _check(
                "suite.schema_pin_matches_live",
                ok=_is_pinned(suite_schema) and suite_schema == schema_pin,
                severity=SEVERITY_BLOCK,
                pass_message="suite schema pin matches live",
                fail_message=(f"suite schema pin {suite_schema!r} does not match live {schema_pin!r}"),
                metric_id="h.pin_integrity",
                hint_code="EVAL_SUITE_PIN_MISMATCH",
            )
        )
        checks.append(
            _check(
                "suite.catalog_pin_matches_live",
                ok=_is_pinned(suite_catalog) and suite_catalog == catalog_pin,
                severity=SEVERITY_BLOCK,
                pass_message="suite catalog pin matches live",
                fail_message=(f"suite catalog pin {suite_catalog!r} does not match live {catalog_pin!r}"),
                metric_id="h.catalog_pinned",
                hint_code="EVAL_SUITE_PIN_MISMATCH",
            )
        )

    # ---- 3. FIND-026 input guards + FIND-027 binding (per fixture) --------
    nonempty_fail = 0
    oversize_fail = 0
    unbound_fail = 0
    fanout_bounded = True
    total_cases = 0
    if prepared is not None:
        from git_cg.eval.scoring.context import (
            DEFAULT_MAX_EVAL_BYTES,
            project_score_context,
        )
        from git_cg.eval.scoring.preconditions import evaluate_preconditions

        budget = max_eval_bytes if max_eval_bytes is not None else DEFAULT_MAX_EVAL_BYTES
        total_cases = len(prepared.encoded_pairs)
        for _case_id, bundle in prepared.encoded_pairs:
            try:
                ctx = project_score_context(bundle, suite=suite, max_eval_bytes=budget)
                pre = evaluate_preconditions(ctx)
            except Exception:
                unbound_fail += 1
                continue
            if not pre.input_nonempty:
                nonempty_fail += 1
            if not pre.input_size_ok:
                oversize_fail += 1
            if ctx.scored_target == "missing":
                unbound_fail += 1
        # Bounded error fan-out: every case short-circuiting on empty input
        # means the harness is producing one failure class across the suite.
        fanout_bounded = not (total_cases > 0 and nonempty_fail == total_cases)

    checks.append(
        _check(
            "find026.input_nonempty",
            ok=nonempty_fail == 0,
            severity=SEVERITY_BLOCK,
            pass_message=f"all {total_cases} cases have non-empty scored input",
            fail_message=f"{nonempty_fail}/{total_cases} cases have empty/missing scored input",
            metric_id="h.eval_input_nonempty",
            hint_code="EVAL_INPUT_EMPTY",
        )
    )
    checks.append(
        _check(
            "find026.input_size_ok",
            ok=oversize_fail == 0,
            severity=SEVERITY_WARN,
            pass_message=f"all {total_cases} cases within eval byte budget",
            fail_message=f"{oversize_fail}/{total_cases} cases exceed the eval byte budget",
            metric_id="h.eval_input_size_ok",
            hint_code="EVAL_INPUT_OVERSIZE",
            warn_only=True,
        )
    )
    checks.append(
        _check(
            "find026.error_fanout_bounded",
            ok=fanout_bounded,
            severity=SEVERITY_BLOCK,
            pass_message="error fan-out bounded (no suite-wide empty-output collapse)",
            fail_message="every case short-circuits on empty input (unbounded error fan-out)",
            metric_id="h.eval_error_fanout_bounded",
        )
    )
    checks.append(
        _check(
            "find027.scored_target_bound",
            ok=unbound_fail == 0,
            severity=SEVERITY_BLOCK,
            pass_message=f"all {total_cases} cases bind a scored format target",
            fail_message=f"{unbound_fail}/{total_cases} cases bind no scored format target",
            metric_id="h.online_scores_match_product_card",
        )
    )

    # ---- 4. FIND-028 prompt-pack freshness (warn severity) ----------------
    prompt_pack_error: str | None = None
    pack_pin: str | None = None
    try:
        from git_cg.eval.lane_c.prompt_pack import prompt_pack_pin, resolve_judge_pack

        pack = resolve_judge_pack("cprime.geval_craft")
        pack_pin = prompt_pack_pin(pack)
    except Exception as exc:
        prompt_pack_error = str(exc)

    if prompt_pack_error is not None:
        # Lane C' pack unresolvable offline → warn, not block (offline lanes may
        # legitimately omit C'). Recorded honestly as a warn-class freshness gap.
        checks.append(
            _check(
                "find028.prompt_pack_resolvable",
                ok=False,
                severity=SEVERITY_WARN,
                pass_message="",
                fail_message=f"Lane C' prompt pack unresolvable offline: {prompt_pack_error}",
                metric_id="h.prompt_pack_suite_fresh",
                hint_code="EVAL_PROMPT_PACK_DRIFT",
                warn_only=True,
            )
        )
    else:
        pack_known = _is_pinned(pack_pin)
        snap_ok = bool(suite_snapshot_pin and str(suite_snapshot_pin).strip())
        checks.append(
            _check(
                "find028.prompt_pack_pinned",
                ok=pack_known,
                severity=SEVERITY_BLOCK,
                pass_message=f"prompt pack pinned: {str(pack_pin)[:24]}…",
                fail_message=f"prompt pack pin floating/unpinnable: {pack_pin!r}",
                metric_id="h.prompt_pack_pinned",
                hint_code="EVAL_PIN_FLOATING",
            )
        )
        checks.append(
            _check(
                "find028.prompt_pack_suite_fresh",
                ok=pack_known and snap_ok,
                severity=SEVERITY_WARN,
                pass_message="prompt pack has a local suite pin (fresh)",
                fail_message=(
                    "prompt pack changed without a local suite snapshot pin"
                    if pack_known
                    else "prompt pack pin missing; freshness undetermined"
                ),
                metric_id="h.prompt_pack_suite_fresh",
                hint_code="EVAL_PROMPT_PACK_DRIFT",
                warn_only=True,
            )
        )

    # ---- 5. Slice-3 checkpoint compatibility (h.compat_hash_resume) -------
    compat_ok = True
    compat_fail_checkpoint: str | None = None
    compat_checked = 0
    if prepared is not None and suite_snapshot_pin:
        from git_cg.eval.checkpoint_store import list_checkpoint_ids, load_checkpoint
        from git_cg.eval.compat import compute_compat_hash

        try:
            live_hash = compute_compat_hash(
                schema_pack_pin=schema_pin or "",
                metric_catalog_pin=catalog_pin or "",
                suite_id=suite_id,
                snapshot_hash=suite_snapshot_pin,
            )
        except Exception:
            live_hash = None

        if live_hash is not None:
            for cid in list_checkpoint_ids(repo_root):
                try:
                    ckpt = load_checkpoint(repo_root, cid)
                except Exception:
                    # Unreadable checkpoint is an I/O concern, not a compat fail.
                    continue
                stored = str(ckpt.get("compat_hash") or "").strip().lower()
                if not stored:
                    continue
                compat_checked += 1
                if stored != live_hash:
                    compat_ok = False
                    compat_fail_checkpoint = cid
                    break

    checks.append(
        _check(
            "compat.hash_resume",
            ok=compat_ok,
            severity=SEVERITY_BLOCK,
            pass_message=(
                f"{compat_checked} checkpoint(s) match live compat hash"
                if compat_checked
                else "no stored checkpoints to diverge (vacuous pass)"
            ),
            fail_message=(f"checkpoint {compat_fail_checkpoint!r} compat_hash diverges from live preimage"),
            metric_id="h.compat_hash_resume",
            hint_code="EVAL_COMPAT_HASH_MISMATCH",
        )
    )

    # ---- Aggregate h.doctor_green (block-severity only) -------------------
    green = not any(c.severity == SEVERITY_BLOCK and c.status == STATUS_FAIL for c in checks)

    # ---- Phantom metric producers → ScoreResultV1 rows --------------------
    from git_cg.eval.scoring.result_builder import make_score

    compat_score = make_score(
        "h.compat_hash_resume",
        compat_ok,
        reason=None if compat_ok else "compat_hash_mismatch",
        evidence={"checkpoints_checked": compat_checked, "failed_checkpoint": compat_fail_checkpoint},
        failure_ids=None if compat_ok else ["EVAL_COMPAT_HASH_MISMATCH"],
        product_authority="git_cg.eval.doctor.run_local_doctor",
    )
    green_score = make_score(
        "h.doctor_green",
        green,
        reason=None if green else "block_severity_check_failed",
        evidence={
            "block_failures": [c.check_id for c in checks if c.severity == SEVERITY_BLOCK and c.status == STATUS_FAIL],
            "check_count": len(checks),
            "aggregation_rule": "block_severity_only",
        },
        failure_ids=None if green else ["EVAL_DOCTOR_RED"],
        product_authority="git_cg.eval.doctor.run_local_doctor",
    )
    export_score = _export_config_score(make_score)

    # Exit: 1 when doctor red (block fail), 3 on compat mismatch (distinct class).
    exit_code = 0
    if not compat_ok:
        exit_code = 3
    elif not green:
        exit_code = 1

    return DoctorReport(
        green=green,
        checks=tuple(checks),
        scores=(compat_score, green_score, export_score),
        suite_id=suite_id,
        exit_code=exit_code,
    )


def _export_config_score(make_score: Any) -> Any:
    """``h.export_config_resolved`` — from S4 config resolution + health."""
    from git_cg.eval.mirror.config import OpikConfigError, operator_config_health, resolve_opik_config

    try:
        config = resolve_opik_config()
        health = operator_config_health(config)
        resolved = health != "config_error"
        reason = None if resolved else f"config_health:{health}"
        return make_score(
            "h.export_config_resolved",
            resolved,
            reason=reason,
            evidence={"health": health, "mode": config.get("mode")},
            failure_ids=None if resolved else ["EVAL_CONFIG_ERROR"],
            product_authority="git_cg.eval.doctor.run_local_doctor",
        )
    except OpikConfigError as exc:
        return make_score(
            "h.export_config_resolved",
            False,
            reason=f"config_error: {exc}",
            evidence={"health": "config_error"},
            failure_ids=["EVAL_CONFIG_ERROR"],
            product_authority="git_cg.eval.doctor.run_local_doctor",
        )


# --------------------------------------------------------------------------
# Opik doctor (git-cg eval opik doctor) — secret-safe, no transport
# --------------------------------------------------------------------------


def run_opik_doctor(*, repo_root: Path) -> DoctorReport:
    """Secret-safe Opik/export/queue health doctor. No transport, no network.

    Reuses S4 helpers (``resolve_opik_config`` / ``operator_config_health`` /
    ``public_config_view`` / ``mask_secret``). Never prints raw token values or
    prefixes — only ``mask_secret()`` output and a presence boolean.
    """
    import os

    from git_cg.eval.mirror.config import (
        OpikConfigError,
        mask_secret,
        operator_config_health,
        public_config_view,
        resolve_opik_config,
    )

    checks: list[DoctorCheck] = []
    config_view: dict[str, Any] | None = None
    health: str = "config_error"

    try:
        config = resolve_opik_config()
        config_view = public_config_view(config)
        health = operator_config_health(config)
    except OpikConfigError as exc:
        checks.append(
            _check(
                "opik.config_resolved",
                ok=False,
                severity=SEVERITY_BLOCK,
                pass_message="",
                fail_message=f"Opik config fail-closed: {exc}",
                metric_id="h.export_config_resolved",
                hint_code="EVAL_CONFIG_ERROR",
            )
        )
        green = False
        scores = _opik_scores(resolved=False, health=health)
        return DoctorReport(
            green=green,
            checks=tuple(checks),
            scores=scores,
            exit_code=2,
            extra={"config": None, "queue_counts": {}},
        )

    config_ok = health != "config_error"
    checks.append(
        _check(
            "opik.config_resolved",
            ok=config_ok,
            severity=SEVERITY_BLOCK,
            pass_message=f"Opik config resolved (mode={config_view.get('mode')})",
            fail_message="Opik config health is config_error (mode token invalid)",
            metric_id="h.export_config_resolved",
            hint_code="EVAL_CONFIG_ERROR",
        )
    )

    # Mode-specific health as observability (never flips block-green by itself
    # unless it is a hard config_error already handled above).
    mode = str(config_view.get("mode") or "off")
    checks.append(
        DoctorCheck(
            "opik.mode",
            STATUS_PASS,
            SEVERITY_WARN,
            f"mode={mode} health={health}",
        )
    )

    # Secret presence: masked form only, never value/prefix.
    ambient_key = os.environ.get("OPIK_API_KEY") or os.environ.get("GIT_CG_OPIK_API_KEY")
    key_present = bool(ambient_key)
    active_mode = mode not in {"off", "local_only", "local"}
    if active_mode and not key_present:
        checks.append(
            _check(
                "opik.api_key_present",
                ok=False,
                severity=SEVERITY_WARN,
                pass_message="",
                fail_message="active export mode but no Opik API key in environment",
                hint_code="EVAL_CONFIG_ERROR",
                warn_only=True,
            )
        )
    else:
        checks.append(
            DoctorCheck(
                "opik.api_key_present",
                STATUS_PASS,
                SEVERITY_WARN,
                (
                    f"api_key={mask_secret(ambient_key)}"
                    if key_present
                    else "no Opik API key (off/local mode — acceptable)"
                ),
            )
        )

    # Queue health (local-only, offline; unreadable rows bucketed, not raised).
    queue_counts = _queue_counts(repo_root)
    unreadable = queue_counts.get("unreadable", 0)
    failed = queue_counts.get("failed", 0)
    checks.append(
        _check(
            "opik.queue_readable",
            ok=unreadable == 0,
            severity=SEVERITY_WARN,
            pass_message=f"export queue readable ({sum(queue_counts.values())} items)",
            fail_message=f"{unreadable} unreadable export-queue row(s)",
            warn_only=True,
        )
    )
    checks.append(
        _check(
            "opik.queue_failed_drainable",
            ok=failed == 0,
            severity=SEVERITY_WARN,
            pass_message="no failed export-queue rows pending retry",
            fail_message=f"{failed} failed export-queue row(s) await drain/retry",
            warn_only=True,
        )
    )

    green = config_ok
    scores = _opik_scores(resolved=config_ok, health=health)
    exit_code = 0 if config_ok else 2

    return DoctorReport(
        green=green,
        checks=tuple(checks),
        scores=scores,
        exit_code=exit_code,
        extra={"config": config_view, "queue_counts": queue_counts},
    )


def _queue_counts(repo_root: Path) -> dict[str, int]:
    """Read-only export-queue status counts (offline; unreadable → bucket)."""
    from git_cg.eval.mirror.queue import export_queue_dir, load_queue_item

    qdir = export_queue_dir(repo_root)
    counts: dict[str, int] = {}
    if qdir.is_dir():
        for path in sorted(qdir.glob("*.json")):
            try:
                item = load_queue_item(path.stem, repo_root=repo_root)
            except Exception:
                counts["unreadable"] = counts.get("unreadable", 0) + 1
                continue
            status = str(item.get("status", "unknown"))
            counts[status] = counts.get(status, 0) + 1
    return counts


def _opik_scores(*, resolved: bool, health: str) -> tuple[Any, ...]:
    """Project the Opik doctor subset of phantom metrics as ScoreResultV1."""
    from git_cg.eval.scoring.result_builder import make_score

    export_score = make_score(
        "h.export_config_resolved",
        resolved,
        reason=None if resolved else f"config_health:{health}",
        evidence={"health": health},
        failure_ids=None if resolved else ["EVAL_CONFIG_ERROR"],
        product_authority="git_cg.eval.doctor.run_opik_doctor",
    )
    green_score = make_score(
        "h.doctor_green",
        resolved,
        reason=None if resolved else "config_error",
        evidence={"aggregation_rule": "block_severity_only", "health": health},
        failure_ids=None if resolved else ["EVAL_DOCTOR_RED"],
        product_authority="git_cg.eval.doctor.run_opik_doctor",
    )
    return (export_score, green_score)


__all__ = [
    "DoctorCheck",
    "DoctorReport",
    "run_local_doctor",
    "run_opik_doctor",
]
