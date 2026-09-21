from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ComparisonStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NOT_CHECKED = "not_checked"


@dataclass(frozen=True)
class ComparisonTolerance:
    relative: float = 0.001
    absolute: float = 1.0e-6

    def __post_init__(self) -> None:
        if self.relative < 0.0 or self.absolute < 0.0:
            raise ValueError("Comparison tolerances cannot be negative.")


@dataclass(frozen=True)
class ScalarComparison:
    label: str
    internal_value: float
    reference_value: float
    absolute_difference: float
    relative_difference: float
    tolerance: ComparisonTolerance
    status: ComparisonStatus
    unit: str = ""
    source: str = ""

    @property
    def passes(self) -> bool:
        return self.status is ComparisonStatus.PASS


def compare_scalar(
    *,
    label: str,
    internal_value: float,
    reference_value: float,
    tolerance: ComparisonTolerance | None = None,
    unit: str = "",
    source: str = "",
) -> ScalarComparison:
    current = tolerance or ComparisonTolerance()
    absolute_difference = abs(internal_value - reference_value)
    scale = max(abs(reference_value), abs(internal_value), current.absolute, 1.0e-15)
    relative_difference = absolute_difference / scale
    limit = max(current.absolute, current.relative * scale)
    return ScalarComparison(
        label=label,
        internal_value=internal_value,
        reference_value=reference_value,
        absolute_difference=absolute_difference,
        relative_difference=relative_difference,
        tolerance=current,
        status=(
            ComparisonStatus.PASS
            if absolute_difference <= limit + 1.0e-15
            else ComparisonStatus.FAIL
        ),
        unit=unit,
        source=source,
    )
