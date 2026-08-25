"""R14 owner redaction ladder for export (plan §7.6, §8.4 deliverable 5).

Applies a per-profile field policy to an ``ape_bundle_v1`` dict before it is
placed into an export batch. The ladder is normative (§7.6):

* ``public_ci``        — hashes, codes, gates, metric ids only.
* ``message_only``     — final message + hybrid fields + scores; no diffs.
* ``default_scrub``    — message, path list, path_class, gold codes,
  trajectory names; no file bodies, raw diffs, secrets, full prompts, env.
* ``private_message``  — full final message + versions metadata.
* ``train_rich``       — message versions, preference pairs, allowlisted
  trajectory + optional full bodies under owner pin.
* ``antipattern_vault``— labeled hard negatives with mandatory ``train_label``.
* ``meta_eval_scrub``  — scrubbed judge_input refs + labels in envelope.
* ``raw_dev_unsafe``   — **refused** on export (owner-local debug only).

Hard laws:

* **Secrets always scrubbed.** Every retained free-text field passes through
  :func:`git_cg.telemetry.redact_payload` (betterleaks) regardless of profile.
* **Scrub failure ⇒ quarantine, not ambient leak.** When the scrubber returns
  the fail-safe omission marker, the field is *removed* and its dotted path is
  recorded under ``meta.redaction_quarantine`` — the payload is never emitted
  in the clear (§7.6: "scrub failure quarantines/omits fields").
* **P1-7:** recursive scrub over *all* retained strings with field-path
  tracking; ``meta`` is a typed key allowlist (not blanket copy). Keys matching
  secret/token/api_key/authorization/prompt/diff/environment/headers/cookie/
  credential are denied unless the active profile explicitly permits them.
* **P0-5:** authority surfaces required by projections (``gate``,
  ``score_card``/``product_card``, bound ``attempts``/final-accept refs, bundle
  ``id``) are retained under every export-capable profile; free-text leaves
  inside them are still scrubbed.
* The input bundle is **never mutated**; a redacted copy is returned.
"""

from __future__ import annotations

from typing import Any, Final

from git_cg.eval.enums import RedactionProfile
from git_cg.telemetry import redact_payload

__all__ = [
    "QUARANTINE_MARKER",
    "RedactionError",
    "redact_bundle_for_export",
]

#: Marker recorded in ``meta.redaction_quarantine`` for each omitted field.
QUARANTINE_MARKER = "scrub_fail_quarantined"

#: betterleaks fail-safe omission sentinel emitted by ``redact_payload``.
_OMISSION_SENTINEL = "[REDACTION FAILED - PAYLOAD OMITTED FOR SAFETY]"

#: Internal drop sentinel (never serialised).
_DROP: Final = object()

# Profiles that may retain allowlisted body-adjacent keys containing otherwise
# denied tokens (still secret-scrubbed). Only train/vault/private planes.
_OWNER_BODY_PROFILES: Final[frozenset[RedactionProfile]] = frozenset(
    {
        RedactionProfile.PRIVATE_MESSAGE,
        RedactionProfile.TRAIN_RICH,
        RedactionProfile.ANTIPATTERN_VAULT,
    }
)

# Even on owner-body profiles these key tokens are never permitted.
_ALWAYS_DENIED_KEY_TOKENS: Final[frozenset[str]] = frozenset(
    {
        "secret",
        "token",
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "credential",
        "headers",
        "environment",
        "prompt",
    }
)


class RedactionError(ValueError):
    """Redaction policy failure (fail-closed; ``export_validation`` class)."""


# --- Field policy tables -------------------------------------------------
#
# Each profile maps to the set of top-level bundle fields *retained*. Anything
# not listed is stripped. The policy is intentionally explicit (allowlist) so
# a new bundle field cannot leak by default — fail closed on unknown fields.
#
# P0-5 authority surfaces are unioned into every export-capable profile.

#: Hashes / codes / gates / ids — the thinnest plane (public_ci).
_PUBLIC_CI_FIELDS = frozenset(
    {
        "schema_version",
        "case_id",
        "artifact_class",
        "bound",
        "final_message_sha256",
        "provenance_label",
        "redaction_profile",
        "regime",
        "schema_pack",
        "metric_catalog",
        "session_thread_id",
        "trajectory_ref",
        "failure_ids",
        "prevention_ids",
        "expected_gold_codes",
        "path_class_gate",
        "instance_kind",
        "unbound_reason",
        "meta",
        # P0-5 authority surfaces (always export-capable).
        "id",
        "gate",
        "score_card",
        "product_card",
        "attempts",
    }
)

