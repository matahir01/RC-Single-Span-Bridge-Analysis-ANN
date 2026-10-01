from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from rc_single_span.analysis.construction import (
    ConstructionAnalysisResult,
    factored_permanent_deflection_at_x_mm,
    run_construction_stage_analysis,
)
from rc_single_span.analysis.permanent import PermanentLoadCategory
from rc_single_span.codes.bs5400.combinations import (
    BS5400LimitState,
    BS5400PermanentGammaFL,
)
from rc_single_span.codes.eurocode.combinations import EurocodeServiceabilityFactors
from rc_single_span.core.models import BridgeProject
from rc_single_span.core.progress import AnalysisControl
from rc_single_span.design.project import (
    BS5400DesignInputs,
    BS5400GirderDesignResult,
    EC2DesignInputs,
    EurocodeGirderDesignResult,
    run_bs5400_project_design,
    run_eurocode_project_design,
)
from rc_single_span.design.project_detailing import (
    BS5400DetailingInputs,
    BS5400GirderDetailingResult,
    EC2DetailingInputs,
    EC2GirderDetailingResult,
    run_bs5400_project_detailing,
    run_eurocode_project_detailing,
)
from rc_single_span.design.stage_d_project import (
    AdvancedGirderDetailingResult,
    AdvancedStageDInputs,
    run_bs5400_advanced_stage_d,
    run_eurocode_advanced_stage_d,
)
from rc_single_span.traffic.bs5400 import (
    BS5400NominalTrafficSuite,
    HASearchResult,
    HBSearchResult,
    run_ha_grillage_search,
    run_hb_grillage_search,
)
from rc_single_span.traffic.bs5400_combined import (
    HAHBCombinedSearchResult,
    run_ha_hb_combined_grillage_search,
)
from rc_single_span.traffic.combinations import (
    BS5400GirderCombinationResult,
    EurocodeGirderCombinationResult,
    build_bs5400_project_combinations,
    build_eurocode_project_combinations,
)
from rc_single_span.traffic.lm1 import (
    LM1SearchResult,
    frequent_lm1_adjustments,
    run_lm1_grillage_search,
)
from rc_single_span.traffic.lm1_influence import (
    prepare_lm1_influence_context,
    run_lm1_influence_grillage_search,
)
from rc_single_span.verification.deflection import (
    CombinedDeflectionEnvelope,
    combined_deflection_envelope,
)


@dataclass(frozen=True)
class ReferenceRunConfig:
    elastic_modulus_mpa: float
    eurocode_sls_factors: EurocodeServiceabilityFactors
    # The 15 m BS EN reference audit converged at 0.6 m with a 4.08765% maximum
    # envelope change from the 1.2 m grid, below the adopted 5% verification
    # criterion. Other bridge geometries should run their own convergence audit.
    lm1_longitudinal_step_m: float = 0.6
    bs_ha_longitudinal_step_m: float = 1.0
    bs_hb_longitudinal_step_m: float = 1.0
    bs_hb_transverse_step_m: float = 0.5
    bs_combined_hb_longitudinal_step_m: float = 2.0
    bs_combined_hb_transverse_step_m: float = 1.0
    bs_combined_ha_kel_step_m: float = 2.0
    hb_units: float = 45.0
    max_exhaustive_tandem_combinations: int = 5000
    max_exhaustive_kel_combinations: int = 5000
    max_exhaustive_ha_assignments: int = 500
    retain_all_cases: bool = True
    lm1_udl_influence_surface: bool = True

    def __post_init__(self) -> None:
        positive = (
            self.elastic_modulus_mpa,
            self.lm1_longitudinal_step_m,
            self.bs_ha_longitudinal_step_m,
            self.bs_hb_longitudinal_step_m,
            self.bs_hb_transverse_step_m,
            self.bs_combined_hb_longitudinal_step_m,
            self.bs_combined_hb_transverse_step_m,
            self.bs_combined_ha_kel_step_m,
            self.hb_units,
        )
        if any(value <= 0.0 for value in positive):
            raise ValueError("Reference-run analysis/search parameters must be positive.")


