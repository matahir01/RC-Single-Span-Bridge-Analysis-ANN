import pytest

from rc_single_span.research.targets import (
    ConsequenceClass,
    bs_en_1990_target_reliability,
    thesis_reference_targets,
)


def test_bs_en_1990_50_year_targets_match_source_table() -> None:
    assert bs_en_1990_target_reliability("CC1", 50).beta == pytest.approx(3.3)
    assert bs_en_1990_target_reliability("CC2", 50).beta == pytest.approx(3.8)
    assert bs_en_1990_target_reliability("CC3", 50).beta == pytest.approx(4.3)


def test_bs_en_1990_one_year_targets_match_source_table() -> None:
    assert bs_en_1990_target_reliability("CC1", 1).beta == pytest.approx(4.2)
    assert bs_en_1990_target_reliability("CC2", 1).beta == pytest.approx(4.7)
    assert bs_en_1990_target_reliability("CC3", 1).beta == pytest.approx(5.2)


def test_target_helper_does_not_invent_other_reference_periods() -> None:
    with pytest.raises(ValueError, match="1-year and 50-year"):
        bs_en_1990_target_reliability(ConsequenceClass.CC2, 100)


def test_thesis_reference_targets_cover_all_consequence_classes() -> None:
    targets = thesis_reference_targets()
    assert tuple(item.consequence_class for item in targets) == tuple(ConsequenceClass)
    assert tuple(item.beta for item in targets) == pytest.approx((3.3, 3.8, 4.3))
