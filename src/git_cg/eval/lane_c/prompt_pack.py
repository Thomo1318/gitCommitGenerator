"""Lane C-prime prompt pack identity — repo SoT for judge prompts (C-PACK).

A ``prompt_pack_v1`` object is the **git-pinned local identity** of a set of
judge prompt files. Runtime authority is always the repo pack + content hash;
cloud / Opik Prompt Library metadata is an optional immutable mirror, never a
live source (F5 — no floating "latest" prompts).

This module is **offline and side-effect free**. It never calls the network,
never imports a provider SDK, and never treats missing/malformed/non-UTF-8
packs as a soft miss.

Frozen schema fields stay on the object; richer identity (version, lane,
files, variable schema, sampling, output contract, cloud_mirror) lives in
``meta`` so we do not pin-bump ``prompt_pack_v1.schema.json`` (D9).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from git_cg.eval.lane_c.taxonomy import EXEC_PACK_DECODE_ERROR, EXEC_PACK_UNRESOLVABLE
from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin
from git_cg.eval.schema_pack import validate_instance

__all__ = [
    "DEFAULT_PROMPT_ROOT",
    "DEFAULT_UNIVERSE_ROOT",
    "PromptPackError",
    "UniverseFingerprint",
    "build_prompt_pack",
    "lint_prompt_pack_hygiene",
    "load_pack_prompt_text",
    "prompt_pack_content_hash",
    "prompt_pack_pin",
    "record_universe_fingerprint",
    "resolve_judge_pack",
    "validate_prompt_pack",
]

DEFAULT_PROMPT_ROOT = Path("prompts") / "eval" / "lane_c"
DEFAULT_UNIVERSE_ROOT = Path("config") / "promptfoo" / "prompts"

_PROMPT_SUFFIXES: Final = {".md", ".txt"}
_UNIVERSE_SUFFIXES: Final = {".md", ".txt", ".yaml", ".yml", ".json"}
_PACK_VERSION: Final = "1"
_DEFAULT_LANE: Final = "judge"
_DEFAULT_VARIABLE_SCHEMA: Final[dict[str, Any]] = {
    "final_message": {"type": "string", "required": True},
    "diff_summary": {"type": "string", "required": False},
}
_DEFAULT_SAMPLING: Final[dict[str, int]] = {"temperature": 0, "max_tokens": 256}
_DEFAULT_OUTPUT_CONTRACT: Final = "json_object"

_LATEST_RE = re.compile(r"(?:^|[^a-z0-9])latest(?:[^a-z0-9]|$)", re.IGNORECASE)
# Body scan: only identity-bearing / pin-shaped "latest" markers fail closed.
# Ordinary prose ("summarize the latest commit") must not mark a family unpinnable.
_IDENTITY_LATEST_LINE_RE = re.compile(
    r"(?im)^(?:\s*(?:provider|model|version|pin|identity|image|tag)\s*[:=]\s*.*\blatest\b"
    r"|\s*@latest\b"
    r"|\s*[^\n]*\b(?:prompt_pack_v\d+|schema_pack_v\d+|metric_catalog_v\d+)@latest\b)"
)

_LEAK_RE = re.compile(
    r"expected[_-]?gold|expected[_-]?label|expected[_-]?final|gold[_-]?codes|gold[_-]?label",
    re.IGNORECASE,
)
_EMPTY_SCORE_RE = re.compile(
    r"(empty.{0,120}score[\"'\s:=]+1)|(score[\"'\s:=]+1.{0,120}empty)|score empty as 1|force a score",
    re.IGNORECASE | re.DOTALL,
)
_SECRETISH_RE = re.compile(r"(sk-|api[_-]?key|secret|password|token|authorization)", re.IGNORECASE)
_PIN_HASH_RE = re.compile(r"^[a-f0-9]{64}$")


class PromptPackError(ValueError):
    """Prompt pack construction, decode, or resolution failure (fail closed)."""

    def __init__(self, message: str, *, code: str = EXEC_PACK_UNRESOLVABLE) -> None:
        """Create a prompt pack error with an execution error code.
        
        Parameters:
        	message (str): Description of the failure.
        	code (str): Execution error code associated with the failure.
        """
        super().__init__(message)
        self.code = code


def prompt_pack_content_hash(files: Sequence[tuple[str, bytes]]) -> str:
    """
    Compute a deterministic SHA-256 digest for prompt file names and contents.
    
    Parameters:
    	files (Sequence[tuple[str, bytes]]): Relative file names paired with their stored content bytes.
    
    Returns:
    	str: The hexadecimal SHA-256 digest of the sorted file names and content bytes.
    """
    h = hashlib.sha256()
    nul = bytes([0])
    for name, content in sorted(files, key=lambda pair: pair[0]):
        h.update(name.encode("utf-8"))
        h.update(nul)
        h.update(content)
        h.update(nul)
    return h.hexdigest()


def prompt_pack_pin(pack: Mapping[str, Any]) -> str:
    """Return the ``prompt_pack_v1@<sha256>`` pin for a built pack."""
    digest = str(pack.get("content_sha256") or "")
    if not _PIN_HASH_RE.fullmatch(digest):
        raise PromptPackError("prompt pack pin requires a sha256 content digest")
    return f"prompt_pack_v1@{digest}"


def _load_named_files(directory: Path, suffixes: set[str]) -> list[tuple[str, bytes]]:
    """
    Load eligible files from a directory in name order.
    
    Parameters:
    	directory (Path): Directory containing the files to load.
    	suffixes (set[str]): File suffixes to include.
    
    Returns:
    	list[tuple[str, bytes]]: Sorted file names paired with their raw contents.
    """
    files: list[tuple[str, bytes]] = []
    for path in sorted(directory.iterdir(), key=lambda p: p.name):
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.suffix.lower() not in suffixes:
            continue
        files.append((path.name, path.read_bytes()))
    return files


def _load_prompt_files(pack_dir: Path) -> list[tuple[str, bytes]]:
    """Load supported prompt files from a pack directory.
    
    Parameters:
    	pack_dir (Path): Directory containing the prompt files.
    
    Returns:
    	list[tuple[str, bytes]]: Sorted relative filenames and their raw contents.
    
    Raises:
    	PromptPackError: If the directory is missing or contains no supported prompt files.
    """
    if not pack_dir.is_dir():
        raise PromptPackError("missing prompt pack directory")
    files = _load_named_files(pack_dir, _PROMPT_SUFFIXES)
    if not files:
        raise PromptPackError("empty prompt pack directory")
    return files


def _decode_prompt_bytes(name: str, data: bytes) -> str:
    """
    Decode prompt file content as strict UTF-8.
    
    Parameters:
    	name (str): Prompt file name used in decode error reporting.
    	data (bytes): Raw prompt file content.
    
    Returns:
    	str: The decoded prompt text.
    
    Raises:
    	PromptPackError: If the content is not valid UTF-8.
    """
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PromptPackError(
            f"prompt pack file is not strict UTF-8: {name}",
            code=EXEC_PACK_DECODE_ERROR,
        ) from exc


def load_pack_prompt_text(pack_dir: Path) -> str:
    """
    Combine the prompt files in a pack directory into a single text value.
    
    Returns:
    	str: The decoded prompt contents joined by blank lines.
    """
    files = _load_prompt_files(pack_dir)
    texts = [_decode_prompt_bytes(name, data) for name, data in files]
    return "\n\n".join(texts)


def lint_prompt_pack_hygiene(text: str) -> None:
    """
    Validate prompt text for expected-answer leakage and forced perfect scores on empty inputs.
    
    Parameters:
    	text (str): Prompt text to check.
    """
    if _LEAK_RE.search(text):
        raise PromptPackError("prompt pack hygiene violation: expected/gold/label leakage")
    if _EMPTY_SCORE_RE.search(text):
        raise PromptPackError("prompt pack hygiene violation: empty input must not force score 1")


def _reject_floating_identity(identity: str) -> None:
    """Reject empty, floating, or malformed prompt pack identities.
    
    Raises:
        PromptPackError: If the identity is empty, contains a floating marker,
            or does not contain a valid `prompt_pack_v1` digest.
    """
    ident = identity.strip()
    if not ident:
        raise PromptPackError("unknown prompt pack identity")
    if _LATEST_RE.search(ident):
        raise PromptPackError("latest/floating prompt pack identity is not allowed")
    if not ident.startswith("prompt_pack_v1@"):
        raise PromptPackError("unknown prompt pack identity")
    digest = ident.split("@", 1)[1]
    if not _PIN_HASH_RE.fullmatch(digest):
        raise PromptPackError("unknown prompt pack identity")


def build_prompt_pack(
    pack_id: str,
    *,
    pack_dir: Path | None = None,
    notes: str | None = None,
    meta: dict[str, Any] | None = None,
    cloud_mirror: Mapping[str, Any] | None = None,
    expected_identity: str | None = None,
    lane: str = _DEFAULT_LANE,
) -> dict[str, Any]:
    """
    Build and validate a Lane C prompt pack from repository-local prompt files.
    
    Parameters:
    	pack_id (str): Identifier for the prompt pack.
    	pack_dir (Path | None): Directory containing the prompt files. The default resolves the directory from the pack identifier.
    	notes (str | None): Optional notes to include in the pack.
    	meta (dict[str, Any] | None): Optional metadata overrides.
    	cloud_mirror (Mapping[str, Any] | None): Optional cloud mirror metadata.
    	expected_identity (str | None): Optional content pin that the built pack must match.
    	lane (str): Lane name stored in the pack metadata.
    
    Returns:
    	dict[str, Any]: A schema-valid ``prompt_pack_v1`` object.
    
    Raises:
    	PromptPackError: If the pack identifier, prompt files, prompt content, identity, or resulting pack is invalid.
    """
    if expected_identity is not None:
        _reject_floating_identity(expected_identity)

    if not isinstance(pack_id, str) or not pack_id.strip():
        raise PromptPackError("pack_id must be a non-empty string")
    pack_id = pack_id.strip()

    if pack_dir is None:
        from git_cg.eval.paths import REPO_ROOT

        subdir = pack_id.removeprefix("lane_c_")
        pack_dir = REPO_ROOT / DEFAULT_PROMPT_ROOT / subdir

    files = _load_prompt_files(pack_dir)
    content_hash = prompt_pack_content_hash(files)
    texts = [_decode_prompt_bytes(name, data) for name, data in files]
    for text in texts:
        lint_prompt_pack_hygiene(text)

    built_meta: dict[str, Any] = {
        "version": _PACK_VERSION,
        "lane": lane,
        "files": [name for name, _data in files],
        "variable_schema": dict(_DEFAULT_VARIABLE_SCHEMA),
        "sampling": dict(_DEFAULT_SAMPLING),
        "output_contract": _DEFAULT_OUTPUT_CONTRACT,
    }
    if meta:
        built_meta.update(meta)
    if cloud_mirror is not None:
        built_meta["cloud_mirror"] = dict(cloud_mirror)

    pack: dict[str, Any] = {
        "schema_version": "prompt_pack_v1",
        "id": f"ppack_{pack_id}",
        "pack_id": pack_id,
        "content_sha256": content_hash,
        "schema_pack": schema_pack_pin(),
        "metric_catalog": metric_catalog_pin(),
        "meta": built_meta,
    }
    if notes is not None:
        pack["notes"] = notes

    validate_prompt_pack(pack)

    pin = prompt_pack_pin(pack)
    if expected_identity is not None and expected_identity.strip() != pin:
        raise PromptPackError("identity mismatch between expected pin and local pack bytes")
    return pack


def validate_prompt_pack(pack: dict[str, Any]) -> None:
    """Validate a prompt pack dict against the frozen ``prompt_pack_v1`` schema."""
    try:
        validate_instance("prompt_pack_v1", pack)
    except Exception as exc:
        raise PromptPackError(f"prompt_pack_v1 validation failed: {exc}") from exc


def resolve_judge_pack(
    metric_id: str,
    *,
    prompt_root: Path | None = None,
    expected_identity: str | None = None,
    cloud_mirror: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve the prompt pack associated with a Lane C metric.
    
    Parameters:
        metric_id (str): Metric identifier with the ``cprime.`` prefix.
        prompt_root (Path | None): Root directory containing metric-specific prompt pack directories.
        expected_identity (str | None): Expected content pin for the resolved pack.
        cloud_mirror (Mapping[str, Any] | None): Optional cloud mirror metadata.
    
    Returns:
        dict[str, Any]: The validated prompt pack.
    
    Raises:
        PromptPackError: If the metric identifier is not a ``cprime.*`` identifier or the prompt pack cannot be built or validated.
    """
    if not isinstance(metric_id, str) or not metric_id.startswith("cprime."):
        raise PromptPackError(f"resolve_judge_pack requires a cprime.* metric id, got: {metric_id!r}")

    suffix = metric_id.removeprefix("cprime.")
    pack_id = f"lane_c_{suffix}"
    pack_dir = prompt_root / suffix if prompt_root is not None else None
    return build_prompt_pack(
        pack_id,
        pack_dir=pack_dir,
        expected_identity=expected_identity,
        cloud_mirror=cloud_mirror,
    )


