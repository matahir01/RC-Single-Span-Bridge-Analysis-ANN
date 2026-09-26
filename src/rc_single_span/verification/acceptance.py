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

    The primary modern V1 gate is BS EN. Legacy BS 5400 / BD 37 capabilities
    remain visible in the matrix but do not block acceptance of the BS EN route.
    Independent checking is not the same as final engineering acceptance: a
    primary capability reaches ``ACCEPTED`` only after its documented boundary
    and project-basis checks are deliberately closed.
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
                    "Retain the closed STAAD evidence while separately closing the BS EN "
                    "loading, design and detailing gates."
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
                    "regions. The engine uses a response-specific signed influence-surface "
                    "search for the BS EN route."
                ),
                boundary=(
                    "Nationally Determined Parameters remain explicit. Influence-cell and "
                    "longitudinal search resolution are numerical controls that require "
                    "project-geometry convergence rather than a universal fixed value."
                ),
                next_evidence=(
                    "Complete the 15 m reference convergence audit at the adopted 5% search "
                    "criterion and preserve a spot-check if the search topology changes."
                ),
            ),
            AcceptanceItem(
                key="bs5400_ha_hb",
                title="Legacy BD 37/01 HA, HB and HA+HB loading",
                domain=VerificationDomain.LOADING,
                state=EvidenceState.INDEPENDENTLY_CHECKED,
                evidence=(
                    "Official archived BD 37/01 clauses pin HA UDL/KEL, HB geometry/factors "
                    "and HA+HB coexistence rules, while the completed STAAD campaign checks "
                    "the resulting reference-model structural responses."
                ),
                boundary=(
                    "BD 37/01 is retained as a legacy route. Authority-specific HB unit counts "
                    "and combinations requiring secondary/accidental actions remain explicit."
                ),
                next_evidence=(
                    "Keep project-authority choices explicit and do not blend legacy BS 5400 "
                    "factors with the BS EN route."
                ),
                v1_gate=False,
            ),
            AcceptanceItem(
                key="bs_en_combinations",
                title="BS EN 1990 ULS/SLS combinations",
                domain=VerificationDomain.COMBINATIONS,
                state=EvidenceState.INDEPENDENTLY_CHECKED,
                evidence=(
                    "BS EN 1990/JRC road-bridge factors and serviceability forms are "
                    "source-pinned with numerical combination tests. Separate Gsup/Ginf "
                    "treatment is explicit and weighted frequent LM1 TS/UDL search is wired."
                ),
                boundary=(
                    "The National Annex/project NDP basis is not inferred. Wind, thermal, "
                    "accidental and other secondary-action combinations outside the focused "
                    "V1 action model are not claimed as verified."
                ),
                next_evidence=(
                    "Record the selected project NDP/NA basis in each real design and expand "
                    "the combination set only when the corresponding actions are modelled."
                ),
            ),
            AcceptanceItem(
                key="legacy_bs_combinations",
                title="Legacy BS 5400 / BD 37 ULS/SLS combinations",
                domain=VerificationDomain.COMBINATIONS,
                state=EvidenceState.INDEPENDENTLY_CHECKED,
                evidence=(
                    "BD 37/01 permanent and primary traffic factors for combinations 1-3 are "
                    "source-pinned and regression-tested independently of the BS EN route."
                ),
                boundary=(
                    "Combinations 4-5 require secondary or accidental actions not presently "
                    "inside the focused legacy action model."
                ),
                next_evidence=(
                    "Extend only when the corresponding legacy actions and project authority "
                    "basis are explicitly modelled."
                ),
                v1_gate=False,
            ),
            AcceptanceItem(
                key="bs_en_flexure_shear",
                title="BS EN 1992-2 flexure and shear design",
                domain=VerificationDomain.DESIGN_RESISTANCE,
                state=EvidenceState.INDEPENDENTLY_CHECKED,
                evidence=(
                    "The production EC2/BS EN resistance kernels reproduce a Concrete Centre "
                    "published flexure example and the JRC bridge shear worked example; "
                    "project-level combined-effect wiring is regression-tested."
                ),
                boundary=(
                    "Independent equation examples do not themselves approve a project girder. "
                    "alpha_cc, material strengths, ductility limits and other NDP/project inputs "
                    "must remain explicit."
                ),
                next_evidence=(
                    "Complete and review the reference-girder hand-check package before moving "
                    "this capability from independently checked to accepted."
                ),
            ),
            AcceptanceItem(
                key="legacy_bs_flexure_shear",
                title="Legacy BS 5400 flexure and shear design",
                domain=VerificationDomain.DESIGN_RESISTANCE,
                state=EvidenceState.INDEPENDENTLY_CHECKED,
                evidence=(
                    "The legacy shear kernel reproduces the owner-supplied Ragana bridge shear "
                    "calculation. The doubly reinforced flexure path now separately reproduces "
                    "the same Ragana beam basis: approximately 3148 kNm limiting concrete "
                    "moment, 2388 mm2 compression steel and 9751 mm2 total tension steel using "
                    "0.72fy compression-steel and 0.87fy tension-steel design stresses."
                ),
                boundary=(
                    "This is legacy BS evidence only. Its stress-block and reinforcement "
                    "assumptions must not be imported into the primary BS EN 1992 route."
                ),
                next_evidence=(
                    "Retain the Ragana regression as a legacy benchmark and verify any further "
                    "legacy project-specific detailing independently when required."
                ),
                v1_gate=False,
            ),
            AcceptanceItem(
                key="bs_en_cracking",
                title="BS EN 1992-2 crack-width checks",
                domain=VerificationDomain.SERVICEABILITY,
                state=EvidenceState.INDEPENDENTLY_CHECKED,
                evidence=(
                    "The source-pinned EC2 crack formula reproduces the published 0.184 mm "
                    "worked-example result, and the production close-spacing crack path now "
                    "calls that same pinned formula."
                ),
                boundary=(
                    "Crack-width limits and the relevant SLS combination remain project/code "
                    "basis inputs; a worked formula match is not a project acceptance."
                ),
                next_evidence=(
                    "Review the complete reference-girder BS EN crack check, including the "
                    "selected combination and limit, before promoting it to accepted."
                ),
            ),
            AcceptanceItem(
                key="legacy_bs_cracking",
                title="Legacy BS 5400 crack-width checks",
                domain=VerificationDomain.SERVICEABILITY,
                state=EvidenceState.INTERNAL_TESTED,
                evidence=(
                    "The layered legacy crack-width implementation and project wiring are "
                    "regression-tested."
                ),
                boundary=(
                    "The available Ragana cracking example is internally inconsistent and is "
                    "deliberately not promoted as independent acceptance evidence."
                ),
                next_evidence=(
                    "Reproduce a consistent independent legacy BS crack-width example before "
                    "claiming independent verification."
                ),
                v1_gate=False,
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
                key="bs_en_reinforcement_detailing",
                title="BS EN reinforcement selection and detailing",
                domain=VerificationDomain.DETAILING,
                state=EvidenceState.INTERNAL_TESTED,
                evidence=(
                    "Required steel, discrete cages, anchorage, curtailment, fatigue, "
                    "construction-stage stress, laps and congestion checks are implemented. "
                    "Published/JRC checks pin anchorage, fatigue and the EC2 tension-shift rule."
                ),
                boundary=(
                    "Project-specific fatigue resistance/detail category, construction-stage "
                    "stress limits, bearing geometry and drawing-level review are not invented."
                ),
                next_evidence=(
                    "Independently hand-check the selected BS EN reference cage, fatigue, "
                    "anchorage, curtailment and end-zone outputs as one detailing package."
                ),
            ),
            AcceptanceItem(
                key="legacy_bs_reinforcement_detailing",
                title="Legacy BS reinforcement selection and detailing",
                domain=VerificationDomain.DETAILING,
                state=EvidenceState.INTERNAL_TESTED,
                evidence=(
                    "Legacy policies remain isolated from BS EN and are protected by internal "
                    "constructability and design-path regression tests."
                ),
                boundary=(
                    "The legacy detailing route has not yet received the same source-pinned "
                    "independent package as the primary BS EN route."
                ),
                next_evidence=(
                    "Verify legacy detailing separately if a project still requires that route."
                ),
                v1_gate=False,
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
                next_evidence=(
                    "Review a complete BS EN reference calculation report against engine outputs."
                ),
            ),
        )
    )
