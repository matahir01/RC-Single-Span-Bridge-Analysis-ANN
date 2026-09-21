import pytest

from rc_single_span.analysis.permanent import automatic_permanent_loads
from rc_single_span.core.models import (
    BridgeProject,
    DeckConstruction,
    MaterialProperties,
    PermanentActionModel,
    PermanentActionStage,
    PermanentLineAction,
    RectangularGirderProfile,
    SingleSpanBridgeGeometry,
    SurfacingLayer,
)
from rc_single_span.verification.full_bridge import (
    build_full_bridge_stage_model,
    build_full_bridge_verification_suite,
)


def _project(*, elastic_modulus_mpa: float | None = 31_000.0) -> BridgeProject:
    return BridgeProject(
        name="Full seven-girder benchmark",
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
            elastic_modulus_mpa=elastic_modulus_mpa,
        ),
        permanent_actions=PermanentActionModel(
            surfacing_layers=[
                SurfacingLayer(
                    name="surfacing",
                    thickness_m=0.080,
                    density_kn_m3=22.0,
                    y_start_m=-3.5,
                    y_end_m=3.5,
                    x_end_m=15.0,
                )
            ],
            line_actions=[
                PermanentLineAction(
                    name="left barrier",
                    magnitude_kn_m=10.0,
                    y_m=-5.5,
                    x_end_m=15.0,
                ),
                PermanentLineAction(
                    name="right barrier",
                    magnitude_kn_m=10.0,
                    y_m=5.5,
                    x_end_m=15.0,
                ),
            ],
        ),
    )


def _orientation_counts(model) -> tuple[int, int]:
    nodes = {item.node_id: item for item in model.nodes}
    longitudinal = sum(
        1
        for beam in model.beams
        if nodes[beam.node_i].y_m == pytest.approx(nodes[beam.node_j].y_m)
        and nodes[beam.node_i].x_m != pytest.approx(nodes[beam.node_j].x_m)
    )
    return longitudinal, len(model.beams) - longitudinal


def test_all_three_stage_models_contain_every_girder_line() -> None:
    suite = build_full_bridge_verification_suite(
        _project(),
        longitudinal_divisions=6,
    )

    assert len(suite.stages) == 3
    assert suite.passes_internal_checks
    for item in suite.stages:
        nodes = {node.node_id: node for node in item.model.nodes}
        longitudinal_y = {
            round(nodes[beam.node_i].y_m, 9)
            for beam in item.model.beams
            if nodes[beam.node_i].y_m == pytest.approx(nodes[beam.node_j].y_m)
            and nodes[beam.node_i].x_m != pytest.approx(nodes[beam.node_j].x_m)
        }
        assert longitudinal_y == {-5.1, -3.4, -1.7, 0.0, 1.7, 3.4, 5.1}
        assert item.analysis.total_applied_vertical_load_kn < 0.0
        assert item.analysis.total_vertical_reaction_kn > 0.0
        assert item.analysis.vertical_equilibrium_residual_kn == pytest.approx(
            0.0,
            abs=1.0e-7,
        )
        assert "PERFORM ANALYSIS" in item.staad_package.staad_std
        assert "PRINT MEMBER FORCES GLOBAL" in item.staad_package.staad_std


def test_transverse_deck_members_activate_only_after_composite_hardening() -> None:
    suite = build_full_bridge_verification_suite(
        _project(),
        longitudinal_divisions=6,
    )
    precast = suite.stage(PermanentActionStage.PRECAST_GIRDER)
    wet_deck = suite.stage(PermanentActionStage.DECK_CONSTRUCTION)
    final = suite.stage(PermanentActionStage.SUPERIMPOSED)

    assert _orientation_counts(precast.model)[1] == 0
    assert _orientation_counts(wet_deck.model)[1] == 0
    assert precast.transverse_system_active is False
    assert wet_deck.transverse_system_active is False
    assert final.transverse_system_active is True
    assert _orientation_counts(final.model)[1] > 0
    assert final.transverse_member_count > 0

    precast_iy = precast.model.sections[3].iy_m4
    wet_deck_iy = wet_deck.model.sections[3].iy_m4
    final_iy = final.model.sections[3].iy_m4
    assert wet_deck_iy == pytest.approx(precast_iy)
    assert final_iy > wet_deck_iy


@pytest.mark.parametrize("stage", list(PermanentActionStage))
def test_each_full_width_stage_preserves_its_automatic_load_resultant(stage) -> None:
    project = _project()
    model = build_full_bridge_stage_model(
        project,
        stage=stage,
        longitudinal_divisions=6,
    )
    expected = -sum(
        item.total_load_kn for item in automatic_permanent_loads(project) if item.stage is stage
    )
    applied = 0.0
    case = model.load_cases[0]
    for load in case.uniform_loads:
        length = model.member_length_m(load.member_id)
        start = 0.0 if load.start_m is None else load.start_m
        end = length if load.end_m is None else load.end_m
        applied += load.magnitude_kn_m * (end - start)
    assert applied == pytest.approx(expected)


def test_full_bridge_builder_requires_an_explicit_elastic_modulus() -> None:
    with pytest.raises(ValueError, match="elastic_modulus_mpa"):
        build_full_bridge_stage_model(
            _project(elastic_modulus_mpa=None),
            stage=PermanentActionStage.PRECAST_GIRDER,
        )
