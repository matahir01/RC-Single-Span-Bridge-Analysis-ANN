from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import exp, sqrt

from rc_single_span.research.sampling import RandomVariable


class JCSSConcreteProduction(str, Enum):
    READY_MIXED = "ready_mixed"
    PRECAST = "precast"


@dataclass(frozen=True)
class JCSSConcretePrior:
    production: JCSSConcreteProduction
    grade: str
    log_location: float
    equivalent_sample_size: float
    log_scale: float
    degrees_of_freedom: float

    @property
    def approximate_log_standard_deviation(self) -> float:
        """JCSS lognormal approximation to the predictive distribution."""

        n = self.equivalent_sample_size
        v = self.degrees_of_freedom
        if n * v <= 10.0 or n <= 1.0 or v <= 2.0:
            raise ValueError("JCSS lognormal approximation conditions are not satisfied.")
        return self.log_scale * sqrt(n / (n - 1.0) * v / (v - 2.0))

    @property
    def approximate_mean_mpa(self) -> float:
        sigma = self.approximate_log_standard_deviation
        return exp(self.log_location + 0.5 * sigma * sigma)

    @property
    def approximate_cov(self) -> float:
        sigma = self.approximate_log_standard_deviation
        return sqrt(exp(sigma * sigma) - 1.0)

    def as_random_variable(self, name: str = "fck_mpa") -> RandomVariable:
        return RandomVariable(
            name,
            "lognormal",
            mean=self.approximate_mean_mpa,
            cov=self.approximate_cov,
        )


_C35_PRIORS = {
    JCSSConcreteProduction.READY_MIXED: JCSSConcretePrior(
        JCSSConcreteProduction.READY_MIXED,
        "C35",
        log_location=3.85,
        equivalent_sample_size=3.0,
        log_scale=0.09,
        degrees_of_freedom=10.0,
    ),
    JCSSConcreteProduction.PRECAST: JCSSConcretePrior(
        JCSSConcreteProduction.PRECAST,
        "C35",
        log_location=3.95,
        equivalent_sample_size=3.0,
        log_scale=0.08,
        degrees_of_freedom=10.0,
    ),
}


def jcss_c35_concrete_prior(
    production: JCSSConcreteProduction | str,
) -> JCSSConcretePrior:
    """Return the JCSS prior for C35 concrete production without local updating."""

    return _C35_PRIORS[JCSSConcreteProduction(production)]


def jcss_rebar_yield_variable(
    nominal_grade_mpa: float = 500.0,
    *,
    name: str = "fyk_mpa",
    bar_diameter_mm: float | None = None,
) -> RandomVariable:
    """JCSS high-standard reinforcing-steel yield model.

    The global production mean is S_nom + 2*30 MPa. When a bar diameter is
    supplied, the JCSS diameter correction is applied to that mean.
    """

    if nominal_grade_mpa <= 0.0:
        raise ValueError("Nominal reinforcing-steel grade must be positive.")
    mean = nominal_grade_mpa + 60.0
    if bar_diameter_mm is not None:
        if bar_diameter_mm <= 0.0:
            raise ValueError("Bar diameter must be positive.")
        mean /= 0.87 + 0.13 * exp(-0.08 * bar_diameter_mm)
    return RandomVariable(name, "normal", mean=mean, std=30.0)


def jcss_rebar_area_variable(
    nominal_area_mm2: float,
    *,
    name: str = "steel_area_mm2",
) -> RandomVariable:
    if nominal_area_mm2 <= 0.0:
        raise ValueError("Nominal reinforcement area must be positive.")
    return RandomVariable(name, "normal", mean=nominal_area_mm2, cov=0.02)


def jcss_concrete_dimension_variable(
    name: str,
    nominal_m: float,
) -> RandomVariable:
    """JCSS generic external concrete-dimension model for X_nom <= 1000 mm."""

    if nominal_m <= 0.0:
        raise ValueError("Nominal dimension must be positive.")
    nominal_mm = nominal_m * 1000.0
    mean_deviation_mm = min(0.003 * nominal_mm, 3.0)
    standard_deviation_mm = min(4.0 + 0.006 * nominal_mm, 10.0)
    return RandomVariable(
        name,
        "normal",
        mean=nominal_m + mean_deviation_mm / 1000.0,
        std=standard_deviation_mm / 1000.0,
    )


def jcss_effective_depth_variable(
    nominal_effective_depth_m: float,
    *,
    name: str = "effective_depth_m",
) -> RandomVariable:
    """JCSS rough default effective-depth deviation: +10 mm mean, 10 mm sigma."""

    if nominal_effective_depth_m <= 0.0:
        raise ValueError("Nominal effective depth must be positive.")
    return RandomVariable(
        name,
        "normal",
        mean=nominal_effective_depth_m + 0.010,
        std=0.010,
    )


def jcss_model_uncertainty_variables() -> tuple[RandomVariable, ...]:
    """Generic JCSS model-error variables used by the response-separation study."""

    return (
        RandomVariable(
            "moment_load_model_factor",
            "lognormal",
            mean=1.0,
            cov=0.10,
        ),
        RandomVariable(
            "shear_load_model_factor",
            "lognormal",
            mean=1.0,
            cov=0.10,
        ),
        RandomVariable(
            "flexure_resistance_model_factor",
            "lognormal",
            mean=1.2,
            cov=0.15,
        ),
        RandomVariable(
            "shear_resistance_model_factor",
            "lognormal",
            mean=1.0,
            cov=0.10,
        ),
    )
