from __future__ import annotations

import os
import sys

from PySide6.QtWidgets import QApplication

from rc_single_span.gui.main_window import BridgeMainWindow as _BaseBridgeMainWindow
from rc_single_span.gui.package_smoke import run_package_smoke
from rc_single_span.gui.visualization import install_visualization_tab


class BridgeMainWindow(_BaseBridgeMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.bridge_schematic = install_visualization_tab(self)


__all__ = ["BridgeMainWindow", "main"]


def main() -> int:
    package_smoke = len(sys.argv) == 3 and sys.argv[1] == "--package-smoke"
    if package_smoke:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication([sys.argv[0]] if package_smoke else sys.argv)
    app.setApplicationName("RC Single-Span Bridge Analysis")
    if package_smoke:
        return run_package_smoke(BridgeMainWindow, sys.argv[2])
    window = BridgeMainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
