import numpy as np
import pytest

from rc_single_span.research.nigeria_traffic import (
    AxleConfiguration,
    kaduna_zaria_wim_spectra_2024,
    nigeria_traffic_evidence,
    selected_federal_road_flows_2008,
)


def test_kaduna_zaria_digitised_axle_totals_match_published_table() -> None:
    spectra = {item.configuration: item for item in kaduna_zaria_wim_spectra_2024()}
    assert spectra[AxleConfiguration.SAST].southbound_total == 86
    assert spectra[AxleConfiguration.SAST].northbound_total == 99
    assert spectra[AxleConfiguration.SADT].southbound_total == 68
    assert spectra[AxleConfiguration.SADT].northbound_total == 76
    assert spectra[AxleConfiguration.TADT].southbound_total == 75
    assert spectra[AxleConfiguration.TADT].northbound_total == 90
    assert spectra[AxleConfiguration.TRDT].southbound_total == 0
    assert spectra[AxleConfiguration.TRDT].northbound_total == 3


def test_axle_spectrum_probabilities_normalise_and_preserve_heavy_tail() -> None:
    spectra = {item.configuration: item for item in kaduna_zaria_wim_spectra_2024()}
    sadt = spectra[AxleConfiguration.SADT]
    tadt = spectra[AxleConfiguration.TADT]
    assert np.sum(sadt.probabilities("northbound")) == pytest.approx(1.0)
    assert np.sum(tadt.probabilities("combined")) == pytest.approx(1.0)
    assert sadt.quantile_load_kn(0.95, "northbound") >= 160.0
    assert tadt.quantile_load_kn(0.95, "northbound") >= 280.0


def test_empty_direction_is_not_silently_interpreted_as_zero_load_distribution() -> None:
    tridem = next(
        item
        for item in kaduna_zaria_wim_spectra_2024()
        if item.configuration is AxleConfiguration.TRDT
    )
    with pytest.raises(ValueError, match="No observations"):
        tridem.probabilities("southbound")
    assert tridem.quantile_load_kn(0.50, "northbound") == pytest.approx(270.0)


def test_selected_federal_flows_match_manual_values() -> None:
    flows = {item.link: item for item in selected_federal_road_flows_2008()}
    assert flows["Bauchi - Yola"].adt_vehicles_per_day == 4200
    assert flows["Bauchi - Yola"].heavy_vehicles_per_day == 370
    assert flows["Bauchi - Yola"].heavy_vehicle_percent == pytest.approx(9.0)
    assert flows["Ilorin - Jebba"].heavy_vehicle_percent == pytest.approx(44.0)
    assert flows["Maiduguri - Ngala"].heavy_vehicle_percent == pytest.approx(33.0)


def test_public_nigeria_evidence_is_not_mislabelled_bridge_calibration_ready() -> None:
    evidence = nigeria_traffic_evidence()
    assert not evidence.bridge_effect_calibration_ready
    assert "Do not convert pavement ESAL" in evidence.bridge_calibration_note
