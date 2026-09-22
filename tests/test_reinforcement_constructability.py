from types import SimpleNamespace

import pytest

from rc_single_span.codes.eurocode.combinations import EurocodeServiceabilityFactors
from rc_single_span.core.models import (
    BarLayer,
    BridgeProject,
    DeckConstruction,
    LongitudinalReinforcement,
    MaterialProperties,
    RectangularGirderProfile,
    SingleSpanBridgeGeometry,
)
from rc_single_span.design.bs5400_detailing import detailing_limits_bs5400
from rc_single_span.design.detailing import (
    audit_provided_longitudinal_cage,
    generate_longitudinal_bar_arrangements,
    longitudinal_cage_effective_depth_m,
    select_longitudinal_bar_arrangement,
)
from rc_single_span.design.project import (
    BS5400DesignInputs,
    EC2DesignInputs,
    EurocodeSLSBasis,
    run_bs5400_project_design,
    run_eurocode_project_design,
)
from rc_single_span.design.project_detailing import (
    BS5400DetailingInputs,
    EC2DetailingInputs,
    run_bs5400_project_detailing,
    run_eurocode_project_detailing,
)
from rc_single_span.traffic.combinations import (
    build_bs5400_project_combinations,
    build_eurocode_project_combinations,
)


def _project() -> BridgeProject:
    return BridgeProject(
        name="Reinforcement constructability benchmark",
        geometry=SingleSpanBridgeGeometry(
            span_m=15.0,
            physical_girder_length_m=14.95,
            deck_width_m=11.0,
            carriageway_width_m=7.0,
            girder_count=7,
            girder_spacing_m=1.70,
            girder_profile=RectangularGirderProfile(
                width_m=0.40,
                depth_m=0.95,
            ),
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
        provided_longitudinal_reinforcement=LongitudinalReinforcement(
            layers=[BarLayer(count=4, diameter_mm=32.0) for _ in range(4)]
        ),
    )


def _component(value: float) -> SimpleNamespace:
    return SimpleNamespace(value=value)


def _traffic_girder(
    index: int,
    *,
    moment: float,
    shear: float,
    torsion: float,
    deflection: float,
    x_m: float,
) -> SimpleNamespace:
    return SimpleNamespace(
        girder_index=index,
        moment_knm=_component(moment),
        shear_kn=_component(shear),
        torsion_knm=_component(torsion),
        deflection_mm=_component(deflection),
        deflection_position_m=x_m,
    )


def _traffic_result(
    *,
    moment: float,
    shear: float,
    torsion: float,
    deflection: float,
    x_m: float = 7.5,
) -> SimpleNamespace:
    return SimpleNamespace(
        girders=tuple(
            _traffic_girder(
                index,
                moment=moment,
                shear=shear,
                torsion=torsion,
                deflection=deflection,
                x_m=x_m,
            )
            for index in range(1, 8)
        )
    )


def test_discrete_selector_can_form_four_layers_of_four_y32() -> None:
    result = select_longitudinal_bar_arrangement(
        required_area_mm2=12800.0,
        web_width_mm=400.0,
        cover_mm=30.0,
        link_diameter_mm=12.0,
        minimum_clear_spacing_mm=25.0,
        available_diameters_mm=(32.0,),
        maximum_layers=4,
        diameter_governs_clear_spacing=False,
    )
    assert result.bar_diameter_mm == pytest.approx(32.0)
    assert result.bar_count == 16
    assert result.layer_count == 4
    assert result.bars_per_layer == (4, 4, 4, 4)
    assert result.clear_horizontal_spacing_mm == pytest.approx(62.6666666667)
    assert result.fits_web


def test_actual_four_by_four_y32_cage_keeps_unknown_vertical_spacing_unresolved() -> None:
    project = _project()
    audit = audit_provided_longitudinal_cage(
        reinforcement=project.provided_longitudinal_reinforcement,
        web_width_mm=400.0,
        cover_mm=30.0,
        link_diameter_mm=12.0,
        minimum_clear_spacing_mm=25.0,
        section_total_depth_mm=1200.0,
        provided_vertical_clear_spacing_mm=None,
        diameter_governs_clear_spacing=False,
    )
    assert audit.horizontal_fit
    assert audit.passes is None
    assert audit.vertical_spacing_ok is None
    assert audit.required_stack_depth_mm is None
    assert "remains unresolved" in audit.status


def test_bs5400_grade410_is_not_silently_remapped_for_minimum_main_steel() -> None:
    with pytest.raises(ValueError, match="not inferred"):
        detailing_limits_bs5400(
            average_breadth_excluding_compression_flange_m=0.40,
            effective_depth_m=1.10,
            gross_concrete_area_m2=0.60,
            reinforcement_grade_mpa=410.0,
            side_face_depth_m=0.95,
            side_face_breadth_m=0.40,
            maximum_aggregate_size_mm=20.0,
        )

    explicit = detailing_limits_bs5400(
        average_breadth_excluding_compression_flange_m=0.40,
        effective_depth_m=1.10,
        gross_concrete_area_m2=0.60,
        reinforcement_grade_mpa=410.0,
        side_face_depth_m=0.95,
        side_face_breadth_m=0.40,
        maximum_aggregate_size_mm=20.0,
        adopted_minimum_main_ratio=0.0018,
    )
    assert explicit.adopted_minimum_main_ratio == pytest.approx(0.0018)
    assert "explicit" in explicit.minimum_main_ratio_basis


def test_eurocode_project_detailing_sizes_discrete_bars_links_and_audits_provided_cage() -> None:
    project = _project()
    traffic = _traffic_result(
        moment=600.0,
        shear=220.0,
        torsion=20.0,
        deflection=8.0,
    )
    combinations = build_eurocode_project_combinations(
        project,
        traffic,
        sls_factors=EurocodeServiceabilityFactors(
            psi1_traffic=0.75,
            psi2_traffic=0.30,
        ),
    )
    design_inputs = EC2DesignInputs(
        effective_depth_m=1.10,
        bar_diameter_mm=32.0,
        bar_spacing_mm=100.0,
        cover_mm=40.0,
        fct_eff_mpa=2.6,
        crack_limit_mm=0.30,
        maximum_neutral_axis_ratio=0.45,
        es_mpa=200000.0,
        ecm_mpa=30000.0,
        deflection_limit_mm=60.0,
        sls_basis=EurocodeSLSBasis.FREQUENT,
    )
    design = run_eurocode_project_design(
        project,
        combinations,
        traffic,
        inputs=design_inputs,
    )
    detailed = run_eurocode_project_detailing(
        project,
        combinations,
        design,
        design_inputs=design_inputs,
        detailing_inputs=EC2DetailingInputs(
            fctm_mpa=2.6,
            aggregate_size_mm=20.0,
            durability_minimum_cover_mm=30.0,
            allowance_for_deviation_mm=5.0,
            provided_cover_mm=40.0,
            provided_link_diameter_mm=12.0,
            provided_vertical_clear_spacing_mm=None,
        ),
    )

    assert len(detailed) == 7
    first = detailed[0]
    assert first.required_flexural_steel_mm2 is not None
    assert first.required_flexural_steel_issue is None
    assert first.selected_longitudinal is not None
    assert first.selected_longitudinal.provided_area_mm2 >= (
        first.governing_required_longitudinal_steel_mm2
    )
    assert first.selected_links.provided_asw_per_s_mm2_per_m >= (
        first.shear_limits.minimum_asw_per_s_mm2_per_m
    )
    assert first.recommended_cage_audit is not None
    assert first.recommended_cage_audit.passes
    assert first.provided_cage_audit is not None
    assert first.provided_cage_audit.horizontal_fit
    assert first.provided_cage_audit.passes is None
    assert first.provided_above_minimum
    assert first.provided_below_maximum
    assert first.cover_check.passes


def test_bs5400_project_detailing_can_recommend_valid_steel_even_when_provided_exterior_is_outside_singly_reinforced_scope() -> None:
    project = _project()
    suite = SimpleNamespace(
        ha=_traffic_result(
            moment=420.0,
            shear=250.0,
            torsion=5.0,
            deflection=7.0,
            x_m=7.0,
        ),
        hb=_traffic_result(
            moment=520.0,
            shear=230.0,
            torsion=12.0,
            deflection=9.0,
            x_m=7.5,
        ),
        ha_hb=_traffic_result(
            moment=490.0,
            shear=340.0,
            torsion=8.0,
            deflection=10.0,
            x_m=8.0,
        ),
    )
    combinations = build_bs5400_project_combinations(
        project,
        suite,
        combinations=(1, 2, 3),
    )
    design_inputs = BS5400DesignInputs(
        effective_depth_m=1.10,
        bar_diameter_mm=32.0,
        bar_spacing_mm=100.0,
        nominal_cover_mm=30.0,
        crack_point_depth_mm=1190.0,
        allowable_crack_width_mm=0.25,
        ec_modified_mpa=27000.0,
        es_mpa=200000.0,
        deflection_limit_mm=60.0,
    )
    design = run_bs5400_project_design(
        project,
        combinations,
        suite,
        inputs=design_inputs,
    )
    assert design[0].flexure is None
    assert design[0].flexure_issue is not None

    detailed = run_bs5400_project_detailing(
        project,
        combinations,
        design,
        design_inputs=design_inputs,
        detailing_inputs=BS5400DetailingInputs(
            aggregate_size_mm=20.0,
            provided_cover_mm=30.0,
            adopted_minimum_main_ratio=0.0018,
            provided_link_diameter_mm=12.0,
            provided_link_spacing_mm=200.0,
            provided_vertical_clear_spacing_mm=None,
            provided_side_face_steel_each_face_mm2=250.0,
        ),
    )

    exterior = detailed[0]
    assert exterior.required_flexural_steel_mm2 is not None
    assert exterior.required_flexural_steel_issue is None
    assert exterior.selected_longitudinal is not None
    assert exterior.selected_longitudinal.provided_area_mm2 >= (
        exterior.governing_required_longitudinal_steel_mm2
    )
    assert exterior.selected_links.provided_asw_per_s_mm2_per_m >= (
        design[0].shear.governing_asv_per_s_mm2_per_m
    )
    assert exterior.recommended_cage_audit is not None
    assert exterior.recommended_cage_audit.passes
    assert exterior.provided_cage_audit is not None
    assert exterior.provided_cage_audit.horizontal_fit
    assert exterior.provided_cage_audit.passes is None
    assert exterior.provided_tension_spacing_ok
    assert exterior.provided_link_spacing_ok
    assert exterior.side_face_steel_ok
    assert "explicit" in exterior.limits.minimum_main_ratio_basis


def test_candidate_generator_keeps_larger_cages_available_for_sls_recheck() -> None:
    candidates = generate_longitudinal_bar_arrangements(
        minimum_area_mm2=6600.0,
        web_width_mm=400.0,
        cover_mm=50.0,
        link_diameter_mm=12.0,
        minimum_clear_spacing_mm=32.0,
        available_diameters_mm=(20.0, 25.0, 32.0),
        maximum_layers=4,
        diameter_governs_clear_spacing=True,
    )

    assert candidates
    assert candidates[0].provided_area_mm2 >= 6600.0
    assert any(item.provided_area_mm2 > 10000.0 for item in candidates)
    assert any(item.bar_diameter_mm == pytest.approx(32.0) for item in candidates)


def test_candidate_effective_depth_comes_from_real_multilayer_cage_centroid() -> None:
    arrangement = select_longitudinal_bar_arrangement(
        required_area_mm2=12800.0,
        web_width_mm=400.0,
        cover_mm=50.0,
        link_diameter_mm=12.0,
        minimum_clear_spacing_mm=32.0,
        available_diameters_mm=(32.0,),
        maximum_layers=4,
        preferred_vertical_clear_spacing_mm=40.0,
        diameter_governs_clear_spacing=True,
    )
    effective_depth = longitudinal_cage_effective_depth_m(
        arrangement,
        section_total_depth_mm=1450.0,
        cover_mm=50.0,
        link_diameter_mm=12.0,
    )

    # 4Y32 x 4 layers at 72 mm vertical pitch: bar-centre levels are
    # 78, 150, 222 and 294 mm from the soffit, centroid = 186 mm.
    assert arrangement.bars_per_layer == (4, 4, 4, 4)
    assert effective_depth == pytest.approx((1450.0 - 186.0) / 1000.0)