@dataclass(frozen=True)
class ReferenceRunResult:
    project: BridgeProject
    construction: ConstructionAnalysisResult
    lm1: LM1SearchResult | None
    bs_traffic: BS5400NominalTrafficSuite | None
    eurocode_combinations: tuple[EurocodeGirderCombinationResult, ...]
    bs5400_combinations: tuple[BS5400GirderCombinationResult, ...]
    eurocode_design: tuple[EurocodeGirderDesignResult, ...] | None
    bs5400_design: tuple[BS5400GirderDesignResult, ...] | None
    eurocode_detailing: tuple[EC2GirderDetailingResult, ...] | None
    bs5400_detailing: tuple[BS5400GirderDetailingResult, ...] | None
    eurocode_advanced_detailing: tuple[AdvancedGirderDetailingResult, ...] | None
    bs5400_advanced_detailing: tuple[AdvancedGirderDetailingResult, ...] | None
    eurocode_characteristic_deflection: tuple[CombinedDeflectionEnvelope, ...] | None
    bs5400_characteristic_deflection: dict[str, tuple[CombinedDeflectionEnvelope, ...]]


def _with_elastic_modulus(
    project: BridgeProject,
    elastic_modulus_mpa: float,
) -> BridgeProject:
    materials = project.materials.model_copy(
        update={"elastic_modulus_mpa": elastic_modulus_mpa}
    )
    return project.model_copy(update={"materials": materials})


def _bs_suite(
    project: BridgeProject,
    config: ReferenceRunConfig,
    control: AnalysisControl | None = None,
) -> BS5400NominalTrafficSuite:
    ha: HASearchResult = run_ha_grillage_search(
        project,
        longitudinal_step_m=config.bs_ha_longitudinal_step_m,
        max_exhaustive_kel_combinations=config.max_exhaustive_kel_combinations,
        retain_all_cases=config.retain_all_cases,
        control=control,
    )
    hb: HBSearchResult = run_hb_grillage_search(
        project,
        units=config.hb_units,
        longitudinal_step_m=config.bs_hb_longitudinal_step_m,
        transverse_step_m=config.bs_hb_transverse_step_m,
        retain_all_cases=config.retain_all_cases,
        control=control,
    )
    ha_hb: HAHBCombinedSearchResult = run_ha_hb_combined_grillage_search(
        project,
        units=config.hb_units,
        hb_longitudinal_step_m=config.bs_combined_hb_longitudinal_step_m,
        hb_transverse_step_m=config.bs_combined_hb_transverse_step_m,
        ha_kel_step_m=config.bs_combined_ha_kel_step_m,
        max_exhaustive_kel_combinations=config.max_exhaustive_kel_combinations,
        max_exhaustive_ha_assignments=config.max_exhaustive_ha_assignments,
        retain_all_cases=config.retain_all_cases,
        control=control,
    )
    return BS5400NominalTrafficSuite(
        ha=ha,
        hb=hb,
        ha_hb=ha_hb,
        application_status=(
            "Reference runner: HA, HB and HA+HB solved on the common grillage with "
            f"retain_all_cases={config.retain_all_cases}."
        ),
    )


def _ec_characteristic_deflection(
    project: BridgeProject,
    lm1: LM1SearchResult,
) -> tuple[CombinedDeflectionEnvelope, ...] | None:
    if not lm1.cases or len(lm1.cases) != lm1.evaluated_case_count:
        return None

    cases = tuple(
        (
            case.placement.case_id,
            f"LM1 case {case.placement.case_id}",
            case.model,
            case.analysis,
        )
        for case in lm1.cases
    )
    return tuple(
        combined_deflection_envelope(
            cases=cases,
            girder_index=index,
            traffic_factor=1.0,
            permanent_deflection_mm=lambda x, girder=index: (
                factored_permanent_deflection_at_x_mm(
                    project,
                    girder_index=girder,
                    x_m=x,
                )
            ),
        )
        for index in range(1, int(project.geometry.girder_count) + 1)
    )


