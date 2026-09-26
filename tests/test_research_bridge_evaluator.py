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


def _sample(dead: float = 1.0, live: float = 1.0) -> dict[str, float]:
    return {
        "fck_mpa": 35.0,
        "fyk_mpa": 500.0,
        "effective_depth_m": 1.08,
        "web_width_m": 0.40,
        "steel_area_mm2": 12868.0,
        "dead_load_factor": dead,
        "live_load_factor": live,
    }


def test_bridge_reliability_evaluator_returns_three_limit_states() -> None:
    evaluator = BridgeLimitStateEvaluator(
        _baseline(),
        ReliabilityModelConfig(
            deflection_limit_mm=50.0,
            provided_asw_per_s_mm2_per_m=1500.0,
        ),
    )
    result = evaluator.evaluate(_sample())
    assert result.valid, result.message
    assert set(evaluator.target_names) <= set(result.values)
    assert all(np.isfinite(result.values[name]) for name in evaluator.target_names)


def test_more_load_reduces_all_limit_state_margins() -> None:
    evaluator = BridgeLimitStateEvaluator(
        _baseline(),
        ReliabilityModelConfig(
            deflection_limit_mm=50.0,
            provided_asw_per_s_mm2_per_m=1500.0,
        ),
    )
    base = evaluator.evaluate(_sample())
    heavier = evaluator.evaluate(_sample(dead=1.15, live=1.20))
    assert base.valid and heavier.valid
    for target in evaluator.target_names:
        assert heavier.values[target] < base.values[target]
