"""Source-pinned BS 5400-4 reinforcement detailing limits.

The regression values below are taken directly from BS 5400-4:1990 detailing
provisions used by the focused legacy path:

- clause 5.8.4.1: minimum main tension steel = 0.15% b_a d for Grade 460 and
  0.25% b_a d for Grade 250;
- clause 5.8.4.2: for beam side faces deeper than 600 mm, longitudinal side-face
  steel is at least 0.05% b_t d on each face;
- clause 5.8.5: main tension/compression reinforcement <= 4% gross area;
- clause 5.8.8.1: clear bar spacing >= maximum aggregate size + 5 mm;
- clause 5.8.8.2: tension-bar spacing <= 300 mm, subject also to crack control;
- beam-link spacing <= 0.75d.
"""

import pytest

from rc_single_span.design.bs5400_detailing import (
    detailing_limits_bs5400,
    minimum_main_ratio_bs5400,
)


def test_bs5400_source_pinned_main_reinforcement_ratios() -> None:
    grade_460, basis_460 = minimum_main_ratio_bs5400(
        reinforcement_grade_mpa=460.0
    )
    grade_250, basis_250 = minimum_main_ratio_bs5400(
        reinforcement_grade_mpa=250.0
    )

    assert grade_460 == pytest.approx(0.0015)
    assert grade_250 == pytest.approx(0.0025)
    assert "460" in basis_460
    assert "250" in basis_250


def test_bs5400_source_pinned_beam_detailing_limits() -> None:
    limits = detailing_limits_bs5400(
        average_breadth_excluding_compression_flange_m=1.0,
        effective_depth_m=0.342,
        gross_concrete_area_m2=0.40,
        reinforcement_grade_mpa=460.0,
        side_face_depth_m=0.80,
        side_face_breadth_m=1.0,
        maximum_aggregate_size_mm=20.0,
    )

    assert limits.minimum_main_steel_mm2 == pytest.approx(513.0)
    assert limits.maximum_main_steel_mm2 == pytest.approx(16000.0)
    assert limits.side_face_reinforcement_required
    assert limits.minimum_side_face_steel_each_face_mm2 == pytest.approx(171.0)
    assert limits.minimum_clear_bar_spacing_mm == pytest.approx(25.0)
    assert limits.maximum_tension_bar_spacing_mm == pytest.approx(300.0)
    assert limits.maximum_link_spacing_mm == pytest.approx(256.5)


def test_bs5400_side_face_threshold_is_not_triggered_at_600_mm() -> None:
    limits = detailing_limits_bs5400(
        average_breadth_excluding_compression_flange_m=1.0,
        effective_depth_m=0.342,
        gross_concrete_area_m2=0.40,
        reinforcement_grade_mpa=460.0,
        side_face_depth_m=0.60,
        side_face_breadth_m=1.0,
        maximum_aggregate_size_mm=20.0,
    )

    assert not limits.side_face_reinforcement_required
    assert limits.minimum_side_face_steel_each_face_mm2 == pytest.approx(0.0)
