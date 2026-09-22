from __future__ import annotations

from dataclasses import dataclass

from rc_single_span.analysis.sections import (
    final_composite_concrete_layers,
    girder_web_width_m,
)
from rc_single_span.core.models import (
    BarLayer,
    BridgeProject,
    LongitudinalReinforcement,
)
from rc_single_span.design.bs5400 import required_steel_area_layered_bs5400
from rc_single_span.design.bs5400_detailing import (
    BS5400DetailingLimits,
    detailing_limits_bs5400,
)
from rc_single_span.design.detailing import (
    LinkArrangement,
    LongitudinalBarArrangement,
    ProvidedCageAudit,
    audit_provided_longitudinal_cage,
    select_vertical_link_arrangement,
)
from rc_single_span.design.eurocode import required_steel_area_layered_ec2
from rc_single_span.design.eurocode_detailing import (
    EC2CoverCheck,
    EC2LongitudinalLimits,
    EC2ShearDetailingLimits,
    longitudinal_limits_ec2,
    nominal_cover_check_ec2,
    shear_detailing_limits_ec2,
)
from rc_single_span.design.project import (
    BS5400DesignInputs,
    BS5400GirderDesignResult,
    EC2DesignInputs,
    EurocodeGirderDesignResult,
    EurocodeSLSBasis,
)
from rc_single_span.design.reinforcement_synthesis import (
    LongitudinalSynthesisResult,
    synthesize_bs5400_longitudinal_reinforcement,
    synthesize_ec2_longitudinal_reinforcement,
)
from rc_single_span.traffic.combinations import (
    BS5400GirderCombinationResult,
    EurocodeGirderCombinationResult,
)


@dataclass(frozen=True)
class EC2DetailingInputs:
    fctm_mpa: float
    aggregate_size_mm: float
    durability_minimum_cover_mm: float
    allowance_for_deviation_mm: float
    provided_cover_mm: float
    available_longitudinal_diameters_mm: tuple[float, ...] = (
        16.0,
        20.0,
        25.0,
        32.0,
        40.0,
    )
    maximum_longitudinal_layers: int = 4
    preferred_vertical_clear_spacing_mm: float | None = None
    available_link_diameters_mm: tuple[float, ...] = (8.0, 10.0, 12.0, 16.0)
    available_link_legs: tuple[int, ...] = (2, 4, 6)
    available_link_spacings_mm: tuple[float, ...] = (
        300.0,
        250.0,
        225.0,
        200.0,
        175.0,
        150.0,
        125.0,
        100.0,
    )
    provided_link_diameter_mm: float | None = None
    provided_vertical_clear_spacing_mm: float | None = None


@dataclass(frozen=True)
class BS5400DetailingInputs:
    aggregate_size_mm: float
    provided_cover_mm: float
    adopted_minimum_main_ratio: float | None = None
    available_longitudinal_diameters_mm: tuple[float, ...] = (
        16.0,
        20.0,
        25.0,
        32.0,
        40.0,
    )
    maximum_longitudinal_layers: int = 4
    preferred_vertical_clear_spacing_mm: float | None = None
    available_link_diameters_mm: tuple[float, ...] = (8.0, 10.0, 12.0, 16.0)
    available_link_legs: tuple[int, ...] = (2, 4, 6)
    available_link_spacings_mm: tuple[float, ...] = (
        300.0,
        250.0,
        225.0,
        200.0,
        175.0,
        150.0,
        125.0,
        100.0,
    )
    maximum_transverse_leg_spacing_mm: float | None = None
    provided_link_diameter_mm: float | None = None
    provided_link_spacing_mm: float | None = None
    provided_vertical_clear_spacing_mm: float | None = None
    provided_side_face_steel_each_face_mm2: float | None = None


@dataclass(frozen=True)
class EC2GirderDetailingResult:
    girder_index: int
    required_flexural_steel_mm2: float | None
    required_flexural_steel_issue: str | None
    longitudinal_limits: EC2LongitudinalLimits
    governing_required_longitudinal_steel_mm2: float | None
    selected_longitudinal: LongitudinalBarArrangement | None
    selected_links: LinkArrangement
    recommended_cage_audit: ProvidedCageAudit | None
    provided_cage_audit: ProvidedCageAudit | None
    provided_longitudinal_area_mm2: float | None
    provided_above_minimum: bool | None
    provided_below_maximum: bool | None
    selected_below_maximum: bool | None
    shear_limits: EC2ShearDetailingLimits
    cover_check: EC2CoverCheck
    longitudinal_synthesis: LongitudinalSynthesisResult | None


