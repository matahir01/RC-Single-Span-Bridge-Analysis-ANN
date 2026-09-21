from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rc_single_span.analysis.construction import (
    factored_permanent_deflection_at_x_mm,
)
from rc_single_span.analysis.permanent import PermanentLoadCategory
from rc_single_span.analysis.sections import (
    final_composite_concrete_layers,
    girder_web_width_m,
)
from rc_single_span.codes.bs5400.combinations import (
    BS5400LimitState,
    BS5400PermanentGammaFL,
    BS5400PrimaryTraffic,
)
from rc_single_span.codes.common import FactoredCombination
from rc_single_span.core.models import BridgeProject, DesignStandard
from rc_single_span.design.bs5400 import (
    BS5400CrackWidthResult,
    BS5400FlexureResult,
    BS5400ShearResult,
    check_crack_width_bs5400,
    check_layered_flexure_bs5400,
    check_shear_bs5400,
)
from rc_single_span.design.eurocode import (
    EC2CrackWidthResult,
    EC2FlexureResult,
    EC2ShearResult,
    check_crack_width_ec2,
    check_layered_flexure_ec2,
    check_shear_ec2,
)
from rc_single_span.design.serviceability import (
    ResponseDeflectionResult,
    response_deflection_check,
)
from rc_single_span.traffic.bs5400 import BS5400NominalTrafficSuite
from rc_single_span.traffic.combinations import (
    BS5400GirderCombinationResult,
    BS5400TrafficCombinationCase,
    EurocodeGirderCombinationResult,
)
from rc_single_span.traffic.lm1 import LM1SearchResult


class EurocodeSLSBasis(str, Enum):
    CHARACTERISTIC = "characteristic"
    FREQUENT = "frequent"
    QUASI_PERMANENT = "quasi_permanent"


@dataclass(frozen=True)
class EC2DesignInputs:
    effective_depth_m: float
    bar_diameter_mm: float
    bar_spacing_mm: float
    cover_mm: float
    fct_eff_mpa: float
    crack_limit_mm: float
    maximum_neutral_axis_ratio: float
    steel_area_mm2: float | None = None
    es_mpa: float = 200000.0
    ecm_mpa: float | None = None
    deflection_limit_mm: float | None = None
    sls_basis: EurocodeSLSBasis = EurocodeSLSBasis.CHARACTERISTIC


@dataclass(frozen=True)
class BS5400DesignInputs:
    effective_depth_m: float
    bar_diameter_mm: float
    bar_spacing_mm: float
    nominal_cover_mm: float
    crack_point_depth_mm: float
    allowable_crack_width_mm: float
    ec_modified_mpa: float
    steel_area_mm2: float | None = None
    es_mpa: float = 200000.0
    tension_zone_width_m: float | None = None
    shear_reinforcement_fyv_mpa: float | None = None
    deflection_limit_mm: float | None = None


@dataclass(frozen=True)
class EurocodeGirderDesignResult:
    girder_index: int
    uls_combination_name: str
    sls_combination_name: str
    flexure: EC2FlexureResult
    shear: EC2ShearResult
    cracking: EC2CrackWidthResult
    deflection: ResponseDeflectionResult


@dataclass(frozen=True)
class BS5400GirderDesignResult:
    girder_index: int
    flexure_case: str
    shear_case: str
    cracking_case: str
    flexure: BS5400FlexureResult
    shear: BS5400ShearResult
    cracking: BS5400CrackWidthResult
    deflection: ResponseDeflectionResult


def _resolve_steel_area(project: BridgeProject, override_mm2: float | None) -> float:
    if override_mm2 is not None:
        if override_mm2 <= 0.0:
            raise ValueError("steel_area_mm2 must be positive.")
        return override_mm2
    reinforcement = project.provided_longitudinal_reinforcement
    if reinforcement is None:
        raise ValueError(
            "Design requires steel_area_mm2 or provided_longitudinal_reinforcement."
        )
    return reinforcement.total_area_mm2


