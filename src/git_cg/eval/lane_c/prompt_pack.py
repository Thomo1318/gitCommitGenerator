"""Lane C-prime prompt pack identity — repo SoT for judge prompts (INT-26).

A ``prompt_pack_v1`` object is the **git-pinned local identity** of a set of
judge prompt files. Runtime authority is always the repo pack + content hash;
the Opik Prompt Library is an optional immutable mirror, never a live source
(F5 — no floating "latest" prompts).

This module is **offline and side-effect free**. It reads repo-local prompt
files, computes a deterministic content hash, and emits schema-valid
``prompt_pack_v1`` dicts. It never calls the network, never imports the Opik
SDK, and never raises on missing prompt files — a missing pack fails closed
with :class:`PromptPackError`.

Pin integrity (F5): every pack carries ``content_sha256`` over the canonical
concatenation of its prompt files. Any drift in file content changes the hash,
making silent prompt mutation detectable by Family H ``h.prompt_pack_pinned``.

Directory layout (repo-relative)::

    prompts/eval/lane_c/<pack_name>/   # one subdirectory per pack
        rubric.md                      # the judge rubric / criteria
        ...                            # optional additional .md/.txt files

``resolve_judge_pack`` maps a ``cprime.*`` metric id to its pack by convention:
``cprime.geval_craft`` → pack directory ``prompts/eval/lane_c/geval_craft/``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin
from git_cg.eval.schema_pack import validate_instance

__all__ = [
    "DEFAULT_PROMPT_ROOT",
    "PromptPackError",
    "build_prompt_pack",
    "load_pack_prompt_text",
    "prompt_pack_content_hash",
    "resolve_judge_pack",
    "validate_prompt_pack",
]

#: Default root for repo-local judge prompt packs, relative to repo root.
#: Each immediate subdirectory is one named pack.
DEFAULT_PROMPT_ROOT = Path("prompts") / "eval" / "lane_c"


class PromptPackError(ValueError):
    """Prompt pack construction or resolution failure (fail closed)."""


def prompt_pack_content_hash(files: list[tuple[str, bytes]]) -> str:
    """Deterministic SHA-256 over canonical prompt file content.

    ``files`` is a list of ``(relative_name, content_bytes)`` pairs. The hash
    covers file names and content in sorted order, with NUL separators, so
    any rename, reorder, or content change produces a different digest.
    """
    h = hashlib.sha256()
    nul = bytes([0])
    for name, content in sorted(files, key=lambda pair: pair[0]):
        h.update(name.encode("utf-8"))
        h.update(nul)
        h.update(content)
        h.update(nul)
    return h.hexdigest()


def _load_prompt_files(pack_dir: Path) -> list[tuple[str, bytes]]:
    """Read prompt files from a pack directory, returning (name, bytes) pairs.

    Only ``.md`` and ``.txt`` files at the top level of *pack_dir* are
    considered. Fails closed on missing or empty directory.
    """
    if not pack_dir.is_dir():
        raise PromptPackError(f"missing prompt pack directory: {pack_dir}")
    files: list[tuple[str, bytes]] = []
    for ext in ("*.md", "*.txt"):
        for path in sorted(pack_dir.glob(ext)):
            if path.is_file():
                files.append((path.name, path.read_bytes()))
    if not files:
        raise PromptPackError(f"empty prompt pack directory: {pack_dir}")
    return files


def load_pack_prompt_text(pack_dir: Path) -> str:
    """Return the concatenated prompt text for a pack directory.

    Reads the same sorted ``.md``/``.txt`` files that
    :func:`prompt_pack_content_hash` hashes, joined with blank lines, so the
    text a judge sees is byte-identical to the content the pack's
    ``content_sha256`` pins. Fails closed via :class:`PromptPackError` on a
    missing/empty directory (same contract as the builder).
    """
    files = _load_prompt_files(pack_dir)
    return "\n\n".join(content.decode("utf-8") for _name, content in files)


def build_prompt_pack(
    pack_id: str,
    *,
    pack_dir: Path | None = None,
    notes: str | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a schema-valid ``prompt_pack_v1`` object from repo-local files.

    ``pack_id`` is the human-readable pack identifier (e.g.
    ``"lane_c_geval_craft"``). When *pack_dir* is ``None`` the directory is
    resolved as ``prompts/eval/lane_c/<pack_id>/`` under the repo root (the
    ``lane_c_`` prefix is stripped to form the subdirectory name).

    The returned dict passes ``validate_instance("prompt_pack_v1", ...)``.
    Raises :class:`PromptPackError` on missing/empty prompt directory or
    schema validation failure.
    """
    if not isinstance(pack_id, str) or not pack_id.strip():
        raise PromptPackError("pack_id must be a non-empty string")
    pack_id = pack_id.strip()

    if pack_dir is None:
        from git_cg.eval.paths import REPO_ROOT

        # Strip the conventional lane_c_ prefix to find the subdirectory.
        subdir = pack_id.removeprefix("lane_c_")
        pack_dir = REPO_ROOT / DEFAULT_PROMPT_ROOT / subdir

    files = _load_prompt_files(pack_dir)
    content_hash = prompt_pack_content_hash(files)

    pack: dict[str, Any] = {
        "schema_version": "prompt_pack_v1",
        "id": f"ppack_{pack_id}",
        "pack_id": pack_id,
        "content_sha256": content_hash,
        "schema_pack": schema_pack_pin(),
        "metric_catalog": metric_catalog_pin(),
    }
    if notes is not None:
        pack["notes"] = notes
    if meta is not None:
        pack["meta"] = meta

    validate_prompt_pack(pack)
    return pack


def validate_prompt_pack(pack: dict[str, Any]) -> None:
    """Validate a prompt pack dict against the frozen ``prompt_pack_v1`` schema.

    Raises :class:`PromptPackError` on validation failure.
    """
    try:
        validate_instance("prompt_pack_v1", pack)
    except Exception as exc:
        raise PromptPackError(f"prompt_pack_v1 validation failed: {exc}") from exc


def resolve_judge_pack(
    metric_id: str,
    *,
    prompt_root: Path | None = None,
) -> dict[str, Any]:
    """Resolve the pinned prompt pack for a ``cprime.*`` metric.

    Maps the metric id to a pack by convention:
    ``cprime.geval_craft`` → pack ``lane_c_geval_craft`` → directory
    ``<prompt_root>/geval_craft/``. The pack is built from the repo-local
    prompt files and validated against the frozen schema.

    Raises :class:`PromptPackError` when the metric id is not a ``cprime.*``
    id or when the pack directory is missing/empty.
    """
    if not isinstance(metric_id, str) or not metric_id.startswith("cprime."):
        raise PromptPackError(f"resolve_judge_pack requires a cprime.* metric id, got: {metric_id!r}")

    suffix = metric_id.removeprefix("cprime.")
    pack_id = f"lane_c_{suffix}"

    pack_dir = prompt_root / suffix if prompt_root is not None else None

    return build_prompt_pack(pack_id, pack_dir=pack_dir)
