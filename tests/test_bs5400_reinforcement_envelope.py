from types import SimpleNamespace

import pytest

from rc_single_span.core.models import (
    BridgeProject,
    MaterialProperties,
    RectangularGirderProfile,
    SingleSpanBridgeGeometry,
)
from rc_single_span.design.detailing import select_longitudinal_bar_arrangement
from rc_single_span.design.reinforcement_envelope import (
    build_bs5400_curtailment_plan_from_envelope,
    build_bs5400_station_reinforcement_envelope,
)
from rc_single_span.traffic.bs5400 import (
    BS5400GirderStationMomentEnvelope,
    BS5400StationMomentEnvelope,
    GoverningComponent,
)


def _project() -> BridgeProject:
    return BridgeProject(
        name="BS station reinforcement envelope benchmark",
        geometry=SingleSpanBridgeGeometry(
            span_m=10.0,
            deck_width_m=5.0,
            carriageway_width_m=3.0,
            girder_count=3,
            girder_spacing_m=1.70,
            girder_profile=RectangularGirderProfile(
                width_m=0.40,
                depth_m=1.20,
            ),
        ),
        materials=MaterialProperties(
            fck_mpa=35.0,
            fcu_mpa=45.0,
            fyk_mpa=460.0,
            concrete_density_kn_m3=25.0,
            elastic_modulus_mpa=34000.0,
        ),
    )


def _station_girder(
    values: tuple[float, ...],
    stations: tuple[float, ...],
    *,
    case_offset: int,
) -> BS5400GirderStationMomentEnvelope:
    return BS5400GirderStationMomentEnvelope(
        girder_index=2,
        y_m=0.0,
        stations=tuple(
            BS5400StationMomentEnvelope(
                x_m=x_m,
                moment_knm=GoverningComponent(
                    value=value,
                    case_id=case_offset + index,
                    member_id=100 + index,
                ),
            )
            for index, (x_m, value) in enumerate(
                zip(stations, values, strict=True),
                start=1,
            )
        ),
    )


def _suite():
    stations = (0.0, 2.5, 5.0, 7.5, 10.0)
    ha = SimpleNamespace(
        design_stations_m=stations,
        station_moments=(
            _station_girder((0.0, 180.0, 360.0, 180.0, 0.0), stations, case_offset=0),
        ),
        kel_combinations_exhaustive=True,
    )
    hb = SimpleNamespace(
        design_stations_m=stations,
        station_moments=(
            _station_girder((0.0, 220.0, 390.0, 220.0, 0.0), stations, case_offset=100),
        ),
    )
    ha_hb = SimpleNamespace(
        design_stations_m=stations,
        station_moments=(
            _station_girder((0.0, 250.0, 430.0, 250.0, 0.0), stations, case_offset=200),
        ),
        ha_assignment_search_exhaustive=True,
        kel_combinations_exhaustive=True,
    )
    return SimpleNamespace(ha=ha, hb=hb, ha_hb=ha_hb)


def test_bs_station_envelope_compares_ha_hb_and_combined_on_exact_same_grid() -> None:
    envelope = build_bs5400_station_reinforcement_envelope(
        _project(),
        _suite(),
        girder_index=2,
        effective_depth_m=1.10,
        minimum_area_mm2=1200.0,
    )

    assert envelope.design_stations_m == pytest.approx(
        (0.0, 2.5, 5.0, 7.5, 10.0)
    )
    assert envelope.singly_reinforced_complete
    assert envelope.traffic_search_exhaustive
    assert envelope.stations[0].governing_required_area_mm2 == pytest.approx(1200.0)
    assert envelope.stations[-1].governing_required_area_mm2 == pytest.approx(1200.0)
    assert envelope.maximum_required_station_m == pytest.approx(5.0)
    assert envelope.maximum_required_area_mm2 is not None
    assert envelope.maximum_required_area_mm2 > 1200.0
    assert envelope.stations[2].traffic.value == "ha_hb"
    assert envelope.stations[2].combination == 1


def test_bs_station_envelope_rejects_mismatched_design_grids_instead_of_interpolating() -> None:
    suite = _suite()
    suite.hb.design_stations_m = (0.0, 5.0, 10.0)

    with pytest.raises(ValueError, match="identical design-station grid"):
        build_bs5400_station_reinforcement_envelope(
            _project(),
            suite,
            girder_index=2,
            effective_depth_m=1.10,
            minimum_area_mm2=1200.0,
        )


def test_bs_station_envelope_can_drive_preliminary_curtailment_when_anchorage_is_explicit() -> None:
    envelope = build_bs5400_station_reinforcement_envelope(
        _project(),
        _suite(),
        girder_index=2,
        effective_depth_m=1.10,
        minimum_area_mm2=1200.0,
    )
    assert envelope.maximum_required_area_mm2 is not None

    arrangement = select_longitudinal_bar_arrangement(
        required_area_mm2=envelope.maximum_required_area_mm2,
        web_width_mm=400.0,
        cover_mm=40.0,
        link_diameter_mm=12.0,
        minimum_clear_spacing_mm=25.0,
        available_diameters_mm=(20.0, 25.0, 32.0),
        maximum_layers=4,
        diameter_governs_clear_spacing=False,
    )
    plan = build_bs5400_curtailment_plan_from_envelope(
        envelope,
        span_m=10.0,
        arrangement=arrangement,
        anchorage_length_mm=900.0,
    )

    assert plan.zones
    assert plan.total_bars == arrangement.bar_count
    assert any(zone.bars_to_continue < arrangement.bar_count for zone in plan.zones)
