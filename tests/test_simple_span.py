import pytest

from rc_single_span.analysis.simple_span import (
    DistributedLoadSegment,
    simple_span_distributed_load_response,
    udl_simple_span,
)


def test_udl_closed_form_reference() -> None:
    result = udl_simple_span(15.0, 20.0)
    assert result.reaction_left_kn == pytest.approx(150.0)
    assert result.reaction_right_kn == pytest.approx(150.0)
    assert result.max_moment_knm == pytest.approx(562.5)
    assert result.max_shear_kn == pytest.approx(150.0)


def test_segmented_udl_recovers_full_span_closed_form() -> None:
    result = simple_span_distributed_load_response(
        15.0,
        [DistributedLoadSegment(20.0, 0.0, 15.0)],
    )
    assert result.reaction_left_kn == pytest.approx(150.0)
    assert result.reaction_right_kn == pytest.approx(150.0)
    assert result.max_moment_position_m == pytest.approx(7.5)
    assert result.max_moment_knm == pytest.approx(562.5)
