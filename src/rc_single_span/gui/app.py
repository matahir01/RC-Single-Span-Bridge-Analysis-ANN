from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from rc_single_span.gui.main_window import BridgeMainWindow

__all__ = ["BridgeMainWindow", "main"]


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("RC Single-Span Bridge Analysis")
    window = BridgeMainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
