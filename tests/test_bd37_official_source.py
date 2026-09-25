"""Source-based checks from the archived Highways Agency BD 37/01 CR01.

Official archive: https://www.standardsforhighways.co.uk/tses/attachments/
d9448824-a259-4cd3-938b-15daeacd90a0?inline=true
Appendix A clauses 3.2.9.3, 6.2.1-6.4.2; pp. A/11, A/55-A/62.
"""

import pytest

from rc_single_span.codes.bs5400.combinations import primary_live_gamma_fl
from rc_single_span.codes.bs5400.traffic import (
    ha_hb_coexistent_gamma_fl,
    ha_kel_kn,
    ha_lane_factor_bd37_01,
    ha_udl_kn_m,
    hb_vehicle_definition,
    notional_lane_layout_bd37_01,
)


def test_bd37_two_lanes_and_short_span_ha() -> None:
    lane = notional_lane_layout_bd37_01(7.0)
    assert (lane.lane_count, lane.lane_width_m) == (2, 3.5)
    assert ha_udl_kn_m(15.0) == pytest.approx(336.0 * 15.0**-0.67)
    assert ha_kel_kn() == 120.0
    for rank in (1, 2):
        assert ha_lane_factor_bd37_01(
            factor_rank=rank, loaded_length_m=15.0,
            lane_width_m=lane.lane_width_m, total_notional_lanes=2,
        ) == pytest.approx(0.959)


def test_bd37_lanes_and_factor_table_boundaries() -> None:
    for width, count in ((5.0, 2), (7.5, 2), (7.5001, 3),
                         (10.95, 3), (10.9501, 4), (21.9, 6)):
        assert notional_lane_layout_bd37_01(width).lane_count == count
    assert ha_lane_factor_bd37_01(
        factor_rank=2, loaded_length_m=75.0,
        lane_width_m=3.5, total_notional_lanes=2,
    ) == pytest.approx(7.1 / 75.0**0.5)
    assert ha_lane_factor_bd37_01(
        factor_rank=2, loaded_length_m=75.0,
        lane_width_m=3.5, total_notional_lanes=6,
    ) == 1.0


def test_bd37_hb_dimensions_and_coexistent_factors() -> None:
    hb = hb_vehicle_definition(units=30.0, inner_axle_spacing_m=6.0)
    assert hb.overall_length_m == 10.0
    assert hb.overall_width_m == 3.5
    assert hb.axle_offsets_m == (0.0, 1.8, 7.8, 9.6)
    assert hb.total_vehicle_load_kn == 1200.0
    assert ha_hb_coexistent_gamma_fl(combination=1, limit_state="uls") == 1.30
    assert ha_hb_coexistent_gamma_fl(combination=1, limit_state="sls") == 1.10
    assert primary_live_gamma_fl(traffic="ha", combination=1, limit_state="uls") == 1.50
    assert primary_live_gamma_fl(traffic="ha", combination=1, limit_state="sls") == 1.20
