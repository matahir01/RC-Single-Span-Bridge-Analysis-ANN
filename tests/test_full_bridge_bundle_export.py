import csv
import json

import pytest

from rc_single_span.codes.eurocode.combinations import (
    EurocodeServiceabilityFactors,
)
from rc_single_span.core.models import (
    BridgeProject,
    MaterialProperties,
    PermanentActionModel,
    PermanentLineAction,
    RectangularGirderProfile,
    SingleSpanBridgeGeometry,
    SurfacingLayer,
)
from rc_single_span.verification.full_bridge_campaign import (
    FullBridgeTrafficSearchConfig,
)
from rc_single_span.verification.full_bridge_export import (
    write_full_bridge_verification_bundle,
)


def _project() -> BridgeProject:
    return BridgeProject(
        name="Full bridge bundle benchmark",
        geometry=SingleSpanBridgeGeometry(
            span_m=15.0,
            physical_girder_length_m=14.95,
            deck_width_m=11.0,
            carriageway_width_m=7.0,
            girder_count=7,
            girder_spacing_m=1.70,
            girder_profile=RectangularGirderProfile(width_m=0.40, depth_m=0.95),
        ),
        materials=MaterialProperties(
            fck_mpa=25.0,
            fcu_mpa=30.0,
            fyk_mpa=410.0,
            concrete_density_kn_m3=24.0,
            elastic_modulus_mpa=31_000.0,
        ),
        permanent_actions=PermanentActionModel(
            surfacing_layers=[
                SurfacingLayer(
                    name="surfacing",
                    thickness_m=0.080,
                    density_kn_m3=22.0,
                    y_start_m=-3.5,
                    y_end_m=3.5,
                    x_end_m=15.0,
                )
            ],
            line_actions=[
                PermanentLineAction(
                    name="left barrier",
                    magnitude_kn_m=10.0,
                    y_m=-5.5,
                    x_end_m=15.0,
                ),
                PermanentLineAction(
                    name="right barrier",
                    magnitude_kn_m=10.0,
                    y_m=5.5,
                    x_end_m=15.0,
                ),
            ],
        ),
    )


def _coarse_config() -> FullBridgeTrafficSearchConfig:
    return FullBridgeTrafficSearchConfig(
        lm1_longitudinal_step_m=7.5,
        lm1_max_exhaustive_tandem_combinations=1000,
        ha_longitudinal_step_m=7.5,
        ha_max_exhaustive_kel_combinations=1000,
        hb_longitudinal_step_m=15.0,
        hb_transverse_step_m=3.5,
        combined_hb_longitudinal_step_m=15.0,
        combined_hb_transverse_step_m=3.5,
        combined_ha_kel_step_m=15.0,
        combined_max_exhaustive_kel_combinations=1000,
        combined_max_exhaustive_ha_assignments=100,
    )


def test_writer_emits_complete_full_width_campaign(tmp_path) -> None:
    output = tmp_path / "full-bridge"
    result = write_full_bridge_verification_bundle(
        _project(),
        output,
        elastic_modulus_basis="explicit benchmark value",
        eurocode_sls_factors=EurocodeServiceabilityFactors(
            psi1_traffic=0.75,
            psi2_traffic=0.0,
        ),
        repository_sha="abc123",
        longitudinal_divisions=6,
        traffic_config=_coarse_config(),
    )
    index = json.loads(result.index_path.read_text(encoding="utf-8"))

    assert index["girder_count"] == 7
    assert index["full_width_stage_model_count"] == 3
    assert index["permanent_component_model_count"] == 4
    assert index["governing_traffic_model_count"] == len(result.traffic_campaign.cases)
    assert index["combination_rule_count"] == 22


    expected_combination_instances = sum(
        len(result.traffic_campaign.cases_for(rule.traffic_action))
        for rule in result.combination_rules
    )
    assert index["combination_instance_count"] == expected_combination_instances
    assert index["repository_sha"] == "abc123"
    assert index["internal_status"] == "passed"
    assert index["external_verification_status"] == "pending"
    assert index["eurocode_sls_factors"] == {
        "psi1_traffic": 0.75,
        "psi1_udl_traffic": None,
        "psi2_traffic": 0.0,
    }

    expected_model_count = (
        index["full_width_stage_model_count"]
        + index["permanent_component_model_count"]
        + index["governing_traffic_model_count"]
    )
    assert len(list(output.rglob("*.std"))) == expected_model_count
    assert len(list(output.rglob("*_manifest.json"))) == expected_model_count
    assert len(list(output.rglob("*_expected_results.csv"))) == expected_model_count
    assert len(list(output.rglob("*_external_results_template.csv"))) == expected_model_count

    final_std = output / "stages/final_composite/full_bridge_final_composite.std"
    assert final_std.is_file()
    text = final_std.read_text(encoding="utf-8")
    assert "STAAD SPACE" in text
    assert "MEMBER INCIDENCES" in text
    assert "PERFORM ANALYSIS" in text

    with (output / "combination_envelopes.csv").open(encoding="utf-8", newline="") as stream:
        envelope_rows = list(csv.DictReader(stream))
    assert len(envelope_rows) == 154
    assert {row["standard"] for row in envelope_rows} == {
        "Eurocode",
        "BS 5400",
    }

    matrix = json.loads(
        (output / "combination_application_matrix.json").read_text(encoding="utf-8")
    )
    assert matrix["combination_instance_count"] == expected_combination_instances
    assert len(matrix["instances"]) == expected_combination_instances
    assert all(len(item["terms"]) == 5 for item in matrix["instances"])
    assert "load-time stiffness" in matrix["application_note"]
    assert len(result.written_files) > expected_model_count * 4



def test_writer_exports_weighted_frequent_lm1_cases_and_source_ids(tmp_path) -> None:
    output = tmp_path / "weighted-frequent"
    result = write_full_bridge_verification_bundle(
        _project(), output,
        elastic_modulus_basis="explicit benchmark value",
        eurocode_sls_factors=EurocodeServiceabilityFactors(
            psi1_traffic=0.75, psi2_traffic=0.0, psi1_udl_traffic=0.4,
        ),
        longitudinal_divisions=6,
        traffic_config=_coarse_config(),
    )
    index = json.loads(result.index_path.read_text(encoding="utf-8"))
    weighted = index["traffic_search"]["lm1_frequent"]
    assert weighted["retained_governing_case_count"] > 0
    assert weighted["tandem_factor"] == 0.75
    assert weighted["udl_factor"] == 0.4
    matrix = json.loads((output / "combination_application_matrix.json").read_text())
    frequent = [row for row in matrix["instances"]
                if row["rule_id"] == "ec_sls_frequent"]
    assert len(frequent) == weighted["retained_governing_case_count"]
    assert all(row["traffic_action"] == "lm1_frequent" for row in frequent)
    assert all(any(term["source_kind"] == "traffic_case"
                   and term["source_key"].startswith("lm1_frequent_")
                   and term["factor"] == 1.0 for term in row["terms"])
               for row in frequent)

def test_writer_refuses_nonempty_output_directory(tmp_path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    (output / "stale.txt").write_text("stale", encoding="utf-8")

    with pytest.raises(FileExistsError, match="stale"):
        write_full_bridge_verification_bundle(
            _project(),
            output,
            elastic_modulus_basis="explicit benchmark value",
            eurocode_sls_factors=EurocodeServiceabilityFactors(
                psi1_traffic=0.75,
                psi2_traffic=0.0,
            ),
            traffic_config=_coarse_config(),
        )
