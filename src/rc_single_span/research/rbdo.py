from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
from scipy.optimize import minimize

from rc_single_span.research.reliability import (
    FORMResult,
    SurrogatePredictor,
    form_surrogate_reliability,
)
from rc_single_span.research.sampling import RandomVariable


@dataclass(frozen=True)
class DesignVariable:
    name: str
    lower: float
    upper: float
    initial: float

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Design-variable name cannot be empty.")
        if self.upper <= self.lower:
            raise ValueError("Design-variable upper bound must exceed lower bound.")
        if not self.lower <= self.initial <= self.upper:
            raise ValueError("Design-variable initial value must lie inside its bounds.")


@dataclass(frozen=True)
class ReliabilityConstraint:
    target_name: str
    minimum_beta: float


@dataclass(frozen=True)
class RBDOResult:
    design: dict[str, float]
    objective: float
    reliability: dict[str, FORMResult]
    success: bool
    message: str
    iterations: int

    @property
    def all_constraints_pass(self) -> bool:
        return all(item.converged for item in self.reliability.values())


def _variables_at_design(
    base_variables: tuple[RandomVariable, ...],
    design: dict[str, float],
) -> tuple[RandomVariable, ...]:
    return tuple(
        variable.with_mean(design[variable.name])
        if variable.name in design
        else variable
        for variable in base_variables
    )


def optimize_surrogate_rbdo(
    model: SurrogatePredictor,
    base_variables: tuple[RandomVariable, ...],
    design_variables: tuple[DesignVariable, ...],
    reliability_constraints: tuple[ReliabilityConstraint, ...],
    objective: Callable[[dict[str, float]], float],
    *,
    maximum_iterations: int = 100,
    ftol: float = 1.0e-6,
    form_kwargs: dict[str, object] | None = None,
) -> RBDOResult:
    """Reliability-based design optimization using ANN + FORM constraints.

    The stochastic distribution of each design variable is obtained by moving
    the mean of its corresponding ``base_variables`` entry while preserving its
    declared COV/standard deviation model. This makes the design/reliability
    coupling explicit and keeps all non-design random variables unchanged.
    """

    if not design_variables:
        raise ValueError("RBDO requires at least one design variable.")
    if not reliability_constraints:
        raise ValueError("RBDO requires at least one reliability constraint.")
    base_names = tuple(variable.name for variable in base_variables)
    if base_names != model.feature_names:
        raise ValueError("base_variables must match surrogate feature_names exactly.")
    design_names = tuple(item.name for item in design_variables)
    if len(set(design_names)) != len(design_names):
        raise ValueError("RBDO design-variable names must be unique.")
    missing = set(design_names) - set(base_names)
    if missing:
        raise ValueError(f"RBDO design variables are not surrogate features: {sorted(missing)}")
    for item in reliability_constraints:
        if item.target_name not in model.target_names:
            raise ValueError(f"Unknown reliability target: {item.target_name}")

    kwargs = dict(form_kwargs or {})
    cache: dict[tuple[float, ...], dict[str, FORMResult]] = {}

    def design_dict(vector: np.ndarray) -> dict[str, float]:
        return {
            item.name: float(value)
            for item, value in zip(design_variables, vector, strict=True)
        }

    def reliability_for(vector: np.ndarray) -> dict[str, FORMResult]:
        key = tuple(round(float(value), 12) for value in vector)
        if key in cache:
            return cache[key]
        design = design_dict(vector)
        variables = _variables_at_design(base_variables, design)
        results = {
            constraint.target_name: form_surrogate_reliability(
                model,
                variables,
                constraint.target_name,
                **kwargs,
            )
            for constraint in reliability_constraints
        }
        cache[key] = results
        return results

    def objective_vector(vector: np.ndarray) -> float:
        value = float(objective(design_dict(vector)))
        if not np.isfinite(value):
            raise ValueError("RBDO objective returned a non-finite value.")
        return value

    scipy_constraints = []
    for index, constraint in enumerate(reliability_constraints):
        def constraint_function(vector: np.ndarray, i: int = index) -> float:
            spec = reliability_constraints[i]
            result = reliability_for(vector)[spec.target_name]
            if not result.converged:
                return -1.0e6
            return result.beta - spec.minimum_beta

        scipy_constraints.append({"type": "ineq", "fun": constraint_function})

    x0 = np.asarray([item.initial for item in design_variables], dtype=float)
    bounds = [(item.lower, item.upper) for item in design_variables]
    result = minimize(
        objective_vector,
        x0,
        method="SLSQP",
        bounds=bounds,
        constraints=scipy_constraints,
        options={"maxiter": maximum_iterations, "ftol": ftol, "disp": False},
    )
    final_design = design_dict(np.asarray(result.x, dtype=float))
    final_reliability = reliability_for(np.asarray(result.x, dtype=float))
    all_pass = all(
        final_reliability[item.target_name].converged
        and final_reliability[item.target_name].beta >= item.minimum_beta - 1.0e-6
        for item in reliability_constraints
    )
    return RBDOResult(
        design=final_design,
        objective=float(result.fun),
        reliability=final_reliability,
        success=bool(result.success and all_pass),
        message=str(result.message),
        iterations=int(getattr(result, "nit", 0)),
    )