@dataclass(frozen=True)
class BS5400GirderDetailingResult:
    girder_index: int
    required_flexural_steel_mm2: float | None
    required_flexural_steel_issue: str | None
    limits: BS5400DetailingLimits
    governing_required_longitudinal_steel_mm2: float | None
    selected_longitudinal: LongitudinalBarArrangement | None
    selected_links: LinkArrangement
    recommended_cage_audit: ProvidedCageAudit | None
    provided_cage_audit: ProvidedCageAudit | None
    provided_longitudinal_area_mm2: float | None
    provided_above_minimum: bool | None
    provided_below_maximum: bool | None
    selected_below_maximum: bool | None
    selected_tension_spacing_ok: bool | None
    provided_tension_spacing_ok: bool | None
    provided_link_spacing_ok: bool | None
    side_face_steel_ok: bool | None
    longitudinal_synthesis: LongitudinalSynthesisResult | None


def _concrete_area_m2(project: BridgeProject, girder_index: int) -> float:
    return sum(
        layer.area_m2
        for layer in final_composite_concrete_layers(
            project.geometry,
            girder_index=girder_index,
        )
    )


def _provided_area(project: BridgeProject) -> float | None:
    reinforcement = project.provided_longitudinal_reinforcement
    return None if reinforcement is None else reinforcement.total_area_mm2


def _recommended_reinforcement(
    arrangement: LongitudinalBarArrangement,
) -> LongitudinalReinforcement:
    return LongitudinalReinforcement(
        layers=[
            BarLayer(
                count=count,
                diameter_mm=arrangement.bar_diameter_mm,
            )
            for count in arrangement.bars_per_layer
        ]
    )


