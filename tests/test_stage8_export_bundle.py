import json

import pytest

from rc_single_span.core.models import (
    BridgeProject,
    MaterialProperties,
    RectangularGirderProfile,
    SingleSpanBridgeGeometry,
)
from rc_single_span.verification.export_bundle import (
    write_construction_verification_bundle,
)


def _project(*, elastic_modulus_mpa: float | None = 30000.0) -> BridgeProject:
    return BridgeProject(
        name="Bundle writer benchmark",
        geometry=SingleSpanBridgeGeometry(
            span_m=10.0,
            deck_width_m=5.0,
            carriageway_width_m=4.0,
            girder_count=2,
            girder_spacing_m=3.0,
            girder_profile=RectangularGirderProfile(
                width_m=0.40,
                depth_m=0.90,
            ),
        ),
        materials=MaterialProperties(
            fck_mpa=25.0,
            fcu_mpa=30.0,
            fyk_mpa=410.0,
            concrete_density_kn_m3=24.0,
            elastic_modulus_mpa=elastic_modulus_mpa,
        ),
    )


def test_construction_bundle_writes_all_stage_packages_and_index(tmp_path) -> None:
    result = write_construction_verification_bundle(
        _project(),
        tmp_path / "bundle",
        elastic_modulus_basis="explicit verification benchmark value",
        repository_sha="abc123",
        longitudinal_divisions=6,
    )

    index = json.loads(result.index_path.read_text(encoding="utf-8"))
    assert result.suite.passes_internal_crosscheck
    assert index["project_name"] == "Bundle writer benchmark"
    assert index["stage_model_count"] == 6
    assert index["elastic_modulus_mpa"] == 30000.0
    assert index["elastic_modulus_basis"] == "explicit verification benchmark value"
    assert index["repository_sha"] == "abc123"
    assert index["external_verification_status"] == "pending"
    assert index["internal_crosscheck_passed"] is True
    assert len(index["stage_models"]) == 6

    std_files = list(result.output_directory.rglob("*.std"))
    expected_files = list(result.output_directory.rglob("*_expected_results.csv"))
    return_templates = list(
        result.output_directory.rglob("*_external_results_template.csv")
    )
    manifests = list(result.output_directory.rglob("*_manifest.json"))
    assert len(std_files) == 6
    assert len(expected_files) == 6
    assert len(return_templates) == 6
    assert len(manifests) == 6
    assert result.internal_crosscheck_path.exists()
    assert "maximum moment" in result.internal_crosscheck_path.read_text(
        encoding="utf-8"
    )


def test_construction_bundle_refuses_missing_or_unexplained_elastic_modulus(
    tmp_path,
) -> None:
    with pytest.raises(ValueError, match="elastic_modulus_mpa"):
        write_construction_verification_bundle(
            _project(elastic_modulus_mpa=None),
            tmp_path / "missing-e",
            elastic_modulus_basis="project basis",
        )

    with pytest.raises(ValueError, match="elastic_modulus_basis"):
        write_construction_verification_bundle(
            _project(),
            tmp_path / "missing-basis",
            elastic_modulus_basis="   ",
        )
