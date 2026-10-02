"""The traffic load fast path preserves the general prepared solver's response."""

from dataclasses import replace

from rc_single_span.analysis.grillage import build_final_composite_grillage
from rc_single_span.analysis.plan_loads import PlanPointLoad, build_plan_load_case
from rc_single_span.analysis.prepared_grillage import (
    prepare_vertical_grillage,
    solve_prepared_vertical_grillage,
)
from rc_single_span.analysis.structural_model import UniformLoad
from rc_single_span.gui.project_state import GuiProjectState


def test_nodal_and_member_point_traffic_matches_general_solver() -> None:
    build = build_final_composite_grillage(
        GuiProjectState().build_project(),
        stations_m=(0.0, 7.5, 15.0),
        additional_y_lines_m=(0.25,),
    )
    prepared = prepare_vertical_grillage(build.model)
    for points in (
        (PlanPointLoad(7.5, 0.0, 50.0),),
        (PlanPointLoad(7.5, 0.0, 50.0), PlanPointLoad(7.5, 0.12, 100.0)),
    ):
        case = build_plan_load_case(
            build.model, load_case_id=1, name="traffic", point_loads=points,
        )
        model = replace(build.model, load_cases=(case,))
        fast = solve_prepared_vertical_grillage(prepared, model)
        # An exactly zero member UDL selects the existing general assembly
        # without changing the physical load or its member-end result.
        general_case = replace(case, uniform_loads=(UniformLoad(
            member_id=build.model.beams[0].member_id, magnitude_kn_m=0.0,
        ),))
        general = solve_prepared_vertical_grillage(
            prepared, replace(model, load_cases=(general_case,)),
        )
        assert fast == general
        assert abs(fast.vertical_equilibrium_residual_kn) < 1e-6
