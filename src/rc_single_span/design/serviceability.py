from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectDeflectionCriterion:
    """Project-selected bridge deflection criterion with explicit provenance.

    BS EN does not provide one universal span-ratio limit that can safely be
    hard-coded for every road bridge.  The design application therefore keeps
    the acceptance criterion as a project/authority input and records where it
    came from.
    """

    allowable_deflection_mm: float
    basis: str

    def __post_init__(self) -> None:
        if self.allowable_deflection_mm <= 0.0:
            raise ValueError("allowable_deflection_mm must be positive.")
        if not self.basis.strip():
            raise ValueError("Deflection criterion basis/provenance is required.")

    @classmethod
    def from_span_ratio(
        cls,
        *,
        span_m: float,
        denominator: float,
        basis: str,
    ) -> ProjectDeflectionCriterion:
        """Create an explicit L/n project criterion without inventing n.

        ``denominator`` must come from the project specification, approving
        authority or another traceable design basis.  This helper deliberately
        has no default denominator.
        """

        if span_m <= 0.0:
            raise ValueError("span_m must be positive.")
        if denominator <= 0.0:
            raise ValueError("Deflection span-ratio denominator must be positive.")
        return cls(
            allowable_deflection_mm=span_m * 1000.0 / denominator,
            basis=basis,
        )


@dataclass(frozen=True)
class ResponseDeflectionResult:
    permanent_deflection_mm: float
    traffic_characteristic_deflection_mm: float
    traffic_factor: float
    total_deflection_mm: float
    allowable_deflection_mm: float | None
    utilization: float | None
    g_deflection_mm: float | None
    passes: bool | None
    status: str
    criterion_basis: str | None = None


def response_deflection_check(
    *,
    permanent_deflection_mm: float,
    traffic_characteristic_deflection_mm: float,
    traffic_factor: float,
    allowable_deflection_mm: float | None,
    status: str,
    criterion_basis: str | None = None,
) -> ResponseDeflectionResult:
    """Combine analysed permanent and traffic vertical responses linearly.

    ``allowable_deflection_mm`` is an explicit project acceptance limit; this
    function does not create a code-default limit.  When a limit is supplied,
    ``criterion_basis`` can carry the corresponding authority/specification
    provenance into the result and calculation report.
    """

    if permanent_deflection_mm < 0.0 or traffic_characteristic_deflection_mm < 0.0:
        raise ValueError("Deflection magnitudes cannot be negative.")
    if traffic_factor < 0.0:
        raise ValueError("traffic_factor cannot be negative.")
    if allowable_deflection_mm is not None and allowable_deflection_mm <= 0.0:
        raise ValueError("allowable_deflection_mm must be positive when supplied.")
    if allowable_deflection_mm is None and criterion_basis is not None:
        raise ValueError("criterion_basis cannot be supplied without a deflection limit.")
    if criterion_basis is not None and not criterion_basis.strip():
        raise ValueError("criterion_basis must be non-empty when supplied.")
    if not status.strip():
        raise ValueError("Deflection status/provenance is required.")

    total = permanent_deflection_mm + (
        traffic_factor * traffic_characteristic_deflection_mm
    )
    if allowable_deflection_mm is None:
        utilization = None
        margin = None
        passes = None
    else:
        utilization = total / allowable_deflection_mm
        margin = allowable_deflection_mm - total
        passes = margin >= -1.0e-12

    return ResponseDeflectionResult(
        permanent_deflection_mm=permanent_deflection_mm,
        traffic_characteristic_deflection_mm=traffic_characteristic_deflection_mm,
        traffic_factor=traffic_factor,
        total_deflection_mm=total,
        allowable_deflection_mm=allowable_deflection_mm,
        utilization=utilization,
        g_deflection_mm=margin,
        passes=passes,
        status=status,
        criterion_basis=criterion_basis,
    )
