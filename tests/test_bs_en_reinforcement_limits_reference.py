"""Source-pinned BS EN / EC2 reinforcement-detailing limits.

The JRC *Bridge Design to Eurocodes - Worked Examples*, concrete bridge chapter,
reproduces the recommended EN 1992-1-1 beam/slab minimum bending steel rule

    As,min = max(0.26 fctm/fyk, 0.0013) bt d.

The coefficients are Nationally Determined Parameter-sensitive where the
standard permits national choice, so the production functions expose them as
arguments instead of treating their defaults as a Nigerian National Annex.

For beam shear detailing, EN 1992-1-1 9.2.2 uses the recommended minimum link
ratio 0.08 sqrt(fck)/fyk and maximum longitudinal spacing 0.75d for vertical
links.  The same rules are used by the BS EN bridge route where applicable.
"""

import pytest

from rc_single_span.design.eurocode_detailing import (
    longitudinal_limits_ec2,
    shear_detailing_limits_ec2,
)


def test_jrc_recommended_minimum_longitudinal_steel_expression() -> None:
    result = longitudinal_limits_ec2(
        fctm_mpa=3.2,
        fyk_mpa=500.0,
        tension_zone_width_m=1.0,
        effective_depth_m=0.35,
        concrete_area_m2=0.40,
    )

    expected_ratio = max(0.26 * 3.2 / 500.0, 0.0013)
    assert expected_ratio == pytest.approx(0.001664)
    assert result.governing_minimum_ratio == pytest.approx(expected_ratio)
    assert result.minimum_tension_steel_mm2 == pytest.approx(
        expected_ratio * 1000.0 * 350.0
    )
    assert result.maximum_longitudinal_steel_mm2 == pytest.approx(16000.0)


def test_bs_en_vertical_link_minimum_ratio_and_spacing_are_explicit() -> None:
    result = shear_detailing_limits_ec2(
        fck_mpa=35.0,
        fyk_mpa=500.0,
        web_width_m=0.40,
        effective_depth_m=1.10,
    )

    expected_rho = 0.08 * 35.0**0.5 / 500.0
    assert result.minimum_rho_w == pytest.approx(expected_rho)
    assert result.minimum_asw_per_s_mm2_per_m == pytest.approx(
        expected_rho * 400.0 * 1000.0
    )
    assert result.maximum_longitudinal_link_spacing_mm == pytest.approx(825.0)
    # The production default also applies its explicit 600 mm transverse cap.
    assert result.maximum_transverse_leg_spacing_mm == pytest.approx(600.0)
