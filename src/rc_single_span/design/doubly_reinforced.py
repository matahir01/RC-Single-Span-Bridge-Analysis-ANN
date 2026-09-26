from __future__ import annotations

from dataclasses import dataclass

from rc_single_span.analysis.sections import ConcreteLayer
from rc_single_span.design.layered import compression_block_properties, validate_layers


@dataclass(frozen=True)
class DoublyReinforcedCheckResult:
    design_moment_knm: float
    resistance_knm: float
    utilization: float
    neutral_axis_m: float
    effective_depth_m: float
    compression_steel_depth_m: float
    tension_steel_area_mm2: float
    compression_steel_area_mm2: float
    tension_steel_stress_mpa: float
    compression_steel_stress_mpa: float
    concrete_compression_force_kn: float
    compression_steel_force_kn: float
    tension_steel_force_kn: float
    force_equilibrium_residual_kn: float
    passes: bool
    basis: str


@dataclass(frozen=True)
class DoublyReinforcedRequirement:
    design_moment_knm: float
    limiting_concrete_moment_knm: float
    excess_moment_knm: float
    effective_depth_m: float
    compression_steel_depth_m: float
    limiting_neutral_axis_m: float
    concrete_compression_force_kn: float
    base_tension_steel_mm2: float
    additional_tension_steel_mm2: float
    total_tension_steel_mm2: float
    compression_steel_mm2: float
    compression_steel_design_stress_mpa: float
    tension_steel_design_stress_mpa: float
    equilibrium_residual_kn: float
    moment_residual_knm: float
    basis: str


def required_doubly_reinforced_steel_ec2(
    *,
    med_knm: float,
    layers: tuple[ConcreteLayer, ...],
    effective_depth_m: float,
    compression_steel_depth_m: float,
    fck_mpa: float,
    fyk_mpa: float,
    maximum_neutral_axis_ratio: float,
    gamma_c: float = 1.50,
    gamma_s: float = 1.15,
    alpha_cc: float = 1.0,
    lambda_block: float = 0.8,
    es_mpa: float = 200000.0,
    ultimate_concrete_strain: float = 0.0035,
) -> DoublyReinforcedRequirement:
    """Design additional compression/tension steel beyond the EC2 singly limit.

    The concrete block is fixed at the configured limiting neutral axis. The
    excess design moment is carried by a compression-steel/additional-tension-
    steel couple. Compression-steel stress is obtained from strain
    compatibility at that limiting neutral axis and capped at f_yd.
    """

    if min(
        med_knm,
        effective_depth_m,
        compression_steel_depth_m,
        fck_mpa,
        fyk_mpa,
        maximum_neutral_axis_ratio,
        gamma_c,
        gamma_s,
        alpha_cc,
        lambda_block,
        es_mpa,
        ultimate_concrete_strain,
    ) <= 0.0:
        raise ValueError("EC2 doubly reinforced design inputs must be positive.")
    if compression_steel_depth_m >= effective_depth_m:
        raise ValueError("Compression steel must lie above the tension steel.")
    if not 0.0 < maximum_neutral_axis_ratio <= 1.0:
        raise ValueError("maximum_neutral_axis_ratio must lie in (0, 1].")
    if not 0.0 < lambda_block <= 1.0:
        raise ValueError("lambda_block must lie in (0, 1].")

    ordered = validate_layers(layers, steel_depth_m=effective_depth_m)
    x_lim = maximum_neutral_axis_ratio * effective_depth_m
    if compression_steel_depth_m >= x_lim:
        raise ValueError(
            "Compression steel lies outside the compression zone at the limiting neutral axis."
        )

    block_depth = lambda_block * x_lim
    area_m2, centroid_m = compression_block_properties(
        ordered,
        block_depth_m=block_depth,
    )
    if area_m2 <= 0.0:
        raise ValueError("Limiting EC2 compression block contains no concrete.")

    concrete_stress_mpa = alpha_cc * fck_mpa / gamma_c
    concrete_force_n = concrete_stress_mpa * area_m2 * 1.0e6
    concrete_lever_m = effective_depth_m - centroid_m
    limiting_moment = concrete_force_n * concrete_lever_m / 1000.0

    if med_knm <= limiting_moment + 1.0e-9:
        raise ValueError(
            "Design moment does not exceed the configured singly reinforced EC2 limit."
        )

    fyd = fyk_mpa / gamma_s
    base_tension = concrete_force_n / fyd

    compression_strain = ultimate_concrete_strain * (
        x_lim - compression_steel_depth_m
    ) / x_lim
    compression_stress = min(es_mpa * compression_strain, fyd)
    if compression_stress <= 0.0:
        raise ValueError("Compression steel develops no compressive design stress.")

    excess_moment = med_knm - limiting_moment
    steel_couple_lever_mm = (
        effective_depth_m - compression_steel_depth_m
    ) * 1000.0
    compression_force_n = excess_moment * 1.0e6 / steel_couple_lever_mm
    compression_area = compression_force_n / compression_stress
    additional_tension = compression_force_n / fyd
    total_tension = base_tension + additional_tension

    equilibrium_residual_kn = (
        total_tension * fyd
        - concrete_force_n
        - compression_area * compression_stress
    ) / 1000.0
    recovered_moment = (
        concrete_force_n * concrete_lever_m / 1000.0
        + compression_area
        * compression_stress
        * steel_couple_lever_mm
        / 1.0e6
    )

    return DoublyReinforcedRequirement(
        design_moment_knm=med_knm,
        limiting_concrete_moment_knm=limiting_moment,
        excess_moment_knm=excess_moment,
        effective_depth_m=effective_depth_m,
        compression_steel_depth_m=compression_steel_depth_m,
        limiting_neutral_axis_m=x_lim,
        concrete_compression_force_kn=concrete_force_n / 1000.0,
        base_tension_steel_mm2=base_tension,
        additional_tension_steel_mm2=additional_tension,
        total_tension_steel_mm2=total_tension,
        compression_steel_mm2=compression_area,
        compression_steel_design_stress_mpa=compression_stress,
        tension_steel_design_stress_mpa=fyd,
        equilibrium_residual_kn=equilibrium_residual_kn,
        moment_residual_knm=recovered_moment - med_knm,
        basis=(
            "EC2 layered limiting concrete block plus compression-steel/additional-"
            "tension-steel couple with compression-steel strain compatibility."
        ),
    )


