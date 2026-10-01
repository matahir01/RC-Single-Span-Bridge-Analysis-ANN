"""Response-specific LM1 UDL placement on the common linear grillage.

The cells cover the carriageway in both plan directions. For a selected signed
response, solve each UDL cell independently and retain only cells with a
positive contribution. Tandem positions remain complete and unchanged.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from itertools import pairwise

import numpy as np

from rc_single_span.analysis.grillage import build_final_composite_grillage
from rc_single_span.analysis.grillage_solver import GrillageAnalysisResult
from rc_single_span.analysis.plan_loads import PlanAreaLoad, build_plan_load_case
from rc_single_span.analysis.prepared_grillage import (
    PreparedVerticalGrillage,
    prepare_vertical_grillage,
    solve_prepared_vertical_grillage,
)
from rc_single_span.analysis.structural_model import StructuralModel
from rc_single_span.analysis.traffic_envelope import (
    _longitudinal_groups,
    _member_deflection_candidates_mm,
    girder_vertical_displacement_mm,
    native_traffic_girder_envelope,
)
from rc_single_span.codes.eurocode.lm1 import (
    LM1AdjustmentFactors,
    lm1_characteristic_lane_load,
    lm1_remaining_area_udl_kn_m2,
    notional_lane_layout,
)
from rc_single_span.core.models import BridgeProject
from rc_single_span.core.progress import AnalysisControl
from rc_single_span.traffic.lm1 import (
    GoverningComponent,
    LM1CaseResult,
    LM1GirderGoverningEnvelope,
    LM1GirderStationMomentEnvelope,
    LM1SearchPlacement,
    LM1SearchResult,
    LM1StationMomentEnvelope,
    _fixed_search_grid,
    _lead_positions,
    _position_vectors,
    build_lm1_plan_loads,
    favourable_udl_regions,
    generate_lm1_search_placements,
)

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
class _DeferredLM1Case:
    placement: LM1SearchPlacement
    model: StructuralModel
    checks: tuple[tuple[int, str, int, float], ...]
    displacement_checks: tuple[tuple[int, float, int, float], ...] = ()


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
    tandem_scale: float = 1.0
    udl_scale: float = 1.0
    pressure_matrix: np.ndarray | None = None
    member_ids: tuple[int, ...] = ()
    tandem_member_values: np.ndarray | None = None
    unit_member_values: np.ndarray | None = None
    node_ids: tuple[int, ...] = ()
    tandem_node_values: np.ndarray | None = None
    unit_node_values: np.ndarray | None = None
    full_udl_analyses: dict[int, GrillageAnalysisResult] = field(
        default_factory=dict, compare=False, repr=False,
    )
    weighted_tandem_analyses: dict[int, GrillageAnalysisResult] = field(
        default_factory=dict, compare=False, repr=False,
    )
    displacement_unit_cache: dict[tuple[int, float], tuple[float, ...]] = field(
        default_factory=dict, compare=False, repr=False,
    )

    def with_uniform_factors(self, factors: LM1AdjustmentFactors) -> LM1InfluenceContext:
        """Reuse the same solved TS/cell basis for uniform TS and UDL scaling.

        A non-uniform lane adjustment requires its own basis and is rejected
        rather than silently approximated with an aggregate factor.
        """
        tandem_keys = ("alpha_Q1", "alpha_Q2", "alpha_Q3")
        udl_keys = ("alpha_q1", "alpha_q2", "alpha_q3", "alpha_q_other", "alpha_q_remaining")

        def common_ratio(keys: tuple[str, ...]) -> float:
            ratios = []
            for key in keys:
                old, new = float(getattr(self.factors, key)), float(getattr(factors, key))
                if old == 0.0:
                    if new != 0.0:
                        raise ValueError(f"Cannot reuse zero LM1 basis coefficient {key}.")
                else:
                    ratios.append(new / old)
            if not ratios or any(not np.isclose(value, ratios[0], rtol=1e-12, atol=1e-12)
                                 for value in ratios):
                raise ValueError("LM1 basis reuse requires uniform component factors.")
            return ratios[0]

        return replace(
            self,
            factors=factors,
            tandem_scale=self.tandem_scale * common_ratio(tandem_keys),
            udl_scale=self.udl_scale * common_ratio(udl_keys),
            weighted_tandem_analyses={},
            displacement_unit_cache=self.displacement_unit_cache,
        )

    def _physical_tandem(self, index: int) -> GrillageAnalysisResult:
        if self.tandem_scale == 1.0:
            return self.tandem_analyses[index]
        cached = self.weighted_tandem_analyses.get(index)
        if cached is None:
            placement = self.placements[index]
            points, _ = build_lm1_plan_loads(
                self.project, placement, factors=self.factors, udl_regions=(),
            )
            case = build_plan_load_case(
                self.model, load_case_id=placement.case_id,
                name="LM1 complete weighted tandems", point_loads=points,
            )
            cached = solve_prepared_vertical_grillage(
                self.prepared, replace(self.model, load_cases=(case,)),
            )
            self.weighted_tandem_analyses[index] = cached
        return cached

    def _best_index(
        self, tandem: np.ndarray, unit: np.ndarray, sign: int,
        response: Callable[[GrillageAnalysisResult], float],
        *, exact_unit_on_ties: tuple[float, ...] | None = None,
    ) -> tuple[int, float]:
        if sign not in (-1, 1):
            raise ValueError("Influence response sign must be +1 or -1.")
        pressures = self.pressure_matrix
        if pressures is None:
            pressures = np.asarray(self.pressures, dtype=float)
        scores = sign * self.tandem_scale * tandem + np.maximum(
            0.0, sign * self.udl_scale * pressures * unit[None, :]
        ).sum(axis=1)
        index = int(np.argmax(scores))
        # Preserve the legacy first-winner selection on near ties. Its search
        # compares influence superposition, before the selected physical case
        # is solved; comparing physical re-solves here can change case IDs.
        tied = np.flatnonzero(
            scores >= scores[index] - 1.0e-10 * max(1.0, abs(scores[index]))
        )
        if len(tied) > 1:
            best_exact = -float("inf")
            exact_unit = exact_unit_on_ties if exact_unit_on_ties is not None else unit
            for candidate in tied:
                candidate = int(candidate)
                pressures = self.pressures[candidate]
                if self.tandem_scale == 1.0 and self.udl_scale == 1.0:
                    tandem_effect = (
                        response(self.tandem_analyses[candidate])
                        if exact_unit_on_ties is not None else float(tandem[candidate])
                    )
                    pressure_values = pressures
                else:
                    tandem_effect = response(self._physical_tandem(candidate))
                    active = {
                        (cell.x_start_m, cell.x_end_m, cell.y_start_m, cell.y_end_m):
                        cell.pressure_kn_m2
                        for cell in _cells(self.model, self.placements[candidate], self.factors)
                    }
                    pressure_values = tuple(active.get(bounds, 0.0)
                                            for bounds in self.surface.cells)
                value = sign * tandem_effect + sum(
                    max(0.0, sign * pressure * float(effect))
                    for pressure, effect in zip(pressure_values, exact_unit, strict=True)
                )
                if value > best_exact:
                    best_exact, index = value, candidate
            return index, best_exact
        return index, float(scores[index])

    def maximize_member(
        self, member_id: int, attribute: str, *, sign: int = 1,
    ) -> LM1SignedResponseSearchResult:
        """Vectorized member-end search with the same first-winner tie rule."""
        if self.tandem_member_values is None or self.unit_member_values is None:
            raise ValueError("Member response matrices have not been prepared.")
        columns = (
            "i_vertical_force_kn", "i_vertical_bending_moment_knm", "i_torsion_knm",
            "j_vertical_force_kn", "j_vertical_bending_moment_knm", "j_torsion_knm",
        )
        member_index = self.member_ids.index(member_id)
        column = columns.index(attribute)
        response = lambda result: float(getattr(result.members[member_index], attribute))
        index, best = self._best_index(
            self.tandem_member_values[:, member_index, column],
            self.unit_member_values[:, member_index, column], sign, response,
        )
        return self._resolved(index, best, response, sign)

    def select_member(
        self, member_id: int, attribute: str, *, sign: int = 1,
    ) -> tuple[LM1SearchPlacement, tuple[Bounds, ...], float]:
        """Select a governing member response without physically re-solving it."""
        if self.tandem_member_values is None or self.unit_member_values is None:
            raise ValueError("Member response matrices have not been prepared.")
        columns = (
            "i_vertical_force_kn", "i_vertical_bending_moment_knm", "i_torsion_knm",
            "j_vertical_force_kn", "j_vertical_bending_moment_knm", "j_torsion_knm",
        )
        member_index = self.member_ids.index(member_id)
        column = columns.index(attribute)
        response = lambda result: float(getattr(result.members[member_index], attribute))
        unit = self.unit_member_values[:, member_index, column]
        index, best = self._best_index(
            self.tandem_member_values[:, member_index, column], unit, sign, response,
        )
        active = {
            (cell.x_start_m, cell.x_end_m, cell.y_start_m, cell.y_end_m):
            cell.pressure_kn_m2
            for cell in _cells(self.model, self.placements[index], self.factors)
        }
        effects = tuple(
            (bounds, active[bounds] * float(effect))
            for bounds, effect in zip(self.surface.cells, unit, strict=True)
            if bounds in active
        )
        return self.placements[index], favourable_udl_regions(effects, sign=sign), best

    def select_displacement(
        self, girder_index: int, x_m: float, *, sign: int = 1,
    ) -> tuple[LM1SearchPlacement, tuple[Bounds, ...], float, float, float]:
        """Select a fixed displacement and recover exact cubic girder deflection."""
        if self.tandem_node_values is None or self.unit_node_values is None:
            raise ValueError("Node response matrices have not been prepared.")
        groups = _longitudinal_groups(self.model)
        if not 1 <= girder_index <= len(groups):
            raise IndexError("girder_index is outside the grillage.")
        model_nodes = {node.node_id: node for node in self.model.nodes}
        beam = next(
            beam for beam in groups[girder_index - 1][1]
            if min(model_nodes[beam.node_i].x_m, model_nodes[beam.node_j].x_m) - 1e-10
            <= x_m <=
            max(model_nodes[beam.node_i].x_m, model_nodes[beam.node_j].x_m) + 1e-10
        )
        ni, nj = model_nodes[beam.node_i], model_nodes[beam.node_j]
        dx = nj.x_m - ni.x_m
        length = abs(dx)
        cx = dx / length
        xi = min(max((x_m - ni.x_m) / dx, 0.0), 1.0)
        i, j = self.node_ids.index(ni.node_id), self.node_ids.index(nj.node_id)

        def interpolate(values: np.ndarray) -> np.ndarray:
            wi, wj = values[:, i, 0], values[:, j, 0]
            slope_i, slope_j = -cx * values[:, i, 1], -cx * values[:, j, 1]
            displacement = (
                (1 - 3 * xi**2 + 2 * xi**3) * wi
                + (3 * xi**2 - 2 * xi**3) * wj
                + length * (xi - 2 * xi**2 + xi**3) * slope_i
                + length * (-xi**2 + xi**3) * slope_j
            )
            return -1000.0 * displacement

        tandem = interpolate(self.tandem_node_values)
        unit = interpolate(self.unit_node_values)
        def response(result: GrillageAnalysisResult) -> float:
            # Follow traffic_envelope.girder_vertical_displacement_mm's
            # operation order, including tiny support roundoff, with the
            # already identified nodes instead of rebuilding girder maps.
            ri, rj = result.nodes[i], result.nodes[j]
            wi, wj = ri.vertical_displacement_m, rj.vertical_displacement_m
            slope_i = -cx * ri.rotation_y_rad
            slope_j = -cx * rj.rotation_y_rad
            local_x = min(max((x_m - ni.x_m) / cx, 0.0), length)
            a = (3.0 * (wj - wi) / length**2
                 - (2.0 * slope_i + slope_j) / length)
            b = (2.0 * (wi - wj) / length**3
                 + (slope_i + slope_j) / length**2)
            return -1000.0 * (
                wi + slope_i * local_x + a * local_x**2 + b * local_x**3
            )

        cache_key = girder_index, x_m
        exact_unit = self.displacement_unit_cache.get(cache_key)
        if exact_unit is None:
            exact_unit = tuple(response(result) for result in self.surface.unit_analyses)
            self.displacement_unit_cache[cache_key] = exact_unit
        index, best = self._best_index(
            tandem, unit, sign, response, exact_unit_on_ties=exact_unit,
        )
        # The original fixed-station response evaluates Hermite coefficients
        # in Python float order. Preserve its cell sign test for the physical
        # selected case; interpolated NumPy values can flip a nearly zero cell.
        active = {
            (cell.x_start_m, cell.x_end_m, cell.y_start_m, cell.y_end_m):
            cell.pressure_kn_m2
            for cell in _cells(self.model, self.placements[index], self.factors)
        }
        effects = tuple(
            (bounds, active[bounds] * effect)
            for bounds, effect in zip(self.surface.cells, exact_unit, strict=True)
            if bounds in active
        )
        regions = favourable_udl_regions(effects, sign=sign)
        selected = np.asarray([
            active.get(bounds, 0.0) if bounds in regions else 0.0
            for bounds in self.surface.cells
        ], dtype=float)
        nodes = (
            self.tandem_scale * self.tandem_node_values[index]
            + np.einsum("c,cnd->nd", selected, self.unit_node_values)
        )
        synthetic = replace(
            self.tandem_analyses[index],
            nodes=tuple(
                replace(node, vertical_displacement_m=float(values[0]),
                        rotation_y_rad=float(values[1]))
                for node, values in zip(self.tandem_analyses[index].nodes, nodes, strict=True)
            ),
        )
        exact, position = max(
            _member_deflection_candidates_mm(self.model, synthetic, groups[girder_index - 1][1]),
            key=lambda item: item[0],
        )
        return self.placements[index], regions, best, exact, position

    def _resolved(
        self, index: int, best: float,
        response: Callable[[GrillageAnalysisResult], float], sign: int,
    ) -> LM1SignedResponseSearchResult:
        placement = self.placements[index]
        influence = optimize_lm1_udl_for_response(
            self.project, placement, self.model, self.prepared, response,
            sign=sign, factors=self.factors, surface=self.surface,
        )
        if abs(sign * influence.response - best) > 1.0e-6 * max(1.0, abs(best)):
            raise RuntimeError("LM1 influence superposition and re-solved case disagree.")
        return LM1SignedResponseSearchResult(placement, influence, len(self.placements))

    def maximize(
        self,
        response: Callable[[GrillageAnalysisResult], float],
        *,
        sign: int = 1,
    ) -> LM1SignedResponseSearchResult:
        if sign not in (-1, 1):
            raise ValueError("Influence response sign must be +1 or -1.")
        unit = np.fromiter((response(result) for result in self.surface.unit_analyses),
                           dtype=float, count=len(self.surface.unit_analyses))
        tandem = np.fromiter((response(result) for result in self.tandem_analyses),
                             dtype=float, count=len(self.tandem_analyses))
        index, best = self._best_index(tandem, unit, sign, response)
        return self._resolved(index, best, response, sign)


def prepare_lm1_udl_influence_surface(
    model: StructuralModel,
    prepared: PreparedVerticalGrillage,
    *, control: AnalysisControl | None = None,
) -> LM1UDLInfluenceSurface:
    """Factor once, solve one unit-pressure case per carriageway grid cell.

    The caller should pass a grid whose carriageway and notional-lane edges
    are present. Cells outside the carriageway are omitted later, at selection.
    """
    x = sorted({node.x_m for node in model.nodes})
    y = sorted({node.y_m for node in model.nodes})
    cells = tuple(
        (x1, x2, y1, y2)
        for x1, x2 in pairwise(x)
        for y1, y2 in pairwise(y)
    )
    analyses = []
    if control is not None:
        control.report("Preparing grillage: UDL cells", 0, len(cells))
    for index, (x1, x2, y1, y2) in enumerate(cells, start=1):
        case = build_plan_load_case(
            model,
            load_case_id=index,
            name="LM1 unit UDL cell",
            area_loads=(PlanAreaLoad(x1, x2, y1, y2, 1.0),),
        )
        analyses.append(
            solve_prepared_vertical_grillage(
                prepared,
                replace(model, load_cases=(case,)),
            )
        )
        if control is not None:
            control.report("Preparing grillage: UDL cells", index, len(cells))
    return LM1UDLInfluenceSurface(cells, tuple(analyses))


def _cells(
    model: StructuralModel,
    placement: LM1SearchPlacement,
    adjustment: LM1AdjustmentFactors,
) -> tuple[PlanAreaLoad, ...]:
    x = sorted({node.x_m for node in model.nodes})
    y = sorted({node.y_m for node in model.nodes})
    strips = [
        (
            lane.y_start_m,
            lane.y_end_m,
            lm1_characteristic_lane_load(
                lane.lane_number,
                adjustment,
            ).udl_kn_m2,
        )
        for lane in placement.lanes
    ] + [
        (
            area.y_start_m,
            area.y_end_m,
            lm1_remaining_area_udl_kn_m2(adjustment),
        )
        for area in placement.remaining
    ]
    result = []
    for x1, x2 in pairwise(x):
        for y1, y2 in pairwise(y):
            pressure = next(
                (
                    q
                    for start, end, q in strips
                    if start <= y1 + 1.0e-9 and y2 <= end + 1.0e-9
                ),
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
        project,
        placement,
        factors=adjustment,
        udl_regions=regions,
    )
    case = build_plan_load_case(
        model,
        load_case_id=placement.case_id,
        name=f"LM1 signed influence placement {placement.case_id}",
        point_loads=points,
        area_loads=areas,
    )
    loaded_model = replace(model, load_cases=(case,))
    analysis = solve_prepared_vertical_grillage(prepared, loaded_model)
    return LM1InfluenceResult(
        regions,
        tuple(effects),
        response(analysis),
        analysis,
        loaded_model,
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
        project,
        factors=factors,
        longitudinal_step_m=longitudinal_step_m,
        max_exhaustive_tandem_combinations=max_exhaustive_tandem_combinations,
    )
    return context.maximize(response, sign=sign)


def prepare_lm1_influence_context(
    project: BridgeProject,
    *,
    factors: LM1AdjustmentFactors | None = None,
    longitudinal_step_m: float = 1.2,
    max_exhaustive_tandem_combinations: int = 5000,
    control: AnalysisControl | None = None,
) -> LM1InfluenceContext:
    """Prepare the shared influence surface and complete tandem solutions."""
    placements = generate_lm1_search_placements(
        project,
        longitudinal_step_m=longitudinal_step_m,
        max_exhaustive_tandem_combinations=max_exhaustive_tandem_combinations,
    )
    if not placements:
        raise ValueError("No LM1 tandem placements were generated.")
    x, y = _fixed_search_grid(project, placements)
    model = build_final_composite_grillage(
        project,
        stations_m=x,
        additional_y_lines_m=y,
    ).model
    prepared = prepare_vertical_grillage(model)
    surface = prepare_lm1_udl_influence_surface(model, prepared, control=control)
    adjustment = factors or LM1AdjustmentFactors()
    tandems = []
    all_pressures = []
    if control is not None:
        control.report("Preparing grillage: tandems", 0, len(placements))
    for index, placement in enumerate(placements, start=1):
        active = {
            (cell.x_start_m, cell.x_end_m, cell.y_start_m, cell.y_end_m):
            cell.pressure_kn_m2
            for cell in _cells(model, placement, adjustment)
        }
        points, _ = build_lm1_plan_loads(
            project,
            placement,
            factors=adjustment,
            udl_regions=(),
        )
        tandem = build_plan_load_case(
            model,
            load_case_id=placement.case_id,
            name="LM1 complete tandems",
            point_loads=points,
        )
        tandems.append(
            solve_prepared_vertical_grillage(
                prepared,
                replace(model, load_cases=(tandem,)),
            )
        )
        all_pressures.append(
            tuple(active.get(bounds, 0.0) for bounds in surface.cells)
        )
        if control is not None:
            control.report("Preparing grillage: tandems", index, len(placements))
    member_ids = tuple(member.member_id for member in tandems[0].members)
    member_attributes = (
        "i_vertical_force_kn", "i_vertical_bending_moment_knm", "i_torsion_knm",
        "j_vertical_force_kn", "j_vertical_bending_moment_knm", "j_torsion_knm",
    )
    def member_matrix(analyses: tuple[GrillageAnalysisResult, ...]) -> np.ndarray:
        return np.asarray([
            [[float(getattr(member, name)) for name in member_attributes]
             for member in analysis.members]
            for analysis in analyses
        ], dtype=float)
    def node_matrix(analyses: tuple[GrillageAnalysisResult, ...]) -> np.ndarray:
        return np.asarray([
            [[node.vertical_displacement_m, node.rotation_y_rad]
             for node in analysis.nodes]
            for analysis in analyses
        ], dtype=float)
    return LM1InfluenceContext(
        project,
        placements,
        model,
        prepared,
        surface,
        tuple(tandems),
        tuple(all_pressures),
        adjustment,
        pressure_matrix=np.asarray(all_pressures, dtype=float),
        member_ids=member_ids,
        tandem_member_values=member_matrix(tuple(tandems)),
        unit_member_values=member_matrix(surface.unit_analyses),
        node_ids=tuple(node.node_id for node in tandems[0].nodes),
        tandem_node_values=node_matrix(tuple(tandems)),
        unit_node_values=node_matrix(surface.unit_analyses),
    )


def _weighted_full_udl_analysis(
    full: GrillageAnalysisResult,
    tandem: GrillageAnalysisResult,
    tandem_scale: float,
    udl_scale: float,
) -> GrillageAnalysisResult:
    """Apply a*T + b*(F-T) to all linear grillage responses."""
    if tuple(item.node_id for item in full.nodes) != tuple(item.node_id for item in tandem.nodes):
        raise ValueError("LM1 full and tandem node bases differ.")
    if tuple(item.member_id for item in full.members) != tuple(
        item.member_id for item in tandem.members
    ):
        raise ValueError("LM1 full and tandem member bases differ.")
    full_factor = udl_scale
    tandem_factor = tandem_scale - udl_scale

    def value(a: float, b: float) -> float:
        return full_factor * a + tandem_factor * b

    node_fields = (
        "vertical_displacement_m", "rotation_x_rad", "rotation_y_rad", "vertical_reaction_kn",
    )
    member_fields = (
        "i_vertical_force_kn", "i_vertical_bending_moment_knm", "i_torsion_knm",
        "j_vertical_force_kn", "j_vertical_bending_moment_knm", "j_torsion_knm",
    )
    return replace(
        full,
        nodes=tuple(replace(a, **{name: value(getattr(a, name), getattr(b, name))
                                  for name in node_fields})
                    for a, b in zip(full.nodes, tandem.nodes, strict=True)),
        members=tuple(replace(a, **{name: value(getattr(a, name), getattr(b, name))
                                    for name in member_fields})
                      for a, b in zip(full.members, tandem.members, strict=True)),
        total_applied_vertical_load_kn=value(
            full.total_applied_vertical_load_kn, tandem.total_applied_vertical_load_kn,
        ),
        total_vertical_reaction_kn=value(
            full.total_vertical_reaction_kn, tandem.total_vertical_reaction_kn,
        ),
        vertical_equilibrium_residual_kn=value(
            full.vertical_equilibrium_residual_kn, tandem.vertical_equilibrium_residual_kn,
        ),
    )


def run_lm1_influence_grillage_search(
    project: BridgeProject,
    *,
    factors: LM1AdjustmentFactors | None = None,
    longitudinal_step_m: float = 1.2,
    max_exhaustive_tandem_combinations: int = 5000,
    context: LM1InfluenceContext | None = None,
    control: AnalysisControl | None = None,
    phase: str = "LM1 characteristic",
) -> LM1SearchResult:
    """Envelope member ends and fixed deflection stations with favourable UDL.

    Every stored governing case is a re-solved physical TS + selected UDL
    patch case. Deflection is sampled at nodes and quarter points of each
    longitudinal element; refine the longitudinal grid for convergence.
    """
    if context is None:
        context = prepare_lm1_influence_context(
            project,
            factors=factors,
            longitudinal_step_m=longitudinal_step_m,
            max_exhaustive_tandem_combinations=max_exhaustive_tandem_combinations,
            control=control,
        )
    elif (context.project != project or context.factors != (factors or LM1AdjustmentFactors())
          or context.placements != generate_lm1_search_placements(
              project, longitudinal_step_m=longitudinal_step_m,
              max_exhaustive_tandem_combinations=max_exhaustive_tandem_combinations)):
        raise ValueError("Supplied LM1 context does not match project, factors or search grid.")
    groups = _longitudinal_groups(context.model)
    nodes = {node.node_id: node for node in context.model.nodes}
    member_index_by_id = {member_id: index for index, member_id in enumerate(context.member_ids)}
    registered: dict[
        tuple[int, tuple[Bounds, ...] | None], LM1CaseResult | _DeferredLM1Case
    ] = {}
    registered_key_by_id: dict[int, tuple[int, tuple[Bounds, ...] | None]] = {}
    superposed_full_ids: set[int] = set()

    def register(placement, regions, model, analysis):
        key = (placement.case_id, regions)
        if key not in registered or isinstance(registered[key], _DeferredLM1Case):
            case_id = (
                registered[key].placement.case_id if key in registered
                else len(context.placements) + len(registered) + 1
            )
            original_case = model.load_cases[0]
            tagged_model = replace(
                model,
                load_cases=(replace(original_case, load_case_id=case_id),),
            )
            tagged_analysis = replace(analysis, load_case_id=case_id)
            tagged_placement = replace(placement, case_id=case_id)
            registered[key] = LM1CaseResult(
                tagged_placement,
                tagged_model,
                tagged_analysis,
                native_traffic_girder_envelope(tagged_model, tagged_analysis),
            )
            registered_key_by_id[case_id] = key
        result = registered[key]
        assert isinstance(result, LM1CaseResult)
        return result

    def reserve_case(placement, regions):
        key = (placement.case_id, regions)
        existing = registered.get(key)
        if existing is None:
            case_id = len(context.placements) + len(registered) + 1
            points, areas = build_lm1_plan_loads(
                project, placement, factors=context.factors, udl_regions=regions,
            )
            physical = build_plan_load_case(
                context.model, load_case_id=case_id,
                name=f"LM1 signed influence placement {placement.case_id}",
                point_loads=points, area_loads=areas,
            )
            model = replace(context.model, load_cases=(physical,))
            existing = _DeferredLM1Case(
                replace(placement, case_id=case_id), model, (),
            )
            registered[key] = existing
            registered_key_by_id[case_id] = key
        return key, existing

    def register_deferred(placement, regions, member_id, attribute, sign, value):
        key, existing = reserve_case(placement, regions)
        if isinstance(existing, _DeferredLM1Case):
            existing = replace(existing, checks=existing.checks + (
                (member_id, attribute, sign, value),
            ))
            registered[key] = existing
        return existing.placement.case_id

    def register_displacement(placement, regions, girder, x_m, sign, value):
        key, existing = reserve_case(placement, regions)
        if isinstance(existing, _DeferredLM1Case):
            existing = replace(existing, displacement_checks=(
                *existing.displacement_checks, (girder, x_m, sign, value),
            ))
            registered[key] = existing
        return existing.placement.case_id

    def resolve_by_id(case_id: int) -> LM1CaseResult:
        key = registered_key_by_id[case_id]
        case = registered[key]
        if isinstance(case, _DeferredLM1Case):
            physical = solve_prepared_vertical_grillage(context.prepared, case.model)
            by_id = {member.member_id: member for member in physical.members}
            for member_id, attribute, sign, predicted in case.checks:
                actual = sign * float(getattr(by_id[member_id], attribute))
                if abs(actual - predicted) > 1e-6 * max(1.0, abs(predicted)):
                    raise RuntimeError("LM1 member influence and physical case disagree.")
            for girder, x_m, sign, predicted in case.displacement_checks:
                actual = sign * girder_vertical_displacement_mm(
                    case.model, physical, girder_index=girder, x_m=x_m,
                )
                if abs(actual - predicted) > 1e-6 * max(1.0, abs(predicted)):
                    raise RuntimeError("LM1 displacement influence and physical case disagree.")
            case = LM1CaseResult(
                case.placement, case.model, physical,
                native_traffic_girder_envelope(case.model, physical),
            )
            registered[key] = case
        return case

    full_udl_cases = []
    if control is not None:
        control.report(f"{phase}: full UDL", 0, len(context.placements))
    for index, placement in enumerate(context.placements):
        points, areas = build_lm1_plan_loads(
            project,
            placement,
            factors=context.factors,
        )
        case = build_plan_load_case(
            context.model,
            load_case_id=placement.case_id,
            name="LM1 full UDL comparison",
            point_loads=points,
            area_loads=areas,
        )
        model = replace(context.model, load_cases=(case,))
        characteristic = context.full_udl_analyses.get(placement.case_id)
        if characteristic is not None:
            analysis = _weighted_full_udl_analysis(
                characteristic, context.tandem_analyses[index],
                context.tandem_scale, context.udl_scale,
            )
        else:
            analysis = solve_prepared_vertical_grillage(context.prepared, model)
            if context.tandem_scale == context.udl_scale == 1.0:
                context.full_udl_analyses[placement.case_id] = analysis
        registered_case = register(placement, None, model, analysis)
        if characteristic is not None:
            superposed_full_ids.add(registered_case.placement.case_id)
        full_udl_cases.append(registered_case)
        if control is not None:
            control.report(f"{phase}: full UDL", index + 1, len(context.placements))

    # Symmetric traffic positions can have indistinguishable deflections in
    # superposition to machine precision. Re-solve the few near-tied full-UDL
    # maxima before the strict first-winner comparison below, preserving the
    # original governing case IDs and continuous Hermite extrema.
    if superposed_full_ids:
        maxima = [max(case.girders[i].deflection_mm for case in full_udl_cases)
                  for i in range(len(groups))]
        for index, case in enumerate(full_udl_cases):
            if not any(abs(case.girders[i].deflection_mm - maximum)
                       <= 1.0e-10 * max(1.0, abs(maximum))
                       for i, maximum in enumerate(maxima)):
                continue
            physical = solve_prepared_vertical_grillage(context.prepared, case.model)
            exact = native_traffic_girder_envelope(case.model, physical)
            full_udl_cases[index] = replace(case, analysis=physical, girders=exact)
            registered[(context.placements[index].case_id, None)] = full_udl_cases[index]
            superposed_full_ids.discard(case.placement.case_id)

    girders = []
    station_girders = []
    if control is not None:
        control.report(f"{phase}: governing girders", 0, len(groups))
    for girder_index, (y_m, beams) in enumerate(groups, start=1):
        best = {
            name: GoverningComponent(-1.0, 0, None)
            for name in ("moment", "shear", "torsion", "deflection")
        }
        stations: dict[float, GoverningComponent] = {}
        deflection_position = 0.0
        for beam in beams:
            if control is not None:
                control.report(f"{phase}: governing girders", girder_index - 1, len(groups))
            for end in ("i", "j"):
                x_m = nodes[beam.node_i if end == "i" else beam.node_j].x_m
                for name, attribute in (
                    ("moment", f"{end}_vertical_bending_moment_knm"),
                    ("shear", f"{end}_vertical_force_kn"),
                    ("torsion", f"{end}_torsion_knm"),
                ):

                    for sign in (-1, 1):
                        placement, regions, value = context.select_member(
                            beam.member_id, attribute, sign=sign,
                        )
                        case_id = register_deferred(
                            placement, regions, beam.member_id, attribute, sign, value,
                        )
                        candidate = GoverningComponent(
                            value, case_id, None,
                        )
                        candidate = replace(candidate, member_id=beam.member_id)
                        station_best = stations.get(
                            x_m, GoverningComponent(-1.0, 0, None),
                        ) if name == "moment" else None
                        near_global = candidate.value >= best[name].value - (
                            1.0e-8 * max(1.0, abs(best[name].value))
                        )
                        near_station = (
                            station_best is not None and candidate.value >= station_best.value -
                            1.0e-8 * max(1.0, abs(station_best.value))
                        )
                        if near_global or near_station:
                            # The legacy search compares *physically solved*
                            # responses for every trial. Superposition can
                            # reverse near-equal member-end winners by roundoff;
                            # re-solve record breakers and close contenders.
                            physical = resolve_by_id(case_id).analysis
                            member = physical.members[member_index_by_id[beam.member_id]]
                            candidate = replace(
                                candidate, value=sign * float(getattr(member, attribute)),
                            )
                        if candidate.value > best[name].value:
                            best[name] = candidate
                        if station_best is not None and candidate.value > station_best.value:
                            stations[x_m] = candidate
        x_samples = {
            node.x_m
            for beam in beams
            for node in (nodes[beam.node_i], nodes[beam.node_j])
        }
        for beam in beams:
            x1, x2 = nodes[beam.node_i].x_m, nodes[beam.node_j].x_m
            x_samples.update(
                x1 + (x2 - x1) * ratio
                for ratio in (0.25, 0.5, 0.75)
            )
        for x_m in sorted(x_samples):
            if control is not None:
                control.report(f"{phase}: governing girders", girder_index - 1, len(groups))
            for sign in (-1, 1):
                placement, regions, predicted, exact, exact_position = (
                    context.select_displacement(girder_index, x_m, sign=sign)
                )
                case_id = register_displacement(
                    placement, regions, girder_index, x_m, sign, predicted,
                )
                current = best["deflection"]
                if (current.case_id and abs(exact - current.value)
                        <= 1.0e-10 * max(1.0, abs(exact), abs(current.value))):
                    current_case = resolve_by_id(current.case_id)
                    current_exact = current_case.girders[girder_index - 1]
                    best["deflection"] = replace(
                        current, value=current_exact.deflection_mm,
                    )
                    deflection_position = current_exact.deflection_position_m
                    candidate_case = resolve_by_id(case_id)
                    exact_result = candidate_case.girders[girder_index - 1]
                    exact, exact_position = (
                        exact_result.deflection_mm, exact_result.deflection_position_m,
                    )
                if exact > best["deflection"].value:
                    best["deflection"] = GoverningComponent(
                        exact, case_id, None,
                    )
                    deflection_position = exact_position
        for case in full_udl_cases:
            exact = case.girders[girder_index - 1]
            if exact.deflection_mm > best["deflection"].value:
                best["deflection"] = GoverningComponent(
                    exact.deflection_mm,
                    case.placement.case_id,
                    None,
                )
                deflection_position = exact.deflection_position_m
        girders.append(
            LM1GirderGoverningEnvelope(
                girder_index,
                y_m,
                best["moment"],
                best["shear"],
                best["torsion"],
                best["deflection"],
                deflection_position,
            )
        )
        station_girders.append(
            LM1GirderStationMomentEnvelope(
                girder_index,
                y_m,
                tuple(
                    LM1StationMomentEnvelope(x, item)
                    for x, item in sorted(stations.items())
                ),
            )
        )
        if control is not None:
            control.report(f"{phase}: governing girders", girder_index, len(groups))
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
        for component in (
            girder.moment_knm,
            girder.shear_kn,
            girder.torsion_knm,
            girder.deflection_mm,
        )
    }
    needed.update(
        station.moment_knm.case_id
        for girder in station_girders
        for station in girder.stations
    )
    def final_case(case: LM1CaseResult | _DeferredLM1Case) -> LM1CaseResult:
        if isinstance(case, _DeferredLM1Case):
            return resolve_by_id(case.placement.case_id)
        if case.placement.case_id not in superposed_full_ids:
            return case
        physical = solve_prepared_vertical_grillage(context.prepared, case.model)
        exact = native_traffic_girder_envelope(case.model, physical)
        for calculated, confirmed in zip(case.girders, exact, strict=True):
            for field_name in ("moment_knm", "shear_kn", "torsion_knm", "deflection_mm"):
                expected = getattr(calculated, field_name)
                actual = getattr(confirmed, field_name)
                if abs(actual - expected) > 1.0e-6 * max(1.0, abs(actual)):
                    raise RuntimeError("Superposed and physically solved LM1 full UDL differ.")
        return replace(case, analysis=physical, girders=exact)

    if control is not None:
        control.report(f"{phase}: verifying cases", 0, len(needed))
    retained_cases = []
    for case in registered.values():
        if case.placement.case_id in needed:
            retained_cases.append(final_case(case))
            if control is not None:
                control.report(f"{phase}: verifying cases", len(retained_cases), len(needed))
    return LM1SearchResult(
        tuple(girders),
        tuple(station_girders),
        tuple(retained_cases),
        len(context.placements),
        longitudinal_step_m,
        exhaustive,
        theoretical,
        "fixed-grid signed member-end and displacement influence-surface UDL",
    )
