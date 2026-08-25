"""S6-A08 — per-command ``cli_output_envelope_v1.data`` sketches.

Slice 2 locks command-discriminated ``data`` shapes for the minimum JSON
operator surface. The envelope schema keeps ``data`` as an object; these
sketches are the closed key contracts implementers must not invent past.

Ownership:
* Registry lives here (import-light; stdlib only).
* ``api_map.py`` renders the sketches into ``docs/eval/operator_api_map.md``
  and fails ``--check`` when a required command lacks a sketch or the
  on-disk map drifts.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class DataSketch:
    """Closed top-level ``data`` sketch for one JSON-capable command.

    Nested object shapes are summarized in ``notes`` / ``nested`` rather than
    re-freezing full artifact schemas (those already live under ``schemas/eval/``).
    """

    command: str
    required_keys: tuple[str, ...]
    optional_keys: tuple[str, ...] = ()
    enums: Mapping[str, tuple[str, ...]] = None  # type: ignore[assignment]
    nested: tuple[str, ...] = ()
    notes: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "enums", dict(self.enums or {}))
        # Stable ordering for deterministic render/tests.
        object.__setattr__(self, "required_keys", tuple(sorted(self.required_keys)))
        object.__setattr__(self, "optional_keys", tuple(sorted(self.optional_keys)))

    @property
    def allowed_keys(self) -> frozenset[str]:
        """Closed top-level key set (required union optional)."""
        return frozenset(self.required_keys) | frozenset(self.optional_keys)


# Minimum command set frozen under Issue #246 Exit-code / envelope block (S6-A08).
MINIMUM_SKETCH_COMMANDS: Final[frozenset[str]] = frozenset(
    {
        "eval run",
        "eval resume",
        "eval recompute-scores",
        "eval doctor",
        "eval opik doctor",
        "eval opik config show",
        "eval failures",
        "eval explain",
        "eval compare",
        "eval diagnose",
        "eval issue list",
        "eval issue show",
        "eval replay",
        "eval promote",
        "eval amend-brief",
        "eval dogfood",
        "eval train-export",
        "eval session show",
        "eval thread show",
        "eval export status",
        "eval export retry",
        "eval export drain",
    }
)

# Shared run/resume/recompute family (RunResult.to_data).
_RUN_MODES: tuple[str, ...] = (
    "fresh_suite_run",
    "resume_missing",
    "recompute_scores",
    "export_only",
    "replay_generation",
)
_RUN_STATUS: tuple[str, ...] = ("completed", "failed", "blocked")


def _sketch(
    command: str,
    *,
    required_keys: tuple[str, ...],
    optional_keys: tuple[str, ...] = (),
    enums: Mapping[str, tuple[str, ...]] | None = None,
    nested: tuple[str, ...] = (),
    notes: str = "",
) -> DataSketch:
    return DataSketch(
        command=command,
        required_keys=required_keys,
        optional_keys=optional_keys,
        enums=enums or {},
        nested=nested,
        notes=notes,
    )


def _build_registry() -> dict[str, DataSketch]:
    """Construct the closed S6-A08 sketch registry (deterministic)."""
    run_required = (
        "status",
        "mode",
        "suite_id",
        "experiment_id",
        "checkpoint_id",
        "compat_hash",
        "completed_case_ids",
        "pending_case_ids",
        "case_results",
        "all_pass",
        "keep_last",
    )
    run_optional = (
        "parent_experiment_id",
        "pruned_checkpoint_ids",
        "triage_filter",
        "triage_only",
        "notes",
    )
    run_enums = {"mode": _RUN_MODES, "status": _RUN_STATUS}
    run_nested = ("case_results[]: {case_id, deterministic_pass, failed_metric_ids}",)
    run_notes = (
        "Shared by run/resume/recompute-scores via RunResult.to_data(). "
        "Failure envelopes may carry a subset with at least status "
        "(+ orchestrator error fields when present). "
        "Never smuggles raw diffs/secrets through data or envelope meta."
    )

    doctor_required = (
        "green",
        "exit_code",
        "suite_id",
        "checks",
        "scores",
        "block_failures",
        "warn_failures",
    )
    doctor_nested = (
        "checks[]: {check_id, status: pass|warn|fail, severity, message, metric_id?, hint?}",
        "scores[]: ScoreResultV1 rows (catalog-aligned phantom metrics)",
    )
    doctor_notes = (
        "Observability-only. h.doctor_green aggregates block-severity checks only. "
        "Secret-bearing values must already be mask_secret()-shaped. "
        "DoctorReport.extra may merge additional closed command-specific keys; "
        "do not invent free-form product keys."
    )

    registry: dict[str, DataSketch] = {
        "eval run": _sketch(
            "eval run",
            required_keys=run_required,
            optional_keys=run_optional,
            enums=run_enums,
            nested=run_nested,
            notes=run_notes,
        ),
        "eval resume": _sketch(
            "eval resume",
            required_keys=run_required,
            optional_keys=run_optional,
            enums=run_enums,
            nested=run_nested,
            notes=run_notes,
        ),
        "eval recompute-scores": _sketch(
            "eval recompute-scores",
            required_keys=run_required,
            optional_keys=run_optional,
            enums=run_enums,
            nested=run_nested,
            notes=run_notes + " Parent experiment retained read-only on recompute.",
        ),
        "eval doctor": _sketch(
            "eval doctor",
            required_keys=doctor_required,
            nested=doctor_nested,
            notes=doctor_notes,
        ),
        "eval opik doctor": _sketch(
            "eval opik doctor",
            required_keys=doctor_required,
            nested=doctor_nested,
            notes=(
                "Secret-safe Opik/export/queue doctor. Same checks[]/scores[] "
                "contract as eval doctor; suite_id may be null."
            ),
        ),
        "eval opik config show": _sketch(
            "eval opik config show",
            required_keys=("config", "secrets", "health_hint", "mirror_result"),
            nested=(
                "secrets: {api_key: masked|null, api_key_present: bool}",
                "config: public_config_view (no raw tokens; may be null on config_error)",
                "mirror_result: S4 mirror result projection",
            ),
            notes=(
                "Canonical config surface. Deprecated `eval config show` emits "
                "the same data shape plus envelope warnings[]."
            ),
        ),
        "eval failures": _sketch(
            "eval failures",
            required_keys=("experiment_id", "failing_cases", "case_count"),
            nested=("failing_cases[]: {case_id, deterministic_pass, metric_ids[], failure_ids[], evaluator_errors[]}",),
            notes="Read-only. experiment_id may be null when no local runs exist.",
        ),
        "eval explain": _sketch(
            "eval explain",
            required_keys=("experiment_id", "case_count", "cases", "headers"),
            nested=(
                "cases[]: deterministic explain rows (blame_span, failure_ids, replay_command, ...)",
                "headers: INT-29 pins/meta projection",
            ),
            notes="No opaque LLM RCA. Secret-safe projection via evidence_scrub.",
        ),
        "eval compare": _sketch(
            "eval compare",
            required_keys=(
                "a",
                "b",
                "lineage_linked",
                "compare_source",
                "metric_delta",
                "structural_delta",
            ),
            enums={
                "compare_source": ("replay_compare_v1", "case_result_delta"),
            },
            nested=(
                "a/b: {experiment_id, case_id}",
                "metric_delta[]: {metric_id, a, b, changed}",
            ),
            notes="Structural + metric delta only; does not write replay artifacts.",
        ),
        "eval diagnose": _sketch(
            "eval diagnose",
            required_keys=("issue", "upserted"),
            nested=("issue: diag_issue_v1 row",),
            notes="Idempotent fingerprint upsert into .eval/issues/.",
        ),
        "eval issue list": _sketch(
            "eval issue list",
            required_keys=("issues", "issue_count"),
            nested=("issues[]: diag_issue_v1 rows",),
            notes="Newest last_seen_at first. Optional --status filter applied before emit.",
        ),
        "eval issue show": _sketch(
            "eval issue show",
            required_keys=("issue",),
            nested=("issue: diag_issue_v1 row",),
            notes="Single-issue read.",
        ),
        "eval replay": _sketch(
            "eval replay",
            required_keys=(
                "compare",
                "replay_bundle",
                "source_path",
                "compare_path",
                "replay_bundle_path",
                "source_bundle_hash",
                "replay_bundle_hash",
                "source_mutated",
                "dry_run",
            ),
            nested=(
                "compare: replay_compare_v1 record",
                "replay_bundle: replayed bundle document",
            ),
            notes="Never mutates the source bundle (source_mutated must be false).",
        ),
        "eval promote": _sketch(
            "eval promote",
            required_keys=("accepted", "denial_reason"),
            optional_keys=(
                "decision",
                "decision_path",
                "artifact_path",
                "dry_run",
            ),
            nested=("decision?: promotion audit row (closed denial_reason set on reject)",),
            notes=(
                "Success path emits all six keys (accepted/denial_reason/decision/"
                "decision_path/artifact_path/dry_run). Denial path always emits "
                "accepted=false + denial_reason and may attach decision/decision_path "
                "when an audit row was retained. Never sole gold authority."
            ),
        ),
        "eval amend-brief": _sketch(
            "eval amend-brief",
            required_keys=(
                "brief",
                "brief_id",
                "written",
                "path",
                "experiment_id",
                "authority",
                "blocking",
                "preference_pair_emitted",
                "lane_c_attachments",
            ),
            enums={"authority": ("advisory",)},
            nested=("brief: amend_brief_v1 document",),
            notes="Advisory only; never auto-applies, accepts, or re-ranks.",
        ),
        "eval dogfood": _sketch(
            "eval dogfood",
            required_keys=(
                "captured",
                "mode",
                "authority",
                "product_block",
                "async_never_awaits_judge",
                "judge_invoked",
            ),
            optional_keys=(
                "skipped",
                "reason",
                "attachment",
                "attachment_id",
                "path",
                "sample_selected",
                "hard_negative_candidate",
            ),
            enums={
                "mode": ("off", "sample", "always", "async"),
                "authority": ("advisory",),
            },
            nested=("attachment?: dogfood_attachment_v1 when captured",),
            notes=("Lane C shadow sidecar. product_block must stay false. async mode never invokes/awaits the judge."),
        ),
        "eval train-export": _sketch(
            "eval train-export",
            required_keys=(
                "export",
                "export_id",
                "row_ids",
                "row_count",
                "dropped_row_ids",
                "scrub_report",
                "positive_gold_count",
                "negative_count",
                "excluded_unlabeled",
                "written",
                "paths",
                "authority",
                "ci_sole_green",
                "product_accept_authority",
            ),
            enums={
                "authority": ("corpus_retention",),
            },
            nested=(
                "export: train_export_v1 header",
                "scrub_report: {status, ...} (row scrub-fail → drop + continue)",
                "paths: null | {export_path, row_paths[], vault_paths[], row_count}",
            ),
            notes=(
                "ci_sole_green and product_accept_authority stay false. "
                "No .eval/quarantine/ store; field quarantine remains S4 meta."
            ),
        ),
        "eval session show": _sketch(
            "eval session show",
            required_keys=(
                "session",
                "session_thread_id",
                "lifecycle",
                "message_version_count",
                "preference_pairs",
                "opik_thread_ref",
                "path",
                "authority",
                "network",
                "surface",
            ),
            enums={
                "lifecycle": ("open", "closed"),
                "surface": ("show_map_only",),
                "authority": ("local_layer_a",),
            },
            nested=("session: commit_session_thread_v1 twin",),
            notes=("Read/map only. network is the boolean false (offline). Not a chat browser."),
        ),
        "eval thread show": _sketch(
            "eval thread show",
            required_keys=(
                "thread",
                "session_thread_id",
                "lifecycle",
                "opik_thread_ref",
                "path",
                "authority",
                "network",
                "surface",
            ),
            enums={
                "lifecycle": ("open", "closed"),
                "surface": ("show_map_only",),
                "authority": ("local_layer_a",),
            },
            nested=("thread: {id, message_versions[], preference_pairs[], message_version_count, ...}",),
            notes=(
                "Read/map only over the same sess_ capture episode. "
                "network is the boolean false (offline). Not a chat browser."
            ),
        ),
        "eval export status": _sketch(
            "eval export status",
            required_keys=("queue_dir", "counts", "health", "bad_mode"),
            nested=("counts: status → int (pending/sending/sent/failed/dropped/unreadable)",),
            notes=(
                "Read-only offline queue projection. Error path may emit empty data {} "
                "(repo unresolvable) outside the happy-path required set."
            ),
        ),
        "eval export retry": _sketch(
            "eval export retry",
            required_keys=("retried", "skipped", "unreadable"),
            optional_keys=("note",),
            notes=("failed→pending requeue summary. Fail-open on repo errors may include note=fail_open."),
        ),
        "eval export drain": _sketch(
            "eval export drain",
            required_keys=(),
            optional_keys=(
                "mode",
                "note",
                "project",
                "pending",
                "mirror_result",
                "export_result",
                "evaluation_job_result",
                "health_hint",
                "attempted",
                "exported",
                "failed",
                "error_classes",
                "error",
            ),
            nested=(
                "dry-run success: {mode, project, pending}",
                "mode=off: {mode: off, note: nothing_to_do}",
                "live drain: mirror_result + attempted/exported/failed/error_classes",
                "fail-open: {note: fail_open, error?}",
            ),
            notes=(
                "F4 fail-open drain. Exact key subset depends on mode/dry-run/config path; "
                "do not invent keys outside the optional set. Config-invalid may use empty data {}."
            ),
        ),
    }
    return registry


ENVELOPE_DATA_SKETCHES: Final[dict[str, DataSketch]] = _build_registry()


def missing_minimum_sketches(
    sketches: Mapping[str, DataSketch] | None = None,
) -> list[str]:
    """Return sorted minimum-set commands lacking a registry sketch."""
    reg = ENVELOPE_DATA_SKETCHES if sketches is None else sketches
    return sorted(cmd for cmd in MINIMUM_SKETCH_COMMANDS if cmd not in reg)


def validate_sketch_registry(
    sketches: Mapping[str, DataSketch] | None = None,
) -> tuple[bool, str]:
    """Fail closed when the minimum command set is not fully sketched."""
    missing = missing_minimum_sketches(sketches)
    if missing:
        return (
            False,
            "envelope data sketches missing for: " + ", ".join(f"`{c}`" for c in missing),
        )
    reg = ENVELOPE_DATA_SKETCHES if sketches is None else sketches
    # Extra hygiene: every registered sketch must name its own command key.
    bad = sorted(cmd for cmd, sk in reg.items() if sk.command != cmd)
    if bad:
        return False, "sketch command field mismatch for: " + ", ".join(bad)
    return True, f"ok: {len(MINIMUM_SKETCH_COMMANDS)} minimum envelope data sketches present"


def render_sketches_markdown(
    sketches: Mapping[str, DataSketch] | None = None,
) -> list[str]:
    """Render the API-map appendix section lines (no trailing file newline)."""
    reg = ENVELOPE_DATA_SKETCHES if sketches is None else sketches
    lines: list[str] = [
        "## Per-command envelope `data` sketches (S6-A08)",
        "",
        "Command-discriminated top-level keys for `cli_output_envelope_v1.data`.",
        "The envelope schema keeps `data` as an object; **these sketches close the",
        "keys**. Implementers must not add undeclared result keys or smuggle",
        "scores/gates/promotion/secrets/raw diffs through `data` or `meta`.",
        "",
        "Nested artifact bodies (for example `amend_brief_v1`, `diag_issue_v1`,",
        "`replay_compare_v1`) remain governed by their own `schemas/eval/*`",
        "documents — sketches name the envelope wrapper keys only.",
        "",
        "### Minimum command set",
        "",
    ]
    for cmd in sorted(MINIMUM_SKETCH_COMMANDS):
        lines.append(f"* `{cmd}`")
    lines.extend(
        [
            "",
            "### Sketches",
            "",
        ]
    )
    for cmd in sorted(reg):
        sk = reg[cmd]
        lines.append(f"#### `{cmd}`")
        lines.append("")
        req = ", ".join(f"`{k}`" for k in sk.required_keys) or "*(none — see path notes)*"
        lines.append(f"* **Required keys:** {req}")
        if sk.optional_keys:
            opt = ", ".join(f"`{k}`" for k in sk.optional_keys)
            lines.append(f"* **Optional keys:** {opt}")
        else:
            lines.append("* **Optional keys:** *(none)*")
        if sk.enums:
            lines.append("* **Closed enums:**")
            for field in sorted(sk.enums):
                vals = " \\| ".join(f"`{v}`" for v in sk.enums[field])
                lines.append(f"  * `{field}`: {vals}")
        if sk.nested:
            lines.append("* **Nested (informational):**")
            for item in sk.nested:
                lines.append(f"  * {item}")
        if sk.notes:
            lines.append(f"* **Notes:** {sk.notes}")
        lines.append("")
    return lines


__all__ = [
    "ENVELOPE_DATA_SKETCHES",
    "MINIMUM_SKETCH_COMMANDS",
    "DataSketch",
    "missing_minimum_sketches",
    "render_sketches_markdown",
    "validate_sketch_registry",
]
