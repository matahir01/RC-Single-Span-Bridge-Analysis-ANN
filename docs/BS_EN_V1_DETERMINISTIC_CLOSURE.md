# BS EN deterministic V1 closure record

Date: 26 September 2026

## Decision

The focused **BS EN deterministic software capability** for the repository is
accepted for V1 within the documented scope below. This is a software
verification/release decision, not approval of any particular bridge design or
construction drawing.

A real project can still be incomplete or fail. Nationally Determined
Parameters, project action models, crack/deflection criteria, fatigue data,
bearing geometry, construction-stage stress limits, splice rules and other
project-specific inputs remain explicit. The program must continue to return an
incomplete/not-ready result when those inputs are absent or when a check fails.

## Accepted V1 scope

- simply supported single-span non-prestressed RC girder bridges;
- rectangular, T and I longitudinal girder profiles supported by the V1 model;
- composite RC deck and the documented three-stage unpropped construction path;
- common full-width grillage structural analysis;
- BS EN 1991-2 LM1 loading with response-specific adverse UDL regions;
- BS EN 1990 primary gravity/road-traffic ULS and SLS combinations implemented
  by the focused action model;
- BS EN 1992 flexure, shear, cracking and elastic-response deflection logic;
- discrete longitudinal and shear reinforcement selection;
- anchorage, curtailment/tension shift, fatigue, construction-stage steel
  stress, lap zoning, local bearing/end-zone congestion and doubly reinforced
  SLS infrastructure when their explicit project inputs are supplied;
- traceable calculation records with an explicit code basis.

Items outside that scope remain outside V1 rather than silently approximated.
Examples include continuous spans, prestressing, curved bridges, general
substructure/foundation design, general local-deck design, staged continuity,
changing supports, arbitrary propping/removal sequences and advanced
creep/shrinkage redistribution.

## Structural-response evidence

The common solver/export path has genuine STAAD.Pro evidence for the reference
model family:

- 83/83 external models returned;
- 410,576/410,576 expected direct-global fields present;
- zero engineering comparison failures;
- construction stages, permanent components, characteristic traffic, weighted
  frequent LM1 and corrected HB/HA+HB output completeness included.

This closes the V1 structural-response capability. It does not validate a code
factor or project detailing choice by itself.

## BS EN 1991-2 LM1 loading evidence

Source-pinned checks cover notional lanes, remaining areas, characteristic LM1
resultants, complete tandem systems, 1.2 m axle spacing, 2.0 m transverse wheel
spacing, separate frequent tandem/UDL factors and adverse-only UDL regions.

The response-specific influence-surface search has an explicit convergence
record for the 15 m, 7 m-carriageway reference bridge:

- 2.4 m -> 1.2 m: rejected at 13.4036% maximum envelope change;
- 1.2 m -> 0.6 m: accepted at 4.08765% maximum envelope change;
- adopted criterion: 5%;
- governing second-refinement quantity: torsion on girder 2;
- 0.6 m search: 576 theoretical tandem combinations per transverse layout,
  2,304 evaluated LM1 placements, exhaustive search retained.

The tolerance was not widened to obtain a pass. `ReferenceRunConfig` therefore
uses 0.6 m for this reference bridge. Other bridge geometries must establish
their own numerical convergence rather than treating 0.6 m as a BS EN rule.

## BS EN 1990 combination evidence

The implemented primary gravity/traffic combination path is source-pinned to the
JRC road-bridge examples and separates characteristic, frequent and
quasi-permanent SLS forms. Frequent LM1 is searched with tandem and UDL factors
applied before placement selection when those factors differ. Unfavourable and
favourable permanent effects have an explicit split helper.

National Annex/NDP values are deliberately not inferred from geography. A real
project must state the adopted authority/basis.

## BS EN 1992 resistance and serviceability evidence

The production resistance/serviceability kernels are tied to independent
worked examples or external response evidence:

- flexure: Concrete Centre published beam example;
- shear: JRC concrete-bridge worked example;
- minimum longitudinal reinforcement and shear-detailing limits: source-pinned
  BS EN/EC2 expressions;
- cracking: published worked example reproducing approximately 0.184 mm;
- elastic structural displacement: independently checked by the completed STAAD
  campaign;
- combined permanent + traffic deflection search: all-case response search plus
  explicit hand-arithmetic regression for the project-selected acceptance
  criterion.

There is intentionally no hidden universal road-bridge span-ratio limit.
`ProjectDeflectionCriterion` requires the limit and its provenance explicitly.

## Reinforcement and Stage D evidence

The deterministic detailing path keeps continuous demand, minimum steel,
discrete cages, actual cage centroid/effective depth, ULS/SLS rechecks and
bridge-specific Stage D checks separate.

Independent/source-pinned evidence exists for straight-bar anchorage, the EC2
truss-model tension shift and JRC reinforcement fatigue. Regression checks also
exercise station-wise reinforcement zoning, construction-stage steel stress,
lap/splice zoning, local bearing/end-zone pressure and congestion, and doubly
reinforced SLS checks. The reference runner now passes the actual traffic search
into basic detailing and can run the advanced Stage D orchestration when
`AdvancedStageDInputs` are supplied.

Acceptance of the software capability does **not** mean those project checks are
automatically satisfied. `AdvancedGirderDetailingResult.complete` and the
reinforcement `final_design_ready` boundary remain conservative: missing
project inputs or failed checks must keep a design incomplete.

## Reporting evidence

Calculation records require an explicit code basis and preserve formula,
substitution, result, reference and status fields. Reporting acceptance means
that the traceability mechanism is suitable for V1; it does not turn a report
into independent engineering approval.

## Legacy route

BS 5400 / BD 37/01 remains available as a separate legacy profile. It is not a
blocker to the primary BS EN V1 decision and must not donate material, loading,
combination or detailing factors to the BS EN path. Legacy capabilities retain
their own evidence states in the acceptance matrix.

## Release interpretation

**GO to move beyond the BS EN deterministic V1 software-verification phase.**

This permits downstream deterministic dataset generation and ANN/reliability/
RBDO development using the accepted V1 capability boundary. Any production
bridge design still requires its actual project basis, National Annex/NDP
choices, explicit serviceability/detailing inputs and competent engineering
review before construction use.
