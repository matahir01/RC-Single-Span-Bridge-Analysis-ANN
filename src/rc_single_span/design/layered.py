from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise

from rc_single_span.analysis.sections import ConcreteLayer


@dataclass(frozen=True)
class LayeredCompressionResistance:
    resistance_knm: float
    neutral_axis_from_top_m: float
    compression_block_depth_m: float
    compression_centroid_from_top_m: float
    lever_arm_m: float
    steel_force_kn: float


@dataclass(frozen=True)
class LayeredUncrackedSection:
    transformed_area_mm2: float
    neutral_axis_from_top_mm: float
    second_moment_mm4: float
    cracking_moment_knm: float


@dataclass(frozen=True)
class LayeredCrackedSection:
    neutral_axis_from_top_mm: float
    second_moment_mm4: float
    steel_stress_mpa: float


def validate_layers(
    layers: tuple[ConcreteLayer, ...],
    *,
    steel_depth_m: float,
) -> tuple[ConcreteLayer, ...]:
    if not layers:
        raise ValueError("Layered section requires at least one participating concrete layer.")
    if steel_depth_m <= 0.0:
        raise ValueError("steel_depth_m must be positive.")
    ordered = tuple(sorted(layers, key=lambda item: (item.top_m, item.bottom_m)))
    for previous, current in pairwise(ordered):
        if current.top_m < previous.bottom_m - 1.0e-12:
            raise ValueError("Participating concrete layers must not overlap.")
    if steel_depth_m > max(item.bottom_m for item in ordered) + 1.0e-12:
        raise ValueError("Tension steel lies outside the layered section.")
    return ordered


def layer_overlap(
    layer: ConcreteLayer,
    *,
    top_m: float,
    bottom_m: float,
) -> tuple[float, float, float] | None:
    overlap_top = max(layer.top_m, top_m)
    overlap_bottom = min(layer.bottom_m, bottom_m)
    if overlap_bottom <= overlap_top:
        return None
    depth = overlap_bottom - overlap_top
    area = layer.width_m * depth
    centroid = 0.5 * (overlap_top + overlap_bottom)
    return area, centroid, depth


def compression_block_properties(
    layers: tuple[ConcreteLayer, ...],
    *,
    block_depth_m: float,
) -> tuple[float, float]:
    pieces: list[tuple[float, float]] = []
    for layer in layers:
        overlap = layer_overlap(layer, top_m=0.0, bottom_m=block_depth_m)
        if overlap is None:
            continue
        area, centroid, _ = overlap
        pieces.append((area, centroid))
    area = sum(item[0] for item in pieces)
    if area <= 0.0:
        return 0.0, 0.0
    centroid = sum(item_area * y for item_area, y in pieces) / area
    return area, centroid


