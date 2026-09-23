import pytest

from rc_single_span.analysis.sections import ConcreteLayer
from rc_single_span.design.doubly_reinforced import (
    check_doubly_reinforced_bs5400,
    check_doubly_reinforced_ec2,
    required_doubly_reinforced_steel_bs5400,
    required_doubly_reinforced_steel_ec2,
)
from rc_single_span.design.doubly_reinforced_detailing import (
    select_doubly_reinforced_cages_bs5400,
    select_doubly_reinforced_cages_ec2,
)


def _rectangular_layers() -> tuple[ConcreteLayer, ...]:
    return (ConcreteLayer(0.30, 0.0, 1.20, "rectangular girder"),)


def test_ec2_doubly_reinforced_requirement_recovers_force_and_moment_equilibrium() -> None:
    result = required_doubly_reinforced_steel_ec2(
        med_knm=3200.0,
        layers=_rectangular_layers(),
        effective_depth_m=1.10,
        compression_steel_depth_m=0.10,
        fck_mpa=35.0,
        fyk_mpa=500.0,
        maximum_neutral_axis_ratio=0.45,
    )

    assert result.excess_moment_knm > 0.0
    assert result.compression_steel_mm2 > 0.0
    assert result.total_tension_steel_mm2 > result.base_tension_steel_mm2
    assert abs(result.equilibrium_residual_kn) < 1.0e-9
    assert abs(result.moment_residual_knm) < 1.0e-9
    assert result.compression_steel_design_stress_mpa == pytest.approx(
        500.0 / 1.15
    )


def test_bs5400_doubly_reinforced_requirement_recovers_force_and_moment_equilibrium() -> None:
    result = required_doubly_reinforced_steel_bs5400(
        med_knm=3000.0,
        layers=_rectangular_layers(),
        effective_depth_m=1.10,
        compression_steel_depth_m=0.10,
        fcu_mpa=40.0,
        fy_mpa=500.0,
    )

    assert result.excess_moment_knm > 0.0
    assert result.compression_steel_mm2 > 0.0
    assert result.total_tension_steel_mm2 > result.base_tension_steel_mm2
    assert result.compression_steel_design_stress_mpa == pytest.approx(435.0)
    assert abs(result.equilibrium_residual_kn) < 1.0e-9
    assert abs(result.moment_residual_knm) < 1.0e-9


def test_doubly_reinforced_design_is_not_used_below_singly_limit() -> None:
    with pytest.raises(ValueError, match="does not exceed"):
        required_doubly_reinforced_steel_ec2(
            med_knm=1000.0,
            layers=_rectangular_layers(),
            effective_depth_m=1.10,
            compression_steel_depth_m=0.10,
            fck_mpa=35.0,
            fyk_mpa=500.0,
            maximum_neutral_axis_ratio=0.45,
        )


def test_compression_steel_must_be_inside_limiting_compression_zone() -> None:
    with pytest.raises(ValueError, match="outside the compression zone"):
        required_doubly_reinforced_steel_ec2(
            med_knm=3200.0,
            layers=_rectangular_layers(),
            effective_depth_m=1.10,
            compression_steel_depth_m=0.55,
            fck_mpa=35.0,
            fyk_mpa=500.0,
            maximum_neutral_axis_ratio=0.45,
        )


def test_ec2_discrete_doubly_reinforced_check_recovers_equilibrium_and_capacity() -> None:
    requirement = required_doubly_reinforced_steel_ec2(
        med_knm=3200.0,
        layers=_rectangular_layers(),
        effective_depth_m=1.10,
        compression_steel_depth_m=0.10,
        fck_mpa=35.0,
        fyk_mpa=500.0,
        maximum_neutral_axis_ratio=0.45,
    )
    result = check_doubly_reinforced_ec2(
        med_knm=3200.0,
        layers=_rectangular_layers(),
        effective_depth_m=1.10,
        compression_steel_depth_m=0.10,
        tension_steel_area_mm2=requirement.total_tension_steel_mm2 * 1.05,
        compression_steel_area_mm2=requirement.compression_steel_mm2 * 1.05,
        fck_mpa=35.0,
        fyk_mpa=500.0,
        maximum_neutral_axis_ratio=0.45,
    )

    assert abs(result.force_equilibrium_residual_kn) < 1.0e-3
    assert result.resistance_knm >= 3200.0
    assert result.passes
    assert result.compression_steel_stress_mpa > 0.0
    assert result.tension_steel_stress_mpa > 0.0


