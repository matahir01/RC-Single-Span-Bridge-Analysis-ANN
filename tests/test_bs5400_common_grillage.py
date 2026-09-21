import pytest

from rc_single_span.codes.bs5400.traffic import (
    ha_lane_load_bd37_01,
    ha_udl_kn_m,
    hb_vehicle_definition,
    notional_lane_layout_bd37_01,
)
from rc_single_span.core.models import (
    BridgeProject,
    MaterialProperties,
    RectangularGirderProfile,
    SingleSpanBridgeGeometry,
)
from rc_single_span.traffic.bs5400 import (
    HALanePlacement,
    HASearchPlacement,
    HBSearchPlacement,
    build_ha_plan_loads,
    build_hb_plan_loads,
    run_ha_grillage_search,
    run_hb_grillage_search,
)


def _project() -> BridgeProject:
    return BridgeProject(
        name="BS common-grillage benchmark",
        geometry=SingleSpanBridgeGeometry(
            span_m=15.0,
            physical_girder_length_m=14.95,
            deck_width_m=11.0,
            carriageway_width_m=7.0,
            girder_count=7,
            girder_spacing_m=1.70,
            girder_profile=RectangularGirderProfile(width_m=0.40, depth_m=0.95),
        ),
        materials=MaterialProperties(
            fck_mpa=25.0,
            fcu_mpa=30.0,
            fyk_mpa=410.0,
            concrete_density_kn_m3=24.0,
            elastic_modulus_mpa=30000.0,
        ),
    )


def test_reference_bd37_ha_values_are_preserved() -> None:
    layout = notional_lane_layout_bd37_01(7.0)
    assert layout.lane_count == 2
    assert layout.lane_width_m == pytest.approx(3.5)
    assert ha_udl_kn_m(15.0) == pytest.approx(54.7467236679)

    lane = ha_lane_load_bd37_01(
        factor_rank=1,
        loaded_length_m=15.0,
        lane_width_m=layout.lane_width_m,
        total_notional_lanes=layout.lane_count,
    )
    assert lane.lane_factor == pytest.approx(0.959)
    assert lane.udl_kn_m == pytest.approx(52.5021079976)
    assert lane.kel_kn == pytest.approx(115.08)


def test_ha_plan_load_preserves_lane_udl_and_kel_resultant() -> None:
    project = _project()
    placement = HASearchPlacement(
        1,
        lanes=(
            HALanePlacement(1, 1, -3.5, 0.0, 7.5),
        ),
    )
    areas, lines = build_ha_plan_loads(project, placement)
    assert len(areas) == 1
    assert len(lines) == 1
    area_force = (
        areas[0].pressure_kn_m2
        * (areas[0].x_end_m - areas[0].x_start_m)
        * (areas[0].y_end_m - areas[0].y_start_m)
    )
    expected = ha_lane_load_bd37_01(
        factor_rank=1,
        loaded_length_m=15.0,
        lane_width_m=3.5,
        total_notional_lanes=2,
    )
    assert area_force == pytest.approx(expected.udl_kn_m * 15.0)
    assert lines[0].total_load_kn == pytest.approx(expected.kel_kn)


def test_45_unit_hb_has_sixteen_wheels_and_standard_transverse_offsets() -> None:
    vehicle = hb_vehicle_definition(units=45.0, inner_axle_spacing_m=6.0)
    assert vehicle.wheel_load_kn == pytest.approx(112.5)
    assert vehicle.axle_load_kn == pytest.approx(450.0)
    assert vehicle.total_vehicle_load_kn == pytest.approx(1800.0)
    assert vehicle.overall_width_m == pytest.approx(3.5)
    assert vehicle.axle_offsets_m == pytest.approx((0.0, 1.8, 7.8, 9.6))
    assert vehicle.wheel_y_offsets_m == pytest.approx((-1.5, -0.5, 0.5, 1.5))

    points = build_hb_plan_loads(
        _project(),
        HBSearchPlacement(
            1,
            units=45.0,
            inner_axle_spacing_m=6.0,
            lead_x_m=2.0,
            centre_y_m=0.0,
        ),
    )
    assert len(points) == 16
    assert sum(point.magnitude_kn for point in points) == pytest.approx(1800.0)


def test_ha_search_uses_common_grillage_and_envelopes_all_girders() -> None:
    result = run_ha_grillage_search(
        _project(),
        longitudinal_step_m=7.5,
        max_exhaustive_kel_combinations=100,
    )
    assert result.evaluated_case_count > 0
    assert result.kel_combinations_exhaustive
    assert len(result.girders) == 7
    assert result.cases
    for case in result.cases:
        scale = max(
            abs(case.analysis.total_applied_vertical_load_kn),
            abs(case.analysis.total_vertical_reaction_kn),
            1.0,
        )
        assert abs(case.analysis.vertical_equilibrium_residual_kn) <= max(
            1.0e-6,
            1.0e-8 * scale,
        )


def test_hb_search_checks_all_five_vehicle_lengths_and_transverse_positions() -> None:
    result = run_hb_grillage_search(
        _project(),
        units=45.0,
        longitudinal_step_m=15.0,
        transverse_step_m=3.5,
    )
    assert result.checked_inner_axle_spacings_m == pytest.approx(
        (6.0, 11.0, 16.0, 21.0, 26.0)
    )
    assert result.evaluated_case_count > 0
    assert len(result.girders) == 7
    assert result.cases
    assert all(item.moment_knm.value > 0.0 for item in result.girders)
    for case in result.cases:
        scale = max(
            abs(case.analysis.total_applied_vertical_load_kn),
            abs(case.analysis.total_vertical_reaction_kn),
            1.0,
        )
        assert abs(case.analysis.vertical_equilibrium_residual_kn) <= max(
            1.0e-6,
            1.0e-8 * scale,
        )
