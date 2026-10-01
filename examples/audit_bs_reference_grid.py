"""Reproduce the reference BS traffic half-step check and compare girder envelopes.

The preserved default search snapshot is from the verified, optimized full BS
route. Use --run to recalculate the three finer searches (several minutes).
"""

import argparse
import gzip
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

from rc_single_span.gui.project_state import GuiProjectState
from rc_single_span.traffic.bs5400 import run_ha_grillage_search, run_hb_grillage_search
from rc_single_span.traffic.bs5400_combined import run_ha_hb_combined_grillage_search


def _read(path: Path) -> dict:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(path: Path) -> None:
    project = GuiProjectState().build_project()
    result = {}
    searches = (
        ("ha", run_ha_grillage_search, {"longitudinal_step_m": 0.5}),
        ("hb", run_hb_grillage_search, {
            "units": 45, "longitudinal_step_m": 0.5, "transverse_step_m": 0.25,
        }),
        ("ha_hb", run_ha_hb_combined_grillage_search, {
            "units": 45, "hb_longitudinal_step_m": 1.0,
            "hb_transverse_step_m": 0.5, "ha_kel_step_m": 1.0,
        }),
    )
    for name, function, settings in searches:
        start = perf_counter()
        search = function(project, retain_all_cases=False, **settings)
        result[name] = {
            "name": name,
            "settings": settings,
            "elapsed_s": perf_counter() - start,
            "evaluated_case_count": search.evaluated_case_count,
            "girders": [asdict(item) for item in search.girders],
            "station_moments": [asdict(item) for item in search.station_moments],
            "retained_case_ids": [
                item.case_id if hasattr(item, "case_id") else item.placement.case_id
                for item in search.cases
            ],
            "kel_exhaustive": getattr(search, "kel_combinations_exhaustive", True),
            "assignment_exhaustive": getattr(search, "ha_assignment_search_exhaustive", True),
        }
        print(f"{name}: {search.evaluated_case_count} placements; "
              f"{result[name]['elapsed_s']:.1f} s", flush=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as stream:
        json.dump(result, stream, sort_keys=True, separators=(",", ":"))


def compare(baseline_path: Path, fine_path: Path, tolerance: float) -> dict:
    baseline = _read(baseline_path)["traffic"]
    fine = _read(fine_path)
    searches = {}
    for name in ("ha", "hb", "ha_hb"):
        coarse_record, fine_record = baseline[name], fine[name]
        components = {}
        for quantity in ("moment_knm", "shear_kn", "torsion_knm", "deflection_mm"):
            changes = [
                (abs(coarse[quantity]["value"] - refined[quantity]["value"])
                 / max(abs(refined[quantity]["value"]), 1.0e-9))
                for coarse, refined in zip(
                    coarse_record["girders"], fine_record["girders"], strict=True,
                )
            ]
            worst = max(range(len(changes)), key=changes.__getitem__)
            components[quantity] = {
                "maximum_relative_change": changes[worst],
                "girder_index": worst + 1,
            }
        exhaustive = bool(fine_record["kel_exhaustive"] and fine_record["assignment_exhaustive"])
        maximum = max(item["maximum_relative_change"] for item in components.values())
        searches[name] = {
            "coarse_placements": coarse_record["evaluated_case_count"],
            "fine_placements": fine_record["evaluated_case_count"],
            "fine_settings": fine_record["settings"],
            "fine_search_exhaustive": exhaustive,
            "component_changes": components,
            "maximum_relative_change": maximum,
            "girder_envelope_criterion_met": exhaustive and maximum <= tolerance,
        }
    return {
        "project": "GUI default 15 m seven-girder rectangular bridge, BS 5400 / BD 37, 45 HB units",
        "default_snapshot_sha256": _sha(baseline_path),
        "half_step_snapshot_sha256": _sha(fine_path),
        "criterion": "maximum girder M/V/T/deflection envelope change / fine value",
        "relative_tolerance": tolerance,
        "searches": searches,
        "default_grid_criterion_met": all(
            item["girder_envelope_criterion_met"] for item in searches.values()
        ),
        "limitations": [
            "A passing two-grid response check is not independent bridge approval.",
            "Station moment shapes and all-cases retention were not compared in this audit.",
            "Grid response convergence is independent of code, model and project input validity.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Recalculate half-step searches")
    parser.add_argument("--baseline", type=Path, default=Path(
        "docs/benchmarks/bs_traffic_fine_optimized_2026-10-01.json.gz"))
    parser.add_argument("--fine", type=Path, default=Path(
        "docs/benchmarks/bs_traffic_halved_grid_2026-10-01.json.gz"))
    parser.add_argument("--output", type=Path, default=Path(
        "docs/benchmarks/bs_traffic_grid_refinement_2026-10-01.json"))
    parser.add_argument("--tolerance", type=float, default=0.05)
    args = parser.parse_args()
    if args.run:
        capture(args.fine)
    audit = compare(args.baseline, args.fine, args.tolerance)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    for name, record in audit["searches"].items():
        print(f"{name}: maximum {record['maximum_relative_change']:.3%}; "
              f"criterion={record['girder_envelope_criterion_met']}")
    print(f"Default grid meets response criterion: {audit['default_grid_criterion_met']}")


if __name__ == "__main__":
    main()
