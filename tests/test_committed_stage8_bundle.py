import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
BUNDLE = ROOT / "stage8_staad_bundle"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_committed_stage8_bundle_is_complete_and_traceable() -> None:
    index = json.loads((BUNDLE / "bundle_index.json").read_text(encoding="utf-8"))
    models = index["stage_models"]

    assert index["stage_model_count"] == 21
    assert len(models) == 21
    assert index["girder_count"] == 7
    assert index["elastic_modulus_mpa"] == pytest.approx(31_000.0)
    assert index["repository_sha"] == "28a4f7e3d6af3dd6108b355a642df8f6a8f48dc5"
    assert index["internal_crosscheck_passed"] is True
    assert index["external_verification_status"] == "pending"
    assert Counter(item["stage"] for item in models) == {
        "precast_girder": 7,
        "deck_construction": 7,
        "superimposed": 7,
    }

    for item in models:
        assert item["internal_crosscheck_passed"] is True
        assert len(item["files"]) == 4
        paths = [BUNDLE / value for value in item["files"]]
        assert all(path.is_file() for path in paths)

        std_path = next(path for path in paths if path.suffix == ".std")
        manifest_path = next(
            path for path in paths if path.name.endswith("_manifest.json")
        )
        expected_path = next(
            path for path in paths if path.name.endswith("_expected_results.csv")
        )
        template_path = next(
            path
            for path in paths
            if path.name.endswith("_external_results_template.csv")
        )
        std = std_path.read_text(encoding="utf-8")
        assert "MEMBER LOAD" in std
        assert " PRIS AX " in std
        assert " IX " in std and " IY " in std and " IZ " in std
        assert "PERFORM ANALYSIS" in std
        assert std.endswith("FINISH\n")
        assert re.search(
            r"(?<![A-Za-z])(?:nan|[+-]?inf)(?![A-Za-z])", std, flags=re.IGNORECASE
        ) is None

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["files"]["staad_std"]["sha256"] == _sha256(std_path)
        assert manifest["files"]["expected_results_csv"]["sha256"] == _sha256(
            expected_path
        )
        assert manifest["files"]["external_results_template_csv"][
            "sha256"
        ] == _sha256(template_path)


def test_committed_stage8_internal_crosscheck_is_all_pass() -> None:
    with (BUNDLE / "internal_crosscheck.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        rows = list(csv.DictReader(stream))

    assert rows
    assert {row["status"] for row in rows} == {"pass"}
    assert {row["stage"] for row in rows if row["scope"] == "stage"} == {
        "precast_girder",
        "deck_construction",
        "superimposed",
    }
