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
    legacy_bs_gate: bool = False

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
        """Primary BS EN V1 software-capability gate."""
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

    @property
    def legacy_bs_v1_gate(self) -> VerificationGate:
        """Focused legacy BS 5400 / BD 37 V1 software-capability gate."""
        return VerificationGate(
            tuple(
                CapabilityEvidence(
                    capability=item.key,
                    state=item.state,
                    evidence=item.evidence,
                )
                for item in self.items
                if item.legacy_bs_gate
            )
        )

    def by_domain(self, domain: VerificationDomain) -> tuple[AcceptanceItem, ...]:
        return tuple(item for item in self.items if item.domain is domain)


def current_v1_acceptance_matrix() -> AcceptanceMatrix:
    """Return the focused single-span software-capability evidence snapshot.

    ``ACCEPTED`` means that the software capability is accepted for the
    documented V1 scope. It is deliberately not a statement that any particular
    bridge project or reinforcement drawing is approved. Project-specific code
    basis, serviceability limits, fatigue/detailing data and final engineering
    review remain explicit project-level responsibilities.

    The primary modern BS EN route and the legacy BS 5400 / BD 37 route have
    separate gates. Shared structural-analysis/reporting capabilities can serve
    both gates, while code-specific loading, combinations, resistance and
    detailing evidence remains isolated.
    """

    return AcceptanceMatrix(
        (
            AcceptanceItem(
                key="common_grillage",
                title="Common full-width grillage structural response",
                domain=VerificationDomain.STRUCTURAL_ANALYSIS,
                state=EvidenceState.ACCEPTED,
                evidence=(
                    "Genuine STAAD evidence covers 83/83 exported full-width models and "
                    "410,576/410,576 expected direct-global result fields with zero "
                    "engineering comparison failures, including HA, HB and HA+HB models."
                ),
                boundary=(
                    "Acceptance is limited to the verified V1 model family and solver "
                    "formulation; it does not by itself validate either code's loading or RC rules."
                ),
                next_evidence=(
                    "Re-open this gate only if the structural formulation, element mapping, "
                    "support model or exported response definitions materially change."
                ),
                legacy_bs_gate=True,
            ),
            AcceptanceItem(
                key="construction_stage_response",
                title="Three-stage construction response",
                domain=VerificationDomain.STRUCTURAL_ANALYSIS,
                state=EvidenceState.ACCEPTED,
                evidence=(
                    "Genuine STAAD returns are complete for precast, deck-construction and "
                    "final-composite reference systems, including permanent-component "
                    "load-time stiffness responses."
                ),
                boundary=(
                    "The accepted V1 sequence is the documented unpropped single-span sequence "
                    "with unchanged supports; general propping, staged continuity and advanced "
                    "time-dependent redistribution remain outside V1."
                ),
                next_evidence=(
                    "Require new external evidence if the accepted construction-stage topology "
                    "or stiffness assumptions are expanded."
                ),
                legacy_bs_gate=True,
            ),
            AcceptanceItem(
                key="eurocode_lm1",
                title="BS EN 1991-2 LM1 loading and search",
                domain=VerificationDomain.LOADING,
                state=EvidenceState.ACCEPTED,
                evidence=(
                    "JRC/source-pinned tests cover LM1 lane loads, complete tandem geometry, "
                    "separate frequent TS/UDL factors and adverse-only UDL regions. The 15 m "
                    "reference search converged from 1.2 m to 0.6 m at 4.08765%, below the "
                    "pre-declared 5% criterion, with exhaustive tandem combinations retained."
                ),
                boundary=(
                    "Nationally Determined Parameters remain explicit. The accepted 0.6 m step "
                    "is reference-geometry evidence, not a universal BS EN discretisation rule."
                ),
                next_evidence=(
                    "Run the same convergence audit for materially different bridge geometries "
                    "or if the LM1 search topology changes."
                ),
            ),
            AcceptanceItem(
                key="bs5400_ha_hb",
                title="Legacy BD 37/01 HA, HB and HA+HB loading",
                domain=VerificationDomain.LOADING,
                state=EvidenceState.ACCEPTED,
                evidence=(
                    "Official archived BD 37/01 clauses pin HA UDL/KEL, HB geometry/factors "
                    "and HA+HB coexistence rules, while the completed STAAD campaign checks "
                    "the resulting reference-model structural responses."
                ),
                boundary=(
                    "This is the legacy BD 37/01 route. Authority-specific HB unit counts and "
                    "other project loading choices remain explicit and are not borrowed from BS EN."
                ),
                next_evidence=(
                    "Preserve the archived-source regressions and re-open the gate if placement, "
                    "lane or coexistence mechanics are materially changed."
                ),
                v1_gate=False,
                legacy_bs_gate=True,
            ),
            AcceptanceItem(
                key="bs_en_combinations",
                title="BS EN 1990 ULS/SLS combinations",
                domain=VerificationDomain.COMBINATIONS,
                state=EvidenceState.ACCEPTED,
                evidence=(
                    "BS EN 1990/JRC road-bridge factors and characteristic/frequent/quasi-"
                    "permanent forms are source-pinned with numerical tests. Separate Gsup/Ginf "
                    "treatment is explicit and weighted frequent LM1 TS/UDL search is wired."
                ),
                boundary=(
                    "The National Annex/project NDP basis is not inferred. Wind, thermal, "
                    "accidental and other secondary-action combinations outside the focused "
                    "V1 action model are outside this acceptance."
                ),
                next_evidence=(
                    "Record the adopted project NDP/NA basis in each real design and expand the "
                    "combination set only when the corresponding actions are modelled."
                ),
            ),
            AcceptanceItem(
                key="legacy_bs_combinations",
                title="Legacy BS 5400 / BD 37 ULS/SLS combinations",
                domain=VerificationDomain.COMBINATIONS,
                state=EvidenceState.ACCEPTED,
                evidence=(
                    "BD 37/01 permanent and primary traffic factors for combinations 1-3 are "
                    "source-pinned and regression-tested independently of the BS EN route."
                ),
                boundary=(
                    "Focused legacy V1 acceptance covers combinations 1-3 for actions actually "
                    "modelled. Combinations 4-5 are outside scope until their secondary or "
                    "accidental actions are explicitly implemented."
                ),
                next_evidence=(
                    "Extend the accepted combination scope only when the corresponding legacy "
                    "actions and authority basis are explicitly modelled and checked."
                ),
                v1_gate=False,
                legacy_bs_gate=True,
            ),
            AcceptanceItem(
                key="bs_en_flexure_shear",
                title="BS EN 1992-2 flexure and shear design",
                domain=VerificationDomain.DESIGN_RESISTANCE,
                state=EvidenceState.ACCEPTED,
                evidence=(
                    "The production BS EN resistance kernels reproduce a Concrete Centre "
                    "published flexure example and the JRC bridge shear worked example. "
                    "Minimum longitudinal/shear reinforcement rules and project-level wiring "
                    "are independently source-pinned or regression-checked."
                ),
                boundary=(
                    "Software acceptance does not approve a project girder. alpha_cc, material "
                    "strengths, ductility limits and other NDP/project inputs remain explicit."
                ),
                next_evidence=(
                    "Preserve the published-example regressions and add new benchmarks when "
                    "resistance models or supported section families are expanded."
                ),
            ),
            AcceptanceItem(
                key="legacy_bs_flexure_shear",
                title="Legacy BS 5400 flexure and shear design",
                domain=VerificationDomain.DESIGN_RESISTANCE,
                state=EvidenceState.ACCEPTED,
                evidence=(
                    "The legacy shear kernel reproduces the owner-supplied Ragana bridge shear "
                    "calculation. The doubly reinforced flexure path separately reproduces the "
                    "same Ragana beam basis using its stated legacy reinforcement design stresses."
                ),
                boundary=(
                    "This acceptance is for the focused legacy BS resistance implementation. "
                    "Its stress-block and reinforcement assumptions must not be imported into BS EN."
                ),
                next_evidence=(
                    "Retain the Ragana regressions and add further independent benchmarks when "
                    "the legacy resistance model or supported section families are expanded."
                ),
                v1_gate=False,
                legacy_bs_gate=True,
            ),
            AcceptanceItem(
                key="bs_en_cracking",
                title="BS EN 1992-2 crack-width checks",
                domain=VerificationDomain.SERVICEABILITY,
                state=EvidenceState.ACCEPTED,
                evidence=(
                    "The source-pinned EC2 crack formula reproduces the published approximately "
                    "0.184 mm worked-example result, and the production close-spacing crack path "
                    "calls the same pinned formula."
                ),
                boundary=(
                    "Crack-width limits and the applicable SLS combination remain explicit "
                    "project/code-basis inputs."
                ),
                next_evidence=(
                    "Preserve the source-pinned example and add further bridge examples if the "
                    "crack model is materially extended."
                ),
            ),
            AcceptanceItem(
                key="legacy_bs_cracking",
                title="Legacy BS 5400 crack-width checks",
                domain=VerificationDomain.SERVICEABILITY,
                state=EvidenceState.ACCEPTED,
                evidence=(
                    "The BS 5400-4 equations 24/25 implementation is pinned against an "
                    "independent worked bridge example: h=400 mm, T16 at 150 mm, As=1340 mm2/m, "
                    "70 kNm/m service moment, giving compression depth about 96.9 mm, a_cr about "
                    "87 mm and crack width about 0.22 mm."
                ),
                boundary=(
                    "The inconsistent Ragana crack calculation remains excluded. The applicable "
                    "allowable crack width, cover and SLS loading remain explicit project inputs."
                ),
                next_evidence=(
                    "Preserve the independent equation benchmark and add another source example "
                    "if the crack-width formulation is materially changed."
                ),
                v1_gate=False,
                legacy_bs_gate=True,
            ),
            AcceptanceItem(
                key="deflection",
                title="Permanent plus traffic deflection",
                domain=VerificationDomain.SERVICEABILITY,
                state=EvidenceState.ACCEPTED,
                evidence=(
                    "STAAD independently checks the underlying elastic displacements. The "
                    "software re-searches permanent plus traffic displacement across retained "
                    "cases, and the project-limit arithmetic/provenance path has an explicit "
                    "traceable hand-calculation regression."
                ),
                boundary=(
                    "There is no hidden universal road-bridge span-ratio limit. A real design "
                    "must supply its deflection criterion and provenance explicitly."
                ),
                next_evidence=(
                    "Re-open this gate if nonlinear/time-dependent deflection or a different "
                    "serviceability response model is introduced."
                ),
                legacy_bs_gate=True,
            ),
            AcceptanceItem(
                key="bs_en_reinforcement_detailing",
                title="BS EN reinforcement selection and detailing",
                domain=VerificationDomain.DETAILING,
                state=EvidenceState.ACCEPTED,
                evidence=(
                    "Required steel, minimum steel, discrete cage selection, actual effective-"
                    "depth rechecks, anchorage, station-wise zoning, tension shift/curtailment, "
                    "fatigue, construction-stage stress, laps, end-zone congestion and doubly "
                    "reinforced SLS infrastructure are wired. Published/JRC checks pin "
                    "anchorage, fatigue and EC2 tension shift; Stage D project orchestration "
                    "requires explicit project inputs and reports unresolved items instead of "
                    "inventing defaults."
                ),
                boundary=(
                    "Acceptance is of the V1 software capability, not of any particular bar "
                    "schedule. Fatigue resistance/category, construction-stage stress limits, "
                    "bearing geometry, splice policy and drawing review remain project inputs."
                ),
                next_evidence=(
                    "Keep AdvancedGirderDetailingResult.complete/final_design_ready conservative "
                    "and require explicit project data before any design is called complete."
                ),
            ),
            AcceptanceItem(
                key="legacy_bs_reinforcement_detailing",
                title="Legacy BS reinforcement selection and detailing",
                domain=VerificationDomain.DETAILING,
                state=EvidenceState.ACCEPTED,
                evidence=(
                    "BS 5400-4 source-pinned regressions cover minimum main steel for Grades 460 "
                    "and 250, 4% maximum main steel, side-face reinforcement above 600 mm depth, "
                    "aggregate-plus-5 mm clear spacing, 300 mm tension-bar spacing and 0.75d link "
                    "spacing. Project detailing also exercises discrete cages, links, side-face "
                    "steel, exact station zoning, doubly reinforced cages and advanced Stage D."
                ),
                boundary=(
                    "Legacy fatigue traffic/detail classification and tension-shift/curtailment "
                    "parameters are not invented: advanced Stage D requires an explicit verified "
                    "fatigue vehicle/model and explicit verified legacy tension-shift length. "
                    "Bearing geometry, stress limits, splice policy and drawing review also "
                    "remain project inputs."
                ),
                next_evidence=(
                    "Keep the explicit-input guards conservative and re-open this gate if legacy "
                    "fatigue, anchorage/curtailment or detailing rules are automated further."
                ),
                v1_gate=False,
                legacy_bs_gate=True,
            ),
            AcceptanceItem(
                key="calculation_reporting",
                title="Traceable calculation reporting",
                domain=VerificationDomain.REPORTING,
                state=EvidenceState.ACCEPTED,
                evidence=(
                    "Calculation records require an explicit code basis and preserve formula, "
                    "substitution, result, reference and status fields deterministically."
                ),
                boundary=(
                    "Reporting acceptance covers traceability/presentation only; it does not "
                    "convert a calculation report into independent engineering approval."
                ),
                next_evidence=(
                    "Preserve code-basis and traceability requirements as report formats expand."
                ),
                legacy_bs_gate=True,
            ),
        )
    )
