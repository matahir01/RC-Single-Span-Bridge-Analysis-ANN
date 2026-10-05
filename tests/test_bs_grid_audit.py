from pathlib import Path
from runpy import run_path
from types import SimpleNamespace

from rc_single_span.traffic.bs5400 import _update_station_moment_governing


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


def test_station_shape_audit_compares_identical_design_stations_directly() -> None:
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

    coarse = {"station_moments": [girder(((0.0, 0.0), (1.0, 90.0), (2.0, 0.0)))]}
    fine = {"station_moments": [girder(((0.0, 0.0), (1.0, 100.0), (2.0, 0.0)))]}
    result = compare_shapes(coarse, fine, evaluation_stations_m=(0.0, 1.0, 2.0))

    assert result["sampling"].startswith("direct values")
    assert result["maximum_normalized_change"] == 0.1
    assert result["x_m"] == 1.0
    assert result["per_girder"][0]["evaluation_station_count"] == 3


def test_station_moment_envelope_merges_roundoff_equal_coordinates() -> None:
    governing: list[dict[str, object]] = []
    current = ((
        SimpleNamespace(girder_index=1, y_m=0.0, x_m=7.2,
                        moment_knm=300.0, member_id=10),
        SimpleNamespace(girder_index=1, y_m=0.0, x_m=7.199999999999999,
                        moment_knm=310.0, member_id=11),
    ),)

    _update_station_moment_governing(governing, case_id=5, current=current)

    stations = governing[0]["stations"]
    assert len(stations) == 1
    component = next(iter(stations.values()))
    assert component.value == 310.0
    assert component.member_id == 11
