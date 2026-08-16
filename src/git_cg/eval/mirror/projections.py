"""Bundle → Opik projections (plan §7.2.9, §8.4 deliverable 4).

Projects a redacted ``ape_bundle_v1`` into the upload payload shapes:

* **trace/span** — the final-bytes-bound attempt as a trace; the deterministic
  gate + score card become metadata/feedback (never re-scored in the cloud).
* **thread** — the ``commit_session_thread_v1`` twin as an Opik thread.
* **feedback** — the product deterministic ``score_card`` as feedback scores.

These projections are **lossy by design**: they carry the redacted, allowlisted
bundle, not raw diffs/secrets. No cloud-side scoring rules are created from raw
traces (FIND-013 / §7.2.10); the deterministic product score card is the
authority and is exported as feedback.

Pure offline builders — no network, no Opik import.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "project_bundle_to_trace",
    "project_score_card_to_feedback",
    "project_session_thread",
]


def _attempts(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    return list(bundle.get("attempts") or [])


def _final_attempt(bundle: dict[str, Any]) -> dict[str, Any] | None:
    attempts = _attempts(bundle)
    return attempts[-1] if attempts else None


def project_bundle_to_trace(
    bundle: dict[str, Any],
    *,
    experiment_name: str,
) -> dict[str, Any]:
    """Project a redacted ``ape_bundle_v1`` to a trace/span upload payload.

    The trace carries the bundle's final-bytes-bound attempt and the
    deterministic gate verdict. The full score card is attached as metadata
    (authoritative, not recomputed). Input/output are the redacted bundle
    fields only — never raw diff text.
    """
    final = _final_attempt(bundle) or {}
    gate = bundle.get("gate") or {}
    score_card = bundle.get("score_card") or bundle.get("product_card") or {}

    return {
        "input": {
            "bundle_id": bundle.get("id"),
            "schema_version": bundle.get("schema_version"),
            "attempt_count": len(_attempts(bundle)),
        },
        "output": {
            "final_message": final.get("final_message"),
            "scored_target": final.get("scored_target"),
        },
        "metadata": {
            "experiment_name": experiment_name,
            "deterministic_pass": gate.get("deterministic_pass"),
            "gate": gate,
            "score_card": score_card,
            "redaction_profile": (bundle.get("meta") or {}).get("redaction_profile"),
        },
    }


def project_session_thread(
    session_thread: dict[str, Any],
    *,
    experiment_name: str,
) -> dict[str, Any]:
    """Project a ``commit_session_thread_v1`` twin to an Opik thread payload.

    Preserves the session id and lifecycle; message versions are carried as
    redacted thread messages. No ids are invented.
    """
    meta = session_thread.get("meta") or {}
    return {
        "thread_id": session_thread.get("session_thread_id"),
        "experiment_name": experiment_name,
        "lifecycle": meta.get("lifecycle"),
        "messages": list(session_thread.get("message_versions") or []),
        "metadata": {
            "attempt_ids": list(session_thread.get("attempt_ids") or []),
            "redaction_profile": session_thread.get("redaction_profile"),
            "trace_id": meta.get("trace_id"),
            "generation_thread_id": meta.get("generation_thread_id"),
        },
    }


def project_score_card_to_feedback(
    bundle: dict[str, Any],
    *,
    experiment_name: str,
) -> list[dict[str, Any]]:
    """Project the deterministic ``score_card`` to Opik feedback scores.

    Each numeric entry in the score card becomes one feedback score. The
    product score card is the authority; these are exported as-is and never
    recomputed from raw traces.
    """
    score_card = bundle.get("score_card") or bundle.get("product_card") or {}
    out: list[dict[str, Any]] = []
    for key, value in score_card.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            out.append(
                {
                    "name": str(key),
                    "value": float(value),
                    "experiment_name": experiment_name,
                    "source": "deterministic_score_card",
                }
            )
    return out
