from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import exp, log, sqrt

import numpy as np
from scipy.stats import lognorm, norm, qmc, uniform

from rc_single_span.research.dependence import GaussianCopula


class DistributionFamily(str, Enum):
    NORMAL = "normal"
    LOGNORMAL = "lognormal"
    UNIFORM = "uniform"


@dataclass(frozen=True)
class RandomVariable:
    """One explicit uncertainty variable used by the research pipeline.

    ``cov`` is the coefficient of variation and is mutually exclusive with
    ``std``. Bounds truncate normal/lognormal variables by remapping probability
    mass rather than clipping samples, which avoids artificial point masses at
    the bounds.
    """

    name: str
    family: DistributionFamily | str
    mean: float | None = None
    cov: float | None = None
    std: float | None = None
    lower: float | None = None
    upper: float | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Random-variable name cannot be empty.")
        family = DistributionFamily(self.family)
        object.__setattr__(self, "family", family)
        if self.lower is not None and self.upper is not None and self.upper <= self.lower:
            raise ValueError("Random-variable upper bound must exceed lower bound.")
        if self.cov is not None and self.std is not None:
            raise ValueError("Specify either cov or std, not both.")

        if family is DistributionFamily.UNIFORM:
            if self.lower is None or self.upper is None:
                raise ValueError("Uniform variables require lower and upper bounds.")
            if self.mean is not None or self.cov is not None or self.std is not None:
                raise ValueError(
                    "Uniform variables are defined by lower/upper only; omit mean/cov/std."
                )
            return

        if self.mean is None:
            raise ValueError("Normal and lognormal variables require a mean.")
        if self.cov is None and self.std is None:
            raise ValueError("Normal and lognormal variables require cov or std.")
        if self.cov is not None and self.cov <= 0.0:
            raise ValueError("Coefficient of variation must be positive.")
        if self.std is not None and self.std <= 0.0:
            raise ValueError("Standard deviation must be positive.")
        if family is DistributionFamily.LOGNORMAL:
            if self.mean <= 0.0:
                raise ValueError("Lognormal mean must be positive.")
            if self.lower is not None and self.lower < 0.0:
                raise ValueError("Lognormal lower bound cannot be negative.")

    @property
    def standard_deviation(self) -> float:
        if self.family is DistributionFamily.UNIFORM:
            assert self.lower is not None and self.upper is not None
            return (self.upper - self.lower) / sqrt(12.0)
        if self.std is not None:
            return self.std
        assert self.mean is not None and self.cov is not None
        return abs(self.mean) * self.cov

    @property
    def expected_value(self) -> float:
        if self.family is DistributionFamily.UNIFORM:
            assert self.lower is not None and self.upper is not None
            return 0.5 * (self.lower + self.upper)
        assert self.mean is not None
        return self.mean

    def with_mean(self, mean: float) -> RandomVariable:
        """Return the same distribution family centred on a new design mean."""

        if self.family is DistributionFamily.UNIFORM:
            assert self.lower is not None and self.upper is not None
            half_range = 0.5 * (self.upper - self.lower)
            return RandomVariable(
                self.name,
                self.family,
                lower=mean - half_range,
                upper=mean + half_range,
            )
        return RandomVariable(
            self.name,
            self.family,
            mean=mean,
            cov=self.cov,
            std=self.std,
            lower=self.lower,
            upper=self.upper,
        )

    def _distribution(self):
        if self.family is DistributionFamily.NORMAL:
            assert self.mean is not None
            return norm(loc=self.mean, scale=self.standard_deviation)
        if self.family is DistributionFamily.LOGNORMAL:
            assert self.mean is not None
            cv = self.standard_deviation / self.mean
            sigma_ln = sqrt(log(1.0 + cv * cv))
            mu_ln = log(self.mean) - 0.5 * sigma_ln * sigma_ln
            return lognorm(s=sigma_ln, scale=exp(mu_ln))
        assert self.lower is not None and self.upper is not None
        return uniform(loc=self.lower, scale=self.upper - self.lower)

    def from_unit_interval(self, values: np.ndarray | float) -> np.ndarray:
        """Map probabilities in [0, 1] to the physical variable."""

        u = np.asarray(values, dtype=float)
        if np.any((u < 0.0) | (u > 1.0)):
            raise ValueError("Unit-interval samples must lie in [0, 1].")
        distribution = self._distribution()

        if self.family is DistributionFamily.UNIFORM:
            probabilities = np.clip(u, 0.0, 1.0)
        else:
            lower_cdf = 0.0 if self.lower is None else float(distribution.cdf(self.lower))
            upper_cdf = 1.0 if self.upper is None else float(distribution.cdf(self.upper))
            if upper_cdf <= lower_cdf + 1.0e-15:
                raise ValueError(f"Bounds for {self.name} contain negligible probability mass.")
            probabilities = lower_cdf + u * (upper_cdf - lower_cdf)
        probabilities = np.clip(probabilities, 1.0e-12, 1.0 - 1.0e-12)
        return np.asarray(distribution.ppf(probabilities), dtype=float)

    def from_standard_normal(self, values: np.ndarray | float) -> np.ndarray:
        """Transform latent standard-normal coordinates to physical space."""

        u = np.asarray(values, dtype=float)
        return self.from_unit_interval(norm.cdf(u))

    def random_sample(self, size: int, rng: np.random.Generator) -> np.ndarray:
        if size <= 0:
            raise ValueError("Sample size must be positive.")
        return self.from_unit_interval(rng.random(size))