def required_doubly_reinforced_steel_bs5400(
    *,
    med_knm: float,
    layers: tuple[ConcreteLayer, ...],
    effective_depth_m: float,
    compression_steel_depth_m: float,
    fcu_mpa: float,
    fy_mpa: float,
    maximum_neutral_axis_ratio: float = 0.50,
    maximum_lever_arm_ratio: float = 0.95,
    concrete_block_stress_factor: float = 0.40,
    tension_steel_design_factor: float = 0.87,
    compression_steel_design_factor: float = 0.72,
) -> DoublyReinforcedRequirement:
    """Legacy BS 5400-style doubly reinforced layered-section extension.

    The limiting concrete block follows the same factors as the repository's
    BS 5400 singly reinforced check. Excess moment is resisted by a compression
    steel/additional tension steel couple using explicit design-stress factors.
    """

    if min(
        med_knm,
        effective_depth_m,
        compression_steel_depth_m,
        fcu_mpa,
        fy_mpa,
        maximum_neutral_axis_ratio,
        maximum_lever_arm_ratio,
        concrete_block_stress_factor,
        tension_steel_design_factor,
        compression_steel_design_factor,
    ) <= 0.0:
        raise ValueError("BS 5400 doubly reinforced design inputs must be positive.")
    if compression_steel_depth_m >= effective_depth_m:
        raise ValueError("Compression steel must lie above the tension steel.")
    if not 0.0 < maximum_neutral_axis_ratio <= 1.0:
        raise ValueError("maximum_neutral_axis_ratio must lie in (0, 1].")
    if not 0.0 < maximum_lever_arm_ratio <= 1.0:
        raise ValueError("maximum_lever_arm_ratio must lie in (0, 1].")

    ordered = validate_layers(layers, steel_depth_m=effective_depth_m)
    x_lim = maximum_neutral_axis_ratio * effective_depth_m
    if compression_steel_depth_m >= x_lim:
        raise ValueError(
            "Compression steel lies outside the compression zone at the limiting neutral axis."
        )

    area_m2, centroid_m = compression_block_properties(
        ordered,
        block_depth_m=x_lim,
    )
    if area_m2 <= 0.0:
        raise ValueError("Limiting BS 5400 compression block contains no concrete.")

    concrete_stress_mpa = concrete_block_stress_factor * fcu_mpa
    concrete_force_n = concrete_stress_mpa * area_m2 * 1.0e6
    concrete_lever_m = min(
        effective_depth_m - centroid_m,
        maximum_lever_arm_ratio * effective_depth_m,
    )
    limiting_moment = concrete_force_n * concrete_lever_m / 1000.0

    if med_knm <= limiting_moment + 1.0e-9:
        raise ValueError(
            "Design moment does not exceed the configured singly reinforced BS 5400 limit."
        )

    tension_stress = tension_steel_design_factor * fy_mpa
    compression_stress = compression_steel_design_factor * fy_mpa
    base_tension = concrete_force_n / tension_stress

    excess_moment = med_knm - limiting_moment
    steel_couple_lever_mm = (
        effective_depth_m - compression_steel_depth_m
    ) * 1000.0
    compression_force_n = excess_moment * 1.0e6 / steel_couple_lever_mm
    compression_area = compression_force_n / compression_stress
    additional_tension = compression_force_n / tension_stress
    total_tension = base_tension + additional_tension

    equilibrium_residual_kn = (
        total_tension * tension_stress
        - concrete_force_n
        - compression_area * compression_stress
    ) / 1000.0
    recovered_moment = (
        concrete_force_n * concrete_lever_m / 1000.0
        + compression_area
        * compression_stress
        * steel_couple_lever_mm
        / 1.0e6
    )

    return DoublyReinforcedRequirement(
        design_moment_knm=med_knm,
        limiting_concrete_moment_knm=limiting_moment,
        excess_moment_knm=excess_moment,
        effective_depth_m=effective_depth_m,
        compression_steel_depth_m=compression_steel_depth_m,
        limiting_neutral_axis_m=x_lim,
        concrete_compression_force_kn=concrete_force_n / 1000.0,
        base_tension_steel_mm2=base_tension,
        additional_tension_steel_mm2=additional_tension,
        total_tension_steel_mm2=total_tension,
        compression_steel_mm2=compression_area,
        compression_steel_design_stress_mpa=compression_stress,
        tension_steel_design_stress_mpa=tension_stress,
        equilibrium_residual_kn=equilibrium_residual_kn,
        moment_residual_knm=recovered_moment - med_knm,
        basis=(
            "BS 5400 layered limiting concrete block plus explicit design-stress "
            "compression-steel/additional-tension-steel couple."
        ),
    )


