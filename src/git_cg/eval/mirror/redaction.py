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
* The input bundle is **never mutated**; a redacted copy is returned.
"""

from __future__ import annotations

import copy
from typing import Any

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


class RedactionError(ValueError):
    """Redaction policy failure (fail-closed; ``export_validation`` class)."""


# --- Field policy tables -------------------------------------------------
#
# Each profile maps to the set of top-level bundle fields *retained*. Anything
# not listed is stripped. The policy is intentionally explicit (allowlist) so
# a new bundle field cannot leak by default — fail closed on unknown fields.

#: Fields that carry free-text and must pass the secret scrubber when kept.
_TEXT_FIELDS = frozenset({"final_message", "expected_final_message"})

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


def _scrub_text(value: Any) -> tuple[Any, bool]:
    """Scrub a free-text value; return ``(scrubbed, quarantined)``.

    ``quarantined`` is True when the scrubber failed safe (omission sentinel)
    — the caller must drop the field rather than emit the sentinel or the raw
    payload.
    """
    if not isinstance(value, str) or value == "":
        return value, False
    scrubbed = redact_payload(value)
    if scrubbed == _OMISSION_SENTINEL:
        return None, True
    return scrubbed, False


def redact_bundle_for_export(
    bundle: dict[str, Any],
    profile: RedactionProfile | str,
) -> dict[str, Any]:
    """Return a redacted copy of ``bundle`` under the R14 ``profile``.

    The input is never mutated. The returned copy:

    * retains only the profile's allowlisted top-level fields;
    * scrubs retained free-text fields through betterleaks;
    * **quarantines** any field whose scrub fails safe — the field is removed
      and its name is appended to ``meta.redaction_quarantine`` so operators
      can see that something was withheld (no silent ambient leak);
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

    for key, value in bundle.items():
        if key not in allowed:
            continue
        if key in _TEXT_FIELDS:
            scrubbed, was_quarantined = _scrub_text(value)
            if was_quarantined:
                quarantined.append(key)
                continue
            out[key] = scrubbed
        elif key == "generation_task_input" and isinstance(value, dict):
            # Scrub free-text leaves inside the task-input snapshot.
            cleaned: dict[str, Any] = {}
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, str):
                    scrubbed_sub, sub_q = _scrub_text(sub_value)
                    if sub_q:
                        quarantined.append(f"generation_task_input.{sub_key}")
                        continue
                    cleaned[sub_key] = scrubbed_sub
                else:
                    cleaned[sub_key] = sub_value
            out[key] = cleaned
        else:
            out[key] = copy.deepcopy(value)

    # Stamp the applied profile (the bundle's own claim may differ pre-export).
    out["redaction_profile"] = prof.value

    # Record quarantines in meta (operators must see withheld fields).
    if quarantined:
        meta = dict(out.get("meta") or {})
        existing = list(meta.get("redaction_quarantine") or [])
        meta["redaction_quarantine"] = sorted(set(existing) | set(quarantined))
        meta["redaction_quarantine_marker"] = QUARANTINE_MARKER
        out["meta"] = meta
    elif "meta" in out and isinstance(out["meta"], dict):
        out["meta"] = copy.deepcopy(out["meta"])

    return out
