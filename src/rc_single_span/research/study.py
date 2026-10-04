"""Config-driven ANN, reliability and RBDO study runner for the desktop workbench."""

from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np
import scipy

from rc_single_span.codes.eurocode.combinations import EurocodeServiceabilityFactors
from rc_single_span.core.models import BridgeProject
from rc_single_span.core.progress import AnalysisControl
from rc_single_span.research.acceptance import ann_reliability_rbdo_gate
from rc_single_span.research.baseline import extract_bs_en_reliability_baseline
from rc_single_span.research.convergence import sample_size_convergence
from rc_single_span.research.dependence import GaussianCopula
from rc_single_span.research.evaluator import (
    FEATURE_NAMES,
    BridgeLimitStateEvaluator,
    ReliabilityModelConfig,
)
from rc_single_span.research.pipeline import ResearchPipelineConfig, run_research_pipeline
from rc_single_span.research.rbdo import (
    DesignVariable,
    ReliabilityConstraint,
    optimize_surrogate_rbdo,
)
from rc_single_span.research.sampling import RandomVariable
from rc_single_span.research.surrogate import MLPConfig
from rc_single_span.research.targets import bs_en_1990_target_reliability
from rc_single_span.research.validation import (
    challenge_surrogate_at_direct_boundaries,
    direct_monte_carlo_reliability,
    validate_surrogate_against_direct,
)
from rc_single_span.verification.reference_runner import ReferenceRunConfig, run_reference_project


def _object(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a JSON object.")
    return value


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable(payload), indent=2), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _variables(data: dict[str, Any]) -> tuple[RandomVariable, ...]:
    raw = data.get("random_variables")
    if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
        raise TypeError("random_variables must be a list of variable objects.")
    variables = tuple(RandomVariable(**item) for item in raw)
    if tuple(variable.name for variable in variables) != FEATURE_NAMES:
        raise ValueError(
            "random_variables must match the reliability evaluator's feature names and order."
        )
    return variables


def _dependence(data: dict[str, Any]) -> GaussianCopula | None:
    raw = data.get("dependence")
    if raw is None:
        return None
    config = _object(raw, "dependence")
    if config.get("enabled") is not True:
        return None
    names = config.get("names")
    matrix = config.get("correlation_matrix")
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        raise TypeError("dependence.names must be a list of strings.")
    if not isinstance(matrix, list):
        raise TypeError("dependence.correlation_matrix must be a list of rows.")
    model = GaussianCopula(tuple(names), matrix)
    model.validate_names(FEATURE_NAMES)
    return model


def _reference_config(data: dict[str, Any]) -> ReferenceRunConfig:
    reference = _object(data.get("reference_run"), "reference_run")
    sls = _object(
        reference.get("serviceability_factors"),
        "reference_run.serviceability_factors",
    )
    return ReferenceRunConfig(
        elastic_modulus_mpa=float(reference["elastic_modulus_mpa"]),
        eurocode_sls_factors=EurocodeServiceabilityFactors(
            psi1_traffic=float(sls["psi1_traffic"]),
            psi1_udl_traffic=float(sls["psi1_udl_traffic"]),
            psi2_traffic=float(sls["psi2_traffic"]),
        ),
        lm1_longitudinal_step_m=float(reference.get("lm1_longitudinal_step_m", 0.6)),
        retain_all_cases=bool(reference.get("retain_all_cases", False)),
        lm1_udl_influence_surface=bool(reference.get("lm1_udl_influence_surface", True)),
    )


