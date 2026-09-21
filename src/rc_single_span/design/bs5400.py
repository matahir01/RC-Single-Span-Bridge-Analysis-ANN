from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from rc_single_span.analysis.sections import ConcreteLayer
from rc_single_span.design.layered import (
    cracked_layered_section,
    layered_compression_resistance,
)


@dataclass(frozen=True)
class BS5400FlexureResult:
    design_moment_knm: float
    resistance_knm: float
    utilization: float
    g_flexure_knm: float
    neutral_axis_m: float
    lever_arm_m: float


@dataclass(frozen=True)
class BS5400ShearResult:
    design_shear_kn: float
    design_shear_stress_mpa: float
    concrete_design_shear_stress_mpa: float
    concrete_resistance_kn: float
    maximum_resistance_kn: float
    governing_asv_per_s_mm2_per_m: float
    requires_links_above_minimum: bool
    exceeds_maximum_shear: bool
    g_shear_concrete_kn: float


@dataclass(frozen=True)
class BS5400CrackWidthResult:
    crack_width_mm: float
    allowable_crack_width_mm: float
    utilization: float
    g_crack_mm: float
    passes: bool
    steel_stress_mpa: float
    compression_depth_mm: float
    mean_strain: float
    acr_mm: float


def check_layered_flexure_bs5400(
    *,
    med_knm: float,
    layers: tuple[ConcreteLayer, ...],
    effective_depth_m: float,
    steel_area_mm2: float,
    fcu_mpa: float,
    fy_mpa: float,
    concrete_block_stress_factor: float = 0.40,
    steel_design_factor: float = 0.87,
    maximum_neutral_axis_ratio: float = 0.50,
    maximum_lever_arm_ratio: float = 0.95,
) -> BS5400FlexureResult:
    if med_knm < 0.0:
        raise ValueError("med_knm cannot be negative.")
    if min(
        steel_area_mm2,
        fcu_mpa,
        fy_mpa,
        concrete_block_stress_factor,
        steel_design_factor,
    ) <= 0.0:
        raise ValueError("BS 5400 flexure inputs must be positive.")

    base = layered_compression_resistance(
        layers=layers,
        effective_depth_m=effective_depth_m,
        steel_force_n=steel_design_factor * fy_mpa * steel_area_mm2,
        concrete_block_stress_mpa=concrete_block_stress_factor * fcu_mpa,
        neutral_axis_block_ratio=1.0,
        maximum_neutral_axis_ratio=maximum_neutral_axis_ratio,
        maximum_lever_arm_ratio=maximum_lever_arm_ratio,
    )
    return BS5400FlexureResult(
        design_moment_knm=med_knm,
        resistance_knm=base.resistance_knm,
        utilization=med_knm / base.resistance_knm,
        g_flexure_knm=base.resistance_knm - med_knm,
        neutral_axis_m=base.neutral_axis_from_top_m,
        lever_arm_m=base.lever_arm_m,
    )


def check_shear_bs5400(
    *,
    ved_kn: float,
    web_width_m: float,
    effective_depth_m: float,
    longitudinal_steel_area_mm2: float,
    fcu_mpa: float,
    fyv_mpa: float,
    gamma_m_concrete_shear: float = 1.25,
    concrete_shear_coefficient: float = 0.27,
    depth_reference_mm: float = 500.0,
    minimum_depth_factor: float = 0.70,
    maximum_shear_coefficient: float = 0.75,
    maximum_shear_cap_mpa: float = 4.75,
    minimum_link_stress_mpa: float = 0.40,
    steel_design_factor: float = 0.87,
    maximum_link_yield_mpa: float = 460.0,
) -> BS5400ShearResult:
    if ved_kn < 0.0:
        raise ValueError("ved_kn cannot be negative.")
    if min(
        web_width_m,
        effective_depth_m,
        longitudinal_steel_area_mm2,
        fcu_mpa,
        fyv_mpa,
    ) <= 0.0:
        raise ValueError("BS 5400 shear inputs must be positive.")

    bw_mm = web_width_m * 1000.0
    d_mm = effective_depth_m * 1000.0
    design_shear_stress = ved_kn * 1000.0 / (bw_mm * d_mm)
    reinforcement_ratio_percent = (
        100.0 * longitudinal_steel_area_mm2 / (bw_mm * d_mm)
    )
    concrete_shear_stress = (
        concrete_shear_coefficient
        / gamma_m_concrete_shear
        * reinforcement_ratio_percent ** (1.0 / 3.0)
        * fcu_mpa ** (1.0 / 3.0)
    )
    depth_factor = max((depth_reference_mm / d_mm) ** 0.25, minimum_depth_factor)
    concrete_design_stress = depth_factor * concrete_shear_stress
    concrete_resistance = concrete_design_stress * bw_mm * d_mm / 1000.0

    maximum_shear_stress = min(
        maximum_shear_coefficient * sqrt(fcu_mpa),
        maximum_shear_cap_mpa,
    )
    maximum_resistance = maximum_shear_stress * bw_mm * d_mm / 1000.0

    effective_fyv = min(fyv_mpa, maximum_link_yield_mpa)
    denominator = steel_design_factor * effective_fyv
    minimum_asv_per_s = minimum_link_stress_mpa * bw_mm / denominator
    requires_above_minimum = design_shear_stress > concrete_design_stress
    design_asv_per_s = 0.0
    if requires_above_minimum:
        design_asv_per_s = (
            bw_mm
            * (
                design_shear_stress
                + minimum_link_stress_mpa
                - concrete_design_stress
            )
            / denominator
        )
    governing = max(minimum_asv_per_s, design_asv_per_s) * 1000.0

    return BS5400ShearResult(
        design_shear_kn=ved_kn,
        design_shear_stress_mpa=design_shear_stress,
        concrete_design_shear_stress_mpa=concrete_design_stress,
        concrete_resistance_kn=concrete_resistance,
        maximum_resistance_kn=maximum_resistance,
        governing_asv_per_s_mm2_per_m=governing,
        requires_links_above_minimum=requires_above_minimum,
        exceeds_maximum_shear=design_shear_stress > maximum_shear_stress,
        g_shear_concrete_kn=concrete_resistance - ved_kn,
    )


