import json
from dataclasses import replace

from rc_single_span.analysis.grillage import build_final_composite_grillage
from rc_single_span.analysis.plan_loads import PlanPointLoad, build_plan_load_case
from rc_single_span.analysis.prepared_grillage import (
    prepare_vertical_grillage,
    solve_prepared_vertical_grillage,
)
from rc_single_span.core.models import (
    BridgeProject,
    MaterialProperties,
    RectangularGirderProfile,
    SingleSpanBridgeGeometry,
)
from rc_single_span.verification.package import build_staad_verification_package
from rc_single_span.verification.staad_export import (
    _staad_member_force_print_commands,
    export_staad_std,
    staad_support_restraints,
)


def _project() -> BridgeProject:
    return BridgeProject(
        name="STAAD verification benchmark",
        geometry=SingleSpanBridgeGeometry(
            span_m=15.0,
            deck_width_m=6.0,
            carriageway_width_m=5.0,
            girder_count=3,
            girder_spacing_m=2.0,
            girder_profile=RectangularGirderProfile(
                width_m=0.40,
                depth_m=0.95,
            ),
        ),
        materials=MaterialProperties(
            fck_mpa=25.0,
            fcu_mpa=30.0,
            fyk_mpa=410.0,
            concrete_density_kn_m3=24.0,
            elastic_modulus_mpa=30000.0,
        ),
    )


def _solved():
    build = build_final_composite_grillage(
        _project(),
        stations_m=(0.0, 7.5, 15.0),
    )
    case = build_plan_load_case(
        build.model,
        load_case_id=7,
        name="midspan point verification",
        point_loads=(
            PlanPointLoad(
                x_m=7.5,
                y_m=0.0,
                magnitude_kn=100.0,
                label="100 kN point",
            ),
        ),
    )
    model = replace(build.model, load_cases=(case,))
    prepared = prepare_vertical_grillage(model)
    analysis = solve_prepared_vertical_grillage(prepared, model)
    return model, analysis


def test_staad_export_uses_exact_model_properties_loads_and_analysis_commands() -> None:
    model, _ = _solved()
    text = export_staad_std(model)

    assert "STAAD SPACE" in text
    assert "SET Z UP" in text
    assert "UNIT METER KNS" in text
    assert "MEMBER PROPERTY" in text
    assert "PRIS AX" in text
    assert " IX " in text
    assert " IY " in text
    assert " IZ " in text
    assert "LOAD 7 LOADTYPE None TITLE" in text
    assert "JOINT LOAD" in text
    assert "FZ -100" in text
    assert "PERFORM ANALYSIS" in text
    assert "PRINT SUPPORT REACTION ALL" in text
    assert "PRINT MEMBER FORCES GLOBAL LIST" in text
    assert "PRINT JOINT DISPLACEMENTS ALL" in text


def test_staad_support_stabilization_is_explicit_and_minimal() -> None:
    model, _ = _solved()
    nodes = {node.node_id: node for node in model.nodes}
    restraints = staad_support_restraints(model)

    min_x = min(nodes[item.node_id].x_m for item in model.supports)
    first_line = [
        item
        for item in restraints
        if abs(nodes[item.node_id].x_m - min_x) <= 1.0e-9
    ]
    other_line = [
        item
        for item in restraints
        if abs(nodes[item.node_id].x_m - min_x) > 1.0e-9
    ]

    assert first_line
    assert all(item.ux for item in first_line)
    assert sum(item.uy for item in first_line) == 1
    assert all(not item.ux and not item.uy for item in other_line)
    assert all(item.uz for item in restraints)


def test_staad_verification_package_is_traceable_and_does_not_claim_acceptance() -> None:
    model, analysis = _solved()
    package = build_staad_verification_package(
        model,
        analysis,
        provenance={
            "repository": "RC-Single-Span-Bridge-Analysis-ANN",
            "purpose": "Stage 8 regression",
        },
    )
    files = package.files("reference_case")
    manifest = json.loads(package.manifest_json)

    assert set(files) == {
        "reference_case.std",
        "reference_case_manifest.json",
        "reference_case_expected_results.csv",
        "reference_case_external_results_template.csv",
    }
    assert manifest["load_case_id"] == 7
    assert manifest["equilibrium"]["residual_kn"] == analysis.vertical_equilibrium_residual_kn
    assert manifest["staad_stabilization"]["ux_restrained_nodes"]
    assert manifest["staad_stabilization"]["uy_restrained_nodes"]
    assert manifest["comparison_scope"]["direct_global_components"] == [
        "support FZ reactions",
        "joint vertical DZ displacements",
        "member-end global FZ",
        "member-end global MX",
        "member-end global MY",
    ]
    assert "first" in manifest["comparison_scope"]["first_external_run_note"].lower()
    assert "not independent verification by itself" in manifest["verification_note"]
    assert "direct_global_mapping" in package.expected_results_csv
    assert "PRINT MEMBER FORCES GLOBAL" in package.external_results_template_csv


def test_staad_member_force_print_commands_do_not_drop_four_digit_ids() -> None:
    member_ids = list(range(1009, 1611))
    commands = _staad_member_force_print_commands(member_ids)

    assert commands
    assert all(len(line) <= 100 for line in commands)
    recovered = [
        int(token)
        for line in commands
        for token in line.split()[5:]
    ]
    assert recovered == member_ids
    assert 1032 in recovered
    assert 1608 in recovered
