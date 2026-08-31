#!/usr/bin/env python3
"""Generate docs/cli reference pages from the live Typer trees.

Mirrors the mise-style CLI reference shape:
  - docs/cli/index.md overview
  - one sub-page per command / group

Source of truth: git_cg.main.app + git_cg.eval.cli.eval_app
(and git_cg.eval.api_map for canonical/deprecated/dark-launch metadata).
"""

from __future__ import annotations

import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import click
from click.testing import CliRunner
from typer.main import get_command

# Per-path doc framing beyond the generic S6 authority blurb.
# Keep these short; live help text remains the option/behaviour SoT.
STATUS_OVERRIDE: dict[str, str] = {
    "eval opik verify": "optional / advisory",
}

AUTHORITY_BOUNDARY_EXTRA: dict[str, list[str]] = {
    "eval opik verify": [
        "* Advisory only (`authority=advisory_non_sot`).",
        "* Does not change `eval opik doctor` exit codes or green rollup.",
        "* Does not feed promote, gates, CI merge, or product accept.",
        "* Network and auth failure are warning-only (exit 0).",
        "* Project creation requires `--remote --create-missing`.",
        "* Local project pins and `config/feedback_definitions.json` remain vocabulary/source of truth.",
    ],
}

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from git_cg.eval.api_map import (  # noqa: E402
    CANONICAL_COMMANDS,
    DARK_LAUNCH_HIDDEN_COMMANDS,
    DEPRECATED_ALIASES,
    walk_eval_tree,
)
from git_cg.eval.cli import eval_app  # noqa: E402
from git_cg.main import app as root_app  # noqa: E402

OUT = REPO / "docs" / "cli"


def _is_group(cmd: object) -> bool:
    return callable(getattr(cmd, "list_commands", None)) and callable(getattr(cmd, "get_command", None))


def _docs_help_env() -> dict[str, str]:
    """Environment for non-truncating, plain help capture."""
    env = dict(os.environ)
    # Rich/Typer truncate option names and choice lists under narrow terminals.
    # Docs must publish complete operator-facing tokens, so pin a wide width.
    #
    # Typer reads TERMINAL_WIDTH into typer.rich_utils.MAX_WIDTH at import time.
    # COLUMNS alone is not enough once the module is already imported.
    env["TERMINAL_WIDTH"] = "120"
    env["COLUMNS"] = "120"
    env["TERM"] = "dumb"
    env["NO_COLOR"] = "1"
    env["FORCE_COLOR"] = "0"
    env["_TYPER_FORCE_DISABLE_TERMINAL"] = "1"
    return env


def _force_typer_help_width(width: int = 120) -> None:
    """Override Typer/Rich help width for docs generation after imports."""
    os.environ["TERMINAL_WIDTH"] = str(width)
    os.environ["COLUMNS"] = str(width)
    try:
        import typer.rich_utils as rich_utils

        rich_utils.MAX_WIDTH = width
        # Keep plain docs capture deterministic (no color/force-tty drift).
        rich_utils.FORCE_TERMINAL = False
        rich_utils.COLOR_SYSTEM = None
    except Exception:  # pragma: no cover - defensive for alternate typer builds
        pass


def _plain_blurb(text: str, limit: int) -> str:
    """Normalize help text into a plain one-line blurb for Markdown lists.

    Strips inline backticks / form-feeds, collapses whitespace, and truncates on
    a word boundary with an explicit ellipsis when the limit is exceeded.
    """
    cleaned = (text or "").replace("`", "").replace("\f", " ").replace("\n", " ")
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        return ""
    if len(cleaned) <= limit:
        return cleaned
    cut = cleaned[: max(1, limit - 1)].rstrip()
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0].rstrip(" ,;:.-")
    return f"{cut}…"


