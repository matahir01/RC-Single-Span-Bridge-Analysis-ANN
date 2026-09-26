from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rc_single_span.codes.bs5400.combinations import BS5400LimitState
from rc_single_span.codes.common import FactoredCombination, LoadEffects


class BS5400Combination4Action(str, Enum):
    """Secondary highway actions explicitly treated by BD 37/01 combination 4."""

    CENTRIFUGAL = "centrifugal"
    LONGITUDINAL_HA = "longitudinal_ha"
    LONGITUDINAL_HB = "longitudinal_hb"
    SKIDDING_HA = "skidding_ha"


@dataclass(frozen=True)
class BS5400Combination4Factors:
    action: BS5400Combination4Action
    gamma_uls: float
    gamma_sls: float
    associated_primary: str
    provenance: str

    def gamma(self, limit_state: BS5400LimitState | str) -> float:
        state = BS5400LimitState(limit_state)
        return self.gamma_uls if state is BS5400LimitState.ULS else self.gamma_sls


_COMBINATION4_FACTORS = {
    BS5400Combination4Action.CENTRIFUGAL: BS5400Combination4Factors(
        action=BS5400Combination4Action.CENTRIFUGAL,
        gamma_uls=1.50,
        gamma_sls=1.00,
        associated_primary="400 kN vertical live load over 6 m in the loaded lane",
        provenance="BD 37/01 Appendix A clauses 6.9.1-6.9.4",
    ),
    BS5400Combination4Action.LONGITUDINAL_HA: BS5400Combination4Factors(
        action=BS5400Combination4Action.LONGITUDINAL_HA,
        gamma_uls=1.25,
        gamma_sls=1.00,
        associated_primary="HA",
        provenance="BD 37/01 Appendix A clauses 6.10.1, 6.10.3-6.10.5",
    ),
    BS5400Combination4Action.LONGITUDINAL_HB: BS5400Combination4Factors(
        action=BS5400Combination4Action.LONGITUDINAL_HB,
        gamma_uls=1.10,
        gamma_sls=1.00,
        associated_primary="HB",
        provenance="BD 37/01 Appendix A clauses 6.10.2-6.10.5",
    ),
    BS5400Combination4Action.SKIDDING_HA: BS5400Combination4Factors(
        action=BS5400Combination4Action.SKIDDING_HA,
        gamma_uls=1.25,
        gamma_sls=1.00,
        associated_primary="HA",
        provenance="BD 37/01 Appendix A clauses 6.11.1-6.11.4",
    ),
}


def combination4_factors(
    action: BS5400Combination4Action | str,
) -> BS5400Combination4Factors:
    return _COMBINATION4_FACTORS[BS5400Combination4Action(action)]


def ha_longitudinal_nominal_kn(loaded_length_m: float) -> float:
    """BD 37/01 6.10.1 nominal HA traction/braking load."""

    if loaded_length_m <= 0.0:
        raise ValueError("loaded_length_m must be positive.")
    return min(8.0 * loaded_length_m + 250.0, 750.0)


def hb_longitudinal_nominal_kn(total_nominal_hb_load_kn: float) -> float:
    """BD 37/01 6.10.2 nominal HB traction/braking load."""

    if total_nominal_hb_load_kn <= 0.0:
        raise ValueError("total_nominal_hb_load_kn must be positive.")
    return 0.25 * total_nominal_hb_load_kn


def centrifugal_nominal_kn(radius_m: float) -> float:
    """BD 37/01 6.9.1 nominal centrifugal point load.

    Clause 6.9 applies to highway carriageways with radius below 1000 m. A
    straight bridge, or a curve with radius at least 1000 m, therefore returns
    zero rather than fabricating a centrifugal action.
    """

    if radius_m <= 0.0:
        raise ValueError("radius_m must be positive.")
    if radius_m >= 1000.0:
        return 0.0
    return 40000.0 / (radius_m + 150.0)


def skidding_nominal_kn() -> float:
    """BD 37/01 6.11.1 nominal accidental skidding load."""

    return 300.0


def nominal_bearing_friction_force_kn(
    *,
    nominal_vertical_load_kn: float,
    coefficient_of_friction: float,
) -> float:
    """Return the nominal combination-5 bearing-friction force magnitude.

    BD 37/01 5.4.7.3 defines the nominal action from nominal permanent vertical
    load and the applicable bearing coefficient of friction. The coefficient is
    deliberately an explicit bearing/project input.
    """

    if nominal_vertical_load_kn < 0.0:
        raise ValueError("nominal_vertical_load_kn cannot be negative.")
    if coefficient_of_friction < 0.0:
        raise ValueError("coefficient_of_friction cannot be negative.")
    return nominal_vertical_load_kn * coefficient_of_friction


def build_bs5400_combination4(
    *,
    factored_permanent: LoadEffects,
    secondary_nominal: LoadEffects,
    associated_primary_nominal: LoadEffects,
    action: BS5400Combination4Action | str,
    limit_state: BS5400LimitState | str,
    permanent_factor_audit: dict[str, float],
) -> FactoredCombination:
    """Build one BD 37/01 combination-4 secondary-live-load case.

    Secondary live loads are considered separately, each with its associated
    primary live load. The caller supplies structural effects from the
    appropriate analysis model; this function performs the code combination and
    preserves the factor audit.
    """

    action_type = BS5400Combination4Action(action)
    state = BS5400LimitState(limit_state)
    factors = combination4_factors(action_type)
    gamma_live = factors.gamma(state)
    audit = dict(permanent_factor_audit)
    audit["secondary_live"] = gamma_live
    audit["associated_primary_live"] = gamma_live
    return FactoredCombination(
        name=f"BS 5400 combination 4 {state.value.upper()} ({action_type.value})",
        effects=(
            factored_permanent
            + secondary_nominal.scaled(gamma_live)
            + associated_primary_nominal.scaled(gamma_live)
        ),
        factors=audit,
    )


def bearing_friction_gamma_fl(limit_state: BS5400LimitState | str) -> float:
    """BD 37/01 5.4.8.3 factor for combination-5 bearing friction."""

    state = BS5400LimitState(limit_state)
    return 1.30 if state is BS5400LimitState.ULS else 1.00


def build_bs5400_combination5(
    *,
    factored_permanent: LoadEffects,
    bearing_friction_nominal: LoadEffects,
    limit_state: BS5400LimitState | str,
    permanent_factor_audit: dict[str, float],
) -> FactoredCombination:
    """Build BD 37/01 combination 5: permanent effects plus bearing friction."""

    state = BS5400LimitState(limit_state)
    gamma_friction = bearing_friction_gamma_fl(state)
    audit = dict(permanent_factor_audit)
    audit["bearing_friction"] = gamma_friction
    return FactoredCombination(
        name=f"BS 5400 combination 5 {state.value.upper()} (bearing friction)",
        effects=factored_permanent + bearing_friction_nominal.scaled(gamma_friction),
        factors=audit,
    )
