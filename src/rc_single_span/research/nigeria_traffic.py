from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np


class AxleConfiguration(str, Enum):
    SAST = "single_axle_single_tyre"
    SADT = "single_axle_dual_tyre"
    TADT = "tandem_axle_dual_tyre"
    TRDT = "tridem_axle_dual_tyre"


@dataclass(frozen=True)
class EmpiricalAxleSpectrum:
    configuration: AxleConfiguration
    load_kn: tuple[float, ...]
    southbound_counts: tuple[int, ...]
    northbound_counts: tuple[int, ...]
    source: str
    site: str
    survey_note: str

    def __post_init__(self) -> None:
        if not self.load_kn:
            raise ValueError("Axle spectrum cannot be empty.")
        if not (
            len(self.load_kn)
            == len(self.southbound_counts)
            == len(self.northbound_counts)
        ):
            raise ValueError("Axle spectrum load/count vectors must have equal length.")
        if any(value < 0.0 for value in self.load_kn):
            raise ValueError("Axle loads cannot be negative.")
        if any(value < 0 for value in self.southbound_counts + self.northbound_counts):
            raise ValueError("Axle-spectrum counts cannot be negative.")
        if not self.source.strip() or not self.site.strip():
            raise ValueError("Axle-spectrum source and site are required.")

    @property
    def southbound_total(self) -> int:
        return sum(self.southbound_counts)

    @property
    def northbound_total(self) -> int:
        return sum(self.northbound_counts)

    @property
    def total_count(self) -> int:
        return self.southbound_total + self.northbound_total

    def probabilities(self, direction: str = "combined") -> np.ndarray:
        if direction == "southbound":
            counts = np.asarray(self.southbound_counts, dtype=float)
        elif direction == "northbound":
            counts = np.asarray(self.northbound_counts, dtype=float)
        elif direction == "combined":
            counts = np.asarray(self.southbound_counts, dtype=float) + np.asarray(
                self.northbound_counts, dtype=float
            )
        else:
            raise ValueError("direction must be southbound, northbound or combined.")
        total = float(np.sum(counts))
        if total <= 0.0:
            raise ValueError(f"No observations are available for {direction}.")
        return counts / total

    def mean_load_kn(self, direction: str = "combined") -> float:
        probabilities = self.probabilities(direction)
        return float(np.dot(np.asarray(self.load_kn, dtype=float), probabilities))

    def quantile_load_kn(self, probability: float, direction: str = "combined") -> float:
        if not 0.0 <= probability <= 1.0:
            raise ValueError("probability must lie in [0, 1].")
        weights = self.probabilities(direction)
        cumulative = np.cumsum(weights)
        index = int(np.searchsorted(cumulative, probability, side="left"))
        index = min(index, len(self.load_kn) - 1)
        return float(self.load_kn[index])


@dataclass(frozen=True)
class FederalRoadTrafficFlow:
    link: str
    adt_vehicles_per_day: int
    heavy_vehicles_per_day: int
    heavy_vehicle_percent: float
    source: str

    def __post_init__(self) -> None:
        if self.adt_vehicles_per_day <= 0 or self.heavy_vehicles_per_day < 0:
            raise ValueError("Traffic-flow counts must be non-negative and ADT positive.")
        if not 0.0 <= self.heavy_vehicle_percent <= 100.0:
            raise ValueError("Heavy-vehicle percentage must lie in [0, 100].")


@dataclass(frozen=True)
class NigeriaTrafficEvidence:
    spectra: tuple[EmpiricalAxleSpectrum, ...]
    federal_flows: tuple[FederalRoadTrafficFlow, ...]
    bridge_vehicle_sequence_available: bool
    bridge_calibration_note: str

    @property
    def bridge_effect_calibration_ready(self) -> bool:
        return self.bridge_vehicle_sequence_available


_AZOJETE_SOURCE = (
    "Awosanya, Murana & Olowosulu (2024), AZOJETE 20(3), 581-600, "
    "Kaduna-Zaria portable WIM axle-load spectra; "
    "https://www.azojete.com.ng/index.php/azojete/article/view/937"
)
_FMW_SOURCE = (
    "Federal Ministry of Works, Highway Manual Part 1 Design, Volume III, "
    "Appendix A Nigerian Traffic and Axle Load Study (2008 survey data); "
    "https://www.fmw.gov.ng/themes/front_end_themes_01/images/uploads_images/1569354557.pdf"
)


def _counts(values: dict[int, int], maximum: int, step: int) -> tuple[int, ...]:
    return tuple(values.get(load, 0) for load in range(0, maximum + step, step))


