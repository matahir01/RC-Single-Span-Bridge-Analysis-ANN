"""Published beam flexure example, The Concrete Centre, 2017 Lecture 3, p. 24.

https://www.concretecentre.com/TCC/media/TCCMediaLibrary/PDF%20attachments/
Lecture-3-Bending-and-Shear-in-Beams-PHG-A8-Oct17.pdf
"""

import pytest

from rc_single_span.analysis.sections import ConcreteLayer
from rc_single_span.design.eurocode import (
    check_layered_flexure_ec2,
    required_steel_area_layered_ec2,
)
from rc_single_span.design.project import EC2DesignInputs


def test_published_rectangular_beam_flexure_with_documented_alpha_cc() -> None:
    # MEd 1410 kNm, b 450 mm, h 1000 mm, d 934 mm,
    # C30/37 and fy 500 MPa; published approximate As 3943 mm2, z 822 mm.
    layers = (ConcreteLayer(0.45, 0.0, 1.0, "published beam"),)
    result = check_layered_flexure_ec2(
        med_knm=1410.0, layers=layers, effective_depth_m=0.934,
        steel_area_mm2=3943.0, fck_mpa=30.0, fyk_mpa=500.0,
        alpha_cc=0.85, maximum_neutral_axis_ratio=0.45,
    )
    assert result.lever_arm_m == pytest.approx(0.822, abs=0.002)
    assert result.resistance_knm == pytest.approx(1410.0, abs=2.0)
    required = required_steel_area_layered_ec2(
        med_knm=1410.0, layers=layers, effective_depth_m=0.934,
        fck_mpa=30.0, fyk_mpa=500.0,
        maximum_neutral_axis_ratio=0.45, alpha_cc=0.85,
    )
    assert required == pytest.approx(3943.0, abs=10.0)


def test_project_design_explicitly_accepts_the_strength_factor() -> None:
    fields = {
        "effective_depth_m": 0.934, "bar_diameter_mm": 32.0,
        "bar_spacing_mm": 100.0, "cover_mm": 40.0,
        "fct_eff_mpa": 2.9, "crack_limit_mm": 0.3,
        "maximum_neutral_axis_ratio": 0.45,
    }
    assert EC2DesignInputs(**fields, alpha_cc=0.85).alpha_cc == 0.85
    with pytest.raises(ValueError, match="alpha_cc"):
        EC2DesignInputs(**fields, alpha_cc=0.0)
