from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from rc_single_span.analysis.sections import (
    final_composite_concrete_layers,
    final_composite_girder_properties,
)
from rc_single_span.core.models import IGirderProfile, RectangularGirderProfile, TGirderProfile
from rc_single_span.design.eurocode import check_layered_flexure_ec2, check_shear_ec2
from rc_single_span.research.baseline import BSENReliabilityBaseline


FEATURE_NAMES = (
    "fck_mpa",
    "fyk_mpa",
    "effective_depth_m",
    "web_width_m",
    "steel_area_mm2",
    "dead_load_factor",
    "live_load_factor",
)

TARGET_NAMES = (
    "g_flexure_knm",
    "g_shear_kn",
    "g_deflection_mm",
)


@dataclass(frozen=True)
class ReliabilityModelConfig:
    """Explicit physical-limit-state assumptions for research sampling.

    Partial factors default to 1.0 because the stochastic strengths and actions
    represent physical random variables rather than code-design values. Set
    different values only when the research methodology deliberately defines a
    different resistance model.
    """

    deflection_limit_mm: float
    gamma_c: float = 1.0
    gamma_s: float = 1.0
    alpha_cc: float = 1.0
    cot_theta: float = 2.0
    z_factor: float = 0.9
    provided_asw_per_s_mm2_per_m: float | None = None
    scale_deflection_by_gross_iy: bool = True

    def __post_init__(self) -> None:
        if self.deflection_limit_mm <= 0.0:
            raise ValueError("deflection_limit_mm must be positive.")
        if min(self.gamma_c, self.gamma_s, self.alpha_cc, self.z_factor) <= 0.0:
            raise ValueError("Resistance-model factors must be positive.")
        if not 1.0 <= self.cot_theta <= 2.5:
            raise ValueError("cot_theta must lie between 1.0 and 2.5.")
        if (
            self.provided_asw_per_s_mm2_per_m is not None
            and self.provided_asw_per_s_mm2_per_m <= 0.0
        ):
            raise ValueError("provided_asw_per_s_mm2_per_m must be positive when supplied.")


@dataclass(frozen=True)
class LimitStateEvaluation:
    valid: bool
    values: dict[str, float]
    message: str = ""

    def target_vector(
        self,
        target_names: tuple[str, ...] = TARGET_NAMES,
    ) -> tuple[float, ...]:
        if not self.valid:
            raise ValueError(self.message or "Cannot read targets from an invalid evaluation.")
        return tuple(float(self.values[name]) for name in target_names)


def _geometry_with_web_width(baseline: BSENReliabilityBaseline, width_m: float):
    geometry = baseline.project.geometry
    profile = geometry.girder_profile
    if isinstance(profile, RectangularGirderProfile):
        updated = profile.model_copy(update={"width_m": width_m})
    elif isinstance(profile, (TGirderProfile, IGirderProfile)):
        updated = profile.model_copy(update={"web_width_m": width_m})
    else:  # pragma: no cover - guarded by the core model union
        raise TypeError("Unsupported girder profile for reliability width variation.")
    updated = type(profile).model_validate(updated.model_dump())
    return geometry.model_copy(update={"girder_profile": updated})


