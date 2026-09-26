from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rc_single_span.codes.bs5400.combinations import BS5400LimitState
from rc_single_span.codes.eurocode.combinations import EurocodeServiceabilityFactors
from rc_single_span.core.models import BridgeProject
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
class GuiAnalysisSummary:
    code_profile: GuiCodeProfile
    code_basis: str
    rows: tuple[GuiResultRow, ...]
    governing_moment: GuiResultRow
    governing_shear: GuiResultRow
    governing_torsion: GuiResultRow
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


def run_gui_analysis(
    project: BridgeProject,
    settings: GuiAnalysisSettings,
) -> tuple[ReferenceRunResult, GuiAnalysisSummary]:
    """Run the verified deterministic bridge engine and build a GUI summary."""

    result = run_reference_project(project, config=_reference_config(settings))
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
        basis = "BS EN 1990:2002+A1:2005; BS EN 1991-2:2003; BS EN 1992-2:2005"
        notes = (
            "LM1 uses the verified complete-tandem/adverse-UDL search.",
            "Design/detailing PASS/CHECK results require the corresponding explicit project inputs.",
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
        notes=notes,
    )
    return result, summary
