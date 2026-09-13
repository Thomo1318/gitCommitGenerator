"""S4-F train dual-axis projections (Q18 / D18 / D28 / P2-4)."""

from __future__ import annotations

import pytest

from git_cg.eval.enums import RedactionProfile
from git_cg.eval.mirror.train import (
    POSITIVE_GOLD,
    TRAIN_DATASET_ID,
    TRAIN_LABELS,
    TrainProjectionError,
    build_train_projection,
    filter_positive_gold,
    normalize_train_label,
    project_train_row,
)

_ABSENT = object()


def _bundle(
    *,
    bid: str,
    label: str | None,
    split: str = "train",
    regime: str | None = None,
    profile: object = "train_rich",
    top_profile: object = _ABSENT,
) -> dict:
    """Build a train-projection bundle fixture with optional label/regime.

    ``profile`` stamps ``meta.redaction_profile`` (``_ABSENT`` omits the key
    entirely — distinct from empty/invalid tokens). ``top_profile`` stamps the
    top-level ``redaction_profile`` when not ``_ABSENT``.
    """
    meta: dict = {"split_group_id": f"sg-{bid}"}
    if profile is not _ABSENT:
        meta["redaction_profile"] = profile
    if label is not None:
        meta["train_label"] = label
    if regime is not None:
        meta["regime"] = regime
    bundle = {
        "id": bid,
        "artifact_class": "final_accept",
        "gate": {"deterministic_pass": True},
        "score_card": {"format_compliance": 1.0},
        "meta": meta,
        "split": split,
    }
    if top_profile is not _ABSENT:
        bundle["redaction_profile"] = top_profile
    return bundle


class TestNormalizeTrainLabel:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("positive", "positive"),
            ("POSITIVE", "positive"),
            ("train-positive", "positive"),
            ("preference_chosen", "positive"),
            ("negative", "negative"),
            ("hard_negative", "negative"),
            ("antipattern_vault", "negative"),
            ("train_negative", "negative"),
            (None, None),
            ("", None),
            ("unlabeled", None),
            ("mystery", None),
        ],
    )
    def test_aliases(self, raw: object, expected: str | None) -> None:
        assert normalize_train_label(raw) == expected

    def test_closed_vocab(self) -> None:
        assert frozenset({"positive", "negative"}) == TRAIN_LABELS


class TestProjectTrainRow:
    def test_labeled_positive(self) -> None:
        row = project_train_row(_bundle(bid="b1", label="positive"))
        assert row is not None
        assert row["label"] == "positive"
        assert row["dataset_id"] == TRAIN_DATASET_ID
        assert row["split"] == "train"
        assert row["redaction_profile"] == "train_rich"
        assert row["ci_sole_green"] is False
        assert row["product_accept_authority"] is False
        assert row["authority"] == "corpus_retention"

    def test_unlabeled_excluded(self) -> None:
        assert project_train_row(_bundle(bid="b2", label=None)) is None


class TestFilterPositiveGold:
    def test_negatives_never_join_positive_gold(self) -> None:
        rows = [
            {"bundle_id": "p", "label": "positive", "regime": "A", "redaction_profile": "train_rich"},
            {"bundle_id": "n", "label": "negative", "regime": "antipattern"},
            {"bundle_id": "u", "label": None},
        ]
        gold = filter_positive_gold(rows)
        assert [g["bundle_id"] for g in gold] == ["p"]
        assert all(g["projection"] == POSITIVE_GOLD for g in gold)
        assert all(g["label"] == "positive" for g in gold)

    def test_unlabeled_excluded_from_positive_gold(self) -> None:
        assert filter_positive_gold([{"bundle_id": "x", "train_label": "unlabeled"}]) == []


