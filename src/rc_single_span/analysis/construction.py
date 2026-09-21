from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise

import numpy as np
from scipy.optimize import minimize_scalar

from rc_single_span.analysis.permanent import (
    PermanentLoadCategory,
    PermanentLoadSegment,
    automatic_permanent_loads,
)
from rc_single_span.analysis.sections import (
    SectionProperties,
    deck_construction_girder_properties,
    final_composite_girder_properties,
    precast_girder_properties,
)
from rc_single_span.analysis.simple_span import (
    DistributedLoadSegment,
    SimpleSpanDistributedResult,
    simple_span_distributed_load_response,
    simple_span_distributed_response_at_x,
)
from rc_single_span.core.models import BridgeProject, PermanentActionStage


@dataclass(frozen=True)
class ConstructionStageGirderResult:
    girder_index: int
    stage: PermanentActionStage
    loads: tuple[PermanentLoadSegment, ...]
    section: SectionProperties
    elastic_modulus_mpa: float
    response: SimpleSpanDistributedResult
    max_downward_deflection_mm: float
    max_deflection_position_m: float


@dataclass(frozen=True)
class CumulativeGirderResult:
    girder_index: int
    max_moment_knm: float
    max_shear_kn: float
    max_downward_deflection_mm: float
    max_deflection_position_m: float


@dataclass(frozen=True)
class ConstructionAnalysisResult:
    stages: tuple[ConstructionStageGirderResult, ...]
    cumulative_by_girder: tuple[CumulativeGirderResult, ...]


@dataclass(frozen=True)
class FactoredPermanentDeflectionResult:
    girder_index: int
    maximum_downward_deflection_mm: float
    maximum_position_m: float
    factors_by_category: dict[PermanentLoadCategory, float]


def _section_for_stage(
    project: BridgeProject,
    *,
    girder_index: int,
    stage: PermanentActionStage,
) -> SectionProperties:
    if stage is PermanentActionStage.PRECAST_GIRDER:
        return precast_girder_properties(project.geometry)
    if stage is PermanentActionStage.DECK_CONSTRUCTION:
        return deck_construction_girder_properties(
            project.geometry,
            girder_index=girder_index,
        )
    return final_composite_girder_properties(
        project.geometry,
        girder_index=girder_index,
    )


def _distributed(loads: tuple[PermanentLoadSegment, ...]) -> tuple[DistributedLoadSegment, ...]:
    return tuple(
        DistributedLoadSegment(
            load.magnitude_kn_m,
            load.x_start_m,
            load.x_end_m,
            label=load.source,
        )
        for load in loads
    )


def _deflection_m(
    span_m: float,
    loads: tuple[DistributedLoadSegment, ...],
    *,
    x_m: float,
    ei_kn_m2: float,
) -> float:
    if not 0.0 <= x_m <= span_m:
        raise ValueError("Deflection coordinate lies outside the span.")
    if x_m in {0.0, span_m} or not loads:
        return 0.0

    boundaries = {0.0, span_m, x_m}
    for load in loads:
        boundaries.update((load.start_m, load.end_m))
    ordered = sorted(boundaries)
    gauss_x, gauss_w = np.polynomial.legendre.leggauss(8)
    unit_left_reaction = (span_m - x_m) / span_m
    integral = 0.0

    for left, right in pairwise(ordered):
        if right <= left:
            continue
        midpoint = 0.5 * (left + right)
        half = 0.5 * (right - left)
        for coordinate, weight in zip(gauss_x, gauss_w, strict=True):
            station = midpoint + half * float(coordinate)
            moment, _ = simple_span_distributed_response_at_x(
                span_m,
                loads,
                station,
            )
            if station <= x_m:
                unit_moment = unit_left_reaction * station
            else:
                unit_moment = unit_left_reaction * station - (station - x_m)
            integral += float(weight) * moment * unit_moment * half
    return integral / ei_kn_m2


