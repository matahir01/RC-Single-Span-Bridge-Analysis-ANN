import pytest

from rc_single_span.codes.eurocode.combinations import (
    EurocodeCombinationFactors,
    EurocodeServiceabilityFactors,
)
from rc_single_span.core.models import (
    BridgeProject,
    MaterialProperties,
    RectangularGirderProfile,
    SingleSpanBridgeGeometry,
)
from rc_single_span.design.detailing import select_longitudinal_bar_arrangement
from rc_single_span.design.project import (
    EC2DesignInputs,
    EurocodeSLSBasis,
    run_eurocode_project_design,
)
from rc_single_span.design.project_detailing import (
    EC2DetailingInputs,
    run_eurocode_project_detailing,
)
from rc_single_span.design.reinforcement_envelope import (
    build_ec2_curtailment_plan_from_envelope,
    build_ec2_station_reinforcement_envelope,
)
from rc_single_span.traffic.combinations import build_eurocode_project_combinations
from rc_single_span.traffic.lm1 import run_lm1_grillage_search


def _project() -> BridgeProject:
    return BridgeProject(
        name="Station reinforcement envelope benchmark",
        geometry=SingleSpanBridgeGeometry(
            span_m=10.0,
            deck_width_m=5.0,
            carriageway_width_m=3.0,
            girder_count=3,
            girder_spacing_m=1.70,
            girder_profile=RectangularGirderProfile(
                width_m=0.40,
                depth_m=1.20,
            ),
        ),
        materials=MaterialProperties(
            fck_mpa=35.0,
            fcu_mpa=45.0,
            fyk_mpa=500.0,
            concrete_density_kn_m3=25.0,
            elastic_modulus_mpa=34000.0,
        ),
    )


def test_lm1_search_retains_stationwise_moment_envelope_without_all_cases() -> None:
    project = _project()
    traffic = run_lm1_grillage_search(
        project,
        longitudinal_step_m=5.0,
        max_exhaustive_tandem_combinations=1000,
        retain_all_cases=False,
    )

    assert traffic.station_moments
    assert len(traffic.station_moments) == 3
    centre = traffic.station_moments[1]
    assert centre.girder_index == 2
    assert centre.stations[0].x_m == pytest.approx(0.0)
    assert centre.stations[-1].x_m == pytest.approx(10.0)
    assert max(item.moment_knm.value for item in centre.stations) > 0.0
    assert all(item.moment_knm.case_id > 0 for item in centre.stations)


def test_ec2_station_demand_keeps_minimum_steel_at_supports_and_peaks_inside_span() -> None:
    project = _project()
    traffic = run_lm1_grillage_search(
        project,
        longitudinal_step_m=5.0,
        max_exhaustive_tandem_combinations=1000,
    )
    minimum_area = 1200.0

    envelope = build_ec2_station_reinforcement_envelope(
        project,
        traffic,
        girder_index=2,
        effective_depth_m=1.10,
        minimum_area_mm2=minimum_area,
        maximum_neutral_axis_ratio=0.45,
        uls_factors=EurocodeCombinationFactors(
            gamma_g_unfavourable=1.35,
            gamma_q_traffic=1.35,
        ),
    )

    assert envelope.singly_reinforced_complete
    assert envelope.traffic_search_exhaustive
    assert envelope.stations[0].governing_required_area_mm2 == pytest.approx(
        minimum_area
    )
    assert envelope.stations[-1].governing_required_area_mm2 == pytest.approx(
        minimum_area
    )
    assert envelope.maximum_required_area_mm2 is not None
    assert envelope.maximum_required_area_mm2 > minimum_area
    assert envelope.maximum_required_station_m is not None
    assert 0.0 < envelope.maximum_required_station_m < 10.0


def test_station_envelope_drives_a_real_curtailment_plan() -> None:
    project = _project()
    traffic = run_lm1_grillage_search(
        project,
        longitudinal_step_m=5.0,
        max_exhaustive_tandem_combinations=1000,
    )
    envelope = build_ec2_station_reinforcement_envelope(
        project,
        traffic,
        girder_index=2,
        effective_depth_m=1.10,
        minimum_area_mm2=1200.0,
        maximum_neutral_axis_ratio=0.45,
    )
    assert envelope.maximum_required_area_mm2 is not None

    arrangement = select_longitudinal_bar_arrangement(
        required_area_mm2=envelope.maximum_required_area_mm2,
        web_width_mm=400.0,
        cover_mm=40.0,
        link_diameter_mm=12.0,
        minimum_clear_spacing_mm=25.0,
        available_diameters_mm=(20.0, 25.0, 32.0),
        maximum_layers=4,
        diameter_governs_clear_spacing=True,
    )
    plan = build_ec2_curtailment_plan_from_envelope(
        envelope,
        span_m=10.0,
        arrangement=arrangement,
        anchorage_length_mm=900.0,
    )

    assert plan.zones
    assert plan.total_bars == arrangement.bar_count
    assert max(zone.bars_to_continue for zone in plan.zones) <= arrangement.bar_count
    assert any(zone.bars_to_continue < arrangement.bar_count for zone in plan.zones)


def test_project_detailing_generates_station_envelope_and_curtailment_when_lm1_is_supplied() -> None:
    project = _project()
    traffic = run_lm1_grillage_search(
        project,
        longitudinal_step_m=5.0,
        max_exhaustive_tandem_combinations=1000,
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
        bar_diameter_mm=25.0,
        bar_spacing_mm=120.0,
        cover_mm=40.0,
        fct_eff_mpa=2.6,
        crack_limit_mm=0.30,
        maximum_neutral_axis_ratio=0.45,
        steel_area_mm2=6000.0,
        es_mpa=200000.0,
        ecm_mpa=34000.0,
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
        ),
        traffic=traffic,
    )

    middle = detailed[1]
    assert middle.reinforcement_envelope is not None
    assert middle.reinforcement_envelope.singly_reinforced_complete
    assert middle.reinforcement_envelope.maximum_required_area_mm2 is not None
    assert middle.curtailment_plan is not None
    assert middle.selected_longitudinal is not None
    assert middle.curtailment_plan.total_bars == middle.selected_longitudinal.bar_count
    assert middle.curtailment_plan.zones
