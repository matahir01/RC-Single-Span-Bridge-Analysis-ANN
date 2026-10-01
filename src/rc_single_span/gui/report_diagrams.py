"""Small raster plots for the A4 calculation sheets."""

from base64 import b64encode

from PySide6.QtCore import QBuffer, QIODevice, QPointF
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPolygonF


def response_chart(stations: tuple[float, ...], values: tuple[float, ...],
                   *, title: str, unit: str) -> str:
    if len(stations) != len(values) or len(values) < 2 or stations[-1] <= stations[0]:
        raise ValueError("A response plot needs at least two ordered stations.")
    image = QImage(900, 240, QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setFont(QFont("Arial", 10))
    painter.setPen(QColor("#22354b"))
    painter.drawText(38, 22, title)
    left, right, top, bottom = 62.0, 866.0, 45.0, 193.0
    low, high = min(0.0, *values), max(0.0, *values)
    if high - low < 1e-12:
        high = low + 1.0

    def x_pos(x: float) -> float:
        return left + (x - stations[0]) / (stations[-1] - stations[0]) * (right - left)

    def y_pos(y: float) -> float:
        return bottom - (y - low) / (high - low) * (bottom - top)

    painter.setPen(QPen(QColor("#b6c5cf"), 1))
    painter.drawLine(QPointF(left, top), QPointF(left, bottom))
    painter.drawLine(QPointF(left, y_pos(0)), QPointF(right, y_pos(0)))
    painter.setPen(QPen(QColor("#175d83"), 2))
    painter.drawPolyline(QPolygonF([QPointF(x_pos(x), y_pos(y))
                                    for x, y in zip(stations, values, strict=True)]))
    painter.setPen(QColor("#22354b"))
    painter.drawText(38, 219, f"{stations[0]:g} m")
    painter.drawText(802, 219, f"{stations[-1]:g} m")
    painter.drawText(62, 38, f"{high:.2f} {unit}")
    painter.drawText(62, 233, f"Min {low:.2f} {unit}   Max {max(values):.2f} {unit}")
    painter.end()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise RuntimeError("Cannot encode response plot.")
    return "data:image/png;base64," + b64encode(bytes(buffer.data())).decode("ascii")
