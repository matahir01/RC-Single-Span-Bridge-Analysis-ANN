import pytest

from rc_single_span.design.fatigue import check_reinforcement_fatigue_stress_range


def test_fatigue_stress_range_check_uses_explicit_partial_factors() -> None:
    result = check_reinforcement_fatigue_stress_range(
        equivalent_stress_range_mpa=80.0,
        characteristic_resistance_range_mpa=150.0,
        gamma_fatigue_action=1.0,
        gamma_fatigue_resistance=1.15,
        resistance_modifier=1.0,
        provenance="unit-test explicit fatigue stress-range inputs",
    )

    assert result.design_action_stress_range_mpa == pytest.approx(80.0)
    assert result.design_resistance_range_mpa == pytest.approx(150.0 / 1.15)
    assert result.utilization == pytest.approx(80.0 / (150.0 / 1.15))
    assert result.passes
    assert result.margin_mpa > 0.0


def test_fatigue_stress_range_failure_is_reported_not_clipped() -> None:
    result = check_reinforcement_fatigue_stress_range(
        equivalent_stress_range_mpa=160.0,
        characteristic_resistance_range_mpa=150.0,
        provenance="unit-test fatigue overload",
    )

    assert not result.passes
    assert result.utilization > 1.0
    assert result.margin_mpa < 0.0


def test_fatigue_check_requires_provenance() -> None:
    with pytest.raises(ValueError, match="provenance"):
        check_reinforcement_fatigue_stress_range(
            equivalent_stress_range_mpa=80.0,
            characteristic_resistance_range_mpa=150.0,
            provenance="",
        )
