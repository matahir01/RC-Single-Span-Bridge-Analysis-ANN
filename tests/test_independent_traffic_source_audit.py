"""Small code-loading checks taken from the JRC bridge worked example.

Source: JRC, Bridge Design to Eurocodes Worked Examples, Chapter 3,
Tables 3.6 and 3.8. These values are not derived from production code.
"""

import importlib.util
from pathlib import Path

import pytest

from rc_single_span.codes.common import LoadEffects
from rc_single_span.codes.eurocode.combinations import (
    EurocodeServiceabilityFactors,
    frequent_sls,
)
from rc_single_span.codes.eurocode.lm1 import (
    lm1_characteristic_lane_load,
    lm1_remaining_area_udl_kn_m2,
    notional_lane_layout,
)
from rc_single_span.traffic.lm1 import (
    LM1LanePlacement,
    LM1RemainingAreaPlacement,
    LM1SearchPlacement,
    build_lm1_plan_loads,
    frequent_lm1_adjustments,
)
from rc_single_span.verification.full_bridge_campaign import build_cross_stage_combination_rules


def reference_bridge_15m():
    path = Path(__file__).parents[1] / "examples" / "reference_bridge_15m.py"
    spec = importlib.util.spec_from_file_location("reference_bridge_15m", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.reference_bridge_15m()


def test_jrc_lm1_table_3_6_characteristic_values() -> None:
    assert [(lm1_characteristic_lane_load(i).axle_load_kn,
             lm1_characteristic_lane_load(i).udl_kn_m2)
            for i in (1, 2, 3, 4)] == [
                (300.0, 9.0), (200.0, 2.5), (100.0, 2.5), (0.0, 2.5)
            ]
    assert lm1_remaining_area_udl_kn_m2() == 2.5


def test_reference_carriageway_characteristic_lm1_load_accounting() -> None:
    project = reference_bridge_15m()
    layout = notional_lane_layout(7.0)
    assert (layout.lane_count, layout.lane_width_m, layout.remaining_width_m) == (
        2, 3.0, 1.0
    )
    placement = LM1SearchPlacement(
        1,
        (LM1LanePlacement(1, -3.5, -0.5, 7.0),
         LM1LanePlacement(2, -0.5, 2.5, 7.0)),
        (LM1RemainingAreaPlacement(2.5, 3.5),),
    )
    points, areas = build_lm1_plan_loads(project, placement)
    # Two 300-kN axles + two 200-kN axles; 15 m of lane/remaining UDL.
    assert sum(point.magnitude_kn for point in points) == pytest.approx(1000.0)
    assert sum((area.x_end_m - area.x_start_m)
               * (area.y_end_m - area.y_start_m)
               * area.pressure_kn_m2 for area in areas) == pytest.approx(555.0)


def test_jrc_table_3_8_requires_distinct_frequent_factors_for_lm1() -> None:
    tandem_kn = 1000.0
    udl_kn = 555.0
    # JRC Table 3.8: psi1 TS = 0.75, psi1 UDL = 0.40.
    source_based_frequent_kn = 0.75 * tandem_kn + 0.40 * udl_kn
    current_aggregate_factor_kn = 0.75 * (tandem_kn + udl_kn)
    assert source_based_frequent_kn == pytest.approx(972.0)
    assert current_aggregate_factor_kn == pytest.approx(1166.25)
    assert source_based_frequent_kn != current_aggregate_factor_kn


def test_frequent_load_generation_weights_tandem_and_udl_before_analysis() -> None:
    factors = EurocodeServiceabilityFactors(0.75, 0.0, psi1_udl_traffic=0.40)
    adjustments = frequent_lm1_adjustments(factors)
    project = reference_bridge_15m()
    placement = LM1SearchPlacement(
        1,
        (LM1LanePlacement(1, -3.5, -0.5, 7.0),
         LM1LanePlacement(2, -0.5, 2.5, 7.0)),
        (LM1RemainingAreaPlacement(2.5, 3.5),),
    )
    points, areas = build_lm1_plan_loads(project, placement, factors=adjustments)
    assert sum(p.magnitude_kn for p in points) == pytest.approx(750.0)
    assert sum((a.x_end_m - a.x_start_m) * (a.y_end_m - a.y_start_m)
               * a.pressure_kn_m2 for a in areas) == pytest.approx(222.0)


def test_scalar_frequent_and_staad_export_reject_distinct_lm1_factors() -> None:
    factors = EurocodeServiceabilityFactors(0.75, 0.0, psi1_udl_traffic=0.40)
    with pytest.raises(ValueError, match="separately weighted"):
        frequent_sls(LoadEffects(), LoadEffects(moment_knm=10.0), factors)
    with pytest.raises(ValueError, match="distinct weighted LM1"):
        build_cross_stage_combination_rules(eurocode_sls_factors=factors)
