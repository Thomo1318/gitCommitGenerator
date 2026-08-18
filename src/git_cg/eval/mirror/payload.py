"""Content-addressed redacted export payload artifacts (P0-3 / E11).

Normative layout::

    .eval/export_payloads/<sha256>.json   # immutable redacted projection body
    .eval/export_queue/<queue_id>.json    # ops row with payload_ref + sha + size

Law:

* Canonical JSON (E10) before hash/size/persist — hash is over the *object*,
  not the pretty on-disk encoding.
* Atomic write + ``.eval/`` containment (S3 Layer-A write law).
* Drain must load by ref and verify sha256 + size — **never** reconstruct
  from item ids alone (P0-3).
* Missing/mismatched artifact → ``export_validation`` class (export health only).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from git_cg.eval.binding.paths import LayerAPathError, atomic_write_json, eval_tree_root, resolve_repo_root
from git_cg.eval.corpus.canonical import canonical_json_bytes, sha256_hex

__all__ = [
    "EXPORT_PAYLOADS_DIRNAME",
    "ExportPayloadError",
    "export_payloads_dir",
    "load_payload_artifact",
    "payload_ref_for_sha",
    "persist_payload_artifact",
    "verify_payload_object",
]

#: Locked sub-path under ``.eval/`` (E11).
EXPORT_PAYLOADS_DIRNAME = "export_payloads"


class ExportPayloadError(ValueError):
    """Payload artifact failure (``export_validation`` class; never product)."""

    def __init__(self, message: str, *, error_class: str = "export_validation") -> None:
        """Create an export payload error with a message and error classification."""
        self.error_class = error_class
        super().__init__(message)


def export_payloads_dir(repo_root: Path) -> Path:
    """Return the contained ``.eval/export_payloads/`` dir (not created here)."""
    return eval_tree_root(repo_root) / EXPORT_PAYLOADS_DIRNAME


def payload_ref_for_sha(sha256: str) -> str:
    """
    Formats a SHA-256 digest as an export payload reference.
    
    Parameters:
        sha256 (str): A lowercase 64-character SHA-256 digest.
    
    Returns:
        str: The digest prefixed with ``sha256:``.
    """
    _assert_sha256(sha256)
    return f"sha256:{sha256}"


def _assert_sha256(value: str) -> None:
    """Validate that a value is a lowercase hexadecimal SHA-256 digest.
    
    Raises:
        ExportPayloadError: If the value is not a 64-character lowercase hexadecimal digest.
    """
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ExportPayloadError(f"invalid payload sha256: {value!r}")


def _sha_from_ref(payload_ref: str) -> str:
    """Extract and validate the SHA-256 digest from a payload reference.
    
    Parameters:
    	payload_ref (str): Payload reference containing a SHA-256 digest.
    
    Returns:
    	str: The validated SHA-256 digest.
    """
    ref = str(payload_ref or "").strip()
    sha = ref.removeprefix("sha256:") if ref.startswith("sha256:") else ref
    _assert_sha256(sha)
    return sha


def _artifact_path(repo_root: Path, sha256: str) -> Path:
    """Return the filesystem path for an export payload artifact identified by its SHA-256 digest.
    
    Parameters:
    	repo_root (Path): Repository root containing the export payload directory.
    	sha256 (str): Lowercase 64-character SHA-256 digest.
    
    Returns:
    	Path: Path to the corresponding JSON artifact.
    """
    _assert_sha256(sha256)
    return export_payloads_dir(repo_root) / f"{sha256}.json"


def verify_payload_object(
    payload: dict[str, Any],
    *,
    expected_sha256: str | None = None,
    expected_size: int | None = None,
) -> tuple[str, int]:
    """
    Compute the SHA-256 digest and canonical byte size of a payload object.
    
    Parameters:
        expected_sha256 (str | None): Optional digest that the payload must match.
        expected_size (int | None): Optional canonical byte size that the payload must match.
    
    Returns:
        tuple[str, int]: The payload's SHA-256 digest and canonical byte size.
    
    Raises:
        ExportPayloadError: If the payload is not a JSON object or does not match an expected digest or size.
    """
    if not isinstance(payload, dict):
        raise ExportPayloadError("payload artifact body must be a JSON object")
    raw = canonical_json_bytes(payload)
    digest = sha256_hex(raw)
    size = len(raw)
    if expected_sha256 is not None and digest != expected_sha256:
        raise ExportPayloadError(f"payload sha256 mismatch: expected {expected_sha256}, got {digest}")
    if expected_size is not None and size != expected_size:
        raise ExportPayloadError(f"payload size mismatch: expected {expected_size}, got {size}")
    return digest, size


def persist_payload_artifact(
    payload: dict[str, Any],
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """
    Persist a payload as an immutable, content-addressed artifact.
    
    Parameters:
        payload (dict[str, Any]): JSON object to persist.
        repo_root (Path | None): Repository root containing the artifact directory.
    
    Returns:
        dict[str, Any]: Payload reference, SHA-256 digest, canonical byte size, and artifact path.
    """
    if not isinstance(payload, dict):
        raise ExportPayloadError("payload artifact body must be a JSON object")
    root = repo_root if repo_root is not None else resolve_repo_root()
    digest, size = verify_payload_object(payload)
    path = _artifact_path(root, digest)
    try:
        if path.is_file():
            # Confirm on-disk object still matches; repair if corrupted.
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
                verify_payload_object(existing, expected_sha256=digest)
            except OSError, json.JSONDecodeError, ExportPayloadError, TypeError:
                atomic_write_json(path, payload)
        else:
            atomic_write_json(path, payload)
    except (OSError, LayerAPathError) as exc:
        raise ExportPayloadError(f"failed to persist payload artifact: {exc}") from exc

    return {
        "payload_ref": payload_ref_for_sha(digest),
        "payload_sha256": digest,
        "payload_size_bytes": size,
        "path": path,
    }


def load_payload_artifact(
    payload_ref: str,
    *,
    repo_root: Path | None = None,
    expected_sha256: str | None = None,
    expected_size: int | None = None,
) -> dict[str, Any]:
    """
    Load and verify a content-addressed export payload artifact.
    
    Parameters:
    	payload_ref (str): Reference identifying the payload artifact.
    	expected_sha256 (str | None): Optional digest that must match the reference.
    	expected_size (int | None): Optional canonical payload size that must match the artifact.
    
    Returns:
    	dict[str, Any]: The verified payload object.
    """
    root = repo_root if repo_root is not None else resolve_repo_root()
    sha = _sha_from_ref(payload_ref)
    if expected_sha256 is not None and sha != expected_sha256:
        raise ExportPayloadError(f"payload_ref sha {sha} != expected {expected_sha256}")
    path = _artifact_path(root, sha)
    if not path.is_file():
        raise ExportPayloadError(f"missing payload artifact: {payload_ref}")
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExportPayloadError(f"unreadable payload artifact {payload_ref}: {exc}") from exc
    if not isinstance(obj, dict):
        raise ExportPayloadError(f"payload artifact is not an object: {payload_ref}")
    verify_payload_object(obj, expected_sha256=sha, expected_size=expected_size)
    return obj
