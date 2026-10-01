"""Replicated LHS and fresh direct boundary challenge for an exploratory ANN."""

import argparse
import csv
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from run_reference_ann_reliability import _dependence, _variables
from thesis_bridge_15m import thesis_bridge_15m

from rc_single_span.codes.eurocode.combinations import EurocodeServiceabilityFactors
from rc_single_span.research.baseline import extract_bs_en_reliability_baseline
from rc_single_span.research.convergence import replicated_sample_size_convergence
from rc_single_span.research.dataset import ReliabilityDataset
from rc_single_span.research.evaluator import BridgeLimitStateEvaluator, ReliabilityModelConfig
from rc_single_span.research.surrogate import NumpyMLPRegressor
from rc_single_span.research.validation import challenge_surrogate_at_direct_boundaries
from rc_single_span.verification.reference_runner import ReferenceRunConfig, run_reference_project


def _training_limits(path: Path, names: tuple[str, ...]) -> tuple[tuple[float, float], ...]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("Training CSV has no rows.")
    return tuple(
        (min(float(row[name]) for row in rows), max(float(row[name]) for row in rows))
        for name in names
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--test", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--counts", type=int, nargs="+", default=[2000, 4000, 8000])
    parser.add_argument("--replications", type=int, default=3)
    parser.add_argument("--iterations", type=int, default=25)
    args = parser.parse_args()

    raw = args.config.read_bytes()
    data = json.loads(raw)
    if data.get("assumptions_confirmed") is not False:
        raise ValueError("This audit requires assumptions_confirmed=false.")
    reference = data["reference_run"]
    factors = reference["serviceability_factors"]
    deterministic = run_reference_project(
        thesis_bridge_15m(),
        config=ReferenceRunConfig(
            elastic_modulus_mpa=float(reference["elastic_modulus_mpa"]),
            eurocode_sls_factors=EurocodeServiceabilityFactors(
                psi1_traffic=float(factors["psi1_traffic"]),
                psi1_udl_traffic=float(factors["psi1_udl_traffic"]),
                psi2_traffic=float(factors["psi2_traffic"]),
            ),
            lm1_longitudinal_step_m=float(reference["lm1_longitudinal_step_m"]),
            retain_all_cases=bool(reference["retain_all_cases"]),
            lm1_udl_influence_surface=bool(reference["lm1_udl_influence_surface"]),
        ),
        code_route="bs_en",
    )
    assumptions = data["limit_state_model"]
    evaluator = BridgeLimitStateEvaluator(
        extract_bs_en_reliability_baseline(deterministic),
        ReliabilityModelConfig(
            deflection_limit_mm=float(assumptions["deflection_limit_mm"]),
            gamma_c=float(assumptions["gamma_c"]),
            gamma_s=float(assumptions["gamma_s"]),
            alpha_cc=float(assumptions["alpha_cc"]),
            cot_theta=float(assumptions["cot_theta"]),
            z_factor=float(assumptions["z_factor"]),
            provided_asw_per_s_mm2_per_m=assumptions["provided_asw_per_s_mm2_per_m"],
        ),
    )
    variables = _variables(data)
    model = NumpyMLPRegressor.load_npz(
        args.model, feature_names=evaluator.feature_names, target_names=evaluator.target_names,
    )
    untouched_test = ReliabilityDataset.read_csv(
        args.test, feature_names=evaluator.feature_names, target_names=evaluator.target_names,
    )
    test_metrics = model.evaluate(untouched_test)
    stability = replicated_sample_size_convergence(
        evaluator, variables, tuple(args.counts),
        replications=args.replications, base_seed=20261001,
        dependence=_dependence(data),
    )
    challenges = challenge_surrogate_at_direct_boundaries(
        evaluator, model, variables, iterations=args.iterations,
    )
    limits = _training_limits(args.train, evaluator.feature_names)
    output = {
        "status": "exploratory numerical diagnostics; action/dependence/criteria unconfirmed",
        "config_sha256": hashlib.sha256(raw).hexdigest(),
        "model_sha256": hashlib.sha256(args.model.read_bytes()).hexdigest(),
        "train_sha256": hashlib.sha256(args.train.read_bytes()).hexdigest(),
        "test_sha256": hashlib.sha256(args.test.read_bytes()).hexdigest(),
        "held_out_test_metrics": asdict(test_metrics),
        "reference_step_m": reference["lm1_longitudinal_step_m"],
        "replicated_lhs": {
            "result": asdict(stability),
            "response_statistics_screen_passed": stability.stability_screen_passed,
            "rare_event_reliability_accepted": False,
        },
        "direct_boundary_challenges": [
            {
                **asdict(item),
                "within_training_axis_ranges": (
                    None if item.features is None else all(
                        low <= feature <= high
                        for feature, (low, high) in zip(item.features, limits, strict=True)
                    )
                ),
                "outside_training_axes": (
                    [] if item.features is None else [
                        name for name, feature, (low, high) in zip(
                            evaluator.feature_names, item.features, limits, strict=True,
                        ) if not low <= feature <= high
                    ]
                ),
            }
            for item in challenges
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2), encoding="utf-8")
    for point in stability.points:
        print(f"n={point.sample_count}: within={point.maximum_within_size_change:.4%}, "
              f"mean_change={point.mean_change_from_previous}")
    for item in output["direct_boundary_challenges"]:
        print(f"{item['target_name']}: bracket={item['bracket_found']} "
              f"error={item['absolute_error']} training_axes={item['within_training_axis_ranges']}")


if __name__ == "__main__":
    main()
