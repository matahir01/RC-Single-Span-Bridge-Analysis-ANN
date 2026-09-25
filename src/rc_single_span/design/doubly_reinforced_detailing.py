from __future__ import annotations

from dataclasses import dataclass

from rc_single_span.analysis.sections import ConcreteLayer
from rc_single_span.design.detailing import (
    LongitudinalBarArrangement,
    generate_longitudinal_bar_arrangements,
    longitudinal_cage_centroid_from_face_m,
    longitudinal_cage_effective_depth_m,
)
from rc_single_span.design.doubly_reinforced import (
    DoublyReinforcedCheckResult,
    DoublyReinforcedRequirement,
    check_doubly_reinforced_bs5400,
    check_doubly_reinforced_ec2,
)


@dataclass(frozen=True)
class DoublyReinforcedCageSelection:
    tension: LongitudinalBarArrangement
    compression: LongitudinalBarArrangement
    actual_effective_depth_m: float
    actual_compression_depth_m: float
    check: DoublyReinforcedCheckResult
    pairs_evaluated: int
    passing_pairs: int
    basis: str


def _candidate_sets(
    *,
    requirement: DoublyReinforcedRequirement,
    tension_width_mm: float,
    compression_width_mm: float,
    cover_mm: float,
    link_diameter_mm: float,
    minimum_clear_spacing_mm: float,
    available_diameters_mm: tuple[float, ...],
    maximum_layers: int,
    preferred_vertical_clear_spacing_mm: float | None,
    diameter_governs_clear_spacing: bool,
) -> tuple[
    tuple[LongitudinalBarArrangement, ...],
    tuple[LongitudinalBarArrangement, ...],
]:
    tension = generate_longitudinal_bar_arrangements(
        minimum_area_mm2=requirement.total_tension_steel_mm2,
        web_width_mm=tension_width_mm,
        cover_mm=cover_mm,
        link_diameter_mm=link_diameter_mm,
        minimum_clear_spacing_mm=minimum_clear_spacing_mm,
        available_diameters_mm=available_diameters_mm,
        maximum_layers=maximum_layers,
        preferred_vertical_clear_spacing_mm=preferred_vertical_clear_spacing_mm,
        diameter_governs_clear_spacing=diameter_governs_clear_spacing,
    )
    compression = generate_longitudinal_bar_arrangements(
        minimum_area_mm2=requirement.compression_steel_mm2,
        web_width_mm=compression_width_mm,
        cover_mm=cover_mm,
        link_diameter_mm=link_diameter_mm,
        minimum_clear_spacing_mm=minimum_clear_spacing_mm,
        available_diameters_mm=available_diameters_mm,
        maximum_layers=maximum_layers,
        preferred_vertical_clear_spacing_mm=preferred_vertical_clear_spacing_mm,
        diameter_governs_clear_spacing=diameter_governs_clear_spacing,
    )
    return tension, compression


def _ranking(item: tuple[LongitudinalBarArrangement, LongitudinalBarArrangement]):
    tension, compression = item
    return (
        tension.layer_count + compression.layer_count,
        tension.bar_count + compression.bar_count,
        tension.provided_area_mm2 + compression.provided_area_mm2,
        compression.layer_count,
        tension.layer_count,
        compression.bar_diameter_mm,
        tension.bar_diameter_mm,
    )


def select_doubly_reinforced_cages_ec2(
    *,
    requirement: DoublyReinforcedRequirement,
    layers: tuple[ConcreteLayer, ...],
    total_depth_m: float,
    tension_width_mm: float,
    compression_width_mm: float,
    cover_mm: float,
    link_diameter_mm: float,
    minimum_clear_spacing_mm: float,
    fck_mpa: float,
    fyk_mpa: float,
    maximum_neutral_axis_ratio: float,
    available_diameters_mm: tuple[float, ...] = (16.0, 20.0, 25.0, 32.0, 40.0),
    maximum_layers: int = 4,
    preferred_vertical_clear_spacing_mm: float | None = None,
    diameter_governs_clear_spacing: bool = True,
    es_mpa: float = 200000.0,
    alpha_cc: float = 1.0,
) -> DoublyReinforcedCageSelection:
    """Select discrete EC2 tension/compression cages and verify actual centroids."""

    if total_depth_m <= 0.0:
        raise ValueError("total_depth_m must be positive.")
    tension_candidates, compression_candidates = _candidate_sets(
        requirement=requirement,
        tension_width_mm=tension_width_mm,
        compression_width_mm=compression_width_mm,
        cover_mm=cover_mm,
        link_diameter_mm=link_diameter_mm,
        minimum_clear_spacing_mm=minimum_clear_spacing_mm,
        available_diameters_mm=available_diameters_mm,
        maximum_layers=maximum_layers,
        preferred_vertical_clear_spacing_mm=preferred_vertical_clear_spacing_mm,
        diameter_governs_clear_spacing=diameter_governs_clear_spacing,
    )

    passing: list[
        tuple[
            LongitudinalBarArrangement,
            LongitudinalBarArrangement,
            float,
            float,
            DoublyReinforcedCheckResult,
        ]
    ] = []
    evaluated = 0
    for tension in tension_candidates:
        d_m = longitudinal_cage_effective_depth_m(
            tension,
            section_total_depth_mm=total_depth_m * 1000.0,
            cover_mm=cover_mm,
            link_diameter_mm=link_diameter_mm,
        )
        for compression in compression_candidates:
            evaluated += 1
            d_prime_m = longitudinal_cage_centroid_from_face_m(
                compression,
                cover_mm=cover_mm,
                link_diameter_mm=link_diameter_mm,
            )
            if d_prime_m >= d_m:
                continue
            try:
                check = check_doubly_reinforced_ec2(
                    med_knm=requirement.design_moment_knm,
                    layers=layers,
                    effective_depth_m=d_m,
                    compression_steel_depth_m=d_prime_m,
                    tension_steel_area_mm2=tension.provided_area_mm2,
                    compression_steel_area_mm2=compression.provided_area_mm2,
                    fck_mpa=fck_mpa,
                    fyk_mpa=fyk_mpa,
                    maximum_neutral_axis_ratio=maximum_neutral_axis_ratio,
                    es_mpa=es_mpa,
                    alpha_cc=alpha_cc,
                )
            except ValueError:
                continue
            if check.passes:
                passing.append((tension, compression, d_m, d_prime_m, check))

    if not passing:
        raise ValueError(
            "No discrete EC2 top/bottom cage pair satisfies the doubly reinforced "
            "ULS check within the configured widths, diameters and layer limits."
        )
    chosen = min(
        passing,
        key=lambda item: _ranking((item[0], item[1])),
    )
    return DoublyReinforcedCageSelection(
        tension=chosen[0],
        compression=chosen[1],
        actual_effective_depth_m=chosen[2],
        actual_compression_depth_m=chosen[3],
        check=chosen[4],
        pairs_evaluated=evaluated,
        passing_pairs=len(passing),
        basis=(
            "Discrete EC2 doubly reinforced cage selection using actual multilayer "
            "top/bottom steel centroids and a final strain-compatible ULS recheck."
        ),
    )


