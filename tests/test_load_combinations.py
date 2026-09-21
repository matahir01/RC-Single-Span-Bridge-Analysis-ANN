from types import SimpleNamespace

import pytest

from rc_single_span.analysis.permanent import (
    PermanentLoadCategory,
    automatic_permanent_loads,
)
from rc_single_span.codes.bs5400.combinations import (
    BS5400LimitState,
    BS5400PermanentGammaFL,
    BS5400PrimaryTraffic,
    build_bs5400_primary_combination,
    primary_live_gamma_fl,
)
from rc_single_span.codes.common import LoadEffects
from rc_single_span.codes.eurocode.combinations import (
    EurocodeServiceabilityFactors,
    build_eurocode_combination_set,
)
from rc_single_span.core.models import (
    BridgeProject,
    MaterialProperties,
    PermanentActionModel,
    PermanentLineAction,
    RectangularGirderProfile,
    SingleSpanBridgeGeometry,
    SurfacingLayer,
)
from rc_single_span.traffic.combinations import (
    build_bs5400_project_combinations,
    build_eurocode_project_combinations,
)


def _project() -> BridgeProject:
    return BridgeProject(
        name="Combination benchmark",
        geometry=SingleSpanBridgeGeometry(
            span_m=15.0,
            physical_girder_length_m=14.95,
            deck_width_m=11.0,
            carriageway_width_m=7.0,
            girder_count=7,
            girder_spacing_m=1.70,
            girder_profile=RectangularGirderProfile(width_m=0.40, depth_m=0.95),
        ),
        materials=MaterialProperties(
            fck_mpa=25.0,
            fcu_mpa=30.0,
            fyk_mpa=410.0,
            concrete_density_kn_m3=24.0,
            elastic_modulus_mpa=30000.0,
        ),
        permanent_actions=PermanentActionModel(
            surfacing_layers=[
                SurfacingLayer(
                    name="asphalt surfacing",
                    thickness_m=0.05,
                    density_kn_m3=22.0,
                    y_start_m=-3.5,
                    y_end_m=3.5,
                )
            ],
            line_actions=[
                PermanentLineAction(
                    name="barrier/service line",
                    magnitude_kn_m=10.0,
                    y_m=0.0,
                )
            ],
        ),
    )


def _component(value: float) -> SimpleNamespace:
    return SimpleNamespace(value=value)


def _traffic_girder(index: int, moment: float, shear: float, torsion: float) -> SimpleNamespace:
    return SimpleNamespace(
        girder_index=index,
        moment_knm=_component(moment),
        shear_kn=_component(shear),
        torsion_knm=_component(torsion),
    )


def _traffic_result(moment: float, shear: float, torsion: float) -> SimpleNamespace:
    return SimpleNamespace(
        girders=tuple(
            _traffic_girder(index, moment, shear, torsion)
            for index in range(1, 8)
        )
    )


def test_permanent_loads_are_explicitly_classified_for_bs_factors() -> None:
    categories = {item.category for item in automatic_permanent_loads(_project())}
    assert categories == {
        PermanentLoadCategory.STRUCTURAL_DEAD,
        PermanentLoadCategory.SURFACING,
        PermanentLoadCategory.OTHER_SUPERIMPOSED,
    }


def test_eurocode_core_combination_values() -> None:
    permanent = LoadEffects(moment_knm=100.0, shear_kn=40.0, torsion_knm=0.0)
    traffic = LoadEffects(moment_knm=200.0, shear_kn=80.0, torsion_knm=20.0)
    result = build_eurocode_combination_set(
        permanent,
        traffic,
        sls_factors=EurocodeServiceabilityFactors(
            psi1_traffic=0.75,
            psi2_traffic=0.30,
        ),
    )

    assert result.persistent_uls.effects.moment_knm == pytest.approx(405.0)
    assert result.characteristic_sls.effects.moment_knm == pytest.approx(300.0)
    assert result.frequent_sls.effects.moment_knm == pytest.approx(250.0)
    assert result.quasi_permanent_sls.effects.moment_knm == pytest.approx(160.0)
    assert result.persistent_uls.effects.torsion_knm == pytest.approx(27.0)


