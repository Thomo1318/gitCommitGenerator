"""Closed enums for the evaluation harness (fail closed on unknown values)."""

from __future__ import annotations

from enum import StrEnum


class Polarity(StrEnum):
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"
    PASS_FAIL = "pass_fail"


class Authority(StrEnum):
    LAW = "law"
    ADVISORY = "advisory"
    LAB = "lab"
    OPS = "ops"
    PROJECTION = "projection"


class Family(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"
    H = "H"
    FAMILY_I = "I"
    CPRIME = "Cprime"
    HUMAN = "human"
    LAB = "lab"
    DOGFOOD = "dogfood"
    GATE = "gate"
    BINDING = "binding"
    EXPORT = "export"
    NLP = "nlp"


class Source(StrEnum):
    """Closed ScoreResult source vocabulary for the local catalog.

    Plan narrative sometimes says ``llm_judge`` / ``heuristic_diag``; those map
    into this closed set (``lane_c_judge`` / ``local_wrapper`` / ``lab_meta``).
    """

    LOCAL_WRAPPER = "local_wrapper"
    LANE_C_JUDGE = "lane_c_judge"
    HUMAN = "human"
    LAB_META = "lab_meta"
    EXPORT_HEALTH = "export_health"


class Severity(StrEnum):
    BLOCK = "block"
    WARN = "warn"
    INFO = "info"


class ArtifactClass(StrEnum):
    """Fail-closed artifact classes used on freeze surfaces."""

    FINAL_ACCEPT = "final_accept"
    FIXTURE_EXPECTED = "fixture_expected"
    FIXTURE = "fixture"
    LIVE_REGEN = "live_regen"
    GIT_RAW = "Git-raw"
    GIT_MID = "Git-mid"
    GOLD_FINAL = "Gold-final"
    REWRITE_MAP_CONFIRMED = "Rewrite-map-confirmed"
    OPIK_UNBOUND = "Opik-unbound"
    PLAN_ONLY = "plan_only"
    TRAJECTORY_ONLY = "trajectory_only"
    TRAIN_ROW = "train_row"
    EXPORT_BATCH = "export_batch"


class RedactionProfile(StrEnum):
    """R14 owner redaction ladder. ``train_rich`` does not imply gate authority."""

    PUBLIC_CI = "public_ci"
    DEFAULT_SCRUB = "default_scrub"
    PRIVATE_MESSAGE = "private_message"
    TRAIN_RICH = "train_rich"
    ANTIPATTERN_VAULT = "antipattern_vault"
    MESSAGE_ONLY = "message_only"
    META_EVAL_SCRUB = "meta_eval_scrub"
    RAW_DEV_UNSAFE = "raw_dev_unsafe"


class ProvenanceLabel(StrEnum):
    """Provenance labels (may overlap names with artifact_class where plan uses both)."""

    GIT_RAW = "Git-raw"
    GIT_MID = "Git-mid"
    GOLD_FINAL = "Gold-final"
    REWRITE_MAP_CONFIRMED = "Rewrite-map-confirmed"
    OPIK_UNBOUND = "Opik-unbound"
    FINAL_ACCEPT = "final_accept"
    LIVE_REGEN = "live_regen"
    FIXTURE = "fixture"


POLARITY = tuple(p.value for p in Polarity)
AUTHORITY = tuple(a.value for a in Authority)
FAMILY = tuple(f.value for f in Family)
SOURCE = tuple(s.value for s in Source)
SEVERITY = tuple(s.value for s in Severity)
ARTIFACT_CLASS = tuple(a.value for a in ArtifactClass)
REDACTION_PROFILE = tuple(r.value for r in RedactionProfile)
PROVENANCE_LABEL = tuple(p.value for p in ProvenanceLabel)
