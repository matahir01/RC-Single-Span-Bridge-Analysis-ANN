from __future__ import annotations

from dataclasses import dataclass

from rc_single_span.codes.bs5400.combinations import BS5400LimitState
from rc_single_span.core.models import BridgeProject
from rc_single_span.design.advanced_detailing import (
    ConstructionStageSteelStress,
    DoublyReinforcedSLSResult,
    EndZoneCongestionResult,
    FatigueTrafficStressRangeResult,
    FatigueVehicle,
    LapSpliceZone,
    TerminationCodeProfile,
    TerminationPlan,
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
from rc_single_span.design.project import (
    BS5400DesignInputs,
    BS5400GirderDesignResult,
    EC2DesignInputs,
    EurocodeGirderDesignResult,
    EurocodeSLSBasis,
)
from rc_single_span.design.project_detailing import (
    BS5400DetailingInputs,
    BS5400GirderDetailingResult,
    EC2GirderDetailingResult,
)
from rc_single_span.traffic.combinations import (
    BS5400GirderCombinationResult,
    EurocodeGirderCombinationResult,
)


@dataclass(frozen=True)
class AdvancedStageDInputs:
    support_anchorage_length_m: float
    minimum_support_bars: int
    minimum_extension_beyond_theoretical_cutoff_m: float
    lap_length_m: float
    splice_end_exclusion_m: float
    maximum_splice_fraction: float
    maximum_demand_ratio_for_splicing: float
    fatigue_distribution_factors: tuple[float, ...]
    fatigue_characteristic_resistance_range_mpa: float
    construction_stage_allowable_steel_stress_mpa: float
    bearing_width_mm: float
    bearing_length_mm: float
    allowable_bearing_pressure_mpa: float
    end_zone_width_mm: float
    end_zone_depth_mm: float
    maximum_local_steel_ratio: float
    sls_tension_steel_stress_limit_mpa: float
    sls_compression_steel_stress_limit_mpa: float
    fatigue_step_m: float = 0.25
    maximum_splice_groups: int | None = None
    ec2_cot_theta: float = 2.0
    ec2_cot_alpha: float = 0.0
    bs5400_tension_shift_length_m: float | None = None
    bs5400_fatigue_vehicle: FatigueVehicle | None = None


@dataclass(frozen=True)
class AdvancedGirderDetailingResult:
    girder_index: int
    termination: TerminationPlan | None
    lap_zones: tuple[LapSpliceZone, ...]
    fatigue: FatigueTrafficStressRangeResult | None
    construction_stage_stress: tuple[ConstructionStageSteelStress, ...]
    end_zone: EndZoneCongestionResult | None
    doubly_reinforced_sls: DoublyReinforcedSLSResult | None
    complete: bool
    outstanding: tuple[str, ...]


def _validate_inputs(project: BridgeProject, inputs: AdvancedStageDInputs) -> None:
    if len(inputs.fatigue_distribution_factors) != int(project.geometry.girder_count):
        raise ValueError(
            "fatigue_distribution_factors must contain one factor for every girder."
        )
    if any(not 0.0 < value <= 1.0 for value in inputs.fatigue_distribution_factors):
        raise ValueError("Each fatigue distribution factor must lie in (0, 1].")
    positive = (
        inputs.support_anchorage_length_m,
        inputs.lap_length_m,
        inputs.fatigue_characteristic_resistance_range_mpa,
        inputs.construction_stage_allowable_steel_stress_mpa,
        inputs.bearing_width_mm,
        inputs.bearing_length_mm,
        inputs.allowable_bearing_pressure_mpa,
        inputs.end_zone_width_mm,
        inputs.end_zone_depth_mm,
        inputs.sls_tension_steel_stress_limit_mpa,
        inputs.sls_compression_steel_stress_limit_mpa,
        inputs.fatigue_step_m,
    )
    if any(value <= 0.0 for value in positive):
        raise ValueError("Advanced Stage D positive inputs must be greater than zero.")


def _selected_tension_cage(detail):
    if detail.doubly_reinforced_cage_selection is not None:
        return (
            detail.doubly_reinforced_cage_selection.tension,
            detail.doubly_reinforced_cage_selection.actual_effective_depth_m,
        )
    if detail.selected_longitudinal is not None:
        return detail.selected_longitudinal, None
    return None, None


def _termination(
    *,
    project: BridgeProject,
    detail,
    code_profile: TerminationCodeProfile,
    inputs: AdvancedStageDInputs,
    lever_arm_m: float | None,
) -> TerminationPlan | None:
    if detail.curtailment_plan is None:
        return None
    rules = build_termination_rules(
        code_profile=code_profile,
        support_anchorage_length_m=inputs.support_anchorage_length_m,
        minimum_support_bars=inputs.minimum_support_bars,
        minimum_extension_beyond_theoretical_cutoff_m=(
            inputs.minimum_extension_beyond_theoretical_cutoff_m
        ),
        lever_arm_m=lever_arm_m,
        cot_theta=inputs.ec2_cot_theta if code_profile is TerminationCodeProfile.EUROCODE else None,
        cot_alpha=inputs.ec2_cot_alpha,
        explicit_tension_shift_length_m=(
            inputs.bs5400_tension_shift_length_m
            if code_profile is TerminationCodeProfile.BS5400
            else None
        ),
    )
    return apply_support_and_termination_rules(
        span_m=float(project.geometry.span_m),
        preliminary=detail.curtailment_plan,
        rules=rules,
    )


def run_eurocode_advanced_stage_d(
    project: BridgeProject,
    combinations: tuple[EurocodeGirderCombinationResult, ...],
    designs: tuple[EurocodeGirderDesignResult, ...],
    details: tuple[EC2GirderDetailingResult, ...],
    *,
    design_inputs: EC2DesignInputs,
    inputs: AdvancedStageDInputs,
) -> tuple[AdvancedGirderDetailingResult, ...]:
    _validate_inputs(project, inputs)
    if not (len(combinations) == len(designs) == len(details)):
        raise ValueError("Eurocode Stage D inputs are inconsistent.")

    results = []
    for combo, design, detail in zip(combinations, designs, details, strict=True):
        if not (
            combo.girder_index == design.girder_index == detail.girder_index
        ):
            raise ValueError("Eurocode Stage D girder ordering is inconsistent.")
        index = detail.girder_index
        outstanding: list[str] = []

        lever_arm = None
        if design.flexure is not None:
            lever_arm = design.flexure.lever_arm_m
        elif detail.doubly_reinforced_cage_selection is not None:
            lever_arm = (
                detail.doubly_reinforced_cage_selection.actual_effective_depth_m
                - detail.doubly_reinforced_cage_selection.actual_compression_depth_m
            )

        termination = None
        try:
            termination = _termination(
                project=project,
                detail=detail,
                code_profile=TerminationCodeProfile.EUROCODE,
                inputs=inputs,
                lever_arm_m=lever_arm,
            )
        except ValueError as exc:
            outstanding.append(f"termination: {exc}")

        laps: tuple[LapSpliceZone, ...] = ()
        if termination is not None:
            laps = build_lap_splice_zones(
                span_m=float(project.geometry.span_m),
                termination=termination,
                lap_length_m=inputs.lap_length_m,
                end_exclusion_m=inputs.splice_end_exclusion_m,
                maximum_splice_fraction=inputs.maximum_splice_fraction,
                maximum_demand_ratio_for_splicing=(
                    inputs.maximum_demand_ratio_for_splicing
                ),
            )
            if not any(item.permitted for item in laps):
                outstanding.append("lap/splice zoning: no permitted low-demand zone")

        tension, selected_depth = _selected_tension_cage(detail)
        fatigue = None
        construction: tuple[ConstructionStageSteelStress, ...] = ()
        end_zone = None
        doubly_sls = None
        if tension is None:
            outstanding.append("no selected tension cage")
        else:
            depth = (
                selected_depth
                if selected_depth is not None
                else (
                    detail.longitudinal_synthesis.selected.effective_depth_m
                    if detail.longitudinal_synthesis is not None
                    and detail.longitudinal_synthesis.selected is not None
                    else design_inputs.effective_depth_m
                )
            )
            layers = __import__(
                "rc_single_span.analysis.sections",
                fromlist=["final_composite_concrete_layers"],
            ).final_composite_concrete_layers(project.geometry, girder_index=index)
            station = (
                detail.reinforcement_envelope.maximum_required_station_m
                if detail.reinforcement_envelope is not None
                and detail.reinforcement_envelope.maximum_required_station_m is not None
                else float(project.geometry.span_m) / 2.0
            )
            try:
                fatigue = fatigue_vehicle_to_steel_stress_range(
                    span_m=float(project.geometry.span_m),
                    station_m=station,
                    vehicle=eurocode_flm3_vehicle(),
                    girder_distribution_factor=inputs.fatigue_distribution_factors[index - 1],
                    layers=layers,
                    tension_steel_area_mm2=tension.provided_area_mm2,
                    tension_steel_depth_m=depth,
                    es_mpa=design_inputs.es_mpa,
                    ecm_mpa=float(
                        design_inputs.ecm_mpa
                        if design_inputs.ecm_mpa is not None
                        else project.materials.elastic_modulus_mpa
                    ),
                    characteristic_resistance_range_mpa=(
                        inputs.fatigue_characteristic_resistance_range_mpa
                    ),
                    step_m=inputs.fatigue_step_m,
                )
                if not fatigue.fatigue_check.passes:
                    outstanding.append("fatigue stress-range check fails")
            except (TypeError, ValueError) as exc:
                outstanding.append(f"fatigue: {exc}")

            try:
                construction = construction_stage_reinforcement_stress_checks(
                    project,
                    girder_index=index,
                    arrangement=tension,
                    cover_mm=detail.cover_check.provided_cover_mm,
                    link_diameter_mm=detail.selected_links.link_diameter_mm,
                    es_mpa=design_inputs.es_mpa,
                    ecm_mpa=float(
                        design_inputs.ecm_mpa
                        if design_inputs.ecm_mpa is not None
                        else project.materials.elastic_modulus_mpa
                    ),
                    allowable_stress_mpa=(
                        inputs.construction_stage_allowable_steel_stress_mpa
                    ),
                )
                if not all(item.passes for item in construction):
                    outstanding.append("construction-stage steel stress check fails")
            except (TypeError, ValueError) as exc:
                outstanding.append(f"construction stage: {exc}")

            try:
                end_zone = check_local_bearing_end_zone_congestion(
                    support_reaction_kn=design.shear.design_shear_kn,
                    bearing_width_mm=inputs.bearing_width_mm,
                    bearing_length_mm=inputs.bearing_length_mm,
                    allowable_bearing_pressure_mpa=inputs.allowable_bearing_pressure_mpa,
                    end_zone_width_mm=inputs.end_zone_width_mm,
                    end_zone_depth_mm=inputs.end_zone_depth_mm,
                    longitudinal_bar_count=tension.bar_count,
                    longitudinal_bar_diameter_mm=tension.bar_diameter_mm,
                    cover_mm=detail.cover_check.provided_cover_mm,
                    link_diameter_mm=detail.selected_links.link_diameter_mm,
                    link_spacing_mm=detail.selected_links.spacing_mm,
                    maximum_link_spacing_mm=(
                        detail.shear_limits.maximum_longitudinal_link_spacing_mm
                    ),
                    minimum_clear_spacing_mm=max(
                        20.0,
                        detail.selected_longitudinal.clear_horizontal_spacing_mm
                        if detail.selected_longitudinal is not None
                        else 20.0,
                    ),
                    maximum_local_steel_ratio=inputs.maximum_local_steel_ratio,
                )
                if not end_zone.passes:
                    outstanding.append("local bearing/end-zone congestion check fails")
            except ValueError as exc:
                outstanding.append(f"end zone: {exc}")

        if detail.doubly_reinforced_cage_selection is not None:
            selected = detail.doubly_reinforced_cage_selection
            if design_inputs.sls_basis is EurocodeSLSBasis.CHARACTERISTIC:
                service_moment = combo.combinations.characteristic_sls.effects.moment_knm
            elif design_inputs.sls_basis is EurocodeSLSBasis.FREQUENT:
                service_moment = combo.combinations.frequent_sls.effects.moment_knm
            else:
                service_moment = combo.combinations.quasi_permanent_sls.effects.moment_knm
            ecm = (
                design_inputs.ecm_mpa
                if design_inputs.ecm_mpa is not None
                else project.materials.elastic_modulus_mpa
            )
            try:
                doubly_sls = check_doubly_reinforced_sls_ec2(
                    layers=__import__(
                        "rc_single_span.analysis.sections",
                        fromlist=["final_composite_concrete_layers"],
                    ).final_composite_concrete_layers(project.geometry, girder_index=index),
                    total_depth_m=project.geometry.total_structural_depth_m,
                    service_moment_knm=service_moment,
                    tension=selected.tension,
                    compression=selected.compression,
                    tension_depth_m=selected.actual_effective_depth_m,
                    compression_depth_m=selected.actual_compression_depth_m,
                    cover_mm=detail.cover_check.provided_cover_mm,
                    es_mpa=design_inputs.es_mpa,
                    ecm_mpa=float(ecm),
                    fct_eff_mpa=design_inputs.fct_eff_mpa,
                    crack_limit_mm=design_inputs.crack_limit_mm,
                    tension_stress_limit_mpa=inputs.sls_tension_steel_stress_limit_mpa,
                    compression_stress_limit_mpa=inputs.sls_compression_steel_stress_limit_mpa,
                )
                if not doubly_sls.passes:
                    outstanding.append("doubly reinforced SLS check fails")
            except (TypeError, ValueError) as exc:
                outstanding.append(f"doubly reinforced SLS: {exc}")

        results.append(
            AdvancedGirderDetailingResult(
                girder_index=index,
                termination=termination,
                lap_zones=laps,
                fatigue=fatigue,
                construction_stage_stress=construction,
                end_zone=end_zone,
                doubly_reinforced_sls=doubly_sls,
                complete=not outstanding,
                outstanding=tuple(outstanding),
            )
        )
    return tuple(results)


def run_bs5400_advanced_stage_d(
    project: BridgeProject,
    combinations: tuple[BS5400GirderCombinationResult, ...],
    designs: tuple[BS5400GirderDesignResult, ...],
    details: tuple[BS5400GirderDetailingResult, ...],
    *,
    design_inputs: BS5400DesignInputs,
    detailing_inputs: BS5400DetailingInputs,
    inputs: AdvancedStageDInputs,
) -> tuple[AdvancedGirderDetailingResult, ...]:
    _validate_inputs(project, inputs)
    if inputs.bs5400_fatigue_vehicle is None:
        raise ValueError(
            "BS 5400 advanced Stage D requires an explicit verified fatigue vehicle/model."
        )
    if inputs.bs5400_tension_shift_length_m is None:
        raise ValueError(
            "BS 5400 advanced Stage D requires an explicit verified tension-shift length."
        )
    if not (len(combinations) == len(designs) == len(details)):
        raise ValueError("BS 5400 Stage D inputs are inconsistent.")

    results = []
    for combo, design, detail in zip(combinations, designs, details, strict=True):
        index = detail.girder_index
        outstanding: list[str] = []
        termination = None
        try:
            termination = _termination(
                project=project,
                detail=detail,
                code_profile=TerminationCodeProfile.BS5400,
                inputs=inputs,
                lever_arm_m=None,
            )
        except ValueError as exc:
            outstanding.append(f"termination: {exc}")
        laps = (
            build_lap_splice_zones(
                span_m=float(project.geometry.span_m),
                termination=termination,
                lap_length_m=inputs.lap_length_m,
                end_exclusion_m=inputs.splice_end_exclusion_m,
                maximum_splice_fraction=inputs.maximum_splice_fraction,
                maximum_demand_ratio_for_splicing=(
                    inputs.maximum_demand_ratio_for_splicing
                ),
            )
            if termination is not None
            else ()
        )
        if laps and not any(item.permitted for item in laps):
            outstanding.append("lap/splice zoning: no permitted low-demand zone")

        tension, selected_depth = _selected_tension_cage(detail)
        fatigue = None
        construction: tuple[ConstructionStageSteelStress, ...] = ()
        end_zone = None
        doubly_sls = None
        if tension is None:
            outstanding.append("no selected tension cage")
        else:
            depth = (
                selected_depth
                if selected_depth is not None
                else (
                    detail.longitudinal_synthesis.selected.effective_depth_m
                    if detail.longitudinal_synthesis is not None
                    and detail.longitudinal_synthesis.selected is not None
                    else design_inputs.effective_depth_m
                )
            )
            from rc_single_span.analysis.sections import final_composite_concrete_layers

            layers = final_composite_concrete_layers(
                project.geometry,
                girder_index=index,
            )
            station = (
                detail.reinforcement_envelope.maximum_required_station_m
                if detail.reinforcement_envelope is not None
                and detail.reinforcement_envelope.maximum_required_station_m is not None
                else float(project.geometry.span_m) / 2.0
            )
            try:
                fatigue = fatigue_vehicle_to_steel_stress_range(
                    span_m=float(project.geometry.span_m),
                    station_m=station,
                    vehicle=inputs.bs5400_fatigue_vehicle,
                    girder_distribution_factor=inputs.fatigue_distribution_factors[index - 1],
                    layers=layers,
                    tension_steel_area_mm2=tension.provided_area_mm2,
                    tension_steel_depth_m=depth,
                    es_mpa=design_inputs.es_mpa,
                    ecm_mpa=design_inputs.ec_modified_mpa,
                    characteristic_resistance_range_mpa=(
                        inputs.fatigue_characteristic_resistance_range_mpa
                    ),
                    step_m=inputs.fatigue_step_m,
                )
                if not fatigue.fatigue_check.passes:
                    outstanding.append("fatigue stress-range check fails")
            except ValueError as exc:
                outstanding.append(f"fatigue: {exc}")
            try:
                construction = construction_stage_reinforcement_stress_checks(
                    project,
                    girder_index=index,
                    arrangement=tension,
                    cover_mm=detailing_inputs.provided_cover_mm,
                    link_diameter_mm=detail.selected_links.link_diameter_mm,
                    es_mpa=design_inputs.es_mpa,
                    ecm_mpa=design_inputs.ec_modified_mpa,
                    allowable_stress_mpa=(
                        inputs.construction_stage_allowable_steel_stress_mpa
                    ),
                )
                if not all(item.passes for item in construction):
                    outstanding.append("construction-stage steel stress check fails")
            except ValueError as exc:
                outstanding.append(f"construction stage: {exc}")
            try:
                end_zone = check_local_bearing_end_zone_congestion(
                    support_reaction_kn=design.shear.design_shear_kn,
                    bearing_width_mm=inputs.bearing_width_mm,
                    bearing_length_mm=inputs.bearing_length_mm,
                    allowable_bearing_pressure_mpa=inputs.allowable_bearing_pressure_mpa,
                    end_zone_width_mm=inputs.end_zone_width_mm,
                    end_zone_depth_mm=inputs.end_zone_depth_mm,
                    longitudinal_bar_count=tension.bar_count,
                    longitudinal_bar_diameter_mm=tension.bar_diameter_mm,
                    cover_mm=detailing_inputs.provided_cover_mm,
                    link_diameter_mm=detail.selected_links.link_diameter_mm,
                    link_spacing_mm=detail.selected_links.spacing_mm,
                    maximum_link_spacing_mm=detail.limits.maximum_link_spacing_mm,
                    minimum_clear_spacing_mm=detail.limits.minimum_clear_bar_spacing_mm,
                    maximum_local_steel_ratio=inputs.maximum_local_steel_ratio,
                )
                if not end_zone.passes:
                    outstanding.append("local bearing/end-zone congestion check fails")
            except ValueError as exc:
                outstanding.append(f"end zone: {exc}")

        if detail.doubly_reinforced_cage_selection is not None:
            selected = detail.doubly_reinforced_cage_selection
            sls_cases = tuple(
                case for case in combo.cases if case.limit_state is BS5400LimitState.SLS
            )
            crack_case = max(
                sls_cases,
                key=lambda case: case.result.effects.moment_knm,
            )
            gamma_live = crack_case.result.factors["primary_live"]
            live_moment = crack_case.nominal_traffic.moment_knm * gamma_live
            permanent_moment = max(
                crack_case.result.effects.moment_knm - live_moment,
                0.0,
            )
            from rc_single_span.analysis.sections import final_composite_concrete_layers

            layers = final_composite_concrete_layers(project.geometry, girder_index=index)
            try:
                doubly_sls = check_doubly_reinforced_sls_bs5400(
                    layers=layers,
                    total_depth_m=project.geometry.total_structural_depth_m,
                    permanent_moment_knm=permanent_moment,
                    live_moment_knm=live_moment,
                    tension=selected.tension,
                    compression=selected.compression,
                    tension_depth_m=selected.actual_effective_depth_m,
                    compression_depth_m=selected.actual_compression_depth_m,
                    cover_mm=detailing_inputs.provided_cover_mm,
                    es_mpa=design_inputs.es_mpa,
                    ec_modified_mpa=design_inputs.ec_modified_mpa,
                    tension_zone_width_m=(
                        design_inputs.tension_zone_width_m
                        if design_inputs.tension_zone_width_m is not None
                        else layers[-1].width_m
                    ),
                    crack_point_depth_mm=design_inputs.crack_point_depth_mm,
                    allowable_crack_width_mm=design_inputs.allowable_crack_width_mm,
                    tension_stress_limit_mpa=inputs.sls_tension_steel_stress_limit_mpa,
                    compression_stress_limit_mpa=inputs.sls_compression_steel_stress_limit_mpa,
                )
                if not doubly_sls.passes:
                    outstanding.append("doubly reinforced SLS check fails")
            except ValueError as exc:
                outstanding.append(f"doubly reinforced SLS: {exc}")

        results.append(
            AdvancedGirderDetailingResult(
                girder_index=index,
                termination=termination,
                lap_zones=laps,
                fatigue=fatigue,
                construction_stage_stress=construction,
                end_zone=end_zone,
                doubly_reinforced_sls=doubly_sls,
                complete=not outstanding,
                outstanding=tuple(outstanding),
            )
        )
    return tuple(results)