def help_for_click(cmd: click.Command, prog: str) -> str:
    """Capture rendered help text for docs pages.

    Typer/rich-click often returns an empty string from ``Command.get_help``
    while still rendering a full panel through the Click runner path.
    Prefer ``CliRunner`` output and normalize the synthetic usage path.
    """
    _force_typer_help_width(120)
    runner = CliRunner(env=_docs_help_env())
    try:
        # Keep env on invoke too: some Rich builds re-read process/console width.
        result = runner.invoke(cmd, ["--help"], color=False, env=_docs_help_env())
        text = (result.output or "").strip()
        if text:
            fixed: list[str] = []
            for line in text.splitlines():
                # Rich help pads lines with trailing spaces; drop them for stable docs.
                line = line.rstrip()
                stripped = line.lstrip()
                indent = line[: len(line) - len(stripped)]
                if stripped.startswith("Usage:"):
                    rest = stripped[len("Usage:") :].lstrip()
                    tokens = rest.split()
                    if tokens:
                        leaf = prog.split()[-1]
                        # Drop synthetic CliRunner root or leaf command token.
                        if tokens[0] in {"root", leaf}:
                            after = rest[len(tokens[0]) :]
                            line = f"{indent}Usage: {prog}{after}"
                        else:
                            line = f"{indent}Usage: {prog} {rest}"
                    else:
                        line = f"{indent}Usage: {prog}"
                fixed.append(line)
            return chr(10).join(fixed).strip()
    except Exception as exc:  # pragma: no cover
        return f"(help unavailable: {exc})"
    ctx = click.Context(cmd, info_name=prog, color=False)
    try:
        fallback = (cmd.get_help(ctx) or "").strip()
        return fallback or f"(help unavailable for {prog})"
    except Exception as exc:  # pragma: no cover
        return f"(help unavailable: {exc})"


def option_rows(cmd: click.Command) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for param in cmd.params:
        if isinstance(param, click.Argument):
            name = (param.name or "ARG").upper()
            req = "yes" if param.required else "no"
            help_text = (getattr(param, "help", None) or "").strip() or "—"
            rows.append((f"`<{name}>`", "arg", f"{help_text} (required={req})"))
        elif isinstance(param, click.Option):
            opts = ", ".join(f"`{o}`" for o in param.opts)
            help_text = (param.help or "").strip() or "—"
            default = ""
            if not param.required and param.default is not None and param.default != () and not callable(param.default):
                default = f" Default: `{param.default!r}`."
            hidden = " *(hidden)*" if getattr(param, "hidden", False) else ""
            rows.append((opts, "flag", f"{help_text}{default}{hidden}"))
    return rows


