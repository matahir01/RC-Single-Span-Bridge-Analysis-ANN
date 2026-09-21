import importlib.util
from pathlib import Path

import pytest

from rc_single_span.core.models import DesignStandard


def _load_reference():
    path = Path(__file__).parents[1] / "examples" / "reference_bridge_15m.py"
    spec = importlib.util.spec_from_file_location("reference_bridge_15m", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.reference_bridge_15m()


def test_reference_bridge_is_dual_code_ready_without_hidden_conversion() -> None:
    bridge = _load_reference()
    bridge.materials.require_for(DesignStandard.EUROCODE)
    bridge.materials.require_for(DesignStandard.BS5400)

    assert bridge.geometry.span_m == pytest.approx(15.0)
    assert bridge.geometry.physical_girder_length_m == pytest.approx(14.95)
    assert bridge.geometry.girder_spacing_m == pytest.approx(1.70)
    assert bridge.geometry.girder_profile.width_m == pytest.approx(0.40)
    assert bridge.geometry.girder_profile.depth_m == pytest.approx(0.95)
    assert bridge.materials.fck_mpa == pytest.approx(25.0)
    assert bridge.materials.fcu_mpa == pytest.approx(30.0)
    assert bridge.materials.fyk_mpa == pytest.approx(410.0)
