from __future__ import annotations

from dataclasses import dataclass

from rc_single_span.codes.common import FactoredCombination, LoadEffects
from rc_single_span.codes.eurocode.basis import BS_EN_1990


@dataclass(frozen=True)
class EurocodeCombinationFactors:
    gamma_g_unfavourable: float = 1.35
    gamma_g_favourable: float = 1.00
    gamma_q_traffic: float = 1.35

    def __post_init__(self) -> None:
        if self.gamma_g_unfavourable <= 0.0:
            raise ValueError("gamma_g_unfavourable must be positive.")
        if self.gamma_g_favourable < 0.0:
            raise ValueError("gamma_g_favourable cannot be negative.")
        if self.gamma_q_traffic <= 0.0:
            raise ValueError("gamma_q_traffic must be positive.")


@dataclass(frozen=True)
class EurocodeServiceabilityFactors:
    psi1_traffic: float
    psi2_traffic: float
    psi1_udl_traffic: float | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.psi1_traffic <= 1.0:
            raise ValueError("psi1_traffic must lie between 0 and 1.")
        if not 0.0 <= self.psi2_traffic <= 1.0:
            raise ValueError("psi2_traffic must lie between 0 and 1.")
        if (
            self.psi1_udl_traffic is not None
            and not 0.0 <= self.psi1_udl_traffic <= 1.0
        ):
            raise ValueError("psi1_udl_traffic must lie between 0 and 1.")

    @property
    def frequent_components_differ(self) -> bool:
        return (
            self.psi1_udl_traffic is not None
            and self.psi1_udl_traffic != self.psi1_traffic
        )


@dataclass(frozen=True)
class EurocodeCombinationSet:
    permanent_characteristic: LoadEffects
    traffic_characteristic: LoadEffects
    persistent_uls: FactoredCombination
    characteristic_sls: FactoredCombination
    frequent_sls: FactoredCombination
    quasi_permanent_sls: FactoredCombination


def persistent_uls_split_permanent(
    permanent_unfavourable: LoadEffects,
    permanent_favourable: LoadEffects,
    traffic: LoadEffects,
    factors: EurocodeCombinationFactors | None = None,
) -> FactoredCombination:
    """Build BS EN 1990 persistent ULS with explicit Gsup/Ginf effects.

    ``permanent_favourable`` must retain its physical response sign. For
    example, a stabilising -20 kNm contribution remains negative and is scaled
    by ``gamma_g_favourable``; it is not converted to a positive magnitude.

    The V1 longitudinal gravity bridge path has only downward permanent actions
    for its positive sagging/shear design envelopes, so it normally passes all
    permanent response through ``permanent_unfavourable``. This split helper
    prevents that simplification from becoming a hidden general-code rule.
    """

    current = factors or EurocodeCombinationFactors()
    return FactoredCombination(
        name=f"{BS_EN_1990} persistent ULS",
        effects=(
            permanent_unfavourable.scaled(current.gamma_g_unfavourable)
            + permanent_favourable.scaled(current.gamma_g_favourable)
            + traffic.scaled(current.gamma_q_traffic)
        ),
        factors={
            "G_unfavourable": current.gamma_g_unfavourable,
            "G_favourable": current.gamma_g_favourable,
            "Q_traffic": current.gamma_q_traffic,
        },
    )


def persistent_uls(
    permanent: LoadEffects,
    traffic: LoadEffects,
    factors: EurocodeCombinationFactors | None = None,
) -> FactoredCombination:
    """Build the V1 gravity-bridge persistent ULS envelope.

    For the current simply supported longitudinal girder path the supplied
    permanent envelope is an unfavourable gravity effect. Use
    :func:`persistent_uls_split_permanent` when a verification contains both
    favourable and unfavourable permanent response components.
    """

    current = factors or EurocodeCombinationFactors()
    split = persistent_uls_split_permanent(
        permanent,
        LoadEffects(),
        traffic,
        current,
    )
    # Keep the established V1 audit schema stable for the all-unfavourable
    # gravity envelope while exposing Gsup/Ginf explicitly through the split
    # helper for verifications that require both signs.
    return FactoredCombination(
        name=split.name,
        effects=split.effects,
        factors={
            "G": current.gamma_g_unfavourable,
            "Q_traffic": current.gamma_q_traffic,
        },
    )


def characteristic_sls(
    permanent: LoadEffects,
    traffic: LoadEffects,
) -> FactoredCombination:
    return FactoredCombination(
        name=f"{BS_EN_1990} characteristic SLS",
        effects=permanent + traffic,
        factors={"G": 1.0, "Q_traffic": 1.0},
    )


def frequent_sls(
    permanent: LoadEffects,
    traffic: LoadEffects,
    factors: EurocodeServiceabilityFactors,
) -> FactoredCombination:
    if factors.frequent_components_differ:
        raise ValueError(
            "Distinct tandem and UDL frequent factors require a separately "
            "weighted LM1 search."
        )
    return FactoredCombination(
        name=f"{BS_EN_1990} frequent SLS",
        effects=permanent + traffic.scaled(factors.psi1_traffic),
        factors={"G": 1.0, "Q_traffic": factors.psi1_traffic},
    )


def quasi_permanent_sls(
    permanent: LoadEffects,
    traffic: LoadEffects,
    factors: EurocodeServiceabilityFactors,
) -> FactoredCombination:
    return FactoredCombination(
        name=f"{BS_EN_1990} quasi-permanent SLS",
        effects=permanent + traffic.scaled(factors.psi2_traffic),
        factors={"G": 1.0, "Q_traffic": factors.psi2_traffic},
    )


def build_eurocode_combination_set(
    permanent: LoadEffects,
    traffic: LoadEffects,
    *,
    sls_factors: EurocodeServiceabilityFactors,
    uls_factors: EurocodeCombinationFactors | None = None,
) -> EurocodeCombinationSet:
    return EurocodeCombinationSet(
        permanent_characteristic=permanent,
        traffic_characteristic=traffic,
        persistent_uls=persistent_uls(permanent, traffic, uls_factors),
        characteristic_sls=characteristic_sls(permanent, traffic),
        frequent_sls=frequent_sls(permanent, traffic, sls_factors),
        quasi_permanent_sls=quasi_permanent_sls(
            permanent,
            traffic,
            sls_factors,
        ),
    )