@dataclass(frozen=True)
class SampleSet:
    names: tuple[str, ...]
    values: np.ndarray
    method: str
    seed: int | None

    def __post_init__(self) -> None:
        array = np.asarray(self.values, dtype=float)
        if array.ndim != 2:
            raise ValueError("SampleSet values must be a two-dimensional array.")
        if array.shape[1] != len(self.names):
            raise ValueError("SampleSet column count must match names.")
        if len(set(self.names)) != len(self.names):
            raise ValueError("SampleSet names must be unique.")
        if not np.all(np.isfinite(array)):
            raise ValueError("SampleSet contains non-finite values.")
        object.__setattr__(self, "values", array)

    @property
    def size(self) -> int:
        return int(self.values.shape[0])

    def records(self) -> tuple[dict[str, float], ...]:
        return tuple(
            {name: float(value) for name, value in zip(self.names, row, strict=True)}
            for row in self.values
        )


def _variable_names(variables: tuple[RandomVariable, ...]) -> tuple[str, ...]:
    if not variables:
        raise ValueError("At least one random variable is required.")
    names = tuple(variable.name for variable in variables)
    if len(set(names)) != len(names):
        raise ValueError("Random-variable names must be unique.")
    return names


def _apply_gaussian_copula(
    unit: np.ndarray,
    dependence: GaussianCopula,
) -> np.ndarray:
    latent = norm.ppf(np.clip(unit, 1.0e-12, 1.0 - 1.0e-12))
    correlated = dependence.correlate_standard_normals(latent)
    return np.asarray(norm.cdf(correlated), dtype=float)


def latin_hypercube(
    variables: tuple[RandomVariable, ...],
    sample_count: int,
    *,
    seed: int | None = None,
    dependence: GaussianCopula | None = None,
) -> SampleSet:
    """Generate a reproducible LHS, optionally coupled by a Gaussian copula."""

    if sample_count <= 0:
        raise ValueError("sample_count must be positive.")
    names = _variable_names(variables)
    unit = qmc.LatinHypercube(d=len(variables), seed=seed).random(sample_count)
    method = "latin_hypercube"
    if dependence is not None:
        dependence.validate_names(names)
        unit = _apply_gaussian_copula(unit, dependence)
        method = "latin_hypercube_gaussian_copula"
    values = np.column_stack(
        [variable.from_unit_interval(unit[:, index]) for index, variable in enumerate(variables)]
    )
    return SampleSet(names, values, method=method, seed=seed)


def independent_random_samples(
    variables: tuple[RandomVariable, ...],
    sample_count: int,
    *,
    seed: int | None = None,
    dependence: GaussianCopula | None = None,
) -> SampleSet:
    """Generate Monte-Carlo samples with optional Gaussian-copula dependence."""

    if sample_count <= 0:
        raise ValueError("sample_count must be positive.")
    names = _variable_names(variables)
    rng = np.random.default_rng(seed)
    if dependence is None:
        values = np.column_stack(
            [variable.random_sample(sample_count, rng) for variable in variables]
        )
        method = "independent_random"
    else:
        dependence.validate_names(names)
        independent = rng.standard_normal((sample_count, len(variables)))
        correlated = dependence.correlate_standard_normals(independent)
        probabilities = norm.cdf(correlated)
        values = np.column_stack(
            [
                variable.from_unit_interval(probabilities[:, index])
                for index, variable in enumerate(variables)
            ]
        )
        method = "gaussian_copula_random"
    return SampleSet(names, values, method=method, seed=seed)


def standard_normal_to_physical(
    variables: tuple[RandomVariable, ...],
    u: np.ndarray,
    *,
    dependence: GaussianCopula | None = None,
) -> np.ndarray:
    """Transform independent normal coordinates to the physical basic variables."""

    names = _variable_names(variables)
    array = np.asarray(u, dtype=float)
    if array.shape[-1] != len(variables):
        raise ValueError("Standard-normal vector dimension does not match variables.")
    latent = array
    if dependence is not None:
        dependence.validate_names(names)
        latent = dependence.correlate_standard_normals(array)
    columns = [
        variable.from_standard_normal(latent[..., index])
        for index, variable in enumerate(variables)
    ]
    return np.stack(columns, axis=-1)
