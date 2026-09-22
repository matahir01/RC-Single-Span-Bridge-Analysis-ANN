from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise
from math import ceil, pi

from rc_single_span.design.detailing import bar_area_mm2


@dataclass(frozen=True)
class EC2AnchorageResult:
    bar_diameter_mm: float
    steel_stress_mpa: float
    fctd_mpa: float
    design_bond_strength_mpa: float
    basic_required_anchorage_length_mm: float
    design_anchorage_length_mm: float
    minimum_anchorage_length_mm: float
    alpha_product: float
    passes_available_length: bool | None
    available_length_mm: float | None


@dataclass(frozen=True)
class FaceReinforcementArrangement:
    bar_diameter_mm: float
    bar_count: int
    provided_area_mm2: float
    centre_spacing_mm: float | None
    required_area_mm2: float
    passes_area: bool
    passes_spacing: bool | None


@dataclass(frozen=True)
class LongitudinalDemandStation:
    x_m: float
    required_area_mm2: float


@dataclass(frozen=True)
class CurtailmentZone:
    start_m: float
    end_m: float
    required_area_mm2: float
    minimum_bars_required: int
    bars_to_continue: int
    theoretical_cutoff_m: float | None
    anchored_cutoff_m: float | None


@dataclass(frozen=True)
class CurtailmentPlan:
    bar_diameter_mm: float
    total_bars: int
    full_bar_area_mm2: float
    anchorage_length_m: float
    zones: tuple[CurtailmentZone, ...]
    status: str


def ec2_design_anchorage_length(
    *,
    bar_diameter_mm: float,
    steel_stress_mpa: float,
    fctk_005_mpa: float,
    gamma_c: float = 1.50,
    alpha_ct: float = 1.0,
    eta1: float = 1.0,
    eta2: float | None = None,
    alpha1: float = 1.0,
    alpha2: float = 1.0,
    alpha3: float = 1.0,
    alpha4: float = 1.0,
    alpha5: float = 1.0,
    available_length_mm: float | None = None,
) -> EC2AnchorageResult:
    """EC2 straight-bar tension anchorage calculation.

    Implements the EN 1992-1-1 bond-length framework:
    f_bd = 2.25 eta1 eta2 f_ctd
    l_b,rqd = (phi/4) sigma_sd / f_bd
    l_bd = alpha1..alpha5 l_b,rqd, subject to the tension-bar minimum.

    Bond-condition and alpha factors are explicit inputs so the program does
    not silently assume favourable detailing where project geometry says
    otherwise.
    """

    if min(
        bar_diameter_mm,
        steel_stress_mpa,
        fctk_005_mpa,
        gamma_c,
        alpha_ct,
        eta1,
        alpha1,
        alpha2,
        alpha3,
        alpha4,
        alpha5,
    ) <= 0.0:
        raise ValueError("EC2 anchorage inputs must be positive.")
    if available_length_mm is not None and available_length_mm <= 0.0:
        raise ValueError("available_length_mm must be positive when supplied.")

    resolved_eta2 = (
        min((132.0 - bar_diameter_mm) / 100.0, 1.0)
        if eta2 is None
        else eta2
    )
    if not 0.0 < resolved_eta2 <= 1.0:
        raise ValueError("eta2 must lie in (0, 1].")

    fctd = alpha_ct * fctk_005_mpa / gamma_c
    fbd = 2.25 * eta1 * resolved_eta2 * fctd
    basic = (bar_diameter_mm / 4.0) * steel_stress_mpa / fbd
    alpha_product = alpha1 * alpha2 * alpha3 * alpha4 * alpha5
    reduced = alpha_product * basic
    minimum = max(0.30 * basic, 10.0 * bar_diameter_mm, 100.0)
    design = max(reduced, minimum)
    passes = (
        None
        if available_length_mm is None
        else available_length_mm + 1.0e-9 >= design
    )
    return EC2AnchorageResult(
        bar_diameter_mm=bar_diameter_mm,
        steel_stress_mpa=steel_stress_mpa,
        fctd_mpa=fctd,
        design_bond_strength_mpa=fbd,
        basic_required_anchorage_length_mm=basic,
        design_anchorage_length_mm=design,
        minimum_anchorage_length_mm=minimum,
        alpha_product=alpha_product,
        passes_available_length=passes,
        available_length_mm=available_length_mm,
    )


