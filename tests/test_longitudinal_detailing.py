import pytest

from rc_single_span.design.longitudinal_detailing import (
    LongitudinalDemandStation,
    build_symmetric_curtailment_plan,
    ec2_design_anchorage_length,
    select_face_reinforcement,
)


def test_ec2_anchorage_recovers_direct_tension_bar_expression() -> None:
    result = ec2_design_anchorage_length(
        bar_diameter_mm=32.0,
        steel_stress_mpa=435.0,
        fctk_005_mpa=2.2,
        gamma_c=1.50,
        alpha_ct=1.0,
        eta1=1.0,
        eta2=1.0,
    )

    fctd = 2.2 / 1.50
    fbd = 2.25 * fctd
    basic = 32.0 / 4.0 * 435.0 / fbd
    minimum = max(0.30 * basic, 320.0, 100.0)

    assert result.fctd_mpa == pytest.approx(fctd)
    assert result.design_bond_strength_mpa == pytest.approx(fbd)
    assert result.basic_required_anchorage_length_mm == pytest.approx(basic)
    assert result.design_anchorage_length_mm == pytest.approx(max(basic, minimum))
    assert result.passes_available_length is None


def test_bs_en_anchorage_matches_concrete_centre_h16_worked_example() -> None:
    """Concrete Centre Lecture 9 example: C25/30, H16, good bond, 25 mm cover.

    The published straight-bar result is about 592 mm. The source calculates
    fctk,0.05 = 1.795 MPa, sigma_sd = 500/1.15 = 435 MPa and alpha2 = 0.916
    (rounded). We use the unrounded alpha2 expression and compare to the source
    at its stated engineering precision.
    """

    alpha2 = 1.0 - 0.15 * (25.0 - 16.0) / 16.0
    result = ec2_design_anchorage_length(
        bar_diameter_mm=16.0,
        steel_stress_mpa=500.0 / 1.15,
        fctk_005_mpa=1.795,
        gamma_c=1.50,
        alpha_ct=1.0,
        eta1=1.0,
        eta2=1.0,
        alpha1=1.0,
        alpha2=alpha2,
        alpha3=1.0,
        alpha4=1.0,
        alpha5=1.0,
    )

    assert result.design_bond_strength_mpa == pytest.approx(2.693, abs=0.001)
    assert result.basic_required_anchorage_length_mm / 16.0 == pytest.approx(
        40.36,
        abs=0.02,
    )
    assert result.design_anchorage_length_mm == pytest.approx(592.0, abs=1.0)


def test_ec2_anchorage_checks_available_length_without_hiding_failure() -> None:
    result = ec2_design_anchorage_length(
        bar_diameter_mm=25.0,
        steel_stress_mpa=400.0,
        fctk_005_mpa=2.0,
        available_length_mm=500.0,
    )

    assert result.design_anchorage_length_mm > 500.0
    assert result.passes_available_length is False


def test_face_reinforcement_meets_area_and_spacing_constraints() -> None:
    result = select_face_reinforcement(
        required_area_mm2=900.0,
        face_length_mm=1000.0,
        available_diameters_mm=(12.0, 16.0),
        maximum_spacing_mm=250.0,
    )

    assert result.provided_area_mm2 >= 900.0
    assert result.passes_area
    assert result.passes_spacing
    assert result.centre_spacing_mm is not None
    assert result.centre_spacing_mm <= 250.0


def test_curtailment_plan_uses_station_demand_and_adds_anchorage_extension() -> None:
    stations = (
        LongitudinalDemandStation(0.0, 1600.0),
        LongitudinalDemandStation(4.0, 4200.0),
        LongitudinalDemandStation(8.0, 9000.0),
        LongitudinalDemandStation(10.0, 12000.0),
        LongitudinalDemandStation(12.0, 9000.0),
        LongitudinalDemandStation(16.0, 4200.0),
        LongitudinalDemandStation(20.0, 1600.0),
    )
    plan = build_symmetric_curtailment_plan(
        span_m=20.0,
        stations=stations,
        bar_diameter_mm=32.0,
        total_bars=16,
        anchorage_length_mm=1200.0,
    )

    assert plan.total_bars == 16
    assert len(plan.zones) == 6
    assert max(zone.bars_to_continue for zone in plan.zones) == 15
    left_zone = plan.zones[0]
    assert left_zone.theoretical_cutoff_m == pytest.approx(2.0)
    assert left_zone.anchored_cutoff_m == pytest.approx(0.8)
    right_zone = plan.zones[-1]
    assert right_zone.theoretical_cutoff_m == pytest.approx(18.0)
    assert right_zone.anchored_cutoff_m == pytest.approx(19.2)


def test_curtailment_rejects_demand_exceeding_full_cage() -> None:
    with pytest.raises(ValueError, match="cannot satisfy"):
        build_symmetric_curtailment_plan(
            span_m=20.0,
            stations=(
                LongitudinalDemandStation(0.0, 1000.0),
                LongitudinalDemandStation(10.0, 20000.0),
                LongitudinalDemandStation(20.0, 1000.0),
            ),
            bar_diameter_mm=25.0,
            total_bars=20,
            anchorage_length_mm=1000.0,
        )
