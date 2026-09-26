"""Independent BS 5400-4 crack-width benchmark.

Source basis:
- BS 5400-4:1990, clause 5.8.8.2, equations 24 and 25.
- Published Bridge 403 worked calculation, sagging SLS slab example:
  h = 400 mm, b = 1000 mm, d = 342 mm, As = 1340 mm2/m,
  Es = 200 GPa, modified Ec = 14 GPa, Mg = 25 kNm/m,
  Mq = 45 kNm/m, T16 at 150 mm, nominal cover = 50 mm.

The worked calculation reports compression depth about 96.9 mm,
a_cr about 87 mm and crack width about 0.22 mm.
"""

import pytest

from rc_single_span.analysis.sections import ConcreteLayer
from rc_single_span.design.bs5400 import check_crack_width_bs5400


def test_bs5400_crack_width_reproduces_independent_bridge_example() -> None:
    result = check_crack_width_bs5400(
        layers=(ConcreteLayer(1.0, 0.0, 0.4, "worked slab strip"),),
        total_depth_m=0.4,
        steel_area_mm2=1340.0,
        steel_depth_m=0.342,
        permanent_moment_knm=25.0,
        live_moment_knm=45.0,
        es_mpa=200000.0,
        ec_modified_mpa=14000.0,
        tension_zone_width_m=1.0,
        crack_point_depth_mm=400.0,
        nominal_cover_mm=50.0,
        bar_spacing_mm=150.0,
        bar_diameter_mm=16.0,
        allowable_crack_width_mm=0.25,
    )

    assert result.compression_depth_mm == pytest.approx(96.9, abs=0.2)
    assert result.acr_mm == pytest.approx(87.0, abs=0.3)
    assert result.crack_width_mm == pytest.approx(0.22, abs=0.01)
    assert result.passes
