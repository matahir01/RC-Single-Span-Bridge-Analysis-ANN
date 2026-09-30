"""Capture a deterministic BS EN reference run from a selected source checkout."""

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
    parser.add_argument("--step", type=float, default=3.0)
    args = parser.parse_args()
    root = args.root.resolve()
    sys.path[:0] = [str(root / "src"), str(root / "examples")]

    from thesis_bridge_15m import thesis_bridge_15m

    from rc_single_span.codes.eurocode.combinations import EurocodeServiceabilityFactors
    from rc_single_span.design.project import EC2DesignInputs
    from rc_single_span.verification.reference_runner import (
        ReferenceRunConfig,
        run_reference_project,
    )

    start = perf_counter()
    result = run_reference_project(
        thesis_bridge_15m(),
        config=ReferenceRunConfig(
            elastic_modulus_mpa=34000,
            eurocode_sls_factors=EurocodeServiceabilityFactors(
                psi1_traffic=0.75, psi1_udl_traffic=0.4, psi2_traffic=0,
            ),
            lm1_longitudinal_step_m=args.step,
            retain_all_cases=False,
        ),
        ec2_design_inputs=EC2DesignInputs(
            effective_depth_m=1.10, bar_diameter_mm=32.0, bar_spacing_mm=90.0,
            cover_mm=50.0, fct_eff_mpa=3.2, crack_limit_mm=0.30,
            maximum_neutral_axis_ratio=0.45, ecm_mpa=34000.0,
        ),
        code_route="bs_en",
    )
    fields = ("moment_knm", "shear_kn", "torsion_knm", "deflection_mm")
    output = {
        "elapsed_s": perf_counter() - start,
        "lm1_count": result.lm1.evaluated_case_count,
        "girders": [
            {name: asdict(getattr(girder, name)) for name in fields}
            for girder in result.lm1.girders
        ],
        "stations": [
            [{"x_m": station.x_m, "moment": asdict(station.moment_knm)}
             for station in girder.stations]
            for girder in result.lm1.station_moments
        ],
        "cases": [
            {"id": case.placement.case_id,
             "tandem": [(lane.lane_number, lane.tandem_lead_x_m)
                        for lane in case.placement.lanes],
             "uniform_loads": [asdict(load) for load in case.model.load_cases[0].uniform_loads]}
            for case in result.lm1.cases
        ],
        "combinations": [
            {"girder": item.girder_index,
             "uls": asdict(item.combinations.persistent_uls.effects),
             "frequent": asdict(item.combinations.frequent_sls.effects)}
            for item in result.eurocode_combinations
        ],
        "design": [asdict(item) for item in result.eurocode_design],
    }
    args.output.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    print(f"{root.name}: {args.step:g} m, {output['elapsed_s']:.2f} s, "
          f"{len(output['cases'])} retained cases")


if __name__ == "__main__":
    main()
