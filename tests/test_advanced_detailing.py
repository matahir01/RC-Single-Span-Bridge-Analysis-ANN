import pytest

from rc_single_span.analysis.sections import ConcreteLayer
from rc_single_span.core.models import (
    BridgeProject,
    MaterialProperties,
    RectangularGirderProfile,
    SingleSpanBridgeGeometry,
)
from rc_single_span.design.advanced_detailing import (
    TerminationCodeProfile,
    apply_support_and_termination_rules,
    build_lap_splice_zones,
    build_termination_rules,
    check_doubly_reinforced_sls_bs5400,
    check_doubly_reinforced_sls_ec2,
    check_local_bearing_end_zone_congestion,
    construction_stage_reinforcement_stress_checks,
    eurocode_flm3_vehicle,
    fatigue_vehicle_to_steel_stress_range,
)
from rc_single_span.design.detailing import select_longitudinal_bar_arrangement
from rc_single_span.design.longitudinal_detailing import (
    LongitudinalDemandStation,
    build_symmetric_curtailment_plan,
)


def _arrangement(required: float = 5000.0):
    return select_longitudinal_bar_arrangement(
        required_area_mm2=required,
        web_width_mm=400.0,
        cover_mm=40.0,
        link_diameter_mm=12.0,
        minimum_clear_spacing_mm=25.0,
        available_diameters_mm=(20.0, 25.0, 32.0),
        maximum_layers=4,
        diameter_governs_clear_spacing=True,
    )


def _project() -> BridgeProject:
    return BridgeProject(
        name="advanced detailing benchmark",
        geometry=SingleSpanBridgeGeometry(
            span_m=20.0,
            deck_width_m=11.0,
            carriageway_width_m=7.0,
            girder_count=7,
            girder_spacing_m=1.7,
            girder_profile=RectangularGirderProfile(width_m=0.40, depth_m=1.20),
        ),
        materials=MaterialProperties(
            fck_mpa=35.0,
            fcu_mpa=45.0,
            fyk_mpa=500.0,
            concrete_density_kn_m3=25.0,
            elastic_modulus_mpa=34000.0,
        ),
    )


def _layers():
    return (ConcreteLayer(0.40, 0.0, 1.20, "girder"),)


def test_support_shift_and_termination_extend_cutoffs() -> None:
    preliminary = build_symmetric_curtailment_plan(
        span_m=20.0,
        stations=(
            LongitudinalDemandStation(0.0, 800.0),
            LongitudinalDemandStation(5.0, 2500.0),
            LongitudinalDemandStation(10.0, 5000.0),
            LongitudinalDemandStation(15.0, 2500.0),
            LongitudinalDemandStation(20.0, 800.0),
        ),
        bar_diameter_mm=32.0,
        total_bars=8,
        anchorage_length_mm=800.0,
    )
    rules = build_termination_rules(
        code_profile=TerminationCodeProfile.EUROCODE,
        support_anchorage_length_m=0.8,
        minimum_support_bars=2,
        minimum_extension_beyond_theoretical_cutoff_m=0.3,
        lever_arm_m=1.0,
        cot_theta=2.0,
    )
    result = apply_support_and_termination_rules(
        span_m=20.0,
        preliminary=preliminary,
        rules=rules,
    )
    assert rules.tension_shift_length_m == pytest.approx(1.0)
    assert result.support_bars_left == 2
    assert any(
        z.design_cutoff_m is not None
        and abs(z.design_cutoff_m - z.theoretical_cutoff_m) >= 1.79
        for z in result.zones
        if z.theoretical_cutoff_m is not None
    )


def test_bs_termination_requires_explicit_verified_shift() -> None:
    with pytest.raises(ValueError, match="explicit verified tension-shift"):
        build_termination_rules(
            code_profile=TerminationCodeProfile.BS5400,
            support_anchorage_length_m=0.8,
            minimum_support_bars=2,
            minimum_extension_beyond_theoretical_cutoff_m=0.2,
        )


def test_flm3_vehicle_sweep_produces_real_stress_range_and_fatigue_check() -> None:
    arrangement = _arrangement()
    result = fatigue_vehicle_to_steel_stress_range(
        span_m=20.0,
        station_m=10.0,
        vehicle=eurocode_flm3_vehicle(),
        girder_distribution_factor=0.25,
        layers=_layers(),
        tension_steel_area_mm2=arrangement.provided_area_mm2,
        tension_steel_depth_m=1.10,
        es_mpa=200000.0,
        ecm_mpa=34000.0,
        characteristic_resistance_range_mpa=180.0,
        step_m=0.5,
    )
    assert result.maximum_vehicle_moment_knm > 0.0
    assert result.equivalent_stress_range_mpa > 0.0
    assert result.fatigue_check.utilization > 0.0


