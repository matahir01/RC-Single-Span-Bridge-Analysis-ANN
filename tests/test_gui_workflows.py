import json
import os
from dataclasses import replace
from threading import Event

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMessageBox

from rc_single_span.core.progress import AnalysisCancelled, AnalysisControl
from rc_single_span.gui.app import BridgeMainWindow
from rc_single_span.gui.dialogs import InputDialog
from rc_single_span.gui.engine_adapter import (
    GuiAccuracyMode,
    GuiAnalysisSummary,
    GuiCodeProfile,
    GuiResultRow,
    run_gui_analysis,
)
from rc_single_span.gui.reporting import render_calculation_report


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    result = BridgeMainWindow()
    yield result
    result.close()
    app.processEvents()


def test_ribbon_input_dialog_commits_or_rolls_back_as_one_edit(window, monkeypatch) -> None:
    previous = window.deck_width_m.value()
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(args[2]))
    dialog = InputDialog(
        "Layout", [("Deck width", window.deck_width_m)],
        validate=lambda: window._read_state().build_project(),
        changed=window._inputs_changed,
        parent=window,
    )
    dialog._bindings[0][1].setValue(1.0)
    dialog._submit()
    assert messages
    assert window.deck_width_m.value() == previous
    dialog._bindings[0][1].setValue(12.0)
    dialog._submit()
    assert window.deck_width_m.value() == 12.0
    assert dialog.result() == dialog.DialogCode.Accepted


def test_layout_ribbon_action_opens_focused_input_window(window, monkeypatch) -> None:
    opened = []
    monkeypatch.setattr(InputDialog, "exec", lambda self: opened.append(self))
    action = next(item for item in window.findChildren(QAction) if item.text() == "Layout")
    action.trigger()
    assert opened[0].windowTitle() == "Layout"
    assert window.span_m in [original for original, _ in opened[0]._bindings]


