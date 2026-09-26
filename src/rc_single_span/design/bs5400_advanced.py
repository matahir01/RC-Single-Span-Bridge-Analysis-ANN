from __future__ import annotations

from dataclasses import replace

from rc_single_span.core.models import BridgeProject
from rc_single_span.design.advanced_detailing import FatigueVehicle
from rc_single_span.design.project import BS5400DesignInputs, BS5400GirderDesignResult
from rc_single_span.design.project_detailing import (
    BS5400DetailingInputs,
    BS5400GirderDetailingResult,
)
from rc_single_span.design.stage_d_project import (
    AdvancedGirderDetailingResult,
    AdvancedStageDInputs,
    run_bs5400_advanced_stage_d,
)
from rc_single_span.traffic.combinations import BS5400GirderCombinationResult


def bs5400_standard_fatigue_vehicle() -> FatigueVehicle:
    """Return the BS 5400:Part 10 standard highway fatigue vehicle.

    The historical standard vehicle is 320 kN: four 80 kN standard axles with
    1.8 m, 6.0 m and 1.8 m longitudinal spacings. The vehicle/load model is a
    code default; fatigue resistance/detail classification and traffic/project
    assumptions remain explicit engineering inputs.
    """

    return FatigueVehicle(
        axle_loads_kn=(80.0, 80.0, 80.0, 80.0),
        axle_spacings_m=(1.8, 6.0, 1.8),
        name="BS 5400 Part 10 standard fatigue vehicle",
        provenance=(
            "BS 5400:Part 10:1980 clauses 7.2.2-7.2.3 and Figure 3: "
            "320 kN vehicle comprising four 80 kN standard axles at "
            "1.8/6.0/1.8 m spacing; one vehicle traverses each lane separately."
        ),
    )


def bs5400_curtailment_extension_m(
    *,
    effective_depth_m: float,
    bar_diameter_mm: float,
) -> float:
    """BS 5400-4:1990 clause 5.8.7 continuation beyond theoretical cutoff.

    Except at end supports, every flexural bar extends beyond the point at which
    it is no longer required by at least the greater of the member effective
    depth and 12 bar diameters.
    """

    if effective_depth_m <= 0.0 or bar_diameter_mm <= 0.0:
        raise ValueError("BS 5400 curtailment inputs must be positive.")
    return max(effective_depth_m, 12.0 * bar_diameter_mm / 1000.0)


def _selected_tension_diameter_mm(detail: BS5400GirderDetailingResult) -> float:
    if detail.doubly_reinforced_cage_selection is not None:
        return float(detail.doubly_reinforced_cage_selection.tension.bar_diameter_mm)
    if detail.selected_longitudinal is not None:
        return float(detail.selected_longitudinal.bar_diameter_mm)
    if (
        detail.longitudinal_synthesis is not None
        and detail.longitudinal_synthesis.selected is not None
    ):
        return float(detail.longitudinal_synthesis.selected.arrangement.bar_diameter_mm)
    raise ValueError(
        f"Girder {detail.girder_index} has no selected tension cage from which "
        "to derive the BS 5400 clause 5.8.7 curtailment extension."
    )


def resolve_bs5400_stage_d_code_defaults(
    *,
    design_inputs: BS5400DesignInputs,
    details: tuple[BS5400GirderDetailingResult, ...],
    inputs: AdvancedStageDInputs,
) -> AdvancedStageDInputs:
    """Fill only genuine BS 5400 code defaults; keep project data explicit."""

    vehicle = inputs.bs5400_fatigue_vehicle or bs5400_standard_fatigue_vehicle()
    shift = inputs.bs5400_tension_shift_length_m
    if shift is None:
        shift = max(
            bs5400_curtailment_extension_m(
                effective_depth_m=design_inputs.effective_depth_m,
                bar_diameter_mm=_selected_tension_diameter_mm(detail),
            )
            for detail in details
        )
    return replace(
        inputs,
        bs5400_fatigue_vehicle=vehicle,
        bs5400_tension_shift_length_m=shift,
    )


def run_bs5400_complete_stage_d(
    project: BridgeProject,
    combinations: tuple[BS5400GirderCombinationResult, ...],
    designs: tuple[BS5400GirderDesignResult, ...],
    details: tuple[BS5400GirderDetailingResult, ...],
    *,
    design_inputs: BS5400DesignInputs,
    detailing_inputs: BS5400DetailingInputs,
    inputs: AdvancedStageDInputs,
) -> tuple[AdvancedGirderDetailingResult, ...]:
    """Run legacy Stage D with code-defined fatigue vehicle and curtailment rule.

    This removes the two historical placeholders from the normal BS route while
    retaining explicit project/detail inputs for fatigue resistance, bearing
    geometry, construction-stage stress, laps and other non-universal choices.
    """

    resolved = resolve_bs5400_stage_d_code_defaults(
        design_inputs=design_inputs,
        details=details,
        inputs=inputs,
    )
    return run_bs5400_advanced_stage_d(
        project,
        combinations,
        designs,
        details,
        design_inputs=design_inputs,
        detailing_inputs=detailing_inputs,
        inputs=resolved,
    )
