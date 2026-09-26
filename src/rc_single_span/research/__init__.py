"""Research utilities built on the verified deterministic bridge engine.

The research package deliberately keeps uncertainty assumptions, surrogate
training and reliability targets outside the deterministic design-code core.
"""

from rc_single_span.research.acceptance import (
    ResearchAcceptanceGate,
    ResearchAcceptanceItem,
    ResearchEvidenceState,
    ann_reliability_rbdo_gate,
)
from rc_single_span.research.baseline import (
    BSENReliabilityBaseline,
    extract_bs_en_reliability_baseline,
)
from rc_single_span.research.dataset import (
    DatasetSplit,
    ReliabilityDataset,
    generate_dataset,
    split_dataset,
)
from rc_single_span.research.evaluator import (
    BridgeLimitStateEvaluator,
    LimitStateEvaluation,
    ReliabilityModelConfig,
)
from rc_single_span.research.pipeline import (
    ResearchPipelineConfig,
    ResearchPipelineResult,
    run_research_pipeline,
)
from rc_single_span.research.rbdo import (
    DesignVariable,
    RBDOResult,
    ReliabilityConstraint,
    optimize_surrogate_rbdo,
)
from rc_single_span.research.reliability import (
    FORMResult,
    MonteCarloResult,
    form_hlrf,
    form_surrogate_reliability,
    monte_carlo_surrogate_reliability,
)
from rc_single_span.research.sampling import (
    DistributionFamily,
    RandomVariable,
    SampleSet,
    independent_random_samples,
    latin_hypercube,
)
from rc_single_span.research.surrogate import (
    MLPConfig,
    NumpyMLPRegressor,
    RegressionMetrics,
    train_numpy_ann,
)
from rc_single_span.research.validation import (
    DirectMonteCarloResult,
    SurrogateValidationResult,
    direct_monte_carlo_reliability,
    validate_surrogate_against_direct,
)

__all__ = [
    "BSENReliabilityBaseline",
    "BridgeLimitStateEvaluator",
    "DatasetSplit",
    "DesignVariable",
    "DirectMonteCarloResult",
    "DistributionFamily",
    "FORMResult",
    "LimitStateEvaluation",
    "MLPConfig",
    "MonteCarloResult",
    "NumpyMLPRegressor",
    "RBDOResult",
    "RandomVariable",
    "RegressionMetrics",
    "ReliabilityConstraint",
    "ReliabilityDataset",
    "ReliabilityModelConfig",
    "ResearchAcceptanceGate",
    "ResearchAcceptanceItem",
    "ResearchEvidenceState",
    "ResearchPipelineConfig",
    "ResearchPipelineResult",
    "SampleSet",
    "SurrogateValidationResult",
    "ann_reliability_rbdo_gate",
    "direct_monte_carlo_reliability",
    "extract_bs_en_reliability_baseline",
    "form_hlrf",
    "form_surrogate_reliability",
    "generate_dataset",
    "independent_random_samples",
    "latin_hypercube",
    "monte_carlo_surrogate_reliability",
    "optimize_surrogate_rbdo",
    "run_research_pipeline",
    "split_dataset",
    "train_numpy_ann",
    "validate_surrogate_against_direct",
]
