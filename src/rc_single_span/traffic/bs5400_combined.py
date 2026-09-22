from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from itertools import combinations, permutations, product

from rc_single_span.analysis.grillage import build_final_composite_grillage
from rc_single_span.analysis.grillage_solver import GrillageAnalysisResult
from rc_single_span.analysis.plan_loads import (
    PlanAreaLoad,
    PlanPointLoad,
    PlanTransverseLineLoad,
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
    native_traffic_girder_station_moments,
)
from rc_single_span.codes.bs5400.traffic import (
    HB_INNER_AXLE_SPACINGS_M,
    HALaneLoad,
    ha_lane_load_bd37_01,
    hb_vehicle_definition,
    notional_lane_layout_bd37_01,
)
from rc_single_span.core.models import BridgeProject
from rc_single_span.traffic.bs5400 import (
    BS5400ConvergenceResult,
    BS5400ConvergenceStep,
    BS5400GirderGoverningEnvelope,
    BS5400GirderStationMomentEnvelope,
    GoverningComponent,
    HBSearchPlacement,
    _compare_envelopes,
    _final_envelopes,
    _final_station_moments,
    _ha_lane_slots,
    _hb_centres,
    _hb_lead_positions,
    _kel_positions,
    _merge_coordinates,
    _position_vectors,
    _require_vertical_equilibrium,
    _update_governing,
    _update_station_moment_governing,
    build_hb_plan_loads,
)


class HAHBLaneTreatment(str, Enum):
    UNOCCUPIED = "unoccupied"
    DISPLACED_CLEAR_ZONE = "displaced_clear_zone"
    RESIDUAL_2P5 = "residual_width_ge_2p5"


@dataclass(frozen=True)
class HAHBLaneGeometry:
    physical_slot: int
    y_start_m: float
    y_end_m: float
    treatment: HAHBLaneTreatment
    residual_y_start_m: float | None = None
    residual_y_end_m: float | None = None

    @property
    def lane_width_m(self) -> float:
        return self.y_end_m - self.y_start_m

    @property
    def residual_width_m(self) -> float:
        if self.residual_y_start_m is None or self.residual_y_end_m is None:
            return 0.0
        return self.residual_y_end_m - self.residual_y_start_m


@dataclass(frozen=True)
class HAHBHALanePlacement:
    geometry: HAHBLaneGeometry
    factor_rank: int
    kel_x_m: float | None


@dataclass(frozen=True)
class HAHBCombinedPlacement:
    case_id: int
    hb: HBSearchPlacement
    ha_lanes: tuple[HAHBHALanePlacement, ...]


@dataclass(frozen=True)
class HAHBCombinedCaseResult:
    placement: HAHBCombinedPlacement
    model: StructuralModel
    analysis: GrillageAnalysisResult
    girders: tuple[GirderCaseEnvelope, ...]
    description: str


@dataclass(frozen=True)
class HAHBCombinedSearchResult:
    girders: tuple[BS5400GirderGoverningEnvelope, ...]
    station_moments: tuple[BS5400GirderStationMomentEnvelope, ...]
    cases: tuple[HAHBCombinedCaseResult, ...]
    evaluated_case_count: int
    hb_units: float
    hb_longitudinal_step_m: float
    hb_transverse_step_m: float
    ha_kel_step_m: float
    ha_assignment_search_exhaustive: bool
    kel_combinations_exhaustive: bool
    checked_inner_axle_spacings_m: tuple[float, ...]


