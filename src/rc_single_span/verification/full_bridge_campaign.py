from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from rc_single_span.analysis.grillage_solver import (
    GrillageAnalysisResult,
    solve_vertical_grillage,
)
from rc_single_span.analysis.permanent import (
    PermanentLoadCategory,
    PermanentLoadSegment,
    automatic_permanent_loads,
)
from rc_single_span.analysis.sections import girder_y_positions_m
from rc_single_span.analysis.structural_model import StructuralModel
from rc_single_span.codes.bs5400.combinations import (
    BS5400LimitState,
    BS5400PermanentGammaFL,
    BS5400PrimaryTraffic,
    primary_live_gamma_fl,
)
from rc_single_span.codes.eurocode.combinations import (
    EurocodeCombinationFactors,
    EurocodeServiceabilityFactors,
)
from rc_single_span.core.models import BridgeProject, PermanentActionStage
from rc_single_span.traffic.bs5400 import (
    BS5400CaseResult,
    HASearchResult,
    HBSearchResult,
    run_ha_grillage_search,
    run_hb_grillage_search,
    traffic_equilibrium_tolerance_kn,
)
from rc_single_span.traffic.bs5400_combined import (
    HAHBCombinedCaseResult,
    HAHBCombinedSearchResult,
    run_ha_hb_combined_grillage_search,
)
from rc_single_span.traffic.lm1 import (
    LM1CaseResult,
    LM1SearchResult,
    frequent_lm1_adjustments,
    run_lm1_grillage_search,
)
from rc_single_span.traffic.lm1_influence import run_lm1_influence_grillage_search
from rc_single_span.verification.full_bridge import (
    build_full_bridge_stage_model,
    build_girder_line_load_case,
)
from rc_single_span.verification.package import (
    StaadVerificationPackage,
    build_staad_verification_package,
)


class TrafficAction(str, Enum):
    LM1 = "lm1"
    LM1_FREQUENT = "lm1_frequent"
    HA = "ha"
    HB = "hb"
    HA_HB = "ha_hb"


@dataclass(frozen=True)
class FullBridgeTrafficSearchConfig:
    lm1_longitudinal_step_m: float = 1.2
    lm1_max_exhaustive_tandem_combinations: int = 5000
    lm1_udl_influence_surface: bool = True
    ha_longitudinal_step_m: float = 1.0
    ha_max_exhaustive_kel_combinations: int = 5000
    hb_units: float = 45.0
    hb_longitudinal_step_m: float = 1.0
    hb_transverse_step_m: float = 0.5
    combined_hb_longitudinal_step_m: float = 2.0
    combined_hb_transverse_step_m: float = 1.0
    combined_ha_kel_step_m: float = 2.0
    combined_max_exhaustive_kel_combinations: int = 5000
    combined_max_exhaustive_ha_assignments: int = 500

    def __post_init__(self) -> None:
        positive = (
            self.lm1_longitudinal_step_m,
            self.ha_longitudinal_step_m,
            self.hb_units,
            self.hb_longitudinal_step_m,
            self.hb_transverse_step_m,
            self.combined_hb_longitudinal_step_m,
            self.combined_hb_transverse_step_m,
            self.combined_ha_kel_step_m,
        )
        if any(value <= 0.0 for value in positive):
            raise ValueError("Full-bridge traffic search dimensions must be positive.")
        counts = (
            self.lm1_max_exhaustive_tandem_combinations,
            self.ha_max_exhaustive_kel_combinations,
            self.combined_max_exhaustive_kel_combinations,
            self.combined_max_exhaustive_ha_assignments,
        )
        if any(value < 1 for value in counts):
            raise ValueError("Full-bridge traffic search limits must be positive.")


@dataclass(frozen=True)
class FullBridgeTrafficCaseVerification:
    case_key: str
    standard: str
    action: TrafficAction
    source_case_id: int
    description: str
    governing_for: tuple[str, ...]
    model: StructuralModel
    analysis: GrillageAnalysisResult
    staad_package: StaadVerificationPackage

    @property
    def passes_equilibrium_check(self) -> bool:
        return abs(
            self.analysis.vertical_equilibrium_residual_kn
        ) <= traffic_equilibrium_tolerance_kn(
            self.analysis,
        )


