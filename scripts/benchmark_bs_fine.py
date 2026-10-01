"""Capture the default GUI BS 5400 route for same-runner old/new comparison."""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from time import perf_counter


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.path[:0] = [str(args.root.resolve() / "src")]

    from rc_single_span.gui.design_adapter import GuiDesignInputs
    from rc_single_span.gui.engine_adapter import (
        GuiAnalysisSettings,
        GuiCodeProfile,
        run_gui_analysis,
    )
    from rc_single_span.gui.project_state import GuiProjectState

    start = perf_counter()
    result, summary = run_gui_analysis(
        GuiProjectState().build_project(),
        GuiAnalysisSettings(code_profile=GuiCodeProfile.BS_5400),
        GuiDesignInputs(enabled=True),
    )
    assert result.bs_traffic is not None
    suite = result.bs_traffic
    record = {
        "elapsed_s": perf_counter() - start,
        "traffic": {
            label: {
                "evaluated_case_count": search.evaluated_case_count,
                "girders": [asdict(item) for item in search.girders],
                "stations": [asdict(item) for item in search.station_moments],
                "retained_cases": [
                    {
                        "case_id": (
                            case.case_id if hasattr(case, "case_id")
                            else case.placement.case_id
                        ),
                        "physical_loads": [asdict(load) for load in case.model.load_cases],
                        "girders": [asdict(item) for item in case.girders],
                    }
                    for case in search.cases
                ],
            }
            for label, search in (("ha", suite.ha), ("hb", suite.hb),
                                  ("ha_hb", suite.ha_hb))
        },
        "combinations": [asdict(item) for item in result.bs5400_combinations],
        "design": [asdict(item) for item in result.bs5400_design],
        "summary_rows": [asdict(item) for item in summary.rows],
    }
    args.output.write_text(json.dumps(record, sort_keys=True, default=str), encoding="utf-8")
    print(f"{args.output}: {record['elapsed_s']:.2f} s; "
          f"HA/HB/HA+HB = "
          f"{[item['evaluated_case_count'] for item in record['traffic'].values()]}")


if __name__ == "__main__":
    main()
