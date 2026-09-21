from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from rc_single_span.analysis.sections import ConcreteLayer
from rc_single_span.design.layered import (
    cracked_layered_section,
    effective_tension_area_mm2,
    effective_tension_depth_mm,
    layered_compression_resistance,
    uncracked_layered_section,
)


@dataclass(frozen=True)
class EC2FlexureResult:
    design_moment_knm: float
    resistance_knm: float
    utilization: float
    g_flexure_knm: float
    neutral_axis_m: float
    lever_arm_m: float
    neutral_axis_ratio: float
    ductility_limit_ratio: float | None
    ductility_passes: bool | None


@dataclass(frozen=True)
class EC2ShearResult:
    design_shear_kn: float
    vrdc_kn: float
    vrdmax_kn: float
    required_asw_per_s_mm2_per_m: float
    rho_l: float
    k: float
    concrete_only_passes: bool
    web_crushing_passes: bool
    g_shear_concrete_kn: float


@dataclass(frozen=True)
class EC2CrackWidthResult:
    crack_width_mm: float
    crack_limit_mm: float
    utilization: float
    g_crack_mm: float
    steel_stress_mpa: float
    cracking_moment_knm: float
    max_crack_spacing_mm: float
    effective_reinforcement_ratio: float
    close_spacing: bool


def check_layered_flexure_ec2(
    *,
    med_knm: float,
    layers: tuple[ConcreteLayer, ...],
    effective_depth_m: float,
    steel_area_mm2: float,
    fck_mpa: float,
    fyk_mpa: float,
    gamma_c: float = 1.50,
    gamma_s: float = 1.15,
    alpha_cc: float = 1.0,
    lambda_block: float = 0.8,
    maximum_neutral_axis_ratio: float | None = None,
) -> EC2FlexureResult:
    if med_knm < 0.0:
        raise ValueError("med_knm cannot be negative.")
    if min(steel_area_mm2, fck_mpa, fyk_mpa, gamma_c, gamma_s, alpha_cc) <= 0.0:
        raise ValueError("EC2 flexure inputs must be positive.")

    steel_force_n = steel_area_mm2 * fyk_mpa / gamma_s
    base = layered_compression_resistance(
        layers=layers,
        effective_depth_m=effective_depth_m,
        steel_force_n=steel_force_n,
        concrete_block_stress_mpa=alpha_cc * fck_mpa / gamma_c,
        neutral_axis_block_ratio=lambda_block,
        maximum_neutral_axis_ratio=maximum_neutral_axis_ratio,
    )
    ratio = base.neutral_axis_from_top_m / effective_depth_m
    ductility_passes = (
        None
        if maximum_neutral_axis_ratio is None
        else ratio <= maximum_neutral_axis_ratio + 1.0e-12
    )
    utilization = med_knm / base.resistance_knm
    return EC2FlexureResult(
        design_moment_knm=med_knm,
        resistance_knm=base.resistance_knm,
        utilization=utilization,
        g_flexure_knm=base.resistance_knm - med_knm,
        neutral_axis_m=base.neutral_axis_from_top_m,
        lever_arm_m=base.lever_arm_m,
        neutral_axis_ratio=ratio,
        ductility_limit_ratio=maximum_neutral_axis_ratio,
        ductility_passes=ductility_passes,
    )


def check_shear_ec2(
    *,
    ved_kn: float,
    web_width_m: float,
    effective_depth_m: float,
    longitudinal_steel_area_mm2: float,
    fck_mpa: float,
    fyk_mpa: float,
    gamma_c: float = 1.50,
    gamma_s: float = 1.15,
    alpha_cc: float = 1.0,
    c_rdc_factor: float = 0.18,
    sigma_cp_mpa: float = 0.0,
    k1: float = 0.15,
    cot_theta: float = 2.0,
    z_factor: float = 0.9,
    alpha_cw: float = 1.0,
) -> EC2ShearResult:
    if ved_kn < 0.0:
        raise ValueError("ved_kn cannot be negative.")
    if min(
        web_width_m,
        effective_depth_m,
        longitudinal_steel_area_mm2,
        fck_mpa,
        fyk_mpa,
    ) <= 0.0:
        raise ValueError("EC2 shear geometry, reinforcement and strengths must be positive.")
    if not 1.0 <= cot_theta <= 2.5:
        raise ValueError("cot_theta must lie between 1.0 and 2.5.")

    bw_mm = web_width_m * 1000.0
    d_mm = effective_depth_m * 1000.0
    k = min(1.0 + sqrt(200.0 / d_mm), 2.0)
    rho_l = min(longitudinal_steel_area_mm2 / (bw_mm * d_mm), 0.02)
    c_rdc = c_rdc_factor / gamma_c
    vmin_mpa = 0.035 * k**1.5 * sqrt(fck_mpa)
    stress_main_mpa = (
        c_rdc * k * (100.0 * rho_l * fck_mpa) ** (1.0 / 3.0)
        + k1 * sigma_cp_mpa
    )
    stress_min_mpa = vmin_mpa + k1 * sigma_cp_mpa
    vrdc_kn = max(stress_main_mpa, stress_min_mpa) * bw_mm * d_mm / 1000.0

    z_mm = z_factor * d_mm
    fyd_mpa = fyk_mpa / gamma_s
    fcd_mpa = alpha_cc * fck_mpa / gamma_c
    tan_theta = 1.0 / cot_theta
    nu1 = 0.6 * (1.0 - fck_mpa / 250.0)
    vrdmax_kn = (
        alpha_cw
        * bw_mm
        * z_mm
        * nu1
        * fcd_mpa
        / (cot_theta + tan_theta)
        / 1000.0
    )
    required_asw_per_s_mm2_per_mm = (
        0.0
        if ved_kn <= vrdc_kn
        else ved_kn * 1000.0 / (z_mm * fyd_mpa * cot_theta)
    )

    return EC2ShearResult(
        design_shear_kn=ved_kn,
        vrdc_kn=vrdc_kn,
        vrdmax_kn=vrdmax_kn,
        required_asw_per_s_mm2_per_m=required_asw_per_s_mm2_per_mm * 1000.0,
        rho_l=rho_l,
        k=k,
        concrete_only_passes=ved_kn <= vrdc_kn + 1.0e-9,
        web_crushing_passes=ved_kn <= vrdmax_kn + 1.0e-9,
        g_shear_concrete_kn=vrdc_kn - ved_kn,
    )


