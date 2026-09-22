from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from rc_single_span.analysis.grillage_solver import GrillageAnalysisResult
from rc_single_span.analysis.structural_model import Beam, StructuralModel


@dataclass(frozen=True)
class GirderCaseEnvelope:
    girder_index: int
    y_m: float
    moment_knm: float
    shear_kn: float
    torsion_knm: float
    deflection_mm: float
    deflection_position_m: float
    governing_moment_member_id: int
    governing_shear_member_id: int
    governing_torsion_member_id: int


@dataclass(frozen=True)
class GirderStationMoment:
    girder_index: int
    y_m: float
    x_m: float
    moment_knm: float
    member_id: int


def _longitudinal_groups(
    model: StructuralModel,
    *,
    tolerance: float = 1.0e-9,
) -> tuple[tuple[float, tuple[Beam, ...]], ...]:
    nodes = {node.node_id: node for node in model.nodes}
    groups: dict[float, list[Beam]] = {}
    for beam in model.beams:
        ni, nj = nodes[beam.node_i], nodes[beam.node_j]
        dx, dy = nj.x_m - ni.x_m, nj.y_m - ni.y_m
        if abs(dy) <= tolerance and abs(dx) > tolerance:
            y = 0.5 * (ni.y_m + nj.y_m)
            groups.setdefault(y, []).append(beam)
        elif abs(dx) <= tolerance and abs(dy) > tolerance:
            continue
        else:
            raise ValueError("Traffic envelope requires an orthogonal grillage.")
    return tuple(
        (
            y,
            tuple(
                sorted(
                    beams,
                    key=lambda beam: min(
                        nodes[beam.node_i].x_m,
                        nodes[beam.node_j].x_m,
                    ),
                )
            ),
        )
        for y, beams in sorted(groups.items())
    )


def _member_deflection_candidates_mm(
    model: StructuralModel,
    analysis: GrillageAnalysisResult,
    beams: tuple[Beam, ...],
) -> tuple[tuple[float, float], ...]:
    nodes = {node.node_id: node for node in model.nodes}
    results = {node.node_id: node for node in analysis.nodes}
    candidates: list[tuple[float, float]] = []

    for beam in beams:
        ni, nj = nodes[beam.node_i], nodes[beam.node_j]
        dx = nj.x_m - ni.x_m
        length = abs(dx)
        if length <= 1.0e-12:
            continue
        cx = dx / length
        ri, rj = results[beam.node_i], results[beam.node_j]
        wi, wj = ri.vertical_displacement_m, rj.vertical_displacement_m
        slope_i = -cx * ri.rotation_y_rad
        slope_j = -cx * rj.rotation_y_rad
        candidates.extend(
            (
                (abs(wi) * 1000.0, ni.x_m),
                (abs(wj) * 1000.0, nj.x_m),
            )
        )

        coefficient_a = (
            3.0 * (wj - wi) / length**2
            - (2.0 * slope_i + slope_j) / length
        )
        coefficient_b = (
            2.0 * (wi - wj) / length**3
            + (slope_i + slope_j) / length**2
        )
        qa = 3.0 * coefficient_b
        qb = 2.0 * coefficient_a
        qc = slope_i
        roots: list[float] = []
        if abs(qa) <= 1.0e-15:
            if abs(qb) > 1.0e-15:
                roots.append(-qc / qb)
        else:
            discriminant = qb**2 - 4.0 * qa * qc
            if discriminant >= 0.0:
                term = sqrt(max(discriminant, 0.0))
                roots.extend(
                    (
                        (-qb - term) / (2.0 * qa),
                        (-qb + term) / (2.0 * qa),
                    )
                )
        for local_x in roots:
            if not 1.0e-10 < local_x < length - 1.0e-10:
                continue
            displacement = (
                wi
                + slope_i * local_x
                + coefficient_a * local_x**2
                + coefficient_b * local_x**3
            )
            candidates.append(
                (
                    abs(displacement) * 1000.0,
                    ni.x_m + cx * local_x,
                )
            )

    if not candidates:
        raise RuntimeError("No longitudinal deflection candidates were found.")
    return tuple(candidates)


