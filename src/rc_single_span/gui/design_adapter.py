from __future__ import annotations

from dataclasses import dataclass

from rc_single_span.design.project import (
    BS5400DesignInputs,
    EC2DesignInputs,
    EurocodeSLSBasis,
)
from rc_single_span.gui.engine_adapter import GuiCodeProfile


@dataclass(frozen=True)
class GuiDesignInputs:
    """Explicit code-specific design inputs collected by the desktop GUI.

    These are deliberately separate from the bridge geometry/material model.
    Values such as crack and deflection limits are project/design-basis inputs,
    not universal defaults injected by the deterministic engine.
    """

    enabled: bool = False
    effective_depth_m: float = 1.10
    bar_diameter_mm: float = 32.0
    bar_spacing_mm: float = 90.0

    ec2_cover_mm: float = 50.0
    ec2_fct_eff_mpa: float = 3.2
    ec2_crack_limit_mm: float = 0.30
    ec2_maximum_neutral_axis_ratio: float = 0.45
    ec2_sls_basis: str = EurocodeSLSBasis.CHARACTERISTIC.value
    ec2_alpha_cc: float = 1.0

    bs_nominal_cover_mm: float = 50.0
    bs_crack_point_depth_mm: float = 1200.0
    bs_allowable_crack_width_mm: float = 0.25
    bs_ec_modified_mpa: float = 34000.0
    bs_shear_reinforcement_fyv_mpa: float = 460.0

    deflection_limit_mm: float | None = None
    deflection_limit_basis: str | None = None

    def __post_init__(self) -> None:
        positive = (
            self.effective_depth_m,
            self.bar_diameter_mm,
            self.bar_spacing_mm,
            self.ec2_cover_mm,
            self.ec2_fct_eff_mpa,
            self.ec2_crack_limit_mm,
            self.ec2_maximum_neutral_axis_ratio,
            self.ec2_alpha_cc,
            self.bs_nominal_cover_mm,
            self.bs_crack_point_depth_mm,
            self.bs_allowable_crack_width_mm,
            self.bs_ec_modified_mpa,
            self.bs_shear_reinforcement_fyv_mpa,
        )
        if any(value <= 0.0 for value in positive):
            raise ValueError("GUI design inputs must be positive.")
        if self.deflection_limit_mm is None and self.deflection_limit_basis is not None:
            raise ValueError("A deflection basis requires an explicit deflection limit.")
        if self.deflection_limit_mm is not None and self.deflection_limit_mm <= 0.0:
            raise ValueError("Deflection limit must be positive when supplied.")
        if self.deflection_limit_basis is not None and not self.deflection_limit_basis.strip():
            raise ValueError("Deflection basis must be non-empty when supplied.")

    def for_profile(self, profile: GuiCodeProfile):
        if not self.enabled:
            return None
        if profile is GuiCodeProfile.BS_EN:
            return EC2DesignInputs(
                effective_depth_m=self.effective_depth_m,
                bar_diameter_mm=self.bar_diameter_mm,
                bar_spacing_mm=self.bar_spacing_mm,
                cover_mm=self.ec2_cover_mm,
                fct_eff_mpa=self.ec2_fct_eff_mpa,
                crack_limit_mm=self.ec2_crack_limit_mm,
                maximum_neutral_axis_ratio=self.ec2_maximum_neutral_axis_ratio,
                deflection_limit_mm=self.deflection_limit_mm,
                deflection_limit_basis=self.deflection_limit_basis,
                sls_basis=EurocodeSLSBasis(self.ec2_sls_basis),
                alpha_cc=self.ec2_alpha_cc,
            )
        return BS5400DesignInputs(
            effective_depth_m=self.effective_depth_m,
            bar_diameter_mm=self.bar_diameter_mm,
            bar_spacing_mm=self.bar_spacing_mm,
            nominal_cover_mm=self.bs_nominal_cover_mm,
            crack_point_depth_mm=self.bs_crack_point_depth_mm,
            allowable_crack_width_mm=self.bs_allowable_crack_width_mm,
            ec_modified_mpa=self.bs_ec_modified_mpa,
            shear_reinforcement_fyv_mpa=self.bs_shear_reinforcement_fyv_mpa,
            deflection_limit_mm=self.deflection_limit_mm,
            deflection_limit_basis=self.deflection_limit_basis,
        )
