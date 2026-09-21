from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import permutations, product

from rc_single_span.analysis.grillage import build_final_composite_grillage
from rc_single_span.analysis.grillage_solver import GrillageAnalysisResult
from rc_single_span.analysis.plan_loads import (
    PlanAreaLoad,
    PlanPointLoad,
    build_plan_load_case,
)
from rc_single_span.analysis.prepared_grillage import (
    prepare_vertical_grillage,
    solve_prepared_vertical_grillage,
)
from rc_single_span.analysis.structural_model import StructuralModel
from rc_single_span.analysis.traffic_envelope import (
    GirderCaseEnvelope,
    native_traffic_girder_envelope,
)
from rc_single_span.codes.eurocode.lm1 import (
    LM1AdjustmentFactors,
    lm1_characteristic_lane_load,
    lm1_remaining_area_udl_kn_m2,
    notional_lane_layout,
)
from rc_single_span.core.models import BridgeProject

LM1_AXLE_SPACING_M = 1.2
LM1_TRANSVERSE_WHEEL_SPACING_M = 2.0


@dataclass(frozen=True)
class LM1LanePlacement:
    lane_number: int
    y_start_m: float
    y_end_m: float
    tandem_lead_x_m: float

    @property
    def centre_y_m(self) -> float:
        return 0.5 * (self.y_start_m + self.y_end_m)


@dataclass(frozen=True)
class LM1RemainingAreaPlacement:
    y_start_m: float
    y_end_m: float


@dataclass(frozen=True)
class LM1SearchPlacement:
    case_id: int
    lanes: tuple[LM1LanePlacement, ...]
    remaining: tuple[LM1RemainingAreaPlacement, ...]


@dataclass(frozen=True)
class GoverningComponent:
    value: float
    case_id: int
    member_id: int | None


@dataclass(frozen=True)
class LM1GirderGoverningEnvelope:
    girder_index: int
    y_m: float
    moment_knm: GoverningComponent
    shear_kn: GoverningComponent
    torsion_knm: GoverningComponent
    deflection_mm: GoverningComponent
    deflection_position_m: float


@dataclass(frozen=True)
class LM1CaseResult:
    placement: LM1SearchPlacement
    model: StructuralModel
    analysis: GrillageAnalysisResult
    girders: tuple[GirderCaseEnvelope, ...]


@dataclass(frozen=True)
class LM1SearchResult:
    girders: tuple[LM1GirderGoverningEnvelope, ...]
    cases: tuple[LM1CaseResult, ...]
    evaluated_case_count: int
    longitudinal_step_m: float
    tandem_combinations_exhaustive: bool
    theoretical_tandem_combinations_per_transverse_layout: int
    search_strategy: str


@dataclass(frozen=True)
class LM1ConvergenceStep:
    coarse_step_m: float
    fine_step_m: float
    maximum_relative_change: float
    governing_quantity: str
    girder_index: int


@dataclass(frozen=True)
class LM1ConvergenceResult:
    result: LM1SearchResult
    refinements: tuple[LM1ConvergenceStep, ...]
    relative_tolerance: float

    @property
    def converged(self) -> bool:
        return bool(self.refinements) and (
            self.refinements[-1].maximum_relative_change
            <= self.relative_tolerance + 1.0e-12
        )


def _merge_coordinates(values: tuple[float, ...]) -> tuple[float, ...]:
    result: list[float] = []
    for value in sorted(values):
        if not result or abs(value - result[-1]) > 1.0e-9:
            result.append(value)
    return tuple(result)


def _lead_positions(span_m: float, step_m: float) -> tuple[float, ...]:
    if step_m <= 0.0:
        raise ValueError("LM1 longitudinal search step must be positive.")
    start = -LM1_AXLE_SPACING_M
    values = [start, 0.0, span_m - LM1_AXLE_SPACING_M, span_m]
    x = start
    while x <= span_m + 1.0e-9:
        values.append(round(x, 12))
        x += step_m
    return _merge_coordinates(
        tuple(min(max(value, start), span_m) for value in values)
    )


