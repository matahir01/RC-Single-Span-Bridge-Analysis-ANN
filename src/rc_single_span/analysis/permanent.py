from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rc_single_span.analysis.sections import (
    girder_tributary_bands_m,
    girder_tributary_widths_m,
    girder_y_positions_m,
)
from rc_single_span.analysis.simple_span import (
    DistributedLoadSegment,
    simple_span_distributed_load_response,
)
from rc_single_span.codes.common import LoadEffects
from rc_single_span.core.models import BridgeProject, PermanentActionStage


class PermanentLoadCategory(str, Enum):
    STRUCTURAL_DEAD = "structural_dead"
    SURFACING = "surfacing"
    OTHER_SUPERIMPOSED = "other_superimposed"


@dataclass(frozen=True)
class PermanentLoadSegment:
    girder_index: int
    stage: PermanentActionStage
    magnitude_kn_m: float
    x_start_m: float
    x_end_m: float
    source: str
    category: PermanentLoadCategory = PermanentLoadCategory.STRUCTURAL_DEAD

    @property
    def total_load_kn(self) -> float:
        return self.magnitude_kn_m * (self.x_end_m - self.x_start_m)


def _line_action_shares(
    y_m: float,
    positions: tuple[float, ...],
) -> tuple[tuple[int, float], ...]:
    if y_m <= positions[0]:
        return ((1, 1.0),)
    if y_m >= positions[-1]:
        return ((len(positions), 1.0),)
    for index in range(len(positions) - 1):
        left, right = positions[index], positions[index + 1]
        if left <= y_m <= right:
            ratio = (y_m - left) / (right - left)
            return ((index + 1, 1.0 - ratio), (index + 2, ratio))
    raise RuntimeError("Line action could not be assigned to the girder layout.")


def automatic_permanent_loads(project: BridgeProject) -> tuple[PermanentLoadSegment, ...]:
    geometry = project.geometry
    span = float(geometry.span_m)
    density = float(project.materials.concrete_density_kn_m3)
    widths = girder_tributary_widths_m(geometry)
    bands = girder_tributary_bands_m(geometry)
    positions = girder_y_positions_m(geometry)
    segments: list[PermanentLoadSegment] = []

    girder_self_weight = float(geometry.girder_profile.area_m2) * density
    false_depth = float(geometry.deck.precast_false_slab_depth_m)
    wet_depth = float(geometry.deck.in_situ_slab_depth_m)

    for girder_index, tributary_width in enumerate(widths, start=1):
        segments.append(
            PermanentLoadSegment(
                girder_index,
                PermanentActionStage.PRECAST_GIRDER,
                girder_self_weight,
                0.0,
                span,
                "precast girder self-weight",
            )
        )
        segments.append(
            PermanentLoadSegment(
                girder_index,
                PermanentActionStage.PRECAST_GIRDER,
                tributary_width * false_depth * density,
                0.0,
                span,
                "precast false-slab self-weight",
            )
        )
        segments.append(
            PermanentLoadSegment(
                girder_index,
                PermanentActionStage.DECK_CONSTRUCTION,
                tributary_width * wet_depth * density,
                0.0,
                span,
                "wet in-situ deck self-weight",
            )
        )

    for layer in project.permanent_actions.surfacing_layers:
        x_end = span if layer.x_end_m is None else float(layer.x_end_m)
        for girder_index, (band_left, band_right) in enumerate(bands, start=1):
            overlap = max(
                0.0,
                min(float(layer.y_end_m), band_right)
                - max(float(layer.y_start_m), band_left),
            )
            if overlap <= 0.0:
                continue
            segments.append(
                PermanentLoadSegment(
                    girder_index,
                    layer.stage,
                    layer.pressure_kn_m2 * overlap,
                    float(layer.x_start_m),
                    x_end,
                    layer.name,
                    category=PermanentLoadCategory.SURFACING,
                )
            )

    for action in project.permanent_actions.line_actions:
        x_end = span if action.x_end_m is None else float(action.x_end_m)
        for girder_index, share in _line_action_shares(float(action.y_m), positions):
            if share <= 0.0:
                continue
            segments.append(
                PermanentLoadSegment(
                    girder_index,
                    action.stage,
                    float(action.magnitude_kn_m) * share,
                    float(action.x_start_m),
                    x_end,
                    action.name,
                    category=PermanentLoadCategory.OTHER_SUPERIMPOSED,
                )
            )

    return tuple(segment for segment in segments if segment.magnitude_kn_m > 0.0)



