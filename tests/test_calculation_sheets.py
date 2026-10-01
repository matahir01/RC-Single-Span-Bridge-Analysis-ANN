"""Worked sheets use real BS traffic/design outputs and yield a readable PDF."""

import os
from dataclasses import replace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtGui import QPageSize, QTextDocument
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QApplication

from rc_single_span.codes.eurocode.combinations import EurocodeServiceabilityFactors
from rc_single_span.gui.design_adapter import GuiDesignInputs
from rc_single_span.gui.engine_adapter import (
    GuiAnalysisSettings,
    GuiAnalysisSummary,
    GuiCodeProfile,
    GuiResultRow,
    _bs_design_rows,
)
from rc_single_span.gui.project_state import GuiProjectState
from rc_single_span.gui.reporting import render_calculation_report
from rc_single_span.verification.reference_runner import ReferenceRunConfig, run_reference_project


def test_bs_worked_sheet_has_governing_case_substitutions_and_diagrams(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    state = GuiProjectState()
    settings = GuiAnalysisSettings(code_profile=GuiCodeProfile.BS_5400)
    design = GuiDesignInputs(enabled=True)
    config = ReferenceRunConfig(
        elastic_modulus_mpa=34000,
        eurocode_sls_factors=EurocodeServiceabilityFactors(.75, 0),
        bs_ha_longitudinal_step_m=7.5,
        bs_hb_longitudinal_step_m=15,
        bs_hb_transverse_step_m=3.5,
        bs_combined_hb_longitudinal_step_m=15,
        bs_combined_hb_transverse_step_m=3.5,
        bs_combined_ha_kel_step_m=15,
        retain_all_cases=False,
    )
    result = run_reference_project(
        state.build_project(), config=config,
        bs5400_design_inputs=design.for_profile(settings.code_profile.value),
        code_route="bs5400",
    )
    rows = tuple(
        GuiResultRow(item.girder_index,
            max(c.effects.moment_knm for c in item.governing if c.limit_state.value == "uls"),
            max(c.effects.shear_kn for c in item.governing if c.limit_state.value == "uls"),
            max(c.effects.torsion_knm for c in item.governing if c.limit_state.value == "uls"),
            "BS 5400")
        for item in result.bs5400_combinations
    )
    summary = GuiAnalysisSummary(
        settings.code_profile, "BS 5400 / BD 37", rows,
        max(rows, key=lambda r: r.moment_knm),
        max(rows, key=lambda r: r.shear_kn),
        max(rows, key=lambda r: r.torsion_knm),
        _bs_design_rows(result), ("Explicit project assumptions",),
    )
    html = render_calculation_report(state, settings, design, summary, result=result)
    with pytest.raises(ValueError, match="project does not match"):
        render_calculation_report(replace(state, name="Changed project"),
                                  settings, design, summary, result=result)
    with pytest.raises(ValueError, match="selected code profile"):
        render_calculation_report(state,
                                  replace(settings, code_profile=GuiCodeProfile.BS_EN),
                                  design, summary, result=result)
    case = max(
        (c for c in result.bs5400_combinations[summary.governing_moment.girder - 1].cases
         if c.limit_state.value == "uls"),
        key=lambda c: c.result.effects.moment_knm,
    )
    assert f"{case.result.factors['primary_live']:.4f} x " in html
    assert f"{case.nominal_traffic.moment_knm:.4f}" in html
    assert f"{result.bs5400_design[0].flexure.design_moment_knm:.4f}" in html
    assert "Nominal ha_hb case" in html
    assert "No project limit supplied; no pass/fail asserted" in html
    assert html.count("data:image/png;base64,") == 3
    target = tmp_path / "bs_calculation_sheets.pdf"
    document = QTextDocument()
    document.setHtml(html)
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    printer.setOutputFileName(str(target))
    document.print_(printer)
    assert target.read_bytes().startswith(b"%PDF-")
    assert target.stat().st_size > 50000
    app.processEvents()