#: message_only adds the final message text (scrubbed) but no diffs/prompts.
_MESSAGE_ONLY_EXTRA = frozenset({"final_message"})

#: default_scrub adds expected message + generation task input *summary*
#: (path list / path_class / gold codes / trajectory names live here already).
_DEFAULT_SCRUB_EXTRA = frozenset({"final_message", "expected_final_message", "generation_task_input"})

#: private_message / train_rich keep the full message + versions metadata.
_PRIVATE_MESSAGE_EXTRA = frozenset({"final_message", "expected_final_message", "generation_task_input"})

#: train_rich additionally keeps the full generation task input snapshot.
_TRAIN_RICH_EXTRA = frozenset({"final_message", "expected_final_message", "generation_task_input"})

#: antipattern_vault keeps the message + ids (labeled hard negatives).
_ANTIPATTERN_EXTRA = frozenset({"final_message", "expected_final_message"})

#: meta_eval_scrub keeps scrubbed judge refs + labels in the envelope.
_META_EVAL_EXTRA = frozenset({"generation_task_input"})


_POLICY: dict[RedactionProfile, frozenset[str]] = {
    RedactionProfile.PUBLIC_CI: _PUBLIC_CI_FIELDS,
    RedactionProfile.MESSAGE_ONLY: _PUBLIC_CI_FIELDS | _MESSAGE_ONLY_EXTRA,
    RedactionProfile.DEFAULT_SCRUB: _PUBLIC_CI_FIELDS | _DEFAULT_SCRUB_EXTRA,
    RedactionProfile.PRIVATE_MESSAGE: _PUBLIC_CI_FIELDS | _PRIVATE_MESSAGE_EXTRA,
    RedactionProfile.TRAIN_RICH: _PUBLIC_CI_FIELDS | _TRAIN_RICH_EXTRA,
    RedactionProfile.ANTIPATTERN_VAULT: _PUBLIC_CI_FIELDS | _ANTIPATTERN_EXTRA,
    RedactionProfile.META_EVAL_SCRUB: _PUBLIC_CI_FIELDS | _META_EVAL_EXTRA,
}

#: Typed meta key allowlist (P1-7). Unknown keys are dropped (fail closed).
_META_ALLOW: Final[frozenset[str]] = frozenset(
    {
        # Producer / binding / session plumbing
        "producer",
        "binding",
        "accept_event",
        "encoding",
        "final_encoding",
        "source_encoding",
        "decode_errors",
        # Authority surfaces may also live under meta (binder layout)
        "score_card",
        "product_card",
        "gate",
        # Corpus / train labels (non-secret)
        "train_label",
        "capture_on",
        "path_class",
        "lifecycle",
        "trace_id",
        "thread_id",
        "generation_thread_id",
        "redaction_profile",
        # Train / split provenance (non-secret; used by train lake + projections)
        "split",
        "split_group_id",
        "provenance_label",
        # Quarantine bookkeeping (written by this module)
        "redaction_quarantine",
        "redaction_quarantine_marker",
        "redaction_denied_keys",
        # Scope / pin tags (non-secret)
        "scope",
        "owner_pin",
        "dataset_split",
        "artifact_class",
        "regime",
    }
)

#: Sub-keys under ``accept_event`` that must never be retained.
_ACCEPT_EVENT_DENY: Final[frozenset[str]] = frozenset({"token"})


def _scrub_text(value: Any) -> tuple[Any, bool]:
    """Scrub a free-text value; return ``(scrubbed, quarantined)``.

    ``quarantined`` is True when the scrubber failed safe (omission sentinel)
    — the caller must drop the field rather than emit the sentinel or the raw
    payload.

    After betterleaks, apply S6-C08 ``mask_secrets_in_text`` so known secret
    shapes still route through S4 ``mask_secret()`` even when the external
    scanner misses them (offline deterministic floor).
    """
    if not isinstance(value, str) or value == "":
        return value, False
    scrubbed = redact_payload(value)
    if scrubbed == _OMISSION_SENTINEL:
        return None, True
    # Local import keeps redaction free of config cycles at module import time.
    from git_cg.eval.evidence_scrub import mask_secrets_in_text

    masked = mask_secrets_in_text(scrubbed)
    return masked if masked is not None else scrubbed, False


