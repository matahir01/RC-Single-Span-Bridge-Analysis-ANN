from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from rc_single_span.gui.project_state import GuiProjectState


class BridgeSchematicWidget(QWidget):
    """Lightweight plan/cross-section schematic driven by the current GUI inputs."""

    def __init__(self, state: GuiProjectState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self.setMinimumHeight(480)

    def set_state(self, state: GuiProjectState) -> None:
        self._state = state
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        text_color = palette.color(self.foregroundRole())
        line_color = palette.color(self.foregroundRole())
        painter.setPen(QPen(line_color, 1.5))

        margin = 36.0
        width = max(float(self.width()) - 2.0 * margin, 100.0)
        height = max(float(self.height()) - 2.0 * margin, 100.0)
        plan_height = 0.50 * height
        cross_y = margin + plan_height + 55.0

        painter.setPen(text_color)
        painter.drawText(int(margin), int(margin - 10.0), "PLAN VIEW")
        painter.setPen(QPen(line_color, 1.5))
        plan = QRectF(margin, margin, width, plan_height - 30.0)
        painter.drawRect(plan)

        state = self._state
        span = max(state.span_m, 1.0e-9)
        deck_width = max(state.deck_width_m, 1.0e-9)
        carriageway_width = min(state.carriageway_width_m, deck_width)

        carriageway_fraction = carriageway_width / deck_width
        carriageway_height = plan.height() * carriageway_fraction
        carriageway_top = plan.center().y() - 0.5 * carriageway_height
        painter.drawRect(
            QRectF(plan.left(), carriageway_top, plan.width(), carriageway_height)
        )

        total_girder_width = max((state.girder_count - 1) * state.girder_spacing_m, 1.0e-9)
        for index in range(state.girder_count):
            y_m = -0.5 * total_girder_width + index * state.girder_spacing_m
            normalized = 0.5 + y_m / deck_width
            y = plan.top() + normalized * plan.height()
            painter.drawLine(int(plan.left()), int(y), int(plan.right()), int(y))
            painter.drawText(int(plan.left() + 6.0), int(y - 3.0), f"G{index + 1}")

        painter.drawText(
            int(plan.left()),
            int(plan.bottom() + 20.0),
            f"Span = {span:.3f} m    Deck = {deck_width:.3f} m    "
            f"Girders = {state.girder_count} @ {state.girder_spacing_m:.3f} m",
        )

        painter.drawText(int(margin), int(cross_y - 20.0), "CROSS SECTION (SCHEMATIC)")
        cross_left = margin
        cross_right = margin + width
        deck_y = cross_y
        painter.drawLine(int(cross_left), int(deck_y), int(cross_right), int(deck_y))
        painter.drawLine(int(cross_left), int(deck_y + 12.0), int(cross_right), int(deck_y + 12.0))

        available = width * 0.90
        spacing_px = available / max(state.girder_count - 1, 1)
        start_x = margin + 0.05 * width
        section_depth_px = min(115.0, max(45.0, 0.12 * height))
        section_width_px = min(42.0, max(18.0, 0.30 * spacing_px))
        for index in range(state.girder_count):
            x = start_x + index * spacing_px
            painter.drawRect(
                QRectF(
                    x - 0.5 * section_width_px,
                    deck_y + 12.0,
                    section_width_px,
                    section_depth_px,
                )
            )
            painter.drawText(int(x - 10.0), int(deck_y + section_depth_px + 32.0), f"G{index + 1}")

        physical_deck_depth = state.false_slab_depth_m + state.in_situ_slab_depth_m
        painter.drawText(
            int(cross_left),
            int(min(self.height() - 18.0, deck_y + section_depth_px + 58.0)),
            f"Precast girder section: {state.section_type.upper()}    "
            f"Deck build-up = {physical_deck_depth:.3f} m",
        )
        painter.end()


def install_visualization_tab(window) -> BridgeSchematicWidget:
    """Attach a geometry visualisation tab to a compatible bridge main window."""

    page = QWidget()
    layout = QVBoxLayout(page)
    note = QLabel(
        "Geometry schematic generated directly from the current project inputs. "
        "This is a modelling aid, not a fabrication/detail drawing."
    )
    note.setWordWrap(True)
    layout.addWidget(note)
    schematic = BridgeSchematicWidget(window._read_state())
    layout.addWidget(schematic, 1)
    refresh = QPushButton("Refresh schematic from current inputs")
    refresh.clicked.connect(lambda: schematic.set_state(window._read_state()))
    layout.addWidget(refresh)
    window._tabs.insertTab(2, page, "Bridge view")
    return schematic
