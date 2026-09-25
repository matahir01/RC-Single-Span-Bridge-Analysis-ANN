"""EC2 slab-strip shear benchmark from the European Commission JRC.

Bridge Design to Eurocodes Worked Examples, Chapter 5, section 5.2.2.7,
printed pp. 107-109. The concrete-only EC2 expression also applies to beams.
The example uses its stated recommended values and French NA selections.
"""

import pytest

from rc_single_span.design.eurocode import check_shear_ec2


def test_jrc_concrete_shear_and_link_demand() -> None:
    # Source: fck 35 MPa, d 360 mm, bw 1000 mm, As 1848 mm2,
    # VEd 235 kN, fyk 500 MPa (fyd approximately 435 MPa), cot(theta)=2.5.
    result = check_shear_ec2(
        ved_kn=235.0,
        web_width_m=1.0,
        effective_depth_m=0.36,
        longitudinal_steel_area_mm2=1848.0,
        fck_mpa=35.0,
        fyk_mpa=500.0,
        cot_theta=2.5,
    )
    assert result.k == pytest.approx(1.74536, abs=0.001)
    assert result.rho_l == pytest.approx(0.0051333, abs=0.00001)
    assert result.vrdc_kn == pytest.approx(198.0, abs=2.0)
    assert result.required_asw_per_s_mm2_per_m == pytest.approx(667.3, abs=2.0)
    assert not result.concrete_only_passes
    assert result.web_crushing_passes