def check_crack_width_ec2(
    *,
    layers: tuple[ConcreteLayer, ...],
    total_depth_m: float,
    steel_area_mm2: float,
    steel_depth_m: float,
    bar_diameter_mm: float,
    bar_spacing_mm: float,
    cover_mm: float,
    service_moment_knm: float,
    es_mpa: float,
    ecm_mpa: float,
    fct_eff_mpa: float,
    crack_limit_mm: float,
    kt: float = 0.4,
    k1: float = 0.8,
    k2: float = 0.5,
    k3: float = 3.4,
    k4: float = 0.425,
) -> EC2CrackWidthResult:
    positive = (
        total_depth_m,
        steel_area_mm2,
        steel_depth_m,
        bar_diameter_mm,
        bar_spacing_mm,
        cover_mm,
        es_mpa,
        ecm_mpa,
        fct_eff_mpa,
        crack_limit_mm,
    )
    if any(value <= 0.0 for value in positive):
        raise ValueError("EC2 crack-width inputs must be positive.")
    if service_moment_knm < 0.0:
        raise ValueError("service_moment_knm cannot be negative.")

    modular_ratio = es_mpa / ecm_mpa
    uncracked = uncracked_layered_section(
        layers=layers,
        steel_area_mm2=steel_area_mm2,
        steel_depth_m=steel_depth_m,
        modular_ratio=modular_ratio,
        fct_eff_mpa=fct_eff_mpa,
    )
    cracked = cracked_layered_section(
        layers=layers,
        steel_area_mm2=steel_area_mm2,
        steel_depth_m=steel_depth_m,
        modular_ratio=modular_ratio,
        service_moment_knm=service_moment_knm,
    )
    hceff = effective_tension_depth_mm(
        total_depth_m=total_depth_m,
        steel_depth_m=steel_depth_m,
        neutral_axis_from_top_mm=cracked.neutral_axis_from_top_mm,
    )
    aceff = effective_tension_area_mm2(
        layers=layers,
        total_depth_m=total_depth_m,
        effective_tension_depth_mm_value=hceff,
    )
    rho = steel_area_mm2 / aceff
    sigma_s = cracked.steel_stress_mpa

    if service_moment_knm <= uncracked.cracking_moment_knm:
        return EC2CrackWidthResult(
            crack_width_mm=0.0,
            crack_limit_mm=crack_limit_mm,
            utilization=0.0,
            g_crack_mm=crack_limit_mm,
            steel_stress_mpa=sigma_s,
            cracking_moment_knm=uncracked.cracking_moment_knm,
            max_crack_spacing_mm=0.0,
            effective_reinforcement_ratio=rho,
            close_spacing=True,
        )

    strain_calc = (
        sigma_s - kt * fct_eff_mpa / rho * (1.0 + modular_ratio * rho)
    ) / es_mpa
    strain_min = 0.6 * sigma_s / es_mpa
    strain_difference = max(strain_calc, strain_min, 0.0)
    close_spacing = bar_spacing_mm <= 5.0 * (cover_mm + bar_diameter_mm / 2.0)
    if close_spacing:
        srmax = k3 * cover_mm + k1 * k2 * k4 * bar_diameter_mm / rho
    else:
        srmax = 1.3 * (
            total_depth_m * 1000.0 - cracked.neutral_axis_from_top_mm
        )
    crack_width = srmax * strain_difference

    return EC2CrackWidthResult(
        crack_width_mm=crack_width,
        crack_limit_mm=crack_limit_mm,
        utilization=crack_width / crack_limit_mm,
        g_crack_mm=crack_limit_mm - crack_width,
        steel_stress_mpa=sigma_s,
        cracking_moment_knm=uncracked.cracking_moment_knm,
        max_crack_spacing_mm=srmax,
        effective_reinforcement_ratio=rho,
        close_spacing=close_spacing,
    )
