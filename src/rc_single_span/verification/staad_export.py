from __future__ import annotations

import re
from dataclasses import dataclass

from rc_single_span.analysis.structural_model import StructuralModel


@dataclass(frozen=True)
class StaadSupportRestraint:
    node_id: int
    ux: bool
    uy: bool
    uz: bool
    rx: bool
    ry: bool
    rz: bool


def _safe_name(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_]", "_", value.strip())
    if not text:
        return "ITEM"
    if text[0].isdigit():
        return f"N_{text}"
    return text[:32]


def _id_list(values: list[int]) -> str:
    if not values:
        return ""
    ordered = sorted(set(values))
    tokens: list[str] = []
    start = previous = ordered[0]
    for value in ordered[1:]:
        if value == previous + 1:
            previous = value
            continue
        if start == previous:
            tokens.append(str(start))
        elif previous == start + 1:
            tokens.extend((str(start), str(previous)))
        else:
            tokens.extend((str(start), "TO", str(previous)))
        start = previous = value
    if start == previous:
        tokens.append(str(start))
    elif previous == start + 1:
        tokens.extend((str(start), str(previous)))
    else:
        tokens.extend((str(start), "TO", str(previous)))
    return " ".join(tokens)


def _chunks(values: list[int], size: int) -> list[str]:
    if size < 1:
        raise ValueError("STAAD ID chunk size must be positive.")
    ordered = sorted(set(values))
    return [
        _id_list(ordered[start : start + size])
        for start in range(0, len(ordered), size)
    ]


def _staad_member_force_print_commands(
    member_ids: list[int],
    *,
    max_line_length: int = 100,
) -> list[str]:
    """Return lossless GLOBAL member-force print commands for STAAD.

    STAAD.Pro can split overlong LIST commands in its input echo. With large
    four-digit member IDs that split can truncate the final ID on a line, which
    silently omits member results from the .ANL evidence file. Build commands by
    character length rather than by a fixed number of IDs so every requested
    member remains inside a conservative line-length budget.
    """

    prefix = "PRINT MEMBER FORCES GLOBAL LIST"
    if max_line_length <= len(prefix) + 1:
        raise ValueError("STAAD print-command line length is too small.")

    commands: list[str] = []
    current = prefix
    for member_id in sorted(set(member_ids)):
        candidate = f"{current} {member_id}"
        if len(candidate) > max_line_length:
            if current == prefix:
                raise ValueError("A STAAD member ID cannot fit in the print command.")
            commands.append(current)
            current = f"{prefix} {member_id}"
            if len(current) > max_line_length:
                raise ValueError("A STAAD member ID cannot fit in the print command.")
        else:
            current = candidate

    if current != prefix:
        commands.append(current)
    return commands


def _support_restraints(model: StructuralModel) -> tuple[StaadSupportRestraint, ...]:
    """Map the vertical-only native support set into a stable 3D STAAD model.

    The native solver has only w, rx and ry DOFs. STAAD SPACE also carries ux,
    uy and rz rigid-body modes, so minimal in-plane stabilization is added:
    every native support on the minimum-x bearing line restrains UX, and the
    first such support also restrains UY. Those extra restraints do not alter
    the native vertical grillage DOFs and are exposed in the verification
    manifest.
    """

    if not model.supports:
        raise ValueError("STAAD verification export requires structural supports.")
    nodes = {node.node_id: node for node in model.nodes}
    support_nodes = [nodes[item.node_id] for item in model.supports]
    min_x = min(node.x_m for node in support_nodes)
    first_line = sorted(
        (
            item
            for item in model.supports
            if abs(nodes[item.node_id].x_m - min_x) <= 1.0e-9
        ),
        key=lambda item: (nodes[item.node_id].y_m, item.node_id),
    )
    if not first_line:
        raise RuntimeError("Unable to identify the minimum-x support line.")
    uy_node = first_line[0].node_id
    first_line_ids = {item.node_id for item in first_line}

    return tuple(
        StaadSupportRestraint(
            node_id=item.node_id,
            ux=item.node_id in first_line_ids,
            uy=item.node_id == uy_node,
            uz=item.uz,
            rx=item.rx,
            ry=item.ry,
            rz=False,
        )
        for item in model.supports
    )


def _support_command(item: StaadSupportRestraint) -> str:
    restrained = (item.ux, item.uy, item.uz, item.rx, item.ry, item.rz)
    if all(restrained):
        return f"{item.node_id} FIXED"
    if restrained[:3] == (True, True, True) and restrained[3:] == (
        False,
        False,
        False,
    ):
        return f"{item.node_id} PINNED"

    labels = ("FX", "FY", "FZ", "MX", "MY", "MZ")
    released = [
        label
        for label, is_restrained in zip(labels, restrained, strict=True)
        if not is_restrained
    ]
    return f"{item.node_id} FIXED BUT {' '.join(released)}"


