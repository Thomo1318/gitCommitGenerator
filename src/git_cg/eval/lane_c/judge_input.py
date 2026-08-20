"""Lane C-prime gold-blind judge input projection (C-INPUT / C-DIFF).

Ordinary judges consume **S3 final-accept evidence**, never a free unbound
``message: str``. Isolation is recursive and fail-closed (D6 / F6): expected /
gold / assert / sole-green gate hints never reach a transport payload.

This module is offline and side-effect free. It does not import a provider
SDK, open a network socket, invoke a judge, or wire the Slice 1/2 runner.
Empty / oversize classification is a host guard for Slice 4 to skip on
``empty_input`` / ``oversize_input`` before any future network call (D12).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Final

from git_cg.eval.binding.binder import BindResult, _project_final_text, message_sha256_bytes
from git_cg.eval.enums import ArtifactClass
from git_cg.eval.lane_c.taxonomy import EXEC_EMPTY_INPUT, EXEC_OVERSIZE_INPUT

__all__ = [
    "DEFAULT_MAX_DIFF_SUMMARY_CHARS",
    "DEFAULT_MAX_INPUT_CHARS",
    "JudgeInput",
    "JudgeInputError",
    "classify_judge_input_size",
    "project_diff_summary",
    "project_judge_input",
]

DEFAULT_MAX_INPUT_CHARS: Final = 32000
DEFAULT_MAX_DIFF_SUMMARY_CHARS: Final = 2000

# Mirror corpus/task_input.py — do not weaken or reimplement differently (C-INPUT).
_FORBIDDEN_NAME = re.compile(r"^(expected|gold)([_-]|$)", re.IGNORECASE)
_ASSERT_NAME = re.compile(r"^assert([_-]|$)", re.IGNORECASE)
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _normalize_key_name(key: str) -> str:
    """Normalize key separators so goldCodes / gold-codes match gold_codes."""
    spaced = _CAMEL_BOUNDARY.sub("_", key)
    return spaced.replace("-", "_")


_FORBIDDEN_EXACT: Final[frozenset[str]] = frozenset(
    {
        "expected_final_message",
        "expected_gold_codes",
        "expected_output",
        "gold_codes",
        "gold_findings",
        "judge_labels",
        "judge_target",
        "gate_deterministic_pass",
        "assert",
    }
)

_CONTEXT_ALLOWED: Final[frozenset[str]] = frozenset({"diff_summary"})

_LAB_ARTIFACT_CLASSES: Final[frozenset[str]] = frozenset(
    {
        ArtifactClass.FIXTURE.value,
        ArtifactClass.LIVE_REGEN.value,
        ArtifactClass.OPIK_UNBOUND.value,
    }
)

_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_RAW_PATCH_RE = re.compile(r"(?m)^(diff --git |index [0-9a-f]{6,}\.\.[0-9a-f]{6,}|--- [ab]/|\+\+\+ [ab]/|@@ -\d)")
_LEAK_IN_TEXT_RE = re.compile(
    r"expected[_-]?gold|expected[_-]?label|expected[_-]?final|gold[_-]?codes|gold[_-]?label",
    re.IGNORECASE,
)
_UNIX_ABS_RE = re.compile(r"(?<![\w.-])(?:/(?:Users|home|private|var|tmp|opt|usr|System|Volumes)(?:/[^/\s,;:'\"]+)+)")
_WIN_ABS_RE = re.compile(r"(?<![\w])[A-Za-z]:\\+(?:[^\\\s,;:'\"]+\\+)*[^\\\s,;:'\"]+")
_FILE_URL_RE = re.compile(r"file://[^\s,;]+")


class JudgeInputError(ValueError):
    """Judge-input isolation, linkage, or host-guard failure."""

    def __init__(self, message: str, *, code: str = "invalid_input") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class JudgeInput:
    """Allowlisted ordinary-path judge payload (C-INPUT).

    ``as_dict`` is the only transport-facing projection. It never invents
    ``bundle_id`` and never emits expected/gold/assert/gate carriers.
    """

    artifact_class: str
    final_message_text: str
    final_message_sha256: str
    encoding: str
    session_thread_id: str | None = None
    diff_summary: str | None = None

    def as_dict(self) -> dict[str, str]:
        payload: dict[str, str] = {
            "artifact_class": self.artifact_class,
            "final_message_text": self.final_message_text,
            "final_message_sha256": self.final_message_sha256,
            "encoding": self.encoding,
        }
        if self.session_thread_id:
            payload["session_thread_id"] = self.session_thread_id
        if self.diff_summary:
            payload["diff_summary"] = self.diff_summary
        return payload


def classify_judge_input_size(
    text: str,
    *,
    max_chars: int = DEFAULT_MAX_INPUT_CHARS,
) -> str | None:
    """Return ``empty_input`` / ``oversize_input`` or ``None`` when within bounds."""
    if not text or not str(text).strip():
        return EXEC_EMPTY_INPUT
    if len(text) > max_chars:
        return EXEC_OVERSIZE_INPUT
    return None


def _is_forbidden_key(key: str) -> bool:
    norm = _normalize_key_name(key)
    if key in _FORBIDDEN_EXACT or norm in _FORBIDDEN_EXACT:
        return True
    if _FORBIDDEN_NAME.match(key) is not None or _FORBIDDEN_NAME.match(norm) is not None:
        return True
    return _ASSERT_NAME.match(key) is not None or _ASSERT_NAME.match(norm) is not None


def _walk_forbidden_keys(obj: Any, found: list[str]) -> None:
    if isinstance(obj, Mapping):
        for key, value in obj.items():
            if isinstance(key, str) and _is_forbidden_key(key):
                found.append(key)
            _walk_forbidden_keys(value, found)
        return
    if isinstance(obj, (list, tuple)):
        for item in obj:
            _walk_forbidden_keys(item, found)


def _strip_forbidden(obj: Any) -> Any:
    if isinstance(obj, Mapping):
        return {
            key: _strip_forbidden(value)
            for key, value in obj.items()
            if not (isinstance(key, str) and _is_forbidden_key(key))
        }
    if isinstance(obj, list):
        return [_strip_forbidden(item) for item in obj]
    if isinstance(obj, tuple):
        return tuple(_strip_forbidden(item) for item in obj)
    return obj


def _isolation_targets(evidence: BindResult | Mapping[str, Any], context: Mapping[str, Any] | None) -> list[Any]:
    targets: list[Any] = []
    if isinstance(evidence, BindResult):
        if evidence.bundle is not None:
            targets.append(evidence.bundle)
        if isinstance(evidence.session_thread, Mapping):
            targets.append(evidence.session_thread)
        if isinstance(evidence.trajectory, Mapping):
            targets.append(evidence.trajectory)
    else:
        targets.append(evidence)
    if context is not None:
        targets.append(context)
    return targets


def _enforce_isolation(targets: Iterable[Any], *, strict: bool) -> None:
    found: list[str] = []
    for target in targets:
        _walk_forbidden_keys(target, found)
    if not found:
        return
    # Preserve first-seen order while uniquifying for a stable error.
    ordered = list(dict.fromkeys(found))
    if strict:
        raise JudgeInputError(
            "judge input must not contain expected/gold/assert/gate target fields: " + ", ".join(ordered)
        )


def _basename_path(path: str) -> str:
    cleaned = path.replace("\\", "/").rstrip("/")
    name = cleaned.rsplit("/", 1)[-1]
    return name or "file"


def _scrub_paths(text: str) -> str:
    scrubbed = _FILE_URL_RE.sub(lambda match: _basename_path(match.group(0).removeprefix("file://")), text)
    scrubbed = _UNIX_ABS_RE.sub(lambda match: _basename_path(match.group(0)), scrubbed)
    return _WIN_ABS_RE.sub(lambda match: _basename_path(match.group(0)), scrubbed)


def project_diff_summary(
    raw: Any,
    *,
    max_chars: int = DEFAULT_MAX_DIFF_SUMMARY_CHARS,
) -> str | None:
    """Project an allowlisted, path-scrubbed, bounded, gold-blind diff summary.

    Rejects raw patches and expected/gold carriers. Never returns file contents
    or absolute paths. Shared helper for judge input (D37 / C-DIFF).
    """
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise JudgeInputError("diff_summary must be a string")
    text = raw.strip()
    if not text:
        return None
    if _RAW_PATCH_RE.search(raw) is not None:
        raise JudgeInputError("diff_summary must not contain a raw patch")
    if _LEAK_IN_TEXT_RE.search(raw) is not None:
        raise JudgeInputError("diff_summary must not contain expected/gold labels")
    scrubbed = _scrub_paths(text)
    if len(scrubbed) > max_chars:
        return scrubbed[:max_chars]
    return scrubbed


def _reject_free_message(payload: Mapping[str, Any]) -> None:
    if "message" in payload:
        raise JudgeInputError("ordinary judge input rejects free unbound message= without final_accept linkage")


def _as_payload(evidence: BindResult | Mapping[str, Any]) -> tuple[dict[str, Any], bool | None]:
    if isinstance(evidence, BindResult):
        if evidence.bundle is None:
            if not evidence.bound:
                raise JudgeInputError(
                    "unbound BindResult has no final_accept bundle",
                    code="unbound",
                )
            raise JudgeInputError("BindResult is missing a final_accept bundle")
        _reject_free_message(evidence.bundle)
        return dict(evidence.bundle), evidence.bound
    if isinstance(evidence, Mapping):
        _reject_free_message(evidence)
        bound = evidence.get("bound")
        return dict(evidence), bound if isinstance(bound, bool) else None
    raise JudgeInputError("judge input evidence must be a BindResult or mapping")


def _project_context(context: Mapping[str, Any] | None, *, strict: bool) -> str | None:
    if context is None:
        return None
    if not isinstance(context, Mapping):
        raise JudgeInputError("judge input context must be an object")
    working: Mapping[str, Any]
    if strict:
        unknown = sorted(key for key in context if key not in _CONTEXT_ALLOWED)
        if unknown:
            raise JudgeInputError(
                f"judge input context contains unsupported keys {unknown}; allowed: {sorted(_CONTEXT_ALLOWED)}"
            )
        working = context
    else:
        working = {key: value for key, value in context.items() if key in _CONTEXT_ALLOWED}
    if "diff_summary" not in working:
        return None
    return project_diff_summary(working.get("diff_summary"))


def _resolve_text_and_encoding(payload: Mapping[str, Any]) -> tuple[str, str, str]:
    raw = payload.get("final_message")
    if raw is None:
        raw = payload.get("final_message_text")
    if raw is None:
        raise JudgeInputError("final_accept linkage requires projected final message text")

    meta = payload.get("meta")
    meta_map = meta if isinstance(meta, Mapping) else {}
    provided_encoding = meta_map.get("final_message_encoding")
    if provided_encoding is None:
        provided_encoding = payload.get("encoding")

    if isinstance(raw, bytes):
        text, extra = _project_final_text(raw)
        encoding = str(extra.get("final_message_encoding") or provided_encoding or "utf-8")
        digest = message_sha256_bytes(raw)
        return text, encoding, digest

    if not isinstance(raw, str):
        raise JudgeInputError("final_message must be text or original bytes")
    encoding = str(provided_encoding or "utf-8")
    return raw, encoding, message_sha256_bytes(raw)


def _validate_encoding(encoding: str) -> str:
    if encoding not in {"utf-8", "utf-8-replace"}:
        raise JudgeInputError("encoding must be utf-8 or utf-8-replace")
    return encoding


def _validate_hash(provided: Any, computed_from_text: str, *, encoding: str) -> str:
    if not isinstance(provided, str) or not _SHA256_RE.fullmatch(provided):
        raise JudgeInputError("final_accept linkage requires final_message_sha256 over original bytes")
    if encoding == "utf-8" and provided != computed_from_text:
        raise JudgeInputError("final_message_sha256 does not match projected utf-8 text")
    return provided


def _validate_artifact_class(artifact_class: Any, *, bound: bool | None, lab_override: bool) -> str:
    if not isinstance(artifact_class, str) or not artifact_class:
        raise JudgeInputError("final_accept linkage requires artifact_class")
    if artifact_class == ArtifactClass.FINAL_ACCEPT.value:
        if bound is False:
            raise JudgeInputError("unbound evidence cannot claim final_accept")
        return artifact_class
    if artifact_class in _LAB_ARTIFACT_CLASSES:
        if not lab_override:
            if bound is False:
                raise JudgeInputError(
                    "ordinary judge input requires bound final_accept linkage; "
                    "lab artifact_class requires explicit lab_override"
                )
            raise JudgeInputError("lab artifact_class requires explicit lab_override")
        return artifact_class
    raise JudgeInputError(f"unsupported artifact_class for judge input: {artifact_class}")


def project_judge_input(
    evidence: BindResult | Mapping[str, Any],
    *,
    context: Mapping[str, Any] | None = None,
    lab_override: bool = False,
    strict: bool = True,
    max_input_chars: int = DEFAULT_MAX_INPUT_CHARS,
) -> JudgeInput:
    """Project gold-blind, final-accept-linked judge input (C-INPUT / C-DIFF).

    Args:
        evidence: S3 ``BindResult`` or its bundle mapping. Ordinary path rejects
            free ``message=`` and unbound / non-``final_accept`` artifacts.
        context: optional allowlisted projection inputs (``diff_summary`` only).
        lab_override: when True, permit explicit lab artifact classes
            (``fixture`` / ``live_regen`` / ``Opik-unbound``). Still gold-blind
            and still requires hash/text/encoding linkage.
        strict: reject (True) or strip (False) forbidden keys. Strip never
            returns expected/gold/assert/gate carriers.
        max_input_chars: host size guard (default 32000). Empty/oversize raise
            with taxonomy codes; they do not score.

    Raises:
        JudgeInputError: isolation leak, missing linkage, or host-guard trip.
    """
    targets = _isolation_targets(evidence, context)
    _enforce_isolation(targets, strict=strict)
    if not strict:
        if isinstance(evidence, BindResult):
            bundle = _strip_forbidden(evidence.bundle) if evidence.bundle is not None else None
            evidence = BindResult(
                bound=evidence.bound,
                bundle=bundle,
                session_thread=_strip_forbidden(evidence.session_thread)
                if isinstance(evidence.session_thread, Mapping)
                else evidence.session_thread,
                trajectory=_strip_forbidden(evidence.trajectory)
                if isinstance(evidence.trajectory, Mapping)
                else evidence.trajectory,
                unbound_reason=evidence.unbound_reason,
                paths_written=evidence.paths_written,
                errors=evidence.errors,
            )
        elif isinstance(evidence, Mapping):
            evidence = _strip_forbidden(evidence)
        if context is not None:
            context = _strip_forbidden(context)

    payload, bound = _as_payload(evidence)
    artifact_class = _validate_artifact_class(
        payload.get("artifact_class"),
        bound=bound,
        lab_override=lab_override,
    )
    text, encoding, computed_hash = _resolve_text_and_encoding(payload)
    encoding = _validate_encoding(encoding)
    provided_hash = payload.get("final_message_sha256")
    if provided_hash is None:
        raise JudgeInputError("final_accept linkage requires final_message_sha256 over original bytes")
    digest = _validate_hash(provided_hash, computed_hash, encoding=encoding)

    session = payload.get("session_thread_id")
    session_thread_id = session.strip() if isinstance(session, str) and session.strip() else None

    diff_summary = _project_context(context, strict=strict)

    size_text = text if not diff_summary else f"{text}\n{diff_summary}"
    size_code = classify_judge_input_size(size_text, max_chars=max_input_chars)
    if size_code == EXEC_EMPTY_INPUT:
        raise JudgeInputError("empty_input: judge input text is empty or whitespace", code=EXEC_EMPTY_INPUT)
    if size_code == EXEC_OVERSIZE_INPUT:
        raise JudgeInputError(
            f"oversize_input: judge input exceeds {max_input_chars} characters",
            code=EXEC_OVERSIZE_INPUT,
        )

    return JudgeInput(
        artifact_class=artifact_class,
        final_message_text=text,
        final_message_sha256=digest,
        encoding=encoding,
        session_thread_id=session_thread_id,
        diff_summary=diff_summary,
    )
