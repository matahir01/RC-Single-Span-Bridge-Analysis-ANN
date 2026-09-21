from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rc_single_span.verification.gate import CapabilityEvidence, EvidenceState, VerificationGate


class VerificationDomain(str, Enum):
    STRUCTURAL_ANALYSIS = "structural_analysis"
    LOADING = "loading"
    COMBINATIONS = "combinations"
    DESIGN_RESISTANCE = "design_resistance"
    SERVICEABILITY = "serviceability"
    DETAILING = "detailing"
    REPORTING = "reporting"


@dataclass(frozen=True)
class AcceptanceItem:
    key: str
    title: str
    domain: VerificationDomain
    state: EvidenceState
    evidence: str
    boundary: str
    next_evidence: str
    v1_gate: bool = True

    def __post_init__(self) -> None:
        for value, label in (
            (self.key, "key"),
            (self.title, "title"),
            (self.evidence, "evidence"),
            (self.boundary, "boundary"),
            (self.next_evidence, "next_evidence"),
        ):
            if not value.strip():
                raise ValueError(f"Acceptance item {label} cannot be empty.")


@dataclass(frozen=True)
class AcceptanceMatrix:
    items: tuple[AcceptanceItem, ...]

    @property
    def v1_gate(self) -> VerificationGate:
        return VerificationGate(
            tuple(
                CapabilityEvidence(
                    capability=item.key,
                    state=item.state,
                    evidence=item.evidence,
                )
                for item in self.items
                if item.v1_gate
            )
        )

    def by_domain(self, domain: VerificationDomain) -> tuple[AcceptanceItem, ...]:
        return tuple(item for item in self.items if item.domain is domain)


