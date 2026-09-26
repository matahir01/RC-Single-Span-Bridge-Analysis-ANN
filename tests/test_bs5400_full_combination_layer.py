from types import SimpleNamespace

import pytest

from rc_single_span.codes.bs5400.secondary import (
    BS5400Combination4Action,
    custom_combination4_factors,
    build_bs5400_combination4,
)
from rc_single_span.codes.common import LoadEffects
from rc_single_span.core.models import (
    BridgeProject,
    DeckConstruction,
    MaterialProperties,
    RectangularGirderProfile,
    SingleSpanBridgeGeometry,
)
from rc_single_span.traffic.bs5400 import BS5400NominalTrafficSuite
from rc_single_span.traffic.bs5400_full_combinations import (
    BS5400Combination4EffectInput,
    build_bs5400_full_project_combinations,
)


def _project() -> BridgeProject:
    return BridgeProject(
        name="BS 5400 supplementary-combination benchmark",
        geometry=SingleSpanBridgeGeometry(
            span_m=15.0,
            physical_girder_length_m=14.95,
            deck_width_m=11.0,
            carriageway_width_m=7.0,
            girder_count=7,
            girder_spacing_m=1.70,
            girder_profile=RectangularGirderProfile(width_m=0.40, depth_m=0.95),
            deck=DeckConstruction(
                precast_false_slab_depth_m=0.075,
                in_situ_slab_depth_m=0.175,
                false_slab_composite_participation=False,
                in_situ_slab_composite_participation=True,
            ),
        ),
        materials=MaterialProperties(
            fck_mpa=35.0,
            fcu_mpa=45.0,
            fyk_mpa=460.0,
            concrete_density_kn_m3=24.0,
            elastic_modulus_mpa=31000.0,
        ),
    )


def _envelope(index: int, scale: float):
    component = lambda value: SimpleNamespace(value=value)
    return SimpleNamespace(
        girder_index=index,
        moment_knm=component(100.0 * scale + index),
        shear_kn=component(50.0 * scale + index),
        torsion_knm=component(10.0 * scale + index),
    )


def _traffic() -> BS5400NominalTrafficSuite:
    def result(scale: float):
        return SimpleNamespace(girders=tuple(_envelope(i, scale) for i in range(1, 8)))

    return BS5400NominalTrafficSuite(
        ha=result(1.0),
        hb=result(1.2),
        ha_hb=result(1.4),
        application_status="synthetic combination-layer regression",
    )


def test_full_project_layer_keeps_primary_1_to_3_and_adds_4_and_5() -> None:
    combo4 = {
        1: (
            BS5400Combination4EffectInput(
                action=BS5400Combination4Action.LONGITUDINAL_HA,
                secondary_nominal=LoadEffects(moment_knm=20.0, shear_kn=5.0),
                associated_primary_nominal=LoadEffects(moment_knm=40.0, shear_kn=10.0),
                provenance="BD 37/01 clause 6.10 benchmark response",
            ),
        )
    }
    combo5 = {1: LoadEffects(moment_knm=12.0, shear_kn=3.0)}
    result = build_bs5400_full_project_combinations(
        _project(),
        _traffic(),
        combination4_effects_by_girder=combo4,
        combination5_bearing_friction_by_girder=combo5,
        combination5_provenance="BD 37/01 5.4.8.3 bearing-friction benchmark response",
    )

    assert len(result) == 7
    first = result[0]
    assert {case.combination for case in first.primary.cases} == {1, 2, 3}
    assert {case.combination for case in first.supplementary} == {4, 5}
    assert len(first.supplementary) == 4  # ULS + SLS for each supplementary action
    assert any("combination 4" in case.result.name for case in first.supplementary)
    assert any("combination 5" in case.result.name for case in first.supplementary)
    assert len(first.all_uls_cases) == 11
    assert len(first.all_sls_cases) == 11
    assert result[1].supplementary == ()


def test_classified_combination4_action_can_use_distinct_primary_factor() -> None:
    factors = custom_combination4_factors(
        action_name="parapet_local_low_normal",
        secondary_gamma_uls=1.50,
        secondary_gamma_sls=1.20,
        associated_primary="HA",
        primary_gamma_uls=1.30,
        primary_gamma_sls=1.10,
        provenance="BD 37/01 Appendix A Table 1 clause 6.7.1",
    )
    result = build_bs5400_combination4(
        factored_permanent=LoadEffects(moment_knm=100.0),
        secondary_nominal=LoadEffects(moment_knm=20.0),
        associated_primary_nominal=LoadEffects(moment_knm=40.0),
        factors_override=factors,
        limit_state="uls",
        permanent_factor_audit={"structural_dead": 1.15},
    )
    assert result.effects.moment_knm == pytest.approx(182.0)
    assert result.factors["secondary_live"] == pytest.approx(1.50)
    assert result.factors["associated_primary_live"] == pytest.approx(1.30)
