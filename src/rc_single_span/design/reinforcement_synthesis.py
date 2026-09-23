from __future__ import annotations

from dataclasses import dataclass

from rc_single_span.analysis.sections import ConcreteLayer
from rc_single_span.design.bs5400 import (
    check_crack_width_bs5400,
    check_layered_flexure_bs5400,
)
from rc_single_span.design.detailing import (
    LongitudinalBarArrangement,
    generate_longitudinal_bar_arrangements,
    longitudinal_cage_effective_depth_m,
)
from rc_single_span.design.eurocode import (
    check_crack_width_ec2,
    check_layered_flexure_ec2,
)


@dataclass(frozen=True)
class SteelDemandComponent:
    name: str
    required_area_mm2: float | None
    status: str


@dataclass(frozen=True)
class LongitudinalCandidateAssessment:
    arrangement: LongitudinalBarArrangement
    effective_depth_m: float
    uls_flexure_passes: bool
    uls_utilization: float | None
    crack_passes: bool | None
    crack_width_mm: float | None
    crack_utilization: float | None
    maximum_steel_passes: bool
    all_current_checks_pass: bool
    notes: tuple[str, ...]


@dataclass(frozen=True)
class LongitudinalSynthesisResult:
    demands: tuple[SteelDemandComponent, ...]
    base_required_area_mm2: float
    candidates_evaluated: int
    passing_candidates: int
    selected: LongitudinalCandidateAssessment | None
    final_design_ready: bool
    outstanding_checks: tuple[str, ...]
    selection_basis: str


def _candidate_rank(
    candidate: LongitudinalCandidateAssessment,
) -> tuple[int, int, float, float]:
    """Transparent constructability ranking for candidates that already pass checks."""

    arrangement = candidate.arrangement
    return (
        arrangement.layer_count,
        arrangement.bar_count,
        arrangement.provided_area_mm2,
        arrangement.bar_diameter_mm,
    )


