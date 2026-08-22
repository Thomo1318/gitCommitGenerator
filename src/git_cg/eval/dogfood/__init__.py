"""S6 Slice 7 maintainer dogfood surface (Issue #246 / R12 / §6.12).

High-frequency Lane C/GEval-style advisory capture on *our own* commits.
Modes are closed: ``off | sample | always | async``. The profile is **off by
default for non-maintainers** and every attachment carries
``authority = "advisory"`` — dogfood is never a sole accept/golden gate.

Sample-mode membership is deterministic and offline-reproducible
(S6-G08): explicit ``--seed`` or a stable hash of
``(experiment_id|run_id, suite_id, rate)``; the attachment records seed, rate,
population id, and selected ids and/or a selected-set hash.

Async mode never blocks the commit path (S6-G02a structural seam).
"""

from git_cg.eval.dogfood.capture import (
    CAPTURE_ON_VALUES,
    DOGFOOD_MODES,
    DOGFoodError,
    attachment_reproduces_membership,
    build_attachment,
    capture_dogfood,
    derive_sample_seed,
    is_maintainer_profile,
    resolve_dogfood_mode,
    select_sample_members,
)

__all__ = [
    "CAPTURE_ON_VALUES",
    "DOGFOOD_MODES",
    "DOGFoodError",
    "attachment_reproduces_membership",
    "build_attachment",
    "capture_dogfood",
    "derive_sample_seed",
    "is_maintainer_profile",
    "resolve_dogfood_mode",
    "select_sample_members",
]
