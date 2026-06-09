from __future__ import annotations

import shutil
import subprocess
from typing import Literal

from rich.console import Console
from rich.panel import Panel

Action = Literal["Commit", "Edit", "Regenerate", "Cancel"]
ACTIONS: tuple[Action, ...] = ("Commit", "Edit", "Regenerate", "Cancel")


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


def prompt_with_gum(title: str, body: str) -> Action | None:
    """Prompt for the next action using gum on /dev/tty.

    Returns None if gum or /dev/tty is unavailable, allowing the caller to
    degrade gracefully to the non-interactive path.
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

            choice = result.stdout.strip()
            if choice in ACTIONS:
                return choice  # type: ignore[return-value]

            return "Commit"
    except FileNotFoundError, OSError:
        return None
