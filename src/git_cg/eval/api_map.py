"""Generate ``docs/eval/operator_api_map.md`` from the live Typer tree.

Slice 2 / RK-S6-10: the operator API map is **not** hand-maintained. This
module introspects ``git_cg.eval.cli.eval_app`` and renders a deterministic
Markdown document. ``--check`` fails when the on-disk map drifts **or** when
S6-A08 per-command envelope ``data`` sketches are incomplete.

No mkdocstrings / mkdocs / S7 autodoc dependency (D29 narrow exception).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from typer.main import get_command

from git_cg.eval.cli import eval_app
from git_cg.eval.cli_output import DEFAULT_KEEP_LAST, REMOVAL_TARGET
from git_cg.eval.envelope_sketches import (
    render_sketches_markdown,
    validate_sketch_registry,
)

DEFAULT_MAP_PATH = Path("docs/eval/operator_api_map.md")

# Canonical S6 surface (Slice 0 lock). Used to annotate status in the map.
CANONICAL_COMMANDS: frozenset[str] = frozenset(
    {
        "eval run",
        "eval resume",
        "eval recompute-scores",
        "eval doctor",
        "eval triage",
        "eval amend-brief",
        "eval dogfood",
        "eval train-export",
        "eval session show",
        "eval thread show",
        "eval failures",
        "eval explain",
        "eval compare",
        "eval replay",
        "eval promote",
        "eval diagnose",
        "eval issue list",
        "eval issue show",
        "eval issue resolve",
        "eval issue reopen",
        "eval issue suppress",
        "eval opik doctor",
        "eval opik config show",
        "eval export status",
        "eval export retry",
        "eval export drain",
        # Landed corpus helpers remain public CLI.
        "eval materialize-core-goldens",
        "eval encode-fixture",
    }
)

DEPRECATED_ALIASES: dict[str, str] = {
    "eval config": "eval opik config show",  # flat command takes action arg
    "eval export-status": "eval export status",
    "eval export-retry": "eval export retry",
    "eval export-drain": "eval export drain",
}

# Canonical commands that remain callable but are omitted from regular help.
DARK_LAUNCH_HIDDEN_COMMANDS: frozenset[str] = frozenset(
    {
        "eval dogfood",
    }
)

SUPPORTED_PYTHON_ENTRYPOINTS: tuple[tuple[str, str, str], ...] = (
    ("score_bundle", "git_cg.eval.scoring", "Score one ape_bundle_v1 offline"),
    ("score_case", "git_cg.eval.scoring", "Score one fixture/case offline"),
    ("score_suite", "git_cg.eval.scoring", "Score a suite offline"),
    ("compose_gates", "git_cg.eval.scoring", "Compose gate.* rollups"),
    ("ScoreResultV1", "git_cg.eval", "Authoritative per-metric score envelope"),
    ("schema_pack_pin", "git_cg.eval", "Frozen schema-pack content pin"),
    ("metric_catalog_pin", "git_cg.eval", "Frozen metric-catalog content pin"),
    ("load_metric_catalog", "git_cg.eval", "Load the pinned metric catalog"),
    ("run_lane_c", "git_cg.eval.lane_c", "Gated Lane C-prime advisory runner"),
)


@dataclass(frozen=True, slots=True)
class CommandNode:
    """One registered CLI path under ``git-cg eval``."""

    path: str  # e.g. "eval export status"
    kind: str  # "command" | "group"
    help: str
    children: tuple[str, ...] = ()


def _click_help(cmd: Any) -> str:
    """Normalize Click/Typer help text into a single-line API-map blurb.

    Prefer short_help when present. Otherwise keep only the brief side of any
    help-depth split (project detail marker or Click form-feed) so long bodies
    do not leak into the operator map table.
    """
    short = getattr(cmd, "short_help", None)
    if short:
        return " ".join(str(short).split())

    help_text = getattr(cmd, "help", None) or ""
    text = str(help_text)
    # Import locally to avoid expanding api_map's module import surface mid-cycle
    # for callers that only need pure helpers; eval_app is already imported above.
    from git_cg.eval.cli import _HELP_DETAIL_MARKER

    for marker in (_HELP_DETAIL_MARKER, ""):
        if marker in text:
            text = text.split(marker, 1)[0]
            break
    return " ".join(text.split())


def walk_eval_tree(prefix: str = "eval") -> list[CommandNode]:
    """Walk the live Click/Typer tree rooted at ``eval_app``."""
    root = get_command(eval_app)
    nodes: list[CommandNode] = []

    def walk(cmd: Any, path_parts: Sequence[str]) -> None:
        """Recursively walk one Click command subtree into CommandNode records."""
        full = " ".join(path_parts) if path_parts else prefix
        is_group = hasattr(cmd, "list_commands") and callable(cmd.list_commands)
        if is_group:
            child_names = sorted(cmd.list_commands(None) or [])
            # Root is the eval group itself — record children only via recursion,
            # but still emit leaf commands and nested groups as nodes.
            if path_parts:  # skip bare "" ; we always start with ("eval",) conceptually
                nodes.append(
                    CommandNode(
                        path=full,
                        kind="group",
                        help=_click_help(cmd),
                        children=tuple(child_names),
                    )
                )
            for child_name in child_names:
                child = cmd.get_command(None, child_name)
                if child is None:
                    continue
                walk(child, (*path_parts, child_name))
        else:
            nodes.append(CommandNode(path=full, kind="command", help=_click_help(cmd)))

    # Synthetic root path "eval"
    child_names = sorted(root.list_commands(None) or [])
    nodes.append(
        CommandNode(
            path=prefix,
            kind="group",
            help=_click_help(root) or "Evaluation harness operator surface",
            children=tuple(child_names),
        )
    )
    for child_name in child_names:
        child = root.get_command(None, child_name)
        if child is None:
            continue
        walk(child, (prefix, child_name))
    return nodes


def _status_for(path: str) -> tuple[str, str]:
    """Return (status, notes) for a command path."""
    if path in DEPRECATED_ALIASES:
        return (
            "temporary alias",
            f"Canonical: `{DEPRECATED_ALIASES[path]}`. Removal: {REMOVAL_TARGET}.",
        )
    if path in CANONICAL_COMMANDS:
        if path in DARK_LAUNCH_HIDDEN_COMMANDS:
            return (
                "canonical (dark-launch)",
                "Maintainer/operator surface; registered and callable, but hidden "
                "from regular `git-cg eval --help` (dark launch).",
            )
        return ("canonical", "Public CLI operator surface.")
    if path.startswith("eval ") and path.count(" ") == 1:
        # top-level under eval that isn't listed — still public if registered
        leaf = path.split(" ", 1)[1]
        if leaf.startswith("export-"):
            return (
                "temporary alias",
                f"Canonical nested form preferred. Removal: {REMOVAL_TARGET}.",
            )
    if path in {
        "eval export",
        "eval issue",
        "eval opik",
        "eval opik config",
        "eval review",
        "eval session",
        "eval thread",
    }:
        return ("group", "Nested Typer group (not invoked alone).")
    if path == "eval":
        return ("group", "Root eval Typer group.")
    return ("registered", "Present on Typer tree; see help.")


def _stability_tier(path: str, kind: str) -> str:
    """Classify a command path into public/supported/internal stability tiers."""
    if kind == "group":
        return "public (group)"
    if path in DEPRECATED_ALIASES or path == "eval config" or path.startswith("eval export-"):
        return "public (deprecated alias)"
    if path in DARK_LAUNCH_HIDDEN_COMMANDS:
        return "public (dark-launch; hidden from regular help)"
    return "public"


def render_operator_api_map(nodes: Iterable[CommandNode] | None = None) -> str:
    """Render the deterministic Markdown operator API map."""
    items = list(nodes) if nodes is not None else walk_eval_tree()
    lines: list[str] = [
        "<!-- Generated by src/git_cg/eval/api_map.py — do not hand-edit.",
        "     Regenerate: uv run python -m git_cg.eval.api_map --write",
        "     Check:      uv run python -m git_cg.eval.api_map --check",
        "-->",
        "",
        "# Operator API map (S6)",
        "",
        "Generated from the **live Typer tree** (`git_cg.eval.cli.eval_app`).",
        "This document is the Slice 2 operator API map (Issue #246 / RK-S6-10).",
        "",
        "> **Not** a general-purpose Python SDK, REST/OpenAPI surface, or S7",
        "> autodoc site. CLI is the primary public operator API.",
        "",
        "## Stability tiers",
        "",
        "| Tier | Surface | Compatibility promise |",
        "|:---|:---|:---|",
        "| **Public** | `git-cg` / `git-cg eval …` CLI | Primary operator API; help-tested |",
        "| **Supported** | Selected `git_cg.eval*` entrypoints listed below | Maintainer/harness-stable |",
        "| **Internal** | All other `git_cg.eval*` / product modules | No compatibility promise |",
        "",
        "Dark-launched canonical commands (currently `eval dogfood`) stay **callable**",
        "for maintainers but are **hidden from regular `git-cg eval --help`** so basic",
        "users do not see them in the default command menu. Direct invocation and",
        "operator-map / claim-matrix references remain valid.",
        "",
        "Undocumented internals are **not** promised compatible (S6-A05).",
        "",
        "## Policy constants",
        "",
        "| Constant | Value |",
        "|:---|:---|",
        f"| Deprecated alias removal target | `{REMOVAL_TARGET}` |",
        f"| Default `--keep-last` (checkpoint retention bound) | `{DEFAULT_KEEP_LAST}` |",
        "",
        "Pruning semantics for `--keep-last` are live (per-suite family; "
        "failed-run retention until a completed supersedes). The default is "
        "recorded here so help/API map stay aligned.",
        "",
        "## Single-writer / operator-writer law",
        "",
        (
            "This section documents the **current ownership boundary**. "
            "It does **not** introduce locking, compare-and-swap, or "
            "multi-writer concurrency primitives for the stores below."
        ),
        "",
        "### Single-operator-writer stores",
        "",
        (
            "The following Layer-A operator surfaces are "
            "**single-operator-writer** by law (one active mutator at a time "
            "per repo checkout):"
        ),
        "",
        ("* `.eval/issues/` + `.eval/diagnostics/` — `eval diagnose` / `eval issue *` (`diag_issue_v1`)"),
        ("* `.eval/review_queue/` — `eval review *` (`human_review_v1` queue envelopes; advisory only)"),
        ("* `.eval/index/promotions/` — `eval promote` decision audit rows (never sole gold-promotion authority)"),
        (
            "* adjacent operator-authored artifacts under the same ownership "
            "posture (for example amend briefs, dogfood attachments, replay "
            "compares, train-export envelopes) when mutated via operator CLI"
        ),
        "",
        "### Suite vs operator mutation boundary",
        "",
        (
            "* **Suite / orchestrator runs** (`eval run`, `eval resume`, "
            "checkpoint + experiment writers) may **read** operator stores "
            "for evidence and routing, and may write their **own** suite "
            "trees (`.eval/checkpoints/`, `.eval/experiments/`, case results)."
        ),
        (
            "* Suite runs **must not concurrently mutate** issue, "
            "review-queue, or promotion stores. Those mutations remain "
            "operator-command paths "
            "(`diagnose` / `issue` / `review` / `promote`)."
        ),
        ("* Doctor and triage are **observability/advisory only** and do not own writes to those mutation stores."),
        "",
        "### Write discipline (already required)",
        "",
        (
            "Operator mutations use governed path helpers "
            "(`git_cg.eval.binding.paths`) and **atomic-write** discipline "
            "(N19.3: temp file in the target directory + `os.replace`, "
            "containment-checked under `.eval/`). Atomic replace prevents "
            "torn JSON; it is **not** a multi-writer lock."
        ),
        "",
        "### Export-queue exception (claim/lease grade already exists)",
        "",
        (
            "`.eval/export_queue/` is the existing multi-step ops queue with "
            "**claim/lease** coordination (`claim_queue_item`, stale-lease "
            "reclaim) plus atomic row writes. That grade is intentionally "
            "higher than the single-operator-writer stores listed above."
        ),
        "",
        "### Future multi-writer gate",
        "",
        (
            "Any design that allows concurrent writers (multiple operators, "
            "daemon workers, or suite+operator simultaneous mutation) on the "
            "single-operator-writer stores **must land export-queue-grade "
            "coordination first** — claim/lease, compare-and-swap, or an "
            "equivalent fail-closed locking protocol — before broadening "
            "writers. Documentation or CLI convenience alone is insufficient."
        ),
        "",
        "## CLI command tree",
        "",
        "| Path | Kind | Tier | Status | Help / notes |",
        "|:---|:---|:---|:---|:---|",
    ]

    for node in sorted(items, key=lambda n: n.path):
        status, notes = _status_for(node.path)
        tier = _stability_tier(node.path, node.kind)
        help_bits = node.help or "—"
        if notes:
            help_bits = f"{help_bits} — {notes}" if help_bits != "—" else notes
        # Escape pipes in table cells
        help_bits = help_bits.replace("|", "\\|")
        lines.append(f"| `{node.path}` | {node.kind} | {tier} | {status} | {help_bits} |")

    lines.extend(
        [
            "",
            "## Canonical S6 operator surface (Slice 0 lock)",
            "",
            "```text",
        ]
    )
    for cmd in sorted(CANONICAL_COMMANDS):
        if cmd.startswith("eval materialize") or cmd.startswith("eval encode"):
            continue
        lines.append(f"git-cg {cmd} …")
    lines.extend(
        [
            "```",
            "",
            "Corpus helpers also public:",
            "",
            "* `git-cg eval materialize-core-goldens`",
            "* `git-cg eval encode-fixture`",
            "",
            "## Temporary compatibility aliases",
            "",
            "| Alias | Canonical | Removal target |",
            "|:---|:---|:---|",
            f"| `git-cg eval config show` | `git-cg eval opik config show` | {REMOVAL_TARGET} |",
            f"| `git-cg eval export-status` | `git-cg eval export status` | {REMOVAL_TARGET} |",
            f"| `git-cg eval export-retry` | `git-cg eval export retry` | {REMOVAL_TARGET} |",
            f"| `git-cg eval export-drain` | `git-cg eval export drain` | {REMOVAL_TARGET} |",
            "",
            "Deprecation notices:",
            "",
            "* **Human mode:** stderr warning",
            "* **`--json` mode:** structured `warnings[]` on `cli_output_envelope_v1`",
            "",
            "## Supported Python entrypoints (not a general SDK)",
            "",
            "These names are **supported maintainer/harness APIs**. Import paths are",
            "canonical; do not treat the rest of `git_cg.eval*` as a public SDK.",
            "",
            "| Name | Import | Role |",
            "|:---|:---|:---|",
        ]
    )
    for name, module, role in SUPPORTED_PYTHON_ENTRYPOINTS:
        lines.append(f"| `{name}` | `{module}` | {role} |")

    lines.extend(
        [
            "",
            "## Internal (explicitly non-supported)",
            "",
            "* Implementation modules under `git_cg.eval.binding`, `git_cg.eval.mirror`",
            "  internals, `git_cg.eval.scoring.family_*`, private `_` helpers, and",
            "  product ranking paths in `git_cg.main` are **internal**.",
            "* Scripts under `scripts/*` are not a second score law (Slice 8 absorption).",
            "* Optional `just eval-*` wrappers must not become a second command law.",
            "",
            "## JSON envelope",
            "",
            "JSON-capable operator commands emit exactly one",
            "`cli_output_envelope_v1` document on stdout:",
            "",
            "* schema: `schemas/eval/cli_output_envelope_v1.schema.json`",
            "* progress / diagnostics / human deprecations → **stderr**",
            "* deprecations also appear in envelope `warnings[]` in JSON mode",
            "",
            # S6-A08: closed per-command data sketches (fail-closed in --check).
            *render_sketches_markdown(),
            "## Doctor report contract (Slice 4)",
            "",
            "`git-cg eval doctor` (local suite/pin/metric) and `git-cg eval opik",
            "doctor` (secret-safe Opik/export/queue) are **observability-only** and",
            "network-free. Neither mutates product accept, ranking, golden",
            "promotion, or Families A-I authority.",
            "",
            "Each emits a machine-readable check list in envelope `data.checks[]`:",
            "",
            "```text",
            "{check_id, metric_id?, status: pass|warn|fail, severity, message, hint?}",
            "```",
            "",
            "Doctor metric producers (close the S6 phantom-metric gap), projected as",
            "catalog-aligned `ScoreResultV1` rows in `data.scores[]`:",
            "",
            "| Metric | Producer | Severity |",
            "|:---|:---|:---|",
            "| `h.compat_hash_resume` | Slice 3 checkpoint compat vs live preimage | block |",
            "| `h.doctor_green` | Rollup over the doctor check set | warn |",
            "| `h.export_config_resolved` | S4 `resolve_opik_config` / `operator_config_health` | warn |",
            "",
            "**Aggregation rule (locked):** `h.doctor_green` aggregates",
            "**block-severity** checks only. Warn-severity check failures never flip",
            "green → red. This rule is part of the frozen doctor contract.",
            "",
            "Secret safety (S6-C08): every secret-bearing value passes through",
            "`mask_secret()` (`•••[len=N]`). Raw token values and prefixes are",
            "never printed in human or JSON output.",
            "",
            "Exit classes: `0` green · `1` doctor red (block fail) · `2` usage/config",
            "· `3` compatibility mismatch · `4` missing evidence.",
            "",
            "## Triage router contract (Slice 8 / D27)",
            "",
            "`git-cg eval triage` is the offline advisory router that absorbs",
            "`scripts/opik_trace_triage.py`. It composes library engines",
            "(`run_local_doctor`, `list_failures`, `explain`) and emits one",
            "`eval_triage_v0` projection inside `cli_output_envelope_v1`.",
            "",
            "* **Authority:** `advisory_offline_router` (`not_score_law: true`).",
            "* **Not** gold promotion, accept-path, ranking, or Opik",
            "  `user_acceptance` threshold triage.",
            "* Exit precedence: `2` usage → `4` store → `3` doctor compat →",
            "  `1` doctor block-red → `0` advisory success (listed failures alone",
            "  stay `0`).",
            "* Explain auto-selects only when exactly one failing case is present",
            "  (or `--case` is explicit).",
            "",
            "## Regeneration",
            "",
            "```bash",
            "uv run python -m git_cg.eval.api_map --write",
            "uv run python -m git_cg.eval.api_map --check",
            "just eval-api-map-check",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def write_map(path: Path = DEFAULT_MAP_PATH) -> Path:
    """Write the operator API map to ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = render_operator_api_map()
    path.write_text(text, encoding="utf-8")
    return path