def test_bs5400_discrete_doubly_reinforced_check_recovers_equilibrium_and_capacity() -> None:
    requirement = required_doubly_reinforced_steel_bs5400(
        med_knm=3000.0,
        layers=_rectangular_layers(),
        effective_depth_m=1.10,
        compression_steel_depth_m=0.10,
        fcu_mpa=40.0,
        fy_mpa=500.0,
    )
    result = check_doubly_reinforced_bs5400(
        med_knm=3000.0,
        layers=_rectangular_layers(),
        effective_depth_m=1.10,
        compression_steel_depth_m=0.10,
        tension_steel_area_mm2=requirement.total_tension_steel_mm2 * 1.05,
        compression_steel_area_mm2=requirement.compression_steel_mm2 * 1.05,
        fcu_mpa=40.0,
        fy_mpa=500.0,
    )

    assert abs(result.force_equilibrium_residual_kn) < 1.0e-3
    assert result.resistance_knm >= 3000.0
    assert result.passes


def test_ec2_discrete_cage_selector_uses_actual_top_and_bottom_centroids() -> None:
    requirement = required_doubly_reinforced_steel_ec2(
        med_knm=3200.0,
        layers=_rectangular_layers(),
        effective_depth_m=1.10,
        compression_steel_depth_m=0.10,
        fck_mpa=35.0,
        fyk_mpa=500.0,
        maximum_neutral_axis_ratio=0.45,
    )
    selection = select_doubly_reinforced_cages_ec2(
        requirement=requirement,
        layers=_rectangular_layers(),
        total_depth_m=1.20,
        tension_width_mm=400.0,
        compression_width_mm=400.0,
        cover_mm=40.0,
        link_diameter_mm=12.0,
        minimum_clear_spacing_mm=25.0,
        fck_mpa=35.0,
        fyk_mpa=500.0,
        maximum_neutral_axis_ratio=0.45,
        available_diameters_mm=(20.0, 25.0, 32.0),
        maximum_layers=4,
    )

    assert selection.tension.provided_area_mm2 >= requirement.total_tension_steel_mm2
    assert selection.compression.provided_area_mm2 >= requirement.compression_steel_mm2
    assert 0.0 < selection.actual_compression_depth_m < selection.actual_effective_depth_m
    assert selection.check.passes
    assert selection.passing_pairs > 0
    assert selection.pairs_evaluated >= selection.passing_pairs


def test_bs5400_discrete_cage_selector_verifies_combined_cage() -> None:
    requirement = required_doubly_reinforced_steel_bs5400(
        med_knm=3000.0,
        layers=_rectangular_layers(),
        effective_depth_m=1.10,
        compression_steel_depth_m=0.10,
        fcu_mpa=40.0,
        fy_mpa=500.0,
    )
    selection = select_doubly_reinforced_cages_bs5400(
        requirement=requirement,
        layers=_rectangular_layers(),
        total_depth_m=1.20,
        tension_width_mm=400.0,
        compression_width_mm=400.0,
        cover_mm=40.0,
        link_diameter_mm=12.0,
        minimum_clear_spacing_mm=25.0,
        fcu_mpa=40.0,
        fy_mpa=500.0,
        available_diameters_mm=(20.0, 25.0, 32.0),
        maximum_layers=4,
    )

    assert selection.check.passes
    assert selection.check.resistance_knm >= 3000.0
    assert selection.tension.provided_area_mm2 >= requirement.total_tension_steel_mm2
    assert selection.compression.provided_area_mm2 >= requirement.compression_steel_mm2
