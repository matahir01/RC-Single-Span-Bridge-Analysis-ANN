from __future__ import annotations

from dataclasses import dataclass
from math import ceil, pi

from rc_single_span.core.models import LongitudinalReinforcement


@dataclass(frozen=True)
class LongitudinalBarArrangement:
    bar_diameter_mm: float
    bar_count: int
    layer_count: int
    bars_per_layer: tuple[int, ...]
    provided_area_mm2: float
    clear_horizontal_spacing_mm: float
    clear_vertical_spacing_mm: float
    minimum_clear_spacing_mm: float
    fits_web: bool


@dataclass(frozen=True)
class LinkArrangement:
    link_diameter_mm: float
    leg_count: int
    spacing_mm: float
    provided_asw_per_s_mm2_per_m: float
    transverse_leg_spacing_mm: float
    satisfies_required_area: bool
    satisfies_longitudinal_spacing: bool
    satisfies_transverse_leg_spacing: bool


@dataclass(frozen=True)
class ProvidedLayerFit:
    layer_index: int
    bar_count: int
    bar_diameter_mm: float
    clear_horizontal_spacing_mm: float
    minimum_clear_spacing_mm: float
    horizontal_fit: bool


@dataclass(frozen=True)
class ProvidedCageAudit:
    available_inside_link_width_mm: float
    available_inside_link_depth_mm: float | None
    layer_checks: tuple[ProvidedLayerFit, ...]
    provided_vertical_clear_spacing_mm: float | None
    minimum_vertical_clear_spacing_mm: float
    required_stack_depth_mm: float | None
    horizontal_fit: bool
    vertical_spacing_ok: bool | None
    vertical_fit: bool | None
    passes: bool | None
    status: str


def bar_area_mm2(diameter_mm: float) -> float:
    if diameter_mm <= 0.0:
        raise ValueError("Bar diameter must be positive.")
    return pi * diameter_mm**2 / 4.0


