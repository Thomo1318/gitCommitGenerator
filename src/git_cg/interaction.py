from __future__ import annotations

import shutil
import subprocess
from typing import Literal

from rich.console import Console
from rich.panel import Panel

Action = Literal["Commit", "Edit", "Regenerate", "Cancel"]
ACTIONS: tuple[Action, ...] = ("Commit", "Edit", "Regenerate", "Cancel")


def emit_terminal_bell() -> None:
    """
    Emit the terminal bell (ASCII BEL) as a passive notification.
    
    Writes the ASCII bell character to standard output and flushes the stream immediately.
    """
    print("\a", end="", flush=True)


def can_open_tty() -> bool:
    """
    Check whether an interactive terminal device (/dev/tty) can be opened.
    
    Returns:
        bool: `True` if `/dev/tty` can be opened, `False` otherwise.
    """
    try:
        with open("/dev/tty"):
            return True
    except OSError:
        return False


def prompt_with_gum(title: str, body: str) -> Action | None:
    """
    Prompt the user to select an Action using the external `gum` chooser on /dev/tty.
    
    Displays `body` inside a titled panel using a console bound to `/dev/tty`, then runs `gum choose` with the available ACTIONS. If the chooser succeeds and produces a valid selection, that Action is returned; otherwise `None` is returned to allow non-interactive fallback.
    
    Parameters:
        title (str): Title shown on the panel.
        body (str): Body text displayed inside the panel.
    
    Returns:
        Action | None: The selected `Action` when a valid choice is made, or `None` if `gum` or `/dev/tty` is unavailable, the chooser exits with a non-zero status, or the output is not one of the known actions.
    """
    if shutil.which("gum") is None:
        return None

    try:
        with (
            open("/dev/tty", encoding="utf-8", errors="ignore") as tty_in,
            open("/dev/tty", "w", encoding="utf-8", errors="ignore") as tty_out,
        ):
            tty_console = Console(file=tty_out, force_terminal=True)
            tty_console.print(Panel(body, title=title, border_style="green"))
            tty_console.print("[bold cyan]Select next action[/bold cyan]")

            result = subprocess.run(
                ["gum", "choose", *ACTIONS],
                stdin=tty_in,
                stdout=subprocess.PIPE,
                stderr=tty_out,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                return None

            choice = result.stdout.strip()
            if choice in ACTIONS:
                return choice  # type: ignore[return-value]

            return None
    except FileNotFoundError, OSError:
        return None
