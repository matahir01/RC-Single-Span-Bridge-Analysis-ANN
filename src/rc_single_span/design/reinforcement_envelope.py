from __future__ import annotations

from dataclasses import dataclass

from rc_single_span.analysis.permanent import (
    PermanentLoadCategory,
    factored_permanent_moment_at_x_knm,
)
from rc_single_span.analysis.sections import final_composite_concrete_layers
from rc_single_span.codes.eurocode.combinations import EurocodeCombinationFactors
from rc_single_span.core.models import BridgeProject
from rc_single_span.design.detailing import LongitudinalBarArrangement
from rc_single_span.design.eurocode import required_steel_area_layered_ec2
from rc_single_span.design.longitudinal_detailing import (
    CurtailmentPlan,
    LongitudinalDemandStation,
    build_symmetric_curtailment_plan,
)
from rc_single_span.traffic.lm1 import LM1SearchResult


@dataclass(frozen=True)
class EC2StationReinforcementDemand:
    x_m: float
    permanent_uls_moment_knm: float
    traffic_characteristic_moment_knm: float
    traffic_uls_moment_knm: float
    total_uls_moment_knm: float
    flexural_required_area_mm2: float | None
    governing_required_area_mm2: float | None
    traffic_case_id: int
    issue: str | None


@dataclass(frozen=True)
class EC2GirderReinforcementEnvelope:
    girder_index: int
    stations: tuple[EC2StationReinforcementDemand, ...]
    maximum_required_area_mm2: float | None
    maximum_required_station_m: float | None
    singly_reinforced_complete: bool
    traffic_search_exhaustive: bool
    basis: str


def build_ec2_station_reinforcement_envelope(
    project: BridgeProject,
    traffic: LM1SearchResult,
    *,
    girder_index: int,
    effective_depth_m: float,
    minimum_area_mm2: float,
    maximum_neutral_axis_ratio: float,
    uls_factors: EurocodeCombinationFactors | None = None,
) -> EC2GirderReinforcementEnvelope:
    """Build station-wise ULS longitudinal steel demand from the LM1 search.

    Permanent moments are evaluated at the exact same x-stations as the common
    LM1 grillage envelope. Traffic is not reconstructed from the single global
    girder maximum: each station uses the LM1 case that actually governs that
    station.
    """

    if not 1 <= girder_index <= int(project.geometry.girder_count):
        raise IndexError("girder_index is outside the physical bridge.")
    if effective_depth_m <= 0.0 or minimum_area_mm2 <= 0.0:
        raise ValueError("EC2 station-reinforcement inputs must be positive.")
    if not 0.0 < maximum_neutral_axis_ratio <= 1.0:
        raise ValueError("maximum_neutral_axis_ratio must lie in (0, 1].")

    station_girder = next(
        (
            item
            for item in traffic.station_moments
            if item.girder_index == girder_index
        ),
        None,
    )
    if station_girder is None:
        raise ValueError(
            "LM1 result does not contain station-wise moments for this girder."
        )

    factors = uls_factors or EurocodeCombinationFactors()
    permanent_factors = {
        category: factors.gamma_g_unfavourable
        for category in PermanentLoadCategory
    }
    layers = final_composite_concrete_layers(
        project.geometry,
        girder_index=girder_index,
    )
    fck = float(project.materials.fck_mpa)
    fyk = float(project.materials.fyk_mpa)

    demands: list[EC2StationReinforcementDemand] = []
    for station in station_girder.stations:
        permanent_uls = factored_permanent_moment_at_x_knm(
            project,
            girder_index=girder_index,
            x_m=station.x_m,
            factors_by_category=permanent_factors,
        )
        traffic_characteristic = station.moment_knm.value
        traffic_uls = factors.gamma_q_traffic * traffic_characteristic
        total_uls = permanent_uls + traffic_uls

        issue: str | None = None
        required: float | None
        governing: float | None
        try:
            required = required_steel_area_layered_ec2(
                med_knm=total_uls,
                layers=layers,
                effective_depth_m=effective_depth_m,
                fck_mpa=fck,
                fyk_mpa=fyk,
                maximum_neutral_axis_ratio=maximum_neutral_axis_ratio,
            )
            governing = max(required, minimum_area_mm2)
        except ValueError as exc:
            required = None
            governing = None
            issue = str(exc)

        demands.append(
            EC2StationReinforcementDemand(
                x_m=station.x_m,
                permanent_uls_moment_knm=permanent_uls,
                traffic_characteristic_moment_knm=traffic_characteristic,
                traffic_uls_moment_knm=traffic_uls,
                total_uls_moment_knm=total_uls,
                flexural_required_area_mm2=required,
                governing_required_area_mm2=governing,
                traffic_case_id=station.moment_knm.case_id,
                issue=issue,
            )
        )

    valid = tuple(
        item
        for item in demands
        if item.governing_required_area_mm2 is not None
    )
    maximum = (
        max(valid, key=lambda item: float(item.governing_required_area_mm2))
        if valid
        else None
    )
    complete = bool(demands) and all(item.issue is None for item in demands)

    return EC2GirderReinforcementEnvelope(
        girder_index=girder_index,
        stations=tuple(demands),
        maximum_required_area_mm2=(
            None
            if maximum is None
            else float(maximum.governing_required_area_mm2)
        ),
        maximum_required_station_m=(
            None if maximum is None else maximum.x_m
        ),
        singly_reinforced_complete=complete,
        traffic_search_exhaustive=traffic.tandem_combinations_exhaustive,
        basis=(
            "Station-wise persistent ULS: factored permanent simple-span response "
            "at the exact LM1 grillage station plus that station's governing LM1 "
            "common-grillage moment. Minimum longitudinal steel is retained at "
            "every station. A curtailment plan is not certifiable when any station "
            "exceeds the configured singly reinforced section limit or when the "
            "traffic search is reduced rather than exhaustive."
        ),
    )


def build_ec2_curtailment_plan_from_envelope(
    envelope: EC2GirderReinforcementEnvelope,
    *,
    span_m: float,
    arrangement: LongitudinalBarArrangement,
    anchorage_length_mm: float,
) -> CurtailmentPlan:
    """Convert a complete EC2 station-demand envelope into bar-continuation zones."""

    if not envelope.singly_reinforced_complete:
        raise ValueError(
            "Curtailment cannot be generated while a station-wise EC2 demand is unresolved."
        )
    if not envelope.traffic_search_exhaustive:
        raise ValueError(
            "Curtailment cannot be certified from a reduced LM1 tandem search."
        )

    stations = tuple(
        LongitudinalDemandStation(
            x_m=item.x_m,
            required_area_mm2=float(item.governing_required_area_mm2),
        )
        for item in envelope.stations
        if item.governing_required_area_mm2 is not None
    )
    return build_symmetric_curtailment_plan(
        span_m=span_m,
        stations=stations,
        bar_diameter_mm=arrangement.bar_diameter_mm,
        total_bars=arrangement.bar_count,
        anchorage_length_mm=anchorage_length_mm,
    )
