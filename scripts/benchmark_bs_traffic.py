"""Capture reproducible coarse BS 5400 outputs and compare solvers fairly.

The optional legacy-run alignment applies only the current support-anchored HA
KEL positions. That holds placement physics constant while checking the old
and optimized solvers; the separate refinement audit measures grid sensitivity.
"""

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from time import perf_counter


def _support_anchored_kel_positions(
    span_m: float,
    step_m: float,
    *,
    merge_coordinates: Callable[[tuple[float, ...]], tuple[float, ...]],
) -> tuple[float, ...]:
    """Backport the current placement rule for a fair legacy-solver run."""
    if step_m <= 0.0:
        raise ValueError("HA KEL search step must be positive.")
    minimum_interval = 0.05
    if step_m < minimum_interval - 1.0e-12:
        raise ValueError("HA KEL search step must be at least 0.05 m.")

    values = [0.0, span_m]
    x = step_m
    while x < span_m - 1.0e-9:
        values.append(round(x, 12))
        x += step_m
    values = sorted(merge_coordinates(tuple(values)))
    if len(values) > 2 and values[-1] - values[-2] < minimum_interval - 1.0e-9:
        values.pop(-2)
    midpoint = span_m / 2.0
    if min(abs(midpoint - value) for value in values) >= minimum_interval - 1.0e-9:
        values.append(midpoint)
    return merge_coordinates(tuple(values))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--align-support-anchored-kel-grid",
        action="store_true",
        help="run the legacy solver with the current HA placement rule",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    sys.path[:0] = [str(root / "src"), str(root / "examples")]

    from thesis_bridge_15m import thesis_bridge_15m

    from rc_single_span.codes.eurocode.combinations import EurocodeServiceabilityFactors
    from rc_single_span.traffic import bs5400 as bs_traffic
    from rc_single_span.traffic import bs5400_combined as bs_traffic_combined

    if args.align_support_anchored_kel_grid:
        def kel_positions(span_m: float, step_m: float) -> tuple[float, ...]:
            return _support_anchored_kel_positions(
                span_m,
                step_m,
                merge_coordinates=bs_traffic._merge_coordinates,
            )

        # Both searches import this helper into their own module namespace.
        bs_traffic._kel_positions = kel_positions
        bs_traffic_combined._kel_positions = kel_positions
        print("Legacy HA searches use the current support-anchored KEL grid.")

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
