from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from rc_single_span.codes.bs5400.combinations import BS5400LimitState
from rc_single_span.codes.eurocode.combinations import EurocodeServiceabilityFactors
from rc_single_span.core.models import BridgeProject
from rc_single_span.core.progress import AnalysisControl
from rc_single_span.design.project import BS5400DesignInputs, EC2DesignInputs
from rc_single_span.gui.design_adapter import GuiDesignInputs
from rc_single_span.traffic.lm1_influence import run_lm1_influence_grillage_search
from rc_single_span.traffic.lm1_influence_convergence import _influence_refinement
from rc_single_span.verification.reference_runner import (
    ReferenceRunConfig,
    ReferenceRunResult,
    _with_elastic_modulus,
    run_reference_project,
)


class GuiCodeProfile(str, Enum):
    BS_EN = "BS EN 1990 / 1991-2 / 1992-2"
    BS_5400 = "BS 5400 / BD 37"


class GuiAccuracyMode(str, Enum):
    QUICK = "Quick"
    STANDARD = "Standard"
    FINAL = "Final Verification"
    CUSTOM = "Custom grid"


@dataclass(frozen=True)
class GuiAnalysisSettings:
    code_profile: GuiCodeProfile = GuiCodeProfile.BS_EN
    elastic_modulus_mpa: float = 34000.0
    psi1_tandem: float = 0.75
    psi1_udl: float = 0.40
    psi2_traffic: float = 0.0
    lm1_step_m: float = 0.6
    retain_all_cases: bool = False
    all_case_combined_deflection: bool = False
    hb_units: float = 45.0
    accuracy_mode: GuiAccuracyMode = GuiAccuracyMode.FINAL
    bs_ha_longitudinal_step_m: float = 1.0
    bs_hb_longitudinal_step_m: float = 1.0
    bs_hb_transverse_step_m: float = 0.5
    bs_combined_hb_longitudinal_step_m: float = 2.0
    bs_combined_hb_transverse_step_m: float = 1.0
    bs_combined_ha_kel_step_m: float = 2.0


@dataclass(frozen=True)
class GuiResultRow:
    girder: int
    moment_knm: float
    shear_kn: float
    torsion_knm: float
    source: str


@dataclass(frozen=True)
class GuiDesignRow:
    girder: int
    flexure_utilization: float | None
    flexure_passes: bool | None
    shear_demand_kn: float
    shear_max_resistance_kn: float
    shear_maximum_passes: bool
    required_shear_steel_mm2_per_m: float
    crack_width_mm: float
    crack_limit_mm: float
    crack_passes: bool
    deflection_mm: float
    deflection_limit_mm: float | None
    deflection_passes: bool | None


@dataclass(frozen=True)
class GuiAnalysisSummary:
    code_profile: GuiCodeProfile
    code_basis: str
    rows: tuple[GuiResultRow, ...]
    governing_moment: GuiResultRow
    governing_shear: GuiResultRow
    governing_torsion: GuiResultRow
    design_rows: tuple[GuiDesignRow, ...]
    notes: tuple[str, ...]
    actual_lm1_step_m: float | None = None


def _reference_config(settings: GuiAnalysisSettings) -> ReferenceRunConfig:
    return ReferenceRunConfig(
        elastic_modulus_mpa=settings.elastic_modulus_mpa,
        eurocode_sls_factors=EurocodeServiceabilityFactors(
            psi1_traffic=settings.psi1_tandem,
            psi2_traffic=settings.psi2_traffic,
            psi1_udl_traffic=settings.psi1_udl,
        ),
        lm1_longitudinal_step_m=settings.lm1_step_m,
        hb_units=settings.hb_units,
        bs_ha_longitudinal_step_m=settings.bs_ha_longitudinal_step_m,
        bs_hb_longitudinal_step_m=settings.bs_hb_longitudinal_step_m,
        bs_hb_transverse_step_m=settings.bs_hb_transverse_step_m,
        bs_combined_hb_longitudinal_step_m=settings.bs_combined_hb_longitudinal_step_m,
        bs_combined_hb_transverse_step_m=settings.bs_combined_hb_transverse_step_m,
        bs_combined_ha_kel_step_m=settings.bs_combined_ha_kel_step_m,
        retain_all_cases=settings.retain_all_cases,
        evaluate_all_case_combined_deflection=settings.all_case_combined_deflection,
        lm1_udl_influence_surface=True,
    )


