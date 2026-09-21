from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable, Iterable

from scipy.optimize import minimize_scalar

from rc_single_span.analysis.grillage_solver import GrillageAnalysisResult
from rc_single_span.analysis.structural_model import StructuralModel
from rc_single_span.analysis.traffic_envelope import girder_vertical_displacement_mm


@dataclass(frozen=True)
class CombinedDeflectionCase:
    case_id: int
    girder_index: int
    x_m: float
    permanent_mm: float
    traffic_mm: float
    traffic_factor: float
    total_mm: float
    label: str


@dataclass(frozen=True)
class CombinedDeflectionEnvelope:
    girder_index: int
    governing: CombinedDeflectionCase
    evaluated_case_count: int


def _longitudinal_intervals(
    model: StructuralModel,
    *,
    girder_index: int,
) -> tuple[tuple[float, float], ...]:
    nodes = {node.node_id: node for node in model.nodes}
    groups: dict[float, list[tuple[float, float]]] = {}
    for beam in model.beams:
        ni, nj = nodes[beam.node_i], nodes[beam.node_j]
        if abs(ni.y_m - nj.y_m) <= 1.0e-9 and abs(ni.x_m - nj.x_m) > 1.0e-9:
            y = 0.5 * (ni.y_m + nj.y_m)
            groups.setdefault(y, []).append(tuple(sorted((ni.x_m, nj.x_m))))
    ordered = sorted(groups.items())
    if not 1 <= girder_index <= len(ordered):
        raise IndexError("girder_index is outside the grillage.")
    return tuple(sorted(ordered[girder_index - 1][1]))


def combined_deflection_for_case(
    *,
    model: StructuralModel,
    analysis: GrillageAnalysisResult,
    case_id: int,
    case_label: str,
    girder_index: int,
    traffic_factor: float,
    permanent_deflection_mm: Callable[[float], float],
) -> CombinedDeflectionCase:
    """Re-search total permanent+traffic displacement across one solved traffic case."""

    if traffic_factor < 0.0:
        raise ValueError("traffic_factor cannot be negative.")
    intervals = _longitudinal_intervals(model, girder_index=girder_index)
    if not intervals:
        raise RuntimeError("No longitudinal intervals found for combined deflection search.")

    def total_at_x(x_m: float) -> tuple[float, float, float]:
        permanent = permanent_deflection_mm(float(x_m))
        traffic = girder_vertical_displacement_mm(
            model,
            analysis,
            girder_index=girder_index,
            x_m=float(x_m),
        )
        return permanent + traffic_factor * traffic, permanent, traffic

    candidates: list[tuple[float, float, float, float]] = []
    for left, right in intervals:
        for x_m in (left, right):
            total, permanent, traffic = total_at_x(x_m)
            candidates.append((total, x_m, permanent, traffic))
        if right - left <= 1.0e-12:
            continue
        result = minimize_scalar(
            lambda x: -total_at_x(float(x))[0],
            bounds=(left, right),
            method="bounded",
            options={"xatol": 1.0e-8},
        )
        x_m = float(result.x)
        total, permanent, traffic = total_at_x(x_m)
        candidates.append((total, x_m, permanent, traffic))

    total, x_m, permanent, traffic = max(candidates, key=lambda item: item[0])
    return CombinedDeflectionCase(
        case_id=case_id,
        girder_index=girder_index,
        x_m=x_m,
        permanent_mm=permanent,
        traffic_mm=traffic,
        traffic_factor=traffic_factor,
        total_mm=total,
        label=case_label,
    )


def combined_deflection_envelope(
    *,
    cases: Iterable[tuple[int, str, StructuralModel, GrillageAnalysisResult]],
    girder_index: int,
    traffic_factor: float,
    permanent_deflection_mm: Callable[[float], float],
) -> CombinedDeflectionEnvelope:
    """Envelope total displacement across every supplied traffic case."""

    evaluated: list[CombinedDeflectionCase] = []
    for case_id, label, model, analysis in cases:
        evaluated.append(
            combined_deflection_for_case(
                model=model,
                analysis=analysis,
                case_id=case_id,
                case_label=label,
                girder_index=girder_index,
                traffic_factor=traffic_factor,
                permanent_deflection_mm=permanent_deflection_mm,
            )
        )
    if not evaluated:
        raise ValueError("Combined deflection envelope requires at least one traffic case.")
    return CombinedDeflectionEnvelope(
        girder_index=girder_index,
        governing=max(evaluated, key=lambda item: item.total_mm),
        evaluated_case_count=len(evaluated),
    )
