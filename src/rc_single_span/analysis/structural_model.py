from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Node:
    node_id: int
    x_m: float
    y_m: float
    z_m: float = 0.0


@dataclass(frozen=True)
class Material:
    material_id: int
    name: str
    elastic_modulus_kn_m2: float
    poisson_ratio: float = 0.2
    weight_density_kn_m3: float = 24.0


@dataclass(frozen=True)
class Section:
    section_id: int
    name: str
    area_m2: float
    torsion_constant_m4: float
    iy_m4: float
    iz_m4: float


@dataclass(frozen=True)
class Beam:
    member_id: int
    node_i: int
    node_j: int
    material_id: int
    section_id: int


@dataclass(frozen=True)
class Support:
    node_id: int
    uz: bool = True
    rx: bool = False
    ry: bool = False


@dataclass(frozen=True)
class UniformLoad:
    member_id: int
    magnitude_kn_m: float
    start_m: float | None = None
    end_m: float | None = None


@dataclass(frozen=True)
class PointLoad:
    member_id: int
    magnitude_kn: float
    distance_from_i_m: float


@dataclass(frozen=True)
class NodalLoad:
    node_id: int
    fz_kn: float = 0.0
    mx_knm: float = 0.0
    my_knm: float = 0.0


@dataclass(frozen=True)
class LoadCase:
    load_case_id: int
    name: str
    uniform_loads: tuple[UniformLoad, ...] = ()
    point_loads: tuple[PointLoad, ...] = ()
    nodal_loads: tuple[NodalLoad, ...] = ()


@dataclass(frozen=True)
class StructuralModel:
    name: str
    nodes: tuple[Node, ...]
    materials: tuple[Material, ...]
    sections: tuple[Section, ...]
    beams: tuple[Beam, ...]
    supports: tuple[Support, ...]
    load_cases: tuple[LoadCase, ...]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Structural model name cannot be empty.")
        for label, values in (
            ("node", [item.node_id for item in self.nodes]),
            ("material", [item.material_id for item in self.materials]),
            ("section", [item.section_id for item in self.sections]),
            ("member", [item.member_id for item in self.beams]),
            ("load case", [item.load_case_id for item in self.load_cases]),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"Duplicate {label} IDs are not allowed.")
        node_ids = {item.node_id for item in self.nodes}
        material_ids = {item.material_id for item in self.materials}
        section_ids = {item.section_id for item in self.sections}
        member_ids = {item.member_id for item in self.beams}
        for beam in self.beams:
            if beam.node_i not in node_ids or beam.node_j not in node_ids:
                raise ValueError("Beam references an unknown node.")
            if beam.material_id not in material_ids:
                raise ValueError("Beam references an unknown material.")
            if beam.section_id not in section_ids:
                raise ValueError("Beam references an unknown section.")
        for support in self.supports:
            if support.node_id not in node_ids:
                raise ValueError("Support references an unknown node.")
        for case in self.load_cases:
            for load in (*case.uniform_loads, *case.point_loads):
                if load.member_id not in member_ids:
                    raise ValueError("Member load references an unknown beam.")
            for load in case.nodal_loads:
                if load.node_id not in node_ids:
                    raise ValueError("Nodal load references an unknown node.")

    def member_length_m(self, member_id: int) -> float:
        beam = next(item for item in self.beams if item.member_id == member_id)
        nodes = {item.node_id: item for item in self.nodes}
        ni = nodes[beam.node_i]
        nj = nodes[beam.node_j]
        dx = nj.x_m - ni.x_m
        dy = nj.y_m - ni.y_m
        dz = nj.z_m - ni.z_m
        return (dx * dx + dy * dy + dz * dz) ** 0.5
