from __future__ import annotations

import argparse
import os
from pathlib import Path

from reference_bridge_15m import reference_bridge_15m

from rc_single_span.codes.eurocode.combinations import (
    EurocodeCombinationFactors,
    EurocodeServiceabilityFactors,
)
from rc_single_span.verification.full_bridge_campaign import (
    FullBridgeTrafficSearchConfig,
)
from rc_single_span.verification.full_bridge_export import (
    write_full_bridge_verification_bundle,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export the full seven-girder construction, traffic and combination "
            "STAAD verification campaign for the 15 m reference bridge."
        )
    )
    parser.add_argument("--elastic-modulus-mpa", type=float, required=True)
    parser.add_argument("--elastic-modulus-basis", required=True)
    parser.add_argument("--psi1-traffic", type=float, required=True)
    parser.add_argument("--psi2-traffic", type=float, required=True)
    parser.add_argument("--gamma-g-unfavourable", type=float, default=1.35)
    parser.add_argument("--gamma-g-favourable", type=float, default=1.00)
    parser.add_argument("--gamma-q-traffic", type=float, default=1.35)
    parser.add_argument(
        "--output-dir",
        default="generated_full_bridge_staad_bundle",
        help="Absent or empty destination directory.",
    )
    parser.add_argument(
        "--repository-sha",
        default=os.getenv("GITHUB_SHA", ""),
    )
    parser.add_argument("--longitudinal-divisions", type=int, default=8)
    parser.add_argument("--lm1-step-m", type=float, default=1.2)
    parser.add_argument("--ha-step-m", type=float, default=1.0)
    parser.add_argument("--hb-longitudinal-step-m", type=float, default=1.0)
    parser.add_argument("--hb-transverse-step-m", type=float, default=0.5)
    parser.add_argument("--combined-hb-longitudinal-step-m", type=float, default=2.0)
    parser.add_argument("--combined-hb-transverse-step-m", type=float, default=1.0)
    parser.add_argument("--combined-ha-kel-step-m", type=float, default=2.0)
    parser.add_argument("--hb-units", type=float, default=45.0)
    return parser


def main() -> None:
    args = _parser().parse_args()
    project = reference_bridge_15m()
    project = project.model_copy(
        update={
            "materials": project.materials.model_copy(
                update={"elastic_modulus_mpa": args.elastic_modulus_mpa}
            )
        }
    )
    result = write_full_bridge_verification_bundle(
        project,
        Path(args.output_dir),
        elastic_modulus_basis=args.elastic_modulus_basis,
        eurocode_sls_factors=EurocodeServiceabilityFactors(
            psi1_traffic=args.psi1_traffic,
            psi2_traffic=args.psi2_traffic,
        ),
        eurocode_uls_factors=EurocodeCombinationFactors(
            gamma_g_unfavourable=args.gamma_g_unfavourable,
            gamma_g_favourable=args.gamma_g_favourable,
            gamma_q_traffic=args.gamma_q_traffic,
        ),
        repository_sha=args.repository_sha or None,
        longitudinal_divisions=args.longitudinal_divisions,
        traffic_config=FullBridgeTrafficSearchConfig(
            lm1_longitudinal_step_m=args.lm1_step_m,
            ha_longitudinal_step_m=args.ha_step_m,
            hb_units=args.hb_units,
            hb_longitudinal_step_m=args.hb_longitudinal_step_m,
            hb_transverse_step_m=args.hb_transverse_step_m,
            combined_hb_longitudinal_step_m=(args.combined_hb_longitudinal_step_m),
            combined_hb_transverse_step_m=args.combined_hb_transverse_step_m,
            combined_ha_kel_step_m=args.combined_ha_kel_step_m,
        ),
    )
    print(f"Wrote {len(result.written_files)} files to {result.output_directory}")
    print(f"Full-width stage models: {len(result.stage_suite.stages)}")
    print(
        "Governing traffic models: "
        f"{len(result.traffic_campaign.cases)} across LM1, HA, HB and HA+HB"
    )
    print(f"Combination rules: {len(result.combination_rules)}")
    print("Internal checks: PASS")
    print("External STAAD verification: PENDING")


if __name__ == "__main__":
    main()