def layered_compression_resistance(
    *,
    layers: tuple[ConcreteLayer, ...],
    effective_depth_m: float,
    steel_force_n: float,
    concrete_block_stress_mpa: float,
    neutral_axis_block_ratio: float,
    maximum_neutral_axis_ratio: float | None = None,
    maximum_lever_arm_ratio: float | None = None,
) -> LayeredCompressionResistance:
    """Resolve a rectangular compression block against actual concrete bands.

    The concrete bands may contain physical gaps. This keeps a non-participating
    false slab out of resistance while preserving the true depth of the precast
    girder below it.
    """

    ordered = validate_layers(layers, steel_depth_m=effective_depth_m)
    if steel_force_n <= 0.0 or concrete_block_stress_mpa <= 0.0:
        raise ValueError("Steel force and concrete block stress must be positive.")
    if not 0.0 < neutral_axis_block_ratio <= 1.0:
        raise ValueError("neutral_axis_block_ratio must lie in (0, 1].")
    if maximum_neutral_axis_ratio is not None and not 0.0 < maximum_neutral_axis_ratio <= 1.0:
        raise ValueError("maximum_neutral_axis_ratio must lie in (0, 1].")
    if maximum_lever_arm_ratio is not None and not 0.0 < maximum_lever_arm_ratio <= 1.0:
        raise ValueError("maximum_lever_arm_ratio must lie in (0, 1].")

    required_area_m2 = steel_force_n / (concrete_block_stress_mpa * 1.0e6)
    upper = min(effective_depth_m, max(item.bottom_m for item in ordered))
    maximum_area, _ = compression_block_properties(ordered, block_depth_m=upper)
    if required_area_m2 > maximum_area + 1.0e-12:
        raise ValueError(
            "Required compression force exceeds participating concrete above the tension steel."
        )

    lower = 0.0
    for _ in range(120):
        mid = 0.5 * (lower + upper)
        area, _ = compression_block_properties(ordered, block_depth_m=mid)
        if area < required_area_m2:
            lower = mid
        else:
            upper = mid
    block_depth = upper
    area, centroid = compression_block_properties(ordered, block_depth_m=block_depth)
    if area <= 0.0:
        raise ValueError("Compression block contains no participating concrete.")

    neutral_axis = block_depth / neutral_axis_block_ratio
    if (
        maximum_neutral_axis_ratio is not None
        and neutral_axis > maximum_neutral_axis_ratio * effective_depth_m + 1.0e-12
    ):
        raise ValueError(
            "Neutral axis exceeds the configured singly reinforced section limit."
        )
    lever_arm = effective_depth_m - centroid
    if maximum_lever_arm_ratio is not None:
        lever_arm = min(lever_arm, maximum_lever_arm_ratio * effective_depth_m)
    if lever_arm <= 0.0:
        raise ValueError("Calculated lever arm is non-positive.")

    return LayeredCompressionResistance(
        resistance_knm=steel_force_n * lever_arm / 1000.0,
        neutral_axis_from_top_m=neutral_axis,
        compression_block_depth_m=block_depth,
        compression_centroid_from_top_m=centroid,
        lever_arm_m=lever_arm,
        steel_force_kn=steel_force_n / 1000.0,
    )


def uncracked_layered_section(
    *,
    layers: tuple[ConcreteLayer, ...],
    steel_area_mm2: float,
    steel_depth_m: float,
    modular_ratio: float,
    fct_eff_mpa: float,
) -> LayeredUncrackedSection:
    ordered = validate_layers(layers, steel_depth_m=steel_depth_m)
    if min(steel_area_mm2, modular_ratio, fct_eff_mpa) <= 0.0:
        raise ValueError("Uncracked section inputs must be positive.")

    concrete_area_mm2 = sum(item.area_m2 for item in ordered) * 1.0e6
    transformed_steel_area = modular_ratio * steel_area_mm2
    transformed_area = concrete_area_mm2 + transformed_steel_area
    concrete_first = sum(
        item.area_m2 * 1.0e6 * item.centroid_from_top_m * 1000.0
        for item in ordered
    )
    steel_y_mm = steel_depth_m * 1000.0
    neutral_axis = (
        concrete_first + transformed_steel_area * steel_y_mm
    ) / transformed_area

    inertia = 0.0
    for item in ordered:
        width_mm = item.width_m * 1000.0
        depth_mm = item.depth_m * 1000.0
        area_mm2 = item.area_m2 * 1.0e6
        y_mm = item.centroid_from_top_m * 1000.0
        inertia += (
            width_mm * depth_mm**3 / 12.0
            + area_mm2 * (y_mm - neutral_axis) ** 2
        )
    inertia += transformed_steel_area * (steel_y_mm - neutral_axis) ** 2

    bottom_mm = max(item.bottom_m for item in ordered) * 1000.0
    tensile_distance = bottom_mm - neutral_axis
    if inertia <= 0.0 or tensile_distance <= 0.0:
        raise ValueError("Invalid uncracked layered-section properties.")

    return LayeredUncrackedSection(
        transformed_area_mm2=transformed_area,
        neutral_axis_from_top_mm=neutral_axis,
        second_moment_mm4=inertia,
        cracking_moment_knm=fct_eff_mpa * inertia / tensile_distance / 1.0e6,
    )