def synthesize_ec2_longitudinal_reinforcement(
    *,
    layers: tuple[ConcreteLayer, ...],
    total_depth_m: float,
    uls_moment_knm: float,
    sls_moment_knm: float,
    required_uls_area_mm2: float,
    minimum_area_mm2: float,
    maximum_area_mm2: float,
    fck_mpa: float,
    fyk_mpa: float,
    maximum_neutral_axis_ratio: float,
    cover_mm: float,
    link_diameter_mm: float,
    web_width_mm: float,
    minimum_clear_spacing_mm: float,
    available_diameters_mm: tuple[float, ...],
    maximum_layers: int,
    preferred_vertical_clear_spacing_mm: float | None,
    es_mpa: float,
    ecm_mpa: float,
    fct_eff_mpa: float,
    crack_limit_mm: float,
    deflection_passes: bool | None,
) -> LongitudinalSynthesisResult:
    if min(required_uls_area_mm2, minimum_area_mm2, maximum_area_mm2) <= 0.0:
        raise ValueError("EC2 steel-demand limits must be positive.")

    base_required = max(required_uls_area_mm2, minimum_area_mm2)
    arrangements = generate_longitudinal_bar_arrangements(
        minimum_area_mm2=base_required,
        web_width_mm=web_width_mm,
        cover_mm=cover_mm,
        link_diameter_mm=link_diameter_mm,
        minimum_clear_spacing_mm=minimum_clear_spacing_mm,
        available_diameters_mm=available_diameters_mm,
        maximum_layers=maximum_layers,
        preferred_vertical_clear_spacing_mm=preferred_vertical_clear_spacing_mm,
        diameter_governs_clear_spacing=True,
    )

    assessments: list[LongitudinalCandidateAssessment] = []
    for arrangement in arrangements:
        effective_depth = longitudinal_cage_effective_depth_m(
            arrangement,
            section_total_depth_mm=total_depth_m * 1000.0,
            cover_mm=cover_mm,
            link_diameter_mm=link_diameter_mm,
        )

        flexure_passes = False
        flexure_utilization: float | None = None
        crack_passes: bool | None = None
        crack_width: float | None = None
        crack_utilization: float | None = None
        notes: list[str] = []

        try:
            flexure = check_layered_flexure_ec2(
                med_knm=uls_moment_knm,
                layers=layers,
                effective_depth_m=effective_depth,
                steel_area_mm2=arrangement.provided_area_mm2,
                fck_mpa=fck_mpa,
                fyk_mpa=fyk_mpa,
                maximum_neutral_axis_ratio=maximum_neutral_axis_ratio,
            )
            flexure_utilization = flexure.utilization
            flexure_passes = (
                flexure.g_flexure_knm >= -1.0e-9
                and flexure.ductility_passes is not False
            )
        except ValueError as exc:
            notes.append(f"ULS flexure rejected: {exc}")

        if flexure_passes:
            bar_spacing = (
                arrangement.bar_diameter_mm
                + arrangement.clear_horizontal_spacing_mm
            )
            try:
                cracking = check_crack_width_ec2(
                    layers=layers,
                    total_depth_m=total_depth_m,
                    steel_area_mm2=arrangement.provided_area_mm2,
                    steel_depth_m=effective_depth,
                    bar_diameter_mm=arrangement.bar_diameter_mm,
                    bar_spacing_mm=bar_spacing,
                    cover_mm=cover_mm,
                    service_moment_knm=sls_moment_knm,
                    es_mpa=es_mpa,
                    ecm_mpa=ecm_mpa,
                    fct_eff_mpa=fct_eff_mpa,
                    crack_limit_mm=crack_limit_mm,
                )
                crack_width = cracking.crack_width_mm
                crack_utilization = cracking.utilization
                crack_passes = cracking.g_crack_mm >= -1.0e-12
            except ValueError as exc:
                crack_passes = False
                notes.append(f"SLS crack check rejected: {exc}")

        maximum_passes = (
            arrangement.provided_area_mm2 <= maximum_area_mm2 + 1.0e-9
        )
        all_current = (
            flexure_passes
            and crack_passes is True
            and maximum_passes
            and deflection_passes is not False
        )
        assessments.append(
            LongitudinalCandidateAssessment(
                arrangement=arrangement,
                effective_depth_m=effective_depth,
                uls_flexure_passes=flexure_passes,
                uls_utilization=flexure_utilization,
                crack_passes=crack_passes,
                crack_width_mm=crack_width,
                crack_utilization=crack_utilization,
                maximum_steel_passes=maximum_passes,
                all_current_checks_pass=all_current,
                notes=tuple(notes),
            )
        )

    passing = [item for item in assessments if item.all_current_checks_pass]
    selected = min(passing, key=_candidate_rank) if passing else None

    outstanding = (
        "advanced Stage D fatigue result",
        "advanced Stage D construction-stage steel-stress result",
        "advanced Stage D support/termination and lap-splice result",
        "advanced Stage D local bearing/end-zone congestion result",
    )
    demands = (
        SteelDemandComponent(
            "ULS flexure",
            required_uls_area_mm2,
            "Calculated from the layered EC2 resistance model.",
        ),
        SteelDemandComponent(
            "EC2 minimum tension steel",
            minimum_area_mm2,
            "Calculated from the configured EC2 detailing limits.",
        ),
        SteelDemandComponent(
            "SLS crack control",
            None,
            "Enforced by direct candidate-cage crack-width recheck using the actual bar diameter, spacing and cage centroid.",
        ),
        SteelDemandComponent(
            "deflection",
            None,
            (
                "Current deflection response passes."
                if deflection_passes is True
                else "Current deflection response fails."
                if deflection_passes is False
                else "No explicit deflection limit was supplied."
            ),
        ),
        SteelDemandComponent(
            "fatigue",
            None,
            "Implemented in advanced Stage D; this base synthesis remains preliminary until a project-specific fatigue vehicle/distribution/resistance result is supplied.",
        ),
        SteelDemandComponent(
            "construction stage",
            None,
            "Implemented in advanced Stage D using cumulative load-time permanent actions and stage-specific participating concrete; project-specific allowable steel stress is still required.",
        ),
    )
    return LongitudinalSynthesisResult(
        demands=demands,
        base_required_area_mm2=base_required,
        candidates_evaluated=len(assessments),
        passing_candidates=len(passing),
        selected=selected,
        final_design_ready=False,
        outstanding_checks=outstanding,
        selection_basis=(
            "Candidates must first pass current ULS flexure, SLS crack control, "
            "maximum-steel and configured deflection checks using their actual cage centroid. "
            "Passing cages are ranked by fewer layers, then fewer bars, then lower steel area. "
            "Selection remains preliminary until the listed outstanding bridge checks are implemented."
        ),
    )


