from dataclasses import replace

import pytest

from rc_single_span.analysis.grillage import build_final_composite_grillage
from rc_single_span.analysis.plan_loads import PlanPointLoad, build_plan_load_case
from rc_single_span.analysis.prepared_grillage import (
    prepare_vertical_grillage,
    solve_prepared_vertical_grillage,
)
from rc_single_span.codes.eurocode.combinations import EurocodeServiceabilityFactors
from rc_single_span.core.models import (
    BridgeProject,
    MaterialProperties,
    RectangularGirderProfile,
    SingleSpanBridgeGeometry,
)
from rc_single_span.verification.acceptance import (
    VerificationDomain,
    current_v1_acceptance_matrix,
)
from rc_single_span.verification.comparison import (
    ComparisonStatus,
    ComparisonTolerance,
    compare_scalar,
)
from rc_single_span.verification.deflection import combined_deflection_envelope
from rc_single_span.verification.reference_runner import ReferenceRunConfig
from rc_single_span.verification.report import (
    CalculationReport,
    CalculationSection,
    CalculationStep,
    render_markdown,
)


def _project() -> BridgeProject:
    return BridgeProject(
        name="Stage8 verification benchmark",
        geometry=SingleSpanBridgeGeometry(
            span_m=15.0,
            deck_width_m=6.0,
            carriageway_width_m=5.0,
            girder_count=3,
            girder_spacing_m=2.0,
            girder_profile=RectangularGirderProfile(
                width_m=0.40,
                depth_m=0.95,
            ),
        ),
        materials=MaterialProperties(
            fck_mpa=25.0,
            fcu_mpa=30.0,
            fyk_mpa=410.0,
            concrete_density_kn_m3=24.0,
            elastic_modulus_mpa=30000.0,
        ),
    )


def _solved_case(load_kn: float, case_id: int):
    build = build_final_composite_grillage(
        _project(),
        stations_m=(0.0, 7.5, 15.0),
    )
    case = build_plan_load_case(
        build.model,
        load_case_id=case_id,
        name=f"verification case {case_id}",
        point_loads=(
            PlanPointLoad(
                x_m=7.5,
                y_m=0.0,
                magnitude_kn=load_kn,
                label="midspan verification point",
            ),
        ),
    )
    model = replace(build.model, load_cases=(case,))
    prepared = prepare_vertical_grillage(model)
    analysis = solve_prepared_vertical_grillage(prepared, model)
    return model, analysis


def test_scalar_comparison_uses_absolute_and_relative_tolerance() -> None:
    passing = compare_scalar(
        label="moment",
        internal_value=100.05,
        reference_value=100.0,
        tolerance=ComparisonTolerance(relative=0.001, absolute=0.01),
        unit="kNm",
        source="independent benchmark",
    )
    failing = compare_scalar(
        label="moment",
        internal_value=101.0,
        reference_value=100.0,
        tolerance=ComparisonTolerance(relative=0.001, absolute=0.01),
    )
    assert passing.status is ComparisonStatus.PASS
    assert failing.status is ComparisonStatus.FAIL


def test_acceptance_matrix_does_not_promote_internal_tests_to_verified() -> None:
    matrix = current_v1_acceptance_matrix()
    assert not matrix.v1_gate.accepted
    assert "common_grillage" in matrix.v1_gate.blockers
    structural = matrix.by_domain(VerificationDomain.STRUCTURAL_ANALYSIS)
    assert structural
    assert all(not item.state.value == "accepted" for item in structural)


def test_calculation_report_forces_formula_substitution_result_and_reference() -> None:
    report = CalculationReport(
        title="Verification calculation",
        project_name="15 m reference",
        assumptions=("Example assumption",),
        warnings=("Independent review pending",),
        sections=(
            CalculationSection(
                title="Flexure",
                steps=(
                    CalculationStep(
                        title="Design moment",
                        formula="M_Ed = 1.35 G_k + 1.35 Q_k",
                        substitution="M_Ed = 1.35(100) + 1.35(200)",
                        result="M_Ed = 405 kNm",
                        reference="EN 1990 project combination basis",
                        status="CHECKED",
                    ),
                ),
            ),
        ),
    )
    markdown = render_markdown(report)
    for token in ("Formula:", "Substitution:", "Result:", "Reference:", "Status:"):
        assert token in markdown


def test_all_case_combined_deflection_search_finds_stronger_traffic_case() -> None:
    model_1, analysis_1 = _solved_case(100.0, 1)
    model_2, analysis_2 = _solved_case(50.0, 2)
    envelope = combined_deflection_envelope(
        cases=(
            (1, "100 kN case", model_1, analysis_1),
            (2, "50 kN case", model_2, analysis_2),
        ),
        girder_index=2,
        traffic_factor=1.0,
        permanent_deflection_mm=lambda x: 0.02 * x * (15.0 - x),
    )
    assert envelope.evaluated_case_count == 2
    assert envelope.governing.case_id == 1
    assert 0.0 < envelope.governing.x_m < 15.0
    assert envelope.governing.total_mm > envelope.governing.permanent_mm
    assert envelope.governing.traffic_mm > 0.0


def test_reference_runner_requires_explicit_positive_analysis_modulus() -> None:
    with pytest.raises(ValueError):
        ReferenceRunConfig(
            elastic_modulus_mpa=0.0,
            eurocode_sls_factors=EurocodeServiceabilityFactors(
                psi1_traffic=0.75,
                psi2_traffic=0.30,
            ),
        )