def check_map(path: Path = DEFAULT_MAP_PATH) -> tuple[bool, str]:
    """Return (ok, message). Fails on sketch gaps or on-disk map drift.

    S6-A08: every minimum JSON command must have a closed ``data`` sketch.
    Sketch incompleteness fails even before map drift is considered.
    """
    sketch_ok, sketch_msg = validate_sketch_registry()
    if not sketch_ok:
        return False, sketch_msg
    expected = render_operator_api_map()
    if not path.is_file():
        return False, f"missing operator API map: {path}"
    actual = path.read_text(encoding="utf-8")
    if actual != expected:
        return False, f"operator API map drift: {path} (run api_map.py --write)"
    return True, f"ok: {path} matches live Typer tree ({sketch_msg})"


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry for generate/check."""
    parser = argparse.ArgumentParser(description="Generate/check docs/eval/operator_api_map.md")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write the operator API map from the live Typer tree.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the on-disk map drifts from the live tree.",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_MAP_PATH,
        help=f"Map path (default: {DEFAULT_MAP_PATH})",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if not args.write and not args.check:
        # Default: print to stdout
        sys.stdout.write(render_operator_api_map())
        return 0

    if args.write:
        out = write_map(args.path)
        print(f"wrote {out}")

    if args.check:
        ok, msg = check_map(args.path)
        print(msg)
        return 0 if ok else 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
