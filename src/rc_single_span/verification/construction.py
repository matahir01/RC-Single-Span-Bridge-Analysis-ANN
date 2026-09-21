from __future__ import annotations

from dataclasses import dataclass

from rc_single_span.analysis.construction import (
    ConstructionAnalysisResult,
    ConstructionStageGirderResult,
    CumulativeGirderResult,
    run_construction_stage_analysis,
)
from rc_single_span.analysis.grillage_solver import GrillageAnalysisResult
from rc_single_span.analysis.permanent import PermanentLoadSegment
from rc_single_span.analysis.simple_span import (
    DistributedLoadSegment,
    simple_span_distributed_load_response,
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
from rc_single_span.verification.beam_fe import solve_construction_beam_fe
from rc_single_span.verification.comparison import (
    ComparisonTolerance,
    ScalarComparison,
    compare_scalar,
)
from rc_single_span.verification.member_forces import native_global_member_end_forces
from rc_single_span.verification.package import (
    StaadVerificationPackage,
    build_staad_verification_package,
)

_STAGE_ORDER = {
    PermanentActionStage.PRECAST_GIRDER: 1,
    PermanentActionStage.DECK_CONSTRUCTION: 2,
    PermanentActionStage.SUPERIMPOSED: 3,
}


@dataclass(frozen=True)
class ConstructionStageVerification:
    girder_index: int
    stage: PermanentActionStage
    reference: ConstructionStageGirderResult
    model: StructuralModel
    analysis: GrillageAnalysisResult
    comparisons: tuple[ScalarComparison, ...]
    staad_package: StaadVerificationPackage

    @property
    def passes_internal_crosscheck(self) -> bool:
        return all(item.passes for item in self.comparisons)


@dataclass(frozen=True)
class CumulativePermanentVerification:
    girder_index: int
    reference: CumulativeGirderResult
    comparisons: tuple[ScalarComparison, ...]

    @property
    def passes_internal_crosscheck(self) -> bool:
        return all(item.passes for item in self.comparisons)


@dataclass(frozen=True)
class ConstructionVerificationSuite:
    construction: ConstructionAnalysisResult
    stages: tuple[ConstructionStageVerification, ...]
    cumulative: tuple[CumulativePermanentVerification, ...]

    @property
    def passes_internal_crosscheck(self) -> bool:
        return all(
            item.passes_internal_crosscheck
            for item in (*self.stages, *self.cumulative)
        )

    def stage(
        self,
        *,
        girder_index: int,
        stage: PermanentActionStage,
    ) -> ConstructionStageVerification:
        return next(
            item
            for item in self.stages
            if item.girder_index == girder_index and item.stage is stage
        )


def _distributed(
    loads: tuple[PermanentLoadSegment, ...],
) -> tuple[DistributedLoadSegment, ...]:
    return tuple(
        DistributedLoadSegment(
            magnitude_kn_m=item.magnitude_kn_m,
            start_m=item.x_start_m,
            end_m=item.x_end_m,
            label=item.source,
        )
        for item in loads
    )


def _merge_stations(
    values: tuple[float, ...],
    *,
    tolerance: float = 1.0e-3,
) -> tuple[float, ...]:
    result: list[float] = []
    for value in sorted(float(item) for item in values):
        if not result or abs(value - result[-1]) > tolerance:
            result.append(value)
    return tuple(result)


def _shared_stations_for_girder(
    *,
    span_m: float,
    stage_items: tuple[ConstructionStageGirderResult, ...],
    cumulative: CumulativeGirderResult,
    longitudinal_divisions: int,
) -> tuple[float, ...]:
    if not 0 <= longitudinal_divisions <= 16:
        raise ValueError(
            "Construction verification supplemental divisions must lie between 0 and 16."
        )

    base = (
        ()
        if longitudinal_divisions == 0
        else tuple(
            span_m * index / longitudinal_divisions
            for index in range(longitudinal_divisions + 1)
        )
    )
    load_boundaries = tuple(
        coordinate
        for item in stage_items
        for load in item.loads
        for coordinate in (load.x_start_m, load.x_end_m)
    )
    stage_targets = tuple(
        coordinate
        for item in stage_items
        for coordinate in (
            item.response.max_moment_position_m,
            item.max_deflection_position_m,
        )
    )
    all_loads = tuple(
        load
        for item in stage_items
        for load in _distributed(item.loads)
    )
    combined_response = simple_span_distributed_load_response(
        span_m,
        all_loads,
    )
    return _merge_stations(
        (
            0.0,
            span_m,
            *base,
            *load_boundaries,
            *stage_targets,
            combined_response.max_moment_position_m,
            cumulative.max_deflection_position_m,
        )
    )


def _stage_structural_model(
    project: BridgeProject,
    item: ConstructionStageGirderResult,
    *,
    stations_m: tuple[float, ...],
) -> StructuralModel:
    nodes = tuple(
        Node(index + 1, x_m, 0.0, 0.0)
        for index, x_m in enumerate(stations_m)
    )
    section = item.section
    model_section = Section(
        1,
        f"{item.stage.value} girder {item.girder_index}",
        section.area_m2,
        section.torsion_constant_m4,
        section.iy_m4,
        section.iz_m4,
    )
    material = Material(
        1,
        "Concrete",
        item.elastic_modulus_mpa * 1000.0,
        poisson_ratio=0.2,
        weight_density_kn_m3=float(project.materials.concrete_density_kn_m3),
    )

    beams: list[Beam] = []
    loads: list[UniformLoad] = []
    for member_index in range(len(stations_m) - 1):
        member_id = member_index + 1
        x1 = stations_m[member_index]
        x2 = stations_m[member_index + 1]
        member_length = x2 - x1
        beams.append(
            Beam(
                member_id,
                member_index + 1,
                member_index + 2,
                1,
                1,
            )
        )
        for source in item.loads:
            overlap_start = max(x1, source.x_start_m)
            overlap_end = min(x2, source.x_end_m)
            if overlap_end <= overlap_start + 1.0e-12:
                continue
            local_start = overlap_start - x1
            local_end = overlap_end - x1
            if (
                local_start <= 1.0e-10
                and abs(local_end - member_length) <= 1.0e-10
            ):
                loads.append(
                    UniformLoad(
                        member_id=member_id,
                        magnitude_kn_m=-source.magnitude_kn_m,
                    )
                )
            else:
                loads.append(
                    UniformLoad(
                        member_id=member_id,
                        magnitude_kn_m=-source.magnitude_kn_m,
                        start_m=local_start,
                        end_m=local_end,
                    )
                )

    load_case_id = 100 * item.girder_index + _STAGE_ORDER[item.stage]
    load_case = LoadCase(
        load_case_id,
        f"G{item.girder_index} {item.stage.value}",
        uniform_loads=tuple(loads),
    )
    return StructuralModel(
        name=(
            f"{project.name} - construction stage {item.stage.value} "
            f"- girder {item.girder_index}"
        ),
        nodes=nodes,
        materials=(material,),
        sections=(model_section,),
        beams=tuple(beams),
        supports=tuple(
            Support(
                node.node_id,
                uz=node.node_id in {nodes[0].node_id, nodes[-1].node_id},
                rx=True,
            )
            for node in nodes
        ),
        load_cases=(load_case,),
    )


def _node_at_x(
    model: StructuralModel,
    analysis: GrillageAnalysisResult,
    x_m: float,
):
    nodes = {item.node_id: item for item in model.nodes}
    result = {item.node_id: item for item in analysis.nodes}
    node = next(
        (
            item
            for item in model.nodes
            if abs(item.x_m - x_m) <= 1.0e-3
        ),
        None,
    )
    if node is None:
        raise ValueError(f"Verification station {x_m:.12g} m is absent from the model.")
    return nodes[node.node_id], result[node.node_id]


def _moment_magnitude_at_x(
    model: StructuralModel,
    analysis: GrillageAnalysisResult,
    x_m: float,
) -> float:
    nodes = {item.node_id: item for item in model.nodes}
    beam_by_id = {item.member_id: item for item in model.beams}
    candidates: list[float] = []
    for row in native_global_member_end_forces(model, analysis):
        beam = beam_by_id[row.member_id]
        node_id = beam.node_i if row.end == "i" else beam.node_j
        if abs(nodes[node_id].x_m - x_m) <= 1.0e-3:
            candidates.append(abs(row.my_knm))
    if not candidates:
        raise ValueError(f"No member-end moment exists at x={x_m:.12g} m.")
    return max(candidates)


def _stage_comparisons(
    item: ConstructionStageGirderResult,
    model: StructuralModel,
    analysis: GrillageAnalysisResult,
) -> tuple[ScalarComparison, ...]:
    node_results = {row.node_id: row for row in analysis.nodes}
    left = node_results[model.nodes[0].node_id].vertical_reaction_kn
    right = node_results[model.nodes[-1].node_id].vertical_reaction_kn
    max_shear = max(abs(left), abs(right))
    max_moment = _moment_magnitude_at_x(
        model,
        analysis,
        item.response.max_moment_position_m,
    )
    _, target_node = _node_at_x(
        model,
        analysis,
        item.max_deflection_position_m,
    )
    deflection_mm = -target_node.vertical_displacement_m * 1000.0

    force_tolerance = ComparisonTolerance(relative=1.0e-5, absolute=1.0e-5)
    deflection_tolerance = ComparisonTolerance(
        relative=2.0e-3,
        absolute=1.0e-3,
    )
    source = "independent native beam-FE cross-check of construction-stage equations"
    return (
        compare_scalar(
            label=f"G{item.girder_index} {item.stage.value} left reaction",
            internal_value=left,
            reference_value=item.response.reaction_left_kn,
            tolerance=force_tolerance,
            unit="kN",
            source=source,
        ),
        compare_scalar(
            label=f"G{item.girder_index} {item.stage.value} right reaction",
            internal_value=right,
            reference_value=item.response.reaction_right_kn,
            tolerance=force_tolerance,
            unit="kN",
            source=source,
        ),
        compare_scalar(
            label=f"G{item.girder_index} {item.stage.value} maximum shear",
            internal_value=max_shear,
            reference_value=item.response.max_abs_shear_kn,
            tolerance=force_tolerance,
            unit="kN",
            source=source,
        ),
        compare_scalar(
            label=f"G{item.girder_index} {item.stage.value} maximum moment",
            internal_value=max_moment,
            reference_value=item.response.max_moment_knm,
            tolerance=force_tolerance,
            unit="kNm",
            source=source,
        ),
        compare_scalar(
            label=f"G{item.girder_index} {item.stage.value} maximum deflection",
            internal_value=deflection_mm,
            reference_value=item.max_downward_deflection_mm,
            tolerance=deflection_tolerance,
            unit="mm",
            source=source,
        ),
    )


def _cumulative_comparisons(
    *,
    girder_index: int,
    stage_cases: tuple[ConstructionStageVerification, ...],
    reference: CumulativeGirderResult,
) -> tuple[ScalarComparison, ...]:
    if not stage_cases:
        raise ValueError("Cumulative construction verification requires stage cases.")

    span = stage_cases[0].model.nodes[-1].x_m
    all_loads = tuple(
        load
        for case in stage_cases
        for load in _distributed(case.reference.loads)
    )
    combined_response = simple_span_distributed_load_response(span, all_loads)
    moment_position = combined_response.max_moment_position_m

    left_reaction = sum(
        case.analysis.nodes[0].vertical_reaction_kn
        for case in stage_cases
    )
    right_reaction = sum(
        case.analysis.nodes[-1].vertical_reaction_kn
        for case in stage_cases
    )
    max_shear = max(abs(left_reaction), abs(right_reaction))
    max_moment = sum(
        _moment_magnitude_at_x(
            case.model,
            case.analysis,
            moment_position,
        )
        for case in stage_cases
    )

    cumulative_deflection_mm = 0.0
    for case in stage_cases:
        _, node = _node_at_x(
            case.model,
            case.analysis,
            reference.max_deflection_position_m,
        )
        cumulative_deflection_mm += -node.vertical_displacement_m * 1000.0

    force_tolerance = ComparisonTolerance(relative=1.0e-5, absolute=1.0e-5)
    deflection_tolerance = ComparisonTolerance(
        relative=2.0e-3,
        absolute=1.0e-3,
    )
    source = "superposed native stage-beam FE cross-check"
    return (
        compare_scalar(
            label=f"G{girder_index} cumulative maximum shear",
            internal_value=max_shear,
            reference_value=reference.max_shear_kn,
            tolerance=force_tolerance,
            unit="kN",
            source=source,
        ),
        compare_scalar(
            label=f"G{girder_index} cumulative maximum moment",
            internal_value=max_moment,
            reference_value=reference.max_moment_knm,
            tolerance=force_tolerance,
            unit="kNm",
            source=source,
        ),
        compare_scalar(
            label=f"G{girder_index} cumulative maximum deflection",
            internal_value=cumulative_deflection_mm,
            reference_value=reference.max_downward_deflection_mm,
            tolerance=deflection_tolerance,
            unit="mm",
            source=source,
        ),
    )


def build_construction_verification_suite(
    project: BridgeProject,
    *,
    longitudinal_divisions: int = 8,
) -> ConstructionVerificationSuite:
    """Cross-check and package every construction/permanent-action stage.

    The production construction workflow is intentionally a set of statically
    determinate longitudinal girder stages after transverse permanent actions
    have been assigned to girder lines. This verifier preserves that exact
    mechanics: same load segments, same stage section A/J/Iy/Iz and same E.

    The second solver is a dedicated Stage-8 bending-only Euler-Bernoulli beam
    FE implementation, deliberately separate from both the production simple-span
    equations and the 3-DOF traffic grillage solver. Exact load boundaries and analytical
    governing response stations are inserted as nodes, with numerically equivalent
    stations within 1 mm coalesced to prevent meaningless sliver elements, so only a small
    number of supplemental divisions is needed; excessive subdivision is avoided
    because it needlessly degrades the conditioning of the verification stiffness
    matrix. Each solved stage is also exported as a STAAD package for genuine
    external verification.
    """

    construction = run_construction_stage_analysis(project)
    span = float(project.geometry.span_m)
    stage_verifications: list[ConstructionStageVerification] = []
    cumulative_verifications: list[CumulativePermanentVerification] = []

    for girder_index in range(1, int(project.geometry.girder_count) + 1):
        stage_items = tuple(
            item
            for item in construction.stages
            if item.girder_index == girder_index
        )
        cumulative = next(
            item
            for item in construction.cumulative_by_girder
            if item.girder_index == girder_index
        )
        stations = _shared_stations_for_girder(
            span_m=span,
            stage_items=stage_items,
            cumulative=cumulative,
            longitudinal_divisions=longitudinal_divisions,
        )

        current: list[ConstructionStageVerification] = []
        for item in stage_items:
            model = _stage_structural_model(
                project,
                item,
                stations_m=stations,
            )
            analysis = solve_construction_beam_fe(model)
            equilibrium_scale = max(
                abs(analysis.total_applied_vertical_load_kn),
                abs(analysis.total_vertical_reaction_kn),
                1.0,
            )
            equilibrium_limit = max(1.0e-5, 1.0e-5 * equilibrium_scale)
            if abs(analysis.vertical_equilibrium_residual_kn) > equilibrium_limit:
                raise RuntimeError(
                    "Construction verification beam failed vertical equilibrium: "
                    f"applied={analysis.total_applied_vertical_load_kn:.12g} kN, "
                    f"reaction={analysis.total_vertical_reaction_kn:.12g} kN, "
                    f"residual={analysis.vertical_equilibrium_residual_kn:.12g} kN, "
                    f"limit={equilibrium_limit:.12g} kN."
                )
            comparisons = _stage_comparisons(
                item,
                model,
                analysis,
            )
            package = build_staad_verification_package(
                model,
                analysis,
                provenance={
                    "repository": "RC-Single-Span-Bridge-Analysis-ANN",
                    "verification_domain": "construction_stage_response",
                    "girder_index": str(girder_index),
                    "stage": item.stage.value,
                    "section_basis": item.section.basis,
                    "load_basis": (
                        "exact automatic_permanent_loads segments assigned to this "
                        "girder and construction stage"
                    ),
                    "native_torsion_stabilization": (
                        "RX restrained at every 1D verification station to remove the "
                        "unused torsional DOF chain; vertical UZ is restrained only at "
                        "the two bearings and no torsional loads are present"
                    ),
                },
            )
            result = ConstructionStageVerification(
                girder_index=girder_index,
                stage=item.stage,
                reference=item,
                model=model,
                analysis=analysis,
                comparisons=comparisons,
                staad_package=package,
            )
            stage_verifications.append(result)
            current.append(result)

        cumulative_verifications.append(
            CumulativePermanentVerification(
                girder_index=girder_index,
                reference=cumulative,
                comparisons=_cumulative_comparisons(
                    girder_index=girder_index,
                    stage_cases=tuple(current),
                    reference=cumulative,
                ),
            )
        )

    return ConstructionVerificationSuite(
        construction=construction,
        stages=tuple(stage_verifications),
        cumulative=tuple(cumulative_verifications),
    )