def _distributed_segments(
    segments: tuple[PermanentLoadSegment, ...],
    *,
    factors_by_category: dict[PermanentLoadCategory, float] | None = None,
) -> tuple[DistributedLoadSegment, ...]:
    factors = factors_by_category or {}
    return tuple(
        DistributedLoadSegment(
            magnitude_kn_m=segment.magnitude_kn_m
            * factors.get(segment.category, 1.0),
            start_m=segment.x_start_m,
            end_m=segment.x_end_m,
            label=f"{segment.category.value}: {segment.source}",
        )
        for segment in segments
    )


def characteristic_permanent_effects(
    project: BridgeProject,
    *,
    girder_index: int,
) -> LoadEffects:
    """Return the characteristic permanent M/V envelope for one girder."""

    if not 1 <= girder_index <= int(project.geometry.girder_count):
        raise IndexError("girder_index is outside the bridge layout.")
    segments = tuple(
        item
        for item in automatic_permanent_loads(project)
        if item.girder_index == girder_index
    )
    response = simple_span_distributed_load_response(
        float(project.geometry.span_m),
        _distributed_segments(segments),
    )
    return LoadEffects(
        moment_knm=response.max_moment_knm,
        shear_kn=response.max_abs_shear_kn,
    )


def characteristic_permanent_effects_by_category(
    project: BridgeProject,
    *,
    girder_index: int,
) -> dict[PermanentLoadCategory, LoadEffects]:
    """Return auditable characteristic permanent effects split by BS load class."""

    if not 1 <= girder_index <= int(project.geometry.girder_count):
        raise IndexError("girder_index is outside the bridge layout.")
    all_segments = automatic_permanent_loads(project)
    result: dict[PermanentLoadCategory, LoadEffects] = {}
    for category in PermanentLoadCategory:
        segments = tuple(
            item
            for item in all_segments
            if item.girder_index == girder_index and item.category is category
        )
        response = simple_span_distributed_load_response(
            float(project.geometry.span_m),
            _distributed_segments(segments),
        )
        result[category] = LoadEffects(
            moment_knm=response.max_moment_knm,
            shear_kn=response.max_abs_shear_kn,
        )
    return result


def factored_permanent_effects(
    project: BridgeProject,
    *,
    girder_index: int,
    factors_by_category: dict[PermanentLoadCategory, float],
) -> LoadEffects:
    """Factor permanent load segments first, then recover their exact span envelope."""

    if not 1 <= girder_index <= int(project.geometry.girder_count):
        raise IndexError("girder_index is outside the bridge layout.")
    missing = set(PermanentLoadCategory) - set(factors_by_category)
    if missing:
        labels = ", ".join(sorted(item.value for item in missing))
        raise ValueError(f"Missing permanent-load factors for: {labels}.")
    if any(value < 0.0 for value in factors_by_category.values()):
        raise ValueError("Permanent-load factors cannot be negative.")

    segments = tuple(
        item
        for item in automatic_permanent_loads(project)
        if item.girder_index == girder_index
    )
    response = simple_span_distributed_load_response(
        float(project.geometry.span_m),
        _distributed_segments(
            segments,
            factors_by_category=factors_by_category,
        ),
    )
    return LoadEffects(
        moment_knm=response.max_moment_knm,
        shear_kn=response.max_abs_shear_kn,
    )
