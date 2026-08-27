"""macOS alerter integration for commit message notifications.

Provides a native macOS notification interface using the alerter tool to prompt
the user with generated commit messages and capture their chosen action.
"""

import subprocess
import sys
from typing import Literal

Action = Literal["Commit", "Edit", "Regenerate", "Cancel", "Timeout", "Error"]


def prompt_commit_message(title: str, body: str) -> Action:
    """
    Prompt the user using macOS `alerter`.
    Returns the action selected by the user.
    """
    # Prepare alerter command
    # Note: alerter ignores -timeout 0 on some systems, so we can omit timeout or set a high value if needed,
    # but by default it stays until clicked if we provide actions.
    cmd = [
        "alerter",
        "--title",
        "git-cg: Commit Generated",
        "--subtitle",
        title,
        "--message",
        body,
        "--actions",
        "Commit,Edit,Regenerate,Cancel",
        "--defaultAction",
        "Commit",
        "--timeout",
        "0",
    ]

    try:
        # capture_output to get the clicked action from stdout
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        output = result.stdout.strip()

        # Alerter returns the clicked action
        if output in ("Commit", "Edit", "Regenerate", "Cancel"):
            return output  # type: ignore
        elif "@TIMEOUT" in output:
            return "Timeout"
        elif "@CLOSED" in output:
            # If the user closed the notification without clicking an action
            return "Cancel"
        else:
            # Fallback for unexpected output
            return "Commit"

    except subprocess.CalledProcessError as e:
        print(f"alerter failed with code {e.returncode}: {e.stderr}", file=sys.stderr)
        return "Error"
    except FileNotFoundError:
        return "Error"
