import pytest

from rc_single_span.analysis.sections import ConcreteLayer
from rc_single_span.design.doubly_reinforced import (
    required_doubly_reinforced_steel_bs5400,
    required_doubly_reinforced_steel_ec2,
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
