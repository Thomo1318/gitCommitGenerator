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


def _item(kind: str, message: str, source: str) -> dict[str, Any]:
    """
    Create a validated message-version record with its SHA-256 hash.
    
    Parameters:
        kind (str): Version kind, such as ``generated``, ``edited``, or
            ``final_accept``.
        message (str): Non-empty message text.
        source (str): Evidence source for the version.
    
    Returns:
        dict[str, Any]: A message-version record containing the kind, message,
            SHA-256 hash, and source.
    
    Raises:
        MessageVersionError: If the kind or source is unsupported, or the message
            is empty or not a string.
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
        "message_sha256": message_sha256_bytes(message),
        "source": source,
    }


def build_message_versions(
    *,
    generated_message: str | None = None,
    final_message: str | None = None,
    edited_message: str | None = None,
    edited: bool | None = None,
) -> list[dict[str, Any]]:
    """
    Build chronologically ordered message-version records from observed message and edit evidence.
    
    Parameters:
        generated_message (str | None): The generated draft message, when observed.
        final_message (str | None): The authoritative final commit message, when observed.
        edited_message (str | None): The edited message text, when explicitly observed.
        edited (bool | None): Whether edit evidence indicates that the generated and final messages differ.
    
    Returns:
        list[dict[str, Any]]: Message-version records for observed generated, edited, and accepted final messages.
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
        versions.append(_item("final_accept", final_message, "commit_editmsg"))

    return versions