def native_traffic_girder_station_moments(
    model: StructuralModel,
    analysis: GrillageAnalysisResult,
) -> tuple[tuple[GirderStationMoment, ...], ...]:
    """Recover absolute longitudinal-girder bending moment at every grillage station.

    Interior stations have member-end results from both adjacent longitudinal
    members. The larger absolute value is retained to avoid losing a local
    station maximum because of member-end sign convention or numerical
    round-off. This is the station-wise quantity needed by reinforcement
    zoning/curtailment rather than the single global girder envelope.
    """

    result_by_member = {item.member_id: item for item in analysis.members}
    nodes = {node.node_id: node for node in model.nodes}
    all_girders: list[tuple[GirderStationMoment, ...]] = []

    for girder_index, (y_m, beams) in enumerate(_longitudinal_groups(model), start=1):
        station_candidates: dict[float, list[tuple[float, int]]] = {}
        for beam in beams:
            result = result_by_member[beam.member_id]
            ni, nj = nodes[beam.node_i], nodes[beam.node_j]
            station_candidates.setdefault(float(ni.x_m), []).append(
                (abs(result.i_vertical_bending_moment_knm), beam.member_id)
            )
            station_candidates.setdefault(float(nj.x_m), []).append(
                (abs(result.j_vertical_bending_moment_knm), beam.member_id)
            )

        all_girders.append(
            tuple(
                GirderStationMoment(
                    girder_index=girder_index,
                    y_m=y_m,
                    x_m=x_m,
                    moment_knm=value,
                    member_id=member_id,
                )
                for x_m, (value, member_id) in (
                    (x, max(items, key=lambda item: item[0]))
                    for x, items in sorted(station_candidates.items())
                )
            )
        )

    return tuple(all_girders)


def native_traffic_girder_envelope(
    model: StructuralModel,
    analysis: GrillageAnalysisResult,
) -> tuple[GirderCaseEnvelope, ...]:
    result_by_member = {item.member_id: item for item in analysis.members}
    envelopes: list[GirderCaseEnvelope] = []

    for girder_index, (y_m, beams) in enumerate(_longitudinal_groups(model), start=1):
        moments: list[tuple[float, int]] = []
        shears: list[tuple[float, int]] = []
        torsions: list[tuple[float, int]] = []
        for beam in beams:
            result = result_by_member[beam.member_id]
            moments.extend(
                (
                    (abs(result.i_vertical_bending_moment_knm), beam.member_id),
                    (abs(result.j_vertical_bending_moment_knm), beam.member_id),
                )
            )
            shears.extend(
                (
                    (abs(result.i_vertical_force_kn), beam.member_id),
                    (abs(result.j_vertical_force_kn), beam.member_id),
                )
            )
            torsions.extend(
                (
                    (abs(result.i_torsion_knm), beam.member_id),
                    (abs(result.j_torsion_knm), beam.member_id),
                )
            )

        moment, moment_member = max(moments)
        shear, shear_member = max(shears)
        torsion, torsion_member = max(torsions)
        deflection, deflection_x = max(
            _member_deflection_candidates_mm(model, analysis, beams),
            key=lambda item: item[0],
        )
        envelopes.append(
            GirderCaseEnvelope(
                girder_index=girder_index,
                y_m=y_m,
                moment_knm=moment,
                shear_kn=shear,
                torsion_knm=torsion,
                deflection_mm=deflection,
                deflection_position_m=deflection_x,
                governing_moment_member_id=moment_member,
                governing_shear_member_id=shear_member,
                governing_torsion_member_id=torsion_member,
            )
        )
    return tuple(envelopes)



def girder_vertical_displacement_mm(
    model: StructuralModel,
    analysis: GrillageAnalysisResult,
    *,
    girder_index: int,
    x_m: float,
) -> float:
    """Return downward-positive traffic displacement at one girder station.

    Longitudinal member deflection is recovered with the same cubic Hermite
    interpolation used by the native traffic envelope.
    """

    groups = _longitudinal_groups(model)
    if not 1 <= girder_index <= len(groups):
        raise IndexError("girder_index is outside the grillage.")
    nodes = {node.node_id: node for node in model.nodes}
    results = {node.node_id: node for node in analysis.nodes}
    _, beams = groups[girder_index - 1]

    for beam in beams:
        ni, nj = nodes[beam.node_i], nodes[beam.node_j]
        x1, x2 = ni.x_m, nj.x_m
        left, right = sorted((x1, x2))
        if not left - 1.0e-10 <= x_m <= right + 1.0e-10:
            continue

        dx = x2 - x1
        length = abs(dx)
        if length <= 1.0e-12:
            continue
        cx = dx / length
        local_x = (x_m - x1) / cx
        local_x = min(max(local_x, 0.0), length)

        ri, rj = results[beam.node_i], results[beam.node_j]
        wi, wj = ri.vertical_displacement_m, rj.vertical_displacement_m
        slope_i = -cx * ri.rotation_y_rad
        slope_j = -cx * rj.rotation_y_rad
        coefficient_a = (
            3.0 * (wj - wi) / length**2
            - (2.0 * slope_i + slope_j) / length
        )
        coefficient_b = (
            2.0 * (wi - wj) / length**3
            + (slope_i + slope_j) / length**2
        )
        displacement_m = (
            wi
            + slope_i * local_x
            + coefficient_a * local_x**2
            + coefficient_b * local_x**3
        )
        return -displacement_m * 1000.0

    raise ValueError("x_m does not lie on the requested longitudinal girder.")
