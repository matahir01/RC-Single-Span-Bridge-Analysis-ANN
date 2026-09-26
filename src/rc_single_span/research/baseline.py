from __future__ import annotations

from dataclasses import dataclass

from rc_single_span.analysis.sections import final_composite_girder_properties
from rc_single_span.core.models import BridgeProject
from rc_single_span.verification.reference_runner import ReferenceRunResult


@dataclass(frozen=True)
class BSENReliabilityBaseline:
    """Verified deterministic action baseline for reliability sampling.

    The baseline separates characteristic permanent and traffic effects before
    uncertainty is introduced. Resistance variables are then varied sample by
    sample, while load-model variables scale the verified nominal action
    components. This avoids re-running the expensive traffic placement search for
    every Monte-Carlo/LHS point and makes the approximation explicit.
    """

    project: BridgeProject
    moment_girder_index: int
    shear_girder_index: int
    deflection_girder_index: int
    permanent_moment_knm: float
    traffic_moment_knm: float
    permanent_shear_kn: float
    traffic_shear_kn: float
    permanent_deflection_mm: float
    traffic_deflection_mm: float
    nominal_deflection_iy_m4: float
    provenance: str

    def __post_init__(self) -> None:
        if min(
            self.moment_girder_index,
            self.shear_girder_index,
            self.deflection_girder_index,
        ) <= 0:
            raise ValueError("Baseline girder indices must be positive.")
        if min(
            self.permanent_moment_knm,
            self.traffic_moment_knm,
            self.permanent_shear_kn,
            self.traffic_shear_kn,
            self.permanent_deflection_mm,
            self.traffic_deflection_mm,
            self.nominal_deflection_iy_m4,
        ) < 0.0:
            raise ValueError("Reliability baseline action magnitudes cannot be negative.")
        if self.nominal_deflection_iy_m4 <= 0.0:
            raise ValueError("Baseline flexural inertia must be positive.")
        if not self.provenance.strip():
            raise ValueError("Reliability baseline provenance is required.")


def extract_bs_en_reliability_baseline(
    result: ReferenceRunResult,
) -> BSENReliabilityBaseline:
    """Extract governing BS EN action components from one verified reference run."""

    combinations = result.eurocode_combinations
    if not combinations:
        raise ValueError("Reference run contains no BS EN combination results.")

    moment_item = max(
        combinations,
        key=lambda item: item.combinations.persistent_uls.effects.moment_knm,
    )
    shear_item = max(
        combinations,
        key=lambda item: item.combinations.persistent_uls.effects.shear_kn,
    )

    deflections = result.eurocode_characteristic_deflection
    if not deflections:
        raise ValueError(
            "Reference run does not contain a complete characteristic deflection envelope."
        )
    deflection_item = max(deflections, key=lambda item: item.governing.total_mm)

    moment_set = moment_item.combinations
    shear_set = shear_item.combinations
    governing_deflection = deflection_item.governing
    iy = final_composite_girder_properties(
        result.project.geometry,
        girder_index=deflection_item.girder_index,
    ).iy_m4

    return BSENReliabilityBaseline(
        project=result.project,
        moment_girder_index=moment_item.girder_index,
        shear_girder_index=shear_item.girder_index,
        deflection_girder_index=deflection_item.girder_index,
        permanent_moment_knm=moment_set.permanent_characteristic.moment_knm,
        traffic_moment_knm=moment_set.traffic_characteristic.moment_knm,
        permanent_shear_kn=shear_set.permanent_characteristic.shear_kn,
        traffic_shear_kn=shear_set.traffic_characteristic.shear_kn,
        permanent_deflection_mm=governing_deflection.permanent_mm,
        traffic_deflection_mm=governing_deflection.traffic_mm,
        nominal_deflection_iy_m4=iy,
        provenance=(
            "BS EN reliability baseline extracted from the verified common-grillage "
            "reference run: governing persistent-ULS moment/shear girders and the "
            "governing characteristic permanent+LM1 displacement case."
        ),
    )
