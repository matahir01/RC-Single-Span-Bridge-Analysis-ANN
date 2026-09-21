import pytest

from rc_single_span.analysis.construction import run_construction_stage_analysis
from rc_single_span.analysis.grillage import build_final_composite_grillage
from rc_single_span.analysis.grillage_solver import solve_vertical_grillage
from rc_single_span.analysis.permanent import automatic_permanent_loads
from rc_single_span.analysis.sections import (
    final_composite_girder_properties,
    girder_tributary_widths_m,
    precast_girder_properties,
)
from rc_single_span.analysis.structural_model import LoadCase, UniformLoad
from rc_single_span.core.models import (
    BridgeProject,
    DeckConstruction,
    MaterialProperties,
    PermanentActionStage,
    RectangularGirderProfile,
    SingleSpanBridgeGeometry,
)


def _project() -> BridgeProject:
    return BridgeProject(
        name="15 m construction benchmark",
        geometry=SingleSpanBridgeGeometry(
            span_m=15.0,
            physical_girder_length_m=14.95,
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
            fck_mpa=25.0,
            fcu_mpa=30.0,
            fyk_mpa=410.0,
            concrete_density_kn_m3=24.0,
            elastic_modulus_mpa=30000.0,
        ),
    )


def test_tributary_widths_cover_the_physical_deck_exactly() -> None:
    widths = girder_tributary_widths_m(_project().geometry)
    assert widths == pytest.approx((1.25, 1.70, 1.70, 1.70, 1.70, 1.70, 1.25))
    assert sum(widths) == pytest.approx(11.0)


def test_final_composite_stiffness_exceeds_precast_stiffness() -> None:
    project = _project()
    precast = precast_girder_properties(project.geometry)
    composite = final_composite_girder_properties(project.geometry, girder_index=4)
    assert composite.area_m2 > precast.area_m2
    assert composite.iy_m4 > precast.iy_m4


def test_automatic_permanent_actions_are_staged_without_double_counting() -> None:
    project = _project()
    loads = automatic_permanent_loads(project)
    middle = [item for item in loads if item.girder_index == 4]

    girder = next(item for item in middle if item.source == "precast girder self-weight")
    false_slab = next(
        item for item in middle if item.source == "precast false-slab self-weight"
    )
    wet = next(item for item in middle if item.source == "wet in-situ deck self-weight")

    assert girder.stage is PermanentActionStage.PRECAST_GIRDER
    assert false_slab.stage is PermanentActionStage.PRECAST_GIRDER
    assert wet.stage is PermanentActionStage.DECK_CONSTRUCTION
    assert girder.magnitude_kn_m == pytest.approx(0.40 * 0.95 * 24.0)
    assert false_slab.magnitude_kn_m == pytest.approx(1.70 * 0.075 * 24.0)
    assert wet.magnitude_kn_m == pytest.approx(1.70 * 0.175 * 24.0)


def test_construction_analysis_uses_load_time_stiffness() -> None:
    project = _project()
    result = run_construction_stage_analysis(project)
    middle = [item for item in result.stages if item.girder_index == 4]
    precast = next(
        item for item in middle if item.stage is PermanentActionStage.PRECAST_GIRDER
    )
    deck = next(
        item for item in middle if item.stage is PermanentActionStage.DECK_CONSTRUCTION
    )
    final = next(
        item for item in middle if item.stage is PermanentActionStage.SUPERIMPOSED
    )
    assert precast.section.iy_m4 == pytest.approx(deck.section.iy_m4)
    assert final.section.iy_m4 > deck.section.iy_m4
    assert precast.max_downward_deflection_mm > 0.0
    assert deck.max_downward_deflection_mm > 0.0

    cumulative = result.cumulative_by_girder[3]
    combined_load = sum(
        load.magnitude_kn_m
        for item in middle
        for load in item.loads
    )
    final_ei = (
        project.materials.elastic_modulus_mpa * 1000.0 * final.section.iy_m4
    )
    wrong_all_final_mm = (
        5.0
        * combined_load
        * project.geometry.span_m**4
        / (384.0 * final_ei)
        * 1000.0
    )
    assert cumulative.max_downward_deflection_mm > wrong_all_final_mm


def test_final_grillage_preserves_equilibrium_under_symmetric_udl() -> None:
    project = _project()
    empty = build_final_composite_grillage(project, longitudinal_divisions=6)
    longitudinal_members = [
        beam
        for beam in empty.model.beams
        if abs(
            next(n for n in empty.model.nodes if n.node_id == beam.node_i).y_m
            - next(n for n in empty.model.nodes if n.node_id == beam.node_j).y_m
        ) < 1.0e-12
    ]
    case = LoadCase(
        1,
        "symmetric UDL",
        uniform_loads=tuple(
            UniformLoad(member.member_id, -5.0)
            for member in longitudinal_members
        ),
    )
    loaded = build_final_composite_grillage(
        project,
        longitudinal_divisions=6,
        load_case=case,
    )
    result = solve_vertical_grillage(loaded.model)
    expected = -5.0 * project.geometry.span_m * project.geometry.girder_count
    assert result.total_applied_vertical_load_kn == pytest.approx(expected)
    assert result.total_vertical_reaction_kn == pytest.approx(-expected)
    assert result.vertical_equilibrium_residual_kn == pytest.approx(0.0, abs=1.0e-7)
