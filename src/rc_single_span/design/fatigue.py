from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReinforcementFatigueEquivalentRange:
    flm3_stress_range_mpa: float
    fatigue_load_multiplier: float
    damage_coefficient: float
    amplified_stress_range_mpa: float
    equivalent_stress_range_mpa: float
    provenance: str


@dataclass(frozen=True)
class ReinforcementFatigueResult:
    equivalent_stress_range_mpa: float
    design_action_stress_range_mpa: float
    characteristic_resistance_range_mpa: float
    design_resistance_range_mpa: float
    gamma_fatigue_action: float
    gamma_fatigue_resistance: float
    resistance_modifier: float
    utilization: float
    margin_mpa: float
    passes: bool
    provenance: str


def equivalent_reinforcement_stress_range_from_flm3(
    *,
    flm3_stress_range_mpa: float,
    fatigue_load_multiplier: float,
    damage_coefficient: float,
    provenance: str,
) -> ReinforcementFatigueEquivalentRange:
    """Convert an FLM3 reinforcement range to a damage-equivalent range.

    For the first-generation BS EN 1992-2 Annex NN method this represents
    Delta_sigma_s,eq = Delta_sigma_s,Ec * lambda_s.  The traffic multiplier
    (for example 1.4 away from intermediate supports in the JRC bridge example)
    and the damage coefficient are deliberately explicit: this routine does not
    infer traffic volume, pavement roughness, influence length or lane factors.
    """

    if min(
        flm3_stress_range_mpa,
        fatigue_load_multiplier,
        damage_coefficient,
    ) <= 0.0:
        raise ValueError("Fatigue equivalent-range inputs must be positive.")
    if not provenance.strip():
        raise ValueError("Fatigue equivalent-range provenance is required.")

    amplified = fatigue_load_multiplier * flm3_stress_range_mpa
    equivalent = damage_coefficient * amplified
    return ReinforcementFatigueEquivalentRange(
        flm3_stress_range_mpa=flm3_stress_range_mpa,
        fatigue_load_multiplier=fatigue_load_multiplier,
        damage_coefficient=damage_coefficient,
        amplified_stress_range_mpa=amplified,
        equivalent_stress_range_mpa=equivalent,
        provenance=provenance,
    )


def check_reinforcement_fatigue_stress_range(
    *,
    equivalent_stress_range_mpa: float,
    characteristic_resistance_range_mpa: float,
    gamma_fatigue_action: float = 1.0,
    gamma_fatigue_resistance: float = 1.15,
    resistance_modifier: float = 1.0,
    provenance: str,
) -> ReinforcementFatigueResult:
    """Check a reinforcement fatigue stress range from explicit inputs.

    This routine intentionally does not invent the traffic fatigue model,
    equivalent-cycle factor, bar/detail category or S-N resistance. Those must
    be supplied by the applicable bridge-code loading/detailing path. Once the
    equivalent stress range and characteristic resistance are known, the check
    is transparent::

        gamma_F,fat * Delta_sigma_E,eq <=
        resistance_modifier * Delta_sigma_R,sk / gamma_M,fat
    """

    if min(
        equivalent_stress_range_mpa,
        characteristic_resistance_range_mpa,
        gamma_fatigue_action,
        gamma_fatigue_resistance,
        resistance_modifier,
    ) <= 0.0:
        raise ValueError("Fatigue stress-range inputs must be positive.")
    if not provenance.strip():
        raise ValueError("Fatigue provenance is required.")

    action = gamma_fatigue_action * equivalent_stress_range_mpa
    resistance = (
        resistance_modifier
        * characteristic_resistance_range_mpa
        / gamma_fatigue_resistance
    )
    utilization = action / resistance
    margin = resistance - action
    return ReinforcementFatigueResult(
        equivalent_stress_range_mpa=equivalent_stress_range_mpa,
        design_action_stress_range_mpa=action,
        characteristic_resistance_range_mpa=characteristic_resistance_range_mpa,
        design_resistance_range_mpa=resistance,
        gamma_fatigue_action=gamma_fatigue_action,
        gamma_fatigue_resistance=gamma_fatigue_resistance,
        resistance_modifier=resistance_modifier,
        utilization=utilization,
        margin_mpa=margin,
        passes=margin >= -1.0e-12,
        provenance=provenance,
    )