def _key_denied(key: str, profile: RedactionProfile) -> bool:
    """Return True when a retained dict key is forbidden under ``profile``.

    Always-denied tokens (secrets/auth/prompt/env/headers/cookies) are never
    owner-relaxable. ``diff`` keys are denied on thin/default profiles and only
    permitted on owner-body profiles (values still secret-scrubbed).
    """
    lowered = key.lower().replace("-", "_")
    # Always-denied secret/auth/prompt surfaces — never owner-relaxable.
    if any(token in lowered for token in _ALWAYS_DENIED_KEY_TOKENS):
        return True
    # ``diff`` is stripped on non-owner-body profiles; owner-body profiles may
    # keep structured diff *summaries* (values still scrubbed).
    return "diff" in lowered and profile not in _OWNER_BODY_PROFILES


def _join_path(prefix: str, key: str | int) -> str:
    if prefix == "":
        return str(key)
    return f"{prefix}.{key}"


def _scrub_tree(
    value: Any,
    *,
    path: str,
    profile: RedactionProfile,
    quarantined: list[str],
    denied: list[str],
    deny_keys: bool,
) -> Any:
    """Deep-copy ``value`` while scrubbing strings and enforcing key policy.

    Returns :data:`_DROP` when the entire node must be omitted.
    """
    if isinstance(value, str):
        scrubbed, was_quarantined = _scrub_text(value)
        if was_quarantined:
            quarantined.append(path or "<root>")
            return _DROP
        return scrubbed

    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for raw_key, child in value.items():
            key = str(raw_key)
            child_path = _join_path(path, key)
            if deny_keys and _key_denied(key, profile):
                denied.append(child_path)
                continue
            cleaned = _scrub_tree(
                child,
                path=child_path,
                profile=profile,
                quarantined=quarantined,
                denied=denied,
                deny_keys=deny_keys,
            )
            if cleaned is _DROP:
                continue
            out[key] = cleaned
        return out

    if isinstance(value, list):
        out_list: list[Any] = []
        for idx, child in enumerate(value):
            child_path = _join_path(path, idx)
            cleaned = _scrub_tree(
                child,
                path=child_path,
                profile=profile,
                quarantined=quarantined,
                denied=denied,
                deny_keys=deny_keys,
            )
            if cleaned is _DROP:
                # Keep list alignment stable for attempt indices: use null slot
                # only when intermediate; for free-text leaves, omit by skipping
                # would shift indices — prefer null placeholder for attempts.
                out_list.append(None)
                continue
            out_list.append(cleaned)
        return out_list

    if isinstance(value, tuple):
        cleaned_items: list[Any] = []
        for idx, child in enumerate(value):
            child_path = _join_path(path, idx)
            cleaned = _scrub_tree(
                child,
                path=child_path,
                profile=profile,
                quarantined=quarantined,
                denied=denied,
                deny_keys=deny_keys,
            )
            if cleaned is _DROP:
                cleaned_items.append(None)
            else:
                cleaned_items.append(cleaned)
        return tuple(cleaned_items)

    # Numbers, bools, None, and other JSON-scalar-ish values pass through.
    return value


def _scrub_meta(
    meta: dict[str, Any],
    *,
    profile: RedactionProfile,
    quarantined: list[str],
    denied: list[str],
) -> dict[str, Any]:
    """Typed meta allowlist + recursive scrub (P1-7)."""
    out: dict[str, Any] = {}
    for raw_key, child in meta.items():
        key = str(raw_key)
        path = f"meta.{key}"
        if key not in _META_ALLOW:
            denied.append(path)
            continue
        if _key_denied(key, profile):
            denied.append(path)
            continue
        if key == "accept_event" and isinstance(child, dict):
            # Never retain accept-event tokens (auth-adjacent).
            cleaned_event: dict[str, Any] = {}
            for ek, ev in child.items():
                ek_s = str(ek)
                if ek_s in _ACCEPT_EVENT_DENY or _key_denied(ek_s, profile):
                    denied.append(f"{path}.{ek_s}")
                    continue
                cleaned = _scrub_tree(
                    ev,
                    path=f"{path}.{ek_s}",
                    profile=profile,
                    quarantined=quarantined,
                    denied=denied,
                    deny_keys=True,
                )
                if cleaned is _DROP:
                    continue
                cleaned_event[ek_s] = cleaned
            out[key] = cleaned_event
            continue
        cleaned = _scrub_tree(
            child,
            path=path,
            profile=profile,
            quarantined=quarantined,
            denied=denied,
            deny_keys=True,
        )
        if cleaned is _DROP:
            continue
        out[key] = cleaned
    return out


