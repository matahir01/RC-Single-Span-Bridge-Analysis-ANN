import pytest

from rc_single_span.design.bs_en_cracking import bs_en_crack_width_from_steel_stress


def test_bs_en_crack_formula_matches_ec2_worked_example_7_3() -> None:
    """Eurocode 2 Worked Examples, Example 7.3, published crack-width result.

    The source gives sigma_s = 234 MPa, lambda = 0.2012, gross rho = 0.0113,
    fct,eff = 2.9 MPa, alpha_e = 15, c = 40 mm, phi = 24 mm and kt = 0.6.
    Therefore rho_p,eff = rho/lambda. The published crack width is 0.184 mm.
    """

    result = bs_en_crack_width_from_steel_stress(
        steel_stress_mpa=234.0,
        effective_reinforcement_ratio=0.0113 / 0.2012,
        bar_diameter_mm=24.0,
        cover_mm=40.0,
        es_mpa=200000.0,
        modular_ratio=15.0,
        fct_eff_mpa=2.9,
        kt=0.6,
    )

    assert result.maximum_crack_spacing_mm == pytest.approx(208.6, abs=0.2)
    assert result.mean_strain_difference == pytest.approx(0.000885, abs=1.0e-6)
    assert result.crack_width_mm == pytest.approx(0.184, abs=0.001)
