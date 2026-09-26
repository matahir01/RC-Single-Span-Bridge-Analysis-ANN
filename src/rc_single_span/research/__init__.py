"""Research utilities built on the verified deterministic bridge engine.

The research package deliberately keeps uncertainty assumptions, surrogate
training and reliability targets outside the deterministic design-code core.
"""

from rc_single_span.research.dataset import ReliabilityDataset, generate_dataset
from rc_single_span.research.evaluator import (
    BridgeLimitStateEvaluator,
    LimitStateEvaluation,
    ReliabilityModelConfig,
)
from rc_single_span.research.reliability import FORMResult, MonteCarloResult, form_hlrf
from rc_single_span.research.sampling import DistributionFamily, RandomVariable, SampleSet

__all__ = [
    "BridgeLimitStateEvaluator",
    "DistributionFamily",
    "FORMResult",
    "LimitStateEvaluation",
    "MonteCarloResult",
    "RandomVariable",
    "ReliabilityDataset",
    "ReliabilityModelConfig",
    "SampleSet",
    "form_hlrf",
    "generate_dataset",
]