def current_v1_acceptance_matrix() -> AcceptanceMatrix:
    """Return the honest Stage-8 starting point for the focused single-span app.

    Internal regression tests are not promoted to independent acceptance.
    External/hand-check evidence must be attached explicitly before state changes.
    """

    return AcceptanceMatrix(
        (
            AcceptanceItem(
                key="common_grillage",
                title="Common full-width grillage structural response",
                domain=VerificationDomain.STRUCTURAL_ANALYSIS,
                state=EvidenceState.INTERNAL_TESTED,
                evidence=(
                    "Sparse common-grillage equilibrium, load mapping and per-girder "
                    "response are protected by repository regression tests."
                ),
                boundary=(
                    "This repository has not yet completed its own independent STAAD "
                    "comparison campaign for the focused model."
                ),
                next_evidence=(
                    "Compare reactions, M, V, T and displacement for the same exported "
                    "single-span models and loads in STAAD."
                ),
            ),
            AcceptanceItem(
                key="construction_stage_response",
                title="Three-stage construction response",
                domain=VerificationDomain.STRUCTURAL_ANALYSIS,
                state=EvidenceState.INTERNAL_TESTED,
                evidence=(
                    "Precast, deck-construction and final-composite stiffness/load stages "
                    "have deterministic regression tests. Stage 8 now rebuilds every "
                    "girder/stage as a separate beam-FE model with the same load segments "
                    "and stage A/J/Iy/Iz, cross-checks reactions/M/V/deflection, and emits "
                    "an exact STAAD verification package for each stage."
                ),
                boundary=(
                    "The second in-repository beam-FE implementation is an internal "
                    "cross-check, not independent external evidence. Genuine STAAD "
                    "stage results have not yet been returned and compared."
                ),
                next_evidence=(
                    "Run the emitted precast, wet-deck and final/superimposed stage "
                    "models in STAAD and compare reactions, M, V and displacement."
                ),
            ),
            AcceptanceItem(
                key="eurocode_lm1",
                title="Eurocode LM1 loading and search",
                domain=VerificationDomain.LOADING,
                state=EvidenceState.INTERNAL_TESTED,
                evidence=(
                    "Notional lanes, LM1 characteristic values, physical wheel/area load "
                    "mapping, equilibrium and convergence controls are regression-tested."
                ),
                boundary="Internal tests do not independently certify the complete loading/search path.",
                next_evidence="Check representative lane/resultant placements by hand and in STAAD.",
            ),
            AcceptanceItem(
                key="bs5400_ha_hb",
                title="BD 37/01 HA, HB and HA+HB loading",
                domain=VerificationDomain.LOADING,
                state=EvidenceState.INTERNAL_TESTED,
                evidence=(
                    "HA UDL/KEL, 45-unit HB geometry, transverse movement and HA+HB "
                    "coexistence rules are protected by targeted regression tests."
                ),
                boundary="No focused-repository independent external solver campaign is recorded yet.",
                next_evidence="Verify representative HA, HB and HA+HB cases independently.",
            ),
            AcceptanceItem(
                key="code_combinations",
                title="Eurocode and BS 5400 ULS/SLS combinations",
                domain=VerificationDomain.COMBINATIONS,
                state=EvidenceState.INTERNAL_TESTED,
                evidence=(
                    "Eurocode ULS/SLS and BS combinations 1-3 factors/superposition are "
                    "covered by deterministic tests with traceable traffic provenance."
                ),
                boundary="Factor application tests are not a substitute for independent code review.",
                next_evidence="Check representative combination rows against hand/code-reference calculations.",
            ),
            AcceptanceItem(
                key="flexure_shear",
                title="EC2 and BS 5400 flexure/shear design",
                domain=VerificationDomain.DESIGN_RESISTANCE,
                state=EvidenceState.INTERNAL_TESTED,
                evidence=(
                    "Layered flexure and shear kernels include migrated benchmark regression "
                    "cases and project-level demand wiring."
                ),
                boundary=(
                    "Migrated regression values remain internal evidence until their external "
                    "worked-example sources are recorded and independently reviewed here."
                ),
                next_evidence="Record and reproduce published/hand flexure and shear examples.",
            ),
            AcceptanceItem(
                key="cracking",
                title="EC2 and BS 5400 crack-width checks",
                domain=VerificationDomain.SERVICEABILITY,
                state=EvidenceState.INTERNAL_TESTED,
                evidence="Layered cracked-section and project-level crack checks are regression-tested.",
                boundary="Allowable crack limits remain explicit project/code inputs.",
                next_evidence="Reproduce independent published or hand crack-width examples.",
            ),
            AcceptanceItem(
                key="deflection",
                title="Permanent plus traffic deflection",
                domain=VerificationDomain.SERVICEABILITY,
                state=EvidenceState.INTERNAL_TESTED,
                evidence=(
                    "Stage-aware permanent deflection and common-grillage traffic displacement "
                    "are implemented; Stage 8 adds an all-case combined displacement re-search."
                ),
                boundary=(
                    "A road-bridge allowable deflection value is not treated as universal and "
                    "must remain an explicit project criterion."
                ),
                next_evidence="Run all-case combined search and compare representative responses externally.",
            ),
            AcceptanceItem(
                key="reinforcement_detailing",
                title="Reinforcement selection and constructability",
                domain=VerificationDomain.DETAILING,
                state=EvidenceState.INTERNAL_TESTED,
                evidence=(
                    "Required steel, discrete bars/links, cover and cage fit checks are "
                    "regression-tested with EC2 and BS policies kept separate."
                ),
                boundary=(
                    "Anchorage/laps, drawing-level congestion and unknown provided vertical "
                    "layer spacing are not silently invented."
                ),
                next_evidence="Hand-check selected cages and link layouts for reference girders.",
            ),
            AcceptanceItem(
                key="calculation_reporting",
                title="Traceable calculation reporting",
                domain=VerificationDomain.REPORTING,
                state=EvidenceState.INTERNAL_TESTED,
                evidence=(
                    "Stage 8 introduces structured formula/substitution/result/reference "
                    "report records with deterministic Markdown rendering."
                ),
                boundary="A desktop/PDF presentation layer is separate from engineering verification.",
                next_evidence="Review a complete reference calculation report against engine outputs.",
            ),
        )
    )
