import pytest

from rc_single_span.research.evaluator import FEATURE_NAMES
from rc_single_span.research.sampling import RandomVariable
from rc_single_span.research.source_profiles import (
    build_jcss_reference_variables,
    jcss_c35_concrete_prior,
    jcss_concrete_dimension_variable,
    jcss_effective_depth_variable,
    jcss_model_uncertainty_variables,
    jcss_rebar_area_variable,
    jcss_rebar_yield_variable,
)


def test_jcss_c35_ready_mixed_prior_matches_logspace_approximation() -> None:
    prior = jcss_c35_concrete_prior("ready_mixed")
    assert prior.approximate_log_standard_deviation == pytest.approx(0.1232375754)
    assert prior.approximate_mean_mpa == pytest.approx(47.35127517)
    assert prior.approximate_cov == pytest.approx(0.1237069770)
    variable = prior.as_random_variable()
    assert variable.mean == pytest.approx(prior.approximate_mean_mpa)
    assert variable.cov == pytest.approx(prior.approximate_cov)


def test_jcss_c35_precast_prior_is_distinct_from_ready_mixed() -> None:
    ready = jcss_c35_concrete_prior("ready_mixed")
    precast = jcss_c35_concrete_prior("precast")
    assert precast.approximate_mean_mpa == pytest.approx(52.24791574)
    assert precast.approximate_cov == pytest.approx(0.1098739681)
    assert precast.approximate_mean_mpa > ready.approximate_mean_mpa


def test_jcss_rebar_profiles_use_source_statistics() -> None:
    yield_strength = jcss_rebar_yield_variable(500.0)
    area = jcss_rebar_area_variable(12868.0)
    assert yield_strength.mean == pytest.approx(560.0)
    assert yield_strength.std == pytest.approx(30.0)
    assert area.mean == pytest.approx(12868.0)
    assert area.cov == pytest.approx(0.02)


def test_jcss_optional_rebar_diameter_correction_is_explicit() -> None:
    corrected = jcss_rebar_yield_variable(500.0, bar_diameter_mm=32.0)
    assert corrected.mean == pytest.approx(636.32775886)
    assert corrected.std == pytest.approx(30.0)


def test_jcss_dimension_and_effective_depth_defaults_are_absolute_mm_models() -> None:
    width = jcss_concrete_dimension_variable("web_width_m", 0.400)
    depth = jcss_effective_depth_variable(1.100)
    assert width.mean == pytest.approx(0.4012)
    assert width.std == pytest.approx(0.0064)
    assert depth.mean == pytest.approx(1.110)
    assert depth.std == pytest.approx(0.010)


def test_jcss_model_uncertainty_profiles_match_documented_generic_values() -> None:
    variables = {item.name: item for item in jcss_model_uncertainty_variables()}
    assert variables["moment_load_model_factor"].mean == pytest.approx(1.0)
    assert variables["moment_load_model_factor"].cov == pytest.approx(0.10)
    assert variables["shear_load_model_factor"].cov == pytest.approx(0.10)
    assert variables["flexure_resistance_model_factor"].mean == pytest.approx(1.2)
    assert variables["flexure_resistance_model_factor"].cov == pytest.approx(0.15)
    assert variables["shear_resistance_model_factor"].cov == pytest.approx(0.10)


def test_reference_builder_preserves_exact_evaluator_feature_order() -> None:
    variables = build_jcss_reference_variables(
        concrete_production="precast",
        nominal_effective_depth_m=1.10,
        nominal_web_width_m=0.40,
        nominal_steel_area_mm2=12868.0,
        dead_load_variable=RandomVariable(
            "dead_load_factor", "normal", mean=1.0, cov=0.04
        ),
        live_load_variable=RandomVariable(
            "live_load_factor", "lognormal", mean=1.0, cov=0.15
        ),
    )
    assert tuple(item.name for item in variables) == FEATURE_NAMES
    assert variables[0].mean == pytest.approx(52.24791574)
    assert variables[1].mean == pytest.approx(560.0)
    assert variables[2].mean == pytest.approx(1.110)
    assert variables[3].mean == pytest.approx(0.4012)
    assert variables[4].cov == pytest.approx(0.02)


def test_reference_builder_refuses_to_invent_or_misname_action_models() -> None:
    dead = RandomVariable("wrong_dead", "normal", mean=1.0, cov=0.04)
    live = RandomVariable("live_load_factor", "lognormal", mean=1.0, cov=0.15)
    with pytest.raises(ValueError, match="dead_load_factor"):
        build_jcss_reference_variables(
            concrete_production="ready_mixed",
            nominal_effective_depth_m=1.10,
            nominal_web_width_m=0.40,
            nominal_steel_area_mm2=12868.0,
            dead_load_variable=dead,
            live_load_variable=live,
        )
