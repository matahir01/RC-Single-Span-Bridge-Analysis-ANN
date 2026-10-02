"""Reproduce the first vertical-equilibrium failure on the denser BS grid.

Compare the sparse traffic assembly to the general prepared-solver path with
an exactly zero member UDL. Stop after the first failure or 32 solved cases.
"""

import argparse
import json
from dataclasses import replace
from itertools import pairwise
from pathlib import Path

from rc_single_span.analysis.structural_model import UniformLoad
from rc_single_span.gui.project_state import GuiProjectState
from rc_single_span.traffic import bs5400_combined
from rc_single_span.traffic.bs5400 import traffic_equilibrium_tolerance_kn


class _ProbeComplete(Exception):
    pass


def probe(max_cases: int = 32) -> dict:
    if max_cases < 1:
        raise ValueError("max_cases must be positive")
    original = bs5400_combined.solve_prepared_vertical_grillage
    checked = 0
    record: dict = {"status": "no failure in sampled cases", "max_cases": max_cases}

    def compare(prepared, model):
        nonlocal checked, record
        analysis = original(prepared, model)
        checked += 1
        tolerance = traffic_equilibrium_tolerance_kn(analysis)
        if abs(analysis.vertical_equilibrium_residual_kn) > tolerance:
            case = model.load_cases[0]
            general_case = replace(case, uniform_loads=(UniformLoad(
                member_id=model.beams[0].member_id, magnitude_kn_m=0.0,
            ),))
            general = original(prepared, replace(model, load_cases=(general_case,)))
            x_grid = sorted({item.x_m for item in model.nodes})
            y_grid = sorted({item.y_m for item in model.nodes})
            record = {
                "status": "strict vertical-equilibrium gate failed",
                "case_id": case.load_case_id,
                "checked_cases": checked,
                "grid_nodes": len(model.nodes),
                "grid_members": len(model.beams),
                "minimum_x_spacing_m": min(b - a for a, b in pairwise(x_grid)),
                "minimum_y_spacing_m": min(b - a for a, b in pairwise(y_grid)),
                "applied_kn": analysis.total_applied_vertical_load_kn,
                "reaction_kn": analysis.total_vertical_reaction_kn,
                "residual_kn": analysis.vertical_equilibrium_residual_kn,
                "tolerance_kn": tolerance,
                "general_solver_residual_kn": general.vertical_equilibrium_residual_kn,
                "general_and_sparse_results_identical": analysis == general,
                "settings": {
                    "hb_longitudinal_step_m": 0.5,
                    "hb_transverse_step_m": 0.25,
                    "ha_kel_step_m": 0.5,
                },
            }
            raise _ProbeComplete
        if checked >= max_cases:
            record["checked_cases"] = checked
            raise _ProbeComplete
        return analysis

    bs5400_combined.solve_prepared_vertical_grillage = compare
    try:
        bs5400_combined.run_ha_hb_combined_grillage_search(
            GuiProjectState().build_project(), units=45,
            hb_longitudinal_step_m=0.5,
            hb_transverse_step_m=0.25,
            ha_kel_step_m=0.5,
        )
    except _ProbeComplete:
        pass
    finally:
        bs5400_combined.solve_prepared_vertical_grillage = original
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(
        "docs/benchmarks/bs_dense_equilibrium_probe_2026-10-02.json"))
    args = parser.parse_args()
    record = probe()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(f"{record['status']}: {record.get('case_id', 'none')} in "
          f"{record['checked_cases']} cases; sparse/general identical = "
          f"{record.get('general_and_sparse_results_identical', 'n/a')}")


if __name__ == "__main__":
    main()