class BridgeLimitStateEvaluator:
    """Fast stochastic evaluator tied to a verified deterministic action baseline.

    The expensive traffic placement/distribution search is performed once in the
    deterministic baseline. Each stochastic sample then varies resistance
    variables and scales permanent/live action components. Web-width uncertainty
    also updates the final composite section inertia used for the elastic
    deflection scaling. This is intentionally a response-separation approximation,
    not a claim that every sampled bridge has been re-analysed as a new grillage.
    """

    feature_names = FEATURE_NAMES
    target_names = TARGET_NAMES

    def __init__(
        self,
        baseline: BSENReliabilityBaseline,
        config: ReliabilityModelConfig,
    ) -> None:
        self.baseline = baseline
        self.config = config

    def evaluate(self, sample: Mapping[str, float]) -> LimitStateEvaluation:
        missing = tuple(name for name in self.feature_names if name not in sample)
        if missing:
            return LimitStateEvaluation(False, {}, f"Missing sample variables: {missing}")

        values = {name: float(sample[name]) for name in self.feature_names}
        if any(value <= 0.0 for value in values.values()):
            return LimitStateEvaluation(
                False,
                {},
                "All reliability sample variables must be positive.",
            )

        fck = values["fck_mpa"]
        fyk = values["fyk_mpa"]
        depth = values["effective_depth_m"]
        width = values["web_width_m"]
        steel_area = values["steel_area_mm2"]
        dead_factor = values["dead_load_factor"]
        live_factor = values["live_load_factor"]

        try:
            geometry = _geometry_with_web_width(self.baseline, width)
            total_depth = float(geometry.total_structural_depth_m)
            if depth >= total_depth:
                raise ValueError(
                    "Sampled effective depth must remain inside the final composite section."
                )

            moment_layers = final_composite_concrete_layers(
                geometry,
                girder_index=self.baseline.moment_girder_index,
            )
            moment_effect = (
                dead_factor * self.baseline.permanent_moment_knm
                + live_factor * self.baseline.traffic_moment_knm
            )
            flexure = check_layered_flexure_ec2(
                med_knm=moment_effect,
                layers=moment_layers,
                effective_depth_m=depth,
                steel_area_mm2=steel_area,
                fck_mpa=fck,
                fyk_mpa=fyk,
                gamma_c=self.config.gamma_c,
                gamma_s=self.config.gamma_s,
                alpha_cc=self.config.alpha_cc,
            )

            shear_effect = (
                dead_factor * self.baseline.permanent_shear_kn
                + live_factor * self.baseline.traffic_shear_kn
            )
            shear = check_shear_ec2(
                ved_kn=shear_effect,
                web_width_m=width,
                effective_depth_m=depth,
                longitudinal_steel_area_mm2=steel_area,
                fck_mpa=fck,
                fyk_mpa=fyk,
                gamma_c=self.config.gamma_c,
                gamma_s=self.config.gamma_s,
                alpha_cc=self.config.alpha_cc,
                cot_theta=self.config.cot_theta,
                z_factor=self.config.z_factor,
            )
            if self.config.provided_asw_per_s_mm2_per_m is None:
                shear_resistance = min(shear.vrdc_kn, shear.vrdmax_kn)
                shear_basis = 0.0
            else:
                asw_per_s_mm2_per_mm = (
                    self.config.provided_asw_per_s_mm2_per_m / 1000.0
                )
                z_mm = self.config.z_factor * depth * 1000.0
                fywd = fyk / self.config.gamma_s
                vrds_kn = (
                    asw_per_s_mm2_per_mm
                    * z_mm
                    * fywd
                    * self.config.cot_theta
                    / 1000.0
                )
                shear_resistance = min(vrds_kn, shear.vrdmax_kn)
                shear_basis = vrds_kn

            if self.config.scale_deflection_by_gross_iy:
                sampled_iy = final_composite_girder_properties(
                    geometry,
                    girder_index=self.baseline.deflection_girder_index,
                ).iy_m4
                stiffness_scale = self.baseline.nominal_deflection_iy_m4 / sampled_iy
            else:
                sampled_iy = self.baseline.nominal_deflection_iy_m4
                stiffness_scale = 1.0
            deflection = stiffness_scale * (
                dead_factor * self.baseline.permanent_deflection_mm
                + live_factor * self.baseline.traffic_deflection_mm
            )

            output = {
                **values,
                "moment_effect_knm": moment_effect,
                "moment_resistance_knm": flexure.resistance_knm,
                "g_flexure_knm": flexure.resistance_knm - moment_effect,
                "shear_effect_kn": shear_effect,
                "shear_resistance_kn": shear_resistance,
                "shear_concrete_resistance_kn": shear.vrdc_kn,
                "shear_link_resistance_kn": shear_basis,
                "shear_crushing_resistance_kn": shear.vrdmax_kn,
                "g_shear_kn": shear_resistance - shear_effect,
                "sampled_gross_iy_m4": sampled_iy,
                "deflection_stiffness_scale": stiffness_scale,
                "deflection_mm": deflection,
                "g_deflection_mm": self.config.deflection_limit_mm - deflection,
            }
            return LimitStateEvaluation(True, output)
        except (ValueError, TypeError, ZeroDivisionError) as exc:
            return LimitStateEvaluation(False, {}, str(exc))