def _bisect_force_equilibrium(
    *,
    lower_m: float,
    upper_m: float,
    residual,
) -> float:
    f_lower = residual(lower_m)
    f_upper = residual(upper_m)
    if abs(f_lower) <= 1.0e-6:
        return lower_m
    if abs(f_upper) <= 1.0e-6:
        return upper_m
    if f_lower * f_upper > 0.0:
        raise ValueError(
            "Doubly reinforced force equilibrium is not bracketed within the "
            "configured neutral-axis range."
        )
    low, high = lower_m, upper_m
    for _ in range(120):
        mid = 0.5 * (low + high)
        value = residual(mid)
        if abs(value) <= 1.0e-3:
            return mid
        if f_lower * value <= 0.0:
            high = mid
            f_upper = value
        else:
            low = mid
            f_lower = value
    return 0.5 * (low + high)


def check_doubly_reinforced_ec2(
    *,
    med_knm: float,
    layers: tuple[ConcreteLayer, ...],
    effective_depth_m: float,
    compression_steel_depth_m: float,
    tension_steel_area_mm2: float,
    compression_steel_area_mm2: float,
    fck_mpa: float,
    fyk_mpa: float,
    maximum_neutral_axis_ratio: float,
    gamma_c: float = 1.50,
    gamma_s: float = 1.15,
    alpha_cc: float = 1.0,
    lambda_block: float = 0.8,
    es_mpa: float = 200000.0,
    ultimate_concrete_strain: float = 0.0035,
) -> DoublyReinforcedCheckResult:
    """Verify a discrete EC2 top/bottom cage using strain compatibility."""

    positive = (
        effective_depth_m,
        compression_steel_depth_m,
        tension_steel_area_mm2,
        compression_steel_area_mm2,
        fck_mpa,
        fyk_mpa,
        maximum_neutral_axis_ratio,
        gamma_c,
        gamma_s,
        alpha_cc,
        lambda_block,
        es_mpa,
        ultimate_concrete_strain,
    )
    if med_knm < 0.0 or any(value <= 0.0 for value in positive):
        raise ValueError("EC2 doubly reinforced check inputs are invalid.")
    if compression_steel_depth_m >= effective_depth_m:
        raise ValueError("Compression steel must lie above tension steel.")
    if not 0.0 < maximum_neutral_axis_ratio <= 1.0:
        raise ValueError("maximum_neutral_axis_ratio must lie in (0, 1].")
    if not 0.0 < lambda_block <= 1.0:
        raise ValueError("lambda_block must lie in (0, 1].")

    ordered = validate_layers(layers, steel_depth_m=effective_depth_m)
    fyd = fyk_mpa / gamma_s
    concrete_stress = alpha_cc * fck_mpa / gamma_c
    x_upper = maximum_neutral_axis_ratio * effective_depth_m
    if compression_steel_depth_m >= x_upper:
        raise ValueError(
            "Compression cage centroid lies outside the permitted compression zone."
        )
    x_lower = compression_steel_depth_m * (1.0 + 1.0e-9)

    def state(x_m: float):
        area_m2, centroid_m = compression_block_properties(
            ordered,
            block_depth_m=lambda_block * x_m,
        )
        concrete_force_n = concrete_stress * area_m2 * 1.0e6
        compression_strain = ultimate_concrete_strain * (
            x_m - compression_steel_depth_m
        ) / x_m
        tension_strain = ultimate_concrete_strain * (
            effective_depth_m - x_m
        ) / x_m
        compression_stress = min(es_mpa * compression_strain, fyd)
        tension_stress = min(es_mpa * tension_strain, fyd)
        compression_force_n = compression_steel_area_mm2 * compression_stress
        tension_force_n = tension_steel_area_mm2 * tension_stress
        residual_n = concrete_force_n + compression_force_n - tension_force_n
        return (
            residual_n,
            area_m2,
            centroid_m,
            concrete_force_n,
            compression_force_n,
            tension_force_n,
            compression_stress,
            tension_stress,
        )

    x_m = _bisect_force_equilibrium(
        lower_m=x_lower,
        upper_m=x_upper,
        residual=lambda value: state(value)[0],
    )
    (
        residual_n,
        _,
        centroid_m,
        concrete_force_n,
        compression_force_n,
        tension_force_n,
        compression_stress,
        tension_stress,
    ) = state(x_m)
    resistance = (
        concrete_force_n * (effective_depth_m - centroid_m)
        + compression_force_n
        * (effective_depth_m - compression_steel_depth_m)
    ) / 1000.0
    utilization = 0.0 if resistance <= 0.0 and med_knm == 0.0 else med_knm / resistance

    return DoublyReinforcedCheckResult(
        design_moment_knm=med_knm,
        resistance_knm=resistance,
        utilization=utilization,
        neutral_axis_m=x_m,
        effective_depth_m=effective_depth_m,
        compression_steel_depth_m=compression_steel_depth_m,
        tension_steel_area_mm2=tension_steel_area_mm2,
        compression_steel_area_mm2=compression_steel_area_mm2,
        tension_steel_stress_mpa=tension_stress,
        compression_steel_stress_mpa=compression_stress,
        concrete_compression_force_kn=concrete_force_n / 1000.0,
        compression_steel_force_kn=compression_force_n / 1000.0,
        tension_steel_force_kn=tension_force_n / 1000.0,
        force_equilibrium_residual_kn=residual_n / 1000.0,
        passes=resistance + 1.0e-9 >= med_knm,
        basis=(
            "EC2 layered concrete compression block with discrete top and bottom "
            "steel stresses from strain compatibility, capped at fyd."
        ),
    )


