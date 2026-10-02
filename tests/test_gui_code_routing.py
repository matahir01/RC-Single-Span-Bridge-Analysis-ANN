from dataclasses import replace

import pytest

from rc_single_span.codes.eurocode.combinations import EurocodeServiceabilityFactors
from rc_single_span.gui import engine_adapter
from rc_single_span.gui.engine_adapter import (
    GuiAnalysisSettings,
    GuiCodeProfile,
    run_gui_analysis,
)
from rc_single_span.gui.project_state import GuiProjectState
from rc_single_span.verification.reference_runner import ReferenceRunConfig, run_reference_project


@pytest.mark.parametrize(
    ("profile", "expected"),
    [(GuiCodeProfile.BS_EN, "bs_en"), (GuiCodeProfile.BS_5400, "bs5400")],
)
def test_gui_runs_only_selected_code_route(monkeypatch, profile, expected) -> None:
    class CapturedRoute(Exception):
        pass

    def capture(_project, *, code_route, **_kwargs):
        raise CapturedRoute(code_route)

    monkeypatch.setattr(engine_adapter, "run_reference_project", capture)
    with pytest.raises(CapturedRoute, match=expected):
        engine_adapter.run_gui_analysis(
            GuiProjectState().build_project(), GuiAnalysisSettings(code_profile=profile)
        )


def test_reference_runner_rejects_invalid_or_mixed_route_before_analysis() -> None:
    project = GuiProjectState().build_project()
    config = ReferenceRunConfig(
        elastic_modulus_mpa=34000.0,
        eurocode_sls_factors=EurocodeServiceabilityFactors(
            psi1_traffic=0.75, psi1_udl_traffic=0.40, psi2_traffic=0.0
        ),
    )
    with pytest.raises(ValueError, match="Unsupported code route"):
        run_reference_project(project, config=config, code_route="unknown")


def test_retained_bs_traffic_does_not_change_engine_envelopes_or_trigger_deflection() -> None:
    project = GuiProjectState().build_project()
    coarse = GuiAnalysisSettings(
        code_profile=GuiCodeProfile.BS_5400,
        bs_ha_longitudinal_step_m=7.5,
        bs_hb_longitudinal_step_m=15.0,
        bs_hb_transverse_step_m=3.5,
        bs_combined_hb_longitudinal_step_m=15.0,
        bs_combined_hb_transverse_step_m=3.5,
        bs_combined_ha_kel_step_m=15.0,
    )
    normal, normal_summary = run_gui_analysis(project, coarse)
    retained, retained_summary = run_gui_analysis(
        project, replace(coarse, retain_all_cases=True)
    )
    assert retained.bs_traffic is not None
    assert normal.bs_traffic is not None
    for name in ("ha", "hb", "ha_hb"):
        a, b = getattr(normal.bs_traffic, name), getattr(retained.bs_traffic, name)
        assert a.evaluated_case_count == b.evaluated_case_count
        assert a.girders == b.girders
        assert a.station_moments == b.station_moments
        assert len(b.cases) == b.evaluated_case_count
    assert normal.bs5400_combinations == retained.bs5400_combinations
    assert normal_summary.rows == retained_summary.rows
    assert retained.bs5400_characteristic_deflection == {}
    assert any("was not evaluated" in note for note in retained_summary.notes)