def _bs_characteristic_deflection(
    project: BridgeProject,
    suite: BS5400NominalTrafficSuite,
) -> dict[str, tuple[CombinedDeflectionEnvelope, ...]]:
    gamma = BS5400PermanentGammaFL()
    named = gamma.as_named_factors(BS5400LimitState.SLS)
    permanent_factors = {
        PermanentLoadCategory.STRUCTURAL_DEAD: named["structural_dead"],
        PermanentLoadCategory.SURFACING: named["surfacing"],
        PermanentLoadCategory.OTHER_SUPERIMPOSED: named["other_superimposed"],
    }
    results: dict[str, tuple[CombinedDeflectionEnvelope, ...]] = {}

    for label, search in (
        ("ha", suite.ha),
        ("hb", suite.hb),
        ("ha_hb", suite.ha_hb),
    ):
        if not search.cases or len(search.cases) != search.evaluated_case_count:
            continue
        case_rows = tuple(
            (
                (
                    case.case_id
                    if hasattr(case, "case_id")
                    else case.placement.case_id
                ),
                (
                    case.description
                    if hasattr(case, "description")
                    else f"HA+HB case {case.placement.case_id}"
                ),
                case.model,
                case.analysis,
            )
            for case in search.cases
        )
        results[label] = tuple(
            combined_deflection_envelope(
                cases=case_rows,
                girder_index=index,
                traffic_factor=1.0,
                permanent_deflection_mm=lambda x, girder=index: (
                    factored_permanent_deflection_at_x_mm(
                        project,
                        girder_index=girder,
                        x_m=x,
                        factors_by_category=permanent_factors,
                    )
                ),
            )
            for index in range(1, int(project.geometry.girder_count) + 1)
        )
    return results