def _max_deflection(
    span_m: float,
    loads: tuple[DistributedLoadSegment, ...],
    *,
    ei_kn_m2: float,
) -> tuple[float, float]:
    if not loads:
        return 0.0, span_m / 2.0

    objective = lambda x: -_deflection_m(
        span_m,
        loads,
        x_m=float(x),
        ei_kn_m2=ei_kn_m2,
    )
    result = minimize_scalar(
        objective,
        bounds=(0.0, span_m),
        method="bounded",
        options={"xatol": 1.0e-8},
    )
    return -float(result.fun), float(result.x)


def run_construction_stage_analysis(
    project: BridgeProject,
    *,
    elastic_modulus_mpa: float | None = None,
) -> ConstructionAnalysisResult:
    e_mpa = (
        float(elastic_modulus_mpa)
        if elastic_modulus_mpa is not None
        else project.materials.elastic_modulus_mpa
    )
    if e_mpa is None or e_mpa <= 0.0:
        raise ValueError(
            "Construction-stage analysis requires an explicit elastic modulus; "
            "the selected code profile may derive it before calling this common workflow."
        )

    span = float(project.geometry.span_m)
    all_segments = automatic_permanent_loads(project)
    stage_results: list[ConstructionStageGirderResult] = []

    for stage in PermanentActionStage:
        for girder_index in range(1, int(project.geometry.girder_count) + 1):
            loads = tuple(
                item
                for item in all_segments
                if item.stage is stage and item.girder_index == girder_index
            )
            distributed = _distributed(loads)
            response = simple_span_distributed_load_response(span, distributed)
            section = _section_for_stage(
                project,
                girder_index=girder_index,
                stage=stage,
            )
            ei = e_mpa * 1000.0 * section.iy_m4
            deflection_m, position_m = _max_deflection(
                span,
                distributed,
                ei_kn_m2=ei,
            )
            stage_results.append(
                ConstructionStageGirderResult(
                    girder_index,
                    stage,
                    loads,
                    section,
                    e_mpa,
                    response,
                    deflection_m * 1000.0,
                    position_m,
                )
            )

    cumulative = []
    for girder_index in range(1, int(project.geometry.girder_count) + 1):
        items = tuple(item for item in stage_results if item.girder_index == girder_index)
        all_loads = tuple(load for item in items for load in _distributed(item.loads))
        combined = simple_span_distributed_load_response(span, all_loads)

        def cumulative_deflection(
            x_m: float,
            stage_items: tuple[ConstructionStageGirderResult, ...] = items,
        ) -> float:
            total = 0.0
            for item in stage_items:
                stage_loads = _distributed(item.loads)
                ei = item.elastic_modulus_mpa * 1000.0 * item.section.iy_m4
                total += _deflection_m(
                    span,
                    stage_loads,
                    x_m=x_m,
                    ei_kn_m2=ei,
                )
            return total

        if all_loads:
            optimum = minimize_scalar(
                lambda x: -cumulative_deflection(float(x)),
                bounds=(0.0, span),
                method="bounded",
                options={"xatol": 1.0e-8},
            )
            max_deflection_m = -float(optimum.fun)
            position_m = float(optimum.x)
        else:
            max_deflection_m = 0.0
            position_m = span / 2.0

        cumulative.append(
            CumulativeGirderResult(
                girder_index,
                combined.max_moment_knm,
                combined.max_abs_shear_kn,
                max_deflection_m * 1000.0,
                position_m,
            )
        )

    return ConstructionAnalysisResult(tuple(stage_results), tuple(cumulative))



