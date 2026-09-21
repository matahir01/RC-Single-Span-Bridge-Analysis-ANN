from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from rc_single_span.analysis.structural_model import Beam, LoadCase, StructuralModel


@dataclass(frozen=True)
class NodeResult:
    node_id: int
    vertical_displacement_m: float
    rotation_x_rad: float
    rotation_y_rad: float
    vertical_reaction_kn: float


@dataclass(frozen=True)
class MemberEndResult:
    member_id: int
    node_i: int
    node_j: int
    i_vertical_force_kn: float
    i_vertical_bending_moment_knm: float
    i_torsion_knm: float
    j_vertical_force_kn: float
    j_vertical_bending_moment_knm: float
    j_torsion_knm: float


@dataclass(frozen=True)
class GrillageAnalysisResult:
    load_case_id: int
    load_case_name: str
    nodes: tuple[NodeResult, ...]
    members: tuple[MemberEndResult, ...]
    total_applied_vertical_load_kn: float
    total_vertical_reaction_kn: float
    vertical_equilibrium_residual_kn: float


@dataclass(frozen=True)
class _Element:
    beam: Beam
    length_m: float
    transformation: np.ndarray
    local_stiffness: np.ndarray
    local_load: np.ndarray
    dofs: tuple[int, ...]


def _node_dofs(index: int) -> tuple[int, int, int]:
    start = 3 * index
    return start, start + 1, start + 2


def _load_case(model: StructuralModel, load_case_id: int | None) -> LoadCase:
    if load_case_id is None:
        if len(model.load_cases) != 1:
            raise ValueError("Specify load_case_id when the model has multiple load cases.")
        return model.load_cases[0]
    return next(case for case in model.load_cases if case.load_case_id == load_case_id)


def _basis(model: StructuralModel, beam: Beam) -> tuple[float, float, float]:
    nodes = {node.node_id: node for node in model.nodes}
    ni, nj = nodes[beam.node_i], nodes[beam.node_j]
    dx, dy, dz = nj.x_m - ni.x_m, nj.y_m - ni.y_m, nj.z_m - ni.z_m
    if abs(dz) > 1.0e-9:
        raise ValueError("Vertical grillage members must be horizontal.")
    length = math.hypot(dx, dy)
    if length <= 1.0e-12:
        raise ValueError("Zero-length grillage member.")
    return dx / length, dy / length, length


def _transformation(cx: float, cy: float) -> np.ndarray:
    node = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, cy, -cx],
            [0.0, cx, cy],
        ]
    )
    matrix = np.zeros((6, 6))
    matrix[:3, :3] = node
    matrix[3:, 3:] = node
    return matrix


def _local_stiffness(length_m: float, ei_kn_m2: float, gj_kn_m2: float) -> np.ndarray:
    length = length_m
    matrix = np.zeros((6, 6))
    bending = ei_kn_m2 / length**3
    k = bending * np.array(
        [
            [12.0, 6.0 * length, -12.0, 6.0 * length],
            [6.0 * length, 4.0 * length**2, -6.0 * length, 2.0 * length**2],
            [-12.0, -6.0 * length, 12.0, -6.0 * length],
            [6.0 * length, 2.0 * length**2, -6.0 * length, 4.0 * length**2],
        ]
    )
    bending_dofs = (0, 1, 3, 4)
    for i, row in enumerate(bending_dofs):
        for j, col in enumerate(bending_dofs):
            matrix[row, col] = k[i, j]
    torsion = gj_kn_m2 / length
    matrix[2, 2] = torsion
    matrix[2, 5] = -torsion
    matrix[5, 2] = -torsion
    matrix[5, 5] = torsion
    return matrix


def _shape(length_m: float, x_m: float) -> np.ndarray:
    xi = x_m / length_m
    return np.array(
        [
            1.0 - 3.0 * xi**2 + 2.0 * xi**3,
            length_m * (xi - 2.0 * xi**2 + xi**3),
            3.0 * xi**2 - 2.0 * xi**3,
            length_m * (-xi**2 + xi**3),
        ]
    )


def _point_load(length_m: float, x_m: float, magnitude_kn: float) -> np.ndarray:
    if not 0.0 <= x_m <= length_m:
        raise ValueError("Member point load lies outside its member.")
    vector = np.zeros(6)
    vector[[0, 1, 3, 4]] = magnitude_kn * _shape(length_m, x_m)
    return vector


def _udl(
    length_m: float,
    start_m: float,
    end_m: float,
    magnitude_kn_m: float,
) -> np.ndarray:
    if start_m < 0.0 or end_m > length_m or end_m <= start_m:
        raise ValueError("Member UDL bounds are invalid.")
    gauss_x, gauss_w = np.polynomial.legendre.leggauss(4)
    midpoint = 0.5 * (start_m + end_m)
    half = 0.5 * (end_m - start_m)
    integrated = np.zeros(4)
    for coordinate, weight in zip(gauss_x, gauss_w, strict=True):
        x_m = midpoint + half * float(coordinate)
        integrated += float(weight) * _shape(length_m, x_m)
    vector = np.zeros(6)
    vector[[0, 1, 3, 4]] = half * magnitude_kn_m * integrated
    return vector


