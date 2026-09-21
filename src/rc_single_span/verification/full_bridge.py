from __future__ import annotations

from dataclasses import dataclass, replace

from rc_single_span.analysis.grillage import build_final_composite_grillage
from rc_single_span.analysis.grillage_solver import (
    GrillageAnalysisResult,
    solve_vertical_grillage,
)
from rc_single_span.analysis.permanent import (
    PermanentLoadSegment,
    automatic_permanent_loads,
)
from rc_single_span.analysis.sections import (
    SectionProperties,
    deck_construction_girder_properties,
    final_composite_girder_properties,
    girder_y_positions_m,
    precast_girder_properties,
)
from rc_single_span.analysis.structural_model import (
    Beam,
    LoadCase,
    Material,
    Node,
    Section,
    StructuralModel,
    Support,
    UniformLoad,
)
from rc_single_span.core.models import BridgeProject, PermanentActionStage
from rc_single_span.verification.package import (
    StaadVerificationPackage,
    build_staad_verification_package,
)

_STAGES = (
    PermanentActionStage.PRECAST_GIRDER,
    PermanentActionStage.DECK_CONSTRUCTION,
    PermanentActionStage.SUPERIMPOSED,
)
_LOAD_CASE_IDS = {
    PermanentActionStage.PRECAST_GIRDER: 101,
    PermanentActionStage.DECK_CONSTRUCTION: 102,
    PermanentActionStage.SUPERIMPOSED: 103,
}


@dataclass(frozen=True)
class FullBridgeStageVerification:
    stage: PermanentActionStage
    model: StructuralModel
    analysis: GrillageAnalysisResult
    staad_package: StaadVerificationPackage
    longitudinal_member_count: int
    transverse_member_count: int
    transverse_system_active: bool
    structural_system_basis: str

    @property
    def passes_equilibrium_check(self) -> bool:
        scale = max(
            abs(self.analysis.total_applied_vertical_load_kn),
            abs(self.analysis.total_vertical_reaction_kn),
            1.0,
        )
        return abs(self.analysis.vertical_equilibrium_residual_kn) <= max(
            1.0e-7,
            scale * 1.0e-9,
        )


@dataclass(frozen=True)
class FullBridgeVerificationSuite:
    stages: tuple[FullBridgeStageVerification, ...]

    @property
    def passes_internal_checks(self) -> bool:
        return all(item.passes_equilibrium_check for item in self.stages)

    def stage(
        self,
        stage: PermanentActionStage,
    ) -> FullBridgeStageVerification:
        return next(item for item in self.stages if item.stage is stage)


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


def _stage_stations(
    project: BridgeProject,
    *,
    stage: PermanentActionStage,
    longitudinal_divisions: int,
) -> tuple[float, ...]:
    if not 2 <= longitudinal_divisions <= 64:
        raise ValueError("Full-bridge longitudinal divisions must lie between 2 and 64.")
    span = float(project.geometry.span_m)
    regular = tuple(
        span * index / longitudinal_divisions for index in range(longitudinal_divisions + 1)
    )
    boundaries = tuple(
        coordinate
        for segment in automatic_permanent_loads(project)
        if segment.stage is stage
        for coordinate in (segment.x_start_m, segment.x_end_m)
    )
    return _merge_coordinates((0.0, span, *regular, *boundaries))


def _section_for_stage(
    project: BridgeProject,
    *,
    stage: PermanentActionStage,
    girder_index: int,
) -> SectionProperties:
    if stage is PermanentActionStage.PRECAST_GIRDER:
        return precast_girder_properties(project.geometry)
    if stage is PermanentActionStage.DECK_CONSTRUCTION:
        return deck_construction_girder_properties(
            project.geometry,
            girder_index=girder_index,
        )
    return final_composite_girder_properties(
        project.geometry,
        girder_index=girder_index,
    )


def _material(project: BridgeProject) -> Material:
    elastic_modulus_mpa = project.materials.elastic_modulus_mpa
    if elastic_modulus_mpa is None or elastic_modulus_mpa <= 0.0:
        raise ValueError("Full-bridge STAAD verification requires explicit elastic_modulus_mpa.")
    return Material(
        1,
        "Concrete",
        float(elastic_modulus_mpa) * 1000.0,
        poisson_ratio=0.2,
        weight_density_kn_m3=float(project.materials.concrete_density_kn_m3),
    )


def _stage_segments(
    project: BridgeProject,
    stage: PermanentActionStage,
) -> tuple[PermanentLoadSegment, ...]:
    return tuple(item for item in automatic_permanent_loads(project) if item.stage is stage)


