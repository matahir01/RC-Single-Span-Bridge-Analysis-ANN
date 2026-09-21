from __future__ import annotations

from dataclasses import dataclass, replace
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
)
from rc_single_span.codes.bs5400.traffic import (
    HB_INNER_AXLE_SPACINGS_M,
    HALaneLoad,
    ha_lane_load_bd37_01,
    hb_vehicle_definition,
    notional_lane_layout_bd37_01,
)
from rc_single_span.core.models import BridgeProject


@dataclass(frozen=True)
class GoverningComponent:
    value: float
    case_id: int
    member_id: int | None


@dataclass(frozen=True)
class BS5400GirderGoverningEnvelope:
    girder_index: int
    y_m: float
    moment_knm: GoverningComponent
    shear_kn: GoverningComponent
    torsion_knm: GoverningComponent
    deflection_mm: GoverningComponent
    deflection_position_m: float


@dataclass(frozen=True)
class HALanePlacement:
    physical_slot: int
    factor_rank: int
    y_start_m: float
    y_end_m: float
    kel_x_m: float


@dataclass(frozen=True)
class HASearchPlacement:
    case_id: int
    lanes: tuple[HALanePlacement, ...]


@dataclass(frozen=True)
class HBSearchPlacement:
    case_id: int
    units: float
    inner_axle_spacing_m: float
    lead_x_m: float
    centre_y_m: float


@dataclass(frozen=True)
class BS5400CaseResult:
    case_id: int
    model: StructuralModel
    analysis: GrillageAnalysisResult
    girders: tuple[GirderCaseEnvelope, ...]
    description: str


@dataclass(frozen=True)
class HASearchResult:
    girders: tuple[BS5400GirderGoverningEnvelope, ...]
    cases: tuple[BS5400CaseResult, ...]
    evaluated_case_count: int
    longitudinal_step_m: float
    kel_combinations_exhaustive: bool


@dataclass(frozen=True)
class HBSearchResult:
    girders: tuple[BS5400GirderGoverningEnvelope, ...]
    cases: tuple[BS5400CaseResult, ...]
    evaluated_case_count: int
    longitudinal_step_m: float
    transverse_step_m: float
    checked_inner_axle_spacings_m: tuple[float, ...]


@dataclass(frozen=True)
class BS5400NominalTrafficSuite:
    ha: HASearchResult
    hb: HBSearchResult
    application_status: str


@dataclass(frozen=True)
class BS5400ConvergenceStep:
    coarse_longitudinal_step_m: float
    fine_longitudinal_step_m: float
    coarse_transverse_step_m: float | None
    fine_transverse_step_m: float | None
    maximum_relative_change: float
    governing_quantity: str
    girder_index: int


@dataclass(frozen=True)
class BS5400ConvergenceResult:
    result: HASearchResult | HBSearchResult
    refinements: tuple[BS5400ConvergenceStep, ...]
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


def _kel_positions(span_m: float, step_m: float) -> tuple[float, ...]:
    if step_m <= 0.0:
        raise ValueError("HA KEL search step must be positive.")
    edge = min(max(step_m / 100.0, 1.0e-4), 0.05)
    values = [edge, span_m / 2.0, span_m - edge]
    x = edge
    while x <= span_m - edge + 1.0e-9:
        values.append(round(x, 12))
        x += step_m
    return _merge_coordinates(tuple(values))


