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
from rc_single_span.analysis.traffic_envelope import (
    _longitudinal_groups,
    girder_vertical_displacement_mm,
    native_traffic_girder_envelope,
)
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
    GoverningComponent,
    LM1CaseResult,
    LM1GirderGoverningEnvelope,
    LM1GirderStationMomentEnvelope,
    LM1SearchResult,
    LM1SearchPlacement,
    LM1StationMomentEnvelope,
    _fixed_search_grid,
    _lead_positions,
    _position_vectors,
    build_lm1_plan_loads,
    favourable_udl_regions,
    generate_lm1_search_placements,
)
from rc_single_span.analysis.prepared_grillage import prepare_vertical_grillage
from rc_single_span.codes.eurocode.lm1 import notional_lane_layout

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


@dataclass(frozen=True)
class LM1InfluenceContext:
    project: BridgeProject
    placements: tuple[LM1SearchPlacement, ...]
    model: StructuralModel
    prepared: PreparedVerticalGrillage
    surface: LM1UDLInfluenceSurface
    tandem_analyses: tuple[GrillageAnalysisResult, ...]
    pressures: tuple[tuple[float, ...], ...]
    factors: LM1AdjustmentFactors

    def maximize(
        self,
        response: Callable[[GrillageAnalysisResult], float],
        *,
        sign: int = 1,
    ) -> LM1SignedResponseSearchResult:
        if sign not in (-1, 1):
            raise ValueError("Influence response sign must be +1 or -1.")
        unit = tuple(response(result) for result in self.surface.unit_analyses)
        best: tuple[float, int] | None = None
        for index, (tandem, pressures) in enumerate(
            zip(self.tandem_analyses, self.pressures, strict=True)
        ):
            value = sign * response(tandem) + sum(
                max(0.0, sign * pressure * effect)
                for pressure, effect in zip(pressures, unit, strict=True)
            )
            if best is None or value > best[0]:
                best = (value, index)
        assert best is not None
        placement = self.placements[best[1]]
        influence = optimize_lm1_udl_for_response(
            self.project, placement, self.model, self.prepared, response,
            sign=sign, factors=self.factors, surface=self.surface,
        )
        if abs(sign * influence.response - best[0]) > 1.0e-6 * max(1.0, abs(best[0])):
            raise RuntimeError("LM1 influence superposition and re-solved case disagree.")
        return LM1SignedResponseSearchResult(
            placement, influence, len(self.placements),
        )


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
    context = prepare_lm1_influence_context(
        project, factors=factors, longitudinal_step_m=longitudinal_step_m,
        max_exhaustive_tandem_combinations=max_exhaustive_tandem_combinations,
    )
    return context.maximize(response, sign=sign)


def prepare_lm1_influence_context(
    project: BridgeProject,
    *,
    factors: LM1AdjustmentFactors | None = None,
    longitudinal_step_m: float = 1.2,
    max_exhaustive_tandem_combinations: int = 5000,
) -> LM1InfluenceContext:
    """Prepare the shared influence surface and complete tandem solutions."""
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
    adjustment = factors or LM1AdjustmentFactors()
    tandems = []
    all_pressures = []
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
        tandems.append(solve_prepared_vertical_grillage(
            prepared, replace(model, load_cases=(tandem,)),
        ))
        all_pressures.append(tuple(active.get(bounds, 0.0) for bounds in surface.cells))
    return LM1InfluenceContext(
        project, placements, model, prepared, surface,
        tuple(tandems), tuple(all_pressures), adjustment,
    )


