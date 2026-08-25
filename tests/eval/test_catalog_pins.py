"""S0-B: catalog + pin reproducibility — offline only."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from git_cg.eval.catalog import load_metric_catalog, metric_ids
from git_cg.eval.enums import Authority, Polarity, Source
from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin
from git_cg.eval.score_result import ScoreResultV1

REQUIRED_PREFIX_FAMILIES = {
    "a.": "A",
    "b.": "B",
    "c.": "C",
    "d.": "D",
    "e.": "E",
    "f.": "F",
    "g.": "G",
    "h.": "H",
    "i.": "I",
    "gate.": "gate",
    "cprime.": "Cprime",
}


def test_s0_b01_catalog_lists_families_and_secondary() -> None:
    cat = load_metric_catalog()
    ids = metric_ids()
    for prefix in REQUIRED_PREFIX_FAMILIES:
        assert any(mid.startswith(prefix) for mid in ids), prefix
    law_ids = {law["law_id"] for law in cat["laws"]}
    assert {"M10", "M11", "M0", "M1"} <= law_ids
    assert any(mid.startswith("i.") for mid in ids)
    assert any(mid.startswith("cprime.") for mid in ids)
    assert "d.skeleton_fallback_final" in ids
    assert "human.gold_dispute" in ids
    assert "human.regime_label" in ids


def test_s0_b02_every_row_has_polarity_and_authority() -> None:
    for row in load_metric_catalog()["metrics"]:
        assert row["polarity"] in {
            "higher_is_better",
            "lower_is_better",
            "pass_fail",
        }
        assert row["authority"] in {"law", "advisory", "lab", "ops", "projection"}


def test_s0_b03_score_result_requires_core_fields() -> None:
    ok = ScoreResultV1(
        metric_id="a.final_message_present",
        polarity=Polarity.PASS_FAIL,
        authority=Authority.LAW,
        source=Source.LOCAL_WRAPPER,
        value=True,
    )
    assert ok.metric_id == "a.final_message_present"

    with pytest.raises(ValidationError):
        ScoreResultV1.model_validate(
            {
                "metric_id": "a.final_message_present",
                "polarity": "pass_fail",
                "source": "local_wrapper",
                "value": True,
            }
        )


def test_s0_b04_polarity_registry_covers_risky_builtins() -> None:
    reg = load_metric_catalog()["polarity_registry"]
    names = {row["vendor_name"] for row in reg}
    assert {"Hallucination", "Moderation", "GEval"} <= names


def test_s0_b05_pins_stable_across_two_invocations() -> None:
    s1, s2 = schema_pack_pin(), schema_pack_pin()
    m1, m2 = metric_catalog_pin(), metric_catalog_pin()
    assert s1 == s2
    assert m1 == m2
    assert s1.startswith("schema_pack_v0@")
    assert m1.startswith("metric_catalog_v0@")
    assert len(s1.split("@", 1)[1]) == 64
    assert len(m1.split("@", 1)[1]) == 64
    # Frozen S0 identities (content hashes). Drift fails closed here.
    assert s1 == ("schema_pack_v0@8616781fb87ea4721253f7efacf120c7c602062a6c578b8a4173fbae5341c3c3")
    assert m1 == ("metric_catalog_v0@430a62c1d7971e1145cfffd41e608a5f6bd39d284a3d050f991b8537f817eb75")


def test_s0_b08_numeric_scores_accept_strict_int() -> None:
    ok = ScoreResultV1(
        metric_id="d.strict_fail_set",
        polarity=Polarity.LOWER_IS_BETTER,
        authority=Authority.LAW,
        source=Source.LOCAL_WRAPPER,
        value=3,
        threshold=0,
        duration_ms=12,
    )
    assert ok.value == 3
    assert ok.threshold == 0
    assert ok.duration_ms == 12


def test_s0_b09_whitespace_metric_id_rejected() -> None:
    with pytest.raises(ValidationError):
        ScoreResultV1(
            metric_id="   ",
            polarity=Polarity.PASS_FAIL,
            authority=Authority.LAW,
            source=Source.LOCAL_WRAPPER,
            value=True,
        )


def test_s0_b06_redaction_profiles_include_train_ladder() -> None:
    profiles = set(load_metric_catalog()["closed_enums"]["redaction_profile"])
    assert {
        "public_ci",
        "default_scrub",
        "private_message",
        "train_rich",
        "antipattern_vault",
    } <= profiles


def test_s0_b07_pass_fail_rejects_numeric_value() -> None:
    with pytest.raises(ValidationError):
        ScoreResultV1(
            metric_id="a.final_message_present",
            polarity=Polarity.PASS_FAIL,
            authority=Authority.LAW,
            source=Source.LOCAL_WRAPPER,
            value=1.0,
        )