class TestBuildTrainProjection:
    def test_q18_single_dataset_metadata(self) -> None:
        bundles = [
            _bundle(bid="p1", label="positive", split="train"),
            _bundle(bid="n1", label="negative", split="train", regime="antipattern"),
            _bundle(bid="u1", label=None),
        ]
        proj = build_train_projection(bundles)
        assert proj["dataset_id"] == TRAIN_DATASET_ID
        assert proj["q18"] == "single_dataset_label_split_metadata"
        assert proj["excluded_unlabeled"] == 1
        assert {r["bundle_id"] for r in proj["positive_gold"]} == {"p1"}
        assert {r["bundle_id"] for r in proj["negatives"]} == {"n1"}
        assert proj["ci_sole_green"] is False
        assert proj["product_accept_authority"] is False
        # Single dataset — both labels share dataset_id.
        assert {r["dataset_id"] for r in proj["rows"]} == {TRAIN_DATASET_ID}

    def test_none_bundle_ids_do_not_false_positive_overlap(self) -> None:
        """Missing bundle ids must not trip the positive/negative overlap guard."""
        pos = _bundle(bid="tmp-pos", label="positive")
        neg = _bundle(bid="tmp-neg", label="negative", regime="antipattern")
        pos["id"] = None
        neg["id"] = None
        pos["meta"] = {**pos["meta"], "split_group_id": "sg-missing"}
        neg["meta"] = {**neg["meta"], "split_group_id": "sg-missing-neg"}
        proj = build_train_projection([pos, neg, _bundle(bid="p2", label="positive")])
        assert len(proj["positive_gold"]) == 2
        assert len(proj["negatives"]) == 1
        assert {r.get("bundle_id") for r in proj["positive_gold"]} == {None, "p2"}

    def test_overlapping_bundle_id_raises(self) -> None:
        with pytest.raises(TrainProjectionError, match="overlap"):
            build_train_projection(
                [
                    _bundle(bid="dup", label="positive"),
                    _bundle(bid="dup", label="negative", regime="antipattern"),
                ]
            )

    def test_missing_ids_do_not_collide(self) -> None:
        proj = build_train_projection(
            [
                {"meta": {"train_label": "positive", "redaction_profile": "train_rich"}},
                {"meta": {"train_label": "negative", "redaction_profile": "train_rich", "regime": "antipattern"}},
            ]
        )
        assert len(proj["rows"]) == 2
        assert len(proj["positive_gold"]) == 1
        assert len(proj["negatives"]) == 1

    def test_s4_f01_rows_carry_labels_redaction_scope(self) -> None:
        proj = build_train_projection([_bundle(bid="p1", label="positive")])
        row = proj["rows"][0]
        for key in (
            "label",
            "split",
            "split_group_id",
            "redaction_profile",
            "provenance_label",
            "source",
            "authority",
        ):
            assert key in row and row[key] not in (None, ""), key


class TestFilterPositiveGoldProfileGate:
    def test_positive_gold_rejects_missing_profile(self) -> None:
        rows = [
            {"bundle_id": "p", "label": "positive", "regime": "A"},
            {"bundle_id": "q", "label": "positive", "regime": "A", "redaction_profile": "train_rich"},
        ]
        gold = filter_positive_gold(rows)
        assert [g["bundle_id"] for g in gold] == ["q"]


