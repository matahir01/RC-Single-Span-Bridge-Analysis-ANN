import numpy as np
import pytest

from rc_single_span.research.reliability import form_hlrf, monte_carlo_surrogate_reliability
from rc_single_span.research.sampling import (
    DistributionFamily,
    RandomVariable,
    latin_hypercube,
)


def test_latin_hypercube_is_reproducible_and_respects_truncation() -> None:
    variables = (
        RandomVariable(
            "strength",
            DistributionFamily.NORMAL,
            mean=35.0,
            cov=0.10,
            lower=25.0,
            upper=50.0,
        ),
        RandomVariable("load", DistributionFamily.LOGNORMAL, mean=1.0, cov=0.15),
        RandomVariable("width", DistributionFamily.UNIFORM, lower=0.35, upper=0.45),
    )
    first = latin_hypercube(variables, 100, seed=7)
    second = latin_hypercube(variables, 100, seed=7)
    assert np.allclose(first.values, second.values)
    assert np.all((first.values[:, 0] >= 25.0) & (first.values[:, 0] <= 50.0))
    assert np.all(first.values[:, 1] > 0.0)
    assert np.all((first.values[:, 2] >= 0.35) & (first.values[:, 2] <= 0.45))


def test_form_matches_linear_independent_normal_solution() -> None:
    variables = (
        RandomVariable("resistance", "normal", mean=100.0, std=10.0),
        RandomVariable("load", "normal", mean=70.0, std=8.0),
    )
    result = form_hlrf(lambda x: float(x[0] - x[1]), variables)
    analytical = 30.0 / np.sqrt(10.0**2 + 8.0**2)
    assert result.converged
    assert result.beta == pytest.approx(analytical, rel=2.0e-3)
    assert abs(result.limit_state_value) < 1.0e-4


class _LinearSurrogate:
    feature_names = ("resistance", "load")
    target_names = ("g",)

    def predict(self, features: np.ndarray) -> np.ndarray:
        values = np.asarray(features, dtype=float)
        one = values.ndim == 1
        if one:
            values = values.reshape(1, -1)
        output = (values[:, 0] - values[:, 1]).reshape(-1, 1)
        return output[0] if one else output


def test_surrogate_monte_carlo_reliability_is_close_to_linear_solution() -> None:
    variables = (
        RandomVariable("resistance", "normal", mean=100.0, std=10.0),
        RandomVariable("load", "normal", mean=70.0, std=8.0),
    )
    result = monte_carlo_surrogate_reliability(
        _LinearSurrogate(),
        variables,
        "g",
        50000,
        seed=11,
    )
    analytical_beta = 30.0 / np.sqrt(10.0**2 + 8.0**2)
    assert result.reliability_index == pytest.approx(analytical_beta, abs=0.12)
    assert result.confidence_low <= result.probability_of_failure <= result.confidence_high
