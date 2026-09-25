"""Independent BS 5400 girder shear example supplied by the project owner.

Ragana River Bridge design calculations (Onyango/Olela, April 2015),
printed pp. 65-67. The report rounds the results to two decimals.
"""

import pytest

from rc_single_span.design.bs5400 import check_shear_bs5400


def test_ragana_report_girder_shear_and_required_links() -> None:
    # Printed p. 66: V=835 kN, average web width=329 mm, d=1349 mm,
    # provided longitudinal area=12861 mm², fcu=35 MPa, fyv=460 MPa.
    result = check_shear_bs5400(
        ved_kn=835.0,
        web_width_m=0.329,
        effective_depth_m=1.349,
        longitudinal_steel_area_mm2=12861.0,
        fcu_mpa=35.0,
        fyv_mpa=460.0,
    )
    # Printed p. 67: v=1.88 N/mm²; depth-adjusted vc=0.79 N/mm²;
    # required Asv/s=1.23 mm²/mm (the API reports mm²/m).
    assert result.design_shear_stress_mpa == pytest.approx(1.88, abs=0.01)
    assert result.concrete_design_shear_stress_mpa == pytest.approx(0.79, abs=0.01)
    assert result.governing_asv_per_s_mm2_per_m / 1000.0 == pytest.approx(
        1.23, abs=0.01
    )
