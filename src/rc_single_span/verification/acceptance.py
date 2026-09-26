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
    """Return the current evidence snapshot for the focused single-span app.

    Independent checking is not the same as final engineering acceptance. A
    capability reaches ``ACCEPTED`` only after its documented boundaries and
    remaining project-basis checks are deliberately closed.
    """

    return AcceptanceMatrix(
        (
            AcceptanceItem(
                key="common_grillage",
                title="Common full-width grillage structural response",
                domain=VerificationDomain.STRUCTURAL_ANALYSIS,
                state=EvidenceState.INDEPENDENTLY_CHECKED,
                evidence=(
                    "The current genuine STAAD campaign covers 83/83 exported full-width "
                    "models and 410,576/410,576 expected direct-global result fields with "
                    "zero engineering comparison failures."
                ),
                boundary=(
                    "This establishes solver response for the verified model family; it does "
                    "not certify traffic-code selection, RC resistance or detailing rules."
                ),
                next_evidence=(
                    "Retain the closed STAAD evidence while separately closing the BS EN and "
                    "legacy-code loading/design gates."
                ),
            ),
            AcceptanceItem(
                key="construction_stage_response",
                title="Three-stage construction response",
                domain=VerificationDomain.STRUCTURAL_ANALYSIS,
                state=EvidenceState.INDEPENDENTLY_CHECKED,
                evidence=(
                    "Genuine STAAD returns are complete for the precast, deck-construction "
                    "and final-composite reference systems, with the permanent-component "
                    "load-time stiffness responses also included in the external campaign."
                ),
                boundary=(
                    "The verified V1 sequence is the essential unpropped single-span sequence "
                    "with unchanged supports; general propping, staged continuity and advanced "
                    "time-dependent redistribution remain outside V1."
                ),
                next_evidence=(
                    "No further external solver rerun is required for the closed V1 stage "
                    "sequence unless its modelling assumptions change."
                ),
            ),
            AcceptanceItem(
                key="eurocode_lm1",
                title="BS EN 1991-2 LM1 loading and search",
                domain=VerificationDomain.LOADING,
                state=EvidenceState.INDEPENDENTLY_CHECKED,
                evidence=(
                    "JRC source values pin LM1 lane loads, complete tandem geometry, separate "
                    "frequent TS/UDL factors and the requirement to load only unfavourable UDL "
                    "regions. The engine now uses a response-specific signed influence-surface "
                    "search for the BS EN route."
                ),
                boundary=(
                    "Nationally Determined Parameters remain explicit. Influence-cell and "
                    "longitudinal search resolution are numerical controls that require "
                    "project-geometry convergence rather than a universal fixed value."
                ),
                next_evidence=(
                    "Complete convergence checks for the 15 m reference geometry and preserve "
                    "a traceable external spot-check if the influence-search topology changes."
                ),
            ),
            AcceptanceItem(
                key="bs5400_ha_hb",
                title="Legacy BD 37/01 HA, HB and HA+HB loading",
                domain=VerificationDomain.LOADING,
                state=EvidenceState.INDEPENDENTLY_CHECKED,
                evidence=(
                    "Official archived BD 37/01 clauses pin HA UDL/KEL, HB geometry/factors "
                    "and HA+HB coexistence rules, while the completed STAAD campaign independently "
                    "checks the resulting reference-model structural responses."
                ),
                boundary=(
                    "BD 37/01 is retained as a legacy route. Authority-specific HB unit counts "
                    "and combinations requiring secondary/accidental actions remain explicit or "
                    "outside the current primary V1 action set."
                ),
                next_evidence=(
                    "Keep project-authority choices explicit and do not blend legacy BS 5400 "
                    "factors with the BS EN route."
                ),
            ),
            AcceptanceItem(
                key="code_combinations",
                title="BS EN and legacy BS 5400 ULS/SLS combinations",
                domain=VerificationDomain.COMBINATIONS,
                state=EvidenceState.INDEPENDENTLY_CHECKED,
                evidence=(
                    "BS EN 1990/JRC recommended bridge factors and serviceability forms are "
                    "source-pinned with numerical combination tests; BD 37/01 permanent and "
                    "primary traffic factors for combinations 1-3 are pinned independently."
                ),
                boundary=(
                    "The BS EN National Annex/project NDP basis is not inferred. Wind, thermal, "
                    "accidental and other secondary-action combinations outside the current "
                    "focused V1 action model are not claimed as verified."
                ),
                next_evidence=(
                    "Record the selected project NDP/NA basis in each real design and expand "
                    "the combination set only when the corresponding actions are modelled."
                ),
            ),
            AcceptanceItem(
                key="flexure_shear",
                title="BS EN 1992-2 and legacy BS 5400 flexure/shear design",
                domain=VerificationDomain.DESIGN_RESISTANCE,
                state=EvidenceState.INTERNAL_TESTED,
                evidence=(
                    "The EC2/BS EN path reproduces published flexure and shear worked examples, "
                    "and the legacy BS path reproduces an owner-supplied shear calculation. "
                    "Project-level demand wiring is regression-tested."
                ),
                boundary=(
                    "The legacy BS flexure path and the full bridge-specific set of resistance "
                    "checks are not yet independently closed as one acceptance package."
                ),
                next_evidence=(
                    "Add an independent legacy BS flexure benchmark and finish the reference "
                    "girder resistance hand-check package."
                ),
            ),
            AcceptanceItem(
                key="cracking",
                title="BS EN 1992-2 and legacy BS crack-width checks",
                domain=VerificationDomain.SERVICEABILITY,
                state=EvidenceState.INTERNAL_TESTED,
                evidence=(
                    "Layered cracked-section and project-level crack checks are regression-tested."
                ),
                boundary=(
                    "The available Ragana legacy cracking example is internally inconsistent and "
                    "is deliberately not promoted as acceptance evidence. Allowable crack limits "
                    "remain explicit project/code inputs."
                ),
                next_evidence="Reproduce independent published or traceable hand crack-width examples.",
            ),
            AcceptanceItem(
                key="deflection",
                title="Permanent plus traffic deflection",
                domain=VerificationDomain.SERVICEABILITY,
                state=EvidenceState.INTERNAL_TESTED,
                evidence=(
                    "Stage-aware permanent deflection and common-grillage traffic displacement "
                    "are implemented, with an all-case combined-displacement search. STAAD "
                    "independently checks the underlying elastic displacements."
                ),
                boundary=(
                    "A road-bridge allowable deflection limit is not treated as universal and "
                    "must remain an explicit project criterion."
                ),
                next_evidence=(
                    "Pin the serviceability acceptance calculation and selected project limit "
                    "against an independent BS EN bridge example or traceable hand calculation."
                ),
            ),
            AcceptanceItem(
                key="reinforcement_detailing",
                title="Reinforcement selection and constructability",
                domain=VerificationDomain.DETAILING,
                state=EvidenceState.INTERNAL_TESTED,
                evidence=(
                    "Required steel, discrete bars/links, anchorage infrastructure, curtailment, "
                    "fatigue, construction-stage stress, laps and congestion checks are present "
                    "with BS EN and legacy BS policies kept separate."
                ),
                boundary=(
                    "Project-specific fatigue resistance/detail category, construction-stage "
                    "stress limits, bearing geometry and drawing-level review are not invented."
                ),
                next_evidence=(
                    "Independently hand-check the selected BS EN cage, fatigue, anchorage, "
                    "curtailment and end-zone outputs for the reference girder."
                ),
            ),
            AcceptanceItem(
                key="calculation_reporting",
                title="Traceable calculation reporting",
                domain=VerificationDomain.REPORTING,
                state=EvidenceState.INTERNAL_TESTED,
                evidence=(
                    "Structured formula/substitution/result/reference report records render "
                    "deterministically and preserve the selected code basis."
                ),
                boundary="A presentation layer is separate from engineering verification.",
                next_evidence="Review a complete reference calculation report against engine outputs.",
            ),
        )
    )
