from __future__ import annotations

from dataclasses import dataclass


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


def response_deflection_check(
    *,
    permanent_deflection_mm: float,
    traffic_characteristic_deflection_mm: float,
    traffic_factor: float,
    allowable_deflection_mm: float | None,
    status: str,
) -> ResponseDeflectionResult:
    """Combine already analysed permanent and traffic vertical responses linearly."""

    if permanent_deflection_mm < 0.0 or traffic_characteristic_deflection_mm < 0.0:
        raise ValueError("Deflection magnitudes cannot be negative.")
    if traffic_factor < 0.0:
        raise ValueError("traffic_factor cannot be negative.")
    if allowable_deflection_mm is not None and allowable_deflection_mm <= 0.0:
        raise ValueError("allowable_deflection_mm must be positive when supplied.")
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
    )
