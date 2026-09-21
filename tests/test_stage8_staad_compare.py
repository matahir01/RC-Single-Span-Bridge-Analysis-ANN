import csv
from dataclasses import replace
from io import StringIO

import pytest

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
from rc_single_span.verification.member_forces import (
    native_global_member_end_forces,
)
from rc_single_span.verification.package import build_staad_verification_package
from rc_single_span.verification.staad_compare import (
    compare_staad_external_results,
)


def _project() -> BridgeProject:
    return BridgeProject(
        name="STAAD global mapping benchmark",
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
        load_case_id=9,
        name="off-centre verification",
        point_loads=(
            PlanPointLoad(
                x_m=7.5,
                y_m=1.0,
                magnitude_kn=100.0,
                label="off-centre 100 kN point",
            ),
        ),
    )
    model = replace(build.model, load_cases=(case,))
    prepared = prepare_vertical_grillage(model)
    analysis = solve_prepared_vertical_grillage(prepared, model)
    return model, analysis


def _external_csv_from_expected(expected_csv: str) -> str:
    source = csv.DictReader(StringIO(expected_csv))
    stream = StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(
        (
            "result_type",
            "object_id",
            "end",
            "component",
            "external_value",
            "unit",
            "source",
            "notes",
        )
    )
    for row in source:
        writer.writerow(
            (
                row["result_type"],
                row["object_id"],
                row["end"],
                row["component"],
                row["value"],
                row["unit"],
                "STAAD regression mirror",
                "",
            )
        )
    return stream.getvalue()


def test_native_member_mapping_matches_solver_transform_for_x_and_y_members() -> None:
    model, analysis = _solved()
    nodes = {node.node_id: node for node in model.nodes}
    native = {item.member_id: item for item in analysis.members}
    global_rows = {
        (item.member_id, item.end): item
        for item in native_global_member_end_forces(model, analysis)
    }

    x_beam = next(
        beam
        for beam in model.beams
        if abs(nodes[beam.node_j].x_m - nodes[beam.node_i].x_m) > 1.0e-9
        and abs(nodes[beam.node_j].y_m - nodes[beam.node_i].y_m) <= 1.0e-9
    )
    y_beam = next(
        beam
        for beam in model.beams
        if abs(nodes[beam.node_j].x_m - nodes[beam.node_i].x_m) <= 1.0e-9
        and abs(nodes[beam.node_j].y_m - nodes[beam.node_i].y_m) > 1.0e-9
    )

    x_native = native[x_beam.member_id]
    x_global = global_rows[(x_beam.member_id, "i")]
    assert x_global.fz_kn == pytest.approx(x_native.i_vertical_force_kn)
    assert x_global.mx_knm == pytest.approx(x_native.i_torsion_knm)
    assert x_global.my_knm == pytest.approx(
        x_native.i_vertical_bending_moment_knm
    )

    y_native = native[y_beam.member_id]
    y_global = global_rows[(y_beam.member_id, "i")]
    assert y_global.fz_kn == pytest.approx(y_native.i_vertical_force_kn)
    assert y_global.mx_knm == pytest.approx(
        -y_native.i_vertical_bending_moment_knm
    )
    assert y_global.my_knm == pytest.approx(y_native.i_torsion_knm)


def test_complete_external_return_can_be_compared_directly_in_global_axes() -> None:
    model, analysis = _solved()
    package = build_staad_verification_package(model, analysis)
    external_csv = _external_csv_from_expected(package.expected_results_csv)

    comparison = compare_staad_external_results(
        model,
        analysis,
        external_csv,
    )
    assert comparison.passes
    assert comparison.comparisons
    assert not comparison.missing_keys
    assert not comparison.unexpected_keys


def test_comparison_fails_when_one_external_result_is_outside_tolerance() -> None:
    model, analysis = _solved()
    package = build_staad_verification_package(model, analysis)
    source = list(csv.DictReader(StringIO(package.expected_results_csv)))

    changed = False
    for row in source:
        value = float(row["value"])
        if abs(value) > 1.0e-6:
            row["value"] = str(value * 1.10)
            changed = True
            break
    assert changed

    stream = StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(
        (
            "result_type",
            "object_id",
            "end",
            "component",
            "external_value",
            "unit",
            "source",
            "notes",
        )
    )
    for row in source:
        writer.writerow(
            (
                row["result_type"],
                row["object_id"],
                row["end"],
                row["component"],
                row["value"],
                row["unit"],
                "STAAD perturbed regression",
                "",
            )
        )

    comparison = compare_staad_external_results(
        model,
        analysis,
        stream.getvalue(),
    )
    assert not comparison.passes
    assert any(not item.passes for item in comparison.comparisons)
