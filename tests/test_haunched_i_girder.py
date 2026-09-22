import importlib.util
from pathlib import Path

import pytest

from rc_single_span.analysis.permanent import permanent_load_summary_by_stage
from rc_single_span.analysis.sections import (
    final_composite_concrete_layers,
    precast_girder_properties,
)
from rc_single_span.core.models import (
    IGirderProfile,
    RectangularGirderProfile,
    PermanentActionStage,
    SectionType,
    SingleSpanBridgeGeometry,
    TGirderProfile,
)


def _haunched_profile() -> IGirderProfile:
    return IGirderProfile(
        top_flange_width_m=0.40,
        top_flange_thickness_m=0.15,
        top_haunch_depth_m=0.15,
        web_width_m=0.25,
        web_depth_m=0.50,
        bottom_haunch_depth_m=0.20,
        bottom_flange_width_m=0.40,
        bottom_flange_thickness_m=0.20,
    )


def _geometry() -> SingleSpanBridgeGeometry:
    return SingleSpanBridgeGeometry(
        span_m=20.0,
        physical_girder_length_m=20.0,
        deck_width_m=11.0,
        carriageway_width_m=7.0,
        girder_count=7,
        girder_spacing_m=1.70,
        girder_profile=_haunched_profile(),
    )


def _load_20m_reference():
    path = Path(__file__).parents[1] / "examples" / "reference_bridge_20m_i.py"
    spec = importlib.util.spec_from_file_location("reference_bridge_20m_i", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.reference_bridge_20m_i()


def test_rectangular_t_and_i_section_options_remain_available() -> None:
    rectangular = RectangularGirderProfile(width_m=0.40, depth_m=0.95)
    tee = TGirderProfile(
        flange_width_m=1.20,
        flange_thickness_m=0.20,
        web_width_m=0.30,
        total_depth_m=1.00,
    )
    i_section = _haunched_profile()

    assert rectangular.section_type is SectionType.RECTANGULAR
    assert tee.section_type is SectionType.T
    assert i_section.section_type is SectionType.I


def test_plain_i_section_remains_backward_compatible_when_haunches_are_zero() -> None:
    profile = IGirderProfile(
        top_flange_width_m=0.40,
        top_flange_thickness_m=0.15,
        web_width_m=0.25,
        web_depth_m=0.85,
        bottom_flange_width_m=0.40,
        bottom_flange_thickness_m=0.20,
    )
    assert profile.top_haunch_depth_m == pytest.approx(0.0)
    assert profile.bottom_haunch_depth_m == pytest.approx(0.0)
    assert profile.total_depth_m == pytest.approx(1.20)
    assert profile.area_m2 == pytest.approx(0.3525)


def test_haunched_i_section_has_exact_physical_area_depth_centroid_and_inertia() -> None:
    profile = _haunched_profile()
    properties = precast_girder_properties(_geometry())

    assert profile.total_depth_m == pytest.approx(1.20)
    assert profile.area_m2 == pytest.approx(0.37875)
    assert properties.area_m2 == pytest.approx(0.37875)
    assert properties.centroid_from_top_m == pytest.approx(0.6097359735973598)
    assert properties.iy_m4 == pytest.approx(0.05332191109735975)
    assert properties.iz_m4 == pytest.approx(0.003572265625)


def test_final_composite_section_retains_physical_haunch_bands() -> None:
    layers = final_composite_concrete_layers(_geometry(), girder_index=4)
    labels = [layer.label for layer in layers]

    assert "precast I-girder top haunch" in labels
    assert "precast I-girder bottom haunch" in labels

    top_haunch = next(
        layer for layer in layers if layer.label == "precast I-girder top haunch"
    )
    bottom_haunch = next(
        layer for layer in layers if layer.label == "precast I-girder bottom haunch"
    )
    assert top_haunch.top_width_m == pytest.approx(0.40)
    assert top_haunch.effective_bottom_width_m == pytest.approx(0.25)
    assert bottom_haunch.top_width_m == pytest.approx(0.25)
    assert bottom_haunch.effective_bottom_width_m == pytest.approx(0.40)


def test_20m_i_reference_is_a_geometry_and_loading_benchmark_not_a_bar_target() -> None:
    bridge = _load_20m_reference()
    assert bridge.geometry.span_m == pytest.approx(20.0)
    assert bridge.geometry.girder_count == 7
    assert bridge.geometry.girder_spacing_m == pytest.approx(1.70)
    assert bridge.geometry.girder_profile.section_type is SectionType.I
    assert bridge.provided_longitudinal_reinforcement is None
    assert len(bridge.permanent_actions.surfacing_layers) == 3
    assert len(bridge.permanent_actions.line_actions) == 6


def test_20m_benchmark_permanent_actions_are_fully_staged_and_auditable() -> None:
    bridge = _load_20m_reference()
    summaries = permanent_load_summary_by_stage(bridge)
    by_stage = {item.stage: item for item in summaries}

    # Stage 1: seven girder self-weights + 75 mm false slab over 11 m deck.
    assert by_stage[PermanentActionStage.PRECAST_GIRDER].total_kn == pytest.approx(
        1738.125
    )

    # Stage 2: 175 mm wet deck + three 250x900 nominal diaphragms.
    assert by_stage[PermanentActionStage.DECK_CONSTRUCTION].total_kn == pytest.approx(
        1134.625
    )
    assert by_stage[PermanentActionStage.DECK_CONSTRUCTION].point_total_kn == pytest.approx(
        172.125
    )

    # Stage 3: asphalt, footway toppings, kerbs, barriers and services.
    assert by_stage[PermanentActionStage.SUPERIMPOSED].total_kn == pytest.approx(
        987.6
    )

    total = sum(item.total_kn for item in summaries)
    assert total == pytest.approx(3860.35)