def _transverse_layouts(
    project: BridgeProject,
) -> tuple[
    tuple[
        tuple[tuple[int, float, float], ...],
        tuple[tuple[float, float], ...],
    ],
    ...,
]:
    geometry = project.geometry
    layout = notional_lane_layout(float(geometry.carriageway_width_m))
    left = (
        float(geometry.carriageway_offset_m)
        - float(geometry.carriageway_width_m) / 2.0
    )
    right = (
        float(geometry.carriageway_offset_m)
        + float(geometry.carriageway_width_m) / 2.0
    )
    lane_width = float(layout.lane_width_m)
    remaining_width = float(layout.remaining_width_m)
    lane_numbers = tuple(range(1, layout.lane_count + 1))

    edge_modes = ("left",) if remaining_width <= 1.0e-12 else ("left", "right")
    generated = []
    seen = set()
    for remainder_edge in edge_modes:
        lane_left = left + remaining_width if remainder_edge == "left" else left
        slots = tuple(
            (
                lane_left + index * lane_width,
                lane_left + (index + 1) * lane_width,
            )
            for index in range(layout.lane_count)
        )
        remaining = (
            ((left, left + remaining_width),)
            if remainder_edge == "left" and remaining_width > 1.0e-12
            else ((right - remaining_width, right),)
            if remaining_width > 1.0e-12
            else ()
        )
        for numbering in permutations(lane_numbers):
            lanes = tuple(
                (lane_number, slot[0], slot[1])
                for lane_number, slot in zip(numbering, slots, strict=True)
            )
            item = (lanes, remaining)
            if item not in seen:
                seen.add(item)
                generated.append(item)
    return tuple(generated)


