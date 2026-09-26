from types import SimpleNamespace

import pytest

from rc_single_span.analysis.sections import (
    ConcreteLayer,
    final_composite_concrete_layers,
)
from rc_single_span.codes.bs5400.combinations import BS5400PrimaryTraffic
from rc_single_span.codes.eurocode.basis import BS_EN_1990
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
from rc_single_span.design.bs5400 import (
    check_layered_flexure_bs5400,
    check_shear_bs5400,
)
from rc_single_span.design.eurocode import check_layered_flexure_ec2
from rc_single_span.design.project import (
    BS5400DesignInputs,
    EC2DesignInputs,
    EurocodeSLSBasis,
    run_bs5400_project_design,
    run_eurocode_project_design,
)
from rc_single_span.traffic.combinations import (
    build_bs5400_project_combinations,
    build_eurocode_project_combinations,
)


def _project() -> BridgeProject:
    return BridgeProject(
        name="RC design workflow benchmark",
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


def test_final_section_keeps_nonparticipating_false_slab_as_physical_gap() -> None:
    layers = final_composite_concrete_layers(
        _project().geometry,
        girder_index=4,
    )
    assert layers[0].top_m == pytest.approx(0.0)
    assert layers[0].bottom_m == pytest.approx(0.175)
    assert layers[1].top_m == pytest.approx(0.250)
    assert layers[1].bottom_m == pytest.approx(1.200)
    assert layers[1].top_m - layers[0].bottom_m == pytest.approx(0.075)


def test_ec2_layered_flexure_matches_contiguous_t_section_benchmark() -> None:
    layers = (
        ConcreteLayer(1.70, 0.0, 0.175, "deck flange"),
        ConcreteLayer(0.30, 0.175, 1.20, "web"),
    )
    result = check_layered_flexure_ec2(
        med_knm=1800.0,
        layers=layers,
        effective_depth_m=1.10,
        steel_area_mm2=6500.0,
        fck_mpa=35.0,
        fyk_mpa=500.0,
        maximum_neutral_axis_ratio=0.45,
    )
    assert result.resistance_knm == pytest.approx(3008.02211244, rel=1.0e-9)
    assert result.g_flexure_knm > 0.0
    assert result.ductility_passes


def test_bs5400_layered_flexure_matches_existing_t_section_benchmark() -> None:
    layers = (
        ConcreteLayer(1.70, 0.0, 0.175, "deck flange"),
        ConcreteLayer(0.30, 0.175, 1.20, "web"),
    )
    result = check_layered_flexure_bs5400(
        med_knm=1800.0,
        layers=layers,
        effective_depth_m=1.10,
        steel_area_mm2=6500.0,
        fcu_mpa=40.0,
        fy_mpa=500.0,
    )
    assert result.neutral_axis_m == pytest.approx(0.103952205882)
    assert result.lever_arm_m == pytest.approx(1.045)
    assert result.resistance_knm == pytest.approx(2954.7375)
    assert result.g_flexure_knm > 0.0


def test_bs5400_shear_retains_published_reference_values() -> None:
    result = check_shear_bs5400(
        ved_kn=443.0,
        web_width_m=1.0,
        effective_depth_m=0.824,
        longitudinal_steel_area_mm2=5362.0,
        fcu_mpa=40.0,
        fyv_mpa=500.0,
    )
    assert result.concrete_resistance_kn == pytest.approx(465.544847200)
    assert result.governing_asv_per_s_mm2_per_m == pytest.approx(999.500249875)
    assert not result.exceeds_maximum_shear


def test_eurocode_project_design_consumes_combined_effects_and_actual_lm1_deflection() -> None:
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
    result = run_eurocode_project_design(
        project,
        combinations,
        traffic,
        inputs=EC2DesignInputs(
            effective_depth_m=1.10,
            bar_diameter_mm=32.0,
            bar_spacing_mm=100.0,
            cover_mm=30.0,
            fct_eff_mpa=2.6,
            crack_limit_mm=0.30,
            maximum_neutral_axis_ratio=0.45,
            es_mpa=200000.0,
            ecm_mpa=30000.0,
            deflection_limit_mm=60.0,
            sls_basis=EurocodeSLSBasis.FREQUENT,
        ),
    )

    assert len(result) == 7
    first = result[0]
    assert first.uls_combination_name == f"{BS_EN_1990} persistent ULS"
    assert first.sls_combination_name == f"{BS_EN_1990} frequent SLS"
    assert first.flexure.design_moment_knm == pytest.approx(
        combinations[0].combinations.persistent_uls.effects.moment_knm
    )
    assert first.shear.design_shear_kn == pytest.approx(
        combinations[0].combinations.persistent_uls.effects.shear_kn
    )
    assert first.cracking.crack_width_mm >= 0.0
    assert first.deflection.traffic_characteristic_deflection_mm == pytest.approx(8.0)
    assert first.deflection.traffic_factor == pytest.approx(0.75)
    assert first.deflection.total_deflection_mm > 6.0
    assert "same traffic-governing station" in first.deflection.status


def test_bs5400_project_design_keeps_governing_case_provenance() -> None:
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
    result = run_bs5400_project_design(
        project,
        combinations,
        suite,
        inputs=BS5400DesignInputs(
            effective_depth_m=1.10,
            bar_diameter_mm=32.0,
            bar_spacing_mm=100.0,
            nominal_cover_mm=30.0,
            crack_point_depth_mm=1190.0,
            allowable_crack_width_mm=0.25,
            ec_modified_mpa=27000.0,
            es_mpa=200000.0,
            deflection_limit_mm=60.0,
        ),
    )

    assert len(result) == 7
    exterior = result[0]
    assert "HB" in exterior.flexure_case.upper()
    assert "ha_hb" in exterior.shear_case.lower()
    assert exterior.flexure is None
    assert exterior.flexure_issue is not None
    assert "Neutral axis exceeds" in exterior.flexure_issue
    assert exterior.shear.design_shear_kn > 0.0
    assert exterior.cracking.crack_width_mm >= 0.0
    assert exterior.deflection.total_deflection_mm > 0.0
    assert any(
        source in exterior.deflection.status
        for source in (
            BS5400PrimaryTraffic.HA.value,
            BS5400PrimaryTraffic.HB.value,
            BS5400PrimaryTraffic.HA_HB.value,
        )
    )

    interior = result[3]
    assert interior.flexure is not None
    assert interior.flexure_issue is None
    assert interior.flexure.design_moment_knm > 0.0
