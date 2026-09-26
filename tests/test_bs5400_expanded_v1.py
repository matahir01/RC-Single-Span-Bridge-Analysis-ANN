from types import SimpleNamespace

import pytest

from rc_single_span.codes.bs5400.combinations import BS5400LimitState
from rc_single_span.codes.bs5400.secondary import (
    BS5400Combination4Action,
    bearing_friction_gamma_fl,
    build_bs5400_combination4,
    build_bs5400_combination5,
    centrifugal_nominal_kn,
    combination4_factors,
    ha_longitudinal_nominal_kn,
    hb_longitudinal_nominal_kn,
    nominal_bearing_friction_force_kn,
    skidding_nominal_kn,
)
from rc_single_span.codes.common import LoadEffects
from rc_single_span.design.bs5400_advanced import (
    bs5400_curtailment_extension_m,
    bs5400_standard_fatigue_vehicle,
    resolve_bs5400_stage_d_code_defaults,
)
from rc_single_span.design.project import BS5400DesignInputs
from rc_single_span.design.stage_d_project import AdvancedStageDInputs


def test_bd37_combination4_nominal_secondary_actions_are_source_pinned() -> None:
    assert ha_longitudinal_nominal_kn(15.0) == pytest.approx(370.0)
    assert ha_longitudinal_nominal_kn(100.0) == pytest.approx(750.0)
    assert hb_longitudinal_nominal_kn(1200.0) == pytest.approx(300.0)
    assert skidding_nominal_kn() == pytest.approx(300.0)
    assert centrifugal_nominal_kn(500.0) == pytest.approx(40000.0 / 650.0)
    assert centrifugal_nominal_kn(1000.0) == 0.0


def test_bd37_combination4_factors_and_separate_secondary_cases() -> None:
    expected = {
        BS5400Combination4Action.CENTRIFUGAL: 1.50,
        BS5400Combination4Action.LONGITUDINAL_HA: 1.25,
        BS5400Combination4Action.LONGITUDINAL_HB: 1.10,
        BS5400Combination4Action.SKIDDING_HA: 1.25,
    }
    for action, gamma in expected.items():
        factors = combination4_factors(action)
        assert factors.gamma(BS5400LimitState.ULS) == pytest.approx(gamma)
        assert factors.gamma(BS5400LimitState.SLS) == pytest.approx(1.0)

    result = build_bs5400_combination4(
        factored_permanent=LoadEffects(moment_knm=100.0, shear_kn=20.0),
        secondary_nominal=LoadEffects(moment_knm=10.0, shear_kn=4.0),
        associated_primary_nominal=LoadEffects(moment_knm=30.0, shear_kn=8.0),
        action=BS5400Combination4Action.LONGITUDINAL_HA,
        limit_state=BS5400LimitState.ULS,
        permanent_factor_audit={"structural_dead": 1.15},
    )
    assert result.effects.moment_knm == pytest.approx(150.0)
    assert result.effects.shear_kn == pytest.approx(35.0)
    assert result.factors["secondary_live"] == pytest.approx(1.25)
    assert result.factors["associated_primary_live"] == pytest.approx(1.25)


def test_bd37_combination5_bearing_friction_is_source_pinned() -> None:
    assert nominal_bearing_friction_force_kn(
        nominal_vertical_load_kn=1000.0,
        coefficient_of_friction=0.05,
    ) == pytest.approx(50.0)
    assert bearing_friction_gamma_fl("uls") == pytest.approx(1.30)
    assert bearing_friction_gamma_fl("sls") == pytest.approx(1.00)

    result = build_bs5400_combination5(
        factored_permanent=LoadEffects(moment_knm=100.0, shear_kn=20.0),
        bearing_friction_nominal=LoadEffects(moment_knm=12.0, shear_kn=5.0),
        limit_state=BS5400LimitState.ULS,
        permanent_factor_audit={"structural_dead": 1.15},
    )
    assert result.effects.moment_knm == pytest.approx(115.6)
    assert result.effects.shear_kn == pytest.approx(26.5)
    assert result.factors["bearing_friction"] == pytest.approx(1.30)


def test_bs5400_part10_standard_fatigue_vehicle_is_320_kn() -> None:
    vehicle = bs5400_standard_fatigue_vehicle()
    assert vehicle.axle_loads_kn == (80.0, 80.0, 80.0, 80.0)
    assert vehicle.axle_spacings_m == (1.8, 6.0, 1.8)
    assert sum(vehicle.axle_loads_kn) == pytest.approx(320.0)


def test_bs5400_clause_5_8_7_curtailment_extension_is_greater_of_d_or_12_phi() -> None:
    assert bs5400_curtailment_extension_m(
        effective_depth_m=1.10,
        bar_diameter_mm=32.0,
    ) == pytest.approx(1.10)
    assert bs5400_curtailment_extension_m(
        effective_depth_m=0.30,
        bar_diameter_mm=32.0,
    ) == pytest.approx(0.384)


def test_stage_d_resolver_supplies_bs_code_vehicle_and_curtailment_rule() -> None:
    design_inputs = BS5400DesignInputs(
        effective_depth_m=1.10,
        bar_diameter_mm=32.0,
        bar_spacing_mm=100.0,
        nominal_cover_mm=40.0,
        crack_point_depth_mm=1180.0,
        allowable_crack_width_mm=0.25,
        ec_modified_mpa=30000.0,
    )
    inputs = AdvancedStageDInputs(
        support_anchorage_length_m=0.8,
        minimum_support_bars=2,
        minimum_extension_beyond_theoretical_cutoff_m=0.0,
        lap_length_m=1.2,
        splice_end_exclusion_m=1.0,
        maximum_splice_fraction=0.5,
        maximum_demand_ratio_for_splicing=0.7,
        fatigue_distribution_factors=(0.2,),
        fatigue_characteristic_resistance_range_mpa=180.0,
        construction_stage_allowable_steel_stress_mpa=400.0,
        bearing_width_mm=400.0,
        bearing_length_mm=500.0,
        allowable_bearing_pressure_mpa=8.0,
        end_zone_width_mm=800.0,
        end_zone_depth_mm=1200.0,
        maximum_local_steel_ratio=0.08,
        sls_tension_steel_stress_limit_mpa=400.0,
        sls_compression_steel_stress_limit_mpa=400.0,
    )
    detail = SimpleNamespace(
        girder_index=1,
        doubly_reinforced_cage_selection=None,
        selected_longitudinal=SimpleNamespace(bar_diameter_mm=32.0),
        longitudinal_synthesis=None,
    )
    resolved = resolve_bs5400_stage_d_code_defaults(
        design_inputs=design_inputs,
        details=(detail,),
        inputs=inputs,
    )
    assert resolved.bs5400_fatigue_vehicle is not None
    assert resolved.bs5400_fatigue_vehicle.axle_loads_kn == (80.0, 80.0, 80.0, 80.0)
    assert resolved.bs5400_tension_shift_length_m == pytest.approx(1.10)
