"""Response-level UDL placement checks using the actual common grillage."""

import pytest
from dataclasses import replace

from rc_single_span.analysis.grillage import build_final_composite_grillage
from rc_single_span.analysis.prepared_grillage import prepare_vertical_grillage
from rc_single_span.analysis.prepared_grillage import solve_prepared_vertical_grillage
from rc_single_span.analysis.plan_loads import build_plan_load_case
from rc_single_span.traffic.lm1 import (
    _fixed_search_grid,
    build_lm1_plan_loads,
    generate_lm1_search_placements,
)
from rc_single_span.traffic.lm1_influence import (
    optimize_lm1_udl_for_response,
    run_lm1_signed_response_search,
)
from test_lm1_common_grillage import _project


def test_actual_grillage_udl_cells_select_signed_unfavourable_regions() -> None:
    project = _project(carriageway_width_m=3.0)
    placement = generate_lm1_search_placements(
        project, longitudinal_step_m=7.5,
    )[0]
    x, y = _fixed_search_grid(project, (placement,))
    model = build_final_composite_grillage(
        project, stations_m=x, additional_y_lines_m=y,
    ).model
    prepared = prepare_vertical_grillage(model)
    member = next(beam.member_id for beam in model.beams
                  if beam.member_id == 1)

    def signed_shear(result):
        return next(item.i_vertical_force_kn for item in result.members
                    if item.member_id == member)

    positive = optimize_lm1_udl_for_response(
        project, placement, model, prepared, signed_shear,
    )
    negative = optimize_lm1_udl_for_response(
        project, placement, model, prepared, signed_shear, sign=-1,
    )
    assert positive.cell_effects
    points, _ = build_lm1_plan_loads(project, placement, udl_regions=())
    tandem = build_plan_load_case(model, load_case_id=1, name="TS only", point_loads=points)
    tandem_response = signed_shear(solve_prepared_vertical_grillage(
        prepared, replace(model, load_cases=(tandem,)),
    ))
    assert positive.response == pytest.approx(
        tandem_response + sum(effect for _, effect in positive.cell_effects
                              if effect > 0.0), abs=1e-7,
    )
    assert negative.response == pytest.approx(
        tandem_response + sum(effect for _, effect in negative.cell_effects
                              if effect < 0.0), abs=1e-7,
    )
    assert positive.analysis.vertical_equilibrium_residual_kn == pytest.approx(0.0, abs=1e-6)
    assert negative.analysis.vertical_equilibrium_residual_kn == pytest.approx(0.0, abs=1e-6)
    assert positive.response >= negative.response - 1e-8
    assert all(effect > 0 for bounds, effect in positive.cell_effects
               if bounds in positive.regions)
    assert all(effect < 0 for bounds, effect in negative.cell_effects
               if bounds in negative.regions)
    points, areas = build_lm1_plan_loads(
        project, placement, udl_regions=positive.regions,
    )
    assert len(points) == 4
    assert len(areas) == len(positive.regions)


def test_signed_response_search_returns_resolved_governing_case() -> None:
    project = _project(carriageway_width_m=3.0)

    def response(result):
        return next(item.i_vertical_force_kn for item in result.members
                    if item.member_id == 1)

    positive = run_lm1_signed_response_search(
        project, response, sign=1, longitudinal_step_m=7.5,
    )
    negative = run_lm1_signed_response_search(
        project, response, sign=-1, longitudinal_step_m=7.5,
    )
    assert positive.evaluated_tandem_placements == negative.evaluated_tandem_placements
    assert positive.influence.response >= negative.influence.response
    assert positive.influence.analysis.vertical_equilibrium_residual_kn == pytest.approx(
        0.0, abs=1e-6,
    )