def factored_permanent_deflection(
    project: BridgeProject,
    *,
    girder_index: int,
    factors_by_category: dict[PermanentLoadCategory, float] | None = None,
    elastic_modulus_mpa: float | None = None,
) -> FactoredPermanentDeflectionResult:
    """Return stage-aware permanent deflection after optional category factors.

    Load factors are applied to each permanent segment before its stage-specific
    M/EI response is integrated. This preserves the separate precast,
    deck-construction and final-composite stiffnesses.
    """

    if not 1 <= girder_index <= int(project.geometry.girder_count):
        raise IndexError("girder_index is outside the bridge layout.")
    factors = factors_by_category or {
        category: 1.0 for category in PermanentLoadCategory
    }
    missing = set(PermanentLoadCategory) - set(factors)
    if missing:
        labels = ", ".join(sorted(item.value for item in missing))
        raise ValueError(f"Missing permanent-deflection factors for: {labels}.")
    if any(value < 0.0 for value in factors.values()):
        raise ValueError("Permanent-deflection factors cannot be negative.")

    e_mpa = (
        float(elastic_modulus_mpa)
        if elastic_modulus_mpa is not None
        else project.materials.elastic_modulus_mpa
    )
    if e_mpa is None or e_mpa <= 0.0:
        raise ValueError("Permanent deflection requires an explicit elastic modulus.")

    span = float(project.geometry.span_m)
    all_segments = automatic_permanent_loads(project)

    def displacement_m(x_m: float) -> float:
        total = 0.0
        for stage in PermanentActionStage:
            stage_segments = tuple(
                segment
                for segment in all_segments
                if segment.girder_index == girder_index and segment.stage is stage
            )
            loads = tuple(
                DistributedLoadSegment(
                    segment.magnitude_kn_m * factors[segment.category],
                    segment.x_start_m,
                    segment.x_end_m,
                    label=segment.source,
                )
                for segment in stage_segments
            )
            if not loads:
                continue
            section = _section_for_stage(
                project,
                girder_index=girder_index,
                stage=stage,
            )
            total += _deflection_m(
                span,
                loads,
                x_m=x_m,
                ei_kn_m2=e_mpa * 1000.0 * section.iy_m4,
            )
        return total

    optimum = minimize_scalar(
        lambda x: -displacement_m(float(x)),
        bounds=(0.0, span),
        method="bounded",
        options={"xatol": 1.0e-8},
    )
    return FactoredPermanentDeflectionResult(
        girder_index=girder_index,
        maximum_downward_deflection_mm=-float(optimum.fun) * 1000.0,
        maximum_position_m=float(optimum.x),
        factors_by_category=dict(factors),
    )



def factored_permanent_deflection_at_x_mm(
    project: BridgeProject,
    *,
    girder_index: int,
    x_m: float,
    factors_by_category: dict[PermanentLoadCategory, float] | None = None,
    elastic_modulus_mpa: float | None = None,
) -> float:
    """Return stage-aware permanent deflection at one longitudinal coordinate."""

    if not 1 <= girder_index <= int(project.geometry.girder_count):
        raise IndexError("girder_index is outside the bridge layout.")
    span = float(project.geometry.span_m)
    if not 0.0 <= x_m <= span:
        raise ValueError("x_m lies outside the bridge span.")
    factors = factors_by_category or {
        category: 1.0 for category in PermanentLoadCategory
    }
    missing = set(PermanentLoadCategory) - set(factors)
    if missing:
        labels = ", ".join(sorted(item.value for item in missing))
        raise ValueError(f"Missing permanent-deflection factors for: {labels}.")
    if any(value < 0.0 for value in factors.values()):
        raise ValueError("Permanent-deflection factors cannot be negative.")

    e_mpa = (
        float(elastic_modulus_mpa)
        if elastic_modulus_mpa is not None
        else project.materials.elastic_modulus_mpa
    )
    if e_mpa is None or e_mpa <= 0.0:
        raise ValueError("Permanent deflection requires an explicit elastic modulus.")

    total_m = 0.0
    all_segments = automatic_permanent_loads(project)
    for stage in PermanentActionStage:
        stage_segments = tuple(
            segment
            for segment in all_segments
            if segment.girder_index == girder_index and segment.stage is stage
        )
        loads = tuple(
            DistributedLoadSegment(
                segment.magnitude_kn_m * factors[segment.category],
                segment.x_start_m,
                segment.x_end_m,
                label=segment.source,
            )
            for segment in stage_segments
        )
        if not loads:
            continue
        section = _section_for_stage(
            project,
            girder_index=girder_index,
            stage=stage,
        )
        total_m += _deflection_m(
            span,
            loads,
            x_m=x_m,
            ei_kn_m2=e_mpa * 1000.0 * section.iy_m4,
        )
    return total_m * 1000.0
