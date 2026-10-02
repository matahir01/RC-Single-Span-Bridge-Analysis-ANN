"""Exercise the packaged executable, Qt runtime and engine in one process."""

from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

from rc_single_span.gui.engine_adapter import GuiCodeProfile, run_gui_analysis

if TYPE_CHECKING:
    from collections.abc import Callable

    from rc_single_span.gui.main_window import BridgeMainWindow


def run_package_smoke(window_factory: Callable[[], BridgeMainWindow], output_dir: str) -> int:
    """Open Qt, save/reopen the 15 m reference, analyse it and export a PDF."""

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    window = None
    try:
        window = window_factory()
        window.show()
        assert window.isVisible()
        reference = window._read_state()
        assert (reference.span_m, reference.girder_count, reference.section_type) == (
            15.0, 7, "rectangular"
        )
        assert reference.physical_girder_length_m == 14.95
        assert reference.deck_width_m == 11.0
        assert window._read_settings().lm1_step_m == 0.6
        # Use the independently audited 1.2 m comparison grid for the package
        # smoke gate. The normal application still defaults to the 0.6 m grid.
        window.lm1_step.setValue(1.2)
        window.design_enabled.setChecked(True)
        window.deflection_enabled.setChecked(True)
        window.deflection_limit.setValue(50.0)
        window.deflection_basis.setText("Packaged-app smoke scenario; not a project criterion")
        project_path = target / "reference_bridge.json"
        window.save_project(project_path)
        window.project_name.setText("Temporary changed name")
        window.open_project(project_path)
        assert window._read_state() == reference
        assert window._read_settings().lm1_step_m == 1.2
        assert window._read_design_inputs().enabled
        assert window._last_summary is None

        state = window._read_state()
        settings = window._read_settings()
        design = window._read_design_inputs()
        result, summary = run_gui_analysis(state.build_project(), settings, design)
        window._run_state, window._run_settings, window._run_design = state, settings, design
        window._run_fingerprint = window._fingerprint()
        window._analysis_finished(result, summary)
        assert window._last_summary is summary
        assert len(summary.rows) == len(summary.design_rows) == 7
        assert window._report_html is not None
        assert "Analysis, loading and combinations" in window._report_html
        assert "Governing" in window._report_html
        assert window._report_html.count("data:image/png;base64,") == 3

        pdf_path = target / "reference_calculation_report.pdf"
        window.write_report_pdf(pdf_path)
        assert pdf_path.read_bytes().startswith(b"%PDF-")
        assert pdf_path.stat().st_size > 50000

        # Exercise the packaged legacy route and its editable BS grid through
        # the same save/open and report path. This is a functional coarse-grid
        # smoke, not a traffic-grid convergence or bridge design acceptance.
        window.code_profile.setCurrentText(GuiCodeProfile.BS_5400.value)
        window.bs_ha_step.setValue(7.5)
        window.bs_hb_long_step.setValue(15.0)
        window.bs_hb_trans_step.setValue(3.5)
        window.bs_combined_long_step.setValue(15.0)
        window.bs_combined_trans_step.setValue(3.5)
        window.bs_combined_kel_step.setValue(15.0)
        window.retain_cases.setChecked(True)
        assert not window.all_case_deflection.isChecked()
        bs_project_path = target / "reference_bs_bridge.json"
        window.save_project(bs_project_path)
        window.project_name.setText("Temporary changed name")
        window.open_project(bs_project_path)
        bs_settings = window._read_settings()
        assert bs_settings.code_profile is GuiCodeProfile.BS_5400
        assert bs_settings.bs_hb_transverse_step_m == 3.5
        assert bs_settings.bs_combined_ha_kel_step_m == 15.0
        assert bs_settings.retain_all_cases and not bs_settings.all_case_combined_deflection
        assert window._last_summary is None
        bs_state = window._read_state()
        bs_design = window._read_design_inputs()
        bs_result, bs_summary = run_gui_analysis(
            bs_state.build_project(), bs_settings, bs_design,
        )
        window._run_state, window._run_settings = bs_state, bs_settings
        window._run_design = bs_design
        window._run_fingerprint = window._fingerprint()
        window._analysis_finished(bs_result, bs_summary)
        assert len(bs_summary.rows) == len(bs_summary.design_rows) == 7
        assert bs_result.bs_traffic is not None
        assert bs_result.bs_traffic.ha_hb.evaluated_case_count == 1032
        assert len(bs_result.bs_traffic.ha_hb.cases) == 1032
        assert bs_result.bs5400_characteristic_deflection == {}
        assert any("was not evaluated" in note for note in bs_summary.notes)
        assert window._report_html is not None
        assert "Equilibrium</td>" in window._report_html
        assert "Unverified grid" in window._report_html
        bs_pdf_path = target / "reference_bs_calculation_report.pdf"
        window.write_report_pdf(bs_pdf_path)
        assert bs_pdf_path.read_bytes().startswith(b"%PDF-")
        assert bs_pdf_path.stat().st_size > 50000
        (target / "smoke_result.json").write_text(
            json.dumps(
                {
                    "status": "passed",
                    "code_basis": summary.code_basis,
                    "girders": len(summary.rows),
                    "design_rows": len(summary.design_rows),
                    "smoke_lm1_step_m": settings.lm1_step_m,
                    "governing_moment_knm": summary.governing_moment.moment_knm,
                    "pdf_bytes": pdf_path.stat().st_size,
                    "bs_girders": len(bs_summary.rows),
                    "bs_design_rows": len(bs_summary.design_rows),
                    "bs_combined_placements": bs_result.bs_traffic.ha_hb.evaluated_case_count,
                    "bs_retained_placements": len(bs_result.bs_traffic.ha_hb.cases),
                    "bs_pdf_bytes": bs_pdf_path.stat().st_size,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        (target / "smoke_error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise
    finally:
        if window is not None:
            window.close()
    return 0
