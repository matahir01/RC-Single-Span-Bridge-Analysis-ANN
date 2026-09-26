from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
from scipy.stats import norm

from rc_single_span.research.evaluator import LimitStateEvaluation
from rc_single_span.research.reliability import SurrogatePredictor
from rc_single_span.research.sampling import RandomVariable, independent_random_samples
from rc_single_span.research.surrogate import RegressionMetrics, regression_metrics


class DirectLimitStateEvaluator(Protocol):
    feature_names: tuple[str, ...]
    target_names: tuple[str, ...]

    def evaluate(self, sample: dict[str, float]) -> LimitStateEvaluation: ...


@dataclass(frozen=True)
class DirectMonteCarloResult:
    target_name: str
    sample_count: int
    failure_count: int
    probability_of_failure: float
    reliability_index: float
    invalid_count: int
    seed: int | None


@dataclass(frozen=True)
class SurrogateValidationResult:
    metrics: RegressionMetrics
    sample_count: int
    invalid_count: int
    maximum_absolute_error: tuple[float, ...]
    near_limit_state_sample_count: tuple[int, ...]
    near_limit_state_maximum_absolute_error: tuple[float | None, ...]


def _validate_order(
    evaluator: DirectLimitStateEvaluator,
    variables: tuple[RandomVariable, ...],
) -> None:
    names = tuple(variable.name for variable in variables)
    if names != evaluator.feature_names:
        raise ValueError("Random variables must exactly match evaluator.feature_names.")


def direct_monte_carlo_reliability(
    evaluator: DirectLimitStateEvaluator,
    variables: tuple[RandomVariable, ...],
    target_name: str,
    sample_count: int,
    *,
    seed: int | None = None,
    invalid_policy: str = "raise",
) -> DirectMonteCarloResult:
    """Run Monte Carlo directly through the deterministic limit-state evaluator.

    This is intended as a validation reference for ANN-based reliability, not as
    a substitute for a more detailed stochastic structural model when the thesis
    methodology requires full re-analysis of each sample.
    """

    if invalid_policy not in {"raise", "skip"}:
        raise ValueError("invalid_policy must be 'raise' or 'skip'.")
    _validate_order(evaluator, variables)
    try:
        target_index = evaluator.target_names.index(target_name)
    except ValueError as exc:
        raise KeyError(target_name) from exc

    samples = independent_random_samples(variables, sample_count, seed=seed)
    failures = 0
    valid = 0
    invalid = 0
    for row_index, sample in enumerate(samples.records()):
        result = evaluator.evaluate(sample)
        if not result.valid:
            invalid += 1
            if invalid_policy == "raise":
                raise ValueError(
                    f"Invalid direct Monte-Carlo sample at row {row_index}: {result.message}"
                )
            continue
        valid += 1
        target = result.target_vector(evaluator.target_names)[target_index]
        failures += int(target <= 0.0)

    if valid == 0:
        raise ValueError("Direct Monte Carlo produced no valid samples.")
    probability = failures / valid
    probability_for_beta = (failures + 0.5) / (valid + 1.0)
    beta = -float(norm.ppf(probability_for_beta))
    return DirectMonteCarloResult(
        target_name=target_name,
        sample_count=valid,
        failure_count=failures,
        probability_of_failure=probability,
        reliability_index=beta,
        invalid_count=invalid,
        seed=seed,
    )


def validate_surrogate_against_direct(
    evaluator: DirectLimitStateEvaluator,
    surrogate: SurrogatePredictor,
    variables: tuple[RandomVariable, ...],
    sample_count: int,
    *,
    seed: int | None = None,
    near_limit_state_fraction: float = 0.10,
) -> SurrogateValidationResult:
    """Compare ANN outputs with fresh direct points, including near g=0 points.

    ``near_limit_state_fraction`` is applied to each target's direct absolute
    target range: a point is classed as near-limit-state when ``|g|`` is within
    that fraction of the largest ``|g|`` observed in this validation sample.
    """

    if not 0.0 < near_limit_state_fraction < 1.0:
        raise ValueError("near_limit_state_fraction must lie in (0, 1).")
    _validate_order(evaluator, variables)
    if surrogate.feature_names != evaluator.feature_names:
        raise ValueError("Surrogate feature names do not match the direct evaluator.")
    if surrogate.target_names != evaluator.target_names:
        raise ValueError("Surrogate target names do not match the direct evaluator.")

    samples = independent_random_samples(variables, sample_count, seed=seed)
    feature_rows: list[tuple[float, ...]] = []
    direct_rows: list[tuple[float, ...]] = []
    invalid = 0
    for sample in samples.records():
        result = evaluator.evaluate(sample)
        if not result.valid:
            invalid += 1
            continue
        feature_rows.append(tuple(sample[name] for name in evaluator.feature_names))
        direct_rows.append(result.target_vector(evaluator.target_names))

    if not direct_rows:
        raise ValueError("Surrogate validation produced no valid direct samples.")
    features = np.asarray(feature_rows, dtype=float)
    direct = np.asarray(direct_rows, dtype=float)
    predicted = np.asarray(surrogate.predict(features), dtype=float)
    metrics = regression_metrics(direct, predicted, evaluator.target_names)
    absolute_error = np.abs(predicted - direct)
    maxima = tuple(map(float, np.max(absolute_error, axis=0)))

    near_counts: list[int] = []
    near_maxima: list[float | None] = []
    for column in range(direct.shape[1]):
        scale = float(np.max(np.abs(direct[:, column])))
        threshold = near_limit_state_fraction * max(scale, 1.0e-12)
        mask = np.abs(direct[:, column]) <= threshold
        count = int(np.count_nonzero(mask))
        near_counts.append(count)
        near_maxima.append(
            None if count == 0 else float(np.max(absolute_error[mask, column]))
        )

    return SurrogateValidationResult(
        metrics=metrics,
        sample_count=len(direct_rows),
        invalid_count=invalid,
        maximum_absolute_error=maxima,
        near_limit_state_sample_count=tuple(near_counts),
        near_limit_state_maximum_absolute_error=tuple(near_maxima),
    )
