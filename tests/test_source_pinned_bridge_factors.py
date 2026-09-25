"""Literal factor checks from the cited bridge code worked sources.

JRC, Bridge Design to Eurocodes: Worked Examples (2012), Chapter 3,
Table 3.8 and Section 3.9.3, pp. 61-63.
Highways Agency, BD 37/01 CR01 (May 2004), Appendix A,
clauses 5.1.2, 5.2.2, 6.2.7, 6.3.4 and 6.4.2.
"""

import pytest

from rc_single_span.codes.common import LoadEffects
from rc_single_span.codes.eurocode.combinations import (
    EurocodeCombinationFactors,
    EurocodeServiceabilityFactors,
    build_eurocode_combination_set,
)
from rc_single_span.codes.bs5400.combinations import (
    BS5400PermanentGammaFL,
    primary_live_gamma_fl,
)


def test_jrc_road_bridge_leading_lm1_factors_and_distinct_sls() -> None:
    factors = EurocodeCombinationFactors()
    assert (factors.gamma_g_unfavourable,
            factors.gamma_g_favourable,
            factors.gamma_q_traffic) == (1.35, 1.0, 1.35)
    psi = EurocodeServiceabilityFactors(0.75, 0.0, psi1_udl_traffic=0.40)
    assert psi.frequent_components_differ
    # Characteristic and quasi-permanent equations can be checked directly;
    # frequent LM1 requires separately weighted TS/UDL traffic analysis.
    with pytest.raises(ValueError, match="separately weighted"):
        build_eurocode_combination_set(
            LoadEffects(moment_knm=10.0),
            LoadEffects(moment_knm=20.0), sls_factors=psi,
        )


def test_bd37_primary_and_permanent_factors_are_not_interchanged() -> None:
    permanent = BS5400PermanentGammaFL()
    assert permanent.as_named_factors("uls") == {
        "structural_dead": 1.15, "surfacing": 1.75,
        "other_superimposed": 1.20,
    }
    assert permanent.as_named_factors("sls") == {
        "structural_dead": 1.00, "surfacing": 1.20,
        "other_superimposed": 1.00,
    }
    for combination, ha_uls, ha_sls, hb_uls, hb_sls in (
        (1, 1.50, 1.20, 1.30, 1.10),
        (2, 1.25, 1.00, 1.10, 1.00),
        (3, 1.25, 1.00, 1.10, 1.00),
    ):
        assert primary_live_gamma_fl(traffic="ha", combination=combination,
                                     limit_state="uls") == ha_uls
        assert primary_live_gamma_fl(traffic="ha", combination=combination,
                                     limit_state="sls") == ha_sls
        for traffic in ("hb", "ha_hb"):
            assert primary_live_gamma_fl(traffic=traffic, combination=combination,
                                         limit_state="uls") == hb_uls
            assert primary_live_gamma_fl(traffic=traffic, combination=combination,
                                         limit_state="sls") == hb_sls