def _position_vectors(
    count: int,
    positions: tuple[float, ...],
    *,
    maximum: int,
) -> tuple[tuple[tuple[float, ...], ...], bool]:
    theoretical = len(positions) ** count
    if theoretical <= maximum:
        return tuple(product(positions, repeat=count)), True

    candidates: list[tuple[float, ...]] = []
    seen: set[tuple[float, ...]] = set()

    def add(values: tuple[float, ...]) -> None:
        if values not in seen:
            seen.add(values)
            candidates.append(values)

    for position in positions:
        add((position,) * count)
    middle = positions[len(positions) // 2]
    for index in range(count):
        for position in positions:
            trial = [middle] * count
            trial[index] = position
            add(tuple(trial))
    return tuple(candidates), False


def _ha_lane_slots(project: BridgeProject) -> tuple[tuple[int, float, float], ...]:
    geometry = project.geometry
    layout = notional_lane_layout_bd37_01(float(geometry.carriageway_width_m))
    if layout.remaining_width_m > 1.0e-12:
        raise NotImplementedError(
            "The focused common-grillage HA search currently requires carriageway width >= 5 m; "
            "the special BD 37/01 single-lane remainder loading is not silently approximated."
        )
    left = (
        float(geometry.carriageway_offset_m)
        - float(geometry.carriageway_width_m) / 2.0
    )
    return tuple(
        (
            index + 1,
            left + index * layout.lane_width_m,
            left + (index + 1) * layout.lane_width_m,
        )
        for index in range(layout.lane_count)
    )


def generate_ha_search_placements(
    project: BridgeProject,
    *,
    longitudinal_step_m: float = 1.0,
    max_exhaustive_kel_combinations: int = 5000,
) -> tuple[tuple[HASearchPlacement, ...], bool]:
    slots = _ha_lane_slots(project)
    positions = _kel_positions(float(project.geometry.span_m), longitudinal_step_m)
    placements: list[HASearchPlacement] = []
    exhaustive_all = True
    case_id = 1

    for loaded_count in range(1, len(slots) + 1):
        vectors, exhaustive = _position_vectors(
            loaded_count,
            positions,
            maximum=max_exhaustive_kel_combinations,
        )
        exhaustive_all = exhaustive_all and exhaustive
        for selected_slots in combinations(slots, loaded_count):
            for ranks in permutations(range(1, loaded_count + 1)):
                for vector in vectors:
                    lanes = tuple(
                        HALanePlacement(
                            physical_slot=slot[0],
                            factor_rank=rank,
                            y_start_m=slot[1],
                            y_end_m=slot[2],
                            kel_x_m=kel_x,
                        )
                        for slot, rank, kel_x in zip(
                            selected_slots,
                            ranks,
                            vector,
                            strict=True,
                        )
                    )
                    placements.append(HASearchPlacement(case_id, lanes))
                    case_id += 1
    return tuple(placements), exhaustive_all


def build_ha_plan_loads(
    project: BridgeProject,
    placement: HASearchPlacement,
) -> tuple[tuple[PlanAreaLoad, ...], tuple[PlanTransverseLineLoad, ...]]:
    layout = notional_lane_layout_bd37_01(float(project.geometry.carriageway_width_m))
    span = float(project.geometry.span_m)
    areas: list[PlanAreaLoad] = []
    lines: list[PlanTransverseLineLoad] = []

    for lane in placement.lanes:
        load: HALaneLoad = ha_lane_load_bd37_01(
            factor_rank=lane.factor_rank,
            loaded_length_m=span,
            lane_width_m=layout.lane_width_m,
            total_notional_lanes=layout.lane_count,
        )
        width = lane.y_end_m - lane.y_start_m
        areas.append(
            PlanAreaLoad(
                0.0,
                span,
                lane.y_start_m,
                lane.y_end_m,
                load.udl_kn_m / width,
                label=f"HA slot {lane.physical_slot} factor rank {lane.factor_rank} UDL",
            )
        )
        lines.append(
            PlanTransverseLineLoad(
                lane.kel_x_m,
                lane.y_start_m,
                lane.y_end_m,
                load.kel_kn,
                label=f"HA slot {lane.physical_slot} factor rank {lane.factor_rank} KEL",
            )
        )
    return tuple(areas), tuple(lines)


def _equilibrium_tolerance_kn(analysis: GrillageAnalysisResult) -> float:
    """Return a strict scale-aware vertical-force equilibrium tolerance.

    Sparse factorization roundoff grows with the load/reaction scale. The
    tolerance remains at least 1e-6 kN and no more permissive than 1e-8 of the
    governing vertical force scale.
    """

    scale = max(
        abs(analysis.total_applied_vertical_load_kn),
        abs(analysis.total_vertical_reaction_kn),
        1.0,
    )
    return max(1.0e-6, 1.0e-8 * scale)


def _require_vertical_equilibrium(
    analysis: GrillageAnalysisResult,
    *,
    traffic_model: str,
) -> None:
    tolerance = _equilibrium_tolerance_kn(analysis)
    if abs(analysis.vertical_equilibrium_residual_kn) > tolerance:
        raise RuntimeError(
            f"{traffic_model} grillage case failed vertical equilibrium: "
            f"residual={analysis.vertical_equilibrium_residual_kn:.12g} kN, "
            f"tolerance={tolerance:.12g} kN."
        )


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
                    "deflection": GoverningComponent(item.deflection_mm, case_id, None),
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
        existing = row["deflection"]
        assert isinstance(existing, GoverningComponent)
        if item.deflection_mm > existing.value:
            row["deflection"] = GoverningComponent(item.deflection_mm, case_id, None)
            row["deflection_x"] = item.deflection_position_m


def _final_envelopes(
    governing: list[dict[str, object]],
) -> tuple[BS5400GirderGoverningEnvelope, ...]:
    return tuple(
        BS5400GirderGoverningEnvelope(
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


def run_ha_grillage_search(
    project: BridgeProject,
    *,
    longitudinal_step_m: float = 1.0,
    max_exhaustive_kel_combinations: int = 5000,
    retain_all_cases: bool = False,
) -> HASearchResult:
    placements, exhaustive = generate_ha_search_placements(
        project,
        longitudinal_step_m=longitudinal_step_m,
        max_exhaustive_kel_combinations=max_exhaustive_kel_combinations,
    )
    if not placements:
        raise RuntimeError("HA search generated no candidate placements.")

    slots = _ha_lane_slots(project)
    x_grid = _merge_coordinates(
        (
            0.0,
            float(project.geometry.span_m),
            *(lane.kel_x_m for placement in placements for lane in placement.lanes),
        )
    )
    y_grid = _merge_coordinates(
        tuple(
            coordinate
            for _, y_start, y_end in slots
            for coordinate in (y_start, y_end)
        )
    )
    build = build_final_composite_grillage(
        project,
        stations_m=x_grid,
        additional_y_lines_m=y_grid,
    )
    prepared = prepare_vertical_grillage(build.model)

    governing: list[dict[str, object]] = []
    all_cases: list[BS5400CaseResult] = []
    retained: dict[int, BS5400CaseResult] = {}

    for placement in placements:
        areas, lines = build_ha_plan_loads(project, placement)
        case = build_plan_load_case(
            build.model,
            load_case_id=placement.case_id,
            name=f"BD 37/01 HA case {placement.case_id}",
            area_loads=areas,
            transverse_line_loads=lines,
        )
        model = replace(build.model, load_cases=(case,))
        analysis = solve_prepared_vertical_grillage(prepared, model)
        _require_vertical_equilibrium(analysis, traffic_model="HA")
        girders = native_traffic_girder_envelope(model, analysis)
        _update_governing(governing, placement.case_id, girders)
        case_result = BS5400CaseResult(
            placement.case_id,
            model,
            analysis,
            girders,
            description="BD 37/01 HA UDL + transverse KEL",
        )

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
            for case_id in tuple(retained):
                if case_id not in active_ids:
                    del retained[case_id]

    return HASearchResult(
        girders=_final_envelopes(governing),
        cases=(
            tuple(all_cases)
            if retain_all_cases
            else tuple(retained[key] for key in sorted(retained))
        ),
        evaluated_case_count=len(placements),
        longitudinal_step_m=longitudinal_step_m,
        kel_combinations_exhaustive=exhaustive,
    )


def _hb_lead_positions(
    span_m: float,
    axle_offsets_m: tuple[float, ...],
    step_m: float,
) -> tuple[float, ...]:
    if step_m <= 0.0:
        raise ValueError("HB longitudinal search step must be positive.")
    start = -max(axle_offsets_m)
    values = [start, 0.0, span_m]
    values.extend(-offset for offset in axle_offsets_m)
    values.extend(span_m - offset for offset in axle_offsets_m)
    x = start
    while x <= span_m + 1.0e-9:
        values.append(round(x, 12))
        x += step_m
    return _merge_coordinates(
        tuple(min(max(value, start), span_m) for value in values)
    )


def _hb_centres(project: BridgeProject, step_m: float) -> tuple[float, ...]:
    if step_m <= 0.0:
        raise ValueError("HB transverse search step must be positive.")
    geometry = project.geometry
    half_vehicle = 1.75
    left = (
        float(geometry.carriageway_offset_m)
        - float(geometry.carriageway_width_m) / 2.0
        + half_vehicle
    )
    right = (
        float(geometry.carriageway_offset_m)
        + float(geometry.carriageway_width_m) / 2.0
        - half_vehicle
    )
    if right < left - 1.0e-9:
        raise ValueError("Carriageway is too narrow for the 3.5 m HB vehicle.")
    if abs(right - left) <= 1.0e-9:
        return (0.5 * (left + right),)

    values = [left, 0.5 * (left + right), right]
    y = left
    while y <= right + 1.0e-9:
        values.append(round(y, 12))
        y += step_m
    return _merge_coordinates(
        tuple(min(max(value, left), right) for value in values)
    )


def build_hb_plan_loads(
    project: BridgeProject,
    placement: HBSearchPlacement,
) -> tuple[PlanPointLoad, ...]:
    vehicle = hb_vehicle_definition(
        units=placement.units,
        inner_axle_spacing_m=placement.inner_axle_spacing_m,
    )
    span = float(project.geometry.span_m)
    points: list[PlanPointLoad] = []
    for axle_number, offset in enumerate(vehicle.axle_offsets_m, start=1):
        x_m = placement.lead_x_m + offset
        if not -1.0e-9 <= x_m <= span + 1.0e-9:
            continue
        x_m = min(max(x_m, 0.0), span)
        for wheel_number, y_offset in enumerate(vehicle.wheel_y_offsets_m, start=1):
            points.append(
                PlanPointLoad(
                    x_m,
                    placement.centre_y_m + y_offset,
                    vehicle.wheel_load_kn,
                    label=f"HB axle {axle_number} wheel {wheel_number}",
                )
            )
    return tuple(points)


def run_hb_grillage_search(
    project: BridgeProject,
    *,
    units: float = 45.0,
    longitudinal_step_m: float = 1.0,
    transverse_step_m: float = 0.5,
    retain_all_cases: bool = False,
) -> HBSearchResult:
    centres = _hb_centres(project, transverse_step_m)
    governing: list[dict[str, object]] = []
    all_cases: list[BS5400CaseResult] = []
    retained: dict[int, BS5400CaseResult] = {}
    case_id = 1
    evaluated = 0

    for spacing in HB_INNER_AXLE_SPACINGS_M:
        vehicle = hb_vehicle_definition(
            units=units,
            inner_axle_spacing_m=spacing,
        )
        leads = _hb_lead_positions(
            float(project.geometry.span_m),
            vehicle.axle_offsets_m,
            longitudinal_step_m,
        )
        placements = tuple(
            HBSearchPlacement(case_id + index, units, spacing, lead, centre)
            for index, (lead, centre) in enumerate(product(leads, centres))
        )
        if not placements:
            continue

        span = float(project.geometry.span_m)
        x_grid_values = [0.0, span]
        y_grid_values: list[float] = []
        for placement in placements:
            for offset in vehicle.axle_offsets_m:
                x_m = placement.lead_x_m + offset
                if -1.0e-9 <= x_m <= span + 1.0e-9:
                    x_grid_values.append(min(max(x_m, 0.0), span))
            y_grid_values.extend(
                placement.centre_y_m + offset
                for offset in vehicle.wheel_y_offsets_m
            )

        build = build_final_composite_grillage(
            project,
            stations_m=_merge_coordinates(tuple(x_grid_values)),
            additional_y_lines_m=_merge_coordinates(tuple(y_grid_values)),
        )
        prepared = prepare_vertical_grillage(build.model)

        for placement in placements:
            points = build_hb_plan_loads(project, placement)
            case = build_plan_load_case(
                build.model,
                load_case_id=placement.case_id,
                name=(
                    f"BD 37/01 HB {units:g} unit spacing "
                    f"{spacing:g} m case {placement.case_id}"
                ),
                point_loads=points,
            )
            model = replace(build.model, load_cases=(case,))
            analysis = solve_prepared_vertical_grillage(prepared, model)
            _require_vertical_equilibrium(analysis, traffic_model="HB")
            girders = native_traffic_girder_envelope(model, analysis)
            _update_governing(governing, placement.case_id, girders)
            case_result = BS5400CaseResult(
                placement.case_id,
                model,
                analysis,
                girders,
                description=(
                    f"BD 37/01 HB {units:g} unit, inner spacing {spacing:g} m, "
                    f"centre y={placement.centre_y_m:.6g} m"
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

        case_id += len(placements)

    return HBSearchResult(
        girders=_final_envelopes(governing),
        cases=(
            tuple(all_cases)
            if retain_all_cases
            else tuple(retained[key] for key in sorted(retained))
        ),
        evaluated_case_count=evaluated,
        longitudinal_step_m=longitudinal_step_m,
        transverse_step_m=transverse_step_m,
        checked_inner_axle_spacings_m=HB_INNER_AXLE_SPACINGS_M,
    )


def run_bs5400_nominal_traffic_suite(
    project: BridgeProject,
    *,
    hb_units: float = 45.0,
    ha_longitudinal_step_m: float = 1.0,
    hb_longitudinal_step_m: float = 1.0,
    hb_transverse_step_m: float = 0.5,
) -> BS5400NominalTrafficSuite:
    return BS5400NominalTrafficSuite(
        ha=run_ha_grillage_search(
            project,
            longitudinal_step_m=ha_longitudinal_step_m,
        ),
        hb=run_hb_grillage_search(
            project,
            units=hb_units,
            longitudinal_step_m=hb_longitudinal_step_m,
            transverse_step_m=hb_transverse_step_m,
        ),
        application_status=(
            "Nominal HA-alone and HB vehicle searches use the common physical grillage. "
            "Code-specific HA+HB coexistence/application under BD 37/01 6.4.2 is intentionally "
            "reserved for the next load-application/combination batch rather than approximated."
        ),
    )


def _compare_envelopes(
    coarse: tuple[BS5400GirderGoverningEnvelope, ...],
    fine: tuple[BS5400GirderGoverningEnvelope, ...],
    *,
    coarse_longitudinal: float,
    fine_longitudinal: float,
    coarse_transverse: float | None,
    fine_transverse: float | None,
) -> BS5400ConvergenceStep:
    worst = (-1.0, "", 0)
    for c, f in zip(coarse, fine, strict=True):
        for name, cv, fv in (
            ("moment", c.moment_knm.value, f.moment_knm.value),
            ("shear", c.shear_kn.value, f.shear_kn.value),
            ("torsion", c.torsion_knm.value, f.torsion_knm.value),
            ("deflection", c.deflection_mm.value, f.deflection_mm.value),
        ):
            relative = abs(fv - cv) / max(abs(fv), 1.0e-9)
            if relative > worst[0]:
                worst = (relative, name, f.girder_index)
    return BS5400ConvergenceStep(
        coarse_longitudinal,
        fine_longitudinal,
        coarse_transverse,
        fine_transverse,
        worst[0],
        worst[1],
        worst[2],
    )


def run_ha_grillage_search_converged(
    project: BridgeProject,
    *,
    initial_longitudinal_step_m: float = 2.0,
    minimum_longitudinal_step_m: float = 0.5,
    relative_tolerance: float = 0.05,
    max_refinements: int = 3,
    max_exhaustive_kel_combinations: int = 5000,
) -> BS5400ConvergenceResult:
    current = run_ha_grillage_search(
        project,
        longitudinal_step_m=initial_longitudinal_step_m,
        max_exhaustive_kel_combinations=max_exhaustive_kel_combinations,
    )
    if not current.kel_combinations_exhaustive:
        raise RuntimeError("HA convergence cannot certify a reduced KEL search.")
    refinements: list[BS5400ConvergenceStep] = []

    for _ in range(max_refinements):
        fine_step = max(minimum_longitudinal_step_m, current.longitudinal_step_m / 2.0)
        if fine_step >= current.longitudinal_step_m - 1.0e-12:
            break
        fine = run_ha_grillage_search(
            project,
            longitudinal_step_m=fine_step,
            max_exhaustive_kel_combinations=max_exhaustive_kel_combinations,
        )
        if not fine.kel_combinations_exhaustive:
            raise RuntimeError("HA convergence cannot certify a reduced KEL search.")
        step = _compare_envelopes(
            current.girders,
            fine.girders,
            coarse_longitudinal=current.longitudinal_step_m,
            fine_longitudinal=fine.longitudinal_step_m,
            coarse_transverse=None,
            fine_transverse=None,
        )
        refinements.append(step)
        current = fine
        if step.maximum_relative_change <= relative_tolerance:
            break

    return BS5400ConvergenceResult(current, tuple(refinements), relative_tolerance)


def run_hb_grillage_search_converged(
    project: BridgeProject,
    *,
    units: float = 45.0,
    initial_longitudinal_step_m: float = 2.0,
    minimum_longitudinal_step_m: float = 0.5,
    initial_transverse_step_m: float = 1.0,
    minimum_transverse_step_m: float = 0.25,
    relative_tolerance: float = 0.05,
    max_refinements: int = 3,
) -> BS5400ConvergenceResult:
    current = run_hb_grillage_search(
        project,
        units=units,
        longitudinal_step_m=initial_longitudinal_step_m,
        transverse_step_m=initial_transverse_step_m,
    )
    refinements: list[BS5400ConvergenceStep] = []

    for _ in range(max_refinements):
        fine_long = max(
            minimum_longitudinal_step_m,
            current.longitudinal_step_m / 2.0,
        )
        fine_transverse = max(
            minimum_transverse_step_m,
            current.transverse_step_m / 2.0,
        )
        if (
            fine_long >= current.longitudinal_step_m - 1.0e-12
            and fine_transverse >= current.transverse_step_m - 1.0e-12
        ):
            break
        fine = run_hb_grillage_search(
            project,
            units=units,
            longitudinal_step_m=fine_long,
            transverse_step_m=fine_transverse,
        )
        step = _compare_envelopes(
            current.girders,
            fine.girders,
            coarse_longitudinal=current.longitudinal_step_m,
            fine_longitudinal=fine.longitudinal_step_m,
            coarse_transverse=current.transverse_step_m,
            fine_transverse=fine.transverse_step_m,
        )
        refinements.append(step)
        current = fine
        if step.maximum_relative_change <= relative_tolerance:
            break

    return BS5400ConvergenceResult(current, tuple(refinements), relative_tolerance)