def run_lm1_influence_grillage_search(
    project: BridgeProject,
    *,
    factors: LM1AdjustmentFactors | None = None,
    longitudinal_step_m: float = 1.2,
    max_exhaustive_tandem_combinations: int = 5000,
) -> LM1SearchResult:
    """Envelope member ends and fixed deflection stations with favourable UDL.

    Every stored governing case is a re-solved physical TS + selected UDL
    patch case. Deflection is sampled at nodes and quarter points of each
    longitudinal element; refine the longitudinal grid for convergence.
    """
    context = prepare_lm1_influence_context(
        project, factors=factors, longitudinal_step_m=longitudinal_step_m,
        max_exhaustive_tandem_combinations=max_exhaustive_tandem_combinations,
    )
    groups = _longitudinal_groups(context.model)
    nodes = {node.node_id: node for node in context.model.nodes}
    registered: dict[tuple[int, tuple[Bounds, ...] | None], LM1CaseResult] = {}

    def register(placement, regions, model, analysis):
        key = (placement.case_id, regions)
        if key not in registered:
            case_id = len(context.placements) + len(registered) + 1
            original_case = model.load_cases[0]
            tagged_model = replace(model, load_cases=(
                replace(original_case, load_case_id=case_id),
            ))
            tagged_analysis = replace(analysis, load_case_id=case_id)
            tagged_placement = replace(placement, case_id=case_id)
            registered[key] = LM1CaseResult(
                tagged_placement, tagged_model, tagged_analysis,
                native_traffic_girder_envelope(tagged_model, tagged_analysis),
            )
        return registered[key]

    def checked(response, sign):
        found = context.maximize(response, sign=sign)
        case = register(
            found.placement, found.influence.regions,
            found.influence.model, found.influence.analysis,
        )
        return GoverningComponent(
            sign * found.influence.response,
            case.placement.case_id,
            None,
        )

    full_udl_cases = []
    for placement in context.placements:
        points, areas = build_lm1_plan_loads(
            project, placement, factors=context.factors,
        )
        case = build_plan_load_case(
            context.model, load_case_id=placement.case_id,
            name="LM1 full UDL comparison", point_loads=points,
            area_loads=areas,
        )
        model = replace(context.model, load_cases=(case,))
        analysis = solve_prepared_vertical_grillage(context.prepared, model)
        full_udl_cases.append(register(placement, None, model, analysis))

    girders = []
    station_girders = []
    for girder_index, (y_m, beams) in enumerate(groups, start=1):
        best = {name: GoverningComponent(-1.0, 0, None)
                for name in ("moment", "shear", "torsion", "deflection")}
        stations: dict[float, GoverningComponent] = {}
        deflection_position = 0.0
        for beam in beams:
            for end in ("i", "j"):
                x_m = nodes[beam.node_i if end == "i" else beam.node_j].x_m
                for name, attribute in (
                    ("moment", f"{end}_vertical_bending_moment_knm"),
                    ("shear", f"{end}_vertical_force_kn"),
                    ("torsion", f"{end}_torsion_knm"),
                ):
                    def response(result, member_id=beam.member_id, attr=attribute):
                        member = next(item for item in result.members
                                      if item.member_id == member_id)
                        return float(getattr(member, attr))

                    for sign in (-1, 1):
                        candidate = checked(response, sign)
                        candidate = replace(candidate, member_id=beam.member_id)
                        if candidate.value > best[name].value:
                            best[name] = candidate
                        if name == "moment" and candidate.value > stations.get(
                            x_m, GoverningComponent(-1.0, 0, None)
                        ).value:
                            stations[x_m] = candidate
        x_samples = {node.x_m for beam in beams for node in
                     (nodes[beam.node_i], nodes[beam.node_j])}
        for beam in beams:
            x1, x2 = nodes[beam.node_i].x_m, nodes[beam.node_j].x_m
            x_samples.update(x1 + (x2 - x1) * ratio for ratio in (.25, .5, .75))
        for x_m in sorted(x_samples):
            def response(result, x=x_m, girder=girder_index):
                return girder_vertical_displacement_mm(
                    context.model, result, girder_index=girder, x_m=x,
                )

            for sign in (-1, 1):
                candidate = checked(response, sign)
                case = next(item for item in registered.values()
                            if item.placement.case_id == candidate.case_id)
                exact = case.girders[girder_index - 1]
                if exact.deflection_mm > best["deflection"].value:
                    best["deflection"] = replace(
                        candidate, value=exact.deflection_mm,
                    )
                    deflection_position = exact.deflection_position_m
        for case in full_udl_cases:
            exact = case.girders[girder_index - 1]
            if exact.deflection_mm > best["deflection"].value:
                best["deflection"] = GoverningComponent(
                    exact.deflection_mm, case.placement.case_id, None,
                )
                deflection_position = exact.deflection_position_m
        girders.append(LM1GirderGoverningEnvelope(
            girder_index, y_m, best["moment"], best["shear"],
            best["torsion"], best["deflection"], deflection_position,
        ))
        station_girders.append(LM1GirderStationMomentEnvelope(
            girder_index, y_m, tuple(
                LM1StationMomentEnvelope(x, item)
                for x, item in sorted(stations.items())
            ),
        ))
    lane_count = notional_lane_layout(
        float(project.geometry.carriageway_width_m),
    ).lane_count
    _, exhaustive, theoretical = _position_vectors(
        lane_count,
        _lead_positions(float(project.geometry.span_m), longitudinal_step_m),
        max_exhaustive_combinations=max_exhaustive_tandem_combinations,
    )
    needed = {
        component.case_id
        for girder in girders
        for component in (girder.moment_knm, girder.shear_kn,
                          girder.torsion_knm, girder.deflection_mm)
    }
    needed.update(
        station.moment_knm.case_id
        for girder in station_girders for station in girder.stations
    )
    return LM1SearchResult(
        tuple(girders), tuple(station_girders),
        tuple(case for case in registered.values()
              if case.placement.case_id in needed),
        len(context.placements), longitudinal_step_m,
        exhaustive, theoretical,
        "fixed-grid signed member-end and displacement influence-surface UDL",
    )
