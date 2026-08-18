"""S4-F train dual-axis projections (Q18 / D18 / D28 / P2-4)."""

from __future__ import annotations

import pytest

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


def _bundle(
    *,
    bid: str,
    label: str | None,
    split: str = "train",
    regime: str | None = None,
    profile: str = "train_rich",
) -> dict:
    """
    Construct a training bundle fixture with optional label and regime metadata.
    
    Parameters:
        bid (str): Bundle identifier.
        label (str | None): Optional training label.
        split (str): Dataset split.
        regime (str | None): Optional regime metadata value.
        profile (str): Redaction profile.
    
    Returns:
        dict: A training bundle containing artifact, gate, score, metadata, and split fields.
    """
    meta: dict = {"redaction_profile": profile, "split_group_id": f"sg-{bid}"}
    if label is not None:
        meta["train_label"] = label
    if regime is not None:
        meta["regime"] = regime
    return {
        "id": bid,
        "artifact_class": "final_accept",
        "gate": {"deterministic_pass": True},
        "score_card": {"format_compliance": 1.0},
        "meta": meta,
        "split": split,
    }


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
            {"bundle_id": "p", "label": "positive", "regime": "A"},
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