@dataclass(frozen=True)
class FullBridgeTrafficCampaign:
    lm1: LM1SearchResult
    ha: HASearchResult
    hb: HBSearchResult
    ha_hb: HAHBCombinedSearchResult
    cases: tuple[FullBridgeTrafficCaseVerification, ...]
    lm1_frequent: LM1SearchResult | None = None

    @property
    def passes_internal_checks(self) -> bool:
        return bool(self.cases) and all(
            item.passes_equilibrium_check and item.governing_for for item in self.cases
        )

    def cases_for(
        self,
        action: TrafficAction,
    ) -> tuple[FullBridgeTrafficCaseVerification, ...]:
        return tuple(item for item in self.cases if item.action is action)


@dataclass(frozen=True)
class PermanentComponentVerification:
    component_key: str
    stage: PermanentActionStage
    category: PermanentLoadCategory
    segments: tuple[PermanentLoadSegment, ...]
    model: StructuralModel
    analysis: GrillageAnalysisResult
    staad_package: StaadVerificationPackage

    @property
    def characteristic_resultant_kn(self) -> float:
        return sum(item.total_load_kn for item in self.segments)


@dataclass(frozen=True)
class PermanentComponentSuite:
    components: tuple[PermanentComponentVerification, ...]

    def for_category(
        self,
        category: PermanentLoadCategory,
    ) -> tuple[PermanentComponentVerification, ...]:
        return tuple(item for item in self.components if item.category is category)


@dataclass(frozen=True)
class CrossStageCombinationRule:
    rule_id: str
    standard: str
    name: str
    traffic_action: TrafficAction
    permanent_factors: dict[PermanentLoadCategory, float]
    traffic_factor: float
    application_basis: str = (
        "Superpose response components from their load-time stiffness models; "
        "do not reapply early-stage permanent loads to the final composite stiffness."
    )


def _case_id(
    case: LM1CaseResult | BS5400CaseResult | HAHBCombinedCaseResult,
) -> int:
    if isinstance(case, BS5400CaseResult):
        return case.case_id
    return case.placement.case_id


def _description(
    action: TrafficAction,
    case: LM1CaseResult | BS5400CaseResult | HAHBCombinedCaseResult,
) -> str:
    if isinstance(case, LM1CaseResult):
        lanes = ", ".join(
            f"lane {lane.lane_number} lead x={lane.tandem_lead_x_m:.6g} m"
            for lane in case.placement.lanes
        )
        return f"BS EN 1991-2:2003 LM1 ({lanes})"
    if isinstance(case, BS5400CaseResult):
        return case.description
    if action is TrafficAction.HA_HB:
        return case.description
    raise TypeError("Unsupported full-bridge traffic case type.")


def _governing_labels(search: object, source_case_id: int) -> tuple[str, ...]:
    labels: list[str] = []
    for girder in search.girders:
        for quantity, component in (
            ("moment", girder.moment_knm),
            ("shear", girder.shear_kn),
            ("torsion", girder.torsion_knm),
            ("deflection", girder.deflection_mm),
        ):
            if component.case_id == source_case_id:
                labels.append(f"G{girder.girder_index} {quantity}")

    # The influence-surface LM1 search can retain a case solely because it
    # governs a longitudinal station used by the reinforcement envelope. Such a
    # case is genuine verification evidence even when it does not govern the
    # girder-wide maximum moment/shear/torsion/deflection summary.
    for girder in getattr(search, "station_moments", ()):
        for station in girder.stations:
            if station.moment_knm.case_id == source_case_id:
                labels.append(
                    f"G{girder.girder_index} moment at x={station.x_m:.6g} m"
                )
    return tuple(dict.fromkeys(labels))


