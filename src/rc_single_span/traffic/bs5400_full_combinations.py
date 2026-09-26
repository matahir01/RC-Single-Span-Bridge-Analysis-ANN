from __future__ import annotations

from dataclasses import dataclass

from rc_single_span.analysis.permanent import (
    PermanentLoadCategory,
    factored_permanent_effects,
)
from rc_single_span.codes.bs5400.combinations import (
    BS5400LimitState,
    BS5400PermanentGammaFL,
)
from rc_single_span.codes.bs5400.secondary import (
    BS5400Combination4Action,
    BS5400Combination4Factors,
    build_bs5400_combination4,
    build_bs5400_combination5,
)
from rc_single_span.codes.common import FactoredCombination, LoadEffects
from rc_single_span.core.models import BridgeProject
from rc_single_span.traffic.bs5400 import BS5400NominalTrafficSuite
from rc_single_span.traffic.combinations import (
    BS5400GirderCombinationResult,
    build_bs5400_project_combinations,
)


@dataclass(frozen=True)
class BS5400Combination4EffectInput:
    """Nominal structural effects for one separately considered secondary action.

    Use ``action`` for the directly source-pinned BD 37/01 6.9-6.11 highway
    actions. Use ``factors_override`` for project-classified actions whose table
    factors depend on containment class, structural mass, bearing type or other
    authority choices. Exactly one factor source is required.
    """

    secondary_nominal: LoadEffects
    associated_primary_nominal: LoadEffects
    provenance: str
    action: BS5400Combination4Action | None = None
    factors_override: BS5400Combination4Factors | None = None

    def __post_init__(self) -> None:
        if not self.provenance.strip():
            raise ValueError("Combination-4 effect input requires provenance.")
        if (self.action is None) == (self.factors_override is None):
            raise ValueError(
                "Combination-4 effect input requires exactly one of action or "
                "factors_override."
            )

    @property
    def action_name(self) -> str:
        if self.factors_override is not None:
            return self.factors_override.action_name
        assert self.action is not None
        return self.action.value


@dataclass(frozen=True)
class BS5400SupplementaryCombinationCase:
    girder_index: int
    combination: int
    limit_state: BS5400LimitState
    action_name: str
    result: FactoredCombination
    provenance: str
    secondary_nominal: LoadEffects | None = None
    associated_primary_nominal: LoadEffects | None = None
    secondary_gamma: float | None = None
    associated_primary_gamma: float | None = None

    @property
    def variable_effects(self) -> LoadEffects | None:
        """Return factored non-permanent effects when component data are retained."""

        if self.secondary_nominal is None or self.secondary_gamma is None:
            return None
        result = self.secondary_nominal.scaled(self.secondary_gamma)
        if self.associated_primary_nominal is not None:
            if self.associated_primary_gamma is None:
                raise ValueError(
                    "Associated primary nominal effect is present without its factor."
                )
            result = result + self.associated_primary_nominal.scaled(
                self.associated_primary_gamma
            )
        return result


@dataclass(frozen=True)
class BS5400FullGirderCombinationResult:
    """Primary combinations 1-3 plus applicable secondary combinations 4-5."""

    girder_index: int
    primary: BS5400GirderCombinationResult
    supplementary: tuple[BS5400SupplementaryCombinationCase, ...]

    @property
    def all_uls_cases(self) -> tuple[FactoredCombination, ...]:
        return tuple(
            [
                case.result
                for case in self.primary.cases
                if case.limit_state is BS5400LimitState.ULS
            ]
            + [
                case.result
                for case in self.supplementary
                if case.limit_state is BS5400LimitState.ULS
            ]
        )

    @property
    def all_sls_cases(self) -> tuple[FactoredCombination, ...]:
        return tuple(
            [
                case.result
                for case in self.primary.cases
                if case.limit_state is BS5400LimitState.SLS
            ]
            + [
                case.result
                for case in self.supplementary
                if case.limit_state is BS5400LimitState.SLS
            ]
        )