def kaduna_zaria_wim_spectra_2024() -> tuple[EmpiricalAxleSpectrum, ...]:
    """Digitised Table 3 axle spectra from the published Kaduna-Zaria WIM study.

    The paper provides axle-group load bins and directional frequencies, plus
    truck/axle totals. It does not publish a vehicle-by-vehicle time sequence,
    axle spacings or a full joint vehicle configuration table sufficient for a
    defensible bridge extreme-load simulation. These spectra are therefore
    evidence inputs for traffic sensitivity/calibration development, not a
    direct replacement for LM1.
    """

    loads_10 = tuple(float(value) for value in range(0, 251, 10))
    loads_20 = tuple(float(value) for value in range(0, 501, 20))
    loads_30 = tuple(float(value) for value in range(0, 751, 30))

    sast_sb = _counts(
        {10: 2, 20: 3, 30: 9, 40: 16, 50: 39, 60: 3, 70: 8, 80: 1,
         100: 2, 110: 2, 120: 1},
        250,
        10,
    )
    sast_nb = _counts(
        {10: 4, 20: 3, 30: 8, 40: 9, 50: 18, 60: 32, 70: 15, 80: 5,
         90: 2, 110: 2, 120: 1},
        250,
        10,
    )
    sadt_sb = _counts(
        {10: 1, 20: 1, 30: 8, 40: 31, 50: 10, 60: 2, 70: 1, 80: 5,
         90: 1, 100: 2, 110: 1, 120: 1, 130: 2, 140: 1, 170: 1},
        250,
        10,
    )
    sadt_nb = _counts(
        {10: 1, 20: 2, 30: 6, 40: 6, 50: 5, 70: 2, 80: 1, 90: 4,
         100: 6, 110: 6, 120: 11, 130: 9, 140: 2, 150: 3, 160: 5,
         170: 1, 180: 1, 190: 1, 200: 3, 210: 1},
        250,
        10,
    )
    tadt_sb = _counts(
        {20: 4, 40: 11, 60: 31, 80: 13, 100: 2, 120: 2, 140: 1,
         200: 3, 220: 2, 240: 2, 300: 2, 320: 1, 340: 1},
        500,
        20,
    )
    tadt_nb = _counts(
        {0: 1, 20: 1, 40: 3, 60: 6, 80: 4, 100: 6, 120: 4, 140: 2,
         160: 7, 180: 8, 200: 8, 220: 15, 240: 11, 260: 1, 280: 6,
         300: 3, 320: 1, 340: 1, 380: 2},
        500,
        20,
    )
    trdt_sb = _counts({}, 750, 30)
    trdt_nb = _counts({270: 2, 390: 1}, 750, 30)

    note = (
        "Published Table 3 directional axle-group frequency data. Bin values are "
        "digitised exactly as reported; zero-load bins are retained because the paper "
        "lists them explicitly."
    )
    return (
        EmpiricalAxleSpectrum(
            AxleConfiguration.SAST,
            loads_10,
            sast_sb,
            sast_nb,
            _AZOJETE_SOURCE,
            "Kaduna-Zaria Roadway",
            note,
        ),
        EmpiricalAxleSpectrum(
            AxleConfiguration.SADT,
            loads_10,
            sadt_sb,
            sadt_nb,
            _AZOJETE_SOURCE,
            "Kaduna-Zaria Roadway",
            note,
        ),
        EmpiricalAxleSpectrum(
            AxleConfiguration.TADT,
            loads_20,
            tadt_sb,
            tadt_nb,
            _AZOJETE_SOURCE,
            "Kaduna-Zaria Roadway",
            note,
        ),
        EmpiricalAxleSpectrum(
            AxleConfiguration.TRDT,
            loads_30,
            trdt_sb,
            trdt_nb,
            _AZOJETE_SOURCE,
            "Kaduna-Zaria Roadway",
            note,
        ),
    )


def selected_federal_road_flows_2008() -> tuple[FederalRoadTrafficFlow, ...]:
    """Selected northern/freight corridor flows from FMW Highway Manual Table A.1."""

    return (
        FederalRoadTrafficFlow("Ilorin - Jebba", 5000, 2200, 44.0, _FMW_SOURCE),
        FederalRoadTrafficFlow("Lokoja - Abuja", 9000, 900, 10.0, _FMW_SOURCE),
        FederalRoadTrafficFlow("Abuja - Kaduna", 8000, 800, 10.0, _FMW_SOURCE),
        FederalRoadTrafficFlow("Jos - Bauchi", 7000, 380, 5.0, _FMW_SOURCE),
        FederalRoadTrafficFlow("Bauchi - Yola", 4200, 370, 9.0, _FMW_SOURCE),
        FederalRoadTrafficFlow("Kaduna - Zaria", 11000, 920, 8.0, _FMW_SOURCE),
        FederalRoadTrafficFlow("Potisku - Maiduguri", 5000, 920, 18.0, _FMW_SOURCE),
        FederalRoadTrafficFlow("Maiduguri - Ngala", 3000, 1000, 33.0, _FMW_SOURCE),
    )


def nigeria_traffic_evidence() -> NigeriaTrafficEvidence:
    return NigeriaTrafficEvidence(
        spectra=kaduna_zaria_wim_spectra_2024(),
        federal_flows=selected_federal_road_flows_2008(),
        bridge_vehicle_sequence_available=False,
        bridge_calibration_note=(
            "Nigeria-specific axle spectra and federal heavy-vehicle flows are available, "
            "but the cited public sources do not provide a complete vehicle-by-vehicle joint "
            "sequence with axle spacings needed to calibrate 15 m bridge moment/shear extremes. "
            "Do not convert pavement ESAL values directly into an LM1 bridge load multiplier."
        ),
    )
