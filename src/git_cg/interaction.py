from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from typing import Literal, cast

from rich.console import Console
from rich.panel import Panel

from git_cg.models import IssueReference

Action = Literal["Commit", "Edit", "Regenerate", "Add issue reference", "Cancel"]
IssueReferenceTypeChoice = Literal["Resolves", "Refs", "Closes", "Fixes", "Back"]

ACTIONS: tuple[Action, ...] = ("Commit", "Edit", "Regenerate", "Add issue reference", "Cancel")
ISSUE_REFERENCE_TYPE_CHOICES: tuple[IssueReferenceTypeChoice, ...] = ("Resolves", "Refs", "Closes", "Fixes", "Back")


def emit_terminal_bell() -> None:
    """Emit a passive terminal bell notification."""
    print("\a", end="", flush=True)


def can_open_tty() -> bool:
    """Return True when an interactive terminal device is available."""
    try:
        with open("/dev/tty"):
            return True
    except OSError:
        return False


def _print_tty_message(message: str, *, style: str = "yellow") -> None:
    """Print a short message to /dev/tty when available."""
    try:
        with open("/dev/tty", "w", encoding="utf-8", errors="ignore") as tty_out:
            Console(file=tty_out, force_terminal=True).print(f"[{style}]{message}[/{style}]")
    except OSError:
        return


def _run_gum_command(
    command: list[str],
    *,
    title: str | None = None,
    body: str | None = None,
    status_text: str | None = None,
    prompt_text: str | None = None,
) -> str | None:
    """Run a gum command on /dev/tty and return stripped stdout."""
    if shutil.which("gum") is None:
        return None

    try:
        with (
            open("/dev/tty", encoding="utf-8", errors="ignore") as tty_in,
            open("/dev/tty", "w", encoding="utf-8", errors="ignore") as tty_out,
        ):
            tty_console = Console(file=tty_out, force_terminal=True)
            if body is not None:
                tty_console.print(Panel(body, title=title, border_style="green"))
            elif title:
                tty_console.print(f"[bold green]{title}[/bold green]")

            if status_text:
                tty_console.print(f"[bold magenta]{status_text}[/bold magenta]")

            if prompt_text:
                tty_console.print(prompt_text)

            result = subprocess.run(
                command,
                stdin=tty_in,
                stdout=subprocess.PIPE,
                stderr=tty_out,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                return None

            stripped = result.stdout.strip()
            return stripped or None
    except FileNotFoundError, OSError:
        return None


def prompt_with_gum(title: str, body: str, *, status_text: str | None = None) -> Action | None:
    """Prompt for the next action using gum on /dev/tty."""
    choice = _run_gum_command(
        ["gum", "choose", *ACTIONS],
        title=title,
        body=body,
        status_text=status_text,
        prompt_text="[bold cyan]Select next action[/bold cyan]",
    )
    if choice in ACTIONS:
        return cast(Action, choice)
    return None


def prompt_issue_reference_type() -> IssueReferenceTypeChoice | None:
    """Prompt for the issue-reference verb using a gum-native submenu."""
    choice = _run_gum_command(
        ["gum", "choose", *ISSUE_REFERENCE_TYPE_CHOICES],
        title="Add issue reference",
        prompt_text="[bold cyan]Select issue reference type[/bold cyan]",
    )
    if choice in ISSUE_REFERENCE_TYPE_CHOICES:
        return cast(IssueReferenceTypeChoice, choice)
    return None


def prompt_issue_number() -> int | None:
    """Prompt for a numeric issue number and validate digits-only input."""
    while True:
        raw_value = _run_gum_command(
            ["gum", "input", "--placeholder", "80", "--prompt", "# "],
            title="Add issue reference",
            prompt_text="[bold cyan]Enter issue number[/bold cyan]",
        )
        if raw_value is None:
            return None
        if raw_value.isdigit():
            return int(raw_value)
        _print_tty_message("Issue number must contain digits only.")


def format_issue_reference_status(issue_references: Sequence[IssueReference] | None) -> str:
    """Return a compact preview string for the current issue-reference review state."""
    if not issue_references:
        return "Current issue reference: None"
    if len(issue_references) == 1:
        return f"Current issue reference: {issue_references[0]}"
    rendered_references = ", ".join(str(issue_reference) for issue_reference in issue_references)
    return f"Current issue references: {rendered_references}"
