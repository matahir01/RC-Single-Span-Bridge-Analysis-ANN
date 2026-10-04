from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
from scipy.optimize import differential_evolution
from scipy.stats import norm

from rc_single_span.core.progress import AnalysisControl
from rc_single_span.research.dependence import GaussianCopula
from rc_single_span.research.evaluator import LimitStateEvaluation
from rc_single_span.research.reliability import SurrogatePredictor, _wilson_interval
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
    confidence_low: float
    confidence_high: float
    confidence_level: float
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


@dataclass(frozen=True)
class BoundaryChallenge:
    target_name: str
    marginal_quantile_range: tuple[float, float]
    candidate_minimum: float
    candidate_maximum: float
    bracket_found: bool
    features: tuple[float, ...] | None
    direct_margin: float | None
    surrogate_margin: float | None
    absolute_error: float | None


def challenge_surrogate_at_direct_boundaries(
    evaluator: DirectLimitStateEvaluator,
    surrogate: SurrogatePredictor,
    variables: tuple[RandomVariable, ...],
    *,
    marginal_tail: float = 0.001,
    iterations: int = 30,
    seed: int = 20261001,
    control: AnalysisControl | None = None,
) -> tuple[BoundaryChallenge, ...]:
    """Find direct g=0 brackets, then test the ANN at independently found roots.

    A bounded marginal-quantile hyperrectangle is searched with a reproducible
    global heuristic. Its endpoints are candidates, not certified extrema.
    A joint corner is not a probability sample, and dependence is deliberately
    not inferred from this diagnostic. Missing brackets remain explicit.
    """

    _validate_order(evaluator, variables)
    if surrogate.feature_names != evaluator.feature_names or surrogate.target_names != evaluator.target_names:
        raise ValueError("Surrogate names do not match the direct evaluator.")
    if not 0.0 < marginal_tail < 0.5 or iterations <= 0:
        raise ValueError("Require a positive iteration count and marginal_tail in (0, 0.5).")

    def physical(probabilities: np.ndarray) -> np.ndarray:
        return np.asarray([
            float(variable.from_unit_interval(probability))
            for variable, probability in zip(variables, probabilities, strict=True)
        ])

    def direct(features: np.ndarray, target_name: str) -> float | None:
        result = evaluator.evaluate(dict(zip(evaluator.feature_names, map(float, features), strict=True)))
        if not result.valid:
            return None
        value = float(result.values[target_name])
        return value if np.isfinite(value) else None

    output: list[BoundaryChallenge] = []
    objective_evaluations = 0
    for index, target_name in enumerate(evaluator.target_names):
        endpoints: list[tuple[np.ndarray, float]] = []
        for sign in (1.0, -1.0):
            def objective(
                probabilities: np.ndarray,
                bound_name: str = target_name,
                bound_sign: float = sign,
                phase_name: str = target_name,
            ) -> float:
                nonlocal objective_evaluations
                objective_evaluations += 1
                if control is not None:
                    control.report(
                        f"Direct boundary challenge: {phase_name}",
                        objective_evaluations,
                        30000,
                    )
                value = direct(physical(probabilities), bound_name)
                return bound_sign * value if value is not None else 1.0e30

            search = differential_evolution(
                objective,
                [(marginal_tail, 1.0 - marginal_tail)] * len(variables),
                seed=seed + 2 * index + (0 if sign > 0 else 1),
                maxiter=iterations,
                popsize=5,
                polish=False,
            )
            point = physical(search.x)
            margin = direct(point, target_name)
            if margin is None:
                raise ValueError(f"No valid direct candidate found for {target_name}.")
            endpoints.append((point, margin))
        (low_point, low), (high_point, high) = endpoints
        if low > 0.0 or high < 0.0:
            output.append(BoundaryChallenge(
                target_name, (marginal_tail, 1.0 - marginal_tail),
                low, high, False, None, None, None, None,
            ))
            continue
        for _ in range(40):
            midpoint = 0.5 * (low_point + high_point)
            margin = direct(midpoint, target_name)
            if margin is None:
                raise ValueError(f"Invalid direct evaluation on {target_name} bracket.")
            if margin <= 0.0:
                low_point, low = midpoint, margin
            else:
                high_point, high = midpoint, margin
        root = 0.5 * (low_point + high_point)
        true_margin = direct(root, target_name)
        assert true_margin is not None
        prediction = np.asarray(surrogate.predict(root), dtype=float)
        predicted_margin = float(prediction[index])
        output.append(BoundaryChallenge(
            target_name, (marginal_tail, 1.0 - marginal_tail),
            endpoints[0][1], endpoints[1][1], True,
            tuple(map(float, root)), true_margin, predicted_margin,
            abs(predicted_margin - true_margin),
        ))
    return tuple(output)


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
    confidence: float = 0.95,
    invalid_policy: str = "raise",
    dependence: GaussianCopula | None = None,
    control: AnalysisControl | None = None,
) -> DirectMonteCarloResult:
    """Run Monte Carlo directly through the deterministic limit-state evaluator.

    This is intended as a validation reference for ANN-based reliability, not as
    a substitute for a more detailed stochastic structural model when the thesis
    methodology requires full re-analysis of each sample.
    """

    if invalid_policy not in {"raise", "skip"}:
        raise ValueError("invalid_policy must be 'raise' or 'skip'.")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must lie in (0, 1).")
    _validate_order(evaluator, variables)
    try:
        target_index = evaluator.target_names.index(target_name)
    except ValueError as exc:
        raise KeyError(target_name) from exc

    samples = independent_random_samples(
        variables,
        sample_count,
        seed=seed,
        dependence=dependence,
    )
    failures = 0
    valid = 0
    invalid = 0
    for row_index, sample in enumerate(samples.records()):
        if control is not None and (row_index % 25 == 0 or row_index + 1 == sample_count):
            control.report("Direct Monte Carlo", row_index + 1, sample_count)
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
    low, high = _wilson_interval(failures, valid, confidence)
    return DirectMonteCarloResult(
        target_name=target_name,
        sample_count=valid,
        failure_count=failures,
        probability_of_failure=probability,
        reliability_index=beta,
        confidence_low=low,
        confidence_high=high,
        confidence_level=confidence,
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
    dependence: GaussianCopula | None = None,
    control: AnalysisControl | None = None,
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

    samples = independent_random_samples(
        variables,
        sample_count,
        seed=seed,
        dependence=dependence,
    )
    feature_rows: list[tuple[float, ...]] = []
    direct_rows: list[tuple[float, ...]] = []
    invalid = 0
    for row_index, sample in enumerate(samples.records()):
        if control is not None and (
            row_index % 25 == 0 or row_index + 1 == sample_count
        ):
            control.report("Fresh direct ANN validation", row_index + 1, sample_count)
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
