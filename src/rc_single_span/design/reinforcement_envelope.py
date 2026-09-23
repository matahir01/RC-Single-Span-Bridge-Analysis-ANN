from __future__ import annotations

from dataclasses import dataclass

from rc_single_span.analysis.permanent import (
    PermanentLoadCategory,
    factored_permanent_moment_at_x_knm,
)
from rc_single_span.analysis.sections import final_composite_concrete_layers
from rc_single_span.codes.bs5400.combinations import (
    BS5400LimitState,
    BS5400PermanentGammaFL,
    BS5400PrimaryTraffic,
    primary_live_gamma_fl,
)
from rc_single_span.codes.eurocode.combinations import EurocodeCombinationFactors
from rc_single_span.core.models import BridgeProject
from rc_single_span.design.bs5400 import required_steel_area_layered_bs5400
from rc_single_span.design.detailing import LongitudinalBarArrangement
from rc_single_span.design.eurocode import required_steel_area_layered_ec2
from rc_single_span.design.longitudinal_detailing import (
    CurtailmentPlan,
    LongitudinalDemandStation,
    build_symmetric_curtailment_plan,
)
from rc_single_span.traffic.bs5400 import BS5400NominalTrafficSuite
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


@dataclass(frozen=True)
class BS5400StationReinforcementDemand:
    x_m: float
    permanent_uls_moment_knm: float
    traffic_nominal_moment_knm: float
    traffic_uls_moment_knm: float
    total_uls_moment_knm: float
    traffic: BS5400PrimaryTraffic
    combination: int
    traffic_case_id: int
    flexural_required_area_mm2: float | None
    governing_required_area_mm2: float | None
    issue: str | None


@dataclass(frozen=True)
class BS5400GirderReinforcementEnvelope:
    girder_index: int
    stations: tuple[BS5400StationReinforcementDemand, ...]
    design_stations_m: tuple[float, ...]
    maximum_required_area_mm2: float | None
    maximum_required_station_m: float | None
    singly_reinforced_complete: bool
    traffic_search_exhaustive: bool
    basis: str


def _bs_station_component(
    suite: BS5400NominalTrafficSuite,
    *,
    traffic: BS5400PrimaryTraffic,
    girder_index: int,
    x_m: float,
):
    search = (
        suite.ha
        if traffic is BS5400PrimaryTraffic.HA
        else suite.hb
        if traffic is BS5400PrimaryTraffic.HB
        else suite.ha_hb
    )
    girder = next(
        (item for item in search.station_moments if item.girder_index == girder_index),
        None,
    )
    if girder is None:
        raise ValueError("BS traffic search is missing the requested girder station envelope.")
    for station in girder.stations:
        if abs(station.x_m - x_m) <= 1.0e-9:
            return station.moment_knm
    raise ValueError(
        "BS traffic search does not contain the requested common design station."
    )


def _bs_common_design_stations(
    suite: BS5400NominalTrafficSuite,
) -> tuple[float, ...]:
    grids = (
        suite.ha.design_stations_m,
        suite.hb.design_stations_m,
        suite.ha_hb.design_stations_m,
    )
    if not all(grids):
        raise ValueError(
            "BS 5400 reinforcement zoning requires an explicit common design-station grid."
        )
    reference = grids[0]
    for grid in grids[1:]:
        if len(grid) != len(reference) or any(
            abs(a - b) > 1.0e-9 for a, b in zip(reference, grid, strict=True)
        ):
            raise ValueError(
                "HA, HB and HA+HB searches do not share an identical design-station grid."
            )
    return reference


