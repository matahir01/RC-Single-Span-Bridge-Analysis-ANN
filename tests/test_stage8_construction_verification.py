import json

import pytest

from rc_single_span.core.models import (
    BridgeProject,
    DeckConstruction,
    MaterialProperties,
    PermanentActionModel,
    PermanentActionStage,
    PermanentLineAction,
    RectangularGirderProfile,
    SingleSpanBridgeGeometry,
    SurfacingLayer,
)
from rc_single_span.verification.construction import (
    build_construction_verification_suite,
)


def _project() -> BridgeProject:
    return BridgeProject(
        name="Construction verification benchmark",
        geometry=SingleSpanBridgeGeometry(
            span_m=12.0,
            deck_width_m=7.0,
            carriageway_width_m=6.0,
            girder_count=3,
            girder_spacing_m=2.5,
            girder_profile=RectangularGirderProfile(
                width_m=0.40,
                depth_m=0.95,
            ),
            deck=DeckConstruction(
                precast_false_slab_depth_m=0.075,
                in_situ_slab_depth_m=0.175,
                false_slab_composite_participation=False,
                in_situ_slab_composite_participation=True,
            ),
        ),
        materials=MaterialProperties(
            fck_mpa=25.0,
            fcu_mpa=30.0,
            fyk_mpa=410.0,
            concrete_density_kn_m3=24.0,
            elastic_modulus_mpa=30000.0,
        ),
        permanent_actions=PermanentActionModel(
            surfacing_layers=[
                SurfacingLayer(
                    name="asphalt",
                    thickness_m=0.05,
                    density_kn_m3=23.0,
                    y_start_m=-3.0,
                    y_end_m=3.0,
                    x_start_m=1.0,
                    x_end_m=11.0,
                )
            ],
            line_actions=[
                PermanentLineAction(
                    name="left barrier",
                    magnitude_kn_m=8.0,
                    y_m=-2.5,
                    x_start_m=0.5,
                    x_end_m=12.0,
                )
            ],
        ),
    )


def test_construction_suite_crosschecks_all_three_stages_and_cumulative_response() -> None:
    suite = build_construction_verification_suite(
        _project(),
        longitudinal_divisions=8,
    )

    assert len(suite.stages) == 9
    assert len(suite.cumulative) == 3
    failed = [
        (
            comparison.label,
            comparison.internal_value,
            comparison.reference_value,
            comparison.relative_difference,
            comparison.absolute_difference,
        )
        for item in (*suite.stages, *suite.cumulative)
        for comparison in item.comparisons
        if not comparison.passes
    ]
    assert suite.passes_internal_crosscheck, failed
    assert all(item.passes_internal_crosscheck for item in suite.stages)
    assert all(item.passes_internal_crosscheck for item in suite.cumulative)

    for item in suite.stages:
        assert len(item.comparisons) == 5
        scale = max(
            abs(item.analysis.total_applied_vertical_load_kn),
            abs(item.analysis.total_vertical_reaction_kn),
            1.0,
        )
        assert abs(item.analysis.vertical_equilibrium_residual_kn) <= max(
            1.0e-5,
            1.0e-5 * scale,
        )


def test_stage_loads_and_stiffness_preserve_the_actual_construction_sequence() -> None:
    suite = build_construction_verification_suite(
        _project(),
        longitudinal_divisions=8,
    )
    precast = suite.stage(
        girder_index=2,
        stage=PermanentActionStage.PRECAST_GIRDER,
    )
    wet = suite.stage(
        girder_index=2,
        stage=PermanentActionStage.DECK_CONSTRUCTION,
    )
    final = suite.stage(
        girder_index=2,
        stage=PermanentActionStage.SUPERIMPOSED,
    )

    assert {item.source for item in precast.reference.loads} == {
        "precast girder self-weight",
        "precast false-slab self-weight",
    }
    assert {item.source for item in wet.reference.loads} == {
        "wet in-situ deck self-weight"
    }
    assert "asphalt" in {item.source for item in final.reference.loads}

    assert wet.reference.section.iy_m4 == pytest.approx(
        precast.reference.section.iy_m4
    )
    assert final.reference.section.iy_m4 > wet.reference.section.iy_m4


def test_each_stage_staad_package_uses_exact_stage_section_and_load_case() -> None:
    suite = build_construction_verification_suite(
        _project(),
        longitudinal_divisions=8,
    )
    item = suite.stage(
        girder_index=1,
        stage=PermanentActionStage.DECK_CONSTRUCTION,
    )
    package = item.staad_package
    manifest = json.loads(package.manifest_json)

    assert manifest["load_case_id"] == item.analysis.load_case_id
    assert manifest["provenance"]["girder_index"] == "1"
    assert manifest["provenance"]["stage"] == "deck_construction"
    assert manifest["provenance"]["section_basis"] == item.reference.section.basis
    assert "STAAD SPACE" in package.staad_std
    assert "MEMBER LOAD" in package.staad_std
    assert "UNI GZ" in package.staad_std
    assert f"IY {item.reference.section.iy_m4:.12g}" in package.staad_std


def test_superimposed_partial_actions_are_split_without_losing_total_load() -> None:
    suite = build_construction_verification_suite(
        _project(),
        longitudinal_divisions=8,
    )
    exterior = suite.stage(
        girder_index=1,
        stage=PermanentActionStage.SUPERIMPOSED,
    )

    expected_downward = sum(load.total_load_kn for load in exterior.reference.loads)
    assert -exterior.analysis.total_applied_vertical_load_kn == pytest.approx(
        expected_downward
    )
    assert exterior.analysis.total_vertical_reaction_kn == pytest.approx(
        expected_downward
    )