class TestTrainProfileMatrix:
    """Fail-closed export-profile matrix (missing/conflict/invalid → excluded)."""

    def test_missing_profile_excluded_from_train_gold(self) -> None:
        proj = build_train_projection([_bundle(bid="b1", label="positive", profile=_ABSENT)])
        assert proj["rows"] == []
        assert proj["positive_gold"] == []
        assert proj["excluded_profile"] == 1
        assert proj["excluded_unlabeled"] == 0

    def test_conflicting_top_meta_profiles_excluded(self) -> None:
        bundle = _bundle(bid="b1", label="positive", profile="default_scrub", top_profile="train_rich")
        proj = build_train_projection([bundle])
        assert proj["rows"] == []
        assert proj["excluded_profile"] == 1

    def test_valid_top_only_accepted(self) -> None:
        bundle = _bundle(bid="b1", label="positive", profile=_ABSENT, top_profile="train_rich")
        proj = build_train_projection([bundle])
        assert proj["excluded_profile"] == 0
        assert proj["rows"][0]["redaction_profile"] == "train_rich"

    def test_no_invented_profile(self) -> None:
        assert project_train_row(_bundle(bid="b1", label="positive", profile=_ABSENT)) is None

    @pytest.mark.parametrize("token", ["", "   "])
    def test_empty_or_whitespace_profile_is_missing(self, token: str) -> None:
        proj = build_train_projection([_bundle(bid="b1", label="positive", profile=token)])
        assert proj["excluded_profile"] == 1
        assert proj["rows"] == []

    @pytest.mark.parametrize("token", ["not_a_profile", "raw_dev_unsafe"])
    def test_invalid_token_rejected(self, token: str) -> None:
        proj = build_train_projection([_bundle(bid="b1", label="positive", profile=token)])
        assert proj["excluded_profile"] == 1
        assert proj["rows"] == []

    def test_meta_only_accepted(self) -> None:
        proj = build_train_projection([_bundle(bid="b1", label="positive")])
        assert proj["excluded_profile"] == 0
        assert proj["rows"][0]["redaction_profile"] == "train_rich"

    def test_equal_top_meta_accepted(self) -> None:
        bundle = _bundle(bid="b1", label="positive", profile="train_rich", top_profile="train_rich")
        proj = build_train_projection([bundle])
        assert proj["excluded_profile"] == 0
        assert len(proj["rows"]) == 1

    def test_counters_disjoint(self) -> None:
        proj = build_train_projection(
            [
                _bundle(bid="p1", label="positive"),
                _bundle(bid="u1", label=None),
                _bundle(bid="x1", label="positive", profile=_ABSENT),
            ]
        )
        assert proj["excluded_unlabeled"] == 1
        assert proj["excluded_profile"] == 1
        assert len(proj["rows"]) == 1

    def test_unlabeled_rows_never_inspect_profiles(self) -> None:
        proj = build_train_projection([_bundle(bid="u1", label=None, profile="raw_dev_unsafe")])
        assert proj["excluded_unlabeled"] == 1
        assert proj["excluded_profile"] == 0

    def test_valid_projection_has_zero_excluded_profile(self) -> None:
        proj = build_train_projection(
            [
                _bundle(bid="p1", label="positive"),
                _bundle(bid="n1", label="negative", regime="antipattern"),
            ]
        )
        assert proj["excluded_profile"] == 0
        assert proj["excluded_unlabeled"] == 0

    def test_rows_never_carry_final_message_b64(self) -> None:
        bundle = _bundle(bid="b1", label="positive")
        bundle["final_message_b64"] = "b64-bytes-must-not-survive"
        row = project_train_row(bundle)
        assert row is not None
        assert "final_message_b64" not in row


class TestExportProfileVocabulary:
    def test_valid_vocabulary_is_enum_minus_raw_dev_unsafe(self) -> None:
        from git_cg.eval.mirror.redaction import _export_profile_or_none

        expected = {p.value for p in RedactionProfile} - {"raw_dev_unsafe"}
        accepted = {
            token for token in (p.value for p in RedactionProfile) if _export_profile_or_none(token) is not None
        }
        assert accepted == expected
        assert _export_profile_or_none("raw_dev_unsafe") is None


class TestExactLabelPrecedence:
    """Label precedence: bundle.train_label → meta.train_label → meta.label → bundle.label.

    Presence (value is not None) governs — an earlier source that is present
    but empty/falsey wins (fail-closed: no silent fallback).
    """

    def test_earlier_empty_top_label_blocks_fallback(self) -> None:
        bundle = _bundle(bid="b1", label=None)
        bundle["train_label"] = ""
        bundle["meta"]["label"] = "positive"
        proj = build_train_projection([bundle])
        assert proj["excluded_unlabeled"] == 1
        assert proj["rows"] == []

    def test_bundle_train_label_highest_precedence(self) -> None:
        bundle = _bundle(bid="b1", label=None)
        bundle["train_label"] = "positive"
        bundle["meta"]["train_label"] = "negative"
        proj = build_train_projection([bundle])
        assert proj["rows"][0]["label"] == "positive"

    def test_meta_train_label_precedes_meta_label(self) -> None:
        bundle = _bundle(bid="b1", label=None)
        bundle["meta"]["train_label"] = "negative"
        bundle["meta"]["label"] = "positive"
        proj = build_train_projection([bundle])
        assert proj["rows"][0]["label"] == "negative"

    def test_meta_label_precedes_bundle_label(self) -> None:
        bundle = _bundle(bid="b1", label=None)
        bundle["meta"]["label"] = "negative"
        bundle["label"] = "positive"
        proj = build_train_projection([bundle])
        assert proj["rows"][0]["label"] == "negative"

    def test_bundle_label_used_when_earlier_sources_absent(self) -> None:
        bundle = _bundle(bid="b1", label=None)
        bundle["label"] = "positive"
        proj = build_train_projection([bundle])
        assert proj["rows"][0]["label"] == "positive"
