from __future__ import annotations

import argparse
import hashlib
import json
import platform
from dataclasses import asdict, is_dataclass
from pathlib import Path

import numpy as np
import scipy
from thesis_bridge_15m import thesis_bridge_15m

from rc_single_span.codes.eurocode.combinations import EurocodeServiceabilityFactors
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
    direct_monte_carlo_reliability,
    validate_surrogate_against_direct,
)
from rc_single_span.verification.reference_runner import ReferenceRunConfig, run_reference_project


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the config-driven 15 m BS EN ANN/reliability research pipeline."
    )
    parser.add_argument("config", type=Path, help="JSON study configuration")
    parser.add_argument("--output", type=Path, default=Path("artifacts/research"))
    parser.add_argument(
        "--exploratory", action="store_true",
        help="Run an unconfirmed example as a clearly labelled sensitivity experiment.",
    )
    return parser


def _require_confirmed(data: dict[str, object]) -> None:
    if data.get("assumptions_confirmed") is not True:
        raise RuntimeError(
            "Research configuration is not confirmed. Replace illustrative probabilistic "
            "inputs with source-justified study values, then set assumptions_confirmed=true."
        )


def _expect_dict(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be a JSON object.")
    return value


def _variables(data: dict[str, object]) -> tuple[RandomVariable, ...]:
    raw = data.get("random_variables")
    if not isinstance(raw, list):
        raise TypeError("random_variables must be a JSON list.")
    variables = tuple(RandomVariable(**item) for item in raw if isinstance(item, dict))
    if tuple(variable.name for variable in variables) != FEATURE_NAMES:
        raise ValueError(
            "random_variables must contain exactly the evaluator features, in this order: "
            f"{FEATURE_NAMES}"
        )
    return variables


def _dependence(data: dict[str, object]) -> GaussianCopula | None:
    raw = data.get("dependence")
    if raw is None:
        return None
    config = _expect_dict(raw, "dependence")
    if config.get("enabled") is not True:
        return None
    names_raw = config.get("names")
    matrix_raw = config.get("correlation_matrix")
    if not isinstance(names_raw, list) or not all(isinstance(item, str) for item in names_raw):
        raise TypeError("dependence.names must be a JSON list of strings.")
    if not isinstance(matrix_raw, list):
        raise TypeError("dependence.correlation_matrix must be a JSON matrix.")
    dependence = GaussianCopula(tuple(names_raw), matrix_raw)
    dependence.validate_names(FEATURE_NAMES)
    return dependence


def _target_reliability(data: dict[str, object]):
    raw = _expect_dict(data.get("target_reliability"), "target_reliability")
    return bs_en_1990_target_reliability(
        str(raw["consequence_class"]),
        int(raw["reference_period_years"]),
    )


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rbdo(
    data: dict[str, object],
    model,
    variables: tuple[RandomVariable, ...],
    dependence: GaussianCopula | None,
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
        raise ValueError("Enabled RBDO requires a non-empty objective_weights mapping.")
    missing = set(weights) - {item.name for item in design_variables}
    if missing:
        raise ValueError(f"RBDO objective contains non-design variables: {sorted(missing)}")

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
    )


def main() -> int:
    args = _parser().parse_args()
    raw_data = json.loads(args.config.read_text(encoding="utf-8"))
    data = _expect_dict(raw_data, "Study configuration root")
    if args.exploratory:
        if data.get("assumptions_confirmed") is True:
            raise ValueError("Confirmed studies should run without --exploratory.")
    else:
        _require_confirmed(data)
    if args.output.exists() and any(args.output.iterdir()):
        raise FileExistsError("Study output directory must be empty for a reproducible run.")

    reference = _expect_dict(data.get("reference_run"), "reference_run")
    sls = _expect_dict(
        reference.get("serviceability_factors"),
        "reference_run.serviceability_factors",
    )
    run_config = ReferenceRunConfig(
        elastic_modulus_mpa=float(reference["elastic_modulus_mpa"]),
        eurocode_sls_factors=EurocodeServiceabilityFactors(
            psi1_traffic=float(sls["psi1_traffic"]),
            psi1_udl_traffic=float(sls["psi1_udl_traffic"]),
            psi2_traffic=float(sls["psi2_traffic"]),
        ),
        lm1_longitudinal_step_m=float(reference.get("lm1_longitudinal_step_m", 0.6)),
        retain_all_cases=bool(reference.get("retain_all_cases", True)),
        lm1_udl_influence_surface=bool(reference.get("lm1_udl_influence_surface", True)),
    )
    deterministic = run_reference_project(thesis_bridge_15m(), config=run_config, code_route="bs_en")
    baseline = extract_bs_en_reliability_baseline(deterministic)

    limit_state = _expect_dict(data.get("limit_state_model"), "limit_state_model")
    evaluator = BridgeLimitStateEvaluator(
        baseline,
        ReliabilityModelConfig(
            deflection_limit_mm=float(limit_state["deflection_limit_mm"]),
            gamma_c=float(limit_state.get("gamma_c", 1.0)),
            gamma_s=float(limit_state.get("gamma_s", 1.0)),
            alpha_cc=float(limit_state.get("alpha_cc", 1.0)),
            cot_theta=float(limit_state.get("cot_theta", 2.0)),
            z_factor=float(limit_state.get("z_factor", 0.9)),
            provided_asw_per_s_mm2_per_m=(
                None
                if limit_state.get("provided_asw_per_s_mm2_per_m") is None
                else float(limit_state["provided_asw_per_s_mm2_per_m"])
            ),
        ),
    )
    variables = _variables(data)
    dependence = _dependence(data)
    target_reliability = _target_reliability(data)

    pipeline = _expect_dict(data.get("pipeline", {}), "pipeline")
    mlp_raw = _expect_dict(pipeline.get("mlp", {}), "pipeline.mlp")
    mlp = MLPConfig(
        hidden_layers=tuple(
            int(value) for value in mlp_raw.get("hidden_layers", [64, 64])
        ),
        learning_rate=float(mlp_raw.get("learning_rate", 1.0e-3)),
        batch_size=int(mlp_raw.get("batch_size", 64)),
        epochs=int(mlp_raw.get("epochs", 1000)),
        patience=int(mlp_raw.get("patience", 60)),
        seed=int(mlp_raw.get("seed", 42)),
    )
    result = run_research_pipeline(
        evaluator,
        variables,
        config=ResearchPipelineConfig(
            sample_count=int(pipeline.get("sample_count", 1500)),
            dataset_seed=int(pipeline.get("dataset_seed", 20260926)),
            split_seed=int(pipeline.get("split_seed", 20260927)),
            train_fraction=float(pipeline.get("train_fraction", 0.70)),
            validation_fraction=float(pipeline.get("validation_fraction", 0.15)),
            backend=str(pipeline.get("backend", "numpy")),
            mlp=mlp,
            run_form=bool(pipeline.get("run_form", True)),
            monte_carlo_samples=int(pipeline.get("surrogate_monte_carlo_samples", 0)),
            reliability_seed=int(pipeline.get("reliability_seed", 20260928)),
            dependence=dependence,
        ),
    )

    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / "study_config.json", data)
    result.dataset.write_csv(output / "dataset.csv")
    result.split.train.write_csv(output / "train.csv")
    result.split.validation.write_csv(output / "validation.csv")
    result.split.test.write_csv(output / "test.csv")
    if hasattr(result.model, "save_npz"):
        result.model.save_npz(output / "ann_model.npz")
    elif hasattr(result.model, "save"):
        result.model.save(output / "ann_model.keras")

    validation_raw = _expect_dict(data.get("validation", {}), "validation")
    direct_check = validate_surrogate_against_direct(
        evaluator,
        result.model,
        variables,
        int(validation_raw.get("fresh_direct_samples", 250)),
        seed=int(validation_raw.get("seed", 20260929)),
        near_limit_state_fraction=float(
            validation_raw.get("near_limit_state_fraction", 0.10)
        ),
        dependence=dependence,
    )
    direct_mc_samples = int(validation_raw.get("direct_monte_carlo_samples", 0))
    direct_mc = (
        {
            target: direct_monte_carlo_reliability(
                evaluator,
                variables,
                target,
                direct_mc_samples,
                seed=int(validation_raw.get("seed", 20260929)) + index + 1,
                dependence=dependence,
            )
            for index, target in enumerate(evaluator.target_names)
        }
        if direct_mc_samples > 0
        else {}
    )
    rbdo_result = _rbdo(data, result.model, variables, dependence)
    convergence_raw = data.get("sample_size_convergence")
    convergence_result = None
    if isinstance(convergence_raw, dict) and convergence_raw.get("enabled") is True:
        convergence_result = sample_size_convergence(
            evaluator,
            variables,
            tuple(int(value) for value in convergence_raw["sample_counts"]),
            base_seed=int(convergence_raw.get("base_seed", 20260930)),
            tolerance=float(convergence_raw.get("tolerance", 0.05)),
            dependence=dependence,
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
        candidate_direct = {"nominal_margins": asdict(candidate_nominal)}
        candidate_direct["nominal_within_training_feature_domain"] = (
            result.feature_domain.contains(np.asarray(
                [variable.expected_value for variable in candidate_variables], dtype=float
            ))
        )
        candidate_samples = int(_expect_dict(data["rbdo"], "rbdo").get("direct_check_samples", 0))
        if candidate_samples > 0:
            candidate_direct["monte_carlo"] = {
                target: asdict(direct_monte_carlo_reliability(
                    evaluator, candidate_variables, target, candidate_samples,
                    seed=int(validation_raw.get("seed", 20260929)) + 100 + index,
                    dependence=dependence,
                ))
                for index, target in enumerate(evaluator.target_names)
            }

    output_files = sorted(path for path in output.iterdir() if path.is_file())

    summary = {
        "status": (
            "EXPLORATORY: unconfirmed probability/action/dependence assumptions; "
            "no reliability or RBDO result is accepted for design or thesis conclusions"
            if args.exploratory else
            "confirmed configuration executed; numerical results still require validation review"
        ),
        "assumptions_confirmed": data.get("assumptions_confirmed") is True,
        "config_sha256": _sha256(args.config),
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
        },
        "output_sha256": {path.name: _sha256(path) for path in output_files},
        "target_reliability": asdict(target_reliability),
        "dependence": (
            None
            if dependence is None
            else {
                "names": dependence.names,
                "correlation_matrix": dependence.correlation.tolist(),
            }
        ),
        "baseline": {
            "project_name": baseline.project.name,
            "material_fck_mpa": baseline.project.materials.fck_mpa,
            "material_fyk_mpa": baseline.project.materials.fyk_mpa,
            "material_ecm_mpa": baseline.project.materials.elastic_modulus_mpa,
            "moment_girder_index": baseline.moment_girder_index,
            "shear_girder_index": baseline.shear_girder_index,
            "deflection_girder_index": baseline.deflection_girder_index,
            "deflection_basis": baseline.deflection_basis,
            "provenance": baseline.provenance,
        },
        "dataset_rows": result.dataset.size,
        "invalid_dataset_rows": result.dataset.invalid_samples,
        "split_rows": {
            "train": result.split.train.size,
            "validation": result.split.validation.size,
            "test": result.split.test.size,
        },
        "training_history": (
            asdict(result.history)
            if is_dataclass(result.history)
            else getattr(result.history, "history", {})
        ),
        "training_feature_domain": asdict(result.feature_domain),
        "test_metrics": asdict(result.test_metrics),
        "fresh_direct_validation": asdict(direct_check),
        "form": {name: asdict(value) for name, value in result.form.items()},
        "surrogate_monte_carlo": {
            name: asdict(value) for name, value in result.monte_carlo.items()
        },
        "direct_monte_carlo": {name: asdict(value) for name, value in direct_mc.items()},
        "rbdo": None if rbdo_result is None else asdict(rbdo_result),
        "rbdo_candidate_direct": candidate_direct,
        "sample_size_convergence": (
            None if convergence_result is None else asdict(convergence_result)
        ),
    }
    _write_json(output / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
