"""Literal factor checks from the cited bridge code worked sources.

JRC, Bridge Design to Eurocodes: Worked Examples (2012), Chapter 3,
Table 3.8 and Section 3.9.3, pp. 61-63. The software records the British
adoption of those first-generation provisions as BS EN 1990 / BS EN 1991-2.
Highways Agency, BD 37/01 CR01 (May 2004), Appendix A,
clauses 5.1.2, 5.2.2, 6.2.7, 6.3.4 and 6.4.2.
"""

import pytest

from rc_single_span.codes.bs5400.combinations import (
    BS5400PermanentGammaFL,
    primary_live_gamma_fl,
)
from rc_single_span.codes.common import LoadEffects
from rc_single_span.codes.eurocode.basis import (
    BS_EN_1990,
    BS_EN_1991_2,
    BS_EN_1992_2,
)
from rc_single_span.codes.eurocode.combinations import (
    EurocodeCombinationFactors,
    EurocodeServiceabilityFactors,
    build_eurocode_combination_set,
    characteristic_sls,
    frequent_sls,
    persistent_uls,
    quasi_permanent_sls,
)


def test_bs_en_bridge_basis_identifiers_are_explicit() -> None:
    assert BS_EN_1990 == "BS EN 1990:2002+A1:2005"
    assert BS_EN_1991_2 == "BS EN 1991-2:2003"
    assert BS_EN_1992_2 == "BS EN 1992-2:2005"


def test_jrc_road_bridge_leading_lm1_factors_and_distinct_sls() -> None:
    factors = EurocodeCombinationFactors()
    assert (
        factors.gamma_g_unfavourable,
        factors.gamma_g_favourable,
        factors.gamma_q_traffic,
    ) == (1.35, 1.0, 1.35)
    psi = EurocodeServiceabilityFactors(0.75, 0.0, psi1_udl_traffic=0.40)
    assert psi.frequent_components_differ
    # Characteristic and quasi-permanent equations can be checked directly;
    # frequent LM1 requires separately weighted TS/UDL traffic analysis.
    with pytest.raises(ValueError, match="separately weighted"):
        build_eurocode_combination_set(
            LoadEffects(moment_knm=10.0),
            LoadEffects(moment_knm=20.0),
            sls_factors=psi,
        )


def test_bs_en_1990_combination_arithmetic_is_not_only_factor_metadata() -> None:
    permanent = LoadEffects(moment_knm=100.0, shear_kn=50.0, torsion_knm=20.0)
    traffic = LoadEffects(moment_knm=200.0, shear_kn=80.0, torsion_knm=30.0)

    uls = persistent_uls(permanent, traffic)
    assert uls.name.startswith(BS_EN_1990)
    assert uls.effects == LoadEffects(
        moment_knm=405.0,
        shear_kn=175.5,
        torsion_knm=67.5,
    )

    characteristic = characteristic_sls(permanent, traffic)
    assert characteristic.name.startswith(BS_EN_1990)
    assert characteristic.effects == LoadEffects(
        moment_knm=300.0,
        shear_kn=130.0,
        torsion_knm=50.0,
    )

    scalar_frequent = frequent_sls(
        permanent,
        traffic,
        EurocodeServiceabilityFactors(psi1_traffic=0.75, psi2_traffic=0.0),
    )
    assert scalar_frequent.effects == LoadEffects(
        moment_knm=250.0,
        shear_kn=110.0,
        torsion_knm=42.5,
    )

    quasi = quasi_permanent_sls(
        permanent,
        traffic,
        EurocodeServiceabilityFactors(psi1_traffic=0.75, psi2_traffic=0.0),
    )
    assert quasi.effects == permanent


def test_bd37_primary_and_permanent_factors_are_not_interchanged() -> None:
    permanent = BS5400PermanentGammaFL()
    assert permanent.as_named_factors("uls") == {
        "structural_dead": 1.15,
        "surfacing": 1.75,
        "other_superimposed": 1.20,
    }
    assert permanent.as_named_factors("sls") == {
        "structural_dead": 1.00,
        "surfacing": 1.20,
        "other_superimposed": 1.00,
    }
    for combination, ha_uls, ha_sls, hb_uls, hb_sls in (
        (1, 1.50, 1.20, 1.30, 1.10),
        (2, 1.25, 1.00, 1.10, 1.00),
        (3, 1.25, 1.00, 1.10, 1.00),
    ):
        assert primary_live_gamma_fl(
            traffic="ha",
            combination=combination,
            limit_state="uls",
        ) == ha_uls
        assert primary_live_gamma_fl(
            traffic="ha",
            combination=combination,
            limit_state="sls",
        ) == ha_sls
        for traffic in ("hb", "ha_hb"):
            assert primary_live_gamma_fl(
                traffic=traffic,
                combination=combination,
                limit_state="uls",
            ) == hb_uls
            assert primary_live_gamma_fl(
                traffic=traffic,
                combination=combination,
                limit_state="sls",
            ) == hb_sls