def staad_support_restraints(
    model: StructuralModel,
) -> tuple[StaadSupportRestraint, ...]:
    return _support_restraints(model)


def export_staad_std(model: StructuralModel) -> str:
    """Export the exact common grillage to STAAD.Pro in kN-m units."""

    if not model.nodes or not model.beams or not model.sections or not model.materials:
        raise ValueError("STAAD export requires a populated structural model.")

    lines: list[str] = [
        f"STAAD SPACE {_safe_name(model.name)}",
        "START JOB INFORMATION",
        "ENGINEER NAME RC_SINGLE_SPAN_BRIDGE_ANALYSIS_ANN",
        "END JOB INFORMATION",
        "SET Z UP",
        "UNIT METER KNS",
        "JOINT COORDINATES",
    ]
    lines.extend(
        f"{node.node_id} {node.x_m:.12g} {node.y_m:.12g} {node.z_m:.12g};"
        for node in model.nodes
    )

    lines.append("MEMBER INCIDENCES")
    lines.extend(
        f"{beam.member_id} {beam.node_i} {beam.node_j};"
        for beam in model.beams
    )

    lines.append("MEMBER PROPERTY")
    for section in model.sections:
        members = [
            beam.member_id
            for beam in model.beams
            if beam.section_id == section.section_id
        ]
        if not members:
            continue
        if min(
            section.area_m2,
            section.torsion_constant_m4,
            section.iy_m4,
            section.iz_m4,
        ) <= 0.0:
            raise ValueError(
                f"Section {section.section_id} contains non-positive STAAD properties."
            )
        for ids in _chunks(members, 10):
            lines.append(
                f"{ids} PRIS AX {section.area_m2:.12g} "
                f"IX {section.torsion_constant_m4:.12g} "
                f"IY {section.iy_m4:.12g} IZ {section.iz_m4:.12g}"
            )

    lines.append("DEFINE MATERIAL START")
    for material in model.materials:
        name = _safe_name(material.name)
        lines.extend(
            (
                f"ISOTROPIC {name}",
                f"E {material.elastic_modulus_kn_m2:.12g}",
                f"POISSON {material.poisson_ratio:.12g}",
                f"DENSITY {material.weight_density_kn_m3:.12g}",
                "ALPHA 1e-05",
            )
        )
    lines.append("END DEFINE MATERIAL")

    lines.append("CONSTANTS")
    for material in model.materials:
        members = [
            beam.member_id
            for beam in model.beams
            if beam.material_id == material.material_id
        ]
        for ids in _chunks(members, 20):
            lines.append(f"MATERIAL {_safe_name(material.name)} MEMB {ids}")

    lines.append("SUPPORTS")
    lines.extend(_support_command(item) for item in _support_restraints(model))

    for case in model.load_cases:
        lines.append(
            f"LOAD {case.load_case_id} LOADTYPE None TITLE {_safe_name(case.name)}"
        )
        if case.uniform_loads or case.point_loads:
            lines.append("MEMBER LOAD")
            for load in case.uniform_loads:
                suffix = ""
                if load.start_m is not None and load.end_m is not None:
                    suffix = f" {load.start_m:.12g} {load.end_m:.12g}"
                lines.append(
                    f"{load.member_id} UNI GZ {load.magnitude_kn_m:.12g}{suffix}"
                )
            for load in case.point_loads:
                lines.append(
                    f"{load.member_id} CON GZ {load.magnitude_kn:.12g} "
                    f"{load.distance_from_i_m:.12g}"
                )
        if case.nodal_loads:
            lines.append("JOINT LOAD")
            for load in case.nodal_loads:
                terms = (
                    ("FZ", load.fz_kn),
                    ("MX", load.mx_knm),
                    ("MY", load.my_knm),
                )
                active = " ".join(
                    f"{name} {value:.12g}"
                    for name, value in terms
                    if abs(value) > 1.0e-15
                )
                if active:
                    lines.append(f"{load.node_id} {active}")

    lines.extend(("PERFORM ANALYSIS", "PRINT SUPPORT REACTION ALL"))
    member_ids = [beam.member_id for beam in model.beams]
    lines.extend(_staad_member_force_print_commands(member_ids))
    lines.extend(("PRINT JOINT DISPLACEMENTS ALL", "FINISH"))
    return "\n".join(lines) + "\n"
