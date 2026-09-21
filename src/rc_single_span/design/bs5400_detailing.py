from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BS5400DetailingLimits:
    minimum_main_steel_mm2: float
    maximum_main_steel_mm2: float
    adopted_minimum_main_ratio: float
    minimum_main_ratio_basis: str
    side_face_reinforcement_required: bool
    minimum_side_face_steel_each_face_mm2: float
    minimum_clear_bar_spacing_mm: float
    maximum_tension_bar_spacing_mm: float
    maximum_link_spacing_mm: float


def minimum_main_ratio_bs5400(
    *,
    reinforcement_grade_mpa: float,
    adopted_minimum_main_ratio: float | None = None,
) -> tuple[float, str]:
    """Return the adopted BS 5400 minimum-main-steel ratio without grade remapping."""

    if reinforcement_grade_mpa <= 0.0:
        raise ValueError("reinforcement_grade_mpa must be positive.")
    if adopted_minimum_main_ratio is not None:
        if adopted_minimum_main_ratio <= 0.0:
            raise ValueError("adopted_minimum_main_ratio must be positive.")
        return (
            adopted_minimum_main_ratio,
            "explicit project/edition minimum-main-steel ratio",
        )
    if abs(reinforcement_grade_mpa - 460.0) <= 1.0e-9:
        return 0.0015, "legacy Grade 460 default"
    if abs(reinforcement_grade_mpa - 250.0) <= 1.0e-9:
        return 0.0025, "legacy Grade 250 default"
    raise ValueError(
        "BS 5400 minimum-main-steel ratio is not inferred for this reinforcement grade. "
        "Supply adopted_minimum_main_ratio explicitly; the physical grade is not remapped."
    )


def detailing_limits_bs5400(
    *,
    average_breadth_excluding_compression_flange_m: float,
    effective_depth_m: float,
    gross_concrete_area_m2: float,
    reinforcement_grade_mpa: float,
    side_face_depth_m: float,
    side_face_breadth_m: float,
    maximum_aggregate_size_mm: float,
    adopted_minimum_main_ratio: float | None = None,
    maximum_main_ratio: float = 0.04,
    side_face_ratio: float = 0.0005,
    maximum_tension_bar_spacing_mm: float = 300.0,
    maximum_link_spacing_factor: float = 0.75,
) -> BS5400DetailingLimits:
    values = (
        average_breadth_excluding_compression_flange_m,
        effective_depth_m,
        gross_concrete_area_m2,
        reinforcement_grade_mpa,
        side_face_depth_m,
        side_face_breadth_m,
        maximum_aggregate_size_mm,
        maximum_main_ratio,
        side_face_ratio,
        maximum_tension_bar_spacing_mm,
        maximum_link_spacing_factor,
    )
    if any(value <= 0.0 for value in values):
        raise ValueError("BS 5400 detailing inputs must be positive.")

    ratio, basis = minimum_main_ratio_bs5400(
        reinforcement_grade_mpa=reinforcement_grade_mpa,
        adopted_minimum_main_ratio=adopted_minimum_main_ratio,
    )
    ba_mm = average_breadth_excluding_compression_flange_m * 1000.0
    d_mm = effective_depth_m * 1000.0
    gross_area_mm2 = gross_concrete_area_m2 * 1_000_000.0
    side_breadth_mm = side_face_breadth_m * 1000.0
    side_required = side_face_depth_m > 0.60
    minimum_side = (
        side_face_ratio * side_breadth_mm * d_mm
        if side_required
        else 0.0
    )

    return BS5400DetailingLimits(
        minimum_main_steel_mm2=ratio * ba_mm * d_mm,
        maximum_main_steel_mm2=maximum_main_ratio * gross_area_mm2,
        adopted_minimum_main_ratio=ratio,
        minimum_main_ratio_basis=basis,
        side_face_reinforcement_required=side_required,
        minimum_side_face_steel_each_face_mm2=minimum_side,
        minimum_clear_bar_spacing_mm=maximum_aggregate_size_mm + 5.0,
        maximum_tension_bar_spacing_mm=maximum_tension_bar_spacing_mm,
        maximum_link_spacing_mm=maximum_link_spacing_factor * d_mm,
    )
