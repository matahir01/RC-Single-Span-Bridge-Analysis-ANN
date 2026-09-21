from __future__ import annotations

from dataclasses import dataclass
from math import hypot

from rc_single_span.analysis.grillage_solver import GrillageAnalysisResult
from rc_single_span.analysis.structural_model import StructuralModel


@dataclass(frozen=True)
class GlobalMemberEndForce:
    member_id: int
    end: str
    fz_kn: float
    mx_knm: float
    my_knm: float


def _member_direction(model: StructuralModel, member_id: int) -> tuple[float, float]:
    beam = next(
        (item for item in model.beams if item.member_id == member_id),
        None,
    )
    if beam is None:
        raise KeyError(f"Unknown member {member_id}.")
    nodes = {node.node_id: node for node in model.nodes}
    ni, nj = nodes[beam.node_i], nodes[beam.node_j]
    dx = nj.x_m - ni.x_m
    dy = nj.y_m - ni.y_m
    length = hypot(dx, dy)
    if length <= 1.0e-12:
        raise ValueError("Zero-length grillage member.")
    if abs(nj.z_m - ni.z_m) > 1.0e-9:
        raise ValueError("Native grillage member is not horizontal.")
    return dx / length, dy / length


def _to_global(
    *,
    member_id: int,
    end: str,
    cx: float,
    cy: float,
    vertical_force_kn: float,
    stored_vertical_bending_knm: float,
    torsion_knm: float,
) -> GlobalMemberEndForce:
    """Transform the native stored member-end components to global axes.

    The native solver stores vertical bending as the negative of its internal
    local bending end-force component, while torsion keeps the local sign.
    With the solver rotation transform, force duality gives:

        Mx = cx*T - cy*Mb
        My = cx*Mb + cy*T

    where Mb is the stored vertical-bending value. Vertical force is already
    global Fz.
    """

    if end not in {"i", "j"}:
        raise ValueError("Member end must be 'i' or 'j'.")
    return GlobalMemberEndForce(
        member_id=member_id,
        end=end,
        fz_kn=vertical_force_kn,
        mx_knm=cx * torsion_knm - cy * stored_vertical_bending_knm,
        my_knm=cx * stored_vertical_bending_knm + cy * torsion_knm,
    )


def native_global_member_end_forces(
    model: StructuralModel,
    analysis: GrillageAnalysisResult,
) -> tuple[GlobalMemberEndForce, ...]:
    """Return native member-end FZ/MX/MY in the STAAD global basis."""

    model_member_ids = {item.member_id for item in model.beams}
    analysis_member_ids = {item.member_id for item in analysis.members}
    if model_member_ids != analysis_member_ids:
        raise ValueError("Analysis member set does not match the exported structural model.")

    rows: list[GlobalMemberEndForce] = []
    for item in analysis.members:
        cx, cy = _member_direction(model, item.member_id)
        rows.append(
            _to_global(
                member_id=item.member_id,
                end="i",
                cx=cx,
                cy=cy,
                vertical_force_kn=item.i_vertical_force_kn,
                stored_vertical_bending_knm=item.i_vertical_bending_moment_knm,
                torsion_knm=item.i_torsion_knm,
            )
        )
        rows.append(
            _to_global(
                member_id=item.member_id,
                end="j",
                cx=cx,
                cy=cy,
                vertical_force_kn=item.j_vertical_force_kn,
                stored_vertical_bending_knm=item.j_vertical_bending_moment_knm,
                torsion_knm=item.j_torsion_knm,
            )
        )
    return tuple(rows)
