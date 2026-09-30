"""Guard the full bridge LM1 optimization against the pre-change engine."""

import json
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from rc_single_span.codes.eurocode.combinations import EurocodeServiceabilityFactors
from rc_single_span.verification.reference_runner import ReferenceRunConfig, run_reference_project

_EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
if str(_EXAMPLES) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES))


def test_full_reference_bridge_matches_legacy_governing_cases_and_design_inputs() -> None:
    from thesis_bridge_15m import thesis_bridge_15m

    golden = json.loads((Path(__file__).resolve().parents[1] / "docs" / "benchmarks"
                         / "lm1_3m_legacy_2026-09-30.json").read_text())
    result = run_reference_project(
        thesis_bridge_15m(),
        config=ReferenceRunConfig(
            elastic_modulus_mpa=34000,
            eurocode_sls_factors=EurocodeServiceabilityFactors(
                psi1_traffic=0.75, psi1_udl_traffic=0.4, psi2_traffic=0,
            ),
            lm1_longitudinal_step_m=3.0,
            retain_all_cases=False,
        ),
        code_route="bs_en",
    )
    assert result.lm1.evaluated_case_count == golden["lm1_count"]
    assert len(result.lm1.cases) == len(golden["cases"])

    for girder, old in zip(result.lm1.girders, golden["girders"], strict=True):
        for name in ("moment_knm", "shear_kn", "torsion_knm", "deflection_mm"):
            actual, expected = asdict(getattr(girder, name)), old[name]
            assert actual["case_id"] == expected["case_id"]
            assert actual["member_id"] == expected["member_id"]
            assert actual["value"] == pytest.approx(expected["value"], abs=1e-7)

    for girder, old in zip(result.lm1.station_moments, golden["stations"], strict=True):
        for station, expected in zip(girder.stations, old, strict=True):
            assert station.x_m == expected["x_m"]
            assert station.moment_knm.case_id == expected["moment"]["case_id"]
            assert station.moment_knm.member_id == expected["moment"]["member_id"]
            assert station.moment_knm.value == pytest.approx(
                expected["moment"]["value"], abs=1e-7,
            )

    for case, expected in zip(result.lm1.cases, golden["cases"], strict=True):
        assert case.placement.case_id == expected["id"]
        assert [(lane.lane_number, lane.tandem_lead_x_m) for lane in case.placement.lanes] == [
            tuple(item) for item in expected["tandem"]
        ]
        assert [asdict(load) for load in case.model.load_cases[0].uniform_loads] == (
            expected["uniform_loads"]
        )

    for combo, expected in zip(result.eurocode_combinations, golden["combinations"],
                               strict=True):
        assert combo.girder_index == expected["girder"]
        for key, effect in (("uls", combo.combinations.persistent_uls.effects),
                            ("frequent", combo.combinations.frequent_sls.effects)):
            for name, value in asdict(effect).items():
                assert value == pytest.approx(expected[key][name], abs=1e-7)
