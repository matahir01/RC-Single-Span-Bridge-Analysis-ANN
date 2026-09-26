"""Run a traceable convergence audit for the BS EN LM1 influence-surface search."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from reference_bridge_15m import reference_bridge_15m
from rc_single_span.traffic.lm1_influence_convergence import (
    run_lm1_influence_grillage_search_converged,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--initial-step", type=float, default=2.4)
    parser.add_argument("--minimum-step", type=float, default=1.2)
    parser.add_argument("--relative-tolerance", type=float, default=0.05)
    parser.add_argument("--max-refinements", type=int, default=1)
    parser.add_argument("--max-exhaustive", type=int, default=5000)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("bs_en_lm1_convergence_audit.json"),
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    project = reference_bridge_15m()
    audit = run_lm1_influence_grillage_search_converged(
        project,
        initial_longitudinal_step_m=args.initial_step,
        minimum_longitudinal_step_m=args.minimum_step,
        relative_tolerance=args.relative_tolerance,
        max_refinements=args.max_refinements,
        max_exhaustive_tandem_combinations=args.max_exhaustive,
    )

    payload = {
        "basis": "BS EN 1991-2:2003 LM1 influence-surface adverse-region search",
        "project": project.name,
        "relative_tolerance": audit.relative_tolerance,
        "converged": audit.converged,
        "final_longitudinal_step_m": audit.result.longitudinal_step_m,
        "tandem_combinations_exhaustive": audit.result.tandem_combinations_exhaustive,
        "theoretical_tandem_combinations_per_transverse_layout": (
            audit.result.theoretical_tandem_combinations_per_transverse_layout
        ),
        "evaluated_case_count": audit.result.evaluated_case_count,
        "search_strategy": audit.result.search_strategy,
        "refinements": [
            {
                "coarse_step_m": item.coarse_step_m,
                "fine_step_m": item.fine_step_m,
                "maximum_relative_change": item.maximum_relative_change,
                "governing_quantity": item.governing_quantity,
                "girder_index": item.girder_index,
            }
            for item in audit.refinements
        ],
    }
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if audit.converged else 2


if __name__ == "__main__":
    raise SystemExit(main())