def run_eurocode_project_detailing(
    project: BridgeProject,
    combinations: tuple[EurocodeGirderCombinationResult, ...],
    design_results: tuple[EurocodeGirderDesignResult, ...],
    *,
    design_inputs: EC2DesignInputs,
    detailing_inputs: EC2DetailingInputs,
) -> tuple[EC2GirderDetailingResult, ...]:
    if len(combinations) != len(design_results):
        raise ValueError("Eurocode combinations and design results are inconsistent.")
    if detailing_inputs.aggregate_size_mm <= 0.0:
        raise ValueError("aggregate_size_mm must be positive.")

    fck = float(project.materials.fck_mpa)
    fyk = float(project.materials.fyk_mpa)
    web_width_m = girder_web_width_m(project.geometry)
    web_width_mm = web_width_m * 1000.0
    provided_area = _provided_area(project)
    results: list[EC2GirderDetailingResult] = []

    for combination, design in zip(combinations, design_results, strict=True):
        if combination.girder_index != design.girder_index:
            raise ValueError("Eurocode girder ordering is inconsistent.")
        index = design.girder_index
        layers = final_composite_concrete_layers(
            project.geometry,
            girder_index=index,
        )
        concrete_area = _concrete_area_m2(project, index)
        tension_width = layers[-1].width_m
        longitudinal_limits = longitudinal_limits_ec2(
            fctm_mpa=detailing_inputs.fctm_mpa,
            fyk_mpa=fyk,
            tension_zone_width_m=tension_width,
            effective_depth_m=design_inputs.effective_depth_m,
            concrete_area_m2=concrete_area,
        )
        shear_limits = shear_detailing_limits_ec2(
            fck_mpa=fck,
            fyk_mpa=fyk,
            web_width_m=web_width_m,
            effective_depth_m=design_inputs.effective_depth_m,
        )

        required_issue: str | None = None
        try:
            required_flexural = required_steel_area_layered_ec2(
                med_knm=combination.combinations.persistent_uls.effects.moment_knm,
                layers=layers,
                effective_depth_m=design_inputs.effective_depth_m,
                fck_mpa=fck,
                fyk_mpa=fyk,
                maximum_neutral_axis_ratio=design_inputs.maximum_neutral_axis_ratio,
            )
        except ValueError as exc:
            required_flexural = None
            required_issue = str(exc)

        required_asw = max(
            shear_limits.minimum_asw_per_s_mm2_per_m,
            design.shear.required_asw_per_s_mm2_per_m,
        )
        selected_links = select_vertical_link_arrangement(
            required_asw_per_s_mm2_per_m=required_asw,
            web_width_mm=web_width_mm,
            maximum_longitudinal_spacing_mm=(
                shear_limits.maximum_longitudinal_link_spacing_mm
            ),
            maximum_transverse_leg_spacing_mm=(
                shear_limits.maximum_transverse_leg_spacing_mm
            ),
            cover_mm=detailing_inputs.provided_cover_mm,
            available_diameters_mm=detailing_inputs.available_link_diameters_mm,
            available_legs=detailing_inputs.available_link_legs,
            available_spacings_mm=detailing_inputs.available_link_spacings_mm,
        )

        selected_longitudinal: LongitudinalBarArrangement | None = None
        recommended_cage: ProvidedCageAudit | None = None
        governing_required: float | None = None
        selected_below_maximum: bool | None = None
        longitudinal_synthesis: LongitudinalSynthesisResult | None = None
        if required_flexural is not None:
            governing_required = max(
                required_flexural,
                longitudinal_limits.minimum_tension_steel_mm2,
            )
            clear_base = max(
                20.0,
                detailing_inputs.aggregate_size_mm + 5.0,
            )
            if design_inputs.sls_basis is EurocodeSLSBasis.CHARACTERISTIC:
                sls_moment = (
                    combination.combinations.characteristic_sls.effects.moment_knm
                )
            elif design_inputs.sls_basis is EurocodeSLSBasis.FREQUENT:
                sls_moment = combination.combinations.frequent_sls.effects.moment_knm
            else:
                sls_moment = (
                    combination.combinations.quasi_permanent_sls.effects.moment_knm
                )
            ecm = (
                float(design_inputs.ecm_mpa)
                if design_inputs.ecm_mpa is not None
                else project.materials.elastic_modulus_mpa
            )
            if ecm is None or ecm <= 0.0:
                raise ValueError(
                    "EC2 reinforcement synthesis requires explicit concrete modulus."
                )
            longitudinal_synthesis = synthesize_ec2_longitudinal_reinforcement(
                layers=layers,
                total_depth_m=project.geometry.total_structural_depth_m,
                uls_moment_knm=(
                    combination.combinations.persistent_uls.effects.moment_knm
                ),
                sls_moment_knm=sls_moment,
                required_uls_area_mm2=required_flexural,
                minimum_area_mm2=longitudinal_limits.minimum_tension_steel_mm2,
                maximum_area_mm2=longitudinal_limits.maximum_longitudinal_steel_mm2,
                fck_mpa=fck,
                fyk_mpa=fyk,
                maximum_neutral_axis_ratio=(
                    design_inputs.maximum_neutral_axis_ratio
                ),
                cover_mm=detailing_inputs.provided_cover_mm,
                link_diameter_mm=selected_links.link_diameter_mm,
                web_width_mm=web_width_mm,
                minimum_clear_spacing_mm=clear_base,
                available_diameters_mm=(
                    detailing_inputs.available_longitudinal_diameters_mm
                ),
                maximum_layers=detailing_inputs.maximum_longitudinal_layers,
                preferred_vertical_clear_spacing_mm=(
                    detailing_inputs.preferred_vertical_clear_spacing_mm
                ),
                es_mpa=design_inputs.es_mpa,
                ecm_mpa=float(ecm),
                fct_eff_mpa=design_inputs.fct_eff_mpa,
                crack_limit_mm=design_inputs.crack_limit_mm,
                deflection_passes=design.deflection.passes,
            )
            if longitudinal_synthesis.selected is not None:
                selected_longitudinal = longitudinal_synthesis.selected.arrangement
                selected_below_maximum = (
                    longitudinal_synthesis.selected.maximum_steel_passes
                )
                recommended_cage = audit_provided_longitudinal_cage(
                    reinforcement=_recommended_reinforcement(selected_longitudinal),
                    web_width_mm=web_width_mm,
                    cover_mm=detailing_inputs.provided_cover_mm,
                    link_diameter_mm=selected_links.link_diameter_mm,
                    minimum_clear_spacing_mm=clear_base,
                    section_total_depth_mm=(
                        project.geometry.total_structural_depth_m * 1000.0
                    ),
                    provided_vertical_clear_spacing_mm=(
                        selected_longitudinal.clear_vertical_spacing_mm
                    ),
                    diameter_governs_clear_spacing=True,
                )

        provided_above_minimum = (
            None
            if provided_area is None
            else provided_area + 1.0e-9
            >= longitudinal_limits.minimum_tension_steel_mm2
        )
        provided_below_maximum = (
            None
            if provided_area is None
            else provided_area
            <= longitudinal_limits.maximum_longitudinal_steel_mm2 + 1.0e-9
        )
        provided_cage: ProvidedCageAudit | None = None
        if (
            project.provided_longitudinal_reinforcement is not None
            and detailing_inputs.provided_link_diameter_mm is not None
        ):
            provided_cage = audit_provided_longitudinal_cage(
                reinforcement=project.provided_longitudinal_reinforcement,
                web_width_mm=web_width_mm,
                cover_mm=detailing_inputs.provided_cover_mm,
                link_diameter_mm=detailing_inputs.provided_link_diameter_mm,
                minimum_clear_spacing_mm=max(
                    20.0,
                    detailing_inputs.aggregate_size_mm + 5.0,
                ),
                section_total_depth_mm=(
                    project.geometry.total_structural_depth_m * 1000.0
                ),
                provided_vertical_clear_spacing_mm=(
                    detailing_inputs.provided_vertical_clear_spacing_mm
                ),
                diameter_governs_clear_spacing=True,
            )

        cover_bar_diameter = (
            max(
                float(layer.diameter_mm)
                for layer in project.provided_longitudinal_reinforcement.layers
            )
            if project.provided_longitudinal_reinforcement is not None
            else (
                selected_longitudinal.bar_diameter_mm
                if selected_longitudinal is not None
                else design_inputs.bar_diameter_mm
            )
        )
        cover_check = nominal_cover_check_ec2(
            bar_diameter_mm=cover_bar_diameter,
            durability_minimum_cover_mm=(
                detailing_inputs.durability_minimum_cover_mm
            ),
            allowance_for_deviation_mm=(
                detailing_inputs.allowance_for_deviation_mm
            ),
            provided_cover_mm=detailing_inputs.provided_cover_mm,
        )

        results.append(
            EC2GirderDetailingResult(
                girder_index=index,
                required_flexural_steel_mm2=required_flexural,
                required_flexural_steel_issue=required_issue,
                longitudinal_limits=longitudinal_limits,
                governing_required_longitudinal_steel_mm2=governing_required,
                selected_longitudinal=selected_longitudinal,
                selected_links=selected_links,
                recommended_cage_audit=recommended_cage,
                provided_cage_audit=provided_cage,
                provided_longitudinal_area_mm2=provided_area,
                provided_above_minimum=provided_above_minimum,
                provided_below_maximum=provided_below_maximum,
                selected_below_maximum=selected_below_maximum,
                shear_limits=shear_limits,
                cover_check=cover_check,
                longitudinal_synthesis=longitudinal_synthesis,
            )
        )
    return tuple(results)


