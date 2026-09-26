import pytest

from rc_single_span.design.project import BS5400DesignInputs, EC2DesignInputs
from rc_single_span.gui.design_adapter import GuiDesignInputs


def test_disabled_gui_design_inputs_do_not_create_code_inputs() -> None:
    inputs = GuiDesignInputs(enabled=False)
    assert inputs.for_profile("BS EN 1990 / 1991-2 / 1992-2") is None
    assert inputs.for_profile("BS 5400 / BD 37") is None


def test_gui_design_inputs_map_to_bs_en() -> None:
    resolved = GuiDesignInputs(
        enabled=True,
        deflection_limit_mm=50.0,
        deflection_limit_basis="Project criterion L/300",
    ).for_profile("BS EN 1990 / 1991-2 / 1992-2")
    assert isinstance(resolved, EC2DesignInputs)
    assert resolved.effective_depth_m == pytest.approx(1.10)
    assert resolved.crack_limit_mm == pytest.approx(0.30)
    assert resolved.deflection_limit_mm == pytest.approx(50.0)
    assert resolved.deflection_limit_basis == "Project criterion L/300"


def test_gui_design_inputs_map_to_bs5400() -> None:
    resolved = GuiDesignInputs(enabled=True).for_profile("BS 5400 / BD 37")
    assert isinstance(resolved, BS5400DesignInputs)
    assert resolved.effective_depth_m == pytest.approx(1.10)
    assert resolved.allowable_crack_width_mm == pytest.approx(0.25)
    assert resolved.shear_reinforcement_fyv_mpa == pytest.approx(460.0)


def test_gui_design_inputs_require_deflection_provenance_pair() -> None:
    with pytest.raises(ValueError, match="deflection basis"):
        GuiDesignInputs(deflection_limit_basis="authority")
