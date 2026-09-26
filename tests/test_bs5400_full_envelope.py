from rc_single_span.codes.bs5400.combinations import (
    BS5400LimitState,
    BS5400PrimaryTraffic,
)
from rc_single_span.codes.common import FactoredCombination, LoadEffects
from rc_single_span.traffic.bs5400_full_combinations import (
    BS5400FullGirderCombinationResult,
    BS5400SupplementaryCombinationCase,
)
from rc_single_span.traffic.bs5400_full_envelope import (
    full_bs5400_combination_envelope,
)
from rc_single_span.traffic.combinations import (
    BS5400GirderCombinationResult,
    BS5400TrafficCombinationCase,
)


def _primary_case(limit_state: BS5400LimitState, moment: float):
    return BS5400TrafficCombinationCase(
        girder_index=1,
        traffic=BS5400PrimaryTraffic.HA,
        combination=1,
        limit_state=limit_state,
        nominal_traffic=LoadEffects(moment_knm=1.0),
        result=FactoredCombination(
            name=f"primary {limit_state.value}",
            effects=LoadEffects(moment_knm=moment, shear_kn=40.0, torsion_knm=5.0),
            factors={"traffic": 1.0},
        ),
    )


def test_supplementary_combination_can_govern_full_envelope() -> None:
    primary = BS5400GirderCombinationResult(
        girder_index=1,
        permanent_characteristic_by_category={},
        cases=(
            _primary_case(BS5400LimitState.ULS, 100.0),
            _primary_case(BS5400LimitState.SLS, 80.0),
        ),
        governing=(),
    )
    supplementary = (
        BS5400SupplementaryCombinationCase(
            girder_index=1,
            combination=4,
            limit_state=BS5400LimitState.ULS,
            action_name="longitudinal_ha",
            result=FactoredCombination(
                name="BS 5400 combination 4 ULS",
                effects=LoadEffects(moment_knm=-140.0, shear_kn=-60.0, torsion_knm=8.0),
                factors={"secondary_live": 1.25},
            ),
            provenance="BD 37/01 benchmark",
        ),
        BS5400SupplementaryCombinationCase(
            girder_index=1,
            combination=5,
            limit_state=BS5400LimitState.SLS,
            action_name="bearing_friction",
            result=FactoredCombination(
                name="BS 5400 combination 5 SLS",
                effects=LoadEffects(moment_knm=90.0, shear_kn=45.0, torsion_knm=-11.0),
                factors={"bearing_friction": 1.0},
            ),
            provenance="BD 37/01 benchmark",
        ),
    )
    result = BS5400FullGirderCombinationResult(
        girder_index=1,
        primary=primary,
        supplementary=supplementary,
    )
    envelope = full_bs5400_combination_envelope(result)
    assert envelope.uls_moment_knm == 140.0
    assert "combination 4" in envelope.uls_moment_source
    assert envelope.uls_shear_kn == 60.0
    assert envelope.sls_torsion_knm == 11.0
    assert "combination 5" in envelope.sls_torsion_source
