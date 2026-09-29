from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

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
        text_color = QColor("#24415a")
        line_color = QColor("#527892")
        painter.fillRect(self.rect(), QColor("#ffffff"))
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
        painter.setBrush(QBrush(QColor("#f5f9fc")))
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
        deck_y = cross_y
        deck_depth = max(state.false_slab_depth_m + state.in_situ_slab_depth_m, 1.0e-9)
        in_situ_px = 18.0 * state.in_situ_slab_depth_m / deck_depth
        painter.setBrush(QBrush(QColor("#dbeaf3")))
        painter.drawRect(QRectF(cross_left, deck_y, width, in_situ_px))
        painter.setBrush(QBrush(QColor("#b9d1e2")))
        painter.drawRect(QRectF(cross_left, deck_y + in_situ_px, width, 18.0 - in_situ_px))

        available = width * 0.90
        spacing_px = available / max(state.girder_count - 1, 1)
        start_x = margin + 0.05 * width
        section_depth_px = min(115.0, max(45.0, 0.12 * height))
        section_width_px = min(54.0, max(22.0, 0.34 * spacing_px))
        girder_top = deck_y + 18.0
        painter.setBrush(QBrush(QColor("#d1a47a")))
        for index in range(state.girder_count):
            x = start_x + index * spacing_px
            if state.section_type == "rectangular":
                painter.drawRect(
                    QRectF(x - section_width_px / 2, girder_top,
                           section_width_px, section_depth_px)
                )
            elif state.section_type == "t":
                flange = min(spacing_px * 0.78, section_width_px * 1.7)
                flange_depth = section_depth_px * (
                    state.t_flange_thickness_m / max(state.t_total_depth_m, 1.0e-9)
                )
                web = max(6.0, min(section_width_px, section_width_px *
                          state.t_web_width_m / max(state.t_flange_width_m, 1.0e-9)))
                painter.drawRect(QRectF(x - flange / 2, girder_top, flange, flange_depth))
                painter.drawRect(QRectF(x - web / 2, girder_top + flange_depth,
                                        web, max(0.0, section_depth_px - flange_depth)))
            else:
                total = (
                    state.i_top_flange_thickness_m + state.i_top_haunch_depth_m
                    + state.i_web_depth_m + state.i_bottom_haunch_depth_m
                    + state.i_bottom_flange_thickness_m
                )
                top_depth = section_depth_px * state.i_top_flange_thickness_m / max(total, 1.0e-9)
                bottom_depth = section_depth_px * state.i_bottom_flange_thickness_m / max(total, 1.0e-9)
                flange = min(spacing_px * 0.78, section_width_px * 1.3)
                web = max(6.0, section_width_px * state.i_web_width_m /
                          max(state.i_top_flange_width_m, 1.0e-9))
                painter.drawRect(QRectF(x - flange / 2, girder_top, flange, top_depth))
                painter.drawRect(QRectF(x - web / 2, girder_top + top_depth,
                                        web, max(0.0, section_depth_px - top_depth - bottom_depth)))
                painter.drawRect(QRectF(x - flange / 2,
                                        girder_top + section_depth_px - bottom_depth,
                                        flange, bottom_depth))
            painter.drawText(int(x - 10.0), int(deck_y + section_depth_px + 38.0), f"G{index + 1}")

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
        "Live geometry schematic generated directly from the current project inputs. "
        "This is a modelling aid, not a fabrication/detail drawing."
    )
    note.setWordWrap(True)
    layout.addWidget(note)
    schematic = BridgeSchematicWidget(window._read_state())
    layout.addWidget(schematic, 1)
    window._tabs.insertTab(2, page, "Bridge view")
    window._refresh_navigation()
    window._tabs.setCurrentWidget(page)
    return schematic