def run_reference_project(
    project: BridgeProject,
    *,
    config: ReferenceRunConfig,
    ec2_design_inputs: EC2DesignInputs | None = None,
    bs5400_design_inputs: BS5400DesignInputs | None = None,
    ec2_detailing_inputs: EC2DetailingInputs | None = None,
    bs5400_detailing_inputs: BS5400DetailingInputs | None = None,
    ec2_advanced_detailing_inputs: AdvancedStageDInputs | None = None,
    bs5400_advanced_detailing_inputs: AdvancedStageDInputs | None = None,
    code_route: Literal["both", "bs_en", "bs5400"] = "both",
    control: AnalysisControl | None = None,
) -> ReferenceRunResult:
    """Run one reproducible deterministic verification project end to end.

    Values absent from the physical project are never invented. Elastic modulus
    is explicit in the run configuration; code/design/detailing inputs are
    explicit optional arguments and are skipped when not supplied. Advanced
    Stage D checks are also optional and require their project-specific inputs.
    """

    if code_route not in {"both", "bs_en", "bs5400"}:
        raise ValueError(f"Unsupported code route: {code_route}")
    if code_route == "bs_en" and (
        bs5400_design_inputs or bs5400_detailing_inputs or bs5400_advanced_detailing_inputs
    ):
        raise ValueError("BS 5400 inputs require the BS 5400 code route.")
    if code_route == "bs5400" and (
        ec2_design_inputs or ec2_detailing_inputs or ec2_advanced_detailing_inputs
    ):
        raise ValueError("EC2 inputs require the BS EN code route.")

    if control is not None:
        control.report("Construction stages")
    resolved = _with_elastic_modulus(project, config.elastic_modulus_mpa)
    construction = run_construction_stage_analysis(resolved)
    lm1_search = (
        run_lm1_influence_grillage_search
        if config.lm1_udl_influence_surface else run_lm1_grillage_search
    )
    lm1_context = (
        prepare_lm1_influence_context(
            resolved,
            longitudinal_step_m=config.lm1_longitudinal_step_m,
            max_exhaustive_tandem_combinations=config.max_exhaustive_tandem_combinations,
            control=control,
        )
        if code_route != "bs5400" and config.lm1_udl_influence_surface else None
    )
    lm1_kwargs = (
        {"context": lm1_context, "control": control, "phase": "LM1 characteristic"}
        if lm1_context is not None
        else {} if config.lm1_udl_influence_surface
        else {"retain_all_cases": config.retain_all_cases}
    )
    lm1 = (
        lm1_search(
            resolved,
            longitudinal_step_m=config.lm1_longitudinal_step_m,
            max_exhaustive_tandem_combinations=config.max_exhaustive_tandem_combinations,
            **lm1_kwargs,
        )
        if code_route != "bs5400" else None
    )
    needs_frequent = lm1 is not None and config.eurocode_sls_factors.frequent_components_differ
    frequent_factors = (
        frequent_lm1_adjustments(config.eurocode_sls_factors) if needs_frequent else None
    )
    frequent_kwargs = (
        {"context": lm1_context.with_uniform_factors(frequent_factors),
         "control": control, "phase": "LM1 frequent"}
        if lm1_context is not None and frequent_factors is not None else lm1_kwargs
    )
    frequent_lm1 = (
        lm1_search(
            resolved,
            factors=frequent_factors,
            longitudinal_step_m=config.lm1_longitudinal_step_m,
            max_exhaustive_tandem_combinations=config.max_exhaustive_tandem_combinations,
            **frequent_kwargs,
        )
        if needs_frequent else None
    )
    if control is not None:
        control.report("Legacy traffic" if code_route == "bs5400" else "Combinations")
    bs_traffic = _bs_suite(resolved, config, control) if code_route != "bs_en" else None
    if control is not None:
        control.report("Combinations")
    ec_combinations = (
        build_eurocode_project_combinations(
            resolved, lm1, sls_factors=config.eurocode_sls_factors,
            frequent_traffic=frequent_lm1,
        ) if lm1 is not None else ()
    )
    bs_combinations = (
        build_bs5400_project_combinations(resolved, bs_traffic)
        if bs_traffic is not None else ()
    )

    if control is not None:
        control.report("EC2 design" if code_route == "bs_en" else "BS 5400 design")
    ec_design = (
        None
        if ec2_design_inputs is None
        else run_eurocode_project_design(
            resolved,
            ec_combinations,
            lm1,
            inputs=ec2_design_inputs,
        )
    )
    bs_design = (
        None
        if bs5400_design_inputs is None
        else run_bs5400_project_design(
            resolved,
            bs_combinations,
            bs_traffic,
            inputs=bs5400_design_inputs,
        )
    )

    if ec2_detailing_inputs is not None and ec_design is None:
        raise ValueError("EC2 detailing requires EC2 design inputs/results.")
    if bs5400_detailing_inputs is not None and bs_design is None:
        raise ValueError("BS 5400 detailing requires BS 5400 design inputs/results.")

    ec_detailing = (
        None
        if ec2_detailing_inputs is None
        else run_eurocode_project_detailing(
            resolved,
            ec_combinations,
            ec_design,
            design_inputs=ec2_design_inputs,
            detailing_inputs=ec2_detailing_inputs,
            traffic=lm1,
        )
    )
    bs_detailing = (
        None
        if bs5400_detailing_inputs is None
        else run_bs5400_project_detailing(
            resolved,
            bs_combinations,
            bs_design,
            design_inputs=bs5400_design_inputs,
            detailing_inputs=bs5400_detailing_inputs,
            traffic=bs_traffic,
        )
    )

    if ec2_advanced_detailing_inputs is not None and ec_detailing is None:
        raise ValueError("EC2 advanced Stage D requires EC2 detailing results.")
    if bs5400_advanced_detailing_inputs is not None and bs_detailing is None:
        raise ValueError("BS 5400 advanced Stage D requires BS 5400 detailing results.")

    ec_advanced = (
        None
        if ec2_advanced_detailing_inputs is None
        else run_eurocode_advanced_stage_d(
            resolved,
            ec_combinations,
            ec_design,
            ec_detailing,
            design_inputs=ec2_design_inputs,
            inputs=ec2_advanced_detailing_inputs,
        )
    )
    bs_advanced = (
        None
        if bs5400_advanced_detailing_inputs is None
        else run_bs5400_advanced_stage_d(
            resolved,
            bs_combinations,
            bs_design,
            bs_detailing,
            design_inputs=bs5400_design_inputs,
            detailing_inputs=bs5400_detailing_inputs,
            inputs=bs5400_advanced_detailing_inputs,
        )
    )

    if control is not None:
        control.report("Finalizing results")
    return ReferenceRunResult(
        project=resolved,
        construction=construction,
        lm1=lm1,
        bs_traffic=bs_traffic,
        eurocode_combinations=ec_combinations,
        bs5400_combinations=bs_combinations,
        eurocode_design=ec_design,
        bs5400_design=bs_design,
        eurocode_detailing=ec_detailing,
        bs5400_detailing=bs_detailing,
        eurocode_advanced_detailing=ec_advanced,
        bs5400_advanced_detailing=bs_advanced,
        eurocode_characteristic_deflection=(
            _ec_characteristic_deflection(resolved, lm1) if lm1 is not None else None
        ),
        bs5400_characteristic_deflection=(
            _bs_characteristic_deflection(resolved, bs_traffic)
            if bs_traffic is not None else {}
        ),
    )