def _validate_effective_depth(project: BridgeProject, effective_depth_m: float) -> None:
    total_depth = project.geometry.total_structural_depth_m
    if not 0.0 < effective_depth_m < total_depth:
        raise ValueError(
            "effective_depth_m must lie inside the final physical composite section."
        )


def _select_eurocode_sls(
    item: EurocodeGirderCombinationResult,
    basis: EurocodeSLSBasis,
) -> FactoredCombination:
    combinations = item.combinations
    if basis is EurocodeSLSBasis.CHARACTERISTIC:
        return combinations.characteristic_sls
    if basis is EurocodeSLSBasis.FREQUENT:
        return combinations.frequent_sls
    return combinations.quasi_permanent_sls


def run_eurocode_project_design(
    project: BridgeProject,
    combinations: tuple[EurocodeGirderCombinationResult, ...],
    traffic: LM1SearchResult,
    *,
    inputs: EC2DesignInputs,
) -> tuple[EurocodeGirderDesignResult, ...]:
    """Run EC2 girder checks from common-grillage LM1 and EN 1990 combinations."""

    project.materials.require_for(DesignStandard.EUROCODE)
    _validate_effective_depth(project, inputs.effective_depth_m)
    steel_area = _resolve_steel_area(project, inputs.steel_area_mm2)
    fck = float(project.materials.fck_mpa)
    fyk = float(project.materials.fyk_mpa)
    ecm = (
        float(inputs.ecm_mpa)
        if inputs.ecm_mpa is not None
        else project.materials.elastic_modulus_mpa
    )
    if ecm is None or ecm <= 0.0:
        raise ValueError("EC2 cracking requires explicit ecm_mpa.")
    if not 0.0 < inputs.maximum_neutral_axis_ratio <= 1.0:
        raise ValueError("maximum_neutral_axis_ratio must lie in (0, 1].")
    if len(combinations) != int(project.geometry.girder_count):
        raise ValueError("Eurocode combination count does not match the bridge.")
    if len(traffic.girders) != int(project.geometry.girder_count):
        raise ValueError("LM1 girder count does not match the bridge.")

    results: list[EurocodeGirderDesignResult] = []
    for item in combinations:
        index = item.girder_index
        layers = final_composite_concrete_layers(
            project.geometry,
            girder_index=index,
        )
        uls = item.combinations.persistent_uls
        sls = _select_eurocode_sls(item, inputs.sls_basis)

        flexure = check_layered_flexure_ec2(
            med_knm=uls.effects.moment_knm,
            layers=layers,
            effective_depth_m=inputs.effective_depth_m,
            steel_area_mm2=steel_area,
            fck_mpa=fck,
            fyk_mpa=fyk,
            maximum_neutral_axis_ratio=inputs.maximum_neutral_axis_ratio,
        )
        shear = check_shear_ec2(
            ved_kn=uls.effects.shear_kn,
            web_width_m=girder_web_width_m(project.geometry),
            effective_depth_m=inputs.effective_depth_m,
            longitudinal_steel_area_mm2=steel_area,
            fck_mpa=fck,
            fyk_mpa=fyk,
        )
        cracking = check_crack_width_ec2(
            layers=layers,
            total_depth_m=project.geometry.total_structural_depth_m,
            steel_area_mm2=steel_area,
            steel_depth_m=inputs.effective_depth_m,
            bar_diameter_mm=inputs.bar_diameter_mm,
            bar_spacing_mm=inputs.bar_spacing_mm,
            cover_mm=inputs.cover_mm,
            service_moment_knm=sls.effects.moment_knm,
            es_mpa=inputs.es_mpa,
            ecm_mpa=float(ecm),
            fct_eff_mpa=inputs.fct_eff_mpa,
            crack_limit_mm=inputs.crack_limit_mm,
        )

        traffic_envelope = traffic.girders[index - 1]
        traffic_factor = sls.factors["Q_traffic"]
        x_m = traffic_envelope.deflection_position_m
        permanent_at_x = factored_permanent_deflection_at_x_mm(
            project,
            girder_index=index,
            x_m=x_m,
        )
        deflection = response_deflection_check(
            permanent_deflection_mm=permanent_at_x,
            traffic_characteristic_deflection_mm=traffic_envelope.deflection_mm.value,
            traffic_factor=traffic_factor,
            allowable_deflection_mm=inputs.deflection_limit_mm,
            status=(
                f"{sls.name}: stage-aware permanent displacement evaluated at "
                f"x={x_m:.6g} m plus the governing LM1 common-grillage traffic "
                "displacement at the same traffic-governing station. Final verification "
                "should re-search combined displacement across every retained traffic case."
            ),
        )
        results.append(
            EurocodeGirderDesignResult(
                girder_index=index,
                uls_combination_name=uls.name,
                sls_combination_name=sls.name,
                flexure=flexure,
                shear=shear,
                cracking=cracking,
                deflection=deflection,
            )
        )
    return tuple(results)


