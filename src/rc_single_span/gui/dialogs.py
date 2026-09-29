"""Focused input windows launched from the bridge ribbon."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

InputWidget = QCheckBox | QComboBox | QDoubleSpinBox | QLineEdit | QSpinBox


def _clone(widget: InputWidget) -> InputWidget:
    if isinstance(widget, QDoubleSpinBox):
        copy = QDoubleSpinBox()
        copy.setRange(widget.minimum(), widget.maximum())
        copy.setDecimals(widget.decimals())
        copy.setSingleStep(widget.singleStep())
        copy.setSuffix(widget.suffix())
        copy.setValue(widget.value())
        return copy
    if isinstance(widget, QSpinBox):
        copy = QSpinBox()
        copy.setRange(widget.minimum(), widget.maximum())
        copy.setSingleStep(widget.singleStep())
        copy.setSuffix(widget.suffix())
        copy.setValue(widget.value())
        return copy
    if isinstance(widget, QComboBox):
        copy = QComboBox()
        for index in range(widget.count()):
            copy.addItem(widget.itemText(index), widget.itemData(index))
        copy.setCurrentIndex(widget.currentIndex())
        return copy
    if isinstance(widget, QCheckBox):
        copy = QCheckBox(widget.text())
        copy.setChecked(widget.isChecked())
        return copy
    if isinstance(widget, QLineEdit):
        copy = QLineEdit(widget.text())
        copy.setPlaceholderText(widget.placeholderText())
        return copy
    raise TypeError(f"Unsupported input widget: {type(widget).__name__}")


def _value(widget: InputWidget) -> float | int | bool | str:
    if isinstance(widget, (QDoubleSpinBox, QSpinBox)):
        return widget.value()
    if isinstance(widget, QComboBox):
        return widget.currentIndex()
    if isinstance(widget, QCheckBox):
        return widget.isChecked()
    return widget.text()


def _set_value(widget: InputWidget, value: float | bool | str) -> None:
    if isinstance(widget, (QDoubleSpinBox, QSpinBox)):
        widget.setValue(value)
    elif isinstance(widget, QComboBox):
        widget.setCurrentIndex(value)
    elif isinstance(widget, QCheckBox):
        widget.setChecked(value)
    else:
        widget.setText(value)


class InputDialog(QDialog):
    """Commit a group of GUI controls only after the complete group validates."""

    def __init__(
        self,
        title: str,
        fields: Sequence[tuple[str, InputWidget]],
        *,
        validate: Callable[[], object],
        changed: Callable[[], None],
        parent: QWidget,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(520, min(650, 160 + 43 * len(fields)))
        self._bindings = [(original, _clone(original)) for _, original in fields]
        self._validate = validate
        self._changed = changed

        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form = QFormLayout(content)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        for (label, _), (_, copy) in zip(fields, self._bindings, strict=True):
            if isinstance(copy, QCheckBox):
                form.addRow(copy)
            else:
                form.addRow(QLabel(label), copy)
        scroll.setWidget(content)
        layout.addWidget(scroll)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._submit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _submit(self) -> None:
        previous = [(original, _value(original)) for original, _ in self._bindings]
        for original, copy in self._bindings:
            blocked = original.blockSignals(True)
            _set_value(original, _value(copy))
            original.blockSignals(blocked)
        try:
            self._validate()
        except (ValueError, TypeError, KeyError) as exc:
            for original, value in previous:
                blocked = original.blockSignals(True)
                _set_value(original, value)
                original.blockSignals(blocked)
            QMessageBox.warning(self, "Check inputs", str(exc))
            return
        self._changed()
        self.accept()
