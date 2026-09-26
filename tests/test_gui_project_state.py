import pytest

from rc_single_span.core.models import IGirderProfile, RectangularGirderProfile, TGirderProfile
from rc_single_span.gui.project_state import GuiProjectState


def test_default_gui_state_builds_thesis_bridge_geometry() -> None:
    project = GuiProjectState().build_project()
    assert project.geometry.span_m == pytest.approx(15.0)
    assert project.geometry.deck_width_m == pytest.approx(11.0)
    assert project.geometry.carriageway_width_m == pytest.approx(7.0)
    assert project.geometry.girder_count == 7
    assert project.geometry.girder_spacing_m == pytest.approx(1.70)
    assert isinstance(project.geometry.girder_profile, RectangularGirderProfile)
    assert project.geometry.deck.physical_depth_m == pytest.approx(0.25)
    assert project.materials.fck_mpa == pytest.approx(35.0)
    assert project.materials.fcu_mpa == pytest.approx(45.0)
    assert project.materials.fyk_mpa == pytest.approx(500.0)
    assert project.provided_longitudinal_reinforcement is not None
    assert project.provided_longitudinal_reinforcement.total_area_mm2 == pytest.approx(
        16 * 3.141592653589793 * 32.0**2 / 4.0
    )


def test_gui_state_supports_t_and_i_section_builders() -> None:
    t_project = GuiProjectState(section_type="t").build_project()
    i_project = GuiProjectState(section_type="i").build_project()
    assert isinstance(t_project.geometry.girder_profile, TGirderProfile)
    assert isinstance(i_project.geometry.girder_profile, IGirderProfile)


def test_gui_state_json_payload_round_trip() -> None:
    state = GuiProjectState(name="Round trip", barrier_kn_m=12.5)
    recovered = GuiProjectState.from_dict(state.as_dict())
    assert recovered == state
    assert recovered.build_project().name == "Round trip"


def test_gui_state_rejects_unknown_serialized_fields() -> None:
    payload = GuiProjectState().as_dict()
    payload["hidden_magic"] = 1
    with pytest.raises(ValueError, match="Unknown GUI project fields"):
        GuiProjectState.from_dict(payload)