def test_bs5400_permanent_and_primary_live_factors() -> None:
    permanent = BS5400PermanentGammaFL()
    assert permanent.as_named_factors("uls") == {
        "structural_dead": pytest.approx(1.15),
        "surfacing": pytest.approx(1.75),
        "other_superimposed": pytest.approx(1.20),
    }
    assert permanent.as_named_factors("sls") == {
        "structural_dead": pytest.approx(1.00),
        "surfacing": pytest.approx(1.20),
        "other_superimposed": pytest.approx(1.00),
    }

    assert primary_live_gamma_fl(
        traffic=BS5400PrimaryTraffic.HA,
        combination=1,
        limit_state=BS5400LimitState.ULS,
    ) == pytest.approx(1.50)
    assert primary_live_gamma_fl(
        traffic=BS5400PrimaryTraffic.HA,
        combination=2,
        limit_state=BS5400LimitState.ULS,
    ) == pytest.approx(1.25)
    assert primary_live_gamma_fl(
        traffic=BS5400PrimaryTraffic.HB,
        combination=1,
        limit_state=BS5400LimitState.SLS,
    ) == pytest.approx(1.10)
    assert primary_live_gamma_fl(
        traffic=BS5400PrimaryTraffic.HA_HB,
        combination=3,
        limit_state=BS5400LimitState.SLS,
    ) == pytest.approx(1.00)


def test_bs5400_core_combination_scales_primary_live_load() -> None:
    result = build_bs5400_primary_combination(
        factored_permanent=LoadEffects(moment_knm=100.0, shear_kn=50.0),
        traffic_nominal=LoadEffects(moment_knm=80.0, shear_kn=40.0, torsion_knm=10.0),
        traffic=BS5400PrimaryTraffic.HB,
        combination=1,
        limit_state=BS5400LimitState.ULS,
        permanent_factor_audit={
            "structural_dead": 1.15,
            "surfacing": 1.75,
            "other_superimposed": 1.20,
        },
    )
    assert result.effects.moment_knm == pytest.approx(204.0)
    assert result.effects.shear_kn == pytest.approx(102.0)
    assert result.effects.torsion_knm == pytest.approx(13.0)
    assert result.factors["primary_live"] == pytest.approx(1.30)


def test_eurocode_project_combination_consumes_lm1_envelope_by_girder() -> None:
    traffic = _traffic_result(200.0, 80.0, 20.0)
    results = build_eurocode_project_combinations(
        _project(),
        traffic,
        sls_factors=EurocodeServiceabilityFactors(
            psi1_traffic=0.75,
            psi2_traffic=0.30,
        ),
    )
    assert len(results) == 7
    assert results[0].girder_index == 1
    assert (
        results[0].combinations.persistent_uls.effects.moment_knm
        > results[0].combinations.characteristic_sls.effects.moment_knm
    )
    assert results[0].combinations.persistent_uls.effects.torsion_knm == pytest.approx(27.0)


def test_bs_project_combinations_keep_componentwise_governing_traffic_source() -> None:
    suite = SimpleNamespace(
        ha=_traffic_result(100.0, 80.0, 4.0),
        hb=_traffic_result(120.0, 70.0, 10.0),
        ha_hb=_traffic_result(110.0, 130.0, 7.0),
    )
    results = build_bs5400_project_combinations(
        _project(),
        suite,
        combinations=(1,),
    )
    assert len(results) == 7
    first = results[0]
    assert len(first.cases) == 6
    assert len(first.governing) == 2

    uls = next(
        item
        for item in first.governing
        if item.limit_state is BS5400LimitState.ULS
    )
    assert uls.governing_sources["moment"] is BS5400PrimaryTraffic.HB
    assert uls.governing_sources["shear"] is BS5400PrimaryTraffic.HA_HB
    assert uls.governing_sources["torsion"] is BS5400PrimaryTraffic.HB
