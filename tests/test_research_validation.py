from dataclasses import dataclass

import numpy as np

from rc_single_span.research.evaluator import LimitStateEvaluation
from rc_single_span.research.sampling import RandomVariable
from rc_single_span.research.validation import (
    direct_monte_carlo_reliability,
    validate_surrogate_against_direct,
)


@dataclass
class _LinearEvaluator:
    feature_names: tuple[str, ...] = ("resistance", "load")
    target_names: tuple[str, ...] = ("g",)

    def evaluate(self, sample: dict[str, float]) -> LimitStateEvaluation:
        return LimitStateEvaluation(True, {"g": sample["resistance"] - sample["load"]})


class _ExactSurrogate:
    feature_names = ("resistance", "load")
    target_names = ("g",)

    def predict(self, features: np.ndarray) -> np.ndarray:
        values = np.asarray(features, dtype=float)
        one = values.ndim == 1
        if one:
            values = values.reshape(1, -1)
        prediction = (values[:, 0] - values[:, 1]).reshape(-1, 1)
        return prediction[0] if one else prediction


def _variables() -> tuple[RandomVariable, ...]:
    return (
        RandomVariable("resistance", "normal", mean=100.0, std=10.0),
        RandomVariable("load", "normal", mean=70.0, std=8.0),
    )


def test_fresh_direct_surrogate_validation_reports_zero_error_for_exact_model() -> None:
    result = validate_surrogate_against_direct(
        _LinearEvaluator(),
        _ExactSurrogate(),
        _variables(),
        500,
        seed=3,
    )
    assert result.invalid_count == 0
    assert result.metrics.r2[0] == 1.0
    assert result.maximum_absolute_error[0] < 1.0e-12


def test_direct_monte_carlo_reliability_matches_linear_normal_solution() -> None:
    result = direct_monte_carlo_reliability(
        _LinearEvaluator(),
        _variables(),
        "g",
        50000,
        seed=4,
    )
    analytical_beta = 30.0 / np.sqrt(10.0**2 + 8.0**2)
    assert abs(result.reliability_index - analytical_beta) < 0.12