def test_project_round_trip_keeps_code_route_and_clears_old_outputs(window, tmp_path) -> None:
    window.project_name.setText("Traceable reference")
    window.section_type.setCurrentText("I")
    window.code_profile.setCurrentIndex(1)
    window.hb_units.setValue(37.0)
    window.bs_ha_step.setValue(0.5)
    window.bs_hb_long_step.setValue(0.5)
    window.bs_hb_trans_step.setValue(0.25)
    window.bs_combined_long_step.setValue(1.0)
    window.bs_combined_trans_step.setValue(0.5)
    window.bs_combined_kel_step.setValue(1.0)
    window.retain_cases.setChecked(True)
    window.all_case_deflection.setChecked(True)
    window.deflection_enabled.setChecked(True)
    window.deflection_limit.setValue(42.0)
    window.deflection_basis.setText("Project brief section 4")
    expected = window._read_state()
    target = tmp_path / "bridge.json"
    window.save_project(target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["analysis"]["code_profile"].startswith("BS 5400")
    assert payload["analysis"]["bs_combined_hb_transverse_step_m"] == 0.5
    assert payload["analysis"]["retain_all_cases"] is True
    assert payload["analysis"]["all_case_combined_deflection"] is True
    assert payload["design"]["deflection_limit_basis"] == "Project brief section 4"
    window._report_html = "previous run"
    window._export_action.setEnabled(True)
    window.project_name.setText("Changed")
    window.open_project(target)
    assert window._read_state() == expected
    assert window._read_settings().hb_units == 37.0
    assert window._read_settings().bs_hb_transverse_step_m == 0.25
    assert window._read_settings().bs_combined_ha_kel_step_m == 1.0
    assert window._read_settings().all_case_combined_deflection
    assert window._read_design_inputs().deflection_limit_mm == 42.0
    assert window._report_html is None
    assert not window._export_action.isEnabled()
    with pytest.raises(ValueError, match="Run the current project"):
        window.write_report_pdf(tmp_path / "stale.pdf")

    payload["project"]["deck_width_m"] = 1.0
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        window.open_project(target)
    assert window._read_state() == expected


def test_retaining_cases_does_not_implicitly_enable_exhaustive_deflection(window) -> None:
    window.code_profile.setCurrentIndex(1)
    window.retain_cases.setChecked(True)
    assert not window.all_case_deflection.isChecked()
    assert window.all_case_deflection.isEnabled()
    window.all_case_deflection.setChecked(True)
    window.code_profile.setCurrentIndex(0)
    assert not window.all_case_deflection.isChecked()
    assert not window.all_case_deflection.isEnabled()
    window.code_profile.setCurrentIndex(1)
    window.all_case_deflection.setChecked(True)
    window.retain_cases.setChecked(False)
    assert not window.all_case_deflection.isChecked()
    assert not window.all_case_deflection.isEnabled()


def test_input_edit_invalidates_result_and_report(window) -> None:
    assert window.design_results_table.horizontalHeaderItem(5).text() == "Web limit"
    window._report_html = "prior report"
    window._export_action.setEnabled(True)
    window.span_m.setValue(16.0)
    assert window._report_html is None
    assert window._last_summary is None
    assert not window._export_action.isEnabled()
    assert "Run the analysis again" in window.result_basis.text()


def test_pdf_report_uses_completed_snapshot_and_stale_run_is_discarded(window, tmp_path) -> None:
    row = GuiResultRow(1, 123.5, 45.25, 6.0, "test engine effects")
    summary = GuiAnalysisSummary(
        GuiCodeProfile.BS_EN, "test basis", (row,), row, row, row, (), ("test scope",)
    )
    window._run_state = window._read_state()
    window._run_settings = window._read_settings()
    window._run_design = window._read_design_inputs()
    window._run_fingerprint = window._fingerprint()
    window._analysis_finished(object(), summary)
    pdf = tmp_path / "calculation.pdf"
    window.write_report_pdf(pdf)
    assert pdf.read_bytes().startswith(b"%PDF-")
    assert "123.500" in window._report_html

    window._run_fingerprint = window._fingerprint()
    window.span_m.setValue(17.0)
    window._analysis_finished(object(), summary)
    assert window._last_summary is None
    assert window._report_html is None


def test_cancel_stops_engine_during_influence_preparation_and_clears_gui(window) -> None:
    cancelled = Event()
    events = []

    def progress(phase: str, completed: int, total: int) -> None:
        events.append((phase, completed, total))
        if phase == "Preparing grillage: UDL cells" and completed == 1:
            cancelled.set()

    with pytest.raises(AnalysisCancelled):
        run_gui_analysis(
            window._read_state().build_project(),
            window._read_settings(),
            window._read_design_inputs(),
            control=AnalysisControl(progress, cancelled.is_set),
        )
    assert any(phase == "Preparing grillage: UDL cells" for phase, _, _ in events)

    window._cancel_event = cancelled
    window._last_result = object()
    window._analysis_cancelled()
    assert window.run_button.isEnabled()
    assert not window.cancel_button.isEnabled()
    assert window._last_result is None
    assert window._last_summary is None
    assert "cancelled" in window.result_basis.text().lower()


def test_accuracy_mode_and_custom_grid_round_trip(window, tmp_path) -> None:
    assert window._read_settings().accuracy_mode is GuiAccuracyMode.FINAL
    assert window.lm1_step.value() == 0.6
    window.analysis_mode.setCurrentText(GuiAccuracyMode.STANDARD.value)
    assert window.lm1_step.value() == 1.2
    window.lm1_step.setValue(0.9)
    assert window._read_settings().accuracy_mode is GuiAccuracyMode.CUSTOM
    target = tmp_path / "accuracy.json"
    window.save_project(target)
    window.analysis_mode.setCurrentText(GuiAccuracyMode.QUICK.value)
    assert window.lm1_step.value() == 3.0
    window.open_project(target)
    assert window._read_settings().accuracy_mode is GuiAccuracyMode.CUSTOM
    assert window._read_settings().lm1_step_m == 0.9


def test_quick_mode_runs_engine_and_labels_unverified_grid(window, tmp_path) -> None:
    state = window._read_state()
    settings = replace(window._read_settings(), accuracy_mode=GuiAccuracyMode.QUICK)
    result, summary = run_gui_analysis(state.build_project(), settings)
    assert result.lm1.longitudinal_step_m == summary.actual_lm1_step_m == 3.0
    assert any("No grid convergence claim" in note for note in summary.notes)
    report = render_calculation_report(
        state, settings, window._read_design_inputs(), summary, result=result)
    assert "LM1 search step 3.000 m" in report
    assert "MEd = gammaG x MG + gammaQ x MLM1" in report
    assert "Traffic case" in report
    assert report.count("data:image/png;base64,") == 3
    window.analysis_mode.setCurrentText(GuiAccuracyMode.QUICK.value)
    window._run_state, window._run_settings = state, settings
    window._run_design = window._read_design_inputs()
    window._run_fingerprint = window._fingerprint()
    window._analysis_finished(result, summary)
    pdf = tmp_path / "quick_calculation_sheets.pdf"
    window.write_report_pdf(pdf)
    assert pdf.read_bytes().startswith(b"%PDF-")
    assert pdf.stat().st_size > 30000