def _rbdo(
    data: dict[str, Any],
    model: object,
    variables: tuple[RandomVariable, ...],
    dependence: GaussianCopula | None,
    control: AnalysisControl | None,
):
    raw = data.get("rbdo")
    if not isinstance(raw, dict) or raw.get("enabled") is not True:
        return None
    design_variables = tuple(
        DesignVariable(**item)
        for item in raw.get("design_variables", [])
        if isinstance(item, dict)
    )
    constraints = tuple(
        ReliabilityConstraint(**item)
        for item in raw.get("reliability_constraints", [])
        if isinstance(item, dict)
    )
    weights = raw.get("objective_weights")
    if not isinstance(weights, dict) or not weights:
        raise ValueError("Enabled RBDO requires objective_weights.")
    if set(weights) - {item.name for item in design_variables}:
        raise ValueError("RBDO objective weights must refer to design variables.")

    def objective(design: dict[str, float]) -> float:
        return sum(float(weights[name]) * design[name] for name in weights)

    return optimize_surrogate_rbdo(
        model,
        variables,
        design_variables,
        constraints,
        objective,
        maximum_iterations=int(raw.get("maximum_iterations", 100)),
        form_kwargs={"dependence": dependence},
        control=control,
    )


def run_research_study(
    project: BridgeProject,
    study_config: dict[str, Any],
    output_directory: str | Path,
    *,
    reference_config: ReferenceRunConfig | None = None,
    control: AnalysisControl | None = None,
    exploratory: bool = True,
) -> dict[str, Any]:
    """Run and record a reproducible research study using the current bridge model.

    Unconfirmed inputs can run only as explicitly exploratory work. The function
    records the full configuration and model hashes and never upgrades an
    exploratory result to an accepted design/reliability result.
    """

    data = _object(study_config, "Study configuration")
    confirmed = data.get("assumptions_confirmed") is True
    if confirmed and exploratory:
        raise ValueError("A confirmed study must be run with exploratory=False.")
    if not confirmed and not exploratory:
        raise ValueError(
            "Study inputs are unconfirmed. Run as exploratory or confirm the sourced basis first."
        )
    if not isinstance(data.get("limit_state_model"), dict):
        raise TypeError("limit_state_model must be provided.")
    destination = Path(output_directory)
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError("Study output directory must be empty for reproducibility.")
    destination.mkdir(parents=True, exist_ok=True)

    if control is not None:
        control.report("Preparing BS EN research baseline", 0, 1)
    resolved_config = reference_config or _reference_config(data)
    deterministic = run_reference_project(
        project,
        config=resolved_config,
        code_route="bs_en",
        control=control,
    )
    baseline = extract_bs_en_reliability_baseline(deterministic)

    limit = _object(data["limit_state_model"], "limit_state_model")
    evaluator = BridgeLimitStateEvaluator(
        baseline,
        ReliabilityModelConfig(
            deflection_limit_mm=float(limit["deflection_limit_mm"]),
            gamma_c=float(limit.get("gamma_c", 1.0)),
            gamma_s=float(limit.get("gamma_s", 1.0)),
            alpha_cc=float(limit.get("alpha_cc", 1.0)),
            cot_theta=float(limit.get("cot_theta", 2.0)),
            z_factor=float(limit.get("z_factor", 0.9)),
            provided_asw_per_s_mm2_per_m=(
                None if limit.get("provided_asw_per_s_mm2_per_m") is None
                else float(limit["provided_asw_per_s_mm2_per_m"])
            ),
        ),
    )
    variables = _variables(data)
    dependence = _dependence(data)
    nominal_evaluation = evaluator.evaluate(
        {variable.name: variable.expected_value for variable in variables}
    )
    target_raw = _object(data.get("target_reliability"), "target_reliability")
    target = bs_en_1990_target_reliability(
        str(target_raw["consequence_class"]),
        int(target_raw["reference_period_years"]),
    )

    pipeline_raw = _object(data.get("pipeline", {}), "pipeline")
    mlp_raw = _object(pipeline_raw.get("mlp", {}), "pipeline.mlp")
    if str(pipeline_raw.get("backend", "numpy")) != "numpy":
        raise ValueError("The desktop research workbench currently requires the NumPy ANN backend.")
    pipeline_config = ResearchPipelineConfig(
        sample_count=int(pipeline_raw.get("sample_count", 1500)),
        dataset_seed=int(pipeline_raw.get("dataset_seed", 20260926)),
        split_seed=int(pipeline_raw.get("split_seed", 20260927)),
        train_fraction=float(pipeline_raw.get("train_fraction", 0.70)),
        validation_fraction=float(pipeline_raw.get("validation_fraction", 0.15)),
        backend="numpy",
        mlp=MLPConfig(
            hidden_layers=tuple(int(value) for value in mlp_raw.get("hidden_layers", [64, 64])),
            learning_rate=float(mlp_raw.get("learning_rate", 1.0e-3)),
            batch_size=int(mlp_raw.get("batch_size", 64)),
            epochs=int(mlp_raw.get("epochs", 1000)),
            patience=int(mlp_raw.get("patience", 60)),
            seed=int(mlp_raw.get("seed", 42)),
        ),
        run_form=bool(pipeline_raw.get("run_form", True)),
        monte_carlo_samples=int(pipeline_raw.get("surrogate_monte_carlo_samples", 0)),
        reliability_seed=int(pipeline_raw.get("reliability_seed", 20260928)),
        dependence=dependence,
    )
    pipeline = run_research_pipeline(
        evaluator,
        variables,
        config=pipeline_config,
        control=control,
    )

    validation_raw = _object(data.get("validation", {}), "validation")
    direct_validation = validate_surrogate_against_direct(
        evaluator,
        pipeline.model,
        variables,
        int(validation_raw.get("fresh_direct_samples", 250)),
        seed=int(validation_raw.get("seed", 20260929)),
        near_limit_state_fraction=float(validation_raw.get("near_limit_state_fraction", 0.10)),
        dependence=dependence,
        control=control,
    )
    boundary_raw = _object(data.get("boundary_challenge", {}), "boundary_challenge")
    boundary = (
        challenge_surrogate_at_direct_boundaries(
            evaluator,
            pipeline.model,
            variables,
            iterations=int(boundary_raw.get("iterations", 25)),
            seed=int(boundary_raw.get("seed", 20261001)),
            control=control,
        )
        if boundary_raw.get("enabled") is True
        else ()
    )

    direct_mc_count = int(validation_raw.get("direct_monte_carlo_samples", 0))
    direct_mc = {}
    if direct_mc_count > 0:
        for index, target_name in enumerate(evaluator.target_names):
            if control is not None:
                control.report(f"Direct Monte Carlo: {target_name}", 0, direct_mc_count)
            direct_mc[target_name] = direct_monte_carlo_reliability(
                evaluator,
                variables,
                target_name,
                direct_mc_count,
                seed=int(validation_raw.get("seed", 20260929)) + index + 1,
                dependence=dependence,
                control=control,
            )

    rbdo_result = _rbdo(data, pipeline.model, variables, dependence, control)
    convergence_raw = data.get("sample_size_convergence")
    convergence = None
    if isinstance(convergence_raw, dict) and convergence_raw.get("enabled") is True:
        convergence = sample_size_convergence(
            evaluator,
            variables,
            tuple(int(value) for value in convergence_raw["sample_counts"]),
            base_seed=int(convergence_raw.get("base_seed", 20260930)),
            tolerance=float(convergence_raw.get("tolerance", 0.05)),
            dependence=dependence,
            control=control,
        )

    candidate_direct = None
    if rbdo_result is not None:
        candidate_variables = tuple(
            variable.with_mean(rbdo_result.design[variable.name])
            if variable.name in rbdo_result.design else variable
            for variable in variables
        )
        candidate_nominal = evaluator.evaluate(
            {variable.name: variable.expected_value for variable in candidate_variables}
        )
        feature_values = np.asarray(
            [variable.expected_value for variable in candidate_variables], dtype=float
        )
        candidate_direct = {
            "nominal_margins": candidate_nominal,
            "nominal_within_training_feature_domain": pipeline.feature_domain.contains(
                feature_values
            ),
        }
        candidate_samples = int(_object(data.get("rbdo", {}), "rbdo").get("direct_check_samples", 0))
        if candidate_samples > 0:
            candidate_direct["monte_carlo"] = {
                target_name: direct_monte_carlo_reliability(
                    evaluator,
                    candidate_variables,
                    target_name,
                    candidate_samples,
                    seed=int(validation_raw.get("seed", 20260929)) + 100 + index,
                    dependence=dependence,
                    control=control,
                )
                for index, target_name in enumerate(evaluator.target_names)
            }

    config_file = destination / "study_config.json"
    project_file = destination / "bridge_project.json"
    _write_json(config_file, data)
    project_file.write_text(project.model_dump_json(indent=2), encoding="utf-8")
    pipeline.dataset.write_csv(destination / "dataset.csv")
    pipeline.split.train.write_csv(destination / "train.csv")
    pipeline.split.validation.write_csv(destination / "validation.csv")
    pipeline.split.test.write_csv(destination / "test.csv")
    if hasattr(pipeline.model, "save_npz"):
        pipeline.model.save_npz(destination / "ann_model.npz")

    artifact_paths = sorted(path for path in destination.iterdir() if path.is_file())
    summary: dict[str, Any] = {
        "status": (
            "EXPLORATORY ONLY: probabilistic assumptions are unconfirmed; no reliability or "
            "RBDO result is accepted for design or thesis conclusions"
            if exploratory else
            "Configuration-confirmed run; numerical acceptance gates remain independently assessed"
        ),
        "assumptions_confirmed": confirmed,
        "config_sha256": _sha256(config_file),
        "project_sha256": _sha256(project_file),
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
        },
        "artifact_sha256": {path.name: _sha256(path) for path in artifact_paths},
        "target_reliability": target,
        "dependence": None if dependence is None else {
            "names": dependence.names,
            "correlation_matrix": dependence.correlation,
        },
        "baseline": {
            "project_name": baseline.project.name,
            "fck_mpa": baseline.project.materials.fck_mpa,
            "fyk_mpa": baseline.project.materials.fyk_mpa,
            "elastic_modulus_mpa": baseline.project.materials.elastic_modulus_mpa,
            "moment_girder_index": baseline.moment_girder_index,
            "shear_girder_index": baseline.shear_girder_index,
            "deflection_girder_index": baseline.deflection_girder_index,
            "permanent_moment_knm": baseline.permanent_moment_knm,
            "traffic_moment_knm": baseline.traffic_moment_knm,
            "permanent_shear_kn": baseline.permanent_shear_kn,
            "traffic_shear_kn": baseline.traffic_shear_kn,
            "permanent_deflection_mm": baseline.permanent_deflection_mm,
            "traffic_deflection_mm": baseline.traffic_deflection_mm,
            "deflection_basis": baseline.deflection_basis,
            "provenance": baseline.provenance,
            "lm1_step_m": resolved_config.lm1_longitudinal_step_m,
        },
        "limit_state_model": limit,
        "nominal_limit_states": nominal_evaluation,
        "random_variables": data["random_variables"],
        "dataset_rows": pipeline.dataset.size,
        "invalid_dataset_rows": pipeline.dataset.invalid_samples,
        "split_rows": {
            "train": pipeline.split.train.size,
            "validation": pipeline.split.validation.size,
            "test": pipeline.split.test.size,
        },
        "training_history": _jsonable(pipeline.history),
        "feature_domain": pipeline.feature_domain,
        "held_out_test_metrics": pipeline.test_metrics,
        "fresh_direct_validation": direct_validation,
        "direct_boundary_challenges": boundary,
        "form": pipeline.form,
        "surrogate_monte_carlo": pipeline.monte_carlo,
        "direct_monte_carlo": direct_mc,
        "rbdo": rbdo_result,
        "rbdo_candidate_direct": candidate_direct,
        "sample_size_convergence": convergence,
        "evidence_gate": ann_reliability_rbdo_gate(),
    }
    _write_json(destination / "summary.json", summary)
    if control is not None:
        control.report("Research study complete", 1, 1)
    return _jsonable(summary)


__all__ = ["run_research_study"]
