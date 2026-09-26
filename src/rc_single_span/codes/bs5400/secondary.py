from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rc_single_span.codes.bs5400.combinations import BS5400LimitState
from rc_single_span.codes.common import FactoredCombination, LoadEffects


class BS5400Combination4Action(str, Enum):
    """Common highway secondary actions explicitly treated by BD 37/01."""

    CENTRIFUGAL = "centrifugal"
    LONGITUDINAL_HA = "longitudinal_ha"
    LONGITUDINAL_HB = "longitudinal_hb"
    SKIDDING_HA = "skidding_ha"


@dataclass(frozen=True)
class BS5400Combination4Factors:
    """Factors for one combination-4 secondary action and its primary action.

    Some BD 37/01 secondary actions use a different factor for the associated
    primary live load (for example parapet collision).  The separate primary
    fields make those cases representable without forcing an incorrect shared
    factor.  For centrifugal, longitudinal and skidding actions the two sets are
    identical and are source-pinned below.
    """

    action_name: str
    gamma_uls: float
    gamma_sls: float
    associated_primary: str
    provenance: str
    primary_gamma_uls: float | None = None
    primary_gamma_sls: float | None = None

    def __post_init__(self) -> None:
        values = (self.gamma_uls, self.gamma_sls)
        if any(value <= 0.0 for value in values):
            raise ValueError("Combination-4 secondary gamma_fL values must be positive.")
        if self.primary_gamma_uls is not None and self.primary_gamma_uls <= 0.0:
            raise ValueError("primary_gamma_uls must be positive when supplied.")
        if self.primary_gamma_sls is not None and self.primary_gamma_sls <= 0.0:
            raise ValueError("primary_gamma_sls must be positive when supplied.")
        if not self.action_name.strip() or not self.provenance.strip():
            raise ValueError("Combination-4 action name and provenance are required.")

    def gamma(self, limit_state: BS5400LimitState | str) -> float:
        state = BS5400LimitState(limit_state)
        return self.gamma_uls if state is BS5400LimitState.ULS else self.gamma_sls

    def primary_gamma(self, limit_state: BS5400LimitState | str) -> float:
        state = BS5400LimitState(limit_state)
        if state is BS5400LimitState.ULS:
            return self.gamma_uls if self.primary_gamma_uls is None else self.primary_gamma_uls
        return self.gamma_sls if self.primary_gamma_sls is None else self.primary_gamma_sls


_COMBINATION4_FACTORS = {
    BS5400Combination4Action.CENTRIFUGAL: BS5400Combination4Factors(
        action_name=BS5400Combination4Action.CENTRIFUGAL.value,
        gamma_uls=1.50,
        gamma_sls=1.00,
        associated_primary="400 kN vertical live load over 6 m in the loaded lane",
        provenance="BD 37/01 Appendix A clauses 6.9.1-6.9.4",
    ),
    BS5400Combination4Action.LONGITUDINAL_HA: BS5400Combination4Factors(
        action_name=BS5400Combination4Action.LONGITUDINAL_HA.value,
        gamma_uls=1.25,
        gamma_sls=1.00,
        associated_primary="HA",
        provenance="BD 37/01 Appendix A clauses 6.10.1, 6.10.3-6.10.5",
    ),
    BS5400Combination4Action.LONGITUDINAL_HB: BS5400Combination4Factors(
        action_name=BS5400Combination4Action.LONGITUDINAL_HB.value,
        gamma_uls=1.10,
        gamma_sls=1.00,
        associated_primary="HB",
        provenance="BD 37/01 Appendix A clauses 6.10.2-6.10.5",
    ),
    BS5400Combination4Action.SKIDDING_HA: BS5400Combination4Factors(
        action_name=BS5400Combination4Action.SKIDDING_HA.value,
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


def custom_combination4_factors(
    *,
    action_name: str,
    secondary_gamma_uls: float,
    secondary_gamma_sls: float,
    associated_primary: str,
    primary_gamma_uls: float,
    primary_gamma_sls: float,
    provenance: str,
) -> BS5400Combination4Factors:
    """Create an auditable factor set for a classified combination-4 action.

    This is intended for actions whose factors depend on the project/element
    classification, such as parapet collision/global effects.  The caller must
    provide the adopted factors and source rather than the software guessing the
    containment level, structural mass class or bearing type.
    """

    return BS5400Combination4Factors(
        action_name=action_name,
        gamma_uls=secondary_gamma_uls,
        gamma_sls=secondary_gamma_sls,
        associated_primary=associated_primary,
        provenance=provenance,
        primary_gamma_uls=primary_gamma_uls,
        primary_gamma_sls=primary_gamma_sls,
    )


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

    BD 37/01 5.4.7.3 derives the nominal action from nominal permanent vertical
    load and the applicable bearing coefficient of friction.  The coefficient
    is deliberately an explicit bearing/project input.
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
    action: BS5400Combination4Action | str | None = None,
    limit_state: BS5400LimitState | str,
    permanent_factor_audit: dict[str, float],
    factors_override: BS5400Combination4Factors | None = None,
) -> FactoredCombination:
    """Build one BD 37/01 combination-4 secondary-live-load case.

    Secondary live loads are considered separately with their associated
    primary live load.  Structural effects must come from an analysis model
    appropriate to the action.  ``factors_override`` covers classified actions
    (for example parapet collision) whose factors cannot safely be inferred from
    bridge geometry alone.
    """

    if (action is None) == (factors_override is None):
        raise ValueError("Supply exactly one of action or factors_override.")
    factors = (
        factors_override
        if factors_override is not None
        else combination4_factors(BS5400Combination4Action(action))
    )
    state = BS5400LimitState(limit_state)
    gamma_secondary = factors.gamma(state)
    gamma_primary = factors.primary_gamma(state)
    audit = dict(permanent_factor_audit)
    audit["secondary_live"] = gamma_secondary
    audit["associated_primary_live"] = gamma_primary
    return FactoredCombination(
        name=f"BS 5400 combination 4 {state.value.upper()} ({factors.action_name})",
        effects=(
            factored_permanent
            + secondary_nominal.scaled(gamma_secondary)
            + associated_primary_nominal.scaled(gamma_primary)
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
