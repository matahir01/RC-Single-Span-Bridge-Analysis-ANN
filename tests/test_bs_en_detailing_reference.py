"""Source-pinned BS EN reinforcement-detailing checks.

The tension-shift expression is reproduced in the JRC report *Eurocode 2:
Background & Applications - Design of Concrete Buildings, Worked Examples*,
Section 4.2.2 (detailing of beams), citing EN 1992-1-1 9.2.1.3(2):

a_l = z (cot(theta) - cot(alpha)) / 2.

For vertical links alpha = 90 degrees, so with z = 0.9d the report gives
``a_l = 0.45 d cot(theta)``.  The bridge path uses the same EC2 truss-model
shift rule; bridge-specific anchorage and continuation requirements remain
separate explicit inputs.
"""

import pytest

from rc_single_span.design.advanced_detailing import ec2_tension_shift_length_m


def test_jrc_vertical_link_tension_shift_identity() -> None:
    effective_depth_m = 1.0
    lever_arm_m = 0.9 * effective_depth_m
    cot_theta = 2.0

    result = ec2_tension_shift_length_m(
        lever_arm_m=lever_arm_m,
        cot_theta=cot_theta,
        cot_alpha=0.0,
    )

    assert result == pytest.approx(
        0.45 * effective_depth_m * cot_theta
    )
    assert result == pytest.approx(0.90)