def _validate_connected_full_bridge(
    project: BridgeProject,
    model: StructuralModel,
) -> None:
    nodes = {item.node_id: item for item in model.nodes}
    longitudinal_y = {
        round(nodes[beam.node_i].y_m, 9)
        for beam in model.beams
        if abs(nodes[beam.node_i].y_m - nodes[beam.node_j].y_m) <= 1.0e-9
        and abs(nodes[beam.node_i].x_m - nodes[beam.node_j].x_m) > 1.0e-9
    }
    expected_y = {round(value, 9) for value in girder_y_positions_m(project.geometry)}
    transverse_count = sum(
        1
        for beam in model.beams
        if abs(nodes[beam.node_i].x_m - nodes[beam.node_j].x_m) <= 1.0e-9
        and abs(nodes[beam.node_i].y_m - nodes[beam.node_j].y_m) > 1.0e-9
    )
    if longitudinal_y != expected_y or transverse_count == 0:
        raise RuntimeError(
            "Traffic verification case is not a connected full-width physical-girder grillage."
        )


def build_full_bridge_traffic_campaign(
    project: BridgeProject,
    *,
    lm1: LM1SearchResult,
    ha: HASearchResult,
    hb: HBSearchResult,
    ha_hb: HAHBCombinedSearchResult,
    lm1_frequent: LM1SearchResult | None = None,
) -> FullBridgeTrafficCampaign:
    """Package every retained governing traffic placement as a seven-girder model."""

    groups: tuple[
        tuple[
            TrafficAction,
            str,
            object,
            tuple[LM1CaseResult | BS5400CaseResult | HAHBCombinedCaseResult, ...],
        ],
        ...,
    ] = (
        (TrafficAction.LM1, "BS EN 1991-2:2003", lm1, lm1.cases),
        *((
            (
                TrafficAction.LM1_FREQUENT,
                "BS EN 1991-2:2003 frequent LM1",
                lm1_frequent,
                lm1_frequent.cases,
            ),
        ) if lm1_frequent is not None else ()),
        (TrafficAction.HA, "BD 37/01", ha, ha.cases),
        (TrafficAction.HB, "BD 37/01", hb, hb.cases),
        (TrafficAction.HA_HB, "BD 37/01", ha_hb, ha_hb.cases),
    )
    packaged: list[FullBridgeTrafficCaseVerification] = []

    for action, standard, search, cases in groups:
        if not cases:
            raise ValueError(f"{action.value} search retained no governing cases.")
        for case in cases:
            source_case_id = _case_id(case)
            governing_for = _governing_labels(search, source_case_id)
            if not governing_for:
                raise RuntimeError(
                    f"Retained {action.value} case {source_case_id} governs no reported quantity."
                )
            _validate_connected_full_bridge(project, case.model)
            case_key = f"{action.value}_{source_case_id:06d}"
            description = _description(action, case)
            package = build_staad_verification_package(
                case.model,
                case.analysis,
                provenance={
                    "repository": "RC-Single-Span-Bridge-Analysis-ANN",
                    "verification_domain": "full_width_governing_traffic_response",
                    "standard": standard,
                    "traffic_action": action.value,
                    "source_search_case_id": str(source_case_id),
                    "case_key": case_key,
                    "governing_for": "; ".join(governing_for),
                    "search_retention_basis": (
                        "case governs at least one girder-wide response or station moment "
                        "quantity across the seven physical girders"
                    ),
                },
            )
            packaged.append(
                FullBridgeTrafficCaseVerification(
                    case_key=case_key,
                    standard=standard,
                    action=action,
                    source_case_id=source_case_id,
                    description=description,
                    governing_for=governing_for,
                    model=case.model,
                    analysis=case.analysis,
                    staad_package=package,
                )
            )

    campaign = FullBridgeTrafficCampaign(lm1, ha, hb, ha_hb, tuple(packaged), lm1_frequent)
    if not campaign.passes_internal_checks:
        raise RuntimeError("Full-bridge traffic campaign failed an internal check.")
    return campaign


