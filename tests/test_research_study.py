import pytest

from rc_single_span.gui.project_state import GuiProjectState
from rc_single_span.gui.research_workspace import ResearchWorkspace, render_research_report
from rc_single_span.research.study import run_research_study


def test_study_runner_keeps_unconfirmed_inputs_explicitly_exploratory(tmp_path) -> None:
    config = ResearchWorkspace._load_packaged_config()
    destination = tmp_path / "study"

    with pytest.raises(ValueError, match="unconfirmed.*exploratory"):
        run_research_study(
            GuiProjectState().build_project(),
            config,
            destination,
            exploratory=False,
        )

    assert not destination.exists()


def test_research_report_shows_limit_state_equations_and_substitutions() -> None:
    report = render_research_report({
        "status": "EXPLORATORY ONLY",
        "baseline": {
            "project_name": "Test bridge",
            "provenance": "Reference analysis",
            "lm1_step_m": 0.6,
            "permanent_moment_knm": 10.0,
            "traffic_moment_knm": 20.0,
            "permanent_shear_kn": 3.0,
            "traffic_shear_kn": 4.0,
            "permanent_deflection_mm": 15.0,
            "traffic_deflection_mm": 20.0,
        },
        "random_variables": [
            {"name": "dead_load_factor", "mean": 1.0},
            {
                "name": "live_load_factor", "family": "uniform",
                "lower": 0.8, "upper": 1.6,
            },
        ],
        "nominal_limit_states": {
            "values": {
                "g_flexure_knm": 21.8,
                "g_shear_kn": 12.2,
                "moment_effect_knm": 34.0,
                "nominal_moment_resistance_knm": 46.5,
                "moment_resistance_knm": 55.8,
                "shear_effect_kn": 7.8,
                "nominal_shear_resistance_kn": 20.0,
                "shear_resistance_kn": 20.0,
                "deflection_stiffness_scale": 1.0,
                "deflection_mm": 39.0,
                "g_deflection_mm": 11.0,
            },
        },
        "limit_state_model": {"deflection_limit_mm": 50.0},
        "split_rows": {},
    })

    assert "gM = MR − MEd" in report
    assert "gV = VR − VEd" in report
    assert "gδ = δlim − δ" in report
    assert "1 × (1 × 10 + 1.2 × 20) = 34 kNm (M_Ed)" in report
    assert "1 × (1 × 3 + 1.2 × 4) = 7.8 kN (V_Ed)" in report
    assert "gδ = 11 mm" in report
    assert "Reference analysis" in report