def _design_kwargs(
    settings: GuiAnalysisSettings,
    design_inputs: GuiDesignInputs | None,
) -> dict[str, object]:
    if design_inputs is None:
        return {}
    resolved = design_inputs.for_profile(settings.code_profile.value)
    if resolved is None:
        return {}
    if isinstance(resolved, EC2DesignInputs):
        return {"ec2_design_inputs": resolved}
    if isinstance(resolved, BS5400DesignInputs):
        return {"bs5400_design_inputs": resolved}
    raise TypeError(f"Unsupported GUI design input type: {type(resolved).__name__}")


def _ec_design_rows(result: ReferenceRunResult) -> tuple[GuiDesignRow, ...]:
    if result.eurocode_design is None:
        return ()
    rows: list[GuiDesignRow] = []
    for item in result.eurocode_design:
        flexure = item.flexure
        flexure_utilization = None if flexure is None else float(flexure.utilization)
        flexure_passes = (
            None
            if flexure is None
            else bool(
                flexure.utilization <= 1.0 + 1.0e-12
                and flexure.ductility_passes is not False
            )
        )
        rows.append(
            GuiDesignRow(
                girder=item.girder_index,
                flexure_utilization=flexure_utilization,
                flexure_passes=flexure_passes,
                shear_demand_kn=float(item.shear.design_shear_kn),
                shear_max_resistance_kn=float(item.shear.vrdmax_kn),
                shear_maximum_passes=bool(item.shear.web_crushing_passes),
                required_shear_steel_mm2_per_m=float(
                    item.shear.required_asw_per_s_mm2_per_m
                ),
                crack_width_mm=float(item.cracking.crack_width_mm),
                crack_limit_mm=float(item.cracking.crack_limit_mm),
                crack_passes=bool(item.cracking.utilization <= 1.0 + 1.0e-12),
                deflection_mm=float(item.deflection.total_deflection_mm),
                deflection_limit_mm=item.deflection.allowable_deflection_mm,
                deflection_passes=item.deflection.passes,
            )
        )
    return tuple(rows)


def _bs_design_rows(result: ReferenceRunResult) -> tuple[GuiDesignRow, ...]:
    if result.bs5400_design is None:
        return ()
    rows: list[GuiDesignRow] = []
    for item in result.bs5400_design:
        flexure = item.flexure
        flexure_utilization = None if flexure is None else float(flexure.utilization)
        flexure_passes = (
            None
            if flexure is None
            else bool(flexure.utilization <= 1.0 + 1.0e-12)
        )
        rows.append(
            GuiDesignRow(
                girder=item.girder_index,
                flexure_utilization=flexure_utilization,
                flexure_passes=flexure_passes,
                shear_demand_kn=float(item.shear.design_shear_kn),
                shear_max_resistance_kn=float(item.shear.maximum_resistance_kn),
                shear_maximum_passes=not item.shear.exceeds_maximum_shear,
                required_shear_steel_mm2_per_m=float(
                    item.shear.governing_asv_per_s_mm2_per_m
                ),
                crack_width_mm=float(item.cracking.crack_width_mm),
                crack_limit_mm=float(item.cracking.allowable_crack_width_mm),
                crack_passes=bool(item.cracking.passes),
                deflection_mm=float(item.deflection.total_deflection_mm),
                deflection_limit_mm=item.deflection.allowable_deflection_mm,
                deflection_passes=item.deflection.passes,
            )
        )
    return tuple(rows)


