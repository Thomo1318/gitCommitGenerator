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
    """
    Emit an ASCII terminal bell to stdout.
    
    Writes the ASCII BEL character ('\a') to standard output without a trailing newline and flushes the stream so the bell is emitted immediately.
    """
    print("\a", end="", flush=True)


def can_open_tty() -> bool:
    """
    Determine whether an interactive terminal device is available.
    
    Returns:
        True if `/dev/tty` can be opened, False otherwise.
    """
    try:
        with open("/dev/tty"):
            return True
    except OSError:
        return False


def _print_tty_message(message: str, *, style: str = "yellow") -> None:
    """
    Write a styled message to /dev/tty when available.
    
    If the TTY cannot be opened the function returns silently without raising.
    
    Parameters:
    	message (str): Text to print to the TTY.
    	style (str): Rich style tag name used to wrap the message (default "yellow").
    """
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
    """
    Run a gum command bound to the controlling TTY, optionally render prompt text beforehand, and return the trimmed output.
    
    Parameters:
    	command (list[str]): The gum command and its arguments to execute.
    	title (str | None): Optional title to render above the prompt.
    	body (str | None): Optional body text to render in a bordered panel below the title.
    	status_text (str | None): Optional status line to render before invoking the command.
    	prompt_text (str | None): Optional prompt line to display prior to running the command.
    
    Returns:
    	str | None: The command's stdout with surrounding whitespace removed, or `None` if gum is not available, the command exits non‑zero, or the output is empty.
    """
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
    """
    Show an interactive menu on /dev/tty for choosing the next action.
    
    Parameters:
        title (str): Title displayed above the menu.
        body (str): Body text or instructions shown in the menu panel.
        status_text (str | None): Optional status text displayed above the prompt.
    
    Returns:
        Action | None: The selected `Action` if it matches a known choice, `None` if the prompt failed or returned an unexpected value.
    """
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
    """
    Prompt the user to select an issue-reference verb from a gum submenu.
    
    Returns:
        choice (IssueReferenceTypeChoice | None): The selected issue-reference type, or `None` if the prompt was cancelled or returned an invalid choice.
    """
    choice = _run_gum_command(
        ["gum", "choose", *ISSUE_REFERENCE_TYPE_CHOICES],
        title="Add issue reference",
        prompt_text="[bold cyan]Select issue reference type[/bold cyan]",
    )
    if choice in ISSUE_REFERENCE_TYPE_CHOICES:
        return cast(IssueReferenceTypeChoice, choice)
    return None


def prompt_issue_number() -> int | None:
    """
    Prompt the user for an issue number, re-prompting until a digits-only value is provided or the prompt is cancelled.
    
    Returns:
        int: The entered issue number.
        None: If the prompt is cancelled or fails.
    """
    while True:
        raw_value = _run_gum_command(
            ["gum", "input", "--placeholder", "80", "--prompt", "# "],
            title="Add issue reference",
            prompt_text="[bold cyan]Enter issue number[/bold cyan]",
        )
        if raw_value is None:
            return None
        if raw_value.isdigit():
            issue_num = int(raw_value)
            if issue_num > 0:
                return issue_num
            _print_tty_message("Issue number must be greater than zero.")
            continue
        _print_tty_message("Issue number must contain digits only.")


def format_issue_reference_status(issue_references: Sequence[IssueReference] | None) -> str:
    """
    Render a compact status line describing the current issue reference(s).
    
    Parameters:
        issue_references (Sequence[IssueReference] | None): Sequence of issue references to describe, or `None`.
    
    Returns:
        str: A status string. If `issue_references` is empty or `None` returns "Current issue reference: None"; if it contains one item returns "Current issue reference: <item>"; if it contains multiple items returns "Current issue references: <item1>, <item2>, ...".
    """
    if not issue_references:
        return "Current issue reference: None"
    if len(issue_references) == 1:
        return f"Current issue reference: {issue_references[0]}"
    rendered_references = ", ".join(str(issue_reference) for issue_reference in issue_references)
    return f"Current issue references: {rendered_references}"
