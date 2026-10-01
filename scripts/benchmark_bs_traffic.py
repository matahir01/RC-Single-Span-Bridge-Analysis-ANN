"""Capture reproducible coarse BS 5400 traffic outputs and timing on one runner."""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from time import perf_counter


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    sys.path[:0] = [str(root / "src"), str(root / "examples")]

    from thesis_bridge_15m import thesis_bridge_15m

    from rc_single_span.codes.eurocode.combinations import EurocodeServiceabilityFactors
    from rc_single_span.verification.reference_runner import (
        ReferenceRunConfig,
        run_reference_project,
    )

    config = ReferenceRunConfig(
        elastic_modulus_mpa=34000,
        eurocode_sls_factors=EurocodeServiceabilityFactors(
            psi1_traffic=0.75, psi2_traffic=0.0,
        ),
        bs_ha_longitudinal_step_m=7.5,
        bs_hb_longitudinal_step_m=15.0,
        bs_hb_transverse_step_m=3.5,
        bs_combined_hb_longitudinal_step_m=15.0,
        bs_combined_hb_transverse_step_m=3.5,
        bs_combined_ha_kel_step_m=15.0,
        retain_all_cases=False,
    )
    start = perf_counter()
    result = run_reference_project(thesis_bridge_15m(), config=config, code_route="bs5400")
    assert result.bs_traffic is not None
    suite = result.bs_traffic
    output = {
        "elapsed_s": perf_counter() - start,
        "config": asdict(config),
        "traffic": {
            name: {
                "evaluated_case_count": search.evaluated_case_count,
                "girders": [asdict(item) for item in search.girders],
                "stations": [asdict(item) for item in search.station_moments],
                "retained_case_ids": [
                    case.case_id if hasattr(case, "case_id") else case.placement.case_id
                    for case in search.cases
                ],
            }
            for name, search in (("ha", suite.ha), ("hb", suite.hb), ("ha_hb", suite.ha_hb))
        },
        "combinations": [asdict(item) for item in result.bs5400_combinations],
    }
    args.output.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    print(f"BS: {output['elapsed_s']:.2f} s; "
          f"HA/HB/HA+HB: {[search.evaluated_case_count for search in (suite.ha, suite.hb, suite.ha_hb)]}")


if __name__ == "__main__":
    main()
