from rc_single_span.verification.legacy_bs_expanded_acceptance import (
    expanded_legacy_bs_v1_gate,
)


def test_expanded_legacy_bs_v1_gate_is_closed() -> None:
    gate = expanded_legacy_bs_v1_gate()
    assert gate.accepted
    assert gate.blockers == ()
    names = {item.capability for item in gate.capabilities}
    assert "legacy_bs_combinations_1_to_5" in names
    assert "legacy_bs_fatigue_vehicle" in names
    assert "legacy_bs_curtailment" in names