@dataclass(frozen=True, slots=True)
class UniverseFingerprint:
    """Snapshot of active prompt universes (S5-D12).

    Absence of ``config/promptfoo/prompts`` is recorded honestly and is **not**
    treated as a second invented source. A present tree with ``latest`` or
    otherwise unpinnable families fails closed.
    """

    root_present: bool
    universes: tuple[str, ...]
    latest_found: tuple[str, ...]
    unpinnable: tuple[str, ...]
    status: str
    pinned: bool
    content_sha256: str

    def as_dict(self) -> dict[str, Any]:
        """Serialise the universe fingerprint as a dictionary.
        
        Returns:
        	dict[str, Any]: A dictionary containing the fingerprint state and content hash.
        """
        return {
            "root_present": self.root_present,
            "universes": list(self.universes),
            "latest_found": list(self.latest_found),
            "unpinnable": list(self.unpinnable),
            "status": self.status,
            "pinned": self.pinned,
            "content_sha256": self.content_sha256,
        }

    def assert_pinned(self) -> None:
        """Ensure the universe fingerprint represents a pinned prompt universe.
        
        Raises:
        	PromptPackError: If the fingerprint contains a floating identity or is otherwise not pinned.
        """
        if self.pinned:
            return
        if self.latest_found:
            raise PromptPackError(
                "universe fingerprint contains latest/unpinnable family",
                code=EXEC_PACK_UNRESOLVABLE,
            )
        raise PromptPackError("universe fingerprint is not pinned", code=EXEC_PACK_UNRESOLVABLE)


