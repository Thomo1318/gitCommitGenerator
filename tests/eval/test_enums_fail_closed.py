"""S0-C: isolation, dual-axis docs markers, fail-closed enums."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from git_cg.eval.enums import ArtifactClass, Authority, Polarity, RedactionProfile, Source
from git_cg.eval.score_result import ScoreResultV1


def test_s0_c01_eval_package_imports_without_opik() -> None:
    import git_cg.eval as ev
    import git_cg.eval.catalog as catalog
    import git_cg.eval.enums as enums
    import git_cg.eval.pins as pins
    import git_cg.eval.schema_pack as schema_pack
    import git_cg.eval.score_result as score_result

    assert hasattr(ev, "schema_pack_pin")
    assert hasattr(ev, "metric_catalog_pin")
    assert hasattr(ev, "ScoreResultV1")

    for mod in (catalog, pins, schema_pack, score_result, enums, ev):
        assert mod.__file__ is not None
        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert "import opik" not in src
        assert "from opik" not in src


def test_s0_c02_unknown_enum_values_fail() -> None:
    with pytest.raises(ValueError):
        ArtifactClass("not_a_real_class")
    with pytest.raises(ValueError):
        Polarity("sometimes_better")
    with pytest.raises(ValueError):
        RedactionProfile("dump_everything")


def test_s0_c03_docs_state_dual_axis() -> None:
    readme = Path("docs/eval/README.md").read_text(encoding="utf-8")
    assert "Train axis ≠ gate axis" in readme
    assert "0.9.2-body-ingest" in readme
    assert "train_rich" in readme
    assert "gate" in readme.lower()


def test_s0_c04_bool_value_requires_pass_fail_polarity() -> None:
    with pytest.raises(ValidationError):
        ScoreResultV1(
            metric_id="c.evidence_surface_precision",
            polarity=Polarity.HIGHER_IS_BETTER,
            authority=Authority.LAW,
            source=Source.LOCAL_WRAPPER,
            value=True,
        )


def test_s0_c05_train_rich_is_not_law_authority_by_itself() -> None:
    assert RedactionProfile.TRAIN_RICH.value == "train_rich"
    assert "law" not in {p.value for p in RedactionProfile}


def test_s0_c06_json_schema_enforces_pass_fail_bool() -> None:
    from git_cg.eval.schema_pack import SchemaPackError, validate_instance

    with pytest.raises(SchemaPackError):
        validate_instance(
            "score_result_v1",
            {
                "metric_id": "a.final_message_present",
                "polarity": "pass_fail",
                "authority": "law",
                "source": "local_wrapper",
                "value": 1,
            },
        )
