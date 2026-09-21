import pytest

from rc_single_span.analysis.grillage import build_final_composite_grillage
from rc_single_span.analysis.plan_loads import build_plan_load_case
from rc_single_span.codes.eurocode.lm1 import (
    lm1_characteristic_lane_load,
    notional_lane_layout,
)
from rc_single_span.core.models import (
    BridgeProject,
    MaterialProperties,
    RectangularGirderProfile,
    SingleSpanBridgeGeometry,
)
from rc_single_span.traffic.lm1 import (
    LM1LanePlacement,
    LM1RemainingAreaPlacement,
    LM1SearchPlacement,
    build_lm1_plan_loads,
    run_lm1_grillage_search,
)


def _project(*, carriageway_width_m: float = 7.0) -> BridgeProject:
    return BridgeProject(
        name="LM1 common-grillage benchmark",
        geometry=SingleSpanBridgeGeometry(
            span_m=15.0,
            physical_girder_length_m=14.95,
            deck_width_m=11.0,
            carriageway_width_m=carriageway_width_m,
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


def test_reference_7m_lm1_lane_layout_and_characteristic_values() -> None:
    layout = notional_lane_layout(7.0)
    assert layout.lane_count == 2
    assert layout.lane_width_m == pytest.approx(3.0)
    assert layout.remaining_width_m == pytest.approx(1.0)
    assert lm1_characteristic_lane_load(1).axle_load_kn == pytest.approx(300.0)
    assert lm1_characteristic_lane_load(1).udl_kn_m2 == pytest.approx(9.0)
    assert lm1_characteristic_lane_load(2).axle_load_kn == pytest.approx(200.0)


def test_reference_snapshot_preserves_lm1_force_totals() -> None:
    project = _project()
    placement = LM1SearchPlacement(
        1,
        lanes=(
            LM1LanePlacement(1, -3.5, -0.5, 5.0),
            LM1LanePlacement(2, -0.5, 2.5, 5.0),
        ),
        remaining=(LM1RemainingAreaPlacement(2.5, 3.5),),
    )
    points, areas = build_lm1_plan_loads(project, placement)
    assert len(points) == 8
    assert sum(item.magnitude_kn for item in points) == pytest.approx(1000.0)
    area_force = sum(
        item.pressure_kn_m2
        * (item.x_end_m - item.x_start_m)
        * (item.y_end_m - item.y_start_m)
        for item in areas
    )
    assert area_force == pytest.approx(555.0)

    x_lines = (0.0, 5.0, 6.2, 15.0)
    y_lines = (-3.5, -3.0, -1.0, -0.5, 0.0, 2.0, 2.5, 3.5)
    build = build_final_composite_grillage(
        project,
        stations_m=x_lines,
        additional_y_lines_m=y_lines,
    )
    case = build_plan_load_case(
        build.model,
        load_case_id=1,
        name="LM1 reference snapshot",
        point_loads=points,
        area_loads=areas,
    )
    applied = -sum(item.fz_kn for item in case.nodal_loads) - sum(
        item.magnitude_kn for item in case.point_loads
    )
    assert applied == pytest.approx(1555.0)


def test_one_lane_lm1_search_runs_on_common_grillage_and_envelopes_all_girders() -> None:
    project = _project(carriageway_width_m=3.0)
    result = run_lm1_grillage_search(
        project,
        longitudinal_step_m=7.5,
        max_exhaustive_tandem_combinations=100,
    )
    assert result.tandem_combinations_exhaustive
    assert result.evaluated_case_count > 0
    assert len(result.girders) == 7
    assert result.cases
    assert all(item.moment_knm.value > 0.0 for item in result.girders)
    assert all(item.shear_kn.value > 0.0 for item in result.girders)
    for case in result.cases:
        assert case.analysis.vertical_equilibrium_residual_kn == pytest.approx(
            0.0,
            abs=1.0e-6,
        )