def write_page(path: Path, title: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {title}\n\n{body.rstrip()}\n", encoding="utf-8")


def slugify(path: str) -> str:
    s = path.strip().lower().replace("git-cg ", "").replace(" ", "-")
    s = re.sub(r"[^a-z0-9._-]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-") or "index"


def eval_page_path(path: str) -> Path:
    parts = path.split()
    assert parts[0] == "eval"
    if len(parts) == 1:
        return OUT / "eval" / "index.md"
    return OUT / "eval" / Path(*parts[1:]).with_suffix(".md")


def _rel(from_file: Path, to_file: Path) -> str:
    return Path(os.path.relpath(to_file, start=from_file.parent)).as_posix()


def generate() -> None:
    _force_typer_help_width(120)
    OUT.mkdir(parents=True, exist_ok=True)
    for p in OUT.rglob("*.md"):
        p.unlink()

    root_click = get_command(root_app)
    root_help = help_for_click(root_click, "git-cg")
    rctx = click.Context(root_click)

    root_cmds: list[tuple[str, click.Command]] = []
    for name in sorted(root_click.list_commands(rctx) or []):
        child = root_click.get_command(rctx, name)
        if child is not None:
            root_cmds.append((name, child))

    root_pages: list[tuple[str, str, str, bool]] = []
    for name, cmd in root_cmds:
        full = f"git-cg {name}"
        page_slug = slugify(full)
        is_group = _is_group(cmd)
        help_text = help_for_click(cmd, full)
        short_src = (cmd.help or cmd.short_help or "").strip()
        short = short_src.splitlines()[0] if short_src else ""
        body_parts = [
            f"> **Usage:** `{full} …`",
            "",
            short or "Root CLI surface.",
            "",
            "## Help",
            "",
            "```text",
            help_text.rstrip(),
            "```",
            "",
        ]
        rows = option_rows(cmd)
        if rows:
            body_parts += [
                "## Parameters",
                "",
                "| Name | Kind | Description |",
                "|:---|:---|:---|",
            ]
            for a, b, c in rows:
                body_parts.append(f"| {a} | {b} | {c.replace('|', '\\|')} |")
            body_parts.append("")
        if is_group:
            gctx = click.Context(cmd)
            kids = sorted(cmd.list_commands(gctx) or [])
            if kids:
                body_parts += ["## Subcommands", ""]
                for k in kids:
                    child = cmd.get_command(gctx, k)
                    ch_src = ((child.help or child.short_help or "") if child else "").strip()
                    ch_short = ch_src.splitlines()[0] if ch_src else ""
                    body_parts.append(f"* `{full} {k}` — {ch_short}")
                body_parts.append("")
        if name == "eval":
            body_parts += [
                "## Eval operator surface",
                "",
                "The evaluation harness operator API is documented on dedicated pages:",
                "",
                "* [Eval overview](eval/index.md)",
                "* [Operator API map](../eval/operator_api_map.md)",
                "",
                "Dark-launched commands (currently `eval dogfood`) stay callable but are "
                "hidden from regular `git-cg eval --help`.",
                "",
            ]
        write_page(OUT / f"{page_slug}.md", full, "\n".join(body_parts))
        root_pages.append((full, page_slug, short, is_group))

    eval_nodes = walk_eval_tree("eval")
    eval_meta = {n.path: n for n in eval_nodes}
    eval_pages: list[tuple[str, Path, str, str, str]] = []

    for node in sorted(eval_nodes, key=lambda n: n.path):
        full = f"git-cg {node.path}"
        cmd: click.Command | None = get_command(eval_app)
        parts = node.path.split()[1:]
        ok = True
        for part in parts:
            if cmd is None or not _is_group(cmd):
                ok = False
                break
            gctx = click.Context(cmd)
            nxt = cmd.get_command(gctx, part)
            if nxt is None:
                ok = False
                break
            cmd = nxt
        help_text = help_for_click(cmd, full) if ok and cmd is not None else node.help
        if node.path in STATUS_OVERRIDE:
            status = STATUS_OVERRIDE[node.path]
        else:
            status_bits: list[str] = []
            if node.path in DEPRECATED_ALIASES:
                status_bits.append(f"deprecated alias → `{DEPRECATED_ALIASES[node.path]}`")
            if node.path in DARK_LAUNCH_HIDDEN_COMMANDS:
                status_bits.append("dark-launch (hidden from regular help)")
            if node.path in CANONICAL_COMMANDS:
                status_bits.append("canonical S6 surface")
            status = ", ".join(status_bits) if status_bits else node.kind

        this_file = eval_page_path(node.path)
        body: list[str] = [
            f"> **Usage:** `{full} …`  ",
            f"> **Kind:** `{node.kind}` · **Status:** {status}",
            "",
            node.help or "Eval operator command.",
            "",
            "## Authority boundary",
            "",
        ]
        if node.path in AUTHORITY_BOUNDARY_EXTRA:
            body.extend(AUTHORITY_BOUNDARY_EXTRA[node.path])
        else:
            body.extend(
                [
                    "* Does **not** re-rank product intents or rewrite SOP authority.",
                    "* Does **not** sole-promote gold as CI authority.",
                    "* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.",
                ]
            )
        body += [
            "",
            "## Help",
            "",
            "```text",
            help_text.rstrip(),
            "```",
            "",
        ]
        if ok and cmd is not None:
            rows = option_rows(cmd)
            if rows:
                body += [
                    "## Parameters",
                    "",
                    "| Name | Kind | Description |",
                    "|:---|:---|:---|",
                ]
                for a, b, c in rows:
                    body.append(f"| {a} | {b} | {c.replace('|', '\\|')} |")
                body.append("")
        if node.children:
            body += ["## Children", ""]
            for ch in node.children:
                child_path = f"{node.path} {ch}"
                child_file = eval_page_path(child_path)
                link = _rel(this_file, child_file)
                meta = eval_meta.get(child_path)
                blurb = _plain_blurb(meta.help if meta else "", 140)
                body.append(f"* [`git-cg {child_path}`]({link}) — {blurb}")
            body.append("")
        overview_link = _rel(this_file, OUT / "index.md")
        api_link = _rel(this_file, REPO / "docs" / "eval" / "operator_api_map.md")
        guide_link = _rel(this_file, REPO / "docs" / "eval" / "README.md")
        body += [
            "## See also",
            "",
            f"* [CLI overview]({overview_link})",
            f"* [Operator API map]({api_link})",
            f"* [Eval operator guide]({guide_link})",
            "",
        ]
        title = full if node.path != "eval" else "git-cg eval"
        write_page(this_file, title, "\n".join(body))
        eval_pages.append((node.path, this_file, node.kind, status, node.help))

    groups: dict[str, list[tuple[str, Path, str, str, str]]] = defaultdict(list)
    for path, page, kind, status, help_ in eval_pages:
        if path == "eval":
            continue
        groups[path.split()[1]].append((path, page, kind, status, help_))

    overview = [
        "The `git-cg` CLI is the **primary public operator API** for commit generation "
        "and the offline Opik evaluation harness.",
        "",
        "This reference mirrors the live Typer tree (same source of truth as "
        "`docs/eval/operator_api_map.md`). Each command has a dedicated page with usage, "
        "parameters, and authority boundaries — modeled after the mise CLI reference layout "
        "(overview + one page per command).",
        "",
        "## Design goals",
        "",
        "* **Deterministic semantic contract first** — ranking/SOP authority is never overridden by eval UX.",
        "* **Offline Lane A by default** for eval operator flows; network/dogfood surfaces are explicit.",
        "* **Secret-safe projection** on doctor/config/export paths.",
        "* **CLI-first docs** — not a general Python SDK and not full-package autodoc.",
        "",
        "## Root commands",
        "",
        "| Command | Description |",
        "|:---|:---|",
    ]
    for full, slug, short, is_group in root_pages:
        overview.append(f"| [`{full}`]({slug}.md) | {short or ('group' if is_group else 'command')} |")
    overview += [
        "",
        "## Global flags",
        "",
        "```text",
        root_help.rstrip(),
        "```",
        "",
        "## Evaluation harness (`git-cg eval`)",
        "",
        "See the [eval overview](eval/index.md) for nested groups. Canonical S6 operator commands:",
        "",
    ]
    for c in sorted(CANONICAL_COMMANDS):
        page = eval_page_path(c)
        link = _rel(OUT / "index.md", page)
        overview.append(f"* [`git-cg {c}`]({link})")
    overview += ["", "### Groups and aliases", ""]
    for top in sorted(groups):
        overview.append(f"* **`git-cg eval {top}`**")
        for path, page, _kind, _status, help_ in sorted(groups[top]):
            link = _rel(OUT / "index.md", page)
            blurb = _plain_blurb(help_ or "", 100)
            overview.append(f"  * [`git-cg {path}`]({link}) — {blurb}")
    overview += [
        "",
        "## Stability tiers",
        "",
        "| Tier | Surface | Promise |",
        "|:---|:---|:---|",
        "| Public | `git-cg` / `git-cg eval …` | Primary operator API; help-tested |",
        "| Supported | Selected `git_cg.eval*` entrypoints in the operator API map | Maintainer/harness-stable |",
        "| Internal | All other modules | No compatibility promise |",
        "",
        "Deprecated aliases remove at **first minor release after S6 GA**.",
        "",
        "## Related docs",
        "",
        "* [Usage (usage-cli generated)](../usage.md)",
        "* [Operator API map](../eval/operator_api_map.md)",
        "* [Eval guide](../eval/README.md)",
        "* [Development guide](../DEVELOPMENT.md)",
        "",
        "## Regeneration",
        "",
        "```bash",
        "uv run python tools/gen_cli_docs.py",
        "# or: just gen-cli-docs",
        "# or: mise run docs:cli",
        "```",
        "",
    ]
    write_page(OUT / "index.md", "CLI reference", "\n".join(overview))
    (OUT / ".generated").write_text(
        "Generated from live Typer trees (git_cg.main.app + git_cg.eval.cli.eval_app).\n"
        "Regenerate via: uv run python tools/gen_cli_docs.py\n",
        encoding="utf-8",
    )
    print(f"wrote {len(root_pages)} root pages + {len(eval_pages)} eval pages → {OUT}")


if __name__ == "__main__":
    generate()