def build_bs5400_station_reinforcement_envelope(
    project: BridgeProject,
    traffic: BS5400NominalTrafficSuite,
    *,
    girder_index: int,
    effective_depth_m: float,
    minimum_area_mm2: float,
    permanent_factors: BS5400PermanentGammaFL | None = None,
    combinations: tuple[int, ...] = (1, 2, 3),
    maximum_neutral_axis_ratio: float = 0.50,
) -> BS5400GirderReinforcementEnvelope:
    """Build exact common-grid BS 5400 ULS longitudinal steel demand.

    HA, HB and HA+HB are compared at the same explicit design x-stations. No
    interpolation between dissimilar traffic grids is used.
    """

    if not 1 <= girder_index <= int(project.geometry.girder_count):
        raise IndexError("girder_index is outside the physical bridge.")
    if effective_depth_m <= 0.0 or minimum_area_mm2 <= 0.0:
        raise ValueError("BS 5400 station-reinforcement inputs must be positive.")
    if not combinations or any(item not in (1, 2, 3) for item in combinations):
        raise ValueError("BS 5400 reinforcement envelope supports combinations 1-3.")
    if not 0.0 < maximum_neutral_axis_ratio <= 1.0:
        raise ValueError("maximum_neutral_axis_ratio must lie in (0, 1].")

    design_stations = _bs_common_design_stations(traffic)
    factors = permanent_factors or BS5400PermanentGammaFL()
    named = factors.as_named_factors(BS5400LimitState.ULS)
    permanent_factor_map = {
        PermanentLoadCategory.STRUCTURAL_DEAD: named["structural_dead"],
        PermanentLoadCategory.SURFACING: named["surfacing"],
        PermanentLoadCategory.OTHER_SUPERIMPOSED: named["other_superimposed"],
    }
    layers = final_composite_concrete_layers(
        project.geometry,
        girder_index=girder_index,
    )
    fcu = float(project.materials.fcu_mpa)
    fy = float(project.materials.fyk_mpa)

    demands: list[BS5400StationReinforcementDemand] = []
    for x_m in design_stations:
        permanent_uls = factored_permanent_moment_at_x_knm(
            project,
            girder_index=girder_index,
            x_m=x_m,
            factors_by_category=permanent_factor_map,
        )
        governing_candidate: BS5400StationReinforcementDemand | None = None

        for traffic_case in BS5400PrimaryTraffic:
            component = _bs_station_component(
                traffic,
                traffic=traffic_case,
                girder_index=girder_index,
                x_m=x_m,
            )
            for combination in combinations:
                gamma_live = primary_live_gamma_fl(
                    traffic=traffic_case,
                    combination=combination,
                    limit_state=BS5400LimitState.ULS,
                )
                traffic_uls = gamma_live * component.value
                total_uls = permanent_uls + traffic_uls

                issue: str | None = None
                required: float | None
                governing_area: float | None
                try:
                    required = required_steel_area_layered_bs5400(
                        med_knm=total_uls,
                        layers=layers,
                        effective_depth_m=effective_depth_m,
                        fcu_mpa=fcu,
                        fy_mpa=fy,
                        maximum_neutral_axis_ratio=maximum_neutral_axis_ratio,
                    )
                    governing_area = max(required, minimum_area_mm2)
                except ValueError as exc:
                    required = None
                    governing_area = None
                    issue = str(exc)

                candidate = BS5400StationReinforcementDemand(
                    x_m=x_m,
                    permanent_uls_moment_knm=permanent_uls,
                    traffic_nominal_moment_knm=component.value,
                    traffic_uls_moment_knm=traffic_uls,
                    total_uls_moment_knm=total_uls,
                    traffic=traffic_case,
                    combination=combination,
                    traffic_case_id=component.case_id,
                    flexural_required_area_mm2=required,
                    governing_required_area_mm2=governing_area,
                    issue=issue,
                )
                if (
                    governing_candidate is None
                    or candidate.total_uls_moment_knm
                    > governing_candidate.total_uls_moment_knm
                ):
                    governing_candidate = candidate

        if governing_candidate is None:
            raise RuntimeError("No BS 5400 traffic candidate was available at a design station.")
        demands.append(governing_candidate)

    valid = tuple(
        item for item in demands if item.governing_required_area_mm2 is not None
    )
    maximum = (
        max(valid, key=lambda item: float(item.governing_required_area_mm2))
        if valid
        else None
    )
    exhaustive = (
        traffic.ha.kel_combinations_exhaustive
        and traffic.ha_hb.ha_assignment_search_exhaustive
        and traffic.ha_hb.kel_combinations_exhaustive
    )
    complete = bool(demands) and all(item.issue is None for item in demands)

    return BS5400GirderReinforcementEnvelope(
        girder_index=girder_index,
        stations=tuple(demands),
        design_stations_m=design_stations,
        maximum_required_area_mm2=(
            None if maximum is None else float(maximum.governing_required_area_mm2)
        ),
        maximum_required_station_m=None if maximum is None else maximum.x_m,
        singly_reinforced_complete=complete,
        traffic_search_exhaustive=exhaustive,
        basis=(
            "Exact common-grid BS 5400 ULS reinforcement envelope. Permanent actions "
            "are factored by category at each x-station. HA, HB and HA+HB nominal "
            "moments are compared with their traffic-specific gamma_fL values for "
            "combinations 1-3. No interpolation between dissimilar traffic grids is used."
        ),
    )


def build_bs5400_curtailment_plan_from_envelope(
    envelope: BS5400GirderReinforcementEnvelope,
    *,
    span_m: float,
    arrangement: LongitudinalBarArrangement,
    anchorage_length_mm: float,
) -> CurtailmentPlan:
    if not envelope.singly_reinforced_complete:
        raise ValueError(
            "Curtailment cannot be generated while a BS station-wise demand is unresolved."
        )
    if not envelope.traffic_search_exhaustive:
        raise ValueError(
            "Curtailment cannot be certified from a reduced BS traffic search."
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
