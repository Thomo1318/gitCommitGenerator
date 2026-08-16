"""S3 capture enablement law (Issue #231, S3-contract-v1.4 / D1, N19.5).

Single canonical switch — ``GIT_CG_EVAL_CAPTURE`` — gates local Layer-A bind
writes, ``trajectory_evidence_v1`` emission, and session-twin capture. Capture
is **off by default** for basic users (I10); a normal ``git-cg commit`` must
never require S3 capture, ``.eval/``, Opik, or scoring.

Parse law (fail-closed, never raises on the product path):

* Truthy  → on:  ``1``, ``true``, ``on``, ``yes`` (case-insensitive, stripped).
* Falsy   → off: unset, empty, ``0``, ``false``, ``off``, ``no``.
* Any other token → **off** (fail closed to non-capture).

Optional alias ``GIT_CG_EVAL_PROFILE`` is read **only** when the canonical
variable is unset/empty; it can widen to on for ``maintainer``/``train``/
``dogfood`` but must never widen the basic default, and the canonical variable
always wins when set.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

__all__ = ["CAPTURE_ENV", "PROFILE_ENV", "capture_enabled"]

#: Canonical capture switch (D1).
CAPTURE_ENV = "GIT_CG_EVAL_CAPTURE"

#: Optional profile alias, read only when the canonical switch is unset/empty.
PROFILE_ENV = "GIT_CG_EVAL_PROFILE"

_TRUTHY = frozenset({"1", "true", "on", "yes"})
_FALSY = frozenset({"0", "false", "off", "no"})

#: Profiles that enable capture when the canonical switch is unset/empty (D1).
_CAPTURE_ON_PROFILES = frozenset({"maintainer", "train", "dogfood"})


def _parse_capture(value: str | None) -> bool | None:
    """Parse the canonical capture token.

    Returns ``True``/``False`` for recognised tokens, or ``None`` when the
    variable is unset/empty (so the profile alias may be consulted). Unknown
    non-empty tokens fail closed to ``False`` (off) — never raise.
    """
    if value is None:
        return None
    token = value.strip().lower()
    if token == "":
        return None
    if token in _TRUTHY:
        return True
    if token in _FALSY:
        return False
    return False  # fail closed on unknown token


def capture_enabled(env: Mapping[str, str] | None = None) -> bool:
    """
    Determine whether capture is enabled by the environment configuration.

    Parameters:
        env: Environment mapping to inspect; defaults to :data:`os.environ`.

    Returns:
        ``True`` when the capture switch is enabled or the profile is
        ``maintainer``, ``train``, or ``dogfood``; ``False`` otherwise.
    """
    source = os.environ if env is None else env
    parsed = _parse_capture(source.get(CAPTURE_ENV))
    if parsed is not None:
        return parsed

    profile = source.get(PROFILE_ENV)
    if profile is None:
        return False
    return profile.strip().lower() in _CAPTURE_ON_PROFILES
