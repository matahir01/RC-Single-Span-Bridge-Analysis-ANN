import pytest

from rc_single_span.design.serviceability import (
    ProjectDeflectionCriterion,
    response_deflection_check,
)


def test_span_ratio_deflection_limit_requires_explicit_project_basis() -> None:
    criterion = ProjectDeflectionCriterion.from_span_ratio(
        span_m=15.0,
        denominator=300.0,
        basis="Project specification: vertical deflection limited to L/300",
    )

    assert criterion.allowable_deflection_mm == pytest.approx(50.0)
    assert "L/300" in criterion.basis


def test_span_ratio_helper_has_no_hidden_default_denominator() -> None:
    with pytest.raises(TypeError):
        ProjectDeflectionCriterion.from_span_ratio(
            span_m=15.0,
            basis="project criterion",
        )


def test_deflection_check_preserves_project_criterion_provenance() -> None:
    criterion = ProjectDeflectionCriterion.from_span_ratio(
        span_m=15.0,
        denominator=250.0,
        basis="Client design brief: L/250 serviceability criterion",
    )
    result = response_deflection_check(
        permanent_deflection_mm=18.0,
        traffic_characteristic_deflection_mm=12.0,
        traffic_factor=0.75,
        allowable_deflection_mm=criterion.allowable_deflection_mm,
        criterion_basis=criterion.basis,
        status="BS EN frequent traffic response with project-selected limit",
    )

    assert result.total_deflection_mm == pytest.approx(27.0)
    assert result.allowable_deflection_mm == pytest.approx(60.0)
    assert result.utilization == pytest.approx(0.45)
    assert result.g_deflection_mm == pytest.approx(33.0)
    assert result.passes
    assert result.criterion_basis == criterion.basis


def test_deflection_check_does_not_claim_pass_without_project_limit() -> None:
    result = response_deflection_check(
        permanent_deflection_mm=18.0,
        traffic_characteristic_deflection_mm=12.0,
        traffic_factor=0.75,
        allowable_deflection_mm=None,
        status="response only; no project acceptance criterion supplied",
    )

    assert result.total_deflection_mm == pytest.approx(27.0)
    assert result.utilization is None
    assert result.g_deflection_mm is None
    assert result.passes is None
    assert result.criterion_basis is None


def test_criterion_provenance_cannot_exist_without_limit() -> None:
    with pytest.raises(ValueError, match="without a deflection limit"):
        response_deflection_check(
            permanent_deflection_mm=10.0,
            traffic_characteristic_deflection_mm=5.0,
            traffic_factor=1.0,
            allowable_deflection_mm=None,
            criterion_basis="L/300",
            status="invalid",
        )
