"""Audit the next exhaustive HA+HB grid against the saved half-step reference.

Run with --run to solve the finer grid; without it, compare saved snapshots.
This checks response-grid sensitivity, not suitability of the bridge design.
"""

import argparse
import gzip
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

from rc_single_span.core.progress import AnalysisControl
from rc_single_span.gui.project_state import GuiProjectState
from rc_single_span.traffic.bs5400_combined import run_ha_hb_combined_grillage_search


def read(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        return json.load(source)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(path: Path) -> None:
    start = perf_counter()
    reported: dict[str, int] = {}

    def progress(phase: str, completed: int, total: int) -> None:
        if not phase.startswith("BS HA+HB: spacing") or total <= 0:
            return
        decile = completed * 10 // total
        if decile > reported.get(phase, -1):
            reported[phase] = decile
            print(f"{phase}: {completed:,}/{total:,} ({decile * 10}%), "
                  f"elapsed {perf_counter() - start:.1f} s", flush=True)

    settings = {
        "units": 45,
        "hb_longitudinal_step_m": 0.5,
        "hb_transverse_step_m": 0.25,
        "ha_kel_step_m": 0.5,
    }
    search = run_ha_hb_combined_grillage_search(
        GuiProjectState().build_project(), retain_all_cases=False,
        control=AnalysisControl(progress), **settings,
    )
    record = {
        "settings": settings,
        "elapsed_s": perf_counter() - start,
        "evaluated_case_count": search.evaluated_case_count,
        "girders": [asdict(item) for item in search.girders],
        "station_moments": [asdict(item) for item in search.station_moments],
        "retained_case_ids": [item.placement.case_id for item in search.cases],
        "kel_exhaustive": search.kel_combinations_exhaustive,
        "assignment_exhaustive": search.ha_assignment_search_exhaustive,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as target:
        json.dump(record, target, sort_keys=True, separators=(",", ":"))
    print(f"Saved {search.evaluated_case_count:,} placements in "
          f"{record['elapsed_s']:.1f} s", flush=True)


def compare(half_path: Path, fine_path: Path, tolerance: float) -> dict:
    half = read(half_path)["ha_hb"]
    fine = read(fine_path)
    components = {}
    for quantity in ("moment_knm", "shear_kn", "torsion_knm", "deflection_mm"):
        changes = [
            abs(coarse[quantity]["value"] - refined[quantity]["value"])
            / max(abs(refined[quantity]["value"]), 1e-9)
            for coarse, refined in zip(half["girders"], fine["girders"], strict=True)
        ]
        worst = max(range(len(changes)), key=changes.__getitem__)
        components[quantity] = {
            "maximum_relative_change": changes[worst],
            "girder_index": worst + 1,
            "per_girder_relative_change": changes,
        }
    maximum = max(item["maximum_relative_change"] for item in components.values())
    exhaustive = bool(fine["kel_exhaustive"] and fine["assignment_exhaustive"])
    return {
        "project": "GUI default 15 m seven-girder rectangular bridge, BS 5400 / BD 37, 45 HB units",
        "half_step_snapshot_sha256": sha256(half_path),
        "second_refinement_snapshot_sha256": sha256(fine_path),
        "half_step_settings": half["settings"],
        "second_refinement_settings": fine["settings"],
        "half_step_placements": half["evaluated_case_count"],
        "second_refinement_placements": fine["evaluated_case_count"],
        "second_refinement_elapsed_s": fine["elapsed_s"],
        "exhaustive_lane_and_kel_search": exhaustive,
        "component_changes": components,
        "maximum_relative_change": maximum,
        "relative_tolerance": tolerance,
        "girder_envelope_criterion_met": exhaustive and maximum <= tolerance,
        "limitations": [
            "Two-grid girder response sensitivity is not an independent proof of global convergence.",
            "KEL edge coordinates change with the step, so the finer grid is not a strict superset.",
            "Station moment shape and all-cases retention are not checked in this audit.",
            "Design validity also requires project actions, code scope, details and independent review.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--half", type=Path, default=Path(
        "docs/benchmarks/bs_traffic_halved_grid_2026-10-01.json.gz"))
    parser.add_argument("--fine", type=Path, default=Path(
        "docs/benchmarks/bs_traffic_second_refinement_2026-10-02.json.gz"))
    parser.add_argument("--output", type=Path, default=Path(
        "docs/benchmarks/bs_traffic_second_refinement_2026-10-02.json"))
    parser.add_argument("--tolerance", type=float, default=0.05)
    args = parser.parse_args()
    if args.run:
        capture(args.fine)
    audit = compare(args.half, args.fine, args.tolerance)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(f"Second refinement: {audit['maximum_relative_change']:.3%}; "
          f"criterion={audit['girder_envelope_criterion_met']}")


if __name__ == "__main__":
    main()
