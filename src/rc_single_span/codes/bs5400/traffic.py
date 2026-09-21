from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BS5400TrafficProfile(str, Enum):
    BS5400_1978 = "bs5400_part2_1978"
    BD37_01_2001 = "bd37_01_2001_composite"


@dataclass(frozen=True)
class BS5400NotionalLaneLayout:
    carriageway_width_m: float
    lane_count: int
    lane_width_m: float
    remaining_width_m: float


@dataclass(frozen=True)
class HALaneLoad:
    factor_rank: int
    lane_factor: float
    udl_kn_m: float
    kel_kn: float
    loaded_length_m: float


@dataclass(frozen=True)
class HBVehicleDefinition:
    units: float
    inner_axle_spacing_m: float
    wheel_load_kn: float
    axle_load_kn: float
    total_vehicle_load_kn: float
    overall_width_m: float
    overall_length_m: float
    axle_offsets_m: tuple[float, ...]
    wheel_y_offsets_m: tuple[float, ...]


HB_INNER_AXLE_SPACINGS_M = (6.0, 11.0, 16.0, 21.0, 26.0)


def notional_lane_layout_bd37_01(
    carriageway_width_m: float,
) -> BS5400NotionalLaneLayout:
    w = float(carriageway_width_m)
    if w < 2.5:
        raise ValueError("Carriageway width below 2.5 m is outside this BD 37/01 implementation.")
    if w < 5.0:
        return BS5400NotionalLaneLayout(w, 1, 2.5, max(w - 2.5, 0.0))

    for upper, count in (
        (7.50, 2),
        (10.95, 3),
        (14.60, 4),
        (18.25, 5),
        (21.90, 6),
    ):
        if w <= upper:
            return BS5400NotionalLaneLayout(w, count, w / count, 0.0)
    raise ValueError("Carriageway widths above 21.90 m need an extended BD 37/01 lane rule set.")


def ha_udl_kn_m(
    loaded_length_m: float,
    *,
    traffic_profile: BS5400TrafficProfile = BS5400TrafficProfile.BD37_01_2001,
) -> float:
    length = float(loaded_length_m)
    if length <= 0.0:
        raise ValueError("loaded_length_m must be positive.")

    if traffic_profile is BS5400TrafficProfile.BS5400_1978:
        if length <= 30.0:
            return 30.0
        return max(151.0 * length ** (-0.475), 9.0)

    if traffic_profile is BS5400TrafficProfile.BD37_01_2001:
        if length <= 50.0:
            return 336.0 * length ** (-0.67)
        if length <= 1600.0:
            return 36.0 * length ** (-0.10)
        raise ValueError("BD 37/01 loaded lengths above 1600 m require authority agreement.")

    raise ValueError(f"Unsupported traffic profile: {traffic_profile}")


def ha_kel_kn() -> float:
    return 120.0


def ha_lane_factor_bd37_01(
    *,
    factor_rank: int,
    loaded_length_m: float,
    lane_width_m: float,
    total_notional_lanes: int,
) -> float:
    if factor_rank < 1 or factor_rank > total_notional_lanes:
        raise ValueError("HA factor rank must identify one available notional lane.")
    if loaded_length_m <= 0.0 or lane_width_m <= 0.0:
        raise ValueError("Loaded length and lane width must be positive.")

    length = float(loaded_length_m)
    alpha1 = min(0.274 * lane_width_m, 1.0)
    alpha2 = 0.0137 * (
        lane_width_m * (40.0 - length) + 3.65 * (length - 20.0)
    )

    if length <= 20.0:
        if factor_rank in (1, 2):
            return alpha1
        if factor_rank == 3:
            return 0.60
        return 0.60 * alpha1
    if length <= 40.0:
        if factor_rank in (1, 2):
            return alpha2
        if factor_rank == 3:
            return 0.60
        return 0.60 * alpha2
    if length <= 50.0:
        return 1.0 if factor_rank in (1, 2) else 0.60
    if length <= 112.0:
        if factor_rank == 1:
            return 1.0
        if factor_rank == 2:
            return 1.0 if total_notional_lanes >= 6 else 7.1 / length**0.5
        return 0.60
    if factor_rank == 1:
        return 1.0
    if factor_rank == 2:
        return 1.0 if total_notional_lanes >= 6 else 0.67
    return 0.60


def ha_lane_load_bd37_01(
    *,
    factor_rank: int,
    loaded_length_m: float,
    lane_width_m: float,
    total_notional_lanes: int,
) -> HALaneLoad:
    factor = ha_lane_factor_bd37_01(
        factor_rank=factor_rank,
        loaded_length_m=loaded_length_m,
        lane_width_m=lane_width_m,
        total_notional_lanes=total_notional_lanes,
    )
    return HALaneLoad(
        factor_rank=factor_rank,
        lane_factor=factor,
        udl_kn_m=ha_udl_kn_m(loaded_length_m) * factor,
        kel_kn=ha_kel_kn() * factor,
        loaded_length_m=loaded_length_m,
    )


def hb_vehicle_definition(
    *,
    units: float,
    inner_axle_spacing_m: float,
) -> HBVehicleDefinition:
    if units <= 0.0 or units > 45.0:
        raise ValueError("HB units must be greater than zero and no more than 45.")
    if inner_axle_spacing_m not in HB_INNER_AXLE_SPACINGS_M:
        raise ValueError(
            f"HB inner axle spacing must be one of {HB_INNER_AXLE_SPACINGS_M} m."
        )

    wheel_load = 2.5 * units
    axle_load = 4.0 * wheel_load
    offsets = (
        0.0,
        1.8,
        1.8 + inner_axle_spacing_m,
        3.6 + inner_axle_spacing_m,
    )
    return HBVehicleDefinition(
        units=units,
        inner_axle_spacing_m=inner_axle_spacing_m,
        wheel_load_kn=wheel_load,
        axle_load_kn=axle_load,
        total_vehicle_load_kn=4.0 * axle_load,
        overall_width_m=3.5,
        overall_length_m=inner_axle_spacing_m + 4.0,
        axle_offsets_m=offsets,
        wheel_y_offsets_m=(-1.5, -0.5, 0.5, 1.5),
    )