def check_doubly_reinforced_bs5400(
    *,
    med_knm: float,
    layers: tuple[ConcreteLayer, ...],
    effective_depth_m: float,
    compression_steel_depth_m: float,
    tension_steel_area_mm2: float,
    compression_steel_area_mm2: float,
    fcu_mpa: float,
    fy_mpa: float,
    maximum_neutral_axis_ratio: float = 0.50,
    maximum_lever_arm_ratio: float = 0.95,
    concrete_block_stress_factor: float = 0.40,
    tension_steel_design_factor: float = 0.87,
    compression_steel_design_factor: float = 0.72,
) -> DoublyReinforcedCheckResult:
    """Verify a discrete BS 5400 top/bottom cage on the repository's legacy basis."""

    positive = (
        effective_depth_m,
        compression_steel_depth_m,
        tension_steel_area_mm2,
        compression_steel_area_mm2,
        fcu_mpa,
        fy_mpa,
        maximum_neutral_axis_ratio,
        maximum_lever_arm_ratio,
        concrete_block_stress_factor,
        tension_steel_design_factor,
        compression_steel_design_factor,
    )
    if med_knm < 0.0 or any(value <= 0.0 for value in positive):
        raise ValueError("BS 5400 doubly reinforced check inputs are invalid.")
    if compression_steel_depth_m >= effective_depth_m:
        raise ValueError("Compression steel must lie above tension steel.")

    ordered = validate_layers(layers, steel_depth_m=effective_depth_m)
    x_upper = maximum_neutral_axis_ratio * effective_depth_m
    if compression_steel_depth_m >= x_upper:
        raise ValueError(
            "Compression cage centroid lies outside the permitted compression zone."
        )
    x_lower = compression_steel_depth_m * (1.0 + 1.0e-9)
    tension_stress = tension_steel_design_factor * fy_mpa
    compression_stress = compression_steel_design_factor * fy_mpa
    concrete_stress = concrete_block_stress_factor * fcu_mpa

    def state(x_m: float):
        area_m2, centroid_m = compression_block_properties(
            ordered,
            block_depth_m=x_m,
        )
        concrete_force_n = concrete_stress * area_m2 * 1.0e6
        compression_force_n = compression_steel_area_mm2 * compression_stress
        tension_force_n = tension_steel_area_mm2 * tension_stress
        residual_n = concrete_force_n + compression_force_n - tension_force_n
        return (
            residual_n,
            centroid_m,
            concrete_force_n,
            compression_force_n,
            tension_force_n,
        )

    x_m = _bisect_force_equilibrium(
        lower_m=x_lower,
        upper_m=x_upper,
        residual=lambda value: state(value)[0],
    )
    (
        residual_n,
        centroid_m,
        concrete_force_n,
        compression_force_n,
        tension_force_n,
    ) = state(x_m)
    concrete_lever = min(
        effective_depth_m - centroid_m,
        maximum_lever_arm_ratio * effective_depth_m,
    )
    resistance = (
        concrete_force_n * concrete_lever
        + compression_force_n
        * (effective_depth_m - compression_steel_depth_m)
    ) / 1000.0
    utilization = 0.0 if resistance <= 0.0 and med_knm == 0.0 else med_knm / resistance

    return DoublyReinforcedCheckResult(
        design_moment_knm=med_knm,
        resistance_knm=resistance,
        utilization=utilization,
        neutral_axis_m=x_m,
        effective_depth_m=effective_depth_m,
        compression_steel_depth_m=compression_steel_depth_m,
        tension_steel_area_mm2=tension_steel_area_mm2,
        compression_steel_area_mm2=compression_steel_area_mm2,
        tension_steel_stress_mpa=tension_stress,
        compression_steel_stress_mpa=compression_stress,
        concrete_compression_force_kn=concrete_force_n / 1000.0,
        compression_steel_force_kn=compression_force_n / 1000.0,
        tension_steel_force_kn=tension_force_n / 1000.0,
        force_equilibrium_residual_kn=residual_n / 1000.0,
        passes=resistance + 1.0e-9 >= med_knm,
        basis=(
            "BS 5400 layered concrete compression block with explicit legacy "
            "design stresses for the discrete top and bottom steel cages."
        ),
    )
