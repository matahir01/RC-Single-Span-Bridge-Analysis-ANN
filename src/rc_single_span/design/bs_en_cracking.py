from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BSEnCrackFormulaResult:
    effective_reinforcement_ratio: float
    steel_stress_mpa: float
    mean_strain_difference: float
    maximum_crack_spacing_mm: float
    crack_width_mm: float


def bs_en_crack_width_from_steel_stress(
    *,
    steel_stress_mpa: float,
    effective_reinforcement_ratio: float,
    bar_diameter_mm: float,
    cover_mm: float,
    es_mpa: float,
    modular_ratio: float,
    fct_eff_mpa: float,
    kt: float,
    k1: float = 0.8,
    k2: float = 0.5,
    k3: float = 3.4,
    k4: float = 0.425,
) -> BSEnCrackFormulaResult:
    """Evaluate the close-spacing BS EN 1992 crack-width expression.

    The caller supplies the cracked-section steel stress and effective
    reinforcement ratio. This deliberately separates the source-checkable
    crack-spacing/mean-strain formula from the section-analysis step used to
    obtain those quantities.
    """

    positive = (
        steel_stress_mpa,
        effective_reinforcement_ratio,
        bar_diameter_mm,
        cover_mm,
        es_mpa,
        modular_ratio,
        fct_eff_mpa,
        kt,
        k1,
        k2,
        k3,
        k4,
    )
    if any(value <= 0.0 for value in positive):
        raise ValueError("BS EN crack-formula inputs must be positive.")

    rho = effective_reinforcement_ratio
    strain_calculated = (
        steel_stress_mpa
        - kt * fct_eff_mpa / rho * (1.0 + modular_ratio * rho)
    ) / es_mpa
    strain_minimum = 0.6 * steel_stress_mpa / es_mpa
    strain_difference = max(strain_calculated, strain_minimum, 0.0)
    maximum_spacing = (
        k3 * cover_mm
        + k1 * k2 * k4 * bar_diameter_mm / rho
    )
    crack_width = maximum_spacing * strain_difference

    return BSEnCrackFormulaResult(
        effective_reinforcement_ratio=rho,
        steel_stress_mpa=steel_stress_mpa,
        mean_strain_difference=strain_difference,
        maximum_crack_spacing_mm=maximum_spacing,
        crack_width_mm=crack_width,
    )
