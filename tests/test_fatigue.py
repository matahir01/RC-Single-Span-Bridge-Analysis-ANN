import pytest

from rc_single_span.design.fatigue import (
    check_reinforcement_fatigue_stress_range,
    equivalent_reinforcement_stress_range_from_flm3,
)


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


def test_bs_en_fatigue_matches_jrc_concrete_bridge_worked_example() -> None:
    """JRC Bridge Design to Eurocodes, concrete bridge fatigue example.

    The worked example reports Delta_sigma_s(FLM3)=63 MPa, a 1.4 span
    multiplier, lambda_s=0.89 (1.16 near expansion joints), straight-bar
    Delta_sigma_Rsk=162.5 MPa, gamma_F,fat=1.0 and gamma_s,fat=1.15. It rounds
    the equivalent ranges to 78 and 102 MPa and the design resistance to
    141 MPa.
    """

    ordinary = equivalent_reinforcement_stress_range_from_flm3(
        flm3_stress_range_mpa=63.0,
        fatigue_load_multiplier=1.4,
        damage_coefficient=0.89,
        provenance="JRC Bridge Design to Eurocodes, Chapter 5 fatigue example",
    )
    near_joint = equivalent_reinforcement_stress_range_from_flm3(
        flm3_stress_range_mpa=63.0,
        fatigue_load_multiplier=1.4,
        damage_coefficient=1.16,
        provenance="JRC Bridge Design to Eurocodes, Chapter 5 fatigue example",
    )

    assert ordinary.amplified_stress_range_mpa == pytest.approx(88.2)
    assert ordinary.equivalent_stress_range_mpa == pytest.approx(78.0, abs=0.6)
    assert near_joint.equivalent_stress_range_mpa == pytest.approx(102.0, abs=0.6)

    result = check_reinforcement_fatigue_stress_range(
        equivalent_stress_range_mpa=near_joint.equivalent_stress_range_mpa,
        characteristic_resistance_range_mpa=162.5,
        gamma_fatigue_action=1.0,
        gamma_fatigue_resistance=1.15,
        provenance="JRC BS EN 1992-2 Annex NN worked fatigue check",
    )
    assert result.design_resistance_range_mpa == pytest.approx(141.0, abs=0.4)
    assert result.design_action_stress_range_mpa == pytest.approx(102.0, abs=0.6)
    assert result.passes


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

    with pytest.raises(ValueError, match="provenance"):
        equivalent_reinforcement_stress_range_from_flm3(
            flm3_stress_range_mpa=63.0,
            fatigue_load_multiplier=1.4,
            damage_coefficient=0.89,
            provenance="",
        )
