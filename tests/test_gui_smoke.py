import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from rc_single_span.gui.app import BridgeMainWindow


def test_desktop_gui_builds_offscreen() -> None:
    app = QApplication.instance() or QApplication([])
    window = BridgeMainWindow()
    assert window.windowTitle() == "RC Single-Span Bridge Analysis"
    assert window._tabs.count() >= 10
    assert window.code_profile.count() == 2
    assert window.section_type.count() == 3
    assert window.design_code_stack.count() == 2
    assert window.design_results_table.columnCount() == 13
    assert window.bridge_schematic is not None
    assert window._read_state().build_project().geometry.girder_count == 7
    window.close()
    app.processEvents()
