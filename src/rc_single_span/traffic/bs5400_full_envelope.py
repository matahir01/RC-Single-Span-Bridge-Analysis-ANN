from __future__ import annotations

from dataclasses import dataclass

from rc_single_span.codes.common import FactoredCombination
from rc_single_span.traffic.bs5400_full_combinations import (
    BS5400FullGirderCombinationResult,
)


@dataclass(frozen=True)
class BS5400FullCombinationEnvelope:
    girder_index: int
    uls_moment_knm: float
    uls_moment_source: str
    uls_shear_kn: float
    uls_shear_source: str
    uls_torsion_knm: float
    uls_torsion_source: str
    sls_moment_knm: float
    sls_moment_source: str
    sls_shear_kn: float
    sls_shear_source: str
    sls_torsion_knm: float
    sls_torsion_source: str


def _governing(
    cases: tuple[FactoredCombination, ...],
    component: str,
) -> tuple[float, str]:
    if not cases:
        raise ValueError("At least one BS 5400 combination case is required.")
    case = max(cases, key=lambda item: abs(getattr(item.effects, component)))
    return abs(float(getattr(case.effects, component))), case.name


def full_bs5400_combination_envelope(
    result: BS5400FullGirderCombinationResult,
) -> BS5400FullCombinationEnvelope:
    """Envelope all available BS 5400 combinations 1-5 for one girder.

    Absolute M/V/T response is used to avoid losing a governing reversed-sign
    effect.  This utility is intentionally response based: where a combination-4
    or combination-5 action is outside the vertical grillage's physics, its
    structural response must first be supplied by an appropriate model through
    the full-combination layer.
    """

    uls = result.all_uls_cases
    sls = result.all_sls_cases
    uls_m, uls_m_source = _governing(uls, "moment_knm")
    uls_v, uls_v_source = _governing(uls, "shear_kn")
    uls_t, uls_t_source = _governing(uls, "torsion_knm")
    sls_m, sls_m_source = _governing(sls, "moment_knm")
    sls_v, sls_v_source = _governing(sls, "shear_kn")
    sls_t, sls_t_source = _governing(sls, "torsion_knm")
    return BS5400FullCombinationEnvelope(
        girder_index=result.girder_index,
        uls_moment_knm=uls_m,
        uls_moment_source=uls_m_source,
        uls_shear_kn=uls_v,
        uls_shear_source=uls_v_source,
        uls_torsion_knm=uls_t,
        uls_torsion_source=uls_t_source,
        sls_moment_knm=sls_m,
        sls_moment_source=sls_m_source,
        sls_shear_kn=sls_v,
        sls_shear_source=sls_v_source,
        sls_torsion_knm=sls_t,
        sls_torsion_source=sls_t_source,
    )


def full_bs5400_project_envelopes(
    results: tuple[BS5400FullGirderCombinationResult, ...],
) -> tuple[BS5400FullCombinationEnvelope, ...]:
    return tuple(full_bs5400_combination_envelope(result) for result in results)