def run_gui_analysis(
    project: BridgeProject,
    settings: GuiAnalysisSettings,
    design_inputs: GuiDesignInputs | None = None,
    *, control: AnalysisControl | None = None,
) -> tuple[ReferenceRunResult, GuiAnalysisSummary]:
    """Run the verified deterministic bridge engine and build a GUI summary."""

    route = "bs_en" if settings.code_profile is GuiCodeProfile.BS_EN else "bs5400"
    # Validate even direct API callers before starting the expensive traffic search.
    config = _reference_config(settings)
    if settings.all_case_combined_deflection and not settings.retain_all_cases:
        raise ValueError("All-case combined deflection requires retained traffic cases.")
    if settings.all_case_combined_deflection and route == "bs_en":
        raise ValueError("GUI all-case combined deflection is available only on the BS 5400 route.")
    audit_notes = []
    coarse = None
    if route == "bs_en" and settings.accuracy_mode in {
        GuiAccuracyMode.STANDARD, GuiAccuracyMode.FINAL,
    }:
        initial = 2.4 if settings.accuracy_mode is GuiAccuracyMode.STANDARD else 1.2
        coarse = run_lm1_influence_grillage_search(
            _with_elastic_modulus(project, settings.elastic_modulus_mpa),
            longitudinal_step_m=initial,
            control=control,
            phase=f"LM1 convergence {initial:g} m",
        )
        if not coarse.tandem_combinations_exhaustive:
            raise RuntimeError("LM1 convergence requires exhaustive tandem placements.")

    step_m = (
        3.0 if settings.accuracy_mode is GuiAccuracyMode.QUICK else
        1.2 if settings.accuracy_mode is GuiAccuracyMode.STANDARD else
        0.6 if settings.accuracy_mode is GuiAccuracyMode.FINAL else
        settings.lm1_step_m
    ) if route == "bs_en" else settings.lm1_step_m

    while True:
        result = run_reference_project(
            project,
            config=replace(config, lm1_longitudinal_step_m=step_m),
            code_route=route,
            control=control,
            **_design_kwargs(settings, design_inputs),
        )
        if coarse is None:
            break
        fine = result.lm1
        if fine is None or not fine.tandem_combinations_exhaustive:
            raise RuntimeError("LM1 convergence requires exhaustive tandem placements.")
        comparison = _influence_refinement(coarse, fine)
        audit_notes.append(
            f"LM1 {comparison.coarse_step_m:g} → {comparison.fine_step_m:g} m: "
            f"maximum envelope change {comparison.maximum_relative_change:.3%} "
            f"({comparison.governing_quantity}, girder {comparison.girder_index}); "
            "adopted criterion 5%."
        )
        if comparison.maximum_relative_change <= 0.05:
            break
        if settings.accuracy_mode is GuiAccuracyMode.STANDARD and step_m == 1.2:
            coarse, step_m = fine, 0.6
            continue
        raise RuntimeError(
            f"LM1 {comparison.coarse_step_m:g} → {step_m:g} m changed by "
            f"{comparison.maximum_relative_change:.3%}, above the 5% criterion. "
            "No converged result was published; refine and recheck the grid."
        )
    if settings.code_profile is GuiCodeProfile.BS_EN:
        rows = tuple(
            GuiResultRow(
                girder=item.girder_index,
                moment_knm=float(item.combinations.persistent_uls.effects.moment_knm),
                shear_kn=float(item.combinations.persistent_uls.effects.shear_kn),
                torsion_knm=float(item.combinations.persistent_uls.effects.torsion_knm),
                source="BS EN persistent ULS",
            )
            for item in result.eurocode_combinations
        )
        design_rows = _ec_design_rows(result)
        basis = "BS EN 1990:2002+A1:2005; BS EN 1991-2:2003; BS EN 1992-2:2005"
        notes = (
            "LM1 uses the verified complete-tandem/adverse-UDL search.",
            "Design results use only the explicit project inputs supplied to the GUI.",
            (
                "The shear PASS/CHECK status concerns maximum web resistance only. "
                "Required link steel is reported, but provided links are not an input or a pass check."
            ),
            f"Analysis mode: {settings.accuracy_mode.value}; final LM1 step {step_m:g} m."
            + (" No grid convergence claim." if coarse is None else ""),
            *audit_notes,
        )
    else:
        rows_list: list[GuiResultRow] = []
        for item in result.bs5400_combinations:
            uls = tuple(
                governing
                for governing in item.governing
                if governing.limit_state is BS5400LimitState.ULS
            )
            if not uls:
                continue
            moment_case = max(uls, key=lambda case: case.effects.moment_knm)
            shear_case = max(uls, key=lambda case: case.effects.shear_kn)
            torsion_case = max(uls, key=lambda case: case.effects.torsion_knm)
            source = (
                "BS 5400 ULS envelope: "
                f"M=C{moment_case.combination}, V=C{shear_case.combination}, "
                f"T=C{torsion_case.combination}"
            )
            rows_list.append(
                GuiResultRow(
                    girder=item.girder_index,
                    moment_knm=float(moment_case.effects.moment_knm),
                    shear_kn=float(shear_case.effects.shear_kn),
                    torsion_knm=float(torsion_case.effects.torsion_knm),
                    source=source,
                )
            )
        rows = tuple(rows_list)
        design_rows = _bs_design_rows(result)
        basis = "BS 5400 / BD 37 legacy highway bridge route"
        notes = (
            "HA, HB and HA+HB combinations 1-3 are generated from the native vertical grillage.",
            "Combinations 4-5 require explicit secondary-action/bearing-friction structural effects and provenance.",
            (
                "The shear PASS/CHECK status concerns maximum web resistance only. "
                "Required link steel is reported, but provided links are not an input or a pass check."
            ),
            (
                "BS traffic placement-grid convergence is unverified for this run. In the "
                "support-anchored 15 m reference audit, default-to-half changed the maximum "
                "girder envelope by 6.809% (torsion, girder 5) and the station shape by 26.510% "
                "(girder 7, x=7.2 m). Half-to-fine changed the envelope by 1.894%, but station "
                "shape by 26.938% (girder 7, x=7.7 m). Check the project grid before relying "
                "on its traffic envelope."
            ),
            (
                "This run's BS steps (m): HA longitudinal "
                f"{config.bs_ha_longitudinal_step_m:g}; HB longitudinal/transverse "
                f"{config.bs_hb_longitudinal_step_m:g}/{config.bs_hb_transverse_step_m:g}; "
                "HA+HB HB longitudinal/transverse/KEL "
                f"{config.bs_combined_hb_longitudinal_step_m:g}/"
                f"{config.bs_combined_hb_transverse_step_m:g}/"
                f"{config.bs_combined_ha_kel_step_m:g}."
            ),
            (
                "All traffic cases were retained for review."
                if settings.retain_all_cases else
                "Only governing physical traffic cases were retained."
            ),
            (
                "Exhaustive combined permanent+traffic deflection was evaluated "
                "across every retained case."
                if settings.all_case_combined_deflection else
                "Exhaustive combined permanent+traffic deflection was not evaluated; "
                "the design deflection uses the engine's separate traffic envelope "
                "and permanent response."
            ),
        )

    if not rows:
        raise RuntimeError("The deterministic engine returned no girder result rows.")
    if control is not None:
        control.report("Preparing summary")
    summary = GuiAnalysisSummary(
        code_profile=settings.code_profile,
        code_basis=basis,
        rows=rows,
        governing_moment=max(rows, key=lambda row: row.moment_knm),
        governing_shear=max(rows, key=lambda row: row.shear_kn),
        governing_torsion=max(rows, key=lambda row: row.torsion_knm),
        design_rows=design_rows,
        notes=notes,
        actual_lm1_step_m=step_m if route == "bs_en" else None,
    )
    return result, summary
