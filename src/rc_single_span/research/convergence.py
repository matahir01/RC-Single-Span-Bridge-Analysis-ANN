from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from rc_single_span.research.dataset import DatasetEvaluator, ReliabilityDataset, generate_dataset
from rc_single_span.research.sampling import RandomVariable


@dataclass(frozen=True)
class TargetSampleStatistics:
    target_name: str
    mean: float
    standard_deviation: float
    q05: float
    median: float
    q95: float
    failure_fraction: float


@dataclass(frozen=True)
class SampleSizeConvergencePoint:
    sample_count: int
    seed: int
    statistics: tuple[TargetSampleStatistics, ...]
    maximum_standardized_change: float | None
    converged_from_previous: bool | None


@dataclass(frozen=True)
class SampleSizeConvergenceResult:
    points: tuple[SampleSizeConvergencePoint, ...]
    tolerance: float

    @property
    def converged(self) -> bool:
        return bool(self.points) and self.points[-1].converged_from_previous is True

    @property
    def recommended_minimum_sample_count(self) -> int | None:
        """Return the first size whose step and every later step meet tolerance."""

        for index, point in enumerate(self.points[1:], start=1):
            if point.converged_from_previous is True and all(
                later.converged_from_previous is True for later in self.points[index:]
            ):
                return point.sample_count
        return None


def _statistics(dataset: ReliabilityDataset) -> tuple[TargetSampleStatistics, ...]:
    results: list[TargetSampleStatistics] = []
    for column, target in enumerate(dataset.target_names):
        values = dataset.targets[:, column]
        results.append(
            TargetSampleStatistics(
                target_name=target,
                mean=float(np.mean(values)),
                standard_deviation=float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
                q05=float(np.quantile(values, 0.05)),
                median=float(np.quantile(values, 0.50)),
                q95=float(np.quantile(values, 0.95)),
                failure_fraction=float(np.mean(values <= 0.0)),
            )
        )
    return tuple(results)


def _standardized_change(
    previous: tuple[TargetSampleStatistics, ...],
    current: tuple[TargetSampleStatistics, ...],
) -> float:
    """Compare adjacent sample sizes without unstable division by near-zero metrics.

    Dimensional statistics are normalised by the larger of the two target standard
    deviations (or 1.0 if both are tiny). Failure fraction is already dimensionless
    and is compared as an absolute probability change. This makes the convergence
    score interpretable near a failure probability of zero.
    """

    if tuple(item.target_name for item in previous) != tuple(
        item.target_name for item in current
    ):
        raise ValueError("Convergence statistics target order does not match.")

    changes: list[float] = []
    for old, new in zip(previous, current, strict=True):
        scale = max(old.standard_deviation, new.standard_deviation, 1.0)
        for old_value, new_value in (
            (old.mean, new.mean),
            (old.standard_deviation, new.standard_deviation),
            (old.q05, new.q05),
            (old.median, new.median),
            (old.q95, new.q95),
        ):
            changes.append(abs(new_value - old_value) / scale)
        changes.append(abs(new.failure_fraction - old.failure_fraction))
    return max(changes, default=0.0)


def sample_size_convergence(
    evaluator: DatasetEvaluator,
    variables: tuple[RandomVariable, ...],
    sample_counts: tuple[int, ...],
    *,
    base_seed: int = 20260926,
    tolerance: float = 0.05,
) -> SampleSizeConvergenceResult:
    """Audit whether direct LHS response statistics stabilise as N increases.

    Each sample size uses an independently seeded LHS. The result is evidence about
    stability of the sampled response domain, not a mathematical proof that a chosen
    N is universally sufficient. Reliability-tail convergence should also be checked
    against FORM/direct Monte Carlo and, where failures are very rare, an appropriate
    rare-event strategy.
    """

    if len(sample_counts) < 2:
        raise ValueError("At least two sample sizes are required for convergence.")
    if any(count <= 0 for count in sample_counts):
        raise ValueError("Sample sizes must be positive.")
    if tuple(sorted(set(sample_counts))) != sample_counts:
        raise ValueError("sample_counts must be unique and strictly increasing.")
    if tolerance <= 0.0:
        raise ValueError("tolerance must be positive.")

    points: list[SampleSizeConvergencePoint] = []
    previous: tuple[TargetSampleStatistics, ...] | None = None
    for index, sample_count in enumerate(sample_counts):
        seed = base_seed + index
        dataset = generate_dataset(
            evaluator,
            variables,
            sample_count,
            seed=seed,
            invalid_policy="raise",
        )
        stats = _statistics(dataset)
        change = None if previous is None else _standardized_change(previous, stats)
        points.append(
            SampleSizeConvergencePoint(
                sample_count=sample_count,
                seed=seed,
                statistics=stats,
                maximum_standardized_change=change,
                converged_from_previous=None if change is None else change <= tolerance,
            )
        )
        previous = stats

    return SampleSizeConvergenceResult(tuple(points), tolerance)
