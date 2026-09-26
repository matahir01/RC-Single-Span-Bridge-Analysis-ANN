from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from rc_single_span.codes.eurocode.combinations import EurocodeServiceabilityFactors
from rc_single_span.research.baseline import extract_bs_en_reliability_baseline
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
from rc_single_span.research.validation import (
    direct_monte_carlo_reliability,
    validate_surrogate_against_direct,
)
from rc_single_span.verification.reference_runner import ReferenceRunConfig, run_reference_project
from reference_bridge_15m import reference_bridge_15m


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the config-driven 15 m BS EN ANN/reliability research pipeline."
    )
    parser.add_argument("config", type=Path, help="JSON study configuration")
    parser.add_argument("--output", type=Path, default=Path("artifacts/research"))
    return parser


def _require_confirmed(data: dict[str, object]) -> None:
    if data.get("assumptions_confirmed") is not True:
        raise RuntimeError(
            "Research configuration is not confirmed. Replace illustrative probabilistic "
            "inputs with source-justified study values, then set assumptions_confirmed=true."
        )


def _variables(data: dict[str, object]) -> tuple[RandomVariable, ...]:
    raw = data.get("random_variables")
    if not isinstance(raw, list):
        raise ValueError("random_variables must be a JSON list.")
    variables = tuple(RandomVariable(**item) for item in raw if isinstance(item, dict))
    if tuple(variable.name for variable in variables) != FEATURE_NAMES:
        raise ValueError(
            "random_variables must contain exactly the evaluator features, in this order: "
            f"{FEATURE_NAMES}"
        )
    return variables


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _rbdo(data: dict[str, object], model, variables: tuple[RandomVariable, ...]):
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
    )


def main() -> int:
    args = _parser().parse_args()
    data = json.loads(args.config.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Study configuration root must be a JSON object.")
    _require_confirmed(data)

    reference = data.get("reference_run")
    if not isinstance(reference, dict):
        raise ValueError("reference_run configuration is required.")
    sls = reference.get("serviceability_factors")
    if not isinstance(sls, dict):
        raise ValueError("reference_run.serviceability_factors is required.")
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
    deterministic = run_reference_project(reference_bridge_15m(), run_config)
    baseline = extract_bs_en_reliability_baseline(deterministic)

    limit_state = data.get("limit_state_model")
    if not isinstance(limit_state, dict):
        raise ValueError("limit_state_model configuration is required.")
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

    pipeline = data.get("pipeline", {})
    if not isinstance(pipeline, dict):
        raise ValueError("pipeline must be a JSON object.")
    mlp_raw = pipeline.get("mlp", {})
    if not isinstance(mlp_raw, dict):
        raise ValueError("pipeline.mlp must be a JSON object.")
    mlp = MLPConfig(
        hidden_layers=tuple(int(value) for value in mlp_raw.get("hidden_layers", [64, 64])),
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
        ),
    )

    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    result.dataset.write_csv(output / "dataset.csv")
    result.split.train.write_csv(output / "train.csv")
    result.split.validation.write_csv(output / "validation.csv")
    result.split.test.write_csv(output / "test.csv")
    if hasattr(result.model, "save_npz"):
        result.model.save_npz(output / "ann_model.npz")
    elif hasattr(result.model, "save"):
        result.model.save(output / "ann_model.keras")

    validation_raw = data.get("validation", {})
    if not isinstance(validation_raw, dict):
        raise ValueError("validation must be a JSON object.")
    direct_check = validate_surrogate_against_direct(
        evaluator,
        result.model,
        variables,
        int(validation_raw.get("fresh_direct_samples", 250)),
        seed=int(validation_raw.get("seed", 20260929)),
        near_limit_state_fraction=float(
            validation_raw.get("near_limit_state_fraction", 0.10)
        ),
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
            )
            for index, target in enumerate(evaluator.target_names)
        }
        if direct_mc_samples > 0
        else {}
    )
    rbdo_result = _rbdo(data, result.model, variables)

    summary = {
        "status": "research outputs generated; acceptance still depends on validation review",
        "baseline": {
            "moment_girder_index": baseline.moment_girder_index,
            "shear_girder_index": baseline.shear_girder_index,
            "deflection_girder_index": baseline.deflection_girder_index,
            "deflection_basis": baseline.deflection_basis,
            "provenance": baseline.provenance,
        },
        "dataset_rows": result.dataset.size,
        "invalid_dataset_rows": result.dataset.invalid_samples,
        "test_metrics": asdict(result.test_metrics),
        "fresh_direct_validation": asdict(direct_check),
        "form": {name: asdict(value) for name, value in result.form.items()},
        "surrogate_monte_carlo": {
            name: asdict(value) for name, value in result.monte_carlo.items()
        },
        "direct_monte_carlo": {name: asdict(value) for name, value in direct_mc.items()},
        "rbdo": None if rbdo_result is None else asdict(rbdo_result),
    }
    _write_json(output / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
