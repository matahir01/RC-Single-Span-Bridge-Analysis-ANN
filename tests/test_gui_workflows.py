import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMessageBox

from rc_single_span.gui.app import BridgeMainWindow
from rc_single_span.gui.dialogs import InputDialog
from rc_single_span.gui.engine_adapter import GuiAnalysisSummary, GuiCodeProfile, GuiResultRow


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
    window.deflection_enabled.setChecked(True)
    window.deflection_limit.setValue(42.0)
    window.deflection_basis.setText("Project brief section 4")
    expected = window._read_state()
    target = tmp_path / "bridge.json"
    window.save_project(target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["analysis"]["code_profile"].startswith("BS 5400")
    assert payload["design"]["deflection_limit_basis"] == "Project brief section 4"
    window._report_html = "previous run"
    window._export_action.setEnabled(True)
    window.project_name.setText("Changed")
    window.open_project(target)
    assert window._read_state() == expected
    assert window._read_settings().hb_units == 37.0
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


def test_input_edit_invalidates_result_and_report(window) -> None:
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