def run_full_bridge_traffic_campaign(
    project: BridgeProject,
    *,
    config: FullBridgeTrafficSearchConfig | None = None,
    eurocode_sls_factors: EurocodeServiceabilityFactors | None = None,
) -> FullBridgeTrafficCampaign:
    """Search, retain and package governing LM1, HA, HB and HA+HB cases."""

    current = config or FullBridgeTrafficSearchConfig()
    lm1_search = (
        run_lm1_influence_grillage_search
        if current.lm1_udl_influence_surface
        else run_lm1_grillage_search
    )
    lm1_kwargs = {} if current.lm1_udl_influence_surface else {
        "retain_all_cases": False,
    }
    lm1 = lm1_search(
        project,
        longitudinal_step_m=current.lm1_longitudinal_step_m,
        max_exhaustive_tandem_combinations=(current.lm1_max_exhaustive_tandem_combinations),
        **lm1_kwargs,
    )
    lm1_frequent = (
        lm1_search(
            project,
            factors=frequent_lm1_adjustments(eurocode_sls_factors),
            longitudinal_step_m=current.lm1_longitudinal_step_m,
            max_exhaustive_tandem_combinations=current.lm1_max_exhaustive_tandem_combinations,
            **lm1_kwargs,
        )
        if eurocode_sls_factors is not None
        and eurocode_sls_factors.frequent_components_differ else None
    )
    ha = run_ha_grillage_search(
        project,
        longitudinal_step_m=current.ha_longitudinal_step_m,
        max_exhaustive_kel_combinations=current.ha_max_exhaustive_kel_combinations,
        retain_all_cases=False,
    )
    hb = run_hb_grillage_search(
        project,
        units=current.hb_units,
        longitudinal_step_m=current.hb_longitudinal_step_m,
        transverse_step_m=current.hb_transverse_step_m,
        retain_all_cases=False,
    )
    ha_hb = run_ha_hb_combined_grillage_search(
        project,
        units=current.hb_units,
        hb_longitudinal_step_m=current.combined_hb_longitudinal_step_m,
        hb_transverse_step_m=current.combined_hb_transverse_step_m,
        ha_kel_step_m=current.combined_ha_kel_step_m,
        max_exhaustive_kel_combinations=(current.combined_max_exhaustive_kel_combinations),
        max_exhaustive_ha_assignments=(current.combined_max_exhaustive_ha_assignments),
        retain_all_cases=False,
    )
    return build_full_bridge_traffic_campaign(
        project,
        lm1=lm1,
        ha=ha,
        hb=hb,
        ha_hb=ha_hb,
        lm1_frequent=lm1_frequent,
    )


def build_permanent_component_suite(
    project: BridgeProject,
    *,
    longitudinal_divisions: int = 8,
) -> PermanentComponentSuite:
    """Build category-separated, stage-stiffness permanent response models."""

    all_segments = automatic_permanent_loads(project)
    stages = (
        PermanentActionStage.PRECAST_GIRDER,
        PermanentActionStage.DECK_CONSTRUCTION,
        PermanentActionStage.SUPERIMPOSED,
    )
    components: list[PermanentComponentVerification] = []
    next_load_case_id = 201
    girder_y = girder_y_positions_m(project.geometry)

    for stage in stages:
        base = build_full_bridge_stage_model(
            project,
            stage=stage,
            longitudinal_divisions=longitudinal_divisions,
        )
        for category in PermanentLoadCategory:
            segments = tuple(
                item for item in all_segments if item.stage is stage and item.category is category
            )
            if not segments:
                continue
            component_key = f"{stage.value}_{category.value}"
            load_case = build_girder_line_load_case(
                base,
                girder_y_m=girder_y,
                segments=segments,
                load_case_id=next_load_case_id,
                name=component_key,
            )
            model = replace(
                base,
                name=f"{project.name} - {component_key}",
                load_cases=(load_case,),
            )
            analysis = solve_vertical_grillage(model)
            package = build_staad_verification_package(
                model,
                analysis,
                provenance={
                    "repository": "RC-Single-Span-Bridge-Analysis-ANN",
                    "verification_domain": "cross_stage_permanent_component",
                    "component_key": component_key,
                    "stage": stage.value,
                    "permanent_category": category.value,
                    "combination_basis": (
                        "result component is superposed after analysis so its "
                        "load-time stiffness remains unchanged"
                    ),
                },
            )
            components.append(
                PermanentComponentVerification(
                    component_key=component_key,
                    stage=stage,
                    category=category,
                    segments=segments,
                    model=model,
                    analysis=analysis,
                    staad_package=package,
                )
            )
            next_load_case_id += 1

    if not components:
        raise ValueError("No automatic permanent components were available to package.")
    return PermanentComponentSuite(tuple(components))


