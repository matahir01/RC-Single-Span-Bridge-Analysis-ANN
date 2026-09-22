import pytest

from rc_single_span.analysis.construction import run_construction_stage_analysis
from rc_single_span.analysis.permanent import automatic_permanent_point_loads
from rc_single_span.analysis.simple_span import (
    PointLoadSegment,
    simple_span_mixed_load_response,
)
from rc_single_span.core.models import (
    BridgeProject,
    DeckConstruction,
    MaterialProperties,
    PermanentActionModel,
    PermanentActionStage,
    PermanentTransverseLineAction,
    RectangularGirderProfile,
    SingleSpanBridgeGeometry,
)


def _project() -> BridgeProject:
    return BridgeProject(
        name="Permanent point-action benchmark",
        geometry=SingleSpanBridgeGeometry(
            span_m=20.0,
            deck_width_m=11.0,
            carriageway_width_m=7.0,
            girder_count=7,
            girder_spacing_m=1.70,
            girder_profile=RectangularGirderProfile(width_m=0.40, depth_m=0.95),
            deck=DeckConstruction(
                precast_false_slab_depth_m=0.075,
                in_situ_slab_depth_m=0.175,
                false_slab_composite_participation=False,
                in_situ_slab_composite_participation=True,
            ),
        ),
        materials=MaterialProperties(
            fck_mpa=35.0,
            fcu_mpa=45.0,
            fyk_mpa=500.0,
            concrete_density_kn_m3=25.0,
            elastic_modulus_mpa=34000.0,
        ),
        permanent_actions=PermanentActionModel(
            transverse_line_actions=[
                PermanentTransverseLineAction(
                    name="midspan diaphragm",
                    magnitude_kn_m=5.625,
                    x_m=10.0,
                    y_start_m=-5.10,
                    y_end_m=5.10,
                    stage=PermanentActionStage.DECK_CONSTRUCTION,
                )
            ]
        ),
    )


def test_simple_span_point_load_recovers_closed_form_reactions_and_moment() -> None:
    span = 20.0
    load = 100.0
    result = simple_span_mixed_load_response(
        span,
        (),
        (PointLoadSegment(load, span / 2.0),),
    )
    assert result.reaction_left_kn == pytest.approx(load / 2.0)
    assert result.reaction_right_kn == pytest.approx(load / 2.0)
    assert result.max_moment_knm == pytest.approx(load * span / 4.0)
    assert result.max_moment_position_m == pytest.approx(span / 2.0)
    assert result.max_abs_shear_kn == pytest.approx(load / 2.0)


def test_transverse_diaphragm_is_distributed_to_longitudinal_girders_without_loss() -> None:
    project = _project()
    points = automatic_permanent_point_loads(project)
    expected_total = 5.625 * 10.20

    assert len(points) == 7
    assert sum(point.magnitude_kn for point in points) == pytest.approx(expected_total)
    assert {point.x_m for point in points} == {10.0}
    assert all(
        point.stage is PermanentActionStage.DECK_CONSTRUCTION for point in points
    )


def test_construction_stage_response_includes_diaphragm_at_load_time_stiffness() -> None:
    project = _project()
    result = run_construction_stage_analysis(project)
    middle = [
        item
        for item in result.stages
        if item.girder_index == 4
        and item.stage is PermanentActionStage.DECK_CONSTRUCTION
    ][0]

    assert len(middle.point_loads) == 1
    assert middle.point_loads[0].source == "midspan diaphragm"
    assert middle.point_loads[0].magnitude_kn == pytest.approx(5.625 * 1.70)
    assert middle.response.max_moment_knm > 0.0
    assert middle.max_downward_deflection_mm > 0.0
