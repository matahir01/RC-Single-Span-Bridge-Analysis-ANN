from types import SimpleNamespace

import pytest

from rc_single_span.analysis.permanent import PermanentLoadCategory
from rc_single_span.codes.eurocode.combinations import (
    EurocodeServiceabilityFactors,
)
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
from rc_single_span.verification.full_bridge_campaign import (
    FullBridgeTrafficCaseVerification,
    FullBridgeTrafficSearchConfig,
    TrafficAction,
    build_cross_stage_combination_rules,
    build_permanent_component_suite,
    run_full_bridge_traffic_campaign,
)


def _project() -> BridgeProject:
    return BridgeProject(
        name="Full bridge campaign benchmark",
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
            elastic_modulus_mpa=31_000.0,
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


@pytest.fixture(scope="module")
def traffic_campaign():
    return run_full_bridge_traffic_campaign(
        _project(),
        config=FullBridgeTrafficSearchConfig(
            lm1_longitudinal_step_m=7.5,
            lm1_max_exhaustive_tandem_combinations=1000,
            ha_longitudinal_step_m=7.5,
            ha_max_exhaustive_kel_combinations=1000,
            hb_longitudinal_step_m=15.0,
            hb_transverse_step_m=3.5,
            combined_hb_longitudinal_step_m=15.0,
            combined_hb_transverse_step_m=3.5,
            combined_ha_kel_step_m=15.0,
            combined_max_exhaustive_kel_combinations=1000,
            combined_max_exhaustive_ha_assignments=100,
        ),
    )


def test_traffic_campaign_packages_all_four_actions(traffic_campaign) -> None:
    assert traffic_campaign.passes_internal_checks
    expected_actions = {
        TrafficAction.LM1, TrafficAction.HA, TrafficAction.HB, TrafficAction.HA_HB,
    }
    assert {item.action for item in traffic_campaign.cases} == expected_actions
    assert all(traffic_campaign.cases_for(action) for action in expected_actions)
    assert traffic_campaign.lm1.evaluated_case_count == 100
    assert traffic_campaign.ha.evaluated_case_count == 40
    assert traffic_campaign.hb.evaluated_case_count == 129
    assert traffic_campaign.ha_hb.evaluated_case_count == 1032


def test_every_traffic_file_is_a_connected_seven_girder_model(
    traffic_campaign,
) -> None:
    expected_y = {-5.1, -3.4, -1.7, 0.0, 1.7, 3.4, 5.1}
    for item in traffic_campaign.cases:
        nodes = {node.node_id: node for node in item.model.nodes}
        longitudinal_y = {
            round(nodes[beam.node_i].y_m, 9)
            for beam in item.model.beams
            if nodes[beam.node_i].y_m == pytest.approx(nodes[beam.node_j].y_m)
            and nodes[beam.node_i].x_m != pytest.approx(nodes[beam.node_j].x_m)
        }
        transverse = [
            beam
            for beam in item.model.beams
            if nodes[beam.node_i].x_m == pytest.approx(nodes[beam.node_j].x_m)
            and nodes[beam.node_i].y_m != pytest.approx(nodes[beam.node_j].y_m)
        ]
        assert longitudinal_y == expected_y
        assert transverse
        assert item.governing_for
        assert item.analysis.vertical_equilibrium_residual_kn == pytest.approx(
            0.0,
            abs=1.0e-5,
        )
        assert "STAAD SPACE" in item.staad_package.staad_std
        assert "PRINT MEMBER FORCES GLOBAL" in item.staad_package.staad_std


def test_permanent_components_preserve_category_and_load_time_stiffness() -> None:
    suite = build_permanent_component_suite(
        _project(),
        longitudinal_divisions=6,
    )
    keys = {item.component_key for item in suite.components}
    assert keys == {
        "precast_girder_structural_dead",
        "deck_construction_structural_dead",
        "superimposed_surfacing",
        "superimposed_other_superimposed",
    }
    assert len(suite.for_category(PermanentLoadCategory.STRUCTURAL_DEAD)) == 2

    for item in suite.components:
        assert item.analysis.total_applied_vertical_load_kn == pytest.approx(
            -item.characteristic_resultant_kn
        )
        assert item.analysis.vertical_equilibrium_residual_kn == pytest.approx(
            0.0,
            abs=1.0e-7,
        )
        nodes = {node.node_id: node for node in item.model.nodes}
        transverse_count = sum(
            1
            for beam in item.model.beams
            if nodes[beam.node_i].x_m == pytest.approx(nodes[beam.node_j].x_m)
            and nodes[beam.node_i].y_m != pytest.approx(nodes[beam.node_j].y_m)
        )
        if item.stage is PermanentActionStage.SUPERIMPOSED:
            assert transverse_count > 0
        else:
            assert transverse_count == 0


def test_cross_stage_rules_cover_eurocode_and_bs5400_factors() -> None:
    rules = build_cross_stage_combination_rules(
        eurocode_sls_factors=EurocodeServiceabilityFactors(
            psi1_traffic=0.75,
            psi2_traffic=0.0,
        )
    )
    assert len(rules) == 22
    assert len({item.rule_id for item in rules}) == 22

    ec_uls = next(item for item in rules if item.rule_id == "ec_uls_persistent")
    assert ec_uls.traffic_action is TrafficAction.LM1
    assert set(ec_uls.permanent_factors.values()) == {1.35}
    assert ec_uls.traffic_factor == pytest.approx(1.35)

    bs = next(item for item in rules if item.rule_id == "bs_combination_1_uls_ha")
    assert bs.permanent_factors[PermanentLoadCategory.STRUCTURAL_DEAD] == 1.15
    assert bs.permanent_factors[PermanentLoadCategory.SURFACING] == 1.75
    assert bs.permanent_factors[PermanentLoadCategory.OTHER_SUPERIMPOSED] == 1.20
    assert bs.traffic_factor == pytest.approx(1.50)
    assert "load-time stiffness" in bs.application_basis


def test_packaging_uses_the_shared_sparse_equilibrium_guard() -> None:
    analysis = SimpleNamespace(
        total_applied_vertical_load_kn=-1352.61162,
        total_vertical_reaction_kn=1352.611602,
        vertical_equilibrium_residual_kn=-1.8e-5,
    )
    item = FullBridgeTrafficCaseVerification(
        case_key="ha_hb_regression",
        standard="BD 37/01",
        action=TrafficAction.HA_HB,
        source_case_id=1,
        description="roundoff regression",
        governing_for=("G1 moment",),
        model=None,
        analysis=analysis,
        staad_package=None,
    )
    assert item.passes_equilibrium_check

    failed = FullBridgeTrafficCaseVerification(
        case_key="ha_hb_failed",
        standard="BD 37/01",
        action=TrafficAction.HA_HB,
        source_case_id=2,
        description="material imbalance regression",
        governing_for=("G1 moment",),
        model=None,
        analysis=SimpleNamespace(
            total_applied_vertical_load_kn=-1352.61162,
            total_vertical_reaction_kn=1352.61062,
            vertical_equilibrium_residual_kn=-1.0e-3,
        ),
        staad_package=None,
    )
    assert not failed.passes_equilibrium_check
