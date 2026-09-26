from __future__ import annotations

from PySide6.QtWidgets import QDoubleSpinBox, QFormLayout, QGroupBox, QSpinBox, QVBoxLayout, QWidget


def double_spin(
    value: float,
    *,
    minimum: float = 0.0,
    maximum: float = 1_000_000.0,
    decimals: int = 3,
    step: float = 0.01,
    suffix: str = "",
) -> QDoubleSpinBox:
    widget = QDoubleSpinBox()
    widget.setRange(minimum, maximum)
    widget.setDecimals(decimals)
    widget.setSingleStep(step)
    widget.setValue(value)
    if suffix:
        widget.setSuffix(suffix)
    return widget


def int_spin(
    value: int,
    *,
    minimum: int = 1,
    maximum: int = 10_000,
) -> QSpinBox:
    widget = QSpinBox()
    widget.setRange(minimum, maximum)
    widget.setValue(value)
    return widget


def form_page(title: str) -> tuple[QWidget, QFormLayout]:
    page = QWidget()
    layout = QVBoxLayout(page)
    group = QGroupBox(title)
    form = QFormLayout(group)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
    layout.addWidget(group)
    layout.addStretch(1)
    return page, form
