from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from rc_single_span.analysis.grillage_solver import (
    GrillageAnalysisResult,
    MemberEndResult,
    NodeResult,
)
from rc_single_span.analysis.structural_model import Beam, LoadCase, StructuralModel


@dataclass(frozen=True)
class _BeamElement:
    beam: Beam
    length_m: float
    stiffness: np.ndarray
    load: np.ndarray
    dofs: tuple[int, int, int, int]


def _node_dofs(index: int) -> tuple[int, int]:
    start = 2 * index
    return start, start + 1


def _load_case(model: StructuralModel, load_case_id: int | None) -> LoadCase:
    if load_case_id is None:
        if len(model.load_cases) != 1:
            raise ValueError("Specify load_case_id when the beam model has multiple cases.")
        return model.load_cases[0]
    return next(item for item in model.load_cases if item.load_case_id == load_case_id)


def _beam_length(model: StructuralModel, beam: Beam) -> float:
    nodes = {item.node_id: item for item in model.nodes}
    ni, nj = nodes[beam.node_i], nodes[beam.node_j]
    if abs(ni.y_m - nj.y_m) > 1.0e-9 or abs(ni.z_m - nj.z_m) > 1.0e-9:
        raise ValueError("Construction beam FE verifier requires longitudinal X-axis members.")
    length = nj.x_m - ni.x_m
    if length <= 1.0e-12:
        raise ValueError("Construction beam members must run in positive X.")
    return length


def _stiffness(length_m: float, ei_kn_m2: float) -> np.ndarray:
    length = length_m
    factor = ei_kn_m2 / length**3
    return factor * np.array(
        [
            [12.0, 6.0 * length, -12.0, 6.0 * length],
            [6.0 * length, 4.0 * length**2, -6.0 * length, 2.0 * length**2],
            [-12.0, -6.0 * length, 12.0, -6.0 * length],
            [6.0 * length, 2.0 * length**2, -6.0 * length, 4.0 * length**2],
        ]
    )


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


def _udl_equivalent(
    length_m: float,
    start_m: float,
    end_m: float,
    magnitude_kn_m: float,
) -> np.ndarray:
    if start_m < 0.0 or end_m > length_m + 1.0e-9 or end_m <= start_m:
        raise ValueError("Beam FE UDL bounds are invalid.")
    gauss_x, gauss_w = np.polynomial.legendre.leggauss(6)
    midpoint = 0.5 * (start_m + end_m)
    half = 0.5 * (end_m - start_m)
    integrated = np.zeros(4)
    for coordinate, weight in zip(gauss_x, gauss_w, strict=True):
        x_m = midpoint + half * float(coordinate)
        integrated += float(weight) * _shape(length_m, x_m)
    return half * magnitude_kn_m * integrated


def _point_equivalent(
    length_m: float,
    x_m: float,
    magnitude_kn: float,
) -> np.ndarray:
    if not 0.0 <= x_m <= length_m:
        raise ValueError("Beam FE point load lies outside its member.")
    return magnitude_kn * _shape(length_m, x_m)


def _element(
    model: StructuralModel,
    beam: Beam,
    case: LoadCase,
    node_index: dict[int, int],
) -> _BeamElement:
    length = _beam_length(model, beam)
    material = next(
        item for item in model.materials if item.material_id == beam.material_id
    )
    section = next(
        item for item in model.sections if item.section_id == beam.section_id
    )
    load = np.zeros(4)
    for item in case.uniform_loads:
        if item.member_id != beam.member_id:
            continue
        start = 0.0 if item.start_m is None else item.start_m
        end = length if item.end_m is None else item.end_m
        load += _udl_equivalent(
            length,
            start,
            end,
            item.magnitude_kn_m,
        )
    for item in case.point_loads:
        if item.member_id == beam.member_id:
            load += _point_equivalent(
                length,
                item.distance_from_i_m,
                item.magnitude_kn,
            )

    i_w, i_theta = _node_dofs(node_index[beam.node_i])
    j_w, j_theta = _node_dofs(node_index[beam.node_j])
    return _BeamElement(
        beam=beam,
        length_m=length,
        stiffness=_stiffness(
            length,
            material.elastic_modulus_kn_m2 * section.iy_m4,
        ),
        load=load,
        dofs=(i_w, i_theta, j_w, j_theta),
    )


