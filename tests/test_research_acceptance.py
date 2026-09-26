from rc_single_span.research.acceptance import (
    ResearchEvidenceState,
    ann_reliability_rbdo_gate,
)


def test_research_gate_remains_validation_pending_after_implementation() -> None:
    gate = ann_reliability_rbdo_gate()
    assert not gate.accepted
    assert "probabilistic_model" in gate.blockers
    assert "sampling_convergence" in gate.blockers
    assert "surrogate_validation" in gate.blockers
    assert "reliability_cross_check" in gate.blockers
    assert "target_reliability" in gate.blockers
    assert "rbdo_validation" in gate.blockers
    target = next(item for item in gate.items if item.key == "target_reliability")
    assert target.state is ResearchEvidenceState.VALIDATED
    assert all(item.state is not ResearchEvidenceState.NOT_STARTED for item in gate.items)
    assert all(item.remaining.strip() for item in gate.items)
