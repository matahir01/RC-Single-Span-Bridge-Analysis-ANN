import pytest

from rc_single_span.codes.eurocode.combinations import EurocodeServiceabilityFactors
from rc_single_span.gui import engine_adapter
from rc_single_span.gui.engine_adapter import GuiAnalysisSettings, GuiCodeProfile
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
