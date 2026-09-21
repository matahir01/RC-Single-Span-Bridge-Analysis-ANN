from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.sparse import csc_matrix, lil_matrix
from scipy.sparse.linalg import splu

from rc_single_span.analysis.grillage_solver import (
    GrillageAnalysisResult,
    MemberEndResult,
    NodeResult,
    _basis,
    _load_case,
    _local_stiffness,
    _node_dofs,
    _point_load,
    _transformation,
    _udl,
)
from rc_single_span.analysis.structural_model import Beam, StructuralModel


@dataclass(frozen=True)
class _PreparedElement:
    beam: Beam
    length_m: float
    transformation: np.ndarray
    local_stiffness: np.ndarray
    dofs: tuple[int, ...]


@dataclass(frozen=True)
class PreparedVerticalGrillage:
    structure_signature: tuple[object, ...]
    node_index_by_id: dict[int, int]
    elements: tuple[_PreparedElement, ...]
    stiffness: csc_matrix
    constrained_dofs: frozenset[int]
    free_dofs: tuple[int, ...]
    reduced_factorization: object


def vertical_grillage_structure_signature(model: StructuralModel) -> tuple[object, ...]:
    return (
        model.nodes,
        model.materials,
        model.sections,
        model.beams,
        model.supports,
    )


def prepare_vertical_grillage(model: StructuralModel) -> PreparedVerticalGrillage:
    """Assemble and sparse-factor the load-independent grillage stiffness once."""

    node_index = {node.node_id: index for index, node in enumerate(model.nodes)}
    dof_count = 3 * len(model.nodes)
    stiffness = lil_matrix((dof_count, dof_count), dtype=float)
    elements: list[_PreparedElement] = []

    for beam in model.beams:
        cx, cy, length = _basis(model, beam)
        material = next(
            item for item in model.materials if item.material_id == beam.material_id
        )
        section = next(
            item for item in model.sections if item.section_id == beam.section_id
        )
        e_kn_m2 = material.elastic_modulus_kn_m2
        g_kn_m2 = e_kn_m2 / (2.0 * (1.0 + material.poisson_ratio))
        transform = _transformation(cx, cy)
        local_k = _local_stiffness(
            length,
            e_kn_m2 * section.iy_m4,
            g_kn_m2 * section.torsion_constant_m4,
        )
        i_dofs = _node_dofs(node_index[beam.node_i])
        j_dofs = _node_dofs(node_index[beam.node_j])
        element = _PreparedElement(
            beam=beam,
            length_m=length,
            transformation=transform,
            local_stiffness=local_k,
            dofs=(*i_dofs, *j_dofs),
        )
        elements.append(element)
        global_k = transform.T @ local_k @ transform
        for local_row, global_row in enumerate(element.dofs):
            for local_col, global_col in enumerate(element.dofs):
                value = float(global_k[local_row, local_col])
                if value != 0.0:
                    stiffness[global_row, global_col] += value

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
    stiffness_csc = stiffness.tocsc()
    reduced = stiffness_csc[list(free), :][:, list(free)].tocsc()
    try:
        factorization = splu(reduced)
    except RuntimeError as exc:
        raise ValueError("Grillage stiffness matrix is singular.") from exc

    return PreparedVerticalGrillage(
        structure_signature=vertical_grillage_structure_signature(model),
        node_index_by_id=node_index,
        elements=tuple(elements),
        stiffness=stiffness_csc,
        constrained_dofs=frozenset(constrained),
        free_dofs=free,
        reduced_factorization=factorization,
    )


def solve_prepared_vertical_grillage(
    prepared: PreparedVerticalGrillage,
    model: StructuralModel,
    *,
    load_case_id: int | None = None,
) -> GrillageAnalysisResult:
    if vertical_grillage_structure_signature(model) != prepared.structure_signature:
        raise ValueError("Prepared grillage structure does not match the supplied model.")

    case = _load_case(model, load_case_id)
    loads = np.zeros(prepared.stiffness.shape[0], dtype=float)
    local_loads: list[np.ndarray] = []

    for element in prepared.elements:
        local = np.zeros(6)
        for load in case.uniform_loads:
            if load.member_id != element.beam.member_id:
                continue
            start = 0.0 if load.start_m is None else load.start_m
            end = element.length_m if load.end_m is None else load.end_m
            local += _udl(
                element.length_m,
                start,
                end,
                load.magnitude_kn_m,
            )
        for load in case.point_loads:
            if load.member_id == element.beam.member_id:
                local += _point_load(
                    element.length_m,
                    load.distance_from_i_m,
                    load.magnitude_kn,
                )
        local_loads.append(local)
        dofs = np.array(element.dofs, dtype=int)
        loads[dofs] += element.transformation.T @ local

    for load in case.nodal_loads:
        w, rx, ry = _node_dofs(prepared.node_index_by_id[load.node_id])
        loads[w] += load.fz_kn
        loads[rx] += load.mx_knm
        loads[ry] += load.my_knm

    displacement = np.zeros(prepared.stiffness.shape[0], dtype=float)
    free = list(prepared.free_dofs)
    displacement[free] = prepared.reduced_factorization.solve(loads[free])
    residual = np.asarray(prepared.stiffness @ displacement).reshape(-1) - loads

    node_results: list[NodeResult] = []
    for index, node in enumerate(model.nodes):
        w, rx, ry = _node_dofs(index)
        node_results.append(
            NodeResult(
                node_id=node.node_id,
                vertical_displacement_m=float(displacement[w]),
                rotation_x_rad=float(displacement[rx]),
                rotation_y_rad=float(displacement[ry]),
                vertical_reaction_kn=(
                    float(residual[w])
                    if w in prepared.constrained_dofs
                    else 0.0
                ),
            )
        )

    member_results: list[MemberEndResult] = []
    for element, local in zip(prepared.elements, local_loads, strict=True):
        dofs = np.array(element.dofs, dtype=int)
        local_displacement = element.transformation @ displacement[dofs]
        end = element.local_stiffness @ local_displacement - local
        member_results.append(
            MemberEndResult(
                member_id=element.beam.member_id,
                node_i=element.beam.node_i,
                node_j=element.beam.node_j,
                i_vertical_force_kn=float(end[0]),
                i_vertical_bending_moment_knm=float(-end[1]),
                i_torsion_knm=float(end[2]),
                j_vertical_force_kn=float(end[3]),
                j_vertical_bending_moment_knm=float(-end[4]),
                j_torsion_knm=float(end[5]),
            )
        )

    total_load = float(sum(loads[0::3]))
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