def classify_ha_lanes_for_hb(
    project: BridgeProject,
    hb: HBSearchPlacement,
) -> tuple[HAHBLaneGeometry, ...]:
    """Classify each notional lane under BD 37/01 6.4.2.

    A lane untouched by HB retains normal HA. A lane wholly containing HB, a
    lane wholly covered by HB, or a partially occupied lane with less than
    2.5 m remaining is treated as displaced and receives the longitudinal
    25 m clear-zone rule. A partially occupied lane with at least 2.5 m
    remaining keeps HA UDL only on the remaining strip and uses the 2.5 m
    lane-width factor basis.
    """

    half_hb = 1.75
    hb_left = hb.centre_y_m - half_hb
    hb_right = hb.centre_y_m + half_hb
    tolerance = 1.0e-9
    result: list[HAHBLaneGeometry] = []

    for physical_slot, y_start, y_end in _ha_lane_slots(project):
        overlap = max(0.0, min(y_end, hb_right) - max(y_start, hb_left))
        if overlap <= tolerance:
            result.append(
                HAHBLaneGeometry(
                    physical_slot,
                    y_start,
                    y_end,
                    HAHBLaneTreatment.UNOCCUPIED,
                )
            )
            continue

        hb_wholly_inside_lane = (
            hb_left >= y_start - tolerance and hb_right <= y_end + tolerance
        )
        lane_wholly_inside_hb = (
            y_start >= hb_left - tolerance and y_end <= hb_right + tolerance
        )
        if hb_wholly_inside_lane or lane_wholly_inside_hb:
            result.append(
                HAHBLaneGeometry(
                    physical_slot,
                    y_start,
                    y_end,
                    HAHBLaneTreatment.DISPLACED_CLEAR_ZONE,
                )
            )
            continue

        residual_candidates: list[tuple[float, float]] = []
        if hb_left > y_start + tolerance:
            residual_candidates.append((y_start, min(hb_left, y_end)))
        if hb_right < y_end - tolerance:
            residual_candidates.append((max(hb_right, y_start), y_end))

        residual_candidates = [
            item for item in residual_candidates if item[1] - item[0] > tolerance
        ]
        if residual_candidates:
            residual = max(
                residual_candidates,
                key=lambda item: item[1] - item[0],
            )
            if residual[1] - residual[0] >= 2.5 - tolerance:
                result.append(
                    HAHBLaneGeometry(
                        physical_slot,
                        y_start,
                        y_end,
                        HAHBLaneTreatment.RESIDUAL_2P5,
                        residual_y_start_m=residual[0],
                        residual_y_end_m=residual[1],
                    )
                )
                continue

        result.append(
            HAHBLaneGeometry(
                physical_slot,
                y_start,
                y_end,
                HAHBLaneTreatment.DISPLACED_CLEAR_ZONE,
            )
        )

    return tuple(result)


def _ha_assignment_sets(
    lane_geometries: tuple[HAHBLaneGeometry, ...],
    *,
    max_exhaustive_assignments: int,
) -> tuple[
    tuple[tuple[tuple[HAHBLaneGeometry, int], ...], ...],
    bool,
]:
    if max_exhaustive_assignments < 1:
        raise ValueError("max_exhaustive_ha_assignments must be positive.")

    exhaustive: list[tuple[tuple[HAHBLaneGeometry, int], ...]] = []
    for loaded_count in range(1, len(lane_geometries) + 1):
        for selected in combinations(lane_geometries, loaded_count):
            for ranks in permutations(range(1, loaded_count + 1)):
                exhaustive.append(tuple(zip(selected, ranks, strict=True)))

    if len(exhaustive) <= max_exhaustive_assignments:
        return tuple(exhaustive), True

    reduced: list[tuple[tuple[HAHBLaneGeometry, int], ...]] = []
    seen: set[tuple[tuple[int, int], ...]] = set()

    def add(items: tuple[tuple[HAHBLaneGeometry, int], ...]) -> None:
        signature = tuple((item.physical_slot, rank) for item, rank in items)
        if signature not in seen:
            seen.add(signature)
            reduced.append(items)

    for lane in lane_geometries:
        add(((lane, 1),))

    identity = tuple(
        (lane, rank)
        for rank, lane in enumerate(lane_geometries, start=1)
    )
    reverse = tuple(
        (lane, rank)
        for rank, lane in enumerate(reversed(lane_geometries), start=1)
    )
    add(identity)
    add(reverse)

    for shift in range(1, len(lane_geometries)):
        rotated = lane_geometries[shift:] + lane_geometries[:shift]
        add(tuple((lane, rank) for rank, lane in enumerate(rotated, start=1)))

    return tuple(reduced), False


def _clear_zone_on_span(
    project: BridgeProject,
    hb: HBSearchPlacement,
) -> tuple[float, float]:
    vehicle = hb_vehicle_definition(
        units=hb.units,
        inner_axle_spacing_m=hb.inner_axle_spacing_m,
    )
    axle_positions = tuple(hb.lead_x_m + value for value in vehicle.axle_offsets_m)
    clear_start = min(axle_positions) - 25.0
    clear_end = max(axle_positions) + 25.0
    span = float(project.geometry.span_m)
    return max(0.0, clear_start), min(span, clear_end)


