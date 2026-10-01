"""Extend the independent-LHS response audit under an unconfirmed study config."""

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from run_reference_ann_reliability import _dependence, _variables
from thesis_bridge_15m import thesis_bridge_15m

from rc_single_span.codes.eurocode.combinations import EurocodeServiceabilityFactors
from rc_single_span.research.baseline import extract_bs_en_reliability_baseline
from rc_single_span.research.convergence import sample_size_convergence
from rc_single_span.research.evaluator import BridgeLimitStateEvaluator, ReliabilityModelConfig
from rc_single_span.verification.reference_runner import ReferenceRunConfig, run_reference_project


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--counts", type=int, nargs="+", default=[2000, 3000, 4000, 6000, 8000])
    parser.add_argument("--base-seed", type=int, default=20261001)
    parser.add_argument("--tolerance", type=float, default=0.05)
    args = parser.parse_args()

    raw = args.config.read_bytes()
    data = json.loads(raw)
    if data.get("assumptions_confirmed") is not False:
        raise ValueError("This exploratory audit requires assumptions_confirmed=false.")
    reference = data["reference_run"]
    sls = reference["serviceability_factors"]
    deterministic = run_reference_project(
        thesis_bridge_15m(),
        config=ReferenceRunConfig(
            elastic_modulus_mpa=float(reference["elastic_modulus_mpa"]),
            eurocode_sls_factors=EurocodeServiceabilityFactors(
                psi1_traffic=float(sls["psi1_traffic"]),
                psi1_udl_traffic=float(sls["psi1_udl_traffic"]),
                psi2_traffic=float(sls["psi2_traffic"]),
            ),
            lm1_longitudinal_step_m=float(reference["lm1_longitudinal_step_m"]),
            retain_all_cases=bool(reference["retain_all_cases"]),
            lm1_udl_influence_surface=bool(reference["lm1_udl_influence_surface"]),
        ),
        code_route="bs_en",
    )
    limit = data["limit_state_model"]
    evaluator = BridgeLimitStateEvaluator(
        extract_bs_en_reliability_baseline(deterministic),
        ReliabilityModelConfig(
            deflection_limit_mm=float(limit["deflection_limit_mm"]),
            gamma_c=float(limit["gamma_c"]),
            gamma_s=float(limit["gamma_s"]),
            alpha_cc=float(limit["alpha_cc"]),
            cot_theta=float(limit["cot_theta"]),
            z_factor=float(limit["z_factor"]),
            provided_asw_per_s_mm2_per_m=limit["provided_asw_per_s_mm2_per_m"],
        ),
    )
    audit = sample_size_convergence(
        evaluator, _variables(data), tuple(args.counts),
        base_seed=args.base_seed, tolerance=args.tolerance,
        dependence=_dependence(data),
    )
    output = {
        "status": "exploratory; unconfirmed action/dependence/project criteria",
        "config_sha256": hashlib.sha256(raw).hexdigest(),
        "reference_step_m": reference["lm1_longitudinal_step_m"],
        "result": asdict(audit),
        "recommended_minimum_sample_count": audit.recommended_minimum_sample_count,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2), encoding="utf-8")
    for point in audit.points:
        print(f"n={point.sample_count} seed={point.seed} "
              f"maximum_change={point.maximum_standardized_change} "
              f"converged={point.converged_from_previous}")
    print(f"recommended_minimum_sample_count={audit.recommended_minimum_sample_count}")


if __name__ == "__main__":
    main()