def select_doubly_reinforced_cages_bs5400(
    *,
    requirement: DoublyReinforcedRequirement,
    layers: tuple[ConcreteLayer, ...],
    total_depth_m: float,
    tension_width_mm: float,
    compression_width_mm: float,
    cover_mm: float,
    link_diameter_mm: float,
    minimum_clear_spacing_mm: float,
    fcu_mpa: float,
    fy_mpa: float,
    available_diameters_mm: tuple[float, ...] = (16.0, 20.0, 25.0, 32.0, 40.0),
    maximum_layers: int = 4,
    preferred_vertical_clear_spacing_mm: float | None = None,
    diameter_governs_clear_spacing: bool = False,
) -> DoublyReinforcedCageSelection:
    """Select discrete BS 5400 tension/compression cages and verify actual centroids."""

    if total_depth_m <= 0.0:
        raise ValueError("total_depth_m must be positive.")
    tension_candidates, compression_candidates = _candidate_sets(
        requirement=requirement,
        tension_width_mm=tension_width_mm,
        compression_width_mm=compression_width_mm,
        cover_mm=cover_mm,
        link_diameter_mm=link_diameter_mm,
        minimum_clear_spacing_mm=minimum_clear_spacing_mm,
        available_diameters_mm=available_diameters_mm,
        maximum_layers=maximum_layers,
        preferred_vertical_clear_spacing_mm=preferred_vertical_clear_spacing_mm,
        diameter_governs_clear_spacing=diameter_governs_clear_spacing,
    )

    passing: list[
        tuple[
            LongitudinalBarArrangement,
            LongitudinalBarArrangement,
            float,
            float,
            DoublyReinforcedCheckResult,
        ]
    ] = []
    evaluated = 0
    for tension in tension_candidates:
        d_m = longitudinal_cage_effective_depth_m(
            tension,
            section_total_depth_mm=total_depth_m * 1000.0,
            cover_mm=cover_mm,
            link_diameter_mm=link_diameter_mm,
        )
        for compression in compression_candidates:
            evaluated += 1
            d_prime_m = longitudinal_cage_centroid_from_face_m(
                compression,
                cover_mm=cover_mm,
                link_diameter_mm=link_diameter_mm,
            )
            if d_prime_m >= d_m:
                continue
            try:
                check = check_doubly_reinforced_bs5400(
                    med_knm=requirement.design_moment_knm,
                    layers=layers,
                    effective_depth_m=d_m,
                    compression_steel_depth_m=d_prime_m,
                    tension_steel_area_mm2=tension.provided_area_mm2,
                    compression_steel_area_mm2=compression.provided_area_mm2,
                    fcu_mpa=fcu_mpa,
                    fy_mpa=fy_mpa,
                )
            except ValueError:
                continue
            if check.passes:
                passing.append((tension, compression, d_m, d_prime_m, check))

    if not passing:
        raise ValueError(
            "No discrete BS 5400 top/bottom cage pair satisfies the doubly reinforced "
            "ULS check within the configured widths, diameters and layer limits."
        )
    chosen = min(
        passing,
        key=lambda item: _ranking((item[0], item[1])),
    )
    return DoublyReinforcedCageSelection(
        tension=chosen[0],
        compression=chosen[1],
        actual_effective_depth_m=chosen[2],
        actual_compression_depth_m=chosen[3],
        check=chosen[4],
        pairs_evaluated=evaluated,
        passing_pairs=len(passing),
        basis=(
            "Discrete BS 5400 doubly reinforced cage selection using actual multilayer "
            "top/bottom steel centroids and a final combined ULS recheck."
        ),
    )