def _ha_load_for_combined_lane(
    project: BridgeProject,
    lane: HAHBHALanePlacement,
) -> HALaneLoad:
    layout = notional_lane_layout_bd37_01(float(project.geometry.carriageway_width_m))
    width_for_factor = (
        2.5
        if lane.geometry.treatment is HAHBLaneTreatment.RESIDUAL_2P5
        else lane.geometry.lane_width_m
    )
    return ha_lane_load_bd37_01(
        factor_rank=lane.factor_rank,
        loaded_length_m=float(project.geometry.span_m),
        lane_width_m=width_for_factor,
        total_notional_lanes=layout.lane_count,
    )


def build_ha_hb_combined_plan_loads(
    project: BridgeProject,
    placement: HAHBCombinedPlacement,
) -> tuple[
    tuple[PlanPointLoad, ...],
    tuple[PlanAreaLoad, ...],
    tuple[PlanTransverseLineLoad, ...],
]:
    """Build one nominal BD 37/01 HA+HB coexistence load snapshot."""

    points = build_hb_plan_loads(project, placement.hb)
    span = float(project.geometry.span_m)
    clear_start, clear_end = _clear_zone_on_span(project, placement.hb)
    areas: list[PlanAreaLoad] = []
    lines: list[PlanTransverseLineLoad] = []

    for lane in placement.ha_lanes:
        geometry = lane.geometry
        load = _ha_load_for_combined_lane(project, lane)

        if geometry.treatment is HAHBLaneTreatment.UNOCCUPIED:
            areas.append(
                PlanAreaLoad(
                    0.0,
                    span,
                    geometry.y_start_m,
                    geometry.y_end_m,
                    load.udl_kn_m / geometry.lane_width_m,
                    label=(
                        f"HA+HB slot {geometry.physical_slot} normal HA UDL "
                        f"rank {lane.factor_rank}"
                    ),
                )
            )
            if lane.kel_x_m is None:
                raise ValueError("Unoccupied HA+HB lane requires one KEL position.")
            lines.append(
                PlanTransverseLineLoad(
                    lane.kel_x_m,
                    geometry.y_start_m,
                    geometry.y_end_m,
                    load.kel_kn,
                    label=(
                        f"HA+HB slot {geometry.physical_slot} normal HA KEL "
                        f"rank {lane.factor_rank}"
                    ),
                )
            )
            continue

        if geometry.treatment is HAHBLaneTreatment.RESIDUAL_2P5:
            if (
                geometry.residual_y_start_m is None
                or geometry.residual_y_end_m is None
                or geometry.residual_width_m < 2.5 - 1.0e-9
            ):
                raise RuntimeError("Residual-2.5 lane geometry is inconsistent.")
            areas.append(
                PlanAreaLoad(
                    0.0,
                    span,
                    geometry.residual_y_start_m,
                    geometry.residual_y_end_m,
                    load.udl_kn_m / geometry.residual_width_m,
                    label=(
                        f"HA+HB slot {geometry.physical_slot} residual HA UDL "
                        f"rank {lane.factor_rank}; 2.5 m factor basis"
                    ),
                )
            )
            continue

        if clear_start > 1.0e-9:
            areas.append(
                PlanAreaLoad(
                    0.0,
                    clear_start,
                    geometry.y_start_m,
                    geometry.y_end_m,
                    load.udl_kn_m / geometry.lane_width_m,
                    label=(
                        f"HA+HB slot {geometry.physical_slot} HA UDL before clear zone "
                        f"rank {lane.factor_rank}"
                    ),
                )
            )
        if clear_end < span - 1.0e-9:
            areas.append(
                PlanAreaLoad(
                    clear_end,
                    span,
                    geometry.y_start_m,
                    geometry.y_end_m,
                    load.udl_kn_m / geometry.lane_width_m,
                    label=(
                        f"HA+HB slot {geometry.physical_slot} HA UDL after clear zone "
                        f"rank {lane.factor_rank}"
                    ),
                )
            )

    return tuple(points), tuple(areas), tuple(lines)


