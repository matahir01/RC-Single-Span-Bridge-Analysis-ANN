from pathlib import Path
from runpy import run_path


def test_default_reference_bs_grid_does_not_pass_halved_grid_check() -> None:
    repository = Path(__file__).resolve().parents[1]
    compare = run_path(str(repository / "examples" / "audit_bs_reference_grid.py"))["compare"]
    root = repository / "docs" / "benchmarks"
    audit = compare(
        root / "bs_traffic_fine_optimized_2026-10-01.json.gz",
        root / "bs_traffic_halved_grid_2026-10-01.json.gz",
        0.05,
    )
    assert not audit["default_grid_criterion_met"]
    assert audit["searches"]["ha"]["girder_envelope_criterion_met"]
    assert audit["searches"]["hb"]["girder_envelope_criterion_met"]
    combined = audit["searches"]["ha_hb"]
    assert combined["fine_search_exhaustive"]
    torsion = combined["component_changes"]["torsion_knm"]
    assert torsion["girder_index"] == 5
    assert 0.07 < torsion["maximum_relative_change"] < 0.08


def test_station_shape_audit_interpolates_coarse_envelope_at_fine_stations() -> None:
    repository = Path(__file__).resolve().parents[1]
    audit_module = run_path(
        str(repository / "examples" / "audit_bs_combined_second_refinement.py")
    )
    compare_shapes = audit_module["compare_station_shapes"]

    def girder(stations: tuple[tuple[float, float], ...]) -> dict:
        return {
            "girder_index": 1,
            "stations": [
                {"x_m": x_m, "moment_knm": {"value": moment}}
                for x_m, moment in stations
            ],
        }

    coarse = {"station_moments": [girder(((0.0, 0.0), (7.5, 100.0), (15.0, 0.0)))]}
    fine = {"station_moments": [girder((
        (0.0, 0.0), (3.75, 50.0), (7.5, 100.0), (11.25, 50.0), (15.0, 0.0),
    ))]}
    changed = {"station_moments": [girder((
        (0.0, 0.0), (3.75, 60.0), (7.5, 100.0), (11.25, 50.0), (15.0, 0.0),
    ))]}

    assert compare_shapes(coarse, fine)["maximum_normalized_change"] == 0.0
    assert compare_shapes(coarse, changed)["maximum_normalized_change"] == 0.1