def controlling_surface_distance_mm(
    *,
    bar_spacing_mm: float,
    nominal_cover_to_bar_surface_mm: float,
    bar_diameter_mm: float,
) -> float:
    if min(
        bar_spacing_mm,
        nominal_cover_to_bar_surface_mm,
        bar_diameter_mm,
    ) <= 0.0:
        raise ValueError("Bar spacing, cover and diameter must be positive.")
    centre_cover = nominal_cover_to_bar_surface_mm + bar_diameter_mm / 2.0
    centre_distance = sqrt((bar_spacing_mm / 2.0) ** 2 + centre_cover**2)
    return centre_distance - bar_diameter_mm / 2.0


def _mean_strain_bs5400(
    *,
    epsilon_1: float,
    epsilon_s: float,
    tension_zone_width_mm: float,
    overall_depth_mm: float,
    crack_point_depth_mm: float,
    compression_depth_mm: float,
    steel_area_mm2: float,
    permanent_moment_knm: float,
    live_moment_knm: float,
) -> float:
    if permanent_moment_knm == 0.0:
        return epsilon_1
    geometry_term = (
        3.8
        * tension_zone_width_mm
        * overall_depth_mm
        * (crack_point_depth_mm - compression_depth_mm)
        / (
            epsilon_s
            * steel_area_mm2
            * (overall_depth_mm - compression_depth_mm)
        )
    )
    load_term = (1.0 - live_moment_knm / permanent_moment_knm) * 1.0e-9
    return min(epsilon_1 - geometry_term * load_term, epsilon_1)


def check_crack_width_bs5400(
    *,
    layers: tuple[ConcreteLayer, ...],
    total_depth_m: float,
    steel_area_mm2: float,
    steel_depth_m: float,
    permanent_moment_knm: float,
    live_moment_knm: float,
    es_mpa: float,
    ec_modified_mpa: float,
    tension_zone_width_m: float,
    crack_point_depth_mm: float,
    nominal_cover_mm: float,
    bar_spacing_mm: float,
    bar_diameter_mm: float,
    allowable_crack_width_mm: float,
) -> BS5400CrackWidthResult:
    positive = (
        total_depth_m,
        steel_area_mm2,
        steel_depth_m,
        es_mpa,
        ec_modified_mpa,
        tension_zone_width_m,
        crack_point_depth_mm,
        nominal_cover_mm,
        bar_spacing_mm,
        bar_diameter_mm,
        allowable_crack_width_mm,
    )
    if any(value <= 0.0 for value in positive):
        raise ValueError("BS 5400 crack-width inputs must be positive.")
    if permanent_moment_knm < 0.0 or live_moment_knm < 0.0:
        raise ValueError("Service moments cannot be negative.")

    service_moment = permanent_moment_knm + live_moment_knm
    cracked = cracked_layered_section(
        layers=layers,
        steel_area_mm2=steel_area_mm2,
        steel_depth_m=steel_depth_m,
        modular_ratio=es_mpa / ec_modified_mpa,
        service_moment_knm=service_moment,
    )
    x_mm = cracked.neutral_axis_from_top_mm
    h_mm = total_depth_m * 1000.0
    d_mm = steel_depth_m * 1000.0
    if not x_mm <= crack_point_depth_mm <= h_mm:
        raise ValueError("crack_point_depth_mm must lie in the tensile zone.")

    epsilon_s = cracked.steel_stress_mpa / es_mpa
    epsilon_1 = (
        0.0
        if epsilon_s <= 0.0
        else epsilon_s * (crack_point_depth_mm - x_mm) / (d_mm - x_mm)
    )
    if epsilon_s <= 0.0 or epsilon_1 <= 0.0:
        mean_strain = 0.0
    else:
        mean_strain = _mean_strain_bs5400(
            epsilon_1=epsilon_1,
            epsilon_s=epsilon_s,
            tension_zone_width_mm=tension_zone_width_m * 1000.0,
            overall_depth_mm=h_mm,
            crack_point_depth_mm=crack_point_depth_mm,
            compression_depth_mm=x_mm,
            steel_area_mm2=steel_area_mm2,
            permanent_moment_knm=permanent_moment_knm,
            live_moment_knm=live_moment_knm,
        )

    acr = controlling_surface_distance_mm(
        bar_spacing_mm=bar_spacing_mm,
        nominal_cover_to_bar_surface_mm=nominal_cover_mm,
        bar_diameter_mm=bar_diameter_mm,
    )
    if mean_strain <= 0.0:
        crack_width = 0.0
    else:
        denominator = 1.0 + 2.0 * (acr - nominal_cover_mm) / (h_mm - x_mm)
        if denominator <= 0.0:
            raise ValueError("Crack-width geometry produces a non-positive denominator.")
        crack_width = 3.0 * acr * mean_strain / denominator

    return BS5400CrackWidthResult(
        crack_width_mm=crack_width,
        allowable_crack_width_mm=allowable_crack_width_mm,
        utilization=crack_width / allowable_crack_width_mm,
        g_crack_mm=allowable_crack_width_mm - crack_width,
        passes=crack_width <= allowable_crack_width_mm + 1.0e-12,
        steel_stress_mpa=cracked.steel_stress_mpa,
        compression_depth_mm=x_mm,
        mean_strain=mean_strain,
        acr_mm=acr,
    )



