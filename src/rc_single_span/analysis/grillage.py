from __future__ import annotations

from dataclasses import dataclass

from rc_single_span.analysis.sections import (
    final_composite_girder_properties,
    girder_y_positions_m,
    station_tributary_widths_m,
    transverse_deck_strip_properties,
)
from rc_single_span.analysis.structural_model import (
    Beam,
    LoadCase,
    Material,
    Node,
    Section,
    StructuralModel,
    Support,
)
from rc_single_span.core.models import BridgeProject


@dataclass(frozen=True)
class GrillageBuild:
    model: StructuralModel
    stations_m: tuple[float, ...]
    girder_y_m: tuple[float, ...]


def _stations(span_m: float, divisions: int) -> tuple[float, ...]:
    if divisions < 2:
        raise ValueError("Grillage requires at least two longitudinal divisions.")
    return tuple(span_m * index / divisions for index in range(divisions + 1))


def build_final_composite_grillage(
    project: BridgeProject,
    *,
    longitudinal_divisions: int = 12,
    elastic_modulus_mpa: float | None = None,
    load_case: LoadCase | None = None,
) -> GrillageBuild:
    geometry = project.geometry
    e_mpa = (
        float(elastic_modulus_mpa)
        if elastic_modulus_mpa is not None
        else project.materials.elastic_modulus_mpa
    )
    if e_mpa is None or e_mpa <= 0.0:
        raise ValueError(
            "Final grillage analysis requires an explicit elastic modulus; "
            "code profiles may derive it before calling the common solver."
        )

    stations = _stations(float(geometry.span_m), longitudinal_divisions)
    y_positions = girder_y_positions_m(geometry)
    node_ids: dict[tuple[int, int], int] = {}
    nodes = []
    next_node = 1
    for x_index, x_m in enumerate(stations):
        for y_index, y_m in enumerate(y_positions):
            node_ids[(x_index, y_index)] = next_node
            nodes.append(Node(next_node, x_m, y_m))
            next_node += 1

    sections = []
    longitudinal_section_ids = []
    for girder_index in range(1, int(geometry.girder_count) + 1):
        props = final_composite_girder_properties(
            geometry,
            girder_index=girder_index,
        )
        section_id = len(sections) + 1
        sections.append(
            Section(
                section_id,
                f"Composite girder {girder_index}",
                props.area_m2,
                props.torsion_constant_m4,
                props.iy_m4,
                props.iz_m4,
            )
        )
        longitudinal_section_ids.append(section_id)

    transverse_section_ids = []
    for index, strip_width in enumerate(station_tributary_widths_m(stations), start=1):
        props = transverse_deck_strip_properties(
            geometry,
            strip_width_m=strip_width,
        )
        section_id = len(sections) + 1
        sections.append(
            Section(
                section_id,
                f"Transverse deck strip {index}",
                props.area_m2,
                props.torsion_constant_m4,
                props.iy_m4,
                props.iz_m4,
            )
        )
        transverse_section_ids.append(section_id)

    beams = []
    member_id = 1
    for y_index in range(len(y_positions)):
        for x_index in range(len(stations) - 1):
            beams.append(
                Beam(
                    member_id,
                    node_ids[(x_index, y_index)],
                    node_ids[(x_index + 1, y_index)],
                    1,
                    longitudinal_section_ids[y_index],
                )
            )
            member_id += 1

    for x_index in range(len(stations)):
        for y_index in range(len(y_positions) - 1):
            beams.append(
                Beam(
                    member_id,
                    node_ids[(x_index, y_index)],
                    node_ids[(x_index, y_index + 1)],
                    1,
                    transverse_section_ids[x_index],
                )
            )
            member_id += 1

    supports = []
    for y_index in range(len(y_positions)):
        supports.append(Support(node_ids[(0, y_index)], uz=True))
        supports.append(Support(node_ids[(len(stations) - 1, y_index)], uz=True))

    model = StructuralModel(
        name=f"{project.name} final composite grillage",
        nodes=tuple(nodes),
        materials=(
            Material(
                1,
                "Concrete",
                e_mpa * 1000.0,
                poisson_ratio=0.2,
                weight_density_kn_m3=float(project.materials.concrete_density_kn_m3),
            ),
        ),
        sections=tuple(sections),
        beams=tuple(beams),
        supports=tuple(supports),
        load_cases=(load_case or LoadCase(1, "EMPTY"),),
    )
    return GrillageBuild(model, stations, y_positions)