def test_construction_stage_stress_checks_all_three_load_time_states() -> None:
    result = construction_stage_reinforcement_stress_checks(
        _project(),
        girder_index=4,
        arrangement=_arrangement(),
        cover_mm=40.0,
        link_diameter_mm=12.0,
        es_mpa=200000.0,
        ecm_mpa=34000.0,
        allowable_stress_mpa=400.0,
    )
    assert len(result) == 3
    assert result[0].cumulative_moment_knm > 0.0
    assert result[-1].cumulative_moment_knm >= result[0].cumulative_moment_knm
    assert all(item.steel_stress_mpa >= 0.0 for item in result)


def test_lap_zoning_and_end_zone_checks_are_explicit() -> None:
    preliminary = build_symmetric_curtailment_plan(
        span_m=20.0,
        stations=(
            LongitudinalDemandStation(0.0, 800.0),
            LongitudinalDemandStation(5.0, 1800.0),
            LongitudinalDemandStation(10.0, 5000.0),
            LongitudinalDemandStation(15.0, 1800.0),
            LongitudinalDemandStation(20.0, 800.0),
        ),
        bar_diameter_mm=32.0,
        total_bars=8,
        anchorage_length_mm=800.0,
    )
    rules = build_termination_rules(
        code_profile=TerminationCodeProfile.EUROCODE,
        support_anchorage_length_m=0.8,
        minimum_support_bars=2,
        minimum_extension_beyond_theoretical_cutoff_m=0.2,
        lever_arm_m=1.0,
        cot_theta=2.0,
    )
    termination = apply_support_and_termination_rules(
        span_m=20.0,
        preliminary=preliminary,
        rules=rules,
    )
    restricted_laps = build_lap_splice_zones(
        span_m=20.0,
        termination=termination,
        lap_length_m=1.2,
        end_exclusion_m=2.0,
        maximum_splice_fraction=0.5,
        maximum_demand_ratio_for_splicing=0.7,
    )
    assert restricted_laps
    assert not any(item.permitted for item in restricted_laps)

    laps = build_lap_splice_zones(
        span_m=20.0,
        termination=termination,
        lap_length_m=1.2,
        end_exclusion_m=0.0,
        maximum_splice_fraction=0.5,
        maximum_demand_ratio_for_splicing=0.7,
    )
    assert any(item.permitted for item in laps)

    end = check_local_bearing_end_zone_congestion(
        support_reaction_kn=900.0,
        bearing_width_mm=400.0,
        bearing_length_mm=500.0,
        allowable_bearing_pressure_mpa=8.0,
        end_zone_width_mm=800.0,
        end_zone_depth_mm=1200.0,
        longitudinal_bar_count=8,
        longitudinal_bar_diameter_mm=32.0,
        cover_mm=50.0,
        link_diameter_mm=12.0,
        link_spacing_mm=150.0,
        maximum_link_spacing_mm=200.0,
        minimum_clear_spacing_mm=25.0,
    )
    assert end.bearing_pressure_passes
    assert end.link_spacing_passes


def test_doubly_reinforced_sls_checks_include_both_cages() -> None:
    tension = _arrangement(6500.0)
    compression = _arrangement(1800.0)
    ec2 = check_doubly_reinforced_sls_ec2(
        layers=_layers(),
        total_depth_m=1.20,
        service_moment_knm=1200.0,
        tension=tension,
        compression=compression,
        tension_depth_m=1.08,
        compression_depth_m=0.10,
        cover_mm=40.0,
        es_mpa=200000.0,
        ecm_mpa=34000.0,
        fct_eff_mpa=3.0,
        crack_limit_mm=0.30,
        tension_stress_limit_mpa=400.0,
        compression_stress_limit_mpa=400.0,
    )
    assert ec2.tension_steel_stress_mpa > 0.0
    assert ec2.compression_steel_stress_mpa > 0.0
    assert ec2.crack_width_mm is not None

    bs = check_doubly_reinforced_sls_bs5400(
        layers=_layers(),
        total_depth_m=1.20,
        permanent_moment_knm=700.0,
        live_moment_knm=500.0,
        tension=tension,
        compression=compression,
        tension_depth_m=1.08,
        compression_depth_m=0.10,
        cover_mm=40.0,
        es_mpa=200000.0,
        ec_modified_mpa=30000.0,
        tension_zone_width_m=0.40,
        crack_point_depth_mm=1180.0,
        allowable_crack_width_mm=0.25,
        tension_stress_limit_mpa=400.0,
        compression_stress_limit_mpa=400.0,
    )
    assert bs.tension_steel_stress_mpa > 0.0
    assert bs.crack_width_mm is not None
