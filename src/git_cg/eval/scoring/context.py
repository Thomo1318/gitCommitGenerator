"""Score context projection — final message / product card binding (FIND-027)."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from git_cg.eval.corpus.canonical import message_sha256
from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin

# Default offline evaluation payload budget (bytes). Oversize ⇒ unevaluable class.
DEFAULT_MAX_EVAL_BYTES = 256_000

# Fields that must never be the primary scored format target (FIND-027).
_WRONG_ARTIFACT_KEYS = frozenset(
    {
        "raw_model_output",
        "generation_json",
        "model_dump",
        "raw_blob",
        "trace_blob",
        "llm_raw",
        "unparsed_output",
    }
)


class ScoreContextError(ValueError):
    """Score context projection failure."""


@dataclass(frozen=True, slots=True)
class ScoreContext:
    """Bound scoring inputs for one case/bundle.

    ``final_message`` is the sole default format/Hybrid target (FIND-027).
    ``product_card`` may carry reverse-parsed / deterministic card fields.
    """

    case_id: str
    bundle: dict[str, Any]
    suite: dict[str, Any] | None
    final_message: str | None
    final_message_sha256: str | None
    artifact_class: str | None
    bound: bool
    unbound_reason: str | None
    schema_pack: str | None
    metric_catalog: str | None
    expected_final_message: str | None
    expected_gold_codes: tuple[str, ...]
    failure_ids: tuple[str, ...]
    path_class_gate: str | None
    generation_task_input: dict[str, str] | None
    product_card: dict[str, Any]
    scored_target: str  # "final_message" | "product_card" | "missing"
    max_eval_bytes: int = DEFAULT_MAX_EVAL_BYTES
    meta: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    @property
    def input_nonempty(self) -> bool:
        """True when FIND-027 selected target has non-whitespace content."""
        if self.scored_target == "missing":
            return False
        if self.scored_target == "final_message":
            return bool(self.final_message and self.final_message.strip())
        # product_card target
        return bool(self.product_card)

    @property
    def input_size_bytes(self) -> int:
        """UTF-8 byte length of the *selected* scored target (FIND-026/027).

        Empty/whitespace ``final_message`` must not hide an oversize product card:
        measure the same artifact that ``scored_target`` selected. Product cards
        use deterministic JSON (sorted keys, compact separators).
        """
        if self.scored_target == "final_message":
            return len((self.final_message or "").encode("utf-8"))
        if self.scored_target == "product_card":
            if not self.product_card:
                return 0
            # Deterministic serialization — never rely on ``str(dict)`` repr.
            payload = json.dumps(
                self.product_card,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
            return len(payload.encode("utf-8"))
        return 0

    @property
    def input_size_ok(self) -> bool:
        """True when selected-target bytes are within ``max_eval_bytes`` (FIND-026)."""
        return self.input_size_bytes <= self.max_eval_bytes


def _as_dict(value: Any) -> dict[str, Any] | None:
    """Shallow ``dict`` copy for mappings; otherwise ``None``."""
    if value is None:
        return None
    if isinstance(value, Mapping):
        return dict(value)
    return None


def _str_tuple(value: Any) -> tuple[str, ...]:
    """Coerce a non-string sequence to a ``tuple[str, ...]``; else empty."""
    if value is None:
        return ()
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(str(x) for x in value if isinstance(x, str))
    return ()


def project_score_context(
    bundle: Mapping[str, Any],
    *,
    suite: Mapping[str, Any] | None = None,
    case_id: str | None = None,
    product_card: Mapping[str, Any] | None = None,
    max_eval_bytes: int = DEFAULT_MAX_EVAL_BYTES,
    allow_wrong_artifact: bool = False,
) -> ScoreContext:
    """Project a bundle (+ optional suite) into a FIND-027 score context.

    Prefer ``bundle.final_message``. Never default format scoring onto raw model
    dumps / generation JSON keys unless ``allow_wrong_artifact`` (tests only).
    Pins come from live S0 loaders; missing identity fields fail closed.
    """
    if not isinstance(bundle, Mapping):
        raise ScoreContextError("bundle must be an object")

    bid = case_id or bundle.get("case_id")
    if not isinstance(bid, str) or not bid.strip():
        raise ScoreContextError("case_id is required on bundle or argument")
    bid = bid.strip()

    warnings: list[str] = []

    # Reject wrong-artifact defaults (FIND-027).
    if not allow_wrong_artifact:
        for key in _WRONG_ARTIFACT_KEYS:
            if key in bundle and bundle.get("final_message") in (None, ""):
                warnings.append(f"ignored_wrong_artifact_key:{key}")

    final_message = bundle.get("final_message")
    if final_message is not None and not isinstance(final_message, str):
        raise ScoreContextError("final_message must be a string when present")

    final_sha = bundle.get("final_message_sha256")
    if isinstance(final_message, str) and final_message != "":
        computed = message_sha256(final_message)
        if isinstance(final_sha, str) and final_sha and final_sha != computed:
            warnings.append("final_message_sha256_mismatch")
        final_sha = computed
    elif not isinstance(final_sha, str):
        final_sha = None

    artifact_class = bundle.get("artifact_class")
    if artifact_class is not None and not isinstance(artifact_class, str):
        raise ScoreContextError("artifact_class must be a string")

    bound = bundle.get("bound", False)
    if not isinstance(bound, bool):
        raise ScoreContextError("bound must be a boolean")

    unbound_reason = bundle.get("unbound_reason")
    if unbound_reason is not None and not isinstance(unbound_reason, str):
        raise ScoreContextError("unbound_reason must be a string")

    card = _as_dict(product_card) or _as_dict(bundle.get("product_card")) or {}
    # score_card alias
    if not card:
        card = _as_dict(bundle.get("score_card")) or {}

    if isinstance(final_message, str) and final_message.strip():
        scored_target = "final_message"
    elif card:
        scored_target = "product_card"
        warnings.append("scored_target_fell_back_to_product_card")
    else:
        scored_target = "missing"

    gti = _as_dict(bundle.get("generation_task_input"))
    gti_out: dict[str, str] | None = None
    if gti is not None:
        gti_out = {str(k): str(v) for k, v in gti.items() if isinstance(v, str)}

    path_class = bundle.get("path_class_gate")
    if path_class is not None and not isinstance(path_class, str):
        path_class = str(path_class)

    meta = _as_dict(bundle.get("meta")) or {}

    return ScoreContext(
        case_id=bid,
        bundle=dict(bundle),
        suite=dict(suite) if isinstance(suite, Mapping) else None,
        final_message=final_message,
        final_message_sha256=final_sha,
        artifact_class=artifact_class if isinstance(artifact_class, str) else None,
        bound=bound,
        unbound_reason=unbound_reason if isinstance(unbound_reason, str) else None,
        schema_pack=bundle.get("schema_pack") if isinstance(bundle.get("schema_pack"), str) else None,
        metric_catalog=bundle.get("metric_catalog") if isinstance(bundle.get("metric_catalog"), str) else None,
        expected_final_message=bundle.get("expected_final_message")
        if isinstance(bundle.get("expected_final_message"), str)
        else None,
        expected_gold_codes=_str_tuple(bundle.get("expected_gold_codes")),
        failure_ids=_str_tuple(bundle.get("failure_ids")),
        path_class_gate=path_class,
        generation_task_input=gti_out,
        product_card=card,
        scored_target=scored_target,
        max_eval_bytes=max_eval_bytes,
        meta=meta,
        warnings=tuple(warnings),
    )


def live_pin_refs() -> list[str]:
    """Return live S0 pin strings for ScoreResult.pin_refs."""
    return [schema_pack_pin(), metric_catalog_pin()]
