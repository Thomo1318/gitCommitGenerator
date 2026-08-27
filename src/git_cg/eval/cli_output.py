"""S6 CLI output helpers: ``cli_output_envelope_v1`` + deprecation notices.

Slice 2 establishes the shared machine contract used by operator commands:

* stdout carries **exactly one** ``cli_output_envelope_v1`` document in ``--json``
  mode (schema frozen in Slice 1);
* progress / diagnostics / human deprecation text go to **stderr**;
* deprecations also surface as structured ``warnings[]`` items in JSON mode.

This module is import-light (stdlib + typer only) so ``git_cg.eval.cli`` can
depend on it without pulling binder or Opik.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

import typer

SCHEMA_VERSION = "cli_output_envelope_v1"

# Locked Slice 0 / Slice 2 policy constants (documented in operator API map).
REMOVAL_TARGET = "first minor release after S6 GA"
DEFAULT_KEEP_LAST = 10

DEPRECATION_CODE = "EVAL_CLI_DEPRECATED"
NOT_IMPLEMENTED_CODE = "EVAL_CLI_NOT_IMPLEMENTED"


def envelope_message(
    code: str,
    message: str,
    *,
    hint: str | None = None,
) -> dict[str, str]:
    """Build a closed ``{code, message, hint?}`` envelope message item."""
    item: dict[str, str] = {"code": code, "message": message}
    if hint:
        item["hint"] = hint
    return item


def build_envelope(
    command: str,
    *,
    ok: bool,
    data: Mapping[str, Any] | None = None,
    errors: Sequence[Mapping[str, str]] | None = None,
    warnings: Sequence[Mapping[str, str]] | None = None,
    meta: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct a ``cli_output_envelope_v1`` document (not yet emitted)."""
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "ok": ok,
        "data": dict(data or {}),
        "errors": [dict(item) for item in (errors or ())],
        "warnings": [dict(item) for item in (warnings or ())],
    }
    if meta:
        payload["meta"] = dict(meta)
    return payload


def emit_json_envelope(envelope: Mapping[str, Any]) -> None:
    """Write exactly one envelope document to stdout (compact, stable keys)."""
    typer.echo(json.dumps(envelope, indent=2, sort_keys=True))


def emit_human_line(message: str, *, err: bool = False) -> None:
    """Write a human-readable line (stderr when ``err`` is true)."""
    typer.echo(message, err=err)


def deprecation_warning(
    *,
    deprecated: str,
    canonical: str,
    removal_target: str = REMOVAL_TARGET,
) -> dict[str, str]:
    """Build the structured deprecation warning item for aliases."""
    return envelope_message(
        DEPRECATION_CODE,
        (f"{deprecated!r} is a temporary compatibility alias; use {canonical!r} instead."),
        hint=f"Scheduled removal: {removal_target}.",
    )


def emit_deprecation_human(
    *,
    deprecated: str,
    canonical: str,
    removal_target: str = REMOVAL_TARGET,
) -> None:
    """Emit a human deprecation notice on stderr."""
    warning = deprecation_warning(
        deprecated=deprecated,
        canonical=canonical,
        removal_target=removal_target,
    )
    line = f"warning: {warning['message']}"
    if hint := warning.get("hint"):
        line = f"{line} ({hint})"
    emit_human_line(line, err=True)


def not_implemented_error(command: str, *, slice_hint: str) -> dict[str, str]:
    """Structured error for thin Slice 2 stubs (behaviour lands later)."""
    return envelope_message(
        NOT_IMPLEMENTED_CODE,
        f"{command} is registered but not implemented yet.",
        hint=f"Behaviour lands in {slice_hint}.",
    )


def emit_not_implemented(
    command: str,
    *,
    slice_hint: str,
    as_json: bool = False,
    exit_code: int = 2,
) -> None:
    """Emit a not-implemented response and exit.

    Human mode: one stderr line + non-zero exit.
    JSON mode: one ``cli_output_envelope_v1`` on stdout with ``ok=false``.
    """
    err = not_implemented_error(command, slice_hint=slice_hint)
    if as_json:
        emit_json_envelope(
            build_envelope(
                command,
                ok=False,
                data={"status": "not_implemented", "slice_hint": slice_hint},
                errors=[err],
            )
        )
    else:
        line = f"{command}: {err['message']}"
        if hint := err.get("hint"):
            line = f"{line} ({hint})"
        emit_human_line(line, err=True)
    raise typer.Exit(code=exit_code)


__all__ = [
    "DEFAULT_KEEP_LAST",
    "DEPRECATION_CODE",
    "NOT_IMPLEMENTED_CODE",
    "REMOVAL_TARGET",
    "SCHEMA_VERSION",
    "build_envelope",
    "deprecation_warning",
    "emit_deprecation_human",
    "emit_human_line",
    "emit_json_envelope",
    "emit_not_implemented",
    "envelope_message",
    "not_implemented_error",
]
