from math import pi, tanh

import pytest

from rc_single_span.analysis.sections import (
    girder_profile_polygon_m,
    precast_girder_properties,
)
from rc_single_span.analysis.torsion import saint_venant_torsion_constant_polygon_m4
from rc_single_span.core.models import IGirderProfile, SingleSpanBridgeGeometry


def _exact_rectangle_j(long_side: float, short_side: float) -> float:
    a = max(long_side, short_side)
    b = min(long_side, short_side)
    series = sum(
        tanh(n * pi * a / (2.0 * b)) / n**5
        for n in range(1, 200, 2)
    )
    return a * b**3 * (
        1.0 / 3.0 - 64.0 * b / (pi**5 * a) * series
    )


def test_prandtl_fem_tracks_exact_rectangular_saint_venant_constant() -> None:
    width = 0.40
    depth = 1.20
    polygon = (
        (-width / 2.0, 0.0),
        (width / 2.0, 0.0),
        (width / 2.0, depth),
        (-width / 2.0, depth),
    )
    result = saint_venant_torsion_constant_polygon_m4(polygon)
    exact = _exact_rectangle_j(depth, width)

    assert result.torsion_constant_m4 == pytest.approx(exact, rel=0.015)
    assert result.fine_m4 > 0.0
    assert result.estimated_relative_error < 0.02


def test_haunched_i_precast_uses_connected_polygon_saint_venant_solution() -> None:
    profile = IGirderProfile(
        top_flange_width_m=0.40,
        top_flange_thickness_m=0.15,
        top_haunch_depth_m=0.15,
        web_width_m=0.25,
        web_depth_m=0.50,
        bottom_haunch_depth_m=0.20,
        bottom_flange_width_m=0.40,
        bottom_flange_thickness_m=0.20,
    )
    geometry = SingleSpanBridgeGeometry(
        span_m=20.0,
        deck_width_m=11.0,
        carriageway_width_m=7.0,
        girder_count=7,
        girder_spacing_m=1.70,
        girder_profile=profile,
    )
    properties = precast_girder_properties(geometry)
    direct = saint_venant_torsion_constant_polygon_m4(
        girder_profile_polygon_m(profile)
    )

    assert properties.torsion_constant_m4 == pytest.approx(
        direct.torsion_constant_m4,
        rel=1.0e-12,
    )
    assert "Prandtl stress-function FEM" in properties.basis
    assert properties.torsion_constant_m4 > 0.0
