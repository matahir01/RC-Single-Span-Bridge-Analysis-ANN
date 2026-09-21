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
    transverse_y_m: tuple[float, ...]


def _merge_coordinates(
    values: tuple[float, ...],
    *,
    tolerance: float = 1.0e-9,
) -> tuple[float, ...]:
    merged: list[float] = []
    for value in sorted(float(item) for item in values):
        if not merged or abs(value - merged[-1]) > tolerance:
            merged.append(value)
    return tuple(merged)


def _stations(
    span_m: float,
    divisions: int,
    explicit: tuple[float, ...] | None,
) -> tuple[float, ...]:
    if explicit is None:
        if divisions < 2:
            raise ValueError("Grillage requires at least two longitudinal divisions.")
        return tuple(span_m * index / divisions for index in range(divisions + 1))

    if not explicit:
        raise ValueError("Explicit grillage stations cannot be empty.")
    stations = _merge_coordinates((0.0, *explicit, span_m))
    if stations[0] < -1.0e-9 or stations[-1] > span_m + 1.0e-9:
        raise ValueError("A grillage station lies outside the physical span.")
    if abs(stations[0]) > 1.0e-9 or abs(stations[-1] - span_m) > 1.0e-9:
        raise ValueError("Explicit grillage stations must cover both supports.")
    return stations


def _transverse_lines(
    project: BridgeProject,
    additional_y_lines_m: tuple[float, ...],
) -> tuple[float, ...]:
    geometry = project.geometry
    half_deck = float(geometry.deck_width_m) / 2.0
    if any(
        value < -half_deck - 1.0e-9 or value > half_deck + 1.0e-9
        for value in additional_y_lines_m
    ):
        raise ValueError("A transverse grillage line lies outside the physical deck.")
    return _merge_coordinates(
        (
            -half_deck,
            *girder_y_positions_m(geometry),
            *additional_y_lines_m,
            half_deck,
        )
    )


def _coordinate_index(values: tuple[float, ...], value: float) -> int:
    for index, coordinate in enumerate(values):
        if abs(coordinate - value) <= 1.0e-9:
            return index
    raise ValueError("Required grillage coordinate was not generated.")


def build_final_composite_grillage(
    project: BridgeProject,
    *,
    longitudinal_divisions: int = 12,
    stations_m: tuple[float, ...] | None = None,
    additional_y_lines_m: tuple[float, ...] = (),
    elastic_modulus_mpa: float | None = None,
    load_case: LoadCase | None = None,
) -> GrillageBuild:
    """Build the common final-state orthogonal grillage.

    Longitudinal members exist only on physical girder lines. Transverse deck
    strips extend to the physical deck edges and may be subdivided at traffic
    lane/wheel coordinates without changing their strip stiffness.
    """

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

    x_stations = _stations(
        float(geometry.span_m),
        longitudinal_divisions,
        stations_m,
    )
    girder_y = girder_y_positions_m(geometry)
    y_lines = _transverse_lines(project, additional_y_lines_m)
    girder_y_indices = tuple(_coordinate_index(y_lines, value) for value in girder_y)

    node_ids: dict[tuple[int, int], int] = {}
    nodes: list[Node] = []
    next_node = 1
    for x_index, x_m in enumerate(x_stations):
        for y_index, y_m in enumerate(y_lines):
            node_ids[(x_index, y_index)] = next_node
            nodes.append(Node(next_node, x_m, y_m))
            next_node += 1

    sections: list[Section] = []
    longitudinal_section_ids: list[int] = []
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

    transverse_section_ids: list[int] = []
    for index, strip_width in enumerate(
        station_tributary_widths_m(x_stations),
        start=1,
    ):
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

    beams: list[Beam] = []
    member_id = 1
    for girder_index, y_index in enumerate(girder_y_indices):
        for x_index in range(len(x_stations) - 1):
            beams.append(
                Beam(
                    member_id,
                    node_ids[(x_index, y_index)],
                    node_ids[(x_index + 1, y_index)],
                    1,
                    longitudinal_section_ids[girder_index],
                )
            )
            member_id += 1

    for x_index in range(len(x_stations)):
        for y_index in range(len(y_lines) - 1):
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

    supports: list[Support] = []
    for y_index in girder_y_indices:
        supports.append(Support(node_ids[(0, y_index)], uz=True))
        supports.append(
            Support(node_ids[(len(x_stations) - 1, y_index)], uz=True)
        )

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
    return GrillageBuild(model, x_stations, girder_y, y_lines)