def _element(
    model: StructuralModel,
    beam: Beam,
    case: LoadCase,
    node_index: dict[int, int],
) -> _Element:
    cx, cy, length = _basis(model, beam)
    material = next(item for item in model.materials if item.material_id == beam.material_id)
    section = next(item for item in model.sections if item.section_id == beam.section_id)
    e_kn_m2 = material.elastic_modulus_kn_m2
    g_kn_m2 = e_kn_m2 / (2.0 * (1.0 + material.poisson_ratio))
    local_load = np.zeros(6)
    for load in case.uniform_loads:
        if load.member_id != beam.member_id:
            continue
        start = 0.0 if load.start_m is None else load.start_m
        end = length if load.end_m is None else load.end_m
        local_load += _udl(length, start, end, load.magnitude_kn_m)
    for load in case.point_loads:
        if load.member_id == beam.member_id:
            local_load += _point_load(
                length,
                load.distance_from_i_m,
                load.magnitude_kn,
            )
    transform = _transformation(cx, cy)
    i_dofs = _node_dofs(node_index[beam.node_i])
    j_dofs = _node_dofs(node_index[beam.node_j])
    return _Element(
        beam=beam,
        length_m=length,
        transformation=transform,
        local_stiffness=_local_stiffness(
            length,
            e_kn_m2 * section.iy_m4,
            g_kn_m2 * section.torsion_constant_m4,
        ),
        local_load=local_load,
        dofs=(*i_dofs, *j_dofs),
    )


def solve_vertical_grillage(
    model: StructuralModel,
    *,
    load_case_id: int | None = None,
) -> GrillageAnalysisResult:
    case = _load_case(model, load_case_id)
    node_index = {node.node_id: index for index, node in enumerate(model.nodes)}
    dof_count = 3 * len(model.nodes)
    stiffness = np.zeros((dof_count, dof_count))
    loads = np.zeros(dof_count)

    elements = tuple(_element(model, beam, case, node_index) for beam in model.beams)
    for element in elements:
        dofs = np.array(element.dofs, dtype=int)
        global_k = (
            element.transformation.T
            @ element.local_stiffness
            @ element.transformation
        )
        global_f = element.transformation.T @ element.local_load
        stiffness[np.ix_(dofs, dofs)] += global_k
        loads[dofs] += global_f

    for load in case.nodal_loads:
        w, rx, ry = _node_dofs(node_index[load.node_id])
        loads[w] += load.fz_kn
        loads[rx] += load.mx_knm
        loads[ry] += load.my_knm

    constrained: set[int] = set()
    for support in model.supports:
        w, rx, ry = _node_dofs(node_index[support.node_id])
        if support.uz:
            constrained.add(w)
        if support.rx:
            constrained.add(rx)
        if support.ry:
            constrained.add(ry)

    if not constrained:
        raise ValueError("Structural model has no active restraints.")
    free = tuple(index for index in range(dof_count) if index not in constrained)
    reduced = stiffness[np.ix_(free, free)]
    if np.linalg.matrix_rank(reduced) < reduced.shape[0]:
        raise ValueError("Grillage stiffness matrix is singular.")

    displacement = np.zeros(dof_count)
    displacement[list(free)] = np.linalg.solve(reduced, loads[list(free)])
    residual = stiffness @ displacement - loads

    node_results = []
    for index, node in enumerate(model.nodes):
        w, rx, ry = _node_dofs(index)
        node_results.append(
            NodeResult(
                node.node_id,
                float(displacement[w]),
                float(displacement[rx]),
                float(displacement[ry]),
                float(residual[w]) if w in constrained else 0.0,
            )
        )

    member_results = []
    for element in elements:
        dofs = np.array(element.dofs, dtype=int)
        local_d = element.transformation @ displacement[dofs]
        end = element.local_stiffness @ local_d - element.local_load
        member_results.append(
            MemberEndResult(
                element.beam.member_id,
                element.beam.node_i,
                element.beam.node_j,
                float(end[0]),
                float(-end[1]),
                float(end[2]),
                float(end[3]),
                float(-end[4]),
                float(end[5]),
            )
        )

    total_load = float(sum(loads[0::3]))
    total_reaction = float(sum(item.vertical_reaction_kn for item in node_results))
    return GrillageAnalysisResult(
        case.load_case_id,
        case.name,
        tuple(node_results),
        tuple(member_results),
        total_load,
        total_reaction,
        total_load + total_reaction,
    )
