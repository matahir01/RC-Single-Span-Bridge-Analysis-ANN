from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rc_single_span.codes.bs5400.combinations import BS5400LimitState
from rc_single_span.codes.eurocode.combinations import EurocodeServiceabilityFactors
from rc_single_span.core.models import BridgeProject
from rc_single_span.design.project import BS5400DesignInputs, EC2DesignInputs
from rc_single_span.gui.design_adapter import GuiDesignInputs
from rc_single_span.verification.reference_runner import (
    ReferenceRunConfig,
    ReferenceRunResult,
    run_reference_project,
)


class GuiCodeProfile(str, Enum):
    BS_EN = "BS EN 1990 / 1991-2 / 1992-2"
    BS_5400 = "BS 5400 / BD 37"


@dataclass(frozen=True)
class GuiAnalysisSettings:
    code_profile: GuiCodeProfile = GuiCodeProfile.BS_EN
    elastic_modulus_mpa: float = 34000.0
    psi1_tandem: float = 0.75
    psi1_udl: float = 0.40
    psi2_traffic: float = 0.0
    lm1_step_m: float = 0.6
    retain_all_cases: bool = False
    hb_units: float = 45.0


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
    shear_passes: bool
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
        retain_all_cases=settings.retain_all_cases,
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
                shear_passes=bool(item.shear.web_crushing_passes),
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
                shear_passes=not item.shear.exceeds_maximum_shear,
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
) -> tuple[ReferenceRunResult, GuiAnalysisSummary]:
    """Run the verified deterministic bridge engine and build a GUI summary."""

    result = run_reference_project(
        project,
        config=_reference_config(settings),
        **_design_kwargs(settings, design_inputs),
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
        )

    if not rows:
        raise RuntimeError("The deterministic engine returned no girder result rows.")
    summary = GuiAnalysisSummary(
        code_profile=settings.code_profile,
        code_basis=basis,
        rows=rows,
        governing_moment=max(rows, key=lambda row: row.moment_knm),
        governing_shear=max(rows, key=lambda row: row.shear_kn),
        governing_torsion=max(rows, key=lambda row: row.torsion_knm),
        design_rows=design_rows,
        notes=notes,
    )
    return result, summary
