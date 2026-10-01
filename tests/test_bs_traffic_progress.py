"""BS traffic progress must correspond to solved placements and support cancellation."""

from threading import Event

import pytest
from test_bs5400_ha_hb_combined import _project

from rc_single_span.core.progress import AnalysisCancelled, AnalysisControl
from rc_single_span.traffic.bs5400 import run_ha_grillage_search, run_hb_grillage_search


@pytest.mark.parametrize("traffic", ["ha", "hb"])
def test_bs_traffic_progress_and_cancellation(traffic: str) -> None:
    cancelled = Event()
    events: list[tuple[str, int, int]] = []

    def progress(phase: str, completed: int, total: int) -> None:
        events.append((phase, completed, total))
        if ("solving cases" in phase or "spacing 6 m" in phase) and completed >= 16:
            cancelled.set()

    control = AnalysisControl(progress, cancelled.is_set)
    with pytest.raises(AnalysisCancelled):
        if traffic == "ha":
            run_ha_grillage_search(_project(), longitudinal_step_m=7.5, control=control)
        else:
            run_hb_grillage_search(
                _project(), longitudinal_step_m=15.0, transverse_step_m=3.5,
                control=control,
            )
    assert any(completed >= 16 and total > completed for _, completed, total in events)
