import pytest

from rc_single_span.analysis.sections import ConcreteLayer
from rc_single_span.design.bs_en_cracking import bs_en_crack_width_from_steel_stress
from rc_single_span.design.eurocode import check_crack_width_ec2


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


def test_production_close_spacing_crack_check_uses_source_pinned_formula() -> None:
    """Protect the project design path from drifting away from the pinned formula."""

    layers = (ConcreteLayer(0.30, 0.0, 0.60, "rectangular check section"),)
    production = check_crack_width_ec2(
        layers=layers,
        total_depth_m=0.60,
        steel_area_mm2=2000.0,
        steel_depth_m=0.55,
        bar_diameter_mm=20.0,
        bar_spacing_mm=100.0,
        cover_mm=40.0,
        service_moment_knm=300.0,
        es_mpa=200000.0,
        ecm_mpa=30000.0,
        fct_eff_mpa=2.9,
        crack_limit_mm=0.30,
        kt=0.6,
    )
    assert production.close_spacing
    assert production.crack_width_mm > 0.0

    pinned = bs_en_crack_width_from_steel_stress(
        steel_stress_mpa=production.steel_stress_mpa,
        effective_reinforcement_ratio=production.effective_reinforcement_ratio,
        bar_diameter_mm=20.0,
        cover_mm=40.0,
        es_mpa=200000.0,
        modular_ratio=200000.0 / 30000.0,
        fct_eff_mpa=2.9,
        kt=0.6,
    )
    assert production.max_crack_spacing_mm == pytest.approx(
        pinned.maximum_crack_spacing_mm
    )
    assert production.crack_width_mm == pytest.approx(pinned.crack_width_mm)