def select_face_reinforcement(
    *,
    required_area_mm2: float,
    face_length_mm: float,
    available_diameters_mm: tuple[float, ...] = (10.0, 12.0, 16.0, 20.0),
    maximum_spacing_mm: float | None = None,
    minimum_bars: int = 2,
) -> FaceReinforcementArrangement:
    """Choose a simple distributed face-steel arrangement.

    The selector satisfies the required area and, when supplied, maximum
    centre spacing.  It is suitable for side-face or nominal longitudinal
    face reinforcement; local anchorage and end-zone geometry remain separate.
    """

    if min(required_area_mm2, face_length_mm) <= 0.0:
        raise ValueError("Face-reinforcement area and face length must be positive.")
    if minimum_bars < 2:
        raise ValueError("minimum_bars must be at least two.")
    if maximum_spacing_mm is not None and maximum_spacing_mm <= 0.0:
        raise ValueError("maximum_spacing_mm must be positive when supplied.")
    if not available_diameters_mm or any(d <= 0.0 for d in available_diameters_mm):
        raise ValueError("available_diameters_mm must contain positive values.")

    candidates: list[FaceReinforcementArrangement] = []
    for diameter in sorted(set(available_diameters_mm)):
        area = bar_area_mm2(diameter)
        count_area = max(minimum_bars, ceil(required_area_mm2 / area))
        count_spacing = (
            minimum_bars
            if maximum_spacing_mm is None
            else max(minimum_bars, ceil(face_length_mm / maximum_spacing_mm) + 1)
        )
        count = max(count_area, count_spacing)
        spacing = face_length_mm / (count - 1) if count > 1 else None
        spacing_ok = (
            None
            if maximum_spacing_mm is None
            else spacing is not None and spacing <= maximum_spacing_mm + 1.0e-9
        )
        candidates.append(
            FaceReinforcementArrangement(
                bar_diameter_mm=diameter,
                bar_count=count,
                provided_area_mm2=count * area,
                centre_spacing_mm=spacing,
                required_area_mm2=required_area_mm2,
                passes_area=count * area + 1.0e-9 >= required_area_mm2,
                passes_spacing=spacing_ok,
            )
        )

    return min(
        candidates,
        key=lambda item: (
            item.provided_area_mm2,
            item.bar_count,
            item.bar_diameter_mm,
        ),
    )


def build_symmetric_curtailment_plan(
    *,
    span_m: float,
    stations: Sequence[LongitudinalDemandStation],
    bar_diameter_mm: float,
    total_bars: int,
    anchorage_length_mm: float,
) -> CurtailmentPlan:
    """Build a conservative symmetric bar-continuation schedule from an As envelope.

    This routine does not invent a moment envelope.  It consumes a station-wise
    required-steel envelope produced elsewhere.  A theoretical bar cutoff is
    moved away from the higher-demand region by at least the supplied anchorage
    length.  The first/last stations must coincide with the supports.
    """

    if span_m <= 0.0 or bar_diameter_mm <= 0.0 or anchorage_length_mm <= 0.0:
        raise ValueError("Curtailment geometry must be positive.")
    if total_bars < 2:
        raise ValueError("total_bars must be at least two.")
    if len(stations) < 2:
        raise ValueError("At least two demand stations are required.")

    ordered = tuple(sorted(stations, key=lambda item: item.x_m))
    if abs(ordered[0].x_m) > 1.0e-9 or abs(ordered[-1].x_m - span_m) > 1.0e-9:
        raise ValueError("Curtailment stations must include both supports.")
    if any(
        item.x_m < 0.0
        or item.x_m > span_m
        or item.required_area_mm2 < 0.0
        for item in ordered
    ):
        raise ValueError("Curtailment demand stations are outside valid bounds.")
    if any(b.x_m <= a.x_m for a, b in pairwise(ordered)):
        raise ValueError("Curtailment station positions must be unique.")

    single_area = pi * bar_diameter_mm**2 / 4.0
    full_area = total_bars * single_area
    if max(item.required_area_mm2 for item in ordered) > full_area + 1.0e-9:
        raise ValueError("Supplied bar set cannot satisfy the station-wise steel demand.")

    anchorage_m = anchorage_length_mm / 1000.0
    zones: list[CurtailmentZone] = []
    for left, right in pairwise(ordered):
        required = max(left.required_area_mm2, right.required_area_mm2)
        bars_required = max(2, ceil(required / single_area))
        bars_continue = min(total_bars, bars_required)

        cutoff: float | None = None
        anchored: float | None = None
        if bars_continue < total_bars:
            cutoff = 0.5 * (left.x_m + right.x_m)
            if cutoff <= span_m / 2.0:
                anchored = max(0.0, cutoff - anchorage_m)
            else:
                anchored = min(span_m, cutoff + anchorage_m)

        zones.append(
            CurtailmentZone(
                start_m=left.x_m,
                end_m=right.x_m,
                required_area_mm2=required,
                minimum_bars_required=bars_required,
                bars_to_continue=bars_continue,
                theoretical_cutoff_m=cutoff,
                anchored_cutoff_m=anchored,
            )
        )

    return CurtailmentPlan(
        bar_diameter_mm=bar_diameter_mm,
        total_bars=total_bars,
        full_bar_area_mm2=full_area,
        anchorage_length_m=anchorage_m,
        zones=tuple(zones),
        status=(
            "Preliminary longitudinal zoning from the supplied station-wise steel "
            "envelope. Cutoffs include the supplied anchorage extension but still "
            "require final code checks for shear-related tension shift, support "
            "anchorage, laps, fatigue and drawing-level detailing."
        ),
    )
