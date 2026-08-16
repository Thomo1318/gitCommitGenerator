"""S3 message_versions hooks (D12 / M7).

Builds the ``message_versions[]`` item list carried on a
``commit_session_thread_v1`` twin. Each item records a real message version —
``generated`` (best-effort redacted draft), ``edited`` (draft ≠ final), or
``final_accept`` (authoritative ``COMMIT_EDITMSG`` bytes) — with its SHA-256 and
evidence source. **Never invent intermediate versions without evidence** (M7):
only the versions actually observed are emitted.

Item shape (D12, locked)::

    {
        "kind": "generated" | "edited" | "final_accept",
        "message": "<text>",
        "message_sha256": "<sha256 hex>",
        "source": "telemetry_state" | "commit_editmsg" | "classify_edit",
    }

No network. No Opik import. Pure and deterministic.
"""

from __future__ import annotations

from typing import Any

from git_cg.eval.binding.binder import message_sha256_bytes

__all__ = [
    "MESSAGE_VERSION_KINDS",
    "MESSAGE_VERSION_SOURCES",
    "MessageVersionError",
    "build_message_versions",
]

#: D12 — allowed ``kind`` values for a message_versions item.
MESSAGE_VERSION_KINDS: frozenset[str] = frozenset({"generated", "edited", "final_accept"})

#: D12 — allowed ``source`` values for a message_versions item.
MESSAGE_VERSION_SOURCES: frozenset[str] = frozenset({"telemetry_state", "commit_editmsg", "classify_edit"})


class MessageVersionError(ValueError):
    """message_versions construction failure (fail closed)."""


def _item(
    kind: str,
    message: str,
    source: str,
    *,
    message_bytes: bytes | None = None,
) -> dict[str, Any]:
    """Build one D12 message-version item: kind / message / sha256 / source.

    Fails closed on unknown ``kind``/``source`` or blank non-string messages.

    Hash authority is :func:`message_sha256_bytes`. When ``message_bytes`` is
    provided (the exact accepted ``COMMIT_EDITMSG`` bytes for
    ``final_accept``), those original bytes are hashed so the version hash
    matches the bundle's ``final_message_sha256`` even if the stored text is a
    UTF-8 replacement projection of invalid input. Without ``message_bytes``,
    the UTF-8 encoding of ``message`` is hashed (Family A text compatibility).
    """
    if kind not in MESSAGE_VERSION_KINDS:
        raise MessageVersionError(f"message version kind must be one of {sorted(MESSAGE_VERSION_KINDS)}: {kind!r}")
    if source not in MESSAGE_VERSION_SOURCES:
        raise MessageVersionError(
            f"message version source must be one of {sorted(MESSAGE_VERSION_SOURCES)}: {source!r}"
        )
    if not isinstance(message, str) or not message.strip():
        raise MessageVersionError(f"message version {kind!r} requires non-empty message text")
    return {
        "kind": kind,
        "message": message,
        "message_sha256": message_sha256_bytes(message if message_bytes is None else message_bytes),
        "source": source,
    }


def build_message_versions(
    *,
    generated_message: str | None = None,
    final_message: str | None = None,
    final_message_bytes: bytes | None = None,
    edited_message: str | None = None,
    edited: bool | None = None,
) -> list[dict[str, Any]]:
    """Build the ``message_versions[]`` list from real evidence (D12/M7).

    Inclusion law:

    * ``generated`` — included when ``generated_message`` is present
      (``GenerationTelemetry.generated_message``; best-effort redacted draft,
      **not** guaranteed raw model output — NTH-U5).
    * ``final_accept`` — included when ``final_message`` (authoritative
      ``COMMIT_EDITMSG`` text projection) is present. Pass
      ``final_message_bytes`` whenever the exact accepted bytes are available
      so the version hash stays aligned with the bundle hash under invalid
      UTF-8 replacement projection (N19.4 / N20.3).
    * ``edited`` — included only when there is real edit evidence: an explicit
      ``edited_message``, or ``edited=True`` (e.g. ``classify_edit`` reports an
      edit) with a draft that differs from the final. Never invented.

    Versions are emitted in chronological order: generated → edited → final.
    """
    versions: list[dict[str, Any]] = []

    if generated_message is not None and generated_message.strip():
        versions.append(_item("generated", generated_message, "telemetry_state"))

    # Edit evidence: explicit edited text, or a draft that differs from final.
    has_edit_evidence = False
    edit_text: str | None = None
    if edited_message is not None and edited_message.strip():
        has_edit_evidence = True
        edit_text = edited_message
    elif edited and generated_message and final_message and generated_message != final_message:
        has_edit_evidence = True
        edit_text = final_message  # the post-edit state observed at accept time
    if has_edit_evidence and edit_text is not None:
        versions.append(_item("edited", edit_text, "classify_edit"))

    if final_message is not None and final_message.strip():
        versions.append(
            _item(
                "final_accept",
                final_message,
                "commit_editmsg",
                message_bytes=final_message_bytes,
            )
        )

    return versions
