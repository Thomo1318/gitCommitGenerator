"""Typer/Rich help theme defaults for git-cg operator UX.

Typer renders ``--help`` via ``typer.rich_utils`` module-level style strings.
We set a small gold-default palette once at import so root and nested surfaces
share readable help body text and visible panel chrome.

This does not change command semantics, ranking, or help text content.
"""

from __future__ import annotations

import typer.rich_utils as rich_utils


def apply_cli_theme() -> None:
    """Apply preferred Rich help styles for operator readability.

    Defaults we override (Typer stock → gold trial):
    - ``STYLE_HELPTEXT``: ``dim`` → normal (body prose readable)
    - ``STYLE_HELPTEXT_FIRST_LINE``: empty → ``bold`` (lead sentence stands out)
    - ``STYLE_OPTIONS_PANEL_BORDER``: ``dim`` → ``cyan`` (Options box visible)
    - ``STYLE_COMMANDS_PANEL_BORDER``: ``dim`` → ``cyan`` (Commands/workflow panels)
    """
    rich_utils.STYLE_HELPTEXT = ""
    rich_utils.STYLE_HELPTEXT_FIRST_LINE = "bold"
    rich_utils.STYLE_OPTIONS_PANEL_BORDER = "cyan"
    rich_utils.STYLE_COMMANDS_PANEL_BORDER = "cyan"