def _longitudinal_members_by_girder(
    model: StructuralModel,
    girder_y_m: tuple[float, ...],
) -> tuple[tuple[Beam, ...], ...]:
    nodes = {item.node_id: item for item in model.nodes}
    by_girder: list[tuple[Beam, ...]] = []
    for y_m in girder_y_m:
        members = tuple(
            sorted(
                (
                    beam
                    for beam in model.beams
                    if abs(nodes[beam.node_i].y_m - y_m) <= 1.0e-9
                    and abs(nodes[beam.node_j].y_m - y_m) <= 1.0e-9
                    and abs(nodes[beam.node_i].x_m - nodes[beam.node_j].x_m) > 1.0e-9
                ),
                key=lambda beam: min(
                    nodes[beam.node_i].x_m,
                    nodes[beam.node_j].x_m,
                ),
            )
        )
        if not members:
            raise RuntimeError(f"No longitudinal members were found on girder line y={y_m} m.")
        by_girder.append(members)
    return tuple(by_girder)


def _stage_load_case(
    model: StructuralModel,
    *,
    stage: PermanentActionStage,
    girder_y_m: tuple[float, ...],
    segments: tuple[PermanentLoadSegment, ...],
) -> LoadCase:
    nodes = {item.node_id: item for item in model.nodes}
    members_by_girder = _longitudinal_members_by_girder(model, girder_y_m)
    loads: list[UniformLoad] = []

    for segment in segments:
        members = members_by_girder[segment.girder_index - 1]
        for member in members:
            node_i = nodes[member.node_i]
            node_j = nodes[member.node_j]
            member_start = min(node_i.x_m, node_j.x_m)
            member_end = max(node_i.x_m, node_j.x_m)
            overlap_start = max(member_start, segment.x_start_m)
            overlap_end = min(member_end, segment.x_end_m)
            if overlap_end <= overlap_start + 1.0e-12:
                continue
            member_length = member_end - member_start
            local_start = overlap_start - member_start
            local_end = overlap_end - member_start
            if local_start <= 1.0e-10 and abs(local_end - member_length) <= 1.0e-10:
                loads.append(
                    UniformLoad(
                        member_id=member.member_id,
                        magnitude_kn_m=-segment.magnitude_kn_m,
                    )
                )
            else:
                loads.append(
                    UniformLoad(
                        member_id=member.member_id,
                        magnitude_kn_m=-segment.magnitude_kn_m,
                        start_m=local_start,
                        end_m=local_end,
                    )
                )

    return LoadCase(
        _LOAD_CASE_IDS[stage],
        f"Full bridge {stage.value}",
        uniform_loads=tuple(loads),
    )


def _unhardened_stage_model(
    project: BridgeProject,
    *,
    stage: PermanentActionStage,
    stations_m: tuple[float, ...],
) -> StructuralModel:
    if stage not in {
        PermanentActionStage.PRECAST_GIRDER,
        PermanentActionStage.DECK_CONSTRUCTION,
    }:
        raise ValueError("The unhardened-stage builder only accepts stages 1 and 2.")

    girder_y = girder_y_positions_m(project.geometry)
    node_ids: dict[tuple[int, int], int] = {}
    nodes: list[Node] = []
    next_node = 1
    for x_index, x_m in enumerate(stations_m):
        for girder_index, y_m in enumerate(girder_y):
            node_ids[(x_index, girder_index)] = next_node
            nodes.append(Node(next_node, x_m, y_m))
            next_node += 1

    sections: list[Section] = []
    for girder_index in range(1, len(girder_y) + 1):
        properties = _section_for_stage(
            project,
            stage=stage,
            girder_index=girder_index,
        )
        sections.append(
            Section(
                girder_index,
                f"{stage.value} girder {girder_index}",
                properties.area_m2,
                properties.torsion_constant_m4,
                properties.iy_m4,
                properties.iz_m4,
            )
        )

    beams: list[Beam] = []
    member_id = 1
    for girder_index in range(len(girder_y)):
        for x_index in range(len(stations_m) - 1):
            beams.append(
                Beam(
                    member_id,
                    node_ids[(x_index, girder_index)],
                    node_ids[(x_index + 1, girder_index)],
                    1,
                    girder_index + 1,
                )
            )
            member_id += 1

    supports: list[Support] = []
    last_x_index = len(stations_m) - 1
    for girder_index in range(len(girder_y)):
        supports.append(
            Support(
                node_ids[(0, girder_index)],
                uz=True,
                rx=True,
            )
        )
        supports.append(Support(node_ids[(last_x_index, girder_index)], uz=True))

    unloaded = StructuralModel(
        name=f"{project.name} - full seven-girder {stage.value}",
        nodes=tuple(nodes),
        materials=(_material(project),),
        sections=tuple(sections),
        beams=tuple(beams),
        supports=tuple(supports),
        load_cases=(LoadCase(_LOAD_CASE_IDS[stage], "EMPTY"),),
    )
    load_case = _stage_load_case(
        unloaded,
        stage=stage,
        girder_y_m=girder_y,
        segments=_stage_segments(project, stage),
    )
    return replace(unloaded, load_cases=(load_case,))


