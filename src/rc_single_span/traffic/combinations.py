from __future__ import annotations

from dataclasses import dataclass, replace

from rc_single_span.analysis.permanent import (
    PermanentLoadCategory,
    characteristic_permanent_effects,
    characteristic_permanent_effects_by_category,
    factored_permanent_effects,
)
from rc_single_span.codes.bs5400.combinations import (
    BS5400LimitState,
    BS5400PermanentGammaFL,
    BS5400PrimaryTraffic,
    build_bs5400_primary_combination,
)
from rc_single_span.codes.common import FactoredCombination, LoadEffects
from rc_single_span.codes.eurocode.combinations import (
    EurocodeCombinationFactors,
    EurocodeCombinationSet,
    EurocodeServiceabilityFactors,
    build_eurocode_combination_set,
)
from rc_single_span.core.models import BridgeProject
from rc_single_span.traffic.bs5400 import BS5400NominalTrafficSuite
from rc_single_span.traffic.lm1 import LM1SearchResult


@dataclass(frozen=True)
class EurocodeGirderCombinationResult:
    girder_index: int
    combinations: EurocodeCombinationSet
    traffic_source: str = "EN 1991-2 LM1 common-grillage envelope"


@dataclass(frozen=True)
class BS5400TrafficCombinationCase:
    girder_index: int
    traffic: BS5400PrimaryTraffic
    combination: int
    limit_state: BS5400LimitState
    nominal_traffic: LoadEffects
    result: FactoredCombination


@dataclass(frozen=True)
class BS5400GoverningCombination:
    girder_index: int
    combination: int
    limit_state: BS5400LimitState
    effects: LoadEffects
    governing_sources: dict[str, BS5400PrimaryTraffic]


@dataclass(frozen=True)
class BS5400GirderCombinationResult:
    girder_index: int
    permanent_characteristic_by_category: dict[PermanentLoadCategory, LoadEffects]
    cases: tuple[BS5400TrafficCombinationCase, ...]
    governing: tuple[BS5400GoverningCombination, ...]


def _envelope_effects(item: object) -> LoadEffects:
    return LoadEffects(
        moment_knm=float(item.moment_knm.value),
        shear_kn=float(item.shear_kn.value),
        torsion_knm=float(item.torsion_knm.value),
    )


def build_eurocode_project_combinations(
    project: BridgeProject,
    traffic: LM1SearchResult,
    *,
    sls_factors: EurocodeServiceabilityFactors,
    uls_factors: EurocodeCombinationFactors | None = None,
    frequent_traffic: LM1SearchResult | None = None,
) -> tuple[EurocodeGirderCombinationResult, ...]:
    """Combine the common permanent actions with the LM1 envelope by girder."""

    expected = int(project.geometry.girder_count)
    if len(traffic.girders) != expected:
        raise ValueError("LM1 result girder count does not match the physical bridge.")
    if sls_factors.frequent_components_differ:
        if frequent_traffic is None or len(frequent_traffic.girders) != expected:
            raise ValueError("Distinct frequent LM1 factors require a complete weighted search result.")
    elif frequent_traffic is not None:
        raise ValueError("A separate frequent search is only required for distinct tandem/UDL factors.")

    results: list[EurocodeGirderCombinationResult] = []
    for girder in traffic.girders:
        permanent = characteristic_permanent_effects(
            project,
            girder_index=girder.girder_index,
        )
        traffic_effects = _envelope_effects(girder)
        combination_set = build_eurocode_combination_set(
            permanent,
            traffic_effects,
            sls_factors=(
                EurocodeServiceabilityFactors(1.0, sls_factors.psi2_traffic)
                if frequent_traffic is not None else sls_factors
            ),
            uls_factors=uls_factors,
        )
        if frequent_traffic is not None:
            weighted_girder = frequent_traffic.girders[girder.girder_index - 1]
            if weighted_girder.girder_index != girder.girder_index:
                raise ValueError("Weighted LM1 result girder order does not match characteristic result.")
            combination_set = replace(
                combination_set,
                frequent_sls=FactoredCombination(
                    name="EN 1990 frequent SLS",
                    effects=permanent + _envelope_effects(weighted_girder),
                    factors={
                        "G": 1.0,
                        "Q_tandem": sls_factors.psi1_traffic,
                        "q_udl": sls_factors.psi1_udl_traffic,
                    },
                ),
            )
        results.append(
            EurocodeGirderCombinationResult(
                girder_index=girder.girder_index,
                combinations=combination_set,
            )
        )
    return tuple(results)


