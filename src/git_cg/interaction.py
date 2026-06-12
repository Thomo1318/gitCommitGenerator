from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from typing import Literal, cast

from rich.console import Console
from rich.panel import Panel

from git_cg.models import IssueReference

Action = Literal[
    "Commit",
    "Edit",
    "Regenerate",
    "Add issue reference",
    "Add regenerate guidance",
    "Clear regenerate guidance",
    "Cancel",
]
IssueReferenceTypeChoice = Literal["Resolves", "Refs", "Closes", "Fixes", "Back"]

ACTIONS: tuple[Action, ...] = (
    "Commit",
    "Edit",
    "Regenerate",
    "Add issue reference",
    "Add regenerate guidance",
    "Clear regenerate guidance",
    "Cancel",
)
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
        str | None: The command's stdout with surrounding whitespace removed, or `None` if gum is not available, the command exits non-zero, or the output is empty.
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
    Prompt for an issue number using an interactive TTY prompt.
    
    The prompt repeats until the user enters a positive integer or cancels. Invalid inputs produce a brief TTY message and re-prompt.
    
    Returns:
        int | None: The entered issue number (an integer greater than zero), or None if the prompt was cancelled or fails.
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


def prompt_regeneration_guidance(current_guidance: str | None = None) -> str | None:
    """
    Prompt the user to enter a short line of guidance for the next regenerate action.
    
    The input is normalised by collapsing internal whitespace and trimming, and validated to be non-empty and at most 200 characters. The provided current_guidance, if any, is shown as contextual status only and is not included in the returned value.
    
    Parameters:
        current_guidance (str | None): Existing guidance to display as status context, or `None` if none.
    
    Returns:
        str | None: The normalised guidance string when valid, or `None` if the prompt was cancelled.
    """
    while True:
        raw_value = _run_gum_command(
            ["gum", "input", "--placeholder", "This is a feature, not a fix.", "--prompt", "> "],
            title="Add regenerate guidance",
            status_text=format_regeneration_guidance_status(current_guidance),
            prompt_text="[bold cyan]Enter short guidance for the next regenerate[/bold cyan]",
        )
        if raw_value is None:
            return None

        normalized_value = " ".join(raw_value.split()).strip()
        if not normalized_value:
            _print_tty_message("Regeneration guidance cannot be empty.")
            continue
        if len(normalized_value) > 200:
            _print_tty_message("Regeneration guidance must be 200 characters or fewer.")
            continue
        return normalized_value


def format_regeneration_guidance_status(regeneration_guidance: str | None, *, max_length: int = 80) -> str:
    """
    Produce a single-line status describing the current regeneration guidance.
    
    Parameters:
        regeneration_guidance (str | None): Current guidance text, or None/empty if absent.
        max_length (int): Maximum number of characters to include from the guidance before truncation.
    
    Returns:
        str: "'Regeneration guidance: None'" when `regeneration_guidance` is falsy; otherwise
        "Regeneration guidance: <text>". If the guidance exceeds `max_length` characters it is
        truncated and suffixed with "..." .
    """
    if not regeneration_guidance:
        return "Regeneration guidance: None"

    normalized_guidance = " ".join(regeneration_guidance.split()).strip()
    if len(normalized_guidance) <= max_length:
        return f"Regeneration guidance: {normalized_guidance}"
    truncated_guidance = normalized_guidance[: max_length - 3].rstrip() + "..."
    return f"Regeneration guidance: {truncated_guidance}"


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