def _unique(items: Iterable[str]) -> tuple[str, ...]:
    """
    Return the items in their first-occurrence order with duplicates removed.
    
    Parameters:
    	items (Iterable[str]): The values to deduplicate.
    
    Returns:
    	tuple[str, ...]: The unique values in first-occurrence order.
    """
    seen: list[str] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return tuple(seen)


def _body_has_floating_latest(text: str) -> bool:
    """Detect whether prompt text contains a floating `latest` identity marker.
    
    Returns:
    	bool: `True` if the text contains a pin-shaped `latest` marker, `False` otherwise.
    """
    if _IDENTITY_LATEST_LINE_RE.search(text):
        return True
    # Pin-shaped tokens anywhere (not ordinary prose).
    lowered = text.lower()
    if "@latest" in lowered:
        return True
    return bool(_LATEST_RE.search(text) and _re_version_latest.search(text))


_re_version_latest = re.compile(r"(?i)\bversion\s*[:=]\s*latest\b")


def record_universe_fingerprint(root: Path | None = None) -> UniverseFingerprint:
    """
    Record a content fingerprint for the prompt universes under the configured root.
    
    Parameters:
    	root (Path | None): Directory containing universe family subdirectories. When
    		omitted, uses the repository's default Promptfoo universe directory.
    
    Returns:
    	UniverseFingerprint: Snapshot containing discovered universes, pinning status,
    		floating identities, unpinnable families, and the content SHA-256 digest.
    		An absent root is recorded with ``status="absent"``.
    """
    if root is None:
        from git_cg.eval.paths import REPO_ROOT

        root = REPO_ROOT / DEFAULT_UNIVERSE_ROOT

    if not root.is_dir():
        return UniverseFingerprint(
            root_present=False,
            universes=(),
            latest_found=(),
            unpinnable=(),
            status="absent",
            pinned=False,
            content_sha256="",
        )

    families = sorted(
        (p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")),
        key=lambda p: p.name,
    )
    hashed: list[tuple[str, bytes]] = []
    latest: list[str] = []
    unpinnable: list[str] = []
    names: list[str] = []

    for family in families:
        names.append(family.name)
        loaded = _load_named_files(family, _UNIVERSE_SUFFIXES)
        if not loaded:
            unpinnable.append(family.name)
            continue
        for name, data in loaded:
            hashed.append((f"{family.name}/{name}", data))
            if _SECRETISH_RE.search(name):
                unpinnable.append(family.name)
                continue
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                unpinnable.append(family.name)
                continue
            if _body_has_floating_latest(text):
                latest.append(f"{family.name}/{name}")
                unpinnable.append(family.name)

    latest_t = _unique(latest)
    unpinnable_t = _unique(unpinnable)
    if names and not latest_t and not unpinnable_t:
        status = "pinned"
        pinned = True
    else:
        status = "unpinnable" if names else "empty"
        pinned = False

    return UniverseFingerprint(
        root_present=True,
        universes=tuple(names),
        latest_found=latest_t,
        unpinnable=unpinnable_t,
        status=status,
        pinned=pinned,
        content_sha256=prompt_pack_content_hash(hashed),
    )