def _position_vectors(
    lane_count: int,
    positions: tuple[float, ...],
    *,
    max_exhaustive_combinations: int,
) -> tuple[tuple[tuple[float, ...], ...], bool, int]:
    theoretical = len(positions) ** lane_count
    if theoretical <= max_exhaustive_combinations:
        return tuple(product(positions, repeat=lane_count)), True, theoretical

    candidates: list[tuple[float, ...]] = []
    seen: set[tuple[float, ...]] = set()

    def add(values: tuple[float, ...]) -> None:
        if values not in seen:
            seen.add(values)
            candidates.append(values)

    for position in positions:
        add((position,) * lane_count)

    seed_indices = {0, len(positions) // 2, len(positions) - 1}
    for seed_index in sorted(seed_indices):
        base = [positions[seed_index]] * lane_count
        for lane_index in range(lane_count):
            for position in positions:
                trial = base.copy()
                trial[lane_index] = position
                add(tuple(trial))

    if lane_count >= 2 and len(positions) ** 2 <= max_exhaustive_combinations:
        middle = positions[len(positions) // 2]
        base = [middle] * lane_count
        for p1 in positions:
            for p2 in positions:
                trial = base.copy()
                trial[0] = p1
                trial[1] = p2
                add(tuple(trial))

    return tuple(candidates), False, theoretical


def generate_lm1_search_placements(
    project: BridgeProject,
    *,
    longitudinal_step_m: float = 1.2,
    max_exhaustive_tandem_combinations: int = 5000,
) -> tuple[LM1SearchPlacement, ...]:
    layout = notional_lane_layout(float(project.geometry.carriageway_width_m))
    positions = _lead_positions(float(project.geometry.span_m), longitudinal_step_m)
    vectors, _, _ = _position_vectors(
        layout.lane_count,
        positions,
        max_exhaustive_combinations=max_exhaustive_tandem_combinations,
    )
    placements: list[LM1SearchPlacement] = []
    case_id = 1
    for lanes, remaining in _transverse_layouts(project):
        for vector in vectors:
            by_lane = {
                lane_number: vector[lane_number - 1]
                for lane_number in range(1, layout.lane_count + 1)
            }
            placements.append(
                LM1SearchPlacement(
                    case_id=case_id,
                    lanes=tuple(
                        LM1LanePlacement(
                            lane_number,
                            y_start,
                            y_end,
                            by_lane[lane_number],
                        )
                        for lane_number, y_start, y_end in lanes
                    ),
                    remaining=tuple(
                        LM1RemainingAreaPlacement(y_start, y_end)
                        for y_start, y_end in remaining
                    ),
                )
            )
            case_id += 1
    return tuple(placements)


def build_lm1_plan_loads(
    project: BridgeProject,
    placement: LM1SearchPlacement,
    *,
    factors: LM1AdjustmentFactors | None = None,
) -> tuple[tuple[PlanPointLoad, ...], tuple[PlanAreaLoad, ...]]:
    span = float(project.geometry.span_m)
    points: list[PlanPointLoad] = []
    areas: list[PlanAreaLoad] = []
    adjustment = factors or LM1AdjustmentFactors()

    for lane_placement in placement.lanes:
        lane = lm1_characteristic_lane_load(
            lane_placement.lane_number,
            adjustment,
        )
        areas.append(
            PlanAreaLoad(
                0.0,
                span,
                lane_placement.y_start_m,
                lane_placement.y_end_m,
                lane.udl_kn_m2,
                label=f"LM1 lane {lane_placement.lane_number} UDL",
            )
        )
        if lane.axle_load_kn <= 0.0:
            continue
        wheel_y = (
            lane_placement.centre_y_m - LM1_TRANSVERSE_WHEEL_SPACING_M / 2.0,
            lane_placement.centre_y_m + LM1_TRANSVERSE_WHEEL_SPACING_M / 2.0,
        )
        if (
            wheel_y[0] < lane_placement.y_start_m - 1.0e-9
            or wheel_y[1] > lane_placement.y_end_m + 1.0e-9
        ):
            raise ValueError("LM1 tandem wheel centres do not fit in the notional lane.")
        wheel_load = lane.axle_load_kn / 2.0
        for axle_number, axle_x in enumerate(
            (
                lane_placement.tandem_lead_x_m,
                lane_placement.tandem_lead_x_m + LM1_AXLE_SPACING_M,
            ),
            start=1,
        ):
            if not -1.0e-9 <= axle_x <= span + 1.0e-9:
                continue
            x_m = min(max(axle_x, 0.0), span)
            for wheel_number, y_m in enumerate(wheel_y, start=1):
                points.append(
                    PlanPointLoad(
                        x_m,
                        y_m,
                        wheel_load,
                        label=(
                            f"LM1 lane {lane_placement.lane_number} "
                            f"axle {axle_number} wheel {wheel_number}"
                        ),
                    )
                )

    remaining_pressure = lm1_remaining_area_udl_kn_m2(adjustment)
    for index, remaining in enumerate(placement.remaining, start=1):
        areas.append(
            PlanAreaLoad(
                0.0,
                span,
                remaining.y_start_m,
                remaining.y_end_m,
                remaining_pressure,
                label=f"LM1 remaining area {index}",
            )
        )
    return tuple(points), tuple(areas)


def _fixed_search_grid(
    project: BridgeProject,
    placements: tuple[LM1SearchPlacement, ...],
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    span = float(project.geometry.span_m)
    x_values = [0.0, span]
    y_values: list[float] = []
    for placement in placements:
        for lane in placement.lanes:
            y_values.extend((lane.y_start_m, lane.y_end_m))
            y_values.extend(
                (
                    lane.centre_y_m - LM1_TRANSVERSE_WHEEL_SPACING_M / 2.0,
                    lane.centre_y_m + LM1_TRANSVERSE_WHEEL_SPACING_M / 2.0,
                )
            )
            for axle_x in (
                lane.tandem_lead_x_m,
                lane.tandem_lead_x_m + LM1_AXLE_SPACING_M,
            ):
                if -1.0e-9 <= axle_x <= span + 1.0e-9:
                    x_values.append(min(max(axle_x, 0.0), span))
        for remaining in placement.remaining:
            y_values.extend((remaining.y_start_m, remaining.y_end_m))
    return _merge_coordinates(tuple(x_values)), _merge_coordinates(tuple(y_values))


def _update_governing(
    governing: list[dict[str, object]],
    case_id: int,
    current: tuple[GirderCaseEnvelope, ...],
) -> None:
    if not governing:
        for item in current:
            governing.append(
                {
                    "y_m": item.y_m,
                    "moment": GoverningComponent(
                        item.moment_knm,
                        case_id,
                        item.governing_moment_member_id,
                    ),
                    "shear": GoverningComponent(
                        item.shear_kn,
                        case_id,
                        item.governing_shear_member_id,
                    ),
                    "torsion": GoverningComponent(
                        item.torsion_knm,
                        case_id,
                        item.governing_torsion_member_id,
                    ),
                    "deflection": GoverningComponent(
                        item.deflection_mm,
                        case_id,
                        None,
                    ),
                    "deflection_x": item.deflection_position_m,
                }
            )
        return

    for index, item in enumerate(current):
        row = governing[index]
        for key, value, member_id in (
            ("moment", item.moment_knm, item.governing_moment_member_id),
            ("shear", item.shear_kn, item.governing_shear_member_id),
            ("torsion", item.torsion_knm, item.governing_torsion_member_id),
        ):
            existing = row[key]
            assert isinstance(existing, GoverningComponent)
            if value > existing.value:
                row[key] = GoverningComponent(value, case_id, member_id)
        existing_deflection = row["deflection"]
        assert isinstance(existing_deflection, GoverningComponent)
        if item.deflection_mm > existing_deflection.value:
            row["deflection"] = GoverningComponent(
                item.deflection_mm,
                case_id,
                None,
            )
            row["deflection_x"] = item.deflection_position_m


def run_lm1_grillage_search(
    project: BridgeProject,
    *,
    factors: LM1AdjustmentFactors | None = None,
    longitudinal_step_m: float = 1.2,
    max_exhaustive_tandem_combinations: int = 5000,
    retain_all_cases: bool = False,
) -> LM1SearchResult:
    """Run LM1 on the common final-state grillage and envelope each girder.

    A single fixed topology contains every candidate tandem axle station and
    transverse lane/wheel coordinate. The sparse stiffness factorization is
    therefore reused for every traffic placement.
    """

    placements = generate_lm1_search_placements(
        project,
        longitudinal_step_m=longitudinal_step_m,
        max_exhaustive_tandem_combinations=max_exhaustive_tandem_combinations,
    )
    if not placements:
        raise RuntimeError("LM1 search generated no candidate placements.")

    lane_count = notional_lane_layout(
        float(project.geometry.carriageway_width_m)
    ).lane_count
    positions = _lead_positions(float(project.geometry.span_m), longitudinal_step_m)
    _, exhaustive, theoretical = _position_vectors(
        lane_count,
        positions,
        max_exhaustive_combinations=max_exhaustive_tandem_combinations,
    )
    x_grid, y_grid = _fixed_search_grid(project, placements)
    build = build_final_composite_grillage(
        project,
        stations_m=x_grid,
        additional_y_lines_m=y_grid,
    )
    prepared = prepare_vertical_grillage(build.model)

    governing: list[dict[str, object]] = []
    all_cases: list[LM1CaseResult] = []
    retained: dict[int, LM1CaseResult] = {}

    for placement in placements:
        points, areas = build_lm1_plan_loads(project, placement, factors=factors)
        case = build_plan_load_case(
            build.model,
            load_case_id=placement.case_id,
            name=f"LM1 search case {placement.case_id}",
            point_loads=points,
            area_loads=areas,
        )
        model = replace(
            build.model,
            name=f"{project.name} LM1 case {placement.case_id}",
            load_cases=(case,),
        )
        analysis = solve_prepared_vertical_grillage(prepared, model)
        if abs(analysis.vertical_equilibrium_residual_kn) > 1.0e-6:
            raise RuntimeError("LM1 grillage case failed vertical equilibrium.")
        case_girders = native_traffic_girder_envelope(model, analysis)
        _update_governing(governing, placement.case_id, case_girders)
        case_result = LM1CaseResult(placement, model, analysis, case_girders)

        if retain_all_cases:
            all_cases.append(case_result)
        else:
            current_ids = {
                component.case_id
                for row in governing
                for component in (
                    row["moment"],
                    row["shear"],
                    row["torsion"],
                    row["deflection"],
                )
                if isinstance(component, GoverningComponent)
            }
            if placement.case_id in current_ids:
                retained[placement.case_id] = case_result
            for case_id in tuple(retained):
                if case_id not in current_ids:
                    del retained[case_id]

    final_girders = tuple(
        LM1GirderGoverningEnvelope(
            girder_index=index + 1,
            y_m=float(row["y_m"]),
            moment_knm=row["moment"],
            shear_kn=row["shear"],
            torsion_knm=row["torsion"],
            deflection_mm=row["deflection"],
            deflection_position_m=float(row["deflection_x"]),
        )
        for index, row in enumerate(governing)
    )
    cases = (
        tuple(all_cases)
        if retain_all_cases
        else tuple(retained[key] for key in sorted(retained))
    )
    return LM1SearchResult(
        girders=final_girders,
        cases=cases,
        evaluated_case_count=len(placements),
        longitudinal_step_m=longitudinal_step_m,
        tandem_combinations_exhaustive=exhaustive,
        theoretical_tandem_combinations_per_transverse_layout=theoretical,
        search_strategy=(
            "fixed-topology sparse exhaustive independent tandems"
            if exhaustive
            else "fixed-topology sparse reduced independent tandems"
        ),
    )


def _refinement(
    coarse: LM1SearchResult,
    fine: LM1SearchResult,
) -> LM1ConvergenceStep:
    worst = (-1.0, "", 0)
    for coarse_girder, fine_girder in zip(coarse.girders, fine.girders, strict=True):
        for name, coarse_value, fine_value in (
            ("moment", coarse_girder.moment_knm.value, fine_girder.moment_knm.value),
            ("shear", coarse_girder.shear_kn.value, fine_girder.shear_kn.value),
            ("torsion", coarse_girder.torsion_knm.value, fine_girder.torsion_knm.value),
            (
                "deflection",
                coarse_girder.deflection_mm.value,
                fine_girder.deflection_mm.value,
            ),
        ):
            relative = abs(fine_value - coarse_value) / max(abs(fine_value), 1.0e-9)
            if relative > worst[0]:
                worst = (relative, name, fine_girder.girder_index)
    return LM1ConvergenceStep(
        coarse_step_m=coarse.longitudinal_step_m,
        fine_step_m=fine.longitudinal_step_m,
        maximum_relative_change=worst[0],
        governing_quantity=worst[1],
        girder_index=worst[2],
    )


def run_lm1_grillage_search_converged(
    project: BridgeProject,
    *,
    factors: LM1AdjustmentFactors | None = None,
    initial_longitudinal_step_m: float = 2.4,
    minimum_longitudinal_step_m: float = 0.6,
    relative_tolerance: float = 0.05,
    max_refinements: int = 3,
    max_exhaustive_tandem_combinations: int = 5000,
) -> LM1ConvergenceResult:
    if initial_longitudinal_step_m <= minimum_longitudinal_step_m:
        raise ValueError("Initial LM1 step must exceed the minimum step.")
    if not 0.0 < relative_tolerance < 1.0:
        raise ValueError("LM1 relative tolerance must lie in (0, 1).")

    current = run_lm1_grillage_search(
        project,
        factors=factors,
        longitudinal_step_m=initial_longitudinal_step_m,
        max_exhaustive_tandem_combinations=max_exhaustive_tandem_combinations,
    )
    if not current.tandem_combinations_exhaustive:
        raise RuntimeError("LM1 convergence cannot certify a reduced tandem search.")

    refinements: list[LM1ConvergenceStep] = []
    for _ in range(max_refinements):
        fine_step = max(
            minimum_longitudinal_step_m,
            current.longitudinal_step_m / 2.0,
        )
        if fine_step >= current.longitudinal_step_m - 1.0e-12:
            break
        fine = run_lm1_grillage_search(
            project,
            factors=factors,
            longitudinal_step_m=fine_step,
            max_exhaustive_tandem_combinations=max_exhaustive_tandem_combinations,
        )
        if not fine.tandem_combinations_exhaustive:
            raise RuntimeError("LM1 convergence cannot certify a reduced tandem search.")
        step = _refinement(current, fine)
        refinements.append(step)
        current = fine
        if step.maximum_relative_change <= relative_tolerance:
            break
        if fine_step <= minimum_longitudinal_step_m + 1.0e-12:
            break

    return LM1ConvergenceResult(
        result=current,
        refinements=tuple(refinements),
        relative_tolerance=relative_tolerance,
    )
