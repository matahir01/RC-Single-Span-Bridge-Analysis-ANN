import sys
from pathlib import Path

import pytest

_EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
if str(_EXAMPLES) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES))

from thesis_bridge_15m import thesis_bridge_15m


def test_thesis_bridge_preserves_verified_reference_geometry() -> None:
    bridge = thesis_bridge_15m()
    geometry = bridge.geometry
    assert geometry.span_m == pytest.approx(15.0)
    assert geometry.physical_girder_length_m == pytest.approx(14.95)
    assert geometry.deck_width_m == pytest.approx(11.0)
    assert geometry.girder_count == 7
    assert geometry.girder_spacing_m == pytest.approx(1.70)
    assert geometry.girder_profile.width_m == pytest.approx(0.40)
    assert geometry.girder_profile.depth_m == pytest.approx(0.95)
    assert geometry.deck.physical_depth_m == pytest.approx(0.25)


def test_thesis_bridge_uses_c35_45_b500_material_basis() -> None:
    bridge = thesis_bridge_15m()
    assert bridge.materials.fck_mpa == pytest.approx(35.0)
    assert bridge.materials.fcu_mpa == pytest.approx(45.0)
    assert bridge.materials.fyk_mpa == pytest.approx(500.0)
    assert bridge.materials.concrete_density_kn_m3 == pytest.approx(25.0)
    assert bridge.materials.elastic_modulus_mpa == pytest.approx(34000.0)


def test_thesis_profile_does_not_strip_traceable_permanent_action_assumptions() -> None:
    bridge = thesis_bridge_15m()
    assert len(bridge.permanent_actions.surfacing_layers) == 1
    assert len(bridge.permanent_actions.line_actions) == 4
    assert all(
        "benchmark assumption" in item.name
        for item in (
            *bridge.permanent_actions.surfacing_layers,
            *bridge.permanent_actions.line_actions,
        )
    )