def build_full_bridge_stage_model(
    project: BridgeProject,
    *,
    stage: PermanentActionStage,
    longitudinal_divisions: int = 8,
) -> StructuralModel:
    """Build one complete bridge-width construction-stage structural model.

    The first two load-time systems contain every physical girder line in one
    coordinated model but no invented transverse stiffness: the reference
    bridge has no modelled diaphragms and its slab has not hardened when those
    actions are applied. The superimposed stage uses the connected final deck
    grillage, including all seven longitudinal girders and transverse deck strips.
    """

    if stage not in _STAGES:
        raise ValueError("Unsupported construction stage.")
    _material(project)
    stations = _stage_stations(
        project,
        stage=stage,
        longitudinal_divisions=longitudinal_divisions,
    )
    if stage is not PermanentActionStage.SUPERIMPOSED:
        return _unhardened_stage_model(
            project,
            stage=stage,
            stations_m=stations,
        )

    girder_y = girder_y_positions_m(project.geometry)
    build = build_final_composite_grillage(
        project,
        stations_m=stations,
        elastic_modulus_mpa=float(project.materials.elastic_modulus_mpa),
        load_case=LoadCase(_LOAD_CASE_IDS[stage], "EMPTY"),
    )
    load_case = _stage_load_case(
        build.model,
        stage=stage,
        girder_y_m=girder_y,
        segments=_stage_segments(project, stage),
    )
    return replace(
        build.model,
        name=f"{project.name} - full seven-girder final composite",
        load_cases=(load_case,),
    )


def _member_counts(model: StructuralModel) -> tuple[int, int]:
    nodes = {item.node_id: item for item in model.nodes}
    longitudinal = sum(
        1
        for beam in model.beams
        if abs(nodes[beam.node_i].y_m - nodes[beam.node_j].y_m) <= 1.0e-9
        and abs(nodes[beam.node_i].x_m - nodes[beam.node_j].x_m) > 1.0e-9
    )
    return longitudinal, len(model.beams) - longitudinal


def build_full_bridge_verification_suite(
    project: BridgeProject,
    *,
    longitudinal_divisions: int = 8,
) -> FullBridgeVerificationSuite:
    """Solve and package all three coordinated full-width bridge stages."""

    results: list[FullBridgeStageVerification] = []
    for stage in _STAGES:
        model = build_full_bridge_stage_model(
            project,
            stage=stage,
            longitudinal_divisions=longitudinal_divisions,
        )
        analysis = solve_vertical_grillage(model)
        longitudinal_count, transverse_count = _member_counts(model)
        connected = stage is PermanentActionStage.SUPERIMPOSED
        basis = (
            "connected final composite seven-girder orthogonal deck grillage"
            if connected
            else (
                "seven coordinated longitudinal girder lines; transverse stiffness "
                "is zero because no diaphragm properties are supplied and the in-situ "
                "deck has not hardened at this load stage"
            )
        )
        package = build_staad_verification_package(
            model,
            analysis,
            provenance={
                "repository": "RC-Single-Span-Bridge-Analysis-ANN",
                "verification_domain": "full_width_construction_stage_response",
                "stage": stage.value,
                "girder_line_count": str(project.geometry.girder_count),
                "structural_system_basis": basis,
                "load_basis": (
                    "all automatic_permanent_loads segments for this stage across "
                    "every physical girder line"
                ),
            },
        )
        result = FullBridgeStageVerification(
            stage=stage,
            model=model,
            analysis=analysis,
            staad_package=package,
            longitudinal_member_count=longitudinal_count,
            transverse_member_count=transverse_count,
            transverse_system_active=connected,
            structural_system_basis=basis,
        )
        if not result.passes_equilibrium_check:
            raise RuntimeError(f"Full-bridge {stage.value} model failed vertical equilibrium.")
        results.append(result)

    return FullBridgeVerificationSuite(tuple(results))
