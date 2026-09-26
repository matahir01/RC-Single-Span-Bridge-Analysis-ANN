from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Callable, Protocol

import numpy as np
from scipy.stats import norm

from rc_single_span.research.sampling import (
    RandomVariable,
    independent_random_samples,
    standard_normal_to_physical,
)


class SurrogatePredictor(Protocol):
    feature_names: tuple[str, ...]
    target_names: tuple[str, ...]

    def predict(self, features: np.ndarray) -> np.ndarray: ...


@dataclass(frozen=True)
class MonteCarloResult:
    target_name: str
    sample_count: int
    failure_count: int
    probability_of_failure: float
    reliability_index: float
    confidence_low: float
    confidence_high: float
    seed: int | None


@dataclass(frozen=True)
class FORMResult:
    beta: float
    probability_of_failure: float
    design_point_u: tuple[float, ...]
    design_point_x: tuple[float, ...]
    alpha: tuple[float, ...]
    limit_state_value: float
    iterations: int
    converged: bool


def _validate_variable_order(
    variables: tuple[RandomVariable, ...],
    feature_names: tuple[str, ...],
) -> None:
    names = tuple(variable.name for variable in variables)
    if names != feature_names:
        raise ValueError("Random-variable order/names must match surrogate feature_names.")


def surrogate_limit_state(
    model: SurrogatePredictor,
    target_name: str,
) -> Callable[[np.ndarray], float]:
    try:
        target_index = model.target_names.index(target_name)
    except ValueError as exc:
        raise KeyError(target_name) from exc

    def evaluate(x: np.ndarray) -> float:
        prediction = np.asarray(model.predict(np.asarray(x, dtype=float)), dtype=float)
        if prediction.ndim != 1 or prediction.size != len(model.target_names):
            raise ValueError("Surrogate single-row prediction has an invalid shape.")
        return float(prediction[target_index])

    return evaluate


def _wilson_interval(failures: int, sample_count: int, confidence: float) -> tuple[float, float]:
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must lie in (0, 1).")
    p = failures / sample_count
    z = float(norm.ppf(0.5 + 0.5 * confidence))
    denominator = 1.0 + z * z / sample_count
    centre = (p + z * z / (2.0 * sample_count)) / denominator
    half = (
        z
        * sqrt(p * (1.0 - p) / sample_count + z * z / (4.0 * sample_count**2))
        / denominator
    )
    return max(0.0, centre - half), min(1.0, centre + half)


def monte_carlo_surrogate_reliability(
    model: SurrogatePredictor,
    variables: tuple[RandomVariable, ...],
    target_name: str,
    sample_count: int,
    *,
    seed: int | None = None,
    confidence: float = 0.95,
) -> MonteCarloResult:
    """Estimate Pf from independent samples evaluated by the ANN surrogate."""

    _validate_variable_order(variables, model.feature_names)
    samples = independent_random_samples(variables, sample_count, seed=seed)
    predictions = np.asarray(model.predict(samples.values), dtype=float)
    if predictions.ndim != 2 or predictions.shape[0] != sample_count:
        raise ValueError("Surrogate batch prediction has an invalid shape.")
    try:
        target_index = model.target_names.index(target_name)
    except ValueError as exc:
        raise KeyError(target_name) from exc
    failures = int(np.count_nonzero(predictions[:, target_index] <= 0.0))
    probability = failures / sample_count
    # Jeffreys-style continuity correction keeps beta finite for zero/all failures
    # while preserving the reported raw Monte-Carlo probability above.
    probability_for_beta = (failures + 0.5) / (sample_count + 1.0)
    beta = -float(norm.ppf(probability_for_beta))
    low, high = _wilson_interval(failures, sample_count, confidence)
    return MonteCarloResult(
        target_name,
        sample_count,
        failures,
        probability,
        beta,
        low,
        high,
        seed,
    )


