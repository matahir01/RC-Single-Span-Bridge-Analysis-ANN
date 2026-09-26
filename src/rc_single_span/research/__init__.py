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
from rc_single_span.research.dependence import GaussianCopula
from rc_single_span.research.evaluator import (
    BridgeLimitStateEvaluator,
    LimitStateEvaluation,
    ReliabilityModelConfig,
)
from rc_single_span.research.nigeria_traffic import (
    AxleConfiguration,
    EmpiricalAxleSpectrum,
    FederalRoadTrafficFlow,
    NigeriaTrafficEvidence,
    kaduna_zaria_wim_spectra_2024,
    nigeria_traffic_evidence,
    selected_federal_road_flows_2008,
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
from rc_single_span.research.source_profiles import (
    JCSSConcretePrior,
    JCSSConcreteProduction,
    build_jcss_reference_variables,
    jcss_c35_concrete_prior,
    jcss_concrete_dimension_variable,
    jcss_effective_depth_variable,
    jcss_model_uncertainty_variables,
    jcss_rebar_area_variable,
    jcss_rebar_yield_variable,
)
from rc_single_span.research.surrogate import (
    MLPConfig,
    NumpyMLPRegressor,
    RegressionMetrics,
    train_numpy_ann,
)
from rc_single_span.research.targets import (
    ConsequenceClass,
    TargetReliability,
    bs_en_1990_target_reliability,
    thesis_reference_targets,
)
from rc_single_span.research.validation import (
    DirectMonteCarloResult,
    SurrogateValidationResult,
    direct_monte_carlo_reliability,
    validate_surrogate_against_direct,
)

__all__ = [
    "AxleConfiguration",
    "BSENReliabilityBaseline",
    "BridgeLimitStateEvaluator",
    "ConsequenceClass",
    "DatasetSplit",
    "DesignVariable",
    "DirectMonteCarloResult",
    "DistributionFamily",
    "EmpiricalAxleSpectrum",
    "FORMResult",
    "FederalRoadTrafficFlow",
    "GaussianCopula",
    "JCSSConcretePrior",
    "JCSSConcreteProduction",
    "LimitStateEvaluation",
    "MLPConfig",
    "MonteCarloResult",
    "NigeriaTrafficEvidence",
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
    "TargetReliability",
    "ann_reliability_rbdo_gate",
    "bs_en_1990_target_reliability",
    "build_jcss_reference_variables",
    "direct_monte_carlo_reliability",
    "extract_bs_en_reliability_baseline",
    "form_hlrf",
    "form_surrogate_reliability",
    "generate_dataset",
    "independent_random_samples",
    "jcss_c35_concrete_prior",
    "jcss_concrete_dimension_variable",
    "jcss_effective_depth_variable",
    "jcss_model_uncertainty_variables",
    "jcss_rebar_area_variable",
    "jcss_rebar_yield_variable",
    "kaduna_zaria_wim_spectra_2024",
    "latin_hypercube",
    "monte_carlo_surrogate_reliability",
    "nigeria_traffic_evidence",
    "optimize_surrogate_rbdo",
    "run_research_pipeline",
    "selected_federal_road_flows_2008",
    "split_dataset",
    "thesis_reference_targets",
    "train_numpy_ann",
    "validate_surrogate_against_direct",
]