def select_longitudinal_bar_arrangement(
    *,
    required_area_mm2: float,
    web_width_mm: float,
    cover_mm: float,
    link_diameter_mm: float,
    minimum_clear_spacing_mm: float,
    available_diameters_mm: tuple[float, ...] = (16.0, 20.0, 25.0, 32.0, 40.0),
    maximum_layers: int = 4,
    preferred_vertical_clear_spacing_mm: float | None = None,
) -> LongitudinalBarArrangement:
    """Choose the least-area unbundled arrangement satisfying explicit cage geometry."""

    if min(
        required_area_mm2,
        web_width_mm,
        cover_mm,
        link_diameter_mm,
        minimum_clear_spacing_mm,
    ) <= 0.0:
        raise ValueError("Longitudinal bar-selection inputs must be positive.")
    if maximum_layers < 1:
        raise ValueError("maximum_layers must be at least one.")
    if not available_diameters_mm or any(value <= 0.0 for value in available_diameters_mm):
        raise ValueError("available_diameters_mm must contain positive values.")
    if (
        preferred_vertical_clear_spacing_mm is not None
        and preferred_vertical_clear_spacing_mm <= 0.0
    ):
        raise ValueError("preferred_vertical_clear_spacing_mm must be positive.")

    clear_width = web_width_mm - 2.0 * (cover_mm + link_diameter_mm)
    if clear_width <= 0.0:
        raise ValueError("Cover and links leave no width for longitudinal bars.")

    candidates: list[LongitudinalBarArrangement] = []
    for diameter in sorted(set(available_diameters_mm)):
        area = bar_area_mm2(diameter)
        count = max(2, ceil(required_area_mm2 / area))
        minimum_clear = max(minimum_clear_spacing_mm, diameter)
        maximum_per_layer = int(
            (clear_width + minimum_clear) // (diameter + minimum_clear)
        )
        if maximum_per_layer < 2:
            continue

        layers = ceil(count / maximum_per_layer)
        if layers > maximum_layers:
            continue
        distribution = [count // layers] * layers
        for index in range(count % layers):
            distribution[index] += 1
        if min(distribution) < 2:
            continue

        governing_count = max(distribution)
        horizontal_clear = (
            (clear_width - governing_count * diameter) / (governing_count - 1)
            if governing_count > 1
            else clear_width - diameter
        )
        if horizontal_clear + 1.0e-9 < minimum_clear:
            continue

        vertical_clear = max(
            minimum_clear,
            preferred_vertical_clear_spacing_mm or minimum_clear,
        )
        candidates.append(
            LongitudinalBarArrangement(
                bar_diameter_mm=diameter,
                bar_count=count,
                layer_count=layers,
                bars_per_layer=tuple(distribution),
                provided_area_mm2=count * area,
                clear_horizontal_spacing_mm=horizontal_clear,
                clear_vertical_spacing_mm=vertical_clear,
                minimum_clear_spacing_mm=minimum_clear,
                fits_web=True,
            )
        )

    if not candidates:
        raise ValueError(
            "No unbundled longitudinal-bar arrangement fits the web, cover and layer limits."
        )
    return min(
        candidates,
        key=lambda item: (
            item.provided_area_mm2,
            item.layer_count,
            item.bar_count,
            item.bar_diameter_mm,
        ),
    )


def select_vertical_link_arrangement(
    *,
    required_asw_per_s_mm2_per_m: float,
    web_width_mm: float,
    maximum_longitudinal_spacing_mm: float,
    cover_mm: float,
    maximum_transverse_leg_spacing_mm: float | None = None,
    available_diameters_mm: tuple[float, ...] = (8.0, 10.0, 12.0, 16.0),
    available_legs: tuple[int, ...] = (2, 4, 6),
    available_spacings_mm: tuple[float, ...] = (
        300.0,
        250.0,
        225.0,
        200.0,
        175.0,
        150.0,
        125.0,
        100.0,
    ),
) -> LinkArrangement:
    """Choose a discrete closed-link arrangement from explicit area/spacing limits."""

    if min(
        required_asw_per_s_mm2_per_m,
        web_width_mm,
        maximum_longitudinal_spacing_mm,
        cover_mm,
    ) <= 0.0:
        raise ValueError("Link-selection inputs must be positive.")
    if (
        maximum_transverse_leg_spacing_mm is not None
        and maximum_transverse_leg_spacing_mm <= 0.0
    ):
        raise ValueError("maximum_transverse_leg_spacing_mm must be positive.")
    if not available_diameters_mm or not available_legs or not available_spacings_mm:
        raise ValueError("Available link options cannot be empty.")

    candidates: list[LinkArrangement] = []
    for diameter in sorted(set(available_diameters_mm)):
        for legs in sorted(set(available_legs)):
            if legs < 2 or legs % 2:
                continue
            inside_width = web_width_mm - 2.0 * (cover_mm + diameter)
            if inside_width <= 0.0:
                continue
            transverse_spacing = inside_width / (legs - 1)
            transverse_ok = (
                True
                if maximum_transverse_leg_spacing_mm is None
                else transverse_spacing
                <= maximum_transverse_leg_spacing_mm + 1.0e-9
            )
            if not transverse_ok:
                continue

            asw_mm2 = legs * bar_area_mm2(diameter)
            for spacing in sorted(set(available_spacings_mm), reverse=True):
                if spacing <= 0.0:
                    continue
                provided = asw_mm2 / spacing * 1000.0
                area_ok = provided + 1.0e-9 >= required_asw_per_s_mm2_per_m
                longitudinal_ok = (
                    spacing <= maximum_longitudinal_spacing_mm + 1.0e-9
                )
                if not area_ok or not longitudinal_ok:
                    continue
                candidates.append(
                    LinkArrangement(
                        link_diameter_mm=diameter,
                        leg_count=legs,
                        spacing_mm=spacing,
                        provided_asw_per_s_mm2_per_m=provided,
                        transverse_leg_spacing_mm=transverse_spacing,
                        satisfies_required_area=area_ok,
                        satisfies_longitudinal_spacing=longitudinal_ok,
                        satisfies_transverse_leg_spacing=transverse_ok,
                    )
                )

    if not candidates:
        raise ValueError(
            "No available vertical-link arrangement satisfies area and spacing requirements."
        )
    return min(
        candidates,
        key=lambda item: (
            item.provided_asw_per_s_mm2_per_m,
            item.link_diameter_mm,
            item.leg_count,
            -item.spacing_mm,
        ),
    )


def audit_provided_longitudinal_cage(
    *,
    reinforcement: LongitudinalReinforcement,
    web_width_mm: float,
    cover_mm: float,
    link_diameter_mm: float,
    minimum_clear_spacing_mm: float,
    section_total_depth_mm: float | None = None,
    provided_vertical_clear_spacing_mm: float | None = None,
) -> ProvidedCageAudit:
    """Audit the stored bar layers without inventing missing vertical spacing."""

    if min(
        web_width_mm,
        cover_mm,
        link_diameter_mm,
        minimum_clear_spacing_mm,
    ) <= 0.0:
        raise ValueError("Provided-cage geometry must be positive.")
    if section_total_depth_mm is not None and section_total_depth_mm <= 0.0:
        raise ValueError("section_total_depth_mm must be positive.")
    if (
        provided_vertical_clear_spacing_mm is not None
        and provided_vertical_clear_spacing_mm <= 0.0
    ):
        raise ValueError("provided_vertical_clear_spacing_mm must be positive.")

    inside_width = web_width_mm - 2.0 * (cover_mm + link_diameter_mm)
    if inside_width <= 0.0:
        raise ValueError("Cover and links leave no width for the provided cage.")

    layer_checks: list[ProvidedLayerFit] = []
    for index, layer in enumerate(reinforcement.layers, start=1):
        count = int(layer.count)
        diameter = float(layer.diameter_mm)
        minimum_clear = max(minimum_clear_spacing_mm, diameter)
        clear = (
            (inside_width - count * diameter) / (count - 1)
            if count > 1
            else inside_width - diameter
        )
        layer_checks.append(
            ProvidedLayerFit(
                layer_index=index,
                bar_count=count,
                bar_diameter_mm=diameter,
                clear_horizontal_spacing_mm=clear,
                minimum_clear_spacing_mm=minimum_clear,
                horizontal_fit=clear + 1.0e-9 >= minimum_clear,
            )
        )

    horizontal_fit = all(item.horizontal_fit for item in layer_checks)
    maximum_diameter = max(float(layer.diameter_mm) for layer in reinforcement.layers)
    minimum_vertical = max(minimum_clear_spacing_mm, maximum_diameter)

    available_depth: float | None = None
    required_stack: float | None = None
    vertical_spacing_ok: bool | None = None
    vertical_fit: bool | None = None
    if section_total_depth_mm is not None:
        available_depth = section_total_depth_mm - 2.0 * (
            cover_mm + link_diameter_mm
        )
        if available_depth <= 0.0:
            raise ValueError("Cover and links leave no depth for the provided cage.")
    if provided_vertical_clear_spacing_mm is not None:
        vertical_spacing_ok = (
            provided_vertical_clear_spacing_mm + 1.0e-9 >= minimum_vertical
        )
        required_stack = (
            sum(float(layer.diameter_mm) for layer in reinforcement.layers)
            + max(len(reinforcement.layers) - 1, 0)
            * provided_vertical_clear_spacing_mm
        )
        if available_depth is not None:
            vertical_fit = required_stack <= available_depth + 1.0e-9

    if not horizontal_fit:
        passes: bool | None = False
    elif vertical_spacing_ok is False or vertical_fit is False:
        passes = False
    elif vertical_spacing_ok is None or (
        available_depth is not None and vertical_fit is None
    ):
        passes = None
    else:
        passes = True

    unresolved = (
        provided_vertical_clear_spacing_mm is None
        or (section_total_depth_mm is not None and vertical_fit is None)
    )
    return ProvidedCageAudit(
        available_inside_link_width_mm=inside_width,
        available_inside_link_depth_mm=available_depth,
        layer_checks=tuple(layer_checks),
        provided_vertical_clear_spacing_mm=provided_vertical_clear_spacing_mm,
        minimum_vertical_clear_spacing_mm=minimum_vertical,
        required_stack_depth_mm=required_stack,
        horizontal_fit=horizontal_fit,
        vertical_spacing_ok=vertical_spacing_ok,
        vertical_fit=vertical_fit,
        passes=passes,
        status=(
            "Horizontal bar fit checked from the stored layer counts and diameters. "
            + (
                "Vertical layer spacing remains unresolved because it was not supplied."
                if unresolved
                else "Vertical clear spacing and total cage depth were checked."
            )
        ),
    )
