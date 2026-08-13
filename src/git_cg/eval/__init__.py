"""Opik evaluation harness contract floor (S0).

Offline-only package: schemas, catalog pins, closed enums, ScoreResult_v1.
Does not require the ``opik`` package and does not score product commits.
"""

from __future__ import annotations

from git_cg.eval.catalog import load_metric_catalog
from git_cg.eval.enums import (
    ARTIFACT_CLASS,
    AUTHORITY,
    FAMILY,
    POLARITY,
    REDACTION_PROFILE,
    SOURCE,
)
from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin
from git_cg.eval.score_result import ScoreResultV1

__all__ = [
    "ARTIFACT_CLASS",
    "AUTHORITY",
    "FAMILY",
    "POLARITY",
    "REDACTION_PROFILE",
    "SOURCE",
    "ScoreResultV1",
    "load_metric_catalog",
    "metric_catalog_pin",
    "schema_pack_pin",
]