def solve_construction_beam_fe(
    model: StructuralModel,
    *,
    load_case_id: int | None = None,
) -> GrillageAnalysisResult:
    """Solve a straight longitudinal construction beam using w/theta DOFs only.

    The returned object uses the common GrillageAnalysisResult container so the
    exact same STAAD package/comparison tooling can be reused. Torsion is zero by
    construction. Stored bending signs match the native grillage convention.
    """

    case = _load_case(model, load_case_id)
    if not model.nodes or not model.beams:
        raise ValueError("Construction beam FE model cannot be empty.")

    ordered_nodes = tuple(sorted(model.nodes, key=lambda item: item.x_m))
    if tuple(item.node_id for item in ordered_nodes) != tuple(
        item.node_id for item in model.nodes
    ):
        raise ValueError("Construction beam FE nodes must be ordered in positive X.")

    node_index = {node.node_id: index for index, node in enumerate(model.nodes)}
    dof_count = 2 * len(model.nodes)
    stiffness = np.zeros((dof_count, dof_count))
    loads = np.zeros(dof_count)

    elements = tuple(
        _element(model, beam, case, node_index)
        for beam in model.beams
    )
    for element in elements:
        dofs = np.array(element.dofs, dtype=int)
        stiffness[np.ix_(dofs, dofs)] += element.stiffness
        loads[dofs] += element.load

    for item in case.nodal_loads:
        w, theta = _node_dofs(node_index[item.node_id])
        loads[w] += item.fz_kn
        # For an X-axis member the native stored/global bending component is MY,
        # while the local beam rotation theta equals -global RY.
        loads[theta] -= item.my_knm
        if abs(item.mx_knm) > 1.0e-12:
            raise ValueError(
                "Construction beam FE verifier does not accept torsional nodal moments."
            )

    constrained: set[int] = set()
    for support in model.supports:
        w, theta = _node_dofs(node_index[support.node_id])
        if support.uz:
            constrained.add(w)
        if support.ry:
            constrained.add(theta)

    if not constrained:
        raise ValueError("Construction beam FE model has no bending restraints.")
    free = tuple(index for index in range(dof_count) if index not in constrained)
    reduced = stiffness[np.ix_(free, free)]
    if np.linalg.matrix_rank(reduced) < reduced.shape[0]:
        raise ValueError("Construction beam FE stiffness matrix is singular.")

    displacement = np.zeros(dof_count)
    displacement[list(free)] = np.linalg.solve(reduced, loads[list(free)])
    residual = stiffness @ displacement - loads

    node_results: list[NodeResult] = []
    for index, node in enumerate(model.nodes):
        w, theta = _node_dofs(index)
        node_results.append(
            NodeResult(
                node_id=node.node_id,
                vertical_displacement_m=float(displacement[w]),
                rotation_x_rad=0.0,
                rotation_y_rad=float(-displacement[theta]),
                vertical_reaction_kn=(
                    float(residual[w]) if w in constrained else 0.0
                ),
            )
        )

    member_results: list[MemberEndResult] = []
    for element in elements:
        dofs = np.array(element.dofs, dtype=int)
        end = element.stiffness @ displacement[dofs] - element.load
        member_results.append(
            MemberEndResult(
                member_id=element.beam.member_id,
                node_i=element.beam.node_i,
                node_j=element.beam.node_j,
                i_vertical_force_kn=float(end[0]),
                i_vertical_bending_moment_knm=float(-end[1]),
                i_torsion_knm=0.0,
                j_vertical_force_kn=float(end[2]),
                j_vertical_bending_moment_knm=float(-end[3]),
                j_torsion_knm=0.0,
            )
        )

    total_load = float(sum(loads[0::2]))
    total_reaction = float(sum(item.vertical_reaction_kn for item in node_results))
    return GrillageAnalysisResult(
        load_case_id=case.load_case_id,
        load_case_name=case.name,
        nodes=tuple(node_results),
        members=tuple(member_results),
        total_applied_vertical_load_kn=total_load,
        total_vertical_reaction_kn=total_reaction,
        vertical_equilibrium_residual_kn=total_load + total_reaction,
    )