def _permanent_factor_map(
    factors: BS5400PermanentGammaFL,
    limit_state: BS5400LimitState,
) -> dict[PermanentLoadCategory, float]:
    named = factors.as_named_factors(limit_state)
    return {
        PermanentLoadCategory.STRUCTURAL_DEAD: named["structural_dead"],
        PermanentLoadCategory.SURFACING: named["surfacing"],
        PermanentLoadCategory.OTHER_SUPERIMPOSED: named["other_superimposed"],
    }


def build_bs5400_full_project_combinations(
    project: BridgeProject,
    traffic: BS5400NominalTrafficSuite,
    *,
    combination4_effects_by_girder: dict[
        int, tuple[BS5400Combination4EffectInput, ...]
    ] | None = None,
    combination5_bearing_friction_by_girder: dict[int, LoadEffects] | None = None,
    combination5_provenance: str | None = None,
    permanent_factors: BS5400PermanentGammaFL | None = None,
) -> tuple[BS5400FullGirderCombinationResult, ...]:
    """Build the focused highway combination set 1-5.

    Combinations 1-3 are generated from the native HA/HB/HA+HB traffic engine.
    Combination 4 secondary actions and combination 5 bearing-friction actions
    require nominal *structural effects* from a model appropriate to those
    horizontal/local actions. This prevents the vertical grillage from
    fabricating response components it does not represent while still making
    the BS combination arithmetic fully executable and auditable.
    """

    primary = build_bs5400_project_combinations(
        project,
        traffic,
        permanent_factors=permanent_factors,
        combinations=(1, 2, 3),
    )
    gamma = permanent_factors or BS5400PermanentGammaFL()
    combo4_map = combination4_effects_by_girder or {}
    combo5_map = combination5_bearing_friction_by_girder or {}
    if combo5_map and (
        combination5_provenance is None or not combination5_provenance.strip()
    ):
        raise ValueError("Combination-5 bearing-friction effects require provenance.")

    expected = int(project.geometry.girder_count)
    invalid = (set(combo4_map) | set(combo5_map)) - set(range(1, expected + 1))
    if invalid:
        raise ValueError(
            f"Supplementary BS effects contain invalid girder indices: {sorted(invalid)}"
        )

    results: list[BS5400FullGirderCombinationResult] = []
    for primary_result in primary:
        index = primary_result.girder_index
        supplementary: list[BS5400SupplementaryCombinationCase] = []
        for state in BS5400LimitState:
            permanent_named = gamma.as_named_factors(state)
            permanent = factored_permanent_effects(
                project,
                girder_index=index,
                factors_by_category=_permanent_factor_map(gamma, state),
            )
            for item in combo4_map.get(index, ()):
                result = build_bs5400_combination4(
                    factored_permanent=permanent,
                    secondary_nominal=item.secondary_nominal,
                    associated_primary_nominal=item.associated_primary_nominal,
                    action=item.action,
                    factors_override=item.factors_override,
                    limit_state=state,
                    permanent_factor_audit=permanent_named,
                )
                supplementary.append(
                    BS5400SupplementaryCombinationCase(
                        girder_index=index,
                        combination=4,
                        limit_state=state,
                        action_name=item.action_name,
                        result=result,
                        provenance=item.provenance,
                        secondary_nominal=item.secondary_nominal,
                        associated_primary_nominal=item.associated_primary_nominal,
                        secondary_gamma=result.factors["secondary_live"],
                        associated_primary_gamma=result.factors[
                            "associated_primary_live"
                        ],
                    )
                )

            if index in combo5_map:
                friction_nominal = combo5_map[index]
                result = build_bs5400_combination5(
                    factored_permanent=permanent,
                    bearing_friction_nominal=friction_nominal,
                    limit_state=state,
                    permanent_factor_audit=permanent_named,
                )
                supplementary.append(
                    BS5400SupplementaryCombinationCase(
                        girder_index=index,
                        combination=5,
                        limit_state=state,
                        action_name="bearing_friction",
                        result=result,
                        provenance=str(combination5_provenance),
                        secondary_nominal=friction_nominal,
                        secondary_gamma=result.factors["bearing_friction"],
                    )
                )

        results.append(
            BS5400FullGirderCombinationResult(
                girder_index=index,
                primary=primary_result,
                supplementary=tuple(supplementary),
            )
        )
    return tuple(results)