def _combined_placements_for_hb(
    project: BridgeProject,
    hb: HBSearchPlacement,
    *,
    first_case_id: int,
    ha_kel_step_m: float,
    max_exhaustive_kel_combinations: int,
    max_exhaustive_ha_assignments: int,
) -> tuple[tuple[HAHBCombinedPlacement, ...], bool, bool]:
    geometries = classify_ha_lanes_for_hb(project, hb)
    assignments, assignment_exhaustive = _ha_assignment_sets(
        geometries,
        max_exhaustive_assignments=max_exhaustive_ha_assignments,
    )
    kel_positions = _kel_positions(float(project.geometry.span_m), ha_kel_step_m)
    placements: list[HAHBCombinedPlacement] = []
    kel_exhaustive_all = True
    case_id = first_case_id

    for assignment in assignments:
        unoccupied = tuple(
            item
            for item, _ in assignment
            if item.treatment is HAHBLaneTreatment.UNOCCUPIED
        )
        if unoccupied:
            vectors, kel_exhaustive = _position_vectors(
                len(unoccupied),
                kel_positions,
                maximum=max_exhaustive_kel_combinations,
            )
        else:
            vectors, kel_exhaustive = ((),), True
        kel_exhaustive_all = kel_exhaustive_all and kel_exhaustive

        for vector in vectors:
            kel_by_slot = {
                lane.physical_slot: kel_x
                for lane, kel_x in zip(unoccupied, vector, strict=True)
            }
            placements.append(
                HAHBCombinedPlacement(
                    case_id=case_id,
                    hb=hb,
                    ha_lanes=tuple(
                        HAHBHALanePlacement(
                            geometry=item,
                            factor_rank=rank,
                            kel_x_m=kel_by_slot.get(item.physical_slot),
                        )
                        for item, rank in assignment
                    ),
                )
            )
            case_id += 1

    return tuple(placements), assignment_exhaustive, kel_exhaustive_all