def _bs_permanent_factor_map(
    factors: BS5400PermanentGammaFL,
    limit_state: BS5400LimitState,
) -> dict[PermanentLoadCategory, float]:
    named = factors.as_named_factors(limit_state)
    return {
        PermanentLoadCategory.STRUCTURAL_DEAD: named["structural_dead"],
        PermanentLoadCategory.SURFACING: named["surfacing"],
        PermanentLoadCategory.OTHER_SUPERIMPOSED: named["other_superimposed"],
    }


def _governing_bs_cases(
    cases: tuple[BS5400TrafficCombinationCase, ...],
    *,
    girder_index: int,
    combination: int,
    limit_state: BS5400LimitState,
) -> BS5400GoverningCombination:
    selected = tuple(
        item
        for item in cases
        if item.combination == combination and item.limit_state is limit_state
    )
    if not selected:
        raise RuntimeError("No BS 5400 traffic cases were available for governing selection.")

    moment_case = max(selected, key=lambda item: item.result.effects.moment_knm)
    shear_case = max(selected, key=lambda item: item.result.effects.shear_kn)
    torsion_case = max(selected, key=lambda item: item.result.effects.torsion_knm)
    return BS5400GoverningCombination(
        girder_index=girder_index,
        combination=combination,
        limit_state=limit_state,
        effects=LoadEffects(
            moment_knm=moment_case.result.effects.moment_knm,
            shear_kn=shear_case.result.effects.shear_kn,
            torsion_knm=torsion_case.result.effects.torsion_knm,
        ),
        governing_sources={
            "moment": moment_case.traffic,
            "shear": shear_case.traffic,
            "torsion": torsion_case.traffic,
        },
    )


def build_bs5400_project_combinations(
    project: BridgeProject,
    traffic: BS5400NominalTrafficSuite,
    *,
    permanent_factors: BS5400PermanentGammaFL | None = None,
    combinations: tuple[int, ...] = (1, 2, 3),
) -> tuple[BS5400GirderCombinationResult, ...]:
    """Build primary highway ULS/SLS combinations for HA, HB and HA+HB.

    The function intentionally covers combinations 1-3 because combinations 4
    and 5 introduce secondary/accidental actions not yet inside the focused V1
    deterministic action model.
    """

    if not combinations:
        raise ValueError("At least one BS 5400 combination number is required.")
    if any(value not in (1, 2, 3) for value in combinations):
        raise ValueError("This primary highway combination engine supports 1, 2 and 3 only.")

    expected = int(project.geometry.girder_count)
    for result in (traffic.ha, traffic.hb, traffic.ha_hb):
        if len(result.girders) != expected:
            raise ValueError("BS traffic result girder count does not match the physical bridge.")

    permanent_gamma = permanent_factors or BS5400PermanentGammaFL()
    results: list[BS5400GirderCombinationResult] = []

    for girder_index in range(1, expected + 1):
        permanent_characteristic = characteristic_permanent_effects_by_category(
            project,
            girder_index=girder_index,
        )
        nominal_by_traffic = {
            BS5400PrimaryTraffic.HA: _envelope_effects(
                traffic.ha.girders[girder_index - 1]
            ),
            BS5400PrimaryTraffic.HB: _envelope_effects(
                traffic.hb.girders[girder_index - 1]
            ),
            BS5400PrimaryTraffic.HA_HB: _envelope_effects(
                traffic.ha_hb.girders[girder_index - 1]
            ),
        }

        cases: list[BS5400TrafficCombinationCase] = []
        for combination in combinations:
            for limit_state in BS5400LimitState:
                permanent_named = permanent_gamma.as_named_factors(limit_state)
                permanent_effects = factored_permanent_effects(
                    project,
                    girder_index=girder_index,
                    factors_by_category=_bs_permanent_factor_map(
                        permanent_gamma,
                        limit_state,
                    ),
                )
                for traffic_case, nominal in nominal_by_traffic.items():
                    combination_result = build_bs5400_primary_combination(
                        factored_permanent=permanent_effects,
                        traffic_nominal=nominal,
                        traffic=traffic_case,
                        combination=combination,
                        limit_state=limit_state,
                        permanent_factor_audit=permanent_named,
                    )
                    cases.append(
                        BS5400TrafficCombinationCase(
                            girder_index=girder_index,
                            traffic=traffic_case,
                            combination=combination,
                            limit_state=limit_state,
                            nominal_traffic=nominal,
                            result=combination_result,
                        )
                    )

        cases_tuple = tuple(cases)
        governing = tuple(
            _governing_bs_cases(
                cases_tuple,
                girder_index=girder_index,
                combination=combination,
                limit_state=limit_state,
            )
            for combination in combinations
            for limit_state in BS5400LimitState
        )
        results.append(
            BS5400GirderCombinationResult(
                girder_index=girder_index,
                permanent_characteristic_by_category=permanent_characteristic,
                cases=cases_tuple,
                governing=governing,
            )
        )

    return tuple(results)
