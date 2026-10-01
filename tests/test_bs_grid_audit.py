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
