"""Audit a pair of exhaustive, origin-anchored HA+HB grids.

Use --run-default, --run-half and --run to generate matched-grid snapshots. The
anchored KEL placement grid includes both supports and nests for the standard
halvings. The comparison checks response-grid sensitivity, not bridge approval.
"""

import argparse
import gzip
import hashlib
import json
import math
from bisect import bisect_right
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

from rc_single_span.core.progress import AnalysisControl
from rc_single_span.gui.project_state import GuiProjectState
from rc_single_span.traffic.bs5400 import _kel_positions
from rc_single_span.traffic.bs5400_combined import run_ha_hb_combined_grillage_search


def read(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        return json.load(source)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare_station_shapes(coarse: dict, fine: dict) -> dict:
    """Compare each coarse absolute moment envelope with a fine-grid shape.

    Coarse station values are linearly interpolated onto every fine station.
    Changes are normalized by that girder's peak fine-grid envelope, avoiding
    unstable pointwise ratios near zero moment.
    """
    girder_changes = []
    for coarse_girder, fine_girder in zip(
        coarse["station_moments"], fine["station_moments"], strict=True,
    ):
        coarse_stations = coarse_girder["stations"]
        fine_stations = fine_girder["stations"]
        coarse_x = [float(item["x_m"]) for item in coarse_stations]
        coarse_m = [float(item["moment_knm"]["value"]) for item in coarse_stations]
        fine_values = [float(item["moment_knm"]["value"]) for item in fine_stations]
        scale = max((abs(value) for value in fine_values), default=0.0)
        maximum = -1.0
        worst_x = 0.0
        for station in fine_stations:
            x_m = float(station["x_m"])
            fine_moment = float(station["moment_knm"]["value"])
            if x_m < coarse_x[0] - 1.0e-9 or x_m > coarse_x[-1] + 1.0e-9:
                raise ValueError("The fine station grid extends beyond the coarse station grid.")
            upper = min(bisect_right(coarse_x, x_m), len(coarse_x) - 1)
            lower_index = max(0, upper - 1)
            x0, x1 = coarse_x[lower_index], coarse_x[upper]
            y0, y1 = coarse_m[lower_index], coarse_m[upper]
            interpolated = y0 if abs(x1 - x0) <= 1.0e-12 else (
                y0 + (x_m - x0) * (y1 - y0) / (x1 - x0)
            )
            change = abs(interpolated - fine_moment) / max(scale, 1.0e-9)
            if change > maximum:
                maximum, worst_x = change, x_m
        girder_changes.append({
            "girder_index": fine_girder["girder_index"],
            "maximum_normalized_change": max(maximum, 0.0),
            "x_m": worst_x,
            "coarse_station_count": len(coarse_stations),
            "fine_station_count": len(fine_stations),
        })
    worst = max(girder_changes, key=lambda item: item["maximum_normalized_change"])
    return {
        "normalization": "per-girder peak fine-grid absolute moment envelope",
        "interpolation": "piecewise linear coarse envelope evaluated at every fine station",
        "maximum_normalized_change": worst["maximum_normalized_change"],
        "girder_index": worst["girder_index"],
        "x_m": worst["x_m"],
        "per_girder": girder_changes,
    }


def capture(
    path: Path,
    *,
    hb_longitudinal_step_m: float,
    hb_transverse_step_m: float,
    ha_kel_step_m: float,
) -> None:
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
        "hb_longitudinal_step_m": hb_longitudinal_step_m,
        "hb_transverse_step_m": hb_transverse_step_m,
        "ha_kel_step_m": ha_kel_step_m,
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


def compare(coarse_path: Path, fine_path: Path, tolerance: float) -> dict:
    coarse_record = read(coarse_path)
    coarse = coarse_record.get("ha_hb", coarse_record)
    fine = read(fine_path)
    components = {}
    for quantity in ("moment_knm", "shear_kn", "torsion_knm", "deflection_mm"):
        changes = [
            abs(before[quantity]["value"] - after[quantity]["value"])
            / max(abs(after[quantity]["value"]), 1e-9)
            for before, after in zip(coarse["girders"], fine["girders"], strict=True)
        ]
        worst = max(range(len(changes)), key=changes.__getitem__)
        components[quantity] = {
            "maximum_relative_change": changes[worst],
            "girder_index": worst + 1,
            "per_girder_relative_change": changes,
        }
    maximum = max(item["maximum_relative_change"] for item in components.values())
    coarse_exhaustive = bool(
        coarse["kel_exhaustive"] and coarse["assignment_exhaustive"]
    )
    fine_exhaustive = bool(fine["kel_exhaustive"] and fine["assignment_exhaustive"])
    project = GuiProjectState().build_project()
    coarse_kel_step = float(coarse["settings"]["ha_kel_step_m"])
    fine_kel_step = float(fine["settings"]["ha_kel_step_m"])
    kel_grid_nested = set(_kel_positions(
        float(project.geometry.span_m), coarse_kel_step,
    )) <= set(_kel_positions(float(project.geometry.span_m), fine_kel_step))
    step_names = (
        "ha_kel_step_m", "hb_longitudinal_step_m", "hb_transverse_step_m",
    )
    matched_halving = all(
        math.isclose(
            float(coarse["settings"][name]), 2.0 * float(fine["settings"][name]),
            rel_tol=0.0, abs_tol=1.0e-12,
        )
        for name in step_names
    ) and float(coarse["settings"]["units"]) == float(fine["settings"]["units"])
    exhaustive = coarse_exhaustive and fine_exhaustive
    station_shape = compare_station_shapes(coarse, fine)
    return {
        "coarse_snapshot_sha256": sha256(coarse_path),
        "fine_snapshot_sha256": sha256(fine_path),
        "coarse_settings": coarse["settings"],
        "fine_settings": fine["settings"],
        "coarse_placements": coarse["evaluated_case_count"],
        "fine_placements": fine["evaluated_case_count"],
        "fine_elapsed_s": fine["elapsed_s"],
        "exhaustive_lane_and_kel_search": exhaustive,
        "matched_halving": matched_halving,
        "ha_kel_grid_nested": kel_grid_nested,
        "component_changes": components,
        "maximum_relative_change": maximum,
        "station_shape": station_shape,
        "station_shape_criterion_met": (
            station_shape["maximum_normalized_change"] <= tolerance
        ),
        "relative_tolerance": tolerance,
        "girder_envelope_criterion_met": (
            exhaustive and matched_halving and kel_grid_nested
            and maximum <= tolerance
        ),
        "grid_criterion_met": (
            exhaustive and matched_halving and kel_grid_nested
            and maximum <= tolerance
            and station_shape["maximum_normalized_change"] <= tolerance
        ),
        "limitations": [
            "Two-grid girder response sensitivity is not an independent proof of global convergence.",
            "Station-shape checks linearly interpolate the coarse envelope between stations.",
            "All-cases retention is not checked in this audit.",
            "Design validity also requires project actions, code scope, details and independent review.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-default", action="store_true")
    parser.add_argument("--run-half", action="store_true")
    parser.add_argument("--run", action="store_true",
                        help="run the finer 0.5 m / 0.25 m / 0.5 m grid")
    parser.add_argument("--default", type=Path, default=Path(
        "docs/benchmarks/bs_traffic_anchored_default_grid_2026-10-03.json.gz"))
    parser.add_argument("--half", type=Path, default=Path(
        "docs/benchmarks/bs_traffic_anchored_halved_grid_2026-10-03.json.gz"))
    parser.add_argument("--fine", type=Path, default=Path(
        "docs/benchmarks/bs_traffic_anchored_second_refinement_2026-10-03.json.gz"))
    parser.add_argument("--output", type=Path, default=Path(
        "docs/benchmarks/bs_traffic_grid_refinement_2026-10-03.json"))
    parser.add_argument("--tolerance", type=float, default=0.05)
    args = parser.parse_args()
    if args.run_default:
        capture(args.default, hb_longitudinal_step_m=2.0,
                hb_transverse_step_m=1.0, ha_kel_step_m=2.0)
    if args.run_half:
        capture(args.half, hb_longitudinal_step_m=1.0,
                hb_transverse_step_m=0.5, ha_kel_step_m=1.0)
    if args.run:
        capture(args.fine, hb_longitudinal_step_m=0.5,
                hb_transverse_step_m=0.25, ha_kel_step_m=0.5)
    if any((args.run_default, args.run_half, args.run)) and not all(
        path.exists() for path in (args.default, args.half, args.fine)
    ):
        return
    default_to_half = compare(args.default, args.half, args.tolerance)
    half_to_fine = compare(args.half, args.fine, args.tolerance)
    audit = {
        "project": "GUI default 15 m seven-girder rectangular bridge, BS 5400 / BD 37, 45 HB units",
        "relative_tolerance": args.tolerance,
        "default_grid_criterion_met": default_to_half["grid_criterion_met"],
        "second_refinement_criterion_met": half_to_fine["grid_criterion_met"],
        "comparisons": {
            "default_to_half": default_to_half,
            "half_to_fine": half_to_fine,
        },
        "limitations": [
            "Two-grid girder response sensitivity is not an independent proof of global convergence.",
            "Station-shape checks linearly interpolate the coarse envelope between stations.",
            "All-cases retention is not checked in this audit.",
            "Design validity also requires project actions, code scope, details and independent review.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(
        "Default to half: "
        f"{default_to_half['maximum_relative_change']:.3%}; "
        f"station shape={default_to_half['station_shape']['maximum_normalized_change']:.3%}; "
        f"criterion={default_to_half['grid_criterion_met']}"
    )
    print(
        "Half to fine: "
        f"{half_to_fine['maximum_relative_change']:.3%}; "
        f"station shape={half_to_fine['station_shape']['maximum_normalized_change']:.3%}; "
        f"criterion={half_to_fine['grid_criterion_met']}"
    )


if __name__ == "__main__":
    main()
