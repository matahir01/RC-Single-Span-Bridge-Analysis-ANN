from __future__ import annotations

from dataclasses import dataclass
from math import floor


@dataclass(frozen=True)
class NotionalLaneLayout:
    carriageway_width_m: float
    lane_count: int
    lane_width_m: float
    remaining_width_m: float


@dataclass(frozen=True)
class LM1LaneLoad:
    lane_number: int
    axle_load_kn: float
    udl_kn_m2: float


@dataclass(frozen=True)
class LM1AdjustmentFactors:
    alpha_q1: float = 1.0
    alpha_q2: float = 1.0
    alpha_q3: float = 1.0
    alpha_q_other: float = 1.0
    alpha_q_remaining: float = 1.0
    alpha_Q1: float = 1.0
    alpha_Q2: float = 1.0
    alpha_Q3: float = 1.0


def notional_lane_layout(carriageway_width_m: float) -> NotionalLaneLayout:
    w = float(carriageway_width_m)
    if w < 3.0:
        raise ValueError("Carriageway width must be at least 3.0 m.")
    if w < 5.4:
        return NotionalLaneLayout(w, 1, 3.0, w - 3.0)
    if w < 6.0:
        return NotionalLaneLayout(w, 2, w / 2.0, 0.0)
    count = floor(w / 3.0)
    return NotionalLaneLayout(w, count, 3.0, w - 3.0 * count)


def lm1_characteristic_lane_load(
    lane_number: int,
    factors: LM1AdjustmentFactors | None = None,
) -> LM1LaneLoad:
    if lane_number < 1:
        raise ValueError("lane_number must be positive.")
    f = factors or LM1AdjustmentFactors()
    if lane_number == 1:
        return LM1LaneLoad(1, 300.0 * f.alpha_Q1, 9.0 * f.alpha_q1)
    if lane_number == 2:
        return LM1LaneLoad(2, 200.0 * f.alpha_Q2, 2.5 * f.alpha_q2)
    if lane_number == 3:
        return LM1LaneLoad(3, 100.0 * f.alpha_Q3, 2.5 * f.alpha_q3)
    return LM1LaneLoad(lane_number, 0.0, 2.5 * f.alpha_q_other)


def lm1_remaining_area_udl_kn_m2(
    factors: LM1AdjustmentFactors | None = None,
) -> float:
    return 2.5 * (factors or LM1AdjustmentFactors()).alpha_q_remaining
