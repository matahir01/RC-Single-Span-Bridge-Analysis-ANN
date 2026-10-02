"""New runner metadata must not disable the old/new BS numeric gate."""

import json
import subprocess
import sys
from pathlib import Path


def test_bs_legacy_comparator_accepts_historical_default_but_rejects_changed_effects(
    tmp_path: Path,
) -> None:
    script = Path(__file__).parents[1] / "scripts" / "compare_bs_traffic.py"
    old = {
        "elapsed_s": 10.0,
        "config": {"retain_all_cases": False},
        "traffic": {"ha": {"moment_knm": 42.0}},
        "combinations": [],
    }
    current = {
        **old,
        "elapsed_s": 5.0,
        "config": {**old["config"], "evaluate_all_case_combined_deflection": True},
    }
    old_path, current_path = tmp_path / "old.json", tmp_path / "current.json"
    old_path.write_text(json.dumps(old), encoding="utf-8")

    def compare(record: dict) -> subprocess.CompletedProcess[str]:
        current_path.write_text(json.dumps(record), encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(script), str(old_path), str(current_path)],
            capture_output=True, text=True, check=False,
        )

    assert compare(current).returncode == 0
    assert compare({**current, "traffic": {"ha": {"moment_knm": 43.0}}}).returncode != 0
    assert compare({**current, "config": {
        **current["config"], "evaluate_all_case_combined_deflection": False,
    }}).returncode != 0