def _promote_authority(out: dict[str, Any], meta: dict[str, Any]) -> None:
    """Lift binder-layout authority from ``meta`` when top-level is empty (P0-5).

    Projections read top-level ``gate`` / ``score_card`` / ``product_card``.
    Accept-path binders currently nest ``score_card`` under ``meta``; promotion
    keeps the export join honest without inventing values.
    """
    for key in ("gate", "score_card", "product_card"):
        if key in out and out[key] not in (None, {}, []):
            continue
        nested = meta.get(key)
        if nested not in (None, {}, []):
            out[key] = nested


def redact_bundle_for_export(
    bundle: dict[str, Any],
    profile: RedactionProfile | str,
) -> dict[str, Any]:
    """Return a redacted copy of ``bundle`` under the R14 ``profile``.

    The input is never mutated. The returned copy:

    * retains only the profile's allowlisted top-level fields (incl. P0-5
      authority surfaces on every export-capable profile);
    * recursively scrubs every retained free-text string through betterleaks;
    * applies a typed ``meta`` allowlist and denies ambient secret/prompt/diff
      keys (P1-7);
    * **quarantines** any field whose scrub fails safe — the field is removed
      and its dotted path is appended to ``meta.redaction_quarantine`` so
      operators can see that something was withheld (no silent ambient leak);
    * stamps ``redaction_profile`` to the applied profile.

    Raises:
        RedactionError: ``raw_dev_unsafe`` requested (never valid on export),
            or an unknown profile token (fail closed).
    """
    try:
        prof = profile if isinstance(profile, RedactionProfile) else RedactionProfile(str(profile))
    except ValueError as exc:
        raise RedactionError(f"unknown redaction profile: {profile!r}") from exc

    if prof is RedactionProfile.RAW_DEV_UNSAFE:
        raise RedactionError("raw_dev_unsafe is owner-local debug only and is never a valid export profile (§7.6)")

    allowed = _POLICY[prof]
    out: dict[str, Any] = {}
    quarantined: list[str] = []
    denied: list[str] = []

    for key, value in bundle.items():
        if key not in allowed:
            continue
        if key == "meta":
            # Handled after the loop so quarantine/deny bookkeeping can merge.
            continue
        if key == "generation_task_input":
            if not isinstance(value, dict):
                cleaned = _scrub_tree(
                    value,
                    path=key,
                    profile=prof,
                    quarantined=quarantined,
                    denied=denied,
                    deny_keys=True,
                )
                if cleaned is not _DROP:
                    out[key] = cleaned
                continue
            cleaned_task = _scrub_tree(
                value,
                path=key,
                profile=prof,
                quarantined=quarantined,
                denied=denied,
                deny_keys=True,
            )
            if cleaned_task is _DROP:
                continue
            out[key] = cleaned_task
            continue

        cleaned = _scrub_tree(
            value,
            path=key,
            profile=prof,
            quarantined=quarantined,
            denied=denied,
            deny_keys=True,
        )
        if cleaned is _DROP:
            continue
        out[key] = cleaned

    # Meta: typed allowlist + recursive scrub (start from input meta only).
    raw_meta = bundle.get("meta") if isinstance(bundle.get("meta"), dict) else {}
    meta_out = _scrub_meta(raw_meta, profile=prof, quarantined=quarantined, denied=denied)

    # P0-5: promote binder-nested authority to top-level for projection join.
    _promote_authority(out, meta_out)

    # Stamp the applied profile (the bundle's own claim may differ pre-export).
    out["redaction_profile"] = prof.value

    if quarantined:
        existing_q = list(meta_out.get("redaction_quarantine") or [])
        meta_out["redaction_quarantine"] = sorted(set(existing_q) | set(quarantined))
        meta_out["redaction_quarantine_marker"] = QUARANTINE_MARKER
    if denied:
        existing_d = list(meta_out.get("redaction_denied_keys") or [])
        meta_out["redaction_denied_keys"] = sorted(set(existing_d) | set(denied))

    if meta_out:
        out["meta"] = meta_out
    elif "meta" in allowed and bundle.get("meta") is not None:
        # Preserve empty meta object only when input had meta and nothing remains
        # after allowlist — omit entirely to avoid hollow noise.
        pass

    return out