def cracked_layered_section(
    *,
    layers: tuple[ConcreteLayer, ...],
    steel_area_mm2: float,
    steel_depth_m: float,
    modular_ratio: float,
    service_moment_knm: float,
) -> LayeredCrackedSection:
    ordered = validate_layers(layers, steel_depth_m=steel_depth_m)
    if min(steel_area_mm2, modular_ratio) <= 0.0 or service_moment_knm < 0.0:
        raise ValueError("Cracked section inputs are invalid.")

    d_mm = steel_depth_m * 1000.0
    transformed_steel_area = modular_ratio * steel_area_mm2

    def equilibrium(x_mm: float) -> float:
        x_m = x_mm / 1000.0
        concrete_first = 0.0
        for item in ordered:
            overlap = layer_overlap(item, top_m=0.0, bottom_m=x_m)
            if overlap is None:
                continue
            area_m2, centroid_m, _ = overlap
            concrete_first += area_m2 * 1.0e6 * (x_mm - centroid_m * 1000.0)
        return concrete_first - transformed_steel_area * (d_mm - x_mm)

    lower = 1.0e-6
    upper = d_mm - 1.0e-6
    if equilibrium(lower) >= 0.0 or equilibrium(upper) <= 0.0:
        raise ValueError("Unable to bracket cracked layered-section neutral axis.")
    for _ in range(120):
        mid = 0.5 * (lower + upper)
        if equilibrium(mid) < 0.0:
            lower = mid
        else:
            upper = mid
    x_mm = 0.5 * (lower + upper)
    x_m = x_mm / 1000.0

    inertia = 0.0
    for item in ordered:
        overlap = layer_overlap(item, top_m=0.0, bottom_m=x_m)
        if overlap is None:
            continue
        area_m2, centroid_m, depth_m = overlap
        width_mm = item.width_m * 1000.0
        depth_mm = depth_m * 1000.0
        area_mm2 = area_m2 * 1.0e6
        centroid_mm = centroid_m * 1000.0
        inertia += (
            width_mm * depth_mm**3 / 12.0
            + area_mm2 * (x_mm - centroid_mm) ** 2
        )
    inertia += transformed_steel_area * (d_mm - x_mm) ** 2
    if inertia <= 0.0:
        raise ValueError("Calculated cracked second moment is non-positive.")

    steel_stress = (
        modular_ratio * service_moment_knm * 1.0e6 * (d_mm - x_mm) / inertia
    )
    return LayeredCrackedSection(
        neutral_axis_from_top_mm=x_mm,
        second_moment_mm4=inertia,
        steel_stress_mpa=steel_stress,
    )


def effective_tension_depth_mm(
    *,
    total_depth_m: float,
    steel_depth_m: float,
    neutral_axis_from_top_mm: float,
) -> float:
    h = total_depth_m * 1000.0
    d = steel_depth_m * 1000.0
    x = neutral_axis_from_top_mm
    if not 0.0 < d < h or not 0.0 < x < h:
        raise ValueError("Steel depth and neutral axis must lie inside the section.")
    return min(2.5 * (h - d), (h - x) / 3.0, h / 2.0)


def effective_tension_area_mm2(
    *,
    layers: tuple[ConcreteLayer, ...],
    total_depth_m: float,
    effective_tension_depth_mm_value: float,
) -> float:
    if total_depth_m <= 0.0 or effective_tension_depth_mm_value <= 0.0:
        raise ValueError("Effective tension-zone inputs must be positive.")
    top_m = total_depth_m - effective_tension_depth_mm_value / 1000.0
    area = 0.0
    for item in layers:
        overlap = layer_overlap(item, top_m=top_m, bottom_m=total_depth_m)
        if overlap is not None:
            area += overlap[0] * 1.0e6
    if area <= 0.0:
        raise ValueError("Effective tension zone contains no participating concrete.")
    return area
