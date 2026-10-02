"""Calculation summary generated from the completed engine run snapshot."""

from __future__ import annotations

from datetime import UTC, datetime
from html import escape

from rc_single_span.gui.design_adapter import GuiDesignInputs
from rc_single_span.gui.engine_adapter import (
    GuiAnalysisSettings,
    GuiAnalysisSummary,
    GuiCodeProfile,
)
from rc_single_span.gui.project_state import GuiProjectState
from rc_single_span.gui.report_sheets import analysis_sheets, design_sheets, row, sheet
from rc_single_span.verification.reference_runner import ReferenceRunResult


def _cell(value: object) -> str:
    return escape(str(value))


def _status(value: bool | None) -> str:
    if value is None:
        return "Not assessed"
    return "Pass" if value else "Check"


def _optional_number(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def render_calculation_report(
    state: GuiProjectState,
    settings: GuiAnalysisSettings,
    design: GuiDesignInputs,
    summary: GuiAnalysisSummary,
    *,
    result: ReferenceRunResult | None = None,
    generated_at: datetime | None = None,
) -> str:
    """Render only the completed run snapshot, never the currently edited form."""

    if not summary.rows or settings.code_profile is not summary.code_profile:
        raise ValueError("Report requires a completed analysis for the selected code profile.")
    if result is not None:
        if (result.project.name != state.name or
                len(result.construction.cumulative_by_girder) != len(summary.rows)):
            raise ValueError("Report project does not match the completed engine result.")
        if (settings.code_profile is GuiCodeProfile.BS_EN) != (result.lm1 is not None):
            raise ValueError("Report code route does not match the completed engine result.")
    generated_at = generated_at or datetime.now(UTC)
    effects = "".join(
        "<tr>"
        f"<td>{row.girder}</td><td>{row.moment_knm:.3f}</td>"
        f"<td>{row.shear_kn:.3f}</td><td>{row.torsion_knm:.3f}</td>"
        f"<td>{_cell(row.source)}</td></tr>"
        for row in summary.rows
    )
    design_rows = "".join(
        "<tr>"
        f"<td>{row.girder}</td>"
        f"<td>{_optional_number(row.flexure_utilization)}</td>"
        f"<td>{_status(row.flexure_passes)}</td>"
        f"<td>{row.shear_demand_kn:.2f} / {row.shear_max_resistance_kn:.2f}</td>"
        f"<td>{_status(row.shear_maximum_passes)}</td>"
        f"<td>{row.crack_width_mm:.3f} / {row.crack_limit_mm:.3f}</td>"
        f"<td>{_status(row.crack_passes)}</td>"
        f"<td>{row.deflection_mm:.3f} / {_optional_number(row.deflection_limit_mm)}</td>"
        f"<td>{_status(row.deflection_passes)}</td></tr>"
        for row in summary.design_rows
    )
    if not design_rows:
        design_rows = "<tr><td colspan='9'>Code-specific design checks were not run.</td></tr>"
    notes = "".join(f"<li>{_cell(note)}</li>" for note in summary.notes)
    criterion = (
        f"{design.deflection_limit_mm:.3f} mm — {_cell(design.deflection_limit_basis)}"
        if design.deflection_limit_mm is not None and design.deflection_limit_basis
        else "Not provided; deflection pass/fail is not assessed."
    )
    traffic = (
        f"LM1 search step {(summary.actual_lm1_step_m or settings.lm1_step_m):.3f} m; "
        f"ψ1 TS/UDL {settings.psi1_tandem:.2f}/{settings.psi1_udl:.2f}; "
        f"ψ2 {settings.psi2_traffic:.2f}"
        if summary.code_profile.value.startswith("BS EN")
        else f"HB {settings.hb_units:.1f} units"
    )
    input_rows = "".join(
        f"<tr><td>{_cell(group)}</td><td>{_cell(key)}</td><td>{_cell(value)}</td></tr>"
        for group, values in (
            ("Project", state.as_dict()),
            ("Analysis", {
                "code_profile": settings.code_profile.value,
                "psi1_tandem": settings.psi1_tandem,
                "psi1_udl": settings.psi1_udl,
                "psi2_traffic": settings.psi2_traffic,
                "lm1_step_m": settings.lm1_step_m,
                "accuracy_mode": settings.accuracy_mode.value,
                "actual_lm1_step_m": summary.actual_lm1_step_m,
                "hb_units": settings.hb_units,
                "bs_ha_longitudinal_step_m": settings.bs_ha_longitudinal_step_m,
                "bs_hb_longitudinal_step_m": settings.bs_hb_longitudinal_step_m,
                "bs_hb_transverse_step_m": settings.bs_hb_transverse_step_m,
                "bs_combined_hb_longitudinal_step_m": settings.bs_combined_hb_longitudinal_step_m,
                "bs_combined_hb_transverse_step_m": settings.bs_combined_hb_transverse_step_m,
                "bs_combined_ha_kel_step_m": settings.bs_combined_ha_kel_step_m,
                "retain_all_cases": settings.retain_all_cases,
                "all_case_combined_deflection": settings.all_case_combined_deflection,
            }),
            ("Design", design.__dict__),
        )
        for key, value in values.items()
    )
    calculations = (
        analysis_sheets(result, summary) + design_sheets(result, settings, design)
        if result is not None else sheet(2, "Detailed engine record unavailable", state.name, [
            row("Result", "The completed engine object was not supplied. Equations, "
                "case IDs and diagrams cannot be generated from this summary.", "Incomplete")])
    )
    provenance = sheet(4 + len(summary.rows), "Provenance and limits", state.name, [
        row("Engine source", "src/rc_single_span/analysis, traffic, codes, design "
            "and verification/reference_runner.py. The source evidence register "
            "is docs/RESEARCH_EVIDENCE_REGISTER.md; these sheets report the "
            "implemented calculation, not every code provision.", "Traceable"),
        row("Scope", f"<ul>{notes}</ul>Software verification is separate from "
            "independent approval of a real bridge.", "Review required"),
    ])
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
body {{ font-family: Arial, sans-serif; color: #24344a; font-size: 9pt; }}
h1 {{ color: #193653; font-size: 19pt; }}
h2 {{ color: #245b85; font-size: 12pt; margin-top: 16pt; }}
table {{ border-collapse: collapse; width: 100%; margin: 8pt 0; }}
th, td {{ border: 1px solid #bfccd6; padding: 4pt; text-align: left; }}
th {{ background: #e9f1f6; }}
.notice {{ border: 1px solid #b79b58; background: #fff9e7; padding: 8pt; }}
.sheet {{ page-break-before: always; }}
.sheet-head td {{ width: 50%; }}
.calculations th:first-child {{ width: 18%; }}
.calculations th:last-child {{ width: 15%; }}
.calculations tr {{ page-break-inside: avoid; }}
</style></head><body>
<h1>RC Single-Span Bridge — Analysis &amp; Design Calculation Sheets</h1>
<p>Project: {_cell(state.name)}<br>Generated: {_cell(generated_at.isoformat(timespec="seconds"))}
<br>Code basis: {_cell(summary.code_basis)}</p>
<p class="notice">Software calculation for the input snapshot below. This report is not
approval of a bridge for construction. Confirm project actions, code basis, National
Annex decisions, detailing and independent engineering review.</p>
<h2>Model and inputs</h2>
<table><tr><th>Parameter</th><th>Run input</th></tr>
<tr><td>Analysis span / physical girder length</td>
<td>{state.span_m:.3f} / {state.physical_girder_length_m:.3f} m</td></tr>
<tr><td>Deck width / carriageway width / offset</td><td>{state.deck_width_m:.3f} /
{state.carriageway_width_m:.3f} / {state.carriageway_offset_m:.3f} m</td></tr>
<tr><td>Girders / spacing / precast section</td>
<td>{state.girder_count} / {state.girder_spacing_m:.3f} m / {_cell(state.section_type)}</td></tr>
<tr><td>Deck build-up</td><td>{state.false_slab_depth_m:.3f} +
{state.in_situ_slab_depth_m:.3f} m</td></tr>
<tr><td>Concrete fck / steel fyk / E</td><td>{state.fck_mpa:.1f} /
{state.fyk_mpa:.1f} / {state.elastic_modulus_mpa:.0f} MPa</td></tr>
<tr><td>Surfacing / barriers / services</td><td>{state.surfacing_thickness_m:.3f} m /
{state.barrier_kn_m:.2f} kN/m each / {state.services_kn_m:.2f} kN/m each</td></tr>
<tr><td>Traffic</td><td>{traffic}</td></tr>
<tr><td>Deflection criterion and provenance</td><td>{criterion}</td></tr></table>
<h2>Governing ULS effects</h2>
<p>Moment: Girder {summary.governing_moment.girder},
{summary.governing_moment.moment_knm:.2f} kNm;
Shear: Girder {summary.governing_shear.girder},
{summary.governing_shear.shear_kn:.2f} kN;
Torsion: Girder {summary.governing_torsion.girder},
{summary.governing_torsion.torsion_knm:.2f} kNm.</p>
<table><tr><th>Girder</th><th>M (kNm)</th><th>V (kN)</th><th>T (kNm)</th>
<th>Source</th></tr>{effects}</table>
<h2>Resistance and serviceability</h2>
<table><tr><th>Girder</th><th>Flex. util.</th><th>Flexure</th><th>VEd/Vmax (kN)</th>
<th>Web limit</th><th>Crack/limit (mm)</th><th>Crack</th><th>Defl./limit (mm)</th>
<th>Deflection</th></tr>{design_rows}</table>
<h2>Scope and provenance notes</h2><ul>{notes}</ul>
{calculations}
{provenance}
<h2>Complete run input register</h2>
<p>Values below are the frozen inputs used for this run; opening or editing a
project clears the report until a new analysis completes.</p>
<table><tr><th>Group</th><th>Input</th><th>Value</th></tr>{input_rows}</table>
</body></html>"""
