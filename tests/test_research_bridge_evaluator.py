import numpy as np

from rc_single_span.core.models import (
    BridgeProject,
    DeckConstruction,
    MaterialProperties,
    RectangularGirderProfile,
    SingleSpanBridgeGeometry,
)
from rc_single_span.research.baseline import BSENReliabilityBaseline
from rc_single_span.research.evaluator import BridgeLimitStateEvaluator, ReliabilityModelConfig


def _baseline() -> BSENReliabilityBaseline:
    project = BridgeProject(
        name="research evaluator unit bridge",
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
            fyk_mpa=500.0,
            concrete_density_kn_m3=25.0,
            elastic_modulus_mpa=34000.0,
        ),
    )
    return BSENReliabilityBaseline(
        project=project,
        moment_girder_index=4,
        shear_girder_index=4,
        deflection_girder_index=4,
        permanent_moment_knm=500.0,
        traffic_moment_knm=700.0,
        permanent_shear_kn=180.0,
        traffic_shear_kn=220.0,
        permanent_deflection_mm=8.0,
        traffic_deflection_mm=12.0,
        nominal_deflection_iy_m4=0.12,
        provenance="synthetic unit-test baseline",
    )


def _sample(dead: float = 1.0, live: float = 1.0, **updates: float) -> dict[str, float]:
    sample = {
        "fck_mpa": 35.0,
        "fyk_mpa": 500.0,
        "effective_depth_m": 1.08,
        "web_width_m": 0.40,
        "steel_area_mm2": 12868.0,
        "dead_load_factor": dead,
        "live_load_factor": live,
        "moment_load_model_factor": 1.0,
        "shear_load_model_factor": 1.0,
        "flexure_resistance_model_factor": 1.0,
        "shear_resistance_model_factor": 1.0,
    }
    sample.update(updates)
    return sample


def _evaluator() -> BridgeLimitStateEvaluator:
    return BridgeLimitStateEvaluator(
        _baseline(),
        ReliabilityModelConfig(
            deflection_limit_mm=50.0,
            provided_asw_per_s_mm2_per_m=1500.0,
        ),
    )


def test_bridge_reliability_evaluator_returns_three_limit_states() -> None:
    evaluator = _evaluator()
    result = evaluator.evaluate(_sample())
    assert result.valid, result.message
    assert set(evaluator.target_names) <= set(result.values)
    assert all(np.isfinite(result.values[name]) for name in evaluator.target_names)


def test_more_load_reduces_all_limit_state_margins() -> None:
    evaluator = _evaluator()
    base = evaluator.evaluate(_sample())
    heavier = evaluator.evaluate(_sample(dead=1.15, live=1.20))
    assert base.valid and heavier.valid
    for target in evaluator.target_names:
        assert heavier.values[target] < base.values[target]


def test_load_effect_model_uncertainty_reduces_matching_margin_only() -> None:
    evaluator = _evaluator()
    base = evaluator.evaluate(_sample())
    moment = evaluator.evaluate(_sample(moment_load_model_factor=1.10))
    shear = evaluator.evaluate(_sample(shear_load_model_factor=1.10))
    assert base.valid and moment.valid and shear.valid
    assert moment.values["g_flexure_knm"] < base.values["g_flexure_knm"]
    assert moment.values["g_shear_kn"] == base.values["g_shear_kn"]
    assert shear.values["g_shear_kn"] < base.values["g_shear_kn"]
    assert shear.values["g_flexure_knm"] == base.values["g_flexure_knm"]
    assert moment.values["g_deflection_mm"] == base.values["g_deflection_mm"]


def test_resistance_model_uncertainty_scales_matching_resistance() -> None:
    evaluator = _evaluator()
    base = evaluator.evaluate(_sample())
    flexure = evaluator.evaluate(_sample(flexure_resistance_model_factor=1.20))
    shear = evaluator.evaluate(_sample(shear_resistance_model_factor=0.90))
    assert base.valid and flexure.valid and shear.valid
    assert flexure.values["moment_resistance_knm"] == np.testing.assert_allclose(
        flexure.values["moment_resistance_knm"],
        1.20 * base.values["nominal_moment_resistance_knm"],
    )
    assert shear.values["shear_resistance_kn"] == np.testing.assert_allclose(
        shear.values["shear_resistance_kn"],
        0.90 * base.values["nominal_shear_resistance_kn"],
    )