def form_hlrf(
    limit_state: Callable[[np.ndarray], float],
    variables: tuple[RandomVariable, ...],
    *,
    initial_u: np.ndarray | None = None,
    maximum_iterations: int = 100,
    tolerance_u: float = 1.0e-5,
    tolerance_g: float = 1.0e-5,
    gradient_step: float = 1.0e-4,
) -> FORMResult:
    """First-order reliability method using the Hasofer-Lind/Rackwitz-Fiessler step.

    Variables are assumed statistically independent. Distribution transforms are
    exact for the families implemented in :mod:`research.sampling`; gradients are
    central finite differences in independent standard-normal space.
    """

    if not variables:
        raise ValueError("FORM requires at least one random variable.")
    if min(maximum_iterations, 1) <= 0:
        raise ValueError("maximum_iterations must be positive.")
    if min(tolerance_u, tolerance_g, gradient_step) <= 0.0:
        raise ValueError("FORM tolerances and gradient_step must be positive.")

    dimension = len(variables)
    u = np.zeros(dimension, dtype=float) if initial_u is None else np.asarray(initial_u, dtype=float)
    if u.shape != (dimension,):
        raise ValueError("initial_u has the wrong dimension.")

    origin_g = float(limit_state(standard_normal_to_physical(variables, np.zeros(dimension))))
    sign = 1.0 if origin_g >= 0.0 else -1.0
    alpha = np.zeros(dimension, dtype=float)
    converged = False
    g = float("nan")
    iteration = 0

    for iteration in range(1, maximum_iterations + 1):
        x = standard_normal_to_physical(variables, u)
        g = float(limit_state(x))
        gradient = np.zeros(dimension, dtype=float)
        for index in range(dimension):
            step = gradient_step * max(1.0, abs(u[index]))
            plus = u.copy()
            minus = u.copy()
            plus[index] += step
            minus[index] -= step
            g_plus = float(limit_state(standard_normal_to_physical(variables, plus)))
            g_minus = float(limit_state(standard_normal_to_physical(variables, minus)))
            gradient[index] = (g_plus - g_minus) / (2.0 * step)

        gradient_norm = float(np.linalg.norm(gradient))
        if gradient_norm <= 1.0e-14:
            raise RuntimeError("FORM encountered a near-zero limit-state gradient.")
        alpha = gradient / gradient_norm
        coefficient = (float(np.dot(gradient, u)) - g) / (gradient_norm**2)
        target = coefficient * gradient

        # A simple backtracking step makes the classical HLRF update much less
        # prone to oscillation on ANN surfaces while retaining the same fixed point.
        current_abs_g = abs(g)
        relaxation = 1.0
        u_new = target
        for _ in range(12):
            candidate = u + relaxation * (target - u)
            candidate_g = abs(
                float(limit_state(standard_normal_to_physical(variables, candidate)))
            )
            u_new = candidate
            if candidate_g <= current_abs_g or relaxation <= 1.0 / 2048.0:
                break
            relaxation *= 0.5

        new_g = float(limit_state(standard_normal_to_physical(variables, u_new)))
        if np.linalg.norm(u_new - u) <= tolerance_u and abs(new_g) <= tolerance_g:
            u = u_new
            g = new_g
            converged = True
            break
        u = u_new

    x_design = standard_normal_to_physical(variables, u)
    g = float(limit_state(x_design))
    beta = sign * float(np.linalg.norm(u))
    probability = float(norm.cdf(-beta))
    return FORMResult(
        beta=beta,
        probability_of_failure=probability,
        design_point_u=tuple(map(float, u)),
        design_point_x=tuple(map(float, x_design)),
        alpha=tuple(map(float, alpha)),
        limit_state_value=g,
        iterations=iteration,
        converged=converged,
    )


def form_surrogate_reliability(
    model: SurrogatePredictor,
    variables: tuple[RandomVariable, ...],
    target_name: str,
    **kwargs,
) -> FORMResult:
    _validate_variable_order(variables, model.feature_names)
    return form_hlrf(surrogate_limit_state(model, target_name), variables, **kwargs)