def required_steel_area_layered_bs5400(
    *,
    med_knm: float,
    layers: tuple[ConcreteLayer, ...],
    effective_depth_m: float,
    fcu_mpa: float,
    fy_mpa: float,
    maximum_neutral_axis_ratio: float = 0.50,
    tolerance_knm: float = 0.01,
) -> float:
    """Solve the least BS 5400 tension-steel area within the singly reinforced scope."""

    if med_knm < 0.0:
        raise ValueError("med_knm cannot be negative.")
    if med_knm == 0.0:
        return 0.0
    if not 0.0 < maximum_neutral_axis_ratio <= 1.0:
        raise ValueError("maximum_neutral_axis_ratio must lie in (0, 1].")

    lower = 1.0
    upper = 1000.0
    last_valid_area = lower
    last_valid_resistance = 0.0
    failed_upper: float | None = None

    for _ in range(40):
        try:
            result = check_layered_flexure_bs5400(
                med_knm=med_knm,
                layers=layers,
                effective_depth_m=effective_depth_m,
                steel_area_mm2=upper,
                fcu_mpa=fcu_mpa,
                fy_mpa=fy_mpa,
                maximum_neutral_axis_ratio=maximum_neutral_axis_ratio,
            )
        except ValueError as exc:
            if (
                "Neutral axis exceeds" in str(exc)
                or "compression force exceeds" in str(exc)
            ):
                failed_upper = upper
                break
            raise
        last_valid_area = upper
        last_valid_resistance = result.resistance_knm
        if result.resistance_knm >= med_knm:
            break
        lower = upper
        upper *= 2.0
    else:
        raise ValueError("Unable to bracket required BS 5400 layered-section steel area.")

    if failed_upper is not None:
        low = last_valid_area
        high = failed_upper
        best_area = last_valid_area
        best_resistance = last_valid_resistance
        for _ in range(100):
            mid = 0.5 * (low + high)
            try:
                result = check_layered_flexure_bs5400(
                    med_knm=med_knm,
                    layers=layers,
                    effective_depth_m=effective_depth_m,
                    steel_area_mm2=mid,
                    fcu_mpa=fcu_mpa,
                    fy_mpa=fy_mpa,
                    maximum_neutral_axis_ratio=maximum_neutral_axis_ratio,
                )
            except ValueError as exc:
                if (
                    "Neutral axis exceeds" in str(exc)
                    or "compression force exceeds" in str(exc)
                ):
                    high = mid
                    continue
                raise
            best_area = mid
            best_resistance = result.resistance_knm
            low = mid
        if best_resistance + tolerance_knm < med_knm:
            raise ValueError(
                "BS 5400 design moment exceeds the configured singly reinforced layered-section capacity."
            )
        upper = best_area
        lower = 1.0

    for _ in range(100):
        mid = 0.5 * (lower + upper)
        try:
            result = check_layered_flexure_bs5400(
                med_knm=med_knm,
                layers=layers,
                effective_depth_m=effective_depth_m,
                steel_area_mm2=mid,
                fcu_mpa=fcu_mpa,
                fy_mpa=fy_mpa,
                maximum_neutral_axis_ratio=maximum_neutral_axis_ratio,
            )
        except ValueError as exc:
            if (
                "Neutral axis exceeds" in str(exc)
                or "compression force exceeds" in str(exc)
            ):
                upper = mid
                continue
            raise
        if abs(result.resistance_knm - med_knm) <= tolerance_knm:
            return mid
        if result.resistance_knm < med_knm:
            lower = mid
        else:
            upper = mid
    return upper
