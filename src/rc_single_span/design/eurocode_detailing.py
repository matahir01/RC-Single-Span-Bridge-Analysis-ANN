from __future__ import annotations

from dataclasses import dataclass
from math import sqrt


@dataclass(frozen=True)
class EC2LongitudinalLimits:
    minimum_tension_steel_mm2: float
    maximum_longitudinal_steel_mm2: float
    governing_minimum_ratio: float


@dataclass(frozen=True)
class EC2ShearDetailingLimits:
    minimum_rho_w: float
    minimum_asw_per_s_mm2_per_m: float
    maximum_longitudinal_link_spacing_mm: float
    maximum_transverse_leg_spacing_mm: float


@dataclass(frozen=True)
class EC2CoverCheck:
    bond_minimum_cover_mm: float
    durability_minimum_cover_mm: float
    allowance_for_deviation_mm: float
    nominal_cover_mm: float
    provided_cover_mm: float
    passes: bool


def longitudinal_limits_ec2(
    *,
    fctm_mpa: float,
    fyk_mpa: float,
    tension_zone_width_m: float,
    effective_depth_m: float,
    concrete_area_m2: float,
    minimum_coefficient: float = 0.26,
    absolute_minimum_ratio: float = 0.0013,
    maximum_ratio: float = 0.04,
) -> EC2LongitudinalLimits:
    if min(
        fctm_mpa,
        fyk_mpa,
        tension_zone_width_m,
        effective_depth_m,
        concrete_area_m2,
        minimum_coefficient,
        absolute_minimum_ratio,
        maximum_ratio,
    ) <= 0.0:
        raise ValueError("EC2 longitudinal detailing inputs must be positive.")

    bt_mm = tension_zone_width_m * 1000.0
    d_mm = effective_depth_m * 1000.0
    ratio_strength = minimum_coefficient * fctm_mpa / fyk_mpa
    ratio = max(ratio_strength, absolute_minimum_ratio)
    return EC2LongitudinalLimits(
        minimum_tension_steel_mm2=ratio * bt_mm * d_mm,
        maximum_longitudinal_steel_mm2=(
            maximum_ratio * concrete_area_m2 * 1_000_000.0
        ),
        governing_minimum_ratio=ratio,
    )


def shear_detailing_limits_ec2(
    *,
    fck_mpa: float,
    fyk_mpa: float,
    web_width_m: float,
    effective_depth_m: float,
    minimum_shear_coefficient: float = 0.08,
    longitudinal_spacing_factor: float = 0.75,
    transverse_spacing_factor: float = 0.75,
    transverse_spacing_cap_mm: float = 600.0,
) -> EC2ShearDetailingLimits:
    if min(
        fck_mpa,
        fyk_mpa,
        web_width_m,
        effective_depth_m,
        minimum_shear_coefficient,
        longitudinal_spacing_factor,
        transverse_spacing_factor,
        transverse_spacing_cap_mm,
    ) <= 0.0:
        raise ValueError("EC2 shear-detailing inputs must be positive.")

    rho_w = minimum_shear_coefficient * sqrt(fck_mpa) / fyk_mpa
    bw_mm = web_width_m * 1000.0
    d_mm = effective_depth_m * 1000.0
    return EC2ShearDetailingLimits(
        minimum_rho_w=rho_w,
        minimum_asw_per_s_mm2_per_m=rho_w * bw_mm * 1000.0,
        maximum_longitudinal_link_spacing_mm=longitudinal_spacing_factor * d_mm,
        maximum_transverse_leg_spacing_mm=min(
            transverse_spacing_factor * d_mm,
            transverse_spacing_cap_mm,
        ),
    )


def nominal_cover_check_ec2(
    *,
    bar_diameter_mm: float,
    durability_minimum_cover_mm: float,
    allowance_for_deviation_mm: float,
    provided_cover_mm: float,
) -> EC2CoverCheck:
    if min(
        bar_diameter_mm,
        durability_minimum_cover_mm,
        provided_cover_mm,
    ) <= 0.0:
        raise ValueError("EC2 cover inputs must be positive.")
    if allowance_for_deviation_mm < 0.0:
        raise ValueError("allowance_for_deviation_mm cannot be negative.")

    bond_minimum = bar_diameter_mm
    nominal = max(bond_minimum, durability_minimum_cover_mm) + allowance_for_deviation_mm
    return EC2CoverCheck(
        bond_minimum_cover_mm=bond_minimum,
        durability_minimum_cover_mm=durability_minimum_cover_mm,
        allowance_for_deviation_mm=allowance_for_deviation_mm,
        nominal_cover_mm=nominal,
        provided_cover_mm=provided_cover_mm,
        passes=provided_cover_mm + 1.0e-9 >= nominal,
    )


def ec2_minimum_clear_spacing_mm(
    *,
    bar_diameter_mm: float,
    aggregate_size_mm: float,
) -> float:
    if bar_diameter_mm <= 0.0 or aggregate_size_mm <= 0.0:
        raise ValueError("Bar diameter and aggregate size must be positive.")
    return max(20.0, bar_diameter_mm, aggregate_size_mm + 5.0)
