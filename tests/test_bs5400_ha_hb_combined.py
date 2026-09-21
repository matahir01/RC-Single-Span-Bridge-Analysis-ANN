from types import SimpleNamespace

import pytest

from rc_single_span.codes.bs5400.traffic import (
    ha_hb_coexistent_gamma_fl,
    ha_lane_load_bd37_01,
)
from rc_single_span.core.models import (
    BridgeProject,
    MaterialProperties,
    RectangularGirderProfile,
    SingleSpanBridgeGeometry,
)
from rc_single_span.traffic.bs5400 import (
    HBSearchPlacement,
    _equilibrium_tolerance_kn,
    _require_vertical_equilibrium,
)
from rc_single_span.traffic.bs5400_combined import (
    HAHBCombinedPlacement,
    HAHBHALanePlacement,
    HAHBLaneTreatment,
    build_ha_hb_combined_plan_loads,
    classify_ha_lanes_for_hb,
    run_ha_hb_combined_grillage_search,
)


def _project() -> BridgeProject:
    return BridgeProject(
        name="BD37 HA+HB coexistence benchmark",
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


def _hb(*, centre_y_m: float, lead_x_m: float = 2.0) -> HBSearchPlacement:
    return HBSearchPlacement(
        case_id=0,
        units=45.0,
        inner_axle_spacing_m=6.0,
        lead_x_m=lead_x_m,
        centre_y_m=centre_y_m,
    )


def test_coexistent_ha_uses_hb_gamma_fl_factors() -> None:
    assert ha_hb_coexistent_gamma_fl(combination=1, limit_state="uls") == pytest.approx(1.30)
    assert ha_hb_coexistent_gamma_fl(combination=1, limit_state="sls") == pytest.approx(1.10)
    assert ha_hb_coexistent_gamma_fl(combination=2, limit_state="uls") == pytest.approx(1.10)
    assert ha_hb_coexistent_gamma_fl(combination=3, limit_state="uls") == pytest.approx(1.10)
    assert ha_hb_coexistent_gamma_fl(combination=2, limit_state="sls") == pytest.approx(1.00)
    assert ha_hb_coexistent_gamma_fl(combination=3, limit_state="sls") == pytest.approx(1.00)


def test_hb_wholly_within_lane_displaces_that_lane_and_leaves_other_unoccupied() -> None:
    lanes = classify_ha_lanes_for_hb(_project(), _hb(centre_y_m=-1.75))
    assert [lane.treatment for lane in lanes] == [
        HAHBLaneTreatment.DISPLACED_CLEAR_ZONE,
        HAHBLaneTreatment.UNOCCUPIED,
    ]


def test_hb_straddling_two_lanes_with_less_than_2p5m_remaining_displaces_both() -> None:
    lanes = classify_ha_lanes_for_hb(_project(), _hb(centre_y_m=0.0))
    assert [lane.treatment for lane in lanes] == [
        HAHBLaneTreatment.DISPLACED_CLEAR_ZONE,
        HAHBLaneTreatment.DISPLACED_CLEAR_ZONE,
    ]


def test_partial_lane_with_at_least_2p5m_remaining_keeps_residual_udl_strip() -> None:
    lanes = classify_ha_lanes_for_hb(_project(), _hb(centre_y_m=-1.0))
    assert lanes[0].treatment is HAHBLaneTreatment.DISPLACED_CLEAR_ZONE
    assert lanes[1].treatment is HAHBLaneTreatment.RESIDUAL_2P5
    assert lanes[1].residual_y_start_m == pytest.approx(0.75)
    assert lanes[1].residual_y_end_m == pytest.approx(3.5)
    assert lanes[1].residual_width_m == pytest.approx(2.75)


def test_15m_displaced_lane_has_no_ha_inside_25m_clear_zone_and_no_kel() -> None:
    project = _project()
    geometry = classify_ha_lanes_for_hb(project, _hb(centre_y_m=0.0))
    placement = HAHBCombinedPlacement(
        case_id=1,
        hb=_hb(centre_y_m=0.0),
        ha_lanes=(
            HAHBHALanePlacement(geometry=geometry[0], factor_rank=1, kel_x_m=None),
            HAHBHALanePlacement(geometry=geometry[1], factor_rank=2, kel_x_m=None),
        ),
    )
    points, areas, lines = build_ha_hb_combined_plan_loads(project, placement)
    assert len(points) == 16
    assert areas == ()
    assert lines == ()


def test_residual_lane_uses_2p5m_factor_basis_and_omits_kel() -> None:
    project = _project()
    geometry = classify_ha_lanes_for_hb(project, _hb(centre_y_m=-1.0))
    residual = geometry[1]
    placement = HAHBCombinedPlacement(
        case_id=1,
        hb=_hb(centre_y_m=-1.0),
        ha_lanes=(
            HAHBHALanePlacement(
                geometry=residual,
                factor_rank=1,
                kel_x_m=None,
            ),
        ),
    )
    _, areas, lines = build_ha_hb_combined_plan_loads(project, placement)
    assert len(areas) == 1
    assert lines == ()

    expected = ha_lane_load_bd37_01(
        factor_rank=1,
        loaded_length_m=15.0,
        lane_width_m=2.5,
        total_notional_lanes=2,
    )
    resultant = (
        areas[0].pressure_kn_m2
        * (areas[0].x_end_m - areas[0].x_start_m)
        * (areas[0].y_end_m - areas[0].y_start_m)
    )
    assert resultant == pytest.approx(expected.udl_kn_m * 15.0)


def test_unoccupied_lane_retains_normal_ha_udl_and_kel() -> None:
    project = _project()
    geometry = classify_ha_lanes_for_hb(project, _hb(centre_y_m=-1.75))
    placement = HAHBCombinedPlacement(
        case_id=1,
        hb=_hb(centre_y_m=-1.75),
        ha_lanes=(
            HAHBHALanePlacement(
                geometry=geometry[1],
                factor_rank=1,
                kel_x_m=7.5,
            ),
        ),
    )
    _, areas, lines = build_ha_hb_combined_plan_loads(project, placement)
    assert len(areas) == 1
    assert len(lines) == 1
    assert lines[0].x_m == pytest.approx(7.5)


def test_combined_search_runs_on_common_grillage_and_preserves_equilibrium() -> None:
    result = run_ha_hb_combined_grillage_search(
        _project(),
        units=30.0,
        hb_longitudinal_step_m=15.0,
        hb_transverse_step_m=3.5,
        ha_kel_step_m=15.0,
        max_exhaustive_kel_combinations=100,
        max_exhaustive_ha_assignments=100,
    )
    assert result.evaluated_case_count > 0
    assert result.ha_assignment_search_exhaustive
    assert result.kel_combinations_exhaustive
    assert len(result.girders) == 7
    assert result.cases
    assert result.checked_inner_axle_spacings_m == pytest.approx(
        (6.0, 11.0, 16.0, 21.0, 26.0)
    )
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


def test_equilibrium_guard_allows_only_machine_scale_sparse_roundoff() -> None:
    analysis = SimpleNamespace(
        total_applied_vertical_load_kn=-1352.61162,
        total_vertical_reaction_kn=1352.611602,
        vertical_equilibrium_residual_kn=-1.8e-5,
    )
    tolerance = _equilibrium_tolerance_kn(analysis)
    assert tolerance == pytest.approx(6.7630581e-5)
    assert abs(analysis.vertical_equilibrium_residual_kn) < tolerance
    _require_vertical_equilibrium(analysis, traffic_model="regression")

    failed = SimpleNamespace(
        total_applied_vertical_load_kn=-1352.61162,
        total_vertical_reaction_kn=1352.61062,
        vertical_equilibrium_residual_kn=-1.0e-3,
    )
    with pytest.raises(RuntimeError, match="failed vertical equilibrium"):
        _require_vertical_equilibrium(failed, traffic_model="regression")