def build_cross_stage_combination_rules(
    *,
    eurocode_sls_factors: EurocodeServiceabilityFactors,
    eurocode_uls_factors: EurocodeCombinationFactors | None = None,
    bs5400_permanent_factors: BS5400PermanentGammaFL | None = None,
) -> tuple[CrossStageCombinationRule, ...]:
    """Return auditable response-superposition factors for both code profiles."""

    ec_uls = eurocode_uls_factors or EurocodeCombinationFactors()
    all_categories = tuple(PermanentLoadCategory)

    def ec_permanent(value: float) -> dict[PermanentLoadCategory, float]:
        return {category: value for category in all_categories}

    bs_en_standard = "BS EN 1990:2002+A1:2005 / BS EN 1991-2:2003"
    rules: list[CrossStageCombinationRule] = [
        CrossStageCombinationRule(
            "ec_uls_persistent",
            bs_en_standard,
            "Persistent ULS",
            TrafficAction.LM1,
            ec_permanent(ec_uls.gamma_g_unfavourable),
            ec_uls.gamma_q_traffic,
        ),
        CrossStageCombinationRule(
            "ec_sls_characteristic",
            bs_en_standard,
            "Characteristic SLS",
            TrafficAction.LM1,
            ec_permanent(1.0),
            1.0,
        ),
        CrossStageCombinationRule(
            "ec_sls_frequent",
            bs_en_standard,
            "Frequent SLS",
            (
                TrafficAction.LM1_FREQUENT
                if eurocode_sls_factors.frequent_components_differ
                else TrafficAction.LM1
            ),
            ec_permanent(1.0),
            (
                1.0
                if eurocode_sls_factors.frequent_components_differ
                else eurocode_sls_factors.psi1_traffic
            ),
        ),
        CrossStageCombinationRule(
            "ec_sls_quasi_permanent",
            bs_en_standard,
            "Quasi-permanent SLS",
            TrafficAction.LM1,
            ec_permanent(1.0),
            eurocode_sls_factors.psi2_traffic,
        ),
    ]

    bs_permanent = bs5400_permanent_factors or BS5400PermanentGammaFL()
    action_map = {
        TrafficAction.HA: BS5400PrimaryTraffic.HA,
        TrafficAction.HB: BS5400PrimaryTraffic.HB,
        TrafficAction.HA_HB: BS5400PrimaryTraffic.HA_HB,
    }
    for action, traffic in action_map.items():
        for combination in (1, 2, 3):
            for limit_state in BS5400LimitState:
                named = bs_permanent.as_named_factors(limit_state)
                permanent = {
                    category: named[category.value]
                    for category in PermanentLoadCategory
                }
                rules.append(
                    CrossStageCombinationRule(
                        rule_id=(
                            f"bs_combination_{combination}_{limit_state.value}_{action.value}"
                        ),
                        standard="BS 5400:Part 2 / BD 37/01",
                        name=(
                            f"Combination {combination} {limit_state.value.upper()} "
                            f"({action.value})"
                        ),
                        traffic_action=action,
                        permanent_factors=permanent,
                        traffic_factor=primary_live_gamma_fl(
                            traffic=traffic,
                            combination=combination,
                            limit_state=limit_state,
                        ),
                    )
                )
    return tuple(rules)
