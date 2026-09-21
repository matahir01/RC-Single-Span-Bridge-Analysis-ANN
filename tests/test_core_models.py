import math

import pytest

from rc_single_span.core.models import (
    BarLayer,
    DesignStandard,
    LongitudinalReinforcement,
    MaterialProperties,
    RectangularGirderProfile,
    SingleSpanBridgeGeometry,
)


def test_single_span_geometry_enforces_deck_and_layout() -> None:
    geometry = SingleSpanBridgeGeometry(
        span_m=15.0,
        deck_width_m=11.0,
        carriageway_width_m=7.0,
        girder_count=7,
        girder_spacing_m=1.70,
        girder_profile=RectangularGirderProfile(width_m=0.40, depth_m=0.95),
    )
    assert geometry.girder_line_width_m == pytest.approx(10.2)
    assert geometry.edge_overhang_m == pytest.approx(0.4)
    assert geometry.total_structural_depth_m == pytest.approx(1.20)


def test_materials_do_not_silently_convert_between_codes() -> None:
    materials = MaterialProperties(fcu_mpa=30.0, fyk_mpa=410.0)
    materials.require_for(DesignStandard.BS5400)
    with pytest.raises(ValueError, match="explicit fck_mpa"):
        materials.require_for(DesignStandard.EUROCODE)


def test_four_layers_of_four_y32_area() -> None:
    reinforcement = LongitudinalReinforcement(
        layers=[BarLayer(count=4, diameter_mm=32.0) for _ in range(4)]
    )
    expected = 16.0 * math.pi * 32.0**2 / 4.0
    assert reinforcement.total_area_mm2 == pytest.approx(expected)
    assert reinforcement.total_area_mm2 == pytest.approx(12867.96, rel=1.0e-5)
