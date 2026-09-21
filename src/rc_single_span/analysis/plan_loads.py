from __future__ import annotations

from dataclasses import dataclass

from rc_single_span.analysis.structural_model import (
    LoadCase,
    NodalLoad,
    PointLoad,
    StructuralModel,
)


@dataclass(frozen=True)
class PlanPointLoad:
    x_m: float
    y_m: float
    magnitude_kn: float
    label: str = "point load"

    def __post_init__(self) -> None:
        if self.magnitude_kn < 0.0:
            raise ValueError("Plan point-load magnitude cannot be negative.")
        if not self.label.strip():
            raise ValueError("Plan point-load label cannot be empty.")


@dataclass(frozen=True)
class PlanAreaLoad:
    x_start_m: float
    x_end_m: float
    y_start_m: float
    y_end_m: float
    pressure_kn_m2: float
    label: str = "area load"

    def __post_init__(self) -> None:
        if self.x_end_m <= self.x_start_m or self.y_end_m <= self.y_start_m:
            raise ValueError("Plan area-load bounds must define positive area.")
        if self.pressure_kn_m2 < 0.0:
            raise ValueError("Plan area-load pressure cannot be negative.")
        if not self.label.strip():
            raise ValueError("Plan area-load label cannot be empty.")


@dataclass(frozen=True)
class PlanTransverseLineLoad:
    x_m: float
    y_start_m: float
    y_end_m: float
    total_load_kn: float
    label: str = "transverse line load"

    def __post_init__(self) -> None:
        if self.y_end_m <= self.y_start_m:
            raise ValueError("Transverse line-load width must be positive.")
        if self.total_load_kn < 0.0:
            raise ValueError("Transverse line-load magnitude cannot be negative.")
        if not self.label.strip():
            raise ValueError("Transverse line-load label cannot be empty.")


def _coordinates(model: StructuralModel) -> tuple[tuple[float, ...], tuple[float, ...]]:
    return (
        tuple(sorted({node.x_m for node in model.nodes})),
        tuple(sorted({node.y_m for node in model.nodes})),
    )


def _coordinate_index(values: tuple[float, ...], value: float) -> int:
    for index, coordinate in enumerate(values):
        if abs(coordinate - value) <= 1.0e-9:
            return index
    raise ValueError(f"Load coordinate {value:.12g} m is absent from the fixed grillage grid.")


def _node_lookup(model: StructuralModel) -> dict[tuple[float, float], int]:
    return {(node.x_m, node.y_m): node.node_id for node in model.nodes}


def _transverse_beam_lookup(
    model: StructuralModel,
) -> dict[tuple[float, float, float], int]:
    nodes = {node.node_id: node for node in model.nodes}
    lookup: dict[tuple[float, float, float], int] = {}
    for beam in model.beams:
        ni, nj = nodes[beam.node_i], nodes[beam.node_j]
        if abs(ni.x_m - nj.x_m) <= 1.0e-9 and abs(ni.y_m - nj.y_m) > 1.0e-9:
            y1, y2 = sorted((ni.y_m, nj.y_m))
            lookup[(ni.x_m, y1, y2)] = beam.member_id
    return lookup


def build_plan_load_case(
    model: StructuralModel,
    *,
    load_case_id: int,
    name: str,
    point_loads: tuple[PlanPointLoad, ...] = (),
    area_loads: tuple[PlanAreaLoad, ...] = (),
    transverse_line_loads: tuple[PlanTransverseLineLoad, ...] = (),
) -> LoadCase:
    """Map physical plan loads onto an existing fixed grillage topology.

    Area pressure is lumped consistently as q*A/4 to each rectangular cell
    corner. Point loads at exact nodes remain nodal; otherwise they act on the
    corresponding transverse member. A transverse knife-edge line is distributed
    by tributary segment width so its total force is conserved exactly.
    """

    if load_case_id <= 0:
        raise ValueError("load_case_id must be positive.")
    if not name.strip():
        raise ValueError("Load-case name cannot be empty.")

    x_values, y_values = _coordinates(model)
    node_by_xy = _node_lookup(model)
    transverse_member = _transverse_beam_lookup(model)
    nodal_force: dict[int, float] = {}
    member_points: list[PointLoad] = []

    def add_nodal(node_id: int, downward_kn: float) -> None:
        nodal_force[node_id] = nodal_force.get(node_id, 0.0) - downward_kn

    for point in point_loads:
        x_index = _coordinate_index(x_values, point.x_m)
        x_m = x_values[x_index]
        exact_y = next(
            (value for value in y_values if abs(value - point.y_m) <= 1.0e-9),
            None,
        )
        if exact_y is not None:
            add_nodal(node_by_xy[(x_m, exact_y)], point.magnitude_kn)
            continue
        segment = next(
            (
                (y_values[index], y_values[index + 1])
                for index in range(len(y_values) - 1)
                if y_values[index] < point.y_m < y_values[index + 1]
            ),
            None,
        )
        if segment is None:
            raise ValueError("Plan point load lies outside the transverse grillage.")
        y1, y2 = segment
        member_id = transverse_member[(x_m, y1, y2)]
        member_points.append(
            PointLoad(
                member_id=member_id,
                magnitude_kn=-point.magnitude_kn,
                distance_from_i_m=point.y_m - y1,
            )
        )

    for patch in area_loads:
        x_start = _coordinate_index(x_values, patch.x_start_m)
        x_end = _coordinate_index(x_values, patch.x_end_m)
        y_start = _coordinate_index(y_values, patch.y_start_m)
        y_end = _coordinate_index(y_values, patch.y_end_m)
        if x_end <= x_start or y_end <= y_start:
            raise ValueError("Area-load bounds do not define grillage cells.")
        for xi in range(x_start, x_end):
            dx = x_values[xi + 1] - x_values[xi]
            for yi in range(y_start, y_end):
                dy = y_values[yi + 1] - y_values[yi]
                corner = patch.pressure_kn_m2 * dx * dy / 4.0
                for xy in (
                    (x_values[xi], y_values[yi]),
                    (x_values[xi + 1], y_values[yi]),
                    (x_values[xi], y_values[yi + 1]),
                    (x_values[xi + 1], y_values[yi + 1]),
                ):
                    add_nodal(node_by_xy[xy], corner)

    for line in transverse_line_loads:
        x_index = _coordinate_index(x_values, line.x_m)
        y_start = _coordinate_index(y_values, line.y_start_m)
        y_end = _coordinate_index(y_values, line.y_end_m)
        if y_end <= y_start:
            raise ValueError("Transverse line load does not cover grillage segments.")
        total_width = line.y_end_m - line.y_start_m
        x_m = x_values[x_index]
        for yi in range(y_start, y_end):
            width = y_values[yi + 1] - y_values[yi]
            segment_force = line.total_load_kn * width / total_width
            add_nodal(node_by_xy[(x_m, y_values[yi])], segment_force / 2.0)
            add_nodal(node_by_xy[(x_m, y_values[yi + 1])], segment_force / 2.0)

    nodal_loads = tuple(
        NodalLoad(node_id=node_id, fz_kn=force)
        for node_id, force in sorted(nodal_force.items())
        if abs(force) > 1.0e-12
    )
    return LoadCase(
        load_case_id=load_case_id,
        name=name,
        point_loads=tuple(member_points),
        nodal_loads=nodal_loads,
    )
