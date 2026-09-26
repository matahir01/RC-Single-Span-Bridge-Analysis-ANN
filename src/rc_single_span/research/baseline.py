from __future__ import annotations

from dataclasses import dataclass

from rc_single_span.analysis.construction import factored_permanent_deflection_at_x_mm
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
    deflection_basis: str = "explicit baseline"

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
        if not self.provenance.strip() or not self.deflection_basis.strip():
            raise ValueError("Reliability baseline provenance/basis is required.")


def _deflection_components(
    result: ReferenceRunResult,
) -> tuple[int, float, float, str]:
    exact = result.eurocode_characteristic_deflection
    if exact:
        item = max(exact, key=lambda envelope: envelope.governing.total_mm)
        governing = item.governing
        return (
            item.girder_index,
            governing.permanent_mm,
            governing.traffic_mm,
            "combined permanent+LM1 displacement re-search across retained traffic cases",
        )

    # The response-specific influence-surface search stores only governing
    # physical cases rather than every tandem placement. In that mode retain the
    # deterministic traffic-governing displacement station and add the
    # characteristic permanent displacement at the same station. This fallback is
    # deliberately labelled because the stochastic model must not claim a full
    # combined-case re-search that was not performed.
    candidates: list[tuple[float, int, float, float]] = []
    for envelope in result.lm1.girders:
        x_m = float(envelope.deflection_position_m)
        permanent = factored_permanent_deflection_at_x_mm(
            result.project,
            girder_index=envelope.girder_index,
            x_m=x_m,
        )
        traffic = float(envelope.deflection_mm.value)
        candidates.append((permanent + traffic, envelope.girder_index, permanent, traffic))
    if not candidates:
        raise ValueError("Reference run contains no BS EN displacement response.")
    _, girder_index, permanent, traffic = max(candidates, key=lambda item: item[0])
    return (
        girder_index,
        permanent,
        traffic,
        "LM1 traffic-governing displacement station plus characteristic permanent displacement "
        "at the same station; not a full all-placement combined displacement re-search",
    )


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
    deflection_index, permanent_deflection, traffic_deflection, deflection_basis = (
        _deflection_components(result)
    )

    moment_set = moment_item.combinations
    shear_set = shear_item.combinations
    iy = final_composite_girder_properties(
        result.project.geometry,
        girder_index=deflection_index,
    ).iy_m4

    return BSENReliabilityBaseline(
        project=result.project,
        moment_girder_index=moment_item.girder_index,
        shear_girder_index=shear_item.girder_index,
        deflection_girder_index=deflection_index,
        permanent_moment_knm=moment_set.permanent_characteristic.moment_knm,
        traffic_moment_knm=moment_set.traffic_characteristic.moment_knm,
        permanent_shear_kn=shear_set.permanent_characteristic.shear_kn,
        traffic_shear_kn=shear_set.traffic_characteristic.shear_kn,
        permanent_deflection_mm=permanent_deflection,
        traffic_deflection_mm=traffic_deflection,
        nominal_deflection_iy_m4=iy,
        provenance=(
            "BS EN reliability baseline extracted from the verified common-grillage reference "
            "run. Characteristic permanent and LM1 components are kept separate before "
            "stochastic scaling."
        ),
        deflection_basis=deflection_basis,
    )