def run_bs5400_project_detailing(
    project: BridgeProject,
    combinations: tuple[BS5400GirderCombinationResult, ...],
    design_results: tuple[BS5400GirderDesignResult, ...],
    *,
    design_inputs: BS5400DesignInputs,
    detailing_inputs: BS5400DetailingInputs,
) -> tuple[BS5400GirderDetailingResult, ...]:
    if len(combinations) != len(design_results):
        raise ValueError("BS 5400 combinations and design results are inconsistent.")
    if detailing_inputs.aggregate_size_mm <= 0.0:
        raise ValueError("aggregate_size_mm must be positive.")

    fcu = float(project.materials.fcu_mpa)
    fy = float(project.materials.fyk_mpa)
    web_width_m = girder_web_width_m(project.geometry)
    web_width_mm = web_width_m * 1000.0
    provided_area = _provided_area(project)
    results: list[BS5400GirderDetailingResult] = []

    for combination, design in zip(combinations, design_results, strict=True):
        if combination.girder_index != design.girder_index:
            raise ValueError("BS 5400 girder ordering is inconsistent.")
        index = design.girder_index
        layers = final_composite_concrete_layers(
            project.geometry,
            girder_index=index,
        )
        concrete_area = _concrete_area_m2(project, index)
        limits = detailing_limits_bs5400(
            average_breadth_excluding_compression_flange_m=web_width_m,
            effective_depth_m=design_inputs.effective_depth_m,
            gross_concrete_area_m2=concrete_area,
            reinforcement_grade_mpa=fy,
            side_face_depth_m=float(project.geometry.girder_profile.total_depth_m),
            side_face_breadth_m=web_width_m,
            maximum_aggregate_size_mm=detailing_inputs.aggregate_size_mm,
            adopted_minimum_main_ratio=(
                detailing_inputs.adopted_minimum_main_ratio
            ),
        )

        uls_cases = tuple(
            case
            for case in combination.cases
            if case.limit_state.value == "uls"
        )
        governing_moment = max(
            case.result.effects.moment_knm
            for case in uls_cases
        )
        required_issue: str | None = None
        try:
            required_flexural = required_steel_area_layered_bs5400(
                med_knm=governing_moment,
                layers=layers,
                effective_depth_m=design_inputs.effective_depth_m,
                fcu_mpa=fcu,
                fy_mpa=fy,
            )
        except ValueError as exc:
            required_flexural = None
            required_issue = str(exc)

        selected_links = select_vertical_link_arrangement(
            required_asw_per_s_mm2_per_m=(
                design.shear.governing_asv_per_s_mm2_per_m
            ),
            web_width_mm=web_width_mm,
            maximum_longitudinal_spacing_mm=limits.maximum_link_spacing_mm,
            maximum_transverse_leg_spacing_mm=(
                detailing_inputs.maximum_transverse_leg_spacing_mm
            ),
            cover_mm=detailing_inputs.provided_cover_mm,
            available_diameters_mm=detailing_inputs.available_link_diameters_mm,
            available_legs=detailing_inputs.available_link_legs,
            available_spacings_mm=detailing_inputs.available_link_spacings_mm,
        )

        selected_longitudinal: LongitudinalBarArrangement | None = None
        recommended_cage: ProvidedCageAudit | None = None
        governing_required: float | None = None
        selected_below_maximum: bool | None = None
        selected_tension_spacing_ok: bool | None = None
        longitudinal_synthesis: LongitudinalSynthesisResult | None = None
        if required_flexural is not None:
            governing_required = max(
                required_flexural,
                limits.minimum_main_steel_mm2,
            )
            sls_cases = tuple(
                case
                for case in combination.cases
                if case.limit_state.value == "sls"
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
            tension_width = (
                design_inputs.tension_zone_width_m
                if design_inputs.tension_zone_width_m is not None
                else layers[-1].width_m
            )
            longitudinal_synthesis = synthesize_bs5400_longitudinal_reinforcement(
                layers=layers,
                total_depth_m=project.geometry.total_structural_depth_m,
                uls_moment_knm=governing_moment,
                permanent_sls_moment_knm=permanent_moment,
                live_sls_moment_knm=live_moment,
                required_uls_area_mm2=required_flexural,
                minimum_area_mm2=limits.minimum_main_steel_mm2,
                maximum_area_mm2=limits.maximum_main_steel_mm2,
                fcu_mpa=fcu,
                fy_mpa=fy,
                cover_mm=detailing_inputs.provided_cover_mm,
                link_diameter_mm=selected_links.link_diameter_mm,
                web_width_mm=web_width_mm,
                minimum_clear_spacing_mm=limits.minimum_clear_bar_spacing_mm,
                maximum_tension_bar_spacing_mm=(
                    limits.maximum_tension_bar_spacing_mm
                ),
                available_diameters_mm=(
                    detailing_inputs.available_longitudinal_diameters_mm
                ),
                maximum_layers=detailing_inputs.maximum_longitudinal_layers,
                preferred_vertical_clear_spacing_mm=(
                    detailing_inputs.preferred_vertical_clear_spacing_mm
                ),
                es_mpa=design_inputs.es_mpa,
                ec_modified_mpa=design_inputs.ec_modified_mpa,
                tension_zone_width_m=tension_width,
                crack_point_depth_mm=design_inputs.crack_point_depth_mm,
                allowable_crack_width_mm=(
                    design_inputs.allowable_crack_width_mm
                ),
                deflection_passes=design.deflection.passes,
            )
            if longitudinal_synthesis.selected is not None:
                selected_longitudinal = longitudinal_synthesis.selected.arrangement
                selected_below_maximum = (
                    longitudinal_synthesis.selected.maximum_steel_passes
                )
                selected_tension_spacing_ok = (
                    selected_longitudinal.bar_diameter_mm
                    + selected_longitudinal.clear_horizontal_spacing_mm
                    <= limits.maximum_tension_bar_spacing_mm + 1.0e-9
                )
                recommended_cage = audit_provided_longitudinal_cage(
                    reinforcement=_recommended_reinforcement(selected_longitudinal),
                    web_width_mm=web_width_mm,
                    cover_mm=detailing_inputs.provided_cover_mm,
                    link_diameter_mm=selected_links.link_diameter_mm,
                    minimum_clear_spacing_mm=limits.minimum_clear_bar_spacing_mm,
                    section_total_depth_mm=(
                        project.geometry.total_structural_depth_m * 1000.0
                    ),
                    provided_vertical_clear_spacing_mm=(
                        selected_longitudinal.clear_vertical_spacing_mm
                    ),
                    diameter_governs_clear_spacing=False,
                )

        provided_above_minimum = (
            None
            if provided_area is None
            else provided_area + 1.0e-9 >= limits.minimum_main_steel_mm2
        )
        provided_below_maximum = (
            None
            if provided_area is None
            else provided_area <= limits.maximum_main_steel_mm2 + 1.0e-9
        )

        provided_cage: ProvidedCageAudit | None = None
        provided_tension_spacing_ok: bool | None = None
        if (
            project.provided_longitudinal_reinforcement is not None
            and detailing_inputs.provided_link_diameter_mm is not None
        ):
            provided_cage = audit_provided_longitudinal_cage(
                reinforcement=project.provided_longitudinal_reinforcement,
                web_width_mm=web_width_mm,
                cover_mm=detailing_inputs.provided_cover_mm,
                link_diameter_mm=detailing_inputs.provided_link_diameter_mm,
                minimum_clear_spacing_mm=limits.minimum_clear_bar_spacing_mm,
                section_total_depth_mm=(
                    project.geometry.total_structural_depth_m * 1000.0
                ),
                provided_vertical_clear_spacing_mm=(
                    detailing_inputs.provided_vertical_clear_spacing_mm
                ),
                diameter_governs_clear_spacing=False,
            )
            provided_tension_spacing_ok = all(
                check.bar_diameter_mm + check.clear_horizontal_spacing_mm
                <= limits.maximum_tension_bar_spacing_mm + 1.0e-9
                for check in provided_cage.layer_checks
            )

        provided_link_spacing_ok = (
            None
            if detailing_inputs.provided_link_spacing_mm is None
            else detailing_inputs.provided_link_spacing_mm
            <= limits.maximum_link_spacing_mm + 1.0e-9
        )
        side_face_ok = (
            None
            if detailing_inputs.provided_side_face_steel_each_face_mm2 is None
            else detailing_inputs.provided_side_face_steel_each_face_mm2 + 1.0e-9
            >= limits.minimum_side_face_steel_each_face_mm2
        )

        results.append(
            BS5400GirderDetailingResult(
                girder_index=index,
                required_flexural_steel_mm2=required_flexural,
                required_flexural_steel_issue=required_issue,
                limits=limits,
                governing_required_longitudinal_steel_mm2=governing_required,
                selected_longitudinal=selected_longitudinal,
                selected_links=selected_links,
                recommended_cage_audit=recommended_cage,
                provided_cage_audit=provided_cage,
                provided_longitudinal_area_mm2=provided_area,
                provided_above_minimum=provided_above_minimum,
                provided_below_maximum=provided_below_maximum,
                selected_below_maximum=selected_below_maximum,
                selected_tension_spacing_ok=selected_tension_spacing_ok,
                provided_tension_spacing_ok=provided_tension_spacing_ok,
                provided_link_spacing_ok=provided_link_spacing_ok,
                side_face_steel_ok=side_face_ok,
                longitudinal_synthesis=longitudinal_synthesis,
            )
        )
    return tuple(results)
