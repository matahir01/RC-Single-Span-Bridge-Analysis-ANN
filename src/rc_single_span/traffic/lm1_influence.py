"""Response-specific LM1 UDL placement on the common linear grillage.

The cells cover the carriageway in both plan directions. For a selected signed
response, solve each UDL cell independently and retain only cells with a
positive contribution. Tandem positions remain complete and unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

from rc_single_span.analysis.grillage_solver import GrillageAnalysisResult
from rc_single_span.analysis.grillage import build_final_composite_grillage
from rc_single_span.analysis.plan_loads import PlanAreaLoad, build_plan_load_case
from rc_single_span.analysis.prepared_grillage import (
    PreparedVerticalGrillage,
    solve_prepared_vertical_grillage,
)
from rc_single_span.analysis.structural_model import StructuralModel
from rc_single_span.codes.eurocode.lm1 import (
    LM1AdjustmentFactors,
    lm1_characteristic_lane_load,
    lm1_remaining_area_udl_kn_m2,
)
from rc_single_span.core.models import BridgeProject
from rc_single_span.traffic.lm1 import (
    LM1SearchPlacement,
    _fixed_search_grid,
    build_lm1_plan_loads,
    favourable_udl_regions,
    generate_lm1_search_placements,
)
from rc_single_span.analysis.prepared_grillage import prepare_vertical_grillage

Bounds = tuple[float, float, float, float]


@dataclass(frozen=True)
class LM1InfluenceResult:
    regions: tuple[Bounds, ...]
    cell_effects: tuple[tuple[Bounds, float], ...]
    response: float
    analysis: GrillageAnalysisResult
    model: StructuralModel


@dataclass(frozen=True)
class LM1UDLInfluenceSurface:
    """Unit-pressure cell analyses on one fixed grillage topology."""

    cells: tuple[Bounds, ...]
    unit_analyses: tuple[GrillageAnalysisResult, ...]


@dataclass(frozen=True)
class LM1SignedResponseSearchResult:
    placement: LM1SearchPlacement
    influence: LM1InfluenceResult
    evaluated_tandem_placements: int


def prepare_lm1_udl_influence_surface(
    model: StructuralModel,
    prepared: PreparedVerticalGrillage,
) -> LM1UDLInfluenceSurface:
    """Factor once, solve one unit-pressure case per carriageway grid cell.

    The caller should pass a grid whose carriageway and notional-lane edges
    are present. Cells outside the carriageway are omitted later, at selection.
    """
    x = sorted({node.x_m for node in model.nodes})
    y = sorted({node.y_m for node in model.nodes})
    cells = tuple((x1, x2, y1, y2)
                  for x1, x2 in zip(x, x[1:])
                  for y1, y2 in zip(y, y[1:]))
    analyses = []
    for index, (x1, x2, y1, y2) in enumerate(cells, start=1):
        case = build_plan_load_case(
            model, load_case_id=index, name="LM1 unit UDL cell",
            area_loads=(PlanAreaLoad(x1, x2, y1, y2, 1.0),),
        )
        analyses.append(solve_prepared_vertical_grillage(
            prepared, replace(model, load_cases=(case,)),
        ))
    return LM1UDLInfluenceSurface(cells, tuple(analyses))


def _cells(
    model: StructuralModel,
    placement: LM1SearchPlacement,
    adjustment: LM1AdjustmentFactors,
) -> tuple[PlanAreaLoad, ...]:
    x = sorted({node.x_m for node in model.nodes})
    y = sorted({node.y_m for node in model.nodes})
    strips = [
        (lane.y_start_m, lane.y_end_m,
         lm1_characteristic_lane_load(lane.lane_number, adjustment).udl_kn_m2)
        for lane in placement.lanes
    ] + [
        (area.y_start_m, area.y_end_m,
         lm1_remaining_area_udl_kn_m2(adjustment))
        for area in placement.remaining
    ]
    result = []
    for x1, x2 in zip(x, x[1:]):
        for y1, y2 in zip(y, y[1:]):
            pressure = next(
                (q for start, end, q in strips
                 if start <= y1 + 1.0e-9 and y2 <= end + 1.0e-9),
                None,
            )
            if pressure is not None and pressure > 0.0:
                result.append(PlanAreaLoad(x1, x2, y1, y2, pressure))
    return tuple(result)


def optimize_lm1_udl_for_response(
    project: BridgeProject,
    placement: LM1SearchPlacement,
    model: StructuralModel,
    prepared: PreparedVerticalGrillage,
    response: Callable[[GrillageAnalysisResult], float],
    *,
    sign: int = 1,
    factors: LM1AdjustmentFactors | None = None,
    surface: LM1UDLInfluenceSurface | None = None,
) -> LM1InfluenceResult:
    """Maximize one signed linear response by 2D cellwise UDL selection.

    ``response`` must return a signed linear quantity (for example one member
    end force, or a displacement at a fixed point), never an absolute envelope
    or a maximum over stations. Call separately for each station and sign.
    """
    if sign not in (-1, 1):
        raise ValueError("Influence response sign must be +1 or -1.")
    adjustment = factors or LM1AdjustmentFactors()
    effects: list[tuple[Bounds, float]] = []
    active = {
        (cell.x_start_m, cell.x_end_m, cell.y_start_m, cell.y_end_m):
        cell.pressure_kn_m2
        for cell in _cells(model, placement, adjustment)
    }
    basis = surface or prepare_lm1_udl_influence_surface(model, prepared)
    for bounds, unit_result in zip(basis.cells, basis.unit_analyses, strict=True):
        pressure = active.get(bounds)
        if pressure is not None:
            effects.append((bounds, pressure * response(unit_result)))
    regions = favourable_udl_regions(tuple(effects), sign=sign)
    points, areas = build_lm1_plan_loads(
        project, placement, factors=adjustment, udl_regions=regions,
    )
    case = build_plan_load_case(
        model, load_case_id=placement.case_id,
        name=f"LM1 signed influence placement {placement.case_id}",
        point_loads=points, area_loads=areas,
    )
    loaded_model = replace(model, load_cases=(case,))
    analysis = solve_prepared_vertical_grillage(prepared, loaded_model)
    return LM1InfluenceResult(
        regions, tuple(effects), response(analysis), analysis, loaded_model,
    )


def run_lm1_signed_response_search(
    project: BridgeProject,
    response: Callable[[GrillageAnalysisResult], float],
    *,
    sign: int = 1,
    factors: LM1AdjustmentFactors | None = None,
    longitudinal_step_m: float = 1.2,
    max_exhaustive_tandem_combinations: int = 5000,
) -> LM1SignedResponseSearchResult:
    """Search complete tandem placements and favourable UDL cells for one response.

    The response must identify a fixed member end or fixed displacement point.
    The selected case is re-solved and its actual member/nodal results returned.
    A full design envelope calls this for both signs at every checked station.
    """
    if sign not in (-1, 1):
        raise ValueError("Influence response sign must be +1 or -1.")
    placements = generate_lm1_search_placements(
        project, longitudinal_step_m=longitudinal_step_m,
        max_exhaustive_tandem_combinations=max_exhaustive_tandem_combinations,
    )
    if not placements:
        raise ValueError("No LM1 tandem placements were generated.")
    x, y = _fixed_search_grid(project, placements)
    model = build_final_composite_grillage(
        project, stations_m=x, additional_y_lines_m=y,
    ).model
    prepared = prepare_vertical_grillage(model)
    surface = prepare_lm1_udl_influence_surface(model, prepared)
    unit_effects = tuple(response(result) for result in surface.unit_analyses)
    adjustment = factors or LM1AdjustmentFactors()
    best: tuple[float, LM1SearchPlacement] | None = None
    for placement in placements:
        active = {
            (cell.x_start_m, cell.x_end_m, cell.y_start_m, cell.y_end_m):
            cell.pressure_kn_m2
            for cell in _cells(model, placement, adjustment)
        }
        points, _ = build_lm1_plan_loads(
            project, placement, factors=adjustment, udl_regions=(),
        )
        tandem = build_plan_load_case(
            model, load_case_id=placement.case_id, name="LM1 complete tandems",
            point_loads=points,
        )
        tandem_result = solve_prepared_vertical_grillage(
            prepared, replace(model, load_cases=(tandem,)),
        )
        value = sign * response(tandem_result) + sum(
            max(0.0, sign * active.get(bounds, 0.0) * unit)
            for bounds, unit in zip(surface.cells, unit_effects, strict=True)
        )
        if best is None or value > best[0]:
            best = (value, placement)
    assert best is not None
    influence = optimize_lm1_udl_for_response(
        project, best[1], model, prepared, response,
        sign=sign, factors=adjustment, surface=surface,
    )
    if abs(sign * influence.response - best[0]) > 1.0e-6 * max(1.0, abs(best[0])):
        raise RuntimeError("LM1 influence superposition and re-solved case disagree.")
    return LM1SignedResponseSearchResult(best[1], influence, len(placements))