def _bs_traffic_envelope(
    traffic: BS5400NominalTrafficSuite,
    source: BS5400PrimaryTraffic,
    girder_index: int,
):
    if source is BS5400PrimaryTraffic.HA:
        return traffic.ha.girders[girder_index - 1]
    if source is BS5400PrimaryTraffic.HB:
        return traffic.hb.girders[girder_index - 1]
    return traffic.ha_hb.girders[girder_index - 1]


def _case_label(case: BS5400TrafficCombinationCase) -> str:
    return (
        f"BS 5400 combination {case.combination} {case.limit_state.value.upper()} "
        f"({case.traffic.value})"
    )


def _bs_sls_permanent_factor_map(
    factors: BS5400PermanentGammaFL,
) -> dict[PermanentLoadCategory, float]:
    named = factors.as_named_factors(BS5400LimitState.SLS)
    return {
        PermanentLoadCategory.STRUCTURAL_DEAD: named["structural_dead"],
        PermanentLoadCategory.SURFACING: named["surfacing"],
        PermanentLoadCategory.OTHER_SUPERIMPOSED: named["other_superimposed"],
    }


def run_bs5400_project_design(
    project: BridgeProject,
    combinations: tuple[BS5400GirderCombinationResult, ...],
    traffic: BS5400NominalTrafficSuite,
    *,
    inputs: BS5400DesignInputs,
    permanent_factors: BS5400PermanentGammaFL | None = None,
) -> tuple[BS5400GirderDesignResult, ...]:
    """Run BS 5400 Part 4 checks from the common-grillage BS traffic path."""

    project.materials.require_for(DesignStandard.BS5400)
    _validate_effective_depth(project, inputs.effective_depth_m)
    steel_area = _resolve_steel_area(project, inputs.steel_area_mm2)
    fcu = float(project.materials.fcu_mpa)
    fy = float(project.materials.fyk_mpa)
    fyv = (
        fy
        if inputs.shear_reinforcement_fyv_mpa is None
        else inputs.shear_reinforcement_fyv_mpa
    )
    if fyv <= 0.0:
        raise ValueError("shear_reinforcement_fyv_mpa must be positive.")
    if len(combinations) != int(project.geometry.girder_count):
        raise ValueError("BS 5400 combination count does not match the bridge.")

    gamma = permanent_factors or BS5400PermanentGammaFL()
    permanent_deflection_factors = _bs_sls_permanent_factor_map(gamma)
    results: list[BS5400GirderDesignResult] = []

    for item in combinations:
        index = item.girder_index
        layers = final_composite_concrete_layers(
            project.geometry,
            girder_index=index,
        )
        uls_cases = tuple(
            case
            for case in item.cases
            if case.limit_state is BS5400LimitState.ULS
        )
        sls_cases = tuple(
            case
            for case in item.cases
            if case.limit_state is BS5400LimitState.SLS
        )
        if not uls_cases or not sls_cases:
            raise ValueError("BS 5400 design requires both ULS and SLS traffic cases.")

        flexure_case = max(
            uls_cases,
            key=lambda case: case.result.effects.moment_knm,
        )
        shear_case = max(
            uls_cases,
            key=lambda case: case.result.effects.shear_kn,
        )
        crack_case = max(
            sls_cases,
            key=lambda case: case.result.effects.moment_knm,
        )

        flexure = check_layered_flexure_bs5400(
            med_knm=flexure_case.result.effects.moment_knm,
            layers=layers,
            effective_depth_m=inputs.effective_depth_m,
            steel_area_mm2=steel_area,
            fcu_mpa=fcu,
            fy_mpa=fy,
        )
        shear = check_shear_bs5400(
            ved_kn=shear_case.result.effects.shear_kn,
            web_width_m=girder_web_width_m(project.geometry),
            effective_depth_m=inputs.effective_depth_m,
            longitudinal_steel_area_mm2=steel_area,
            fcu_mpa=fcu,
            fyv_mpa=fyv,
        )

        gamma_live = crack_case.result.factors["primary_live"]
        live_moment = crack_case.nominal_traffic.moment_knm * gamma_live
        permanent_moment = max(
            crack_case.result.effects.moment_knm - live_moment,
            0.0,
        )
        tension_width = (
            inputs.tension_zone_width_m
            if inputs.tension_zone_width_m is not None
            else layers[-1].width_m
        )
        cracking = check_crack_width_bs5400(
            layers=layers,
            total_depth_m=project.geometry.total_structural_depth_m,
            steel_area_mm2=steel_area,
            steel_depth_m=inputs.effective_depth_m,
            permanent_moment_knm=permanent_moment,
            live_moment_knm=live_moment,
            es_mpa=inputs.es_mpa,
            ec_modified_mpa=inputs.ec_modified_mpa,
            tension_zone_width_m=tension_width,
            crack_point_depth_mm=inputs.crack_point_depth_mm,
            nominal_cover_mm=inputs.nominal_cover_mm,
            bar_spacing_mm=inputs.bar_spacing_mm,
            bar_diameter_mm=inputs.bar_diameter_mm,
            allowable_crack_width_mm=inputs.allowable_crack_width_mm,
        )

        deflection_candidates: list[tuple[ResponseDeflectionResult, str]] = []
        for case in sls_cases:
            envelope = _bs_traffic_envelope(traffic, case.traffic, index)
            x_m = envelope.deflection_position_m
            permanent_at_x = factored_permanent_deflection_at_x_mm(
                project,
                girder_index=index,
                x_m=x_m,
                factors_by_category=permanent_deflection_factors,
            )
            traffic_factor = case.result.factors["primary_live"]
            result = response_deflection_check(
                permanent_deflection_mm=permanent_at_x,
                traffic_characteristic_deflection_mm=envelope.deflection_mm.value,
                traffic_factor=traffic_factor,
                allowable_deflection_mm=inputs.deflection_limit_mm,
                status=(
                    f"{_case_label(case)}: stage-aware BS permanent displacement "
                    f"evaluated at x={x_m:.6g} m plus the corresponding "
                    f"{case.traffic.value} common-grillage traffic displacement at "
                    "the same traffic-governing station. Final verification should "
                    "re-search combined displacement across every retained traffic case."
                ),
            )
            deflection_candidates.append((result, _case_label(case)))
        deflection, _ = max(
            deflection_candidates,
            key=lambda pair: pair[0].total_deflection_mm,
        )

        results.append(
            BS5400GirderDesignResult(
                girder_index=index,
                flexure_case=_case_label(flexure_case),
                shear_case=_case_label(shear_case),
                cracking_case=_case_label(crack_case),
                flexure=flexure,
                shear=shear,
                cracking=cracking,
                deflection=deflection,
            )
        )
    return tuple(results)