def _grid_for_combined_placements(
    project: BridgeProject,
    placements: tuple[HAHBCombinedPlacement, ...],
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    span = float(project.geometry.span_m)
    x_values: list[float] = [0.0, span]
    y_values: list[float] = []

    for placement in placements:
        vehicle = hb_vehicle_definition(
            units=placement.hb.units,
            inner_axle_spacing_m=placement.hb.inner_axle_spacing_m,
        )
        for offset in vehicle.axle_offsets_m:
            x_m = placement.hb.lead_x_m + offset
            if -1.0e-9 <= x_m <= span + 1.0e-9:
                x_values.append(min(max(x_m, 0.0), span))
        y_values.extend(
            placement.hb.centre_y_m + offset
            for offset in vehicle.wheel_y_offsets_m
        )

        clear_start, clear_end = _clear_zone_on_span(project, placement.hb)
        if 1.0e-9 < clear_start < span - 1.0e-9:
            x_values.append(clear_start)
        if 1.0e-9 < clear_end < span - 1.0e-9:
            x_values.append(clear_end)

        for lane in placement.ha_lanes:
            geometry = lane.geometry
            y_values.extend((geometry.y_start_m, geometry.y_end_m))
            if geometry.residual_y_start_m is not None:
                y_values.append(geometry.residual_y_start_m)
            if geometry.residual_y_end_m is not None:
                y_values.append(geometry.residual_y_end_m)
            if lane.kel_x_m is not None:
                x_values.append(lane.kel_x_m)

    return _merge_coordinates(tuple(x_values)), _merge_coordinates(tuple(y_values))


def run_ha_hb_combined_grillage_search(
    project: BridgeProject,
    *,
    units: float = 45.0,
    hb_longitudinal_step_m: float = 2.0,
    hb_transverse_step_m: float = 1.0,
    ha_kel_step_m: float = 2.0,
    max_exhaustive_kel_combinations: int = 5000,
    max_exhaustive_ha_assignments: int = 500,
    retain_all_cases: bool = False,
) -> HAHBCombinedSearchResult:
    """Search nominal HA+HB coexistence under BD 37/01 6.4.2.

    The search keeps exactly one HB vehicle on the superstructure. HA lane
    loadings remain interchangeable and may be omitted, following 6.4.1. For
    the user's two-lane bridge the HA assignment search is exhaustive.
    """

    centres = _hb_centres(project, hb_transverse_step_m)
    governing: list[dict[str, object]] = []
    station_governing: list[dict[str, object]] = []
    all_cases: list[HAHBCombinedCaseResult] = []
    retained: dict[int, HAHBCombinedCaseResult] = {}
    evaluated = 0
    next_case_id = 1
    assignment_exhaustive_all = True
    kel_exhaustive_all = True

    for spacing in HB_INNER_AXLE_SPACINGS_M:
        vehicle = hb_vehicle_definition(
            units=units,
            inner_axle_spacing_m=spacing,
        )
        leads = _hb_lead_positions(
            float(project.geometry.span_m),
            vehicle.axle_offsets_m,
            hb_longitudinal_step_m,
        )

        spacing_placements: list[HAHBCombinedPlacement] = []
        for lead_x, centre_y in product(leads, centres):
            hb = HBSearchPlacement(
                case_id=0,
                units=units,
                inner_axle_spacing_m=spacing,
                lead_x_m=lead_x,
                centre_y_m=centre_y,
            )
            generated, assignment_exhaustive, kel_exhaustive = (
                _combined_placements_for_hb(
                    project,
                    hb,
                    first_case_id=next_case_id,
                    ha_kel_step_m=ha_kel_step_m,
                    max_exhaustive_kel_combinations=max_exhaustive_kel_combinations,
                    max_exhaustive_ha_assignments=max_exhaustive_ha_assignments,
                )
            )
            if generated:
                next_case_id = generated[-1].case_id + 1
                spacing_placements.extend(generated)
            assignment_exhaustive_all = (
                assignment_exhaustive_all and assignment_exhaustive
            )
            kel_exhaustive_all = kel_exhaustive_all and kel_exhaustive

        if not spacing_placements:
            continue

        placements_tuple = tuple(spacing_placements)
        x_grid, y_grid = _grid_for_combined_placements(
            project,
            placements_tuple,
        )
        build = build_final_composite_grillage(
            project,
            stations_m=x_grid,
            additional_y_lines_m=y_grid,
        )
        prepared = prepare_vertical_grillage(build.model)

        for placement in placements_tuple:
            points, areas, lines = build_ha_hb_combined_plan_loads(
                project,
                placement,
            )
            case = build_plan_load_case(
                build.model,
                load_case_id=placement.case_id,
                name=f"BD 37/01 HA+HB case {placement.case_id}",
                point_loads=points,
                area_loads=areas,
                transverse_line_loads=lines,
            )
            model = replace(
                build.model,
                name=f"{project.name} HA+HB case {placement.case_id}",
                load_cases=(case,),
            )
            analysis = solve_prepared_vertical_grillage(prepared, model)
            _require_vertical_equilibrium(
                analysis,
                traffic_model="HA+HB",
            )
            girders = native_traffic_girder_envelope(model, analysis)
            _update_governing(
                governing,
                placement.case_id,
                girders,
            )
            station_moments = native_traffic_girder_station_moments(model, analysis)
            _update_station_moment_governing(
                station_governing,
                case_id=placement.case_id,
                current=station_moments,
            )
            treatments = ",".join(
                f"slot{lane.geometry.physical_slot}:{lane.geometry.treatment.value}"
                for lane in placement.ha_lanes
            )
            case_result = HAHBCombinedCaseResult(
                placement=placement,
                model=model,
                analysis=analysis,
                girders=girders,
                description=(
                    f"BD 37/01 HA+HB, HB {units:g} units, inner spacing "
                    f"{spacing:g} m, centre y={placement.hb.centre_y_m:.6g} m; "
                    f"HA {treatments}"
                ),
            )
            evaluated += 1

            if retain_all_cases:
                all_cases.append(case_result)
            else:
                active_ids = {
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
                if placement.case_id in active_ids:
                    retained[placement.case_id] = case_result
                for retained_id in tuple(retained):
                    if retained_id not in active_ids:
                        del retained[retained_id]

    if not governing:
        raise RuntimeError("HA+HB combined search generated no solved traffic cases.")

    return HAHBCombinedSearchResult(
        girders=_final_envelopes(governing),
        station_moments=_final_station_moments(station_governing),
        cases=(
            tuple(all_cases)
            if retain_all_cases
            else tuple(retained[key] for key in sorted(retained))
        ),
        evaluated_case_count=evaluated,
        hb_units=units,
        hb_longitudinal_step_m=hb_longitudinal_step_m,
        hb_transverse_step_m=hb_transverse_step_m,
        ha_kel_step_m=ha_kel_step_m,
        ha_assignment_search_exhaustive=assignment_exhaustive_all,
        kel_combinations_exhaustive=kel_exhaustive_all,
        checked_inner_axle_spacings_m=HB_INNER_AXLE_SPACINGS_M,
    )


def run_ha_hb_combined_grillage_search_converged(
    project: BridgeProject,
    *,
    units: float = 45.0,
    initial_hb_longitudinal_step_m: float = 4.0,
    minimum_hb_longitudinal_step_m: float = 1.0,
    initial_hb_transverse_step_m: float = 2.0,
    minimum_hb_transverse_step_m: float = 0.5,
    initial_ha_kel_step_m: float = 4.0,
    minimum_ha_kel_step_m: float = 1.0,
    relative_tolerance: float = 0.05,
    max_refinements: int = 3,
    max_exhaustive_kel_combinations: int = 5000,
    max_exhaustive_ha_assignments: int = 500,
) -> BS5400ConvergenceResult:
    current = run_ha_hb_combined_grillage_search(
        project,
        units=units,
        hb_longitudinal_step_m=initial_hb_longitudinal_step_m,
        hb_transverse_step_m=initial_hb_transverse_step_m,
        ha_kel_step_m=initial_ha_kel_step_m,
        max_exhaustive_kel_combinations=max_exhaustive_kel_combinations,
        max_exhaustive_ha_assignments=max_exhaustive_ha_assignments,
    )
    if not current.ha_assignment_search_exhaustive:
        raise RuntimeError(
            "HA+HB convergence cannot certify a reduced HA lane-assignment search."
        )
    if not current.kel_combinations_exhaustive:
        raise RuntimeError(
            "HA+HB convergence cannot certify a reduced HA KEL-position search."
        )

    refinements: list[BS5400ConvergenceStep] = []
    for _ in range(max_refinements):
        fine_long = max(
            minimum_hb_longitudinal_step_m,
            current.hb_longitudinal_step_m / 2.0,
        )
        fine_transverse = max(
            minimum_hb_transverse_step_m,
            current.hb_transverse_step_m / 2.0,
        )
        fine_kel = max(
            minimum_ha_kel_step_m,
            current.ha_kel_step_m / 2.0,
        )
        if (
            fine_long >= current.hb_longitudinal_step_m - 1.0e-12
            and fine_transverse >= current.hb_transverse_step_m - 1.0e-12
            and fine_kel >= current.ha_kel_step_m - 1.0e-12
        ):
            break

        fine = run_ha_hb_combined_grillage_search(
            project,
            units=units,
            hb_longitudinal_step_m=fine_long,
            hb_transverse_step_m=fine_transverse,
            ha_kel_step_m=fine_kel,
            max_exhaustive_kel_combinations=max_exhaustive_kel_combinations,
            max_exhaustive_ha_assignments=max_exhaustive_ha_assignments,
        )
        if not fine.ha_assignment_search_exhaustive:
            raise RuntimeError(
                "HA+HB convergence cannot certify a reduced HA lane-assignment search."
            )
        if not fine.kel_combinations_exhaustive:
            raise RuntimeError(
                "HA+HB convergence cannot certify a reduced HA KEL-position search."
            )

        step = _compare_envelopes(
            current.girders,
            fine.girders,
            coarse_longitudinal=current.hb_longitudinal_step_m,
            fine_longitudinal=fine.hb_longitudinal_step_m,
            coarse_transverse=current.hb_transverse_step_m,
            fine_transverse=fine.hb_transverse_step_m,
        )
        refinements.append(step)
        current = fine
        if step.maximum_relative_change <= relative_tolerance:
            break

    return BS5400ConvergenceResult(
        result=current,
        refinements=tuple(refinements),
        relative_tolerance=relative_tolerance,
    )
