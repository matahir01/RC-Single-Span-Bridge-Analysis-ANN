from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from rc_single_span.research.dataset import (
    DatasetEvaluator,
    DatasetSplit,
    ReliabilityDataset,
    generate_dataset,
    split_dataset,
)
from rc_single_span.research.keras_backend import train_keras_ann
from rc_single_span.research.reliability import (
    FORMResult,
    MonteCarloResult,
    form_surrogate_reliability,
    monte_carlo_surrogate_reliability,
)
from rc_single_span.research.sampling import RandomVariable
from rc_single_span.research.surrogate import (
    MLPConfig,
    NumpyMLPRegressor,
    RegressionMetrics,
    TrainingHistory,
    train_numpy_ann,
)


@dataclass(frozen=True)
class FeatureDomain:
    names: tuple[str, ...]
    minimum: tuple[float, ...]
    maximum: tuple[float, ...]

    @classmethod
    def from_dataset(cls, dataset: ReliabilityDataset) -> FeatureDomain:
        return cls(
            dataset.feature_names,
            tuple(map(float, np.min(dataset.features, axis=0))),
            tuple(map(float, np.max(dataset.features, axis=0))),
        )

    def contains(self, row: np.ndarray) -> bool:
        values = np.asarray(row, dtype=float)
        if values.shape != (len(self.names),):
            raise ValueError("Feature-domain query has the wrong dimension.")
        lower = np.asarray(self.minimum)
        upper = np.asarray(self.maximum)
        return bool(np.all(values >= lower) and np.all(values <= upper))


@dataclass(frozen=True)
class ResearchPipelineConfig:
    sample_count: int = 1500
    dataset_seed: int = 20260926
    split_seed: int = 20260927
    train_fraction: float = 0.70
    validation_fraction: float = 0.15
    backend: Literal["numpy", "keras"] = "numpy"
    mlp: MLPConfig = field(default_factory=MLPConfig)
    run_form: bool = True
    monte_carlo_samples: int = 0
    reliability_seed: int = 20260928

    def __post_init__(self) -> None:
        if self.sample_count <= 0:
            raise ValueError("sample_count must be positive.")
        if self.monte_carlo_samples < 0:
            raise ValueError("monte_carlo_samples cannot be negative.")
        if self.backend not in {"numpy", "keras"}:
            raise ValueError("backend must be 'numpy' or 'keras'.")


@dataclass(frozen=True)
class ResearchPipelineResult:
    dataset: ReliabilityDataset
    split: DatasetSplit
    model: object
    history: object
    test_metrics: RegressionMetrics
    feature_domain: FeatureDomain
    form: dict[str, FORMResult]
    monte_carlo: dict[str, MonteCarloResult]


def run_research_pipeline(
    evaluator: DatasetEvaluator,
    variables: tuple[RandomVariable, ...],
    *,
    config: ResearchPipelineConfig | None = None,
) -> ResearchPipelineResult:
    """Generate LHS data, train ANN, then optionally run ANN-based reliability.

    The function intentionally does not declare the surrogate or RBDO fit for a
    thesis merely because training completed. Test metrics, near-limit-state
    checks and direct deterministic spot checks remain evidence to review before
    accepting a trained model for reliability conclusions.
    """

    current = config or ResearchPipelineConfig()
    dataset = generate_dataset(
        evaluator,
        variables,
        current.sample_count,
        seed=current.dataset_seed,
        invalid_policy="raise",
    )
    split = split_dataset(
        dataset,
        train_fraction=current.train_fraction,
        validation_fraction=current.validation_fraction,
        seed=current.split_seed,
    )

    if current.backend == "numpy":
        model, history, metrics = train_numpy_ann(split, config=current.mlp)
    else:
        model, history, metrics = train_keras_ann(split, config=current.mlp)

    form_results = (
        {
            target: form_surrogate_reliability(model, variables, target)
            for target in dataset.target_names
        }
        if current.run_form
        else {}
    )
    mc_results = (
        {
            target: monte_carlo_surrogate_reliability(
                model,
                variables,
                target,
                current.monte_carlo_samples,
                seed=current.reliability_seed + index,
            )
            for index, target in enumerate(dataset.target_names)
        }
        if current.monte_carlo_samples > 0
        else {}
    )
    return ResearchPipelineResult(
        dataset=dataset,
        split=split,
        model=model,
        history=history,
        test_metrics=metrics,
        feature_domain=FeatureDomain.from_dataset(dataset),
        form=form_results,
        monte_carlo=mc_results,
    )


__all__ = [
    "FeatureDomain",
    "NumpyMLPRegressor",
    "ResearchPipelineConfig",
    "ResearchPipelineResult",
    "TrainingHistory",
    "run_research_pipeline",
]
