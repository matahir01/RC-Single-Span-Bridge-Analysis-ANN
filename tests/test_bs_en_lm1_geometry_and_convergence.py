"""Source-pinned BS EN 1991-2 LM1 geometry and convergence controls."""

import pytest
from test_lm1_common_grillage import _project

from rc_single_span.codes.eurocode.lm1 import notional_lane_layout
from rc_single_span.traffic.lm1 import (
    LM1_AXLE_SPACING_M,
    LM1_TRANSVERSE_WHEEL_SPACING_M,
    _transverse_layouts,
    build_lm1_plan_loads,
    generate_lm1_search_placements,
)
from rc_single_span.traffic.lm1_influence_convergence import (
    run_lm1_influence_grillage_search_converged,
)


def test_bs_en_reference_carriageway_enumerates_lane_numbering_and_remaining_edges() -> None:
    """A 7 m carriageway must consider both lane orderings and both remainder edges."""

    project = _project(carriageway_width_m=7.0)
    layout = notional_lane_layout(7.0)
    assert layout.lane_count == 2
    assert layout.lane_width_m == pytest.approx(3.0)
    assert layout.remaining_width_m == pytest.approx(1.0)

    transverse = _transverse_layouts(project)
    assert len(transverse) == 4
    assert {tuple(item[0] for item in lanes) for lanes, _ in transverse} == {
        (1, 2),
        (2, 1),
    }

    left = -3.5
    right = 3.5
    remainder_bounds = {remaining[0] for _, remaining in transverse}
    assert remainder_bounds == {(left, left + 1.0), (right - 1.0, right)}

    for lanes, remaining in transverse:
        assert len(lanes) == 2
        assert len(remaining) == 1
        for _, y_start, y_end in lanes:
            assert y_end - y_start == pytest.approx(3.0)


def test_bs_en_lm1_tandem_wheels_and_characteristic_resultants_match_source_basis() -> None:
    """Pin the JRC/BS EN reference LM1 axle, wheel and UDL resultants for 7 m x 15 m."""

    project = _project(carriageway_width_m=7.0)
    placement = generate_lm1_search_placements(
        project,
        longitudinal_step_m=15.0,
    )[0]
    points, areas = build_lm1_plan_loads(project, placement)

    # Two loaded notional lanes, two axles per tandem and two wheels per axle.
    assert len(points) == 8
    assert len(areas) == 3  # lane 1 UDL + lane 2 UDL + remaining-area UDL
    assert sum(point.load_kn for point in points) == pytest.approx(1000.0)
    assert sum(
        area.pressure_kn_m2
        * (area.x_end_m - area.x_start_m)
        * (area.y_end_m - area.y_start_m)
        for area in areas
    ) == pytest.approx(555.0)

    by_lane: dict[int, list] = {1: [], 2: []}
    for point in points:
        lane = 1 if "lane 1" in point.label else 2
        by_lane[lane].append(point)

    for lane_number, lane_points in by_lane.items():
        assert len(lane_points) == 4
        xs = sorted({point.x_m for point in lane_points})
        assert len(xs) == 2
        assert xs[1] - xs[0] == pytest.approx(LM1_AXLE_SPACING_M)
        for axle_x in xs:
            ys = sorted(point.y_m for point in lane_points if point.x_m == axle_x)
            assert len(ys) == 2
            assert ys[1] - ys[0] == pytest.approx(LM1_TRANSVERSE_WHEEL_SPACING_M)

        lane = next(item for item in placement.lanes if item.lane_number == lane_number)
        assert all(
            lane.y_start_m <= point.y_m <= lane.y_end_m
            for point in lane_points
        )


def test_influence_surface_search_has_an_explicit_exhaustive_refinement_path() -> None:
    """The adverse-region production search can now be convergence-audited directly."""

    project = _project(carriageway_width_m=3.0)
    audit = run_lm1_influence_grillage_search_converged(
        project,
        initial_longitudinal_step_m=7.5,
        minimum_longitudinal_step_m=3.75,
        relative_tolerance=0.99,
        max_refinements=1,
    )

    assert len(audit.refinements) == 1
    refinement = audit.refinements[0]
    assert refinement.coarse_step_m == pytest.approx(7.5)
    assert refinement.fine_step_m == pytest.approx(3.75)
    assert refinement.maximum_relative_change >= 0.0
    assert refinement.governing_quantity in {
        "moment",
        "shear",
        "torsion",
        "deflection",
    }
    assert audit.result.tandem_combinations_exhaustive
    assert audit.result.longitudinal_step_m == pytest.approx(3.75)
