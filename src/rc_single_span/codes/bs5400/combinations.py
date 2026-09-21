from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rc_single_span.codes.bs5400.traffic import ha_hb_coexistent_gamma_fl
from rc_single_span.codes.common import FactoredCombination, LoadEffects


class BS5400LimitState(str, Enum):
    ULS = "uls"
    SLS = "sls"


class BS5400PrimaryTraffic(str, Enum):
    HA = "ha"
    HB = "hb"
    HA_HB = "ha_hb"


@dataclass(frozen=True)
class BS5400PermanentGammaFL:
    """BD 37/01 / composite BS 5400:Part 2 permanent-load factors."""

    concrete_dead_uls: float = 1.15
    concrete_dead_sls: float = 1.00
    surfacing_uls: float = 1.75
    surfacing_sls: float = 1.20
    other_superimposed_uls: float = 1.20
    other_superimposed_sls: float = 1.00

    def __post_init__(self) -> None:
        if min(
            self.concrete_dead_uls,
            self.concrete_dead_sls,
            self.surfacing_uls,
            self.surfacing_sls,
            self.other_superimposed_uls,
            self.other_superimposed_sls,
        ) <= 0.0:
            raise ValueError("BS 5400 permanent gamma_fL values must be positive.")

    def as_named_factors(
        self,
        limit_state: BS5400LimitState | str,
    ) -> dict[str, float]:
        state = BS5400LimitState(limit_state)
        if state is BS5400LimitState.ULS:
            return {
                "structural_dead": self.concrete_dead_uls,
                "surfacing": self.surfacing_uls,
                "other_superimposed": self.other_superimposed_uls,
            }
        return {
            "structural_dead": self.concrete_dead_sls,
            "surfacing": self.surfacing_sls,
            "other_superimposed": self.other_superimposed_sls,
        }


def primary_live_gamma_fl(
    *,
    traffic: BS5400PrimaryTraffic | str,
    combination: int,
    limit_state: BS5400LimitState | str,
) -> float:
    """Return primary highway live-load gamma_fL for combinations 1-3."""

    if combination not in (1, 2, 3):
        raise ValueError("Primary highway traffic combinations are implemented for 1-3 only.")
    traffic_case = BS5400PrimaryTraffic(traffic)
    state = BS5400LimitState(limit_state)

    if traffic_case in (BS5400PrimaryTraffic.HB, BS5400PrimaryTraffic.HA_HB):
        return ha_hb_coexistent_gamma_fl(
            combination=combination,
            limit_state=state.value,
        )

    if state is BS5400LimitState.ULS:
        return 1.50 if combination == 1 else 1.25
    return 1.20 if combination == 1 else 1.00


def build_bs5400_primary_combination(
    *,
    factored_permanent: LoadEffects,
    traffic_nominal: LoadEffects,
    traffic: BS5400PrimaryTraffic | str,
    combination: int,
    limit_state: BS5400LimitState | str,
    permanent_factor_audit: dict[str, float],
) -> FactoredCombination:
    """Combine already-factor-resolved permanent effects with one traffic envelope."""

    traffic_case = BS5400PrimaryTraffic(traffic)
    state = BS5400LimitState(limit_state)
    gamma_live = primary_live_gamma_fl(
        traffic=traffic_case,
        combination=combination,
        limit_state=state,
    )
    factors = dict(permanent_factor_audit)
    factors["primary_live"] = gamma_live
    return FactoredCombination(
        name=(
            f"BS 5400 combination {combination} {state.value.upper()} "
            f"({traffic_case.value})"
        ),
        effects=factored_permanent + traffic_nominal.scaled(gamma_live),
        factors=factors,
    )
