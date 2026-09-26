import numpy as np
import pytest

from rc_single_span.research.dependence import GaussianCopula
from rc_single_span.research.sampling import (
    RandomVariable,
    independent_random_samples,
    latin_hypercube,
    standard_normal_to_physical,
)


def _variables() -> tuple[RandomVariable, ...]:
    return (
        RandomVariable("x", "normal", mean=0.0, std=1.0),
        RandomVariable("y", "normal", mean=0.0, std=1.0),
    )


def test_gaussian_copula_rejects_invalid_matrix() -> None:
    with pytest.raises(ValueError, match="symmetric"):
        GaussianCopula(("x", "y"), np.array([[1.0, 0.5], [0.2, 1.0]]))
    with pytest.raises(ValueError, match="positive definite"):
        GaussianCopula(("x", "y"), np.array([[1.0, 1.0], [1.0, 1.0]]))


def test_correlated_monte_carlo_reproduces_requested_latent_correlation() -> None:
    variables = _variables()
    dependence = GaussianCopula(
        ("x", "y"),
        np.array([[1.0, 0.70], [0.70, 1.0]]),
    )
    samples = independent_random_samples(
        variables,
        30000,
        seed=1234,
        dependence=dependence,
    )
    correlation = float(np.corrcoef(samples.values.T)[0, 1])
    assert correlation == pytest.approx(0.70, abs=0.02)
    assert samples.method == "gaussian_copula_random"


def test_lhs_accepts_same_dependence_model_and_preserves_marginal_centres() -> None:
    variables = _variables()
    dependence = GaussianCopula(
        ("x", "y"),
        np.array([[1.0, -0.5], [-0.5, 1.0]]),
    )
    samples = latin_hypercube(variables, 5000, seed=7, dependence=dependence)
    assert samples.method == "latin_hypercube_gaussian_copula"
    assert np.mean(samples.values[:, 0]) == pytest.approx(0.0, abs=0.06)
    assert np.mean(samples.values[:, 1]) == pytest.approx(0.0, abs=0.06)
    assert float(np.corrcoef(samples.values.T)[0, 1]) == pytest.approx(-0.5, abs=0.04)


def test_form_transform_uses_independent_u_and_correlated_latent_space() -> None:
    variables = _variables()
    dependence = GaussianCopula(
        ("x", "y"),
        np.array([[1.0, 0.6], [0.6, 1.0]]),
    )
    physical = standard_normal_to_physical(
        variables,
        np.array([1.0, 0.0]),
        dependence=dependence,
    )
    assert physical[0] == pytest.approx(1.0)
    assert physical[1] == pytest.approx(0.6)


def test_dependence_variable_order_must_match() -> None:
    dependence = GaussianCopula(
        ("y", "x"),
        np.array([[1.0, 0.2], [0.2, 1.0]]),
    )
    with pytest.raises(ValueError, match="names/order"):
        latin_hypercube(_variables(), 20, dependence=dependence)