def synthesize_bs5400_longitudinal_reinforcement(
    *,
    layers: tuple[ConcreteLayer, ...],
    total_depth_m: float,
    uls_moment_knm: float,
    permanent_sls_moment_knm: float,
    live_sls_moment_knm: float,
    required_uls_area_mm2: float,
    minimum_area_mm2: float,
    maximum_area_mm2: float,
    fcu_mpa: float,
    fy_mpa: float,
    cover_mm: float,
    link_diameter_mm: float,
    web_width_mm: float,
    minimum_clear_spacing_mm: float,
    maximum_tension_bar_spacing_mm: float,
    available_diameters_mm: tuple[float, ...],
    maximum_layers: int,
    preferred_vertical_clear_spacing_mm: float | None,
    es_mpa: float,
    ec_modified_mpa: float,
    tension_zone_width_m: float,
    crack_point_depth_mm: float,
    allowable_crack_width_mm: float,
    deflection_passes: bool | None,
) -> LongitudinalSynthesisResult:
    if min(required_uls_area_mm2, minimum_area_mm2, maximum_area_mm2) <= 0.0:
        raise ValueError("BS 5400 steel-demand limits must be positive.")

    base_required = max(required_uls_area_mm2, minimum_area_mm2)
    arrangements = generate_longitudinal_bar_arrangements(
        minimum_area_mm2=base_required,
        web_width_mm=web_width_mm,
        cover_mm=cover_mm,
        link_diameter_mm=link_diameter_mm,
        minimum_clear_spacing_mm=minimum_clear_spacing_mm,
        available_diameters_mm=available_diameters_mm,
        maximum_layers=maximum_layers,
        preferred_vertical_clear_spacing_mm=preferred_vertical_clear_spacing_mm,
        diameter_governs_clear_spacing=False,
    )

    assessments: list[LongitudinalCandidateAssessment] = []
    for arrangement in arrangements:
        effective_depth = longitudinal_cage_effective_depth_m(
            arrangement,
            section_total_depth_mm=total_depth_m * 1000.0,
            cover_mm=cover_mm,
            link_diameter_mm=link_diameter_mm,
        )
        flexure_passes = False
        flexure_utilization: float | None = None
        crack_passes: bool | None = None
        crack_width: float | None = None
        crack_utilization: float | None = None
        notes: list[str] = []

        try:
            flexure = check_layered_flexure_bs5400(
                med_knm=uls_moment_knm,
                layers=layers,
                effective_depth_m=effective_depth,
                steel_area_mm2=arrangement.provided_area_mm2,
                fcu_mpa=fcu_mpa,
                fy_mpa=fy_mpa,
            )
            flexure_utilization = flexure.utilization
            flexure_passes = flexure.g_flexure_knm >= -1.0e-9
        except ValueError as exc:
            notes.append(f"ULS flexure rejected: {exc}")

        centre_spacing = (
            arrangement.bar_diameter_mm
            + arrangement.clear_horizontal_spacing_mm
        )
        spacing_passes = (
            centre_spacing <= maximum_tension_bar_spacing_mm + 1.0e-9
        )
        if not spacing_passes:
            notes.append("BS 5400 tension-bar spacing limit exceeded.")

        if flexure_passes and spacing_passes:
            try:
                cracking = check_crack_width_bs5400(
                    layers=layers,
                    total_depth_m=total_depth_m,
                    steel_area_mm2=arrangement.provided_area_mm2,
                    steel_depth_m=effective_depth,
                    permanent_moment_knm=permanent_sls_moment_knm,
                    live_moment_knm=live_sls_moment_knm,
                    es_mpa=es_mpa,
                    ec_modified_mpa=ec_modified_mpa,
                    tension_zone_width_m=tension_zone_width_m,
                    crack_point_depth_mm=crack_point_depth_mm,
                    nominal_cover_mm=cover_mm,
                    bar_spacing_mm=centre_spacing,
                    bar_diameter_mm=arrangement.bar_diameter_mm,
                    allowable_crack_width_mm=allowable_crack_width_mm,
                )
                crack_width = cracking.crack_width_mm
                crack_utilization = cracking.utilization
                crack_passes = cracking.passes
            except ValueError as exc:
                crack_passes = False
                notes.append(f"SLS crack check rejected: {exc}")
        elif not spacing_passes:
            crack_passes = False

        maximum_passes = (
            arrangement.provided_area_mm2 <= maximum_area_mm2 + 1.0e-9
        )
        all_current = (
            flexure_passes
            and crack_passes is True
            and maximum_passes
            and deflection_passes is not False
        )
        assessments.append(
            LongitudinalCandidateAssessment(
                arrangement=arrangement,
                effective_depth_m=effective_depth,
                uls_flexure_passes=flexure_passes,
                uls_utilization=flexure_utilization,
                crack_passes=crack_passes,
                crack_width_mm=crack_width,
                crack_utilization=crack_utilization,
                maximum_steel_passes=maximum_passes,
                all_current_checks_pass=all_current,
                notes=tuple(notes),
            )
        )

    passing = [item for item in assessments if item.all_current_checks_pass]
    selected = min(passing, key=_candidate_rank) if passing else None

    outstanding = (
        "advanced Stage D fatigue result",
        "advanced Stage D construction-stage steel-stress result",
        "advanced Stage D support/termination and lap-splice result",
        "side-face reinforcement integration into the final drawing cage",
        "advanced Stage D local bearing/end-zone congestion result",
    )
    demands = (
        SteelDemandComponent(
            "ULS flexure",
            required_uls_area_mm2,
            "Calculated from the layered BS 5400 resistance model.",
        ),
        SteelDemandComponent(
            "BS 5400 minimum main steel",
            minimum_area_mm2,
            "Calculated from the configured BS 5400 detailing limits.",
        ),
        SteelDemandComponent(
            "SLS crack control",
            None,
            "Enforced by direct candidate-cage crack-width recheck using actual bar diameter, spacing and cage centroid.",
        ),
        SteelDemandComponent(
            "deflection",
            None,
            (
                "Current deflection response passes."
                if deflection_passes is True
                else "Current deflection response fails."
                if deflection_passes is False
                else "No explicit deflection limit was supplied."
            ),
        ),
        SteelDemandComponent(
            "fatigue",
            None,
            "Implemented in advanced Stage D; BS fatigue still requires an explicit verified fatigue vehicle/model and resistance basis.",
        ),
        SteelDemandComponent(
            "construction stage",
            None,
            "Implemented in advanced Stage D using cumulative load-time permanent actions and stage-specific participating concrete; project-specific allowable steel stress is still required.",
        ),
    )
    return LongitudinalSynthesisResult(
        demands=demands,
        base_required_area_mm2=base_required,
        candidates_evaluated=len(assessments),
        passing_candidates=len(passing),
        selected=selected,
        final_design_ready=False,
        outstanding_checks=outstanding,
        selection_basis=(
            "Candidates must first pass current ULS flexure, BS tension-bar spacing, "
            "SLS crack control, maximum-steel and configured deflection checks using "
            "their actual cage centroid. Passing cages are ranked by fewer layers, "
            "then fewer bars, then lower steel area. Selection remains preliminary "
            "until the listed outstanding bridge checks are implemented."
        ),
    )
