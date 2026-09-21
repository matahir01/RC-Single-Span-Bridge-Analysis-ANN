from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "full_bridge_staad_bundle"


def _index() -> dict[str, object]:
    return json.loads((BUNDLE / "bundle_index.json").read_text(encoding="utf-8"))


def test_committed_full_bridge_snapshot_inventory_and_status() -> None:
    index = _index()

    assert index["project_name"] == "15 m single-span RC girder reference"
    assert index["span_m"] == 15.0
    assert index["deck_width_m"] == 11.0
    assert index["girder_count"] == 7
    assert index["girder_spacing_m"] == 1.7
    assert index["elastic_modulus_mpa"] == 31_000.0
    assert index["full_width_stage_model_count"] == 3
    assert index["permanent_component_model_count"] == 4
    assert index["governing_traffic_model_count"] == 60
    assert index["combination_rule_count"] == 22
    assert index["combination_instance_count"] == 324
    assert index["internal_status"] == "passed"
    assert index["external_verification_status"] == "pending"

    traffic = index["traffic_search"]
    assert traffic["lm1"]["evaluated_case_count"] == 1024
    assert traffic["lm1"]["retained_governing_case_count"] == 18
    assert traffic["lm1"]["tandem_combinations_exhaustive"]
    assert traffic["ha"]["evaluated_case_count"] == 612
    assert traffic["ha"]["retained_governing_case_count"] == 14
    assert traffic["ha"]["kel_combinations_exhaustive"]
    assert traffic["hb"]["evaluated_case_count"] == 1845
    assert traffic["hb"]["retained_governing_case_count"] == 13
    assert traffic["ha_hb"]["evaluated_case_count"] == 9672
    assert traffic["ha_hb"]["retained_governing_case_count"] == 15
    assert traffic["ha_hb"]["ha_assignment_search_exhaustive"]
    assert traffic["ha_hb"]["kel_combinations_exhaustive"]

    stage_models = {item["model_label"]: item for item in index["stage_models"]}
    final = stage_models["final_composite"]
    assert final["longitudinal_member_count"] == 56
    assert final["transverse_member_count"] == 72
    assert final["transverse_system_active"]

    std_files = sorted(BUNDLE.rglob("*.std"))
    manifests = sorted(BUNDLE.rglob("*_manifest.json"))
    assert len(std_files) == 67
    assert len(manifests) == 67

    required_commands = (
        "STAAD SPACE",
        "JOINT COORDINATES",
        "MEMBER INCIDENCES",
        "MEMBER PROPERTY",
        "CONSTANTS",
        "SUPPORTS",
        "PERFORM ANALYSIS",
    )
    for path in std_files:
        text = path.read_text(encoding="utf-8")
        assert all(command in text for command in required_commands), path
        assert any(line.startswith("LOAD ") for line in text.splitlines()), path


def test_committed_full_bridge_archive_is_complete_and_checksum_matches() -> None:
    archive = BUNDLE / "full-seven-girder-staad-bundle.zip"
    checksum = BUNDLE / "full-seven-girder-staad-bundle.zip.sha256"

    expected_digest = checksum.read_text(encoding="utf-8").split()[0]
    actual_digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    assert actual_digest == expected_digest

    with zipfile.ZipFile(archive) as bundle_zip:
        names = [name for name in bundle_zip.namelist() if not name.endswith("/")]

    assert len(names) == 274
    assert sum(name.endswith(".std") for name in names) == 67
    assert sum(name.endswith("_manifest.json") for name in names) == 67
    assert sum(name.endswith("_expected_results.csv") for name in names) == 67
    assert sum(name.endswith("_external_results_template.csv") for name in names) == 67
    assert "bundle_index.json" in names
    assert "combination_application_matrix.json" in names
