# RC Single-Span Bridge Analysis & ANN

A focused engineering application for simply supported, single-span,
non-prestressed reinforced-concrete girder bridges.

The deterministic analysis/design engine is the primary product. ANN surrogate
modelling, reliability analysis and RBDO are downstream capabilities built on
that deterministic engine.

## Design basis

One physical bridge model is shared by all code profiles:

`physical bridge -> code-specific traffic/combinations -> common structural solver -> code-specific RC design`

### Primary modern V1 route: BS EN

The primary route is explicitly the British-adopted first-generation Eurocode
bridge family used by this implementation:

- **BS EN 1990:2002+A1:2005** — basis and combinations;
- **BS EN 1991-2:2003** — bridge traffic actions;
- **BS EN 1992-2:2005** — concrete bridges, together with applicable
  BS EN 1992-1-1 provisions.

Internal modules may retain `eurocode` in Python package names, but user-facing
provenance is BS EN. National Annex / Nationally Determined Parameter choices
remain explicit project inputs. Recommended Eurocode values are not silently
labelled as Nigerian National Annex values, and UK NA values are used only when
the project/client/approving authority adopts them.

### Secondary legacy route: BS 5400 / BD 37

BS 5400 / BD 37/01 is retained as a **legacy** deterministic profile for older
projects, owner/authority requirements and comparison work. Its expanded V1
software-capability gate is separately accepted; it remains isolated from BS EN
and traffic, material, resistance and detailing factors are not borrowed between
the two routes.

BS 5400-4:1990 is a withdrawn legacy standard. Software acceptance of this path
is therefore not a recommendation to select it for a new project: the adopted
project/authority basis must explicitly require the legacy route.

## Focused V1 scope

V1 covers:

- simply supported, one-span, non-prestressed RC girder bridges;
- rectangular, T and I longitudinal girder profiles supported by the model;
- composite reinforced-concrete deck;
- three-stage unpropped construction response: precast girder,
  deck-construction and final hardened-composite stages;
- full-width grillage analysis and transverse distribution;
- BS EN 1991-2 LM1 traffic with response-specific adverse UDL regions;
- BS EN 1990 primary gravity/road-traffic ULS/SLS combinations;
- legacy BD 37/01 HA, HB and HA+HB traffic;
- legacy BS 5400 / BD 37 highway combinations 1-5, with supplementary
  horizontal/local/bearing response supplied by an analysis model appropriate
  to the action when it lies outside the vertical-grillage response space;
- BS 5400 Part 10 standard highway fatigue-vehicle generation;
- BS 5400-4 flexural-bar curtailment continuation using `max(d, 12 phi)`;
- flexure, shear, cracking and elastic-response deflection checks;
- discrete reinforcement selection and bridge-specific detailing infrastructure;
- traceable calculation records carrying code basis, formula, substitution,
  result, reference and status.

Continuous spans, prestressing, curved bridges, general substructure/foundation
design, general local-deck design, staged continuity, changing supports,
arbitrary propping/removal sequences and advanced creep/shrinkage
redistribution remain outside focused V1.

## Reference bridge

The main verification bridge is the 15 m single-span, seven-girder reference:
seven girders at 1.70 m spacing, 400 x 950 mm precast rectangular girders,
11.0 m overall deck and a 75 + 175 mm deck build-up. Benchmark permanent actions
and material values in `examples/reference_bridge_15m.py` are explicitly labelled
verification assumptions where they are not project/as-built data.

## Structural-analysis verification — CLOSED

The common solver/export path has genuine external STAAD evidence:

- **83/83 external models**;
- **410,576/410,576 expected direct-global fields**;
- **zero engineering comparison failures**.

The campaign covers construction stages, permanent-component response,
characteristic traffic, separately weighted frequent LM1 traffic and corrected
HB/HA+HB output completeness.

This verifies structural response for the accepted V1 model family. It does not
by itself approve traffic-code choices, National Annex values, reinforcement or
a real bridge project.

See `docs/STAAD_EXTERNAL_VERIFICATION_2026-09-25.md` and
`docs/STAAD_WEIGHTED_FREQUENT_EXTERNAL_VERIFICATION_2026-09-25.md`.

## BS EN 1991-2 LM1 — CLOSED FOR THE 15 m REFERENCE

The production BS EN path uses a response-specific signed influence-surface
search. Complete tandem systems are searched, unit-pressure carriageway cells
are evaluated, only adverse UDL cells are retained for each signed response,
and the governing physical tandem + selected-UDL cases are re-solved.

Source-pinned tests cover notional lanes, remaining areas, characteristic
resultants, complete tandem geometry, 1.2 m axle spacing, 2.0 m transverse wheel
spacing and separate frequent tandem/UDL factors.

The numerical search-resolution audit retained its pre-declared 5% criterion:

- 2.4 m -> 1.2 m: **13.4036%**, rejected;
- 1.2 m -> 0.6 m: **4.08765%**, accepted;
- second-refinement governing response: torsion, girder 2;
- 0.6 m search: 576 theoretical tandem combinations per transverse layout and
  2,304 evaluated LM1 placements, with exhaustive tandem search retained.

`ReferenceRunConfig` now uses **0.6 m** for this 15 m reference bridge. That is a
verified numerical setting for this geometry, not a universal BS EN rule; a
materially different bridge geometry must establish its own convergence.

See `docs/BS_EN_LM1_CONVERGENCE_AUDIT.md`.

## BS EN frequent SLS — CLOSED

The frequent-LM1 implementation weights tandem and UDL components before the
placement search when their factors differ. The source-reference values used in
the verification campaign were 0.75 for the tandem system and 0.40 for UDL,
with quasi-permanent road traffic 0.0. Those are verification values, not an
automatic Nigerian NA selection.

The weighted external STAAD campaign matched **46,189/46,189** expected fields
for 17 frequent cases with zero engineering comparison failures.

## BS EN concrete design and detailing evidence

The primary route has independent/source-pinned checks for:

- flexure against a published Concrete Centre worked beam example;
- shear against the JRC concrete-bridge worked example;
- minimum longitudinal reinforcement and shear-detailing limits;
- crack width against a published example (approximately 0.184 mm);
- straight-bar anchorage against a worked example;
- EC2 tension shift;
- reinforcement fatigue against the JRC bridge example.

The design/detailing path also contains discrete cage selection, actual cage
centroid/effective-depth rechecks, station-wise reinforcement zoning,
curtailment, moving-axle fatigue-to-steel stress range, construction-stage steel
stress, lap/splice zoning, local bearing/end-zone congestion and doubly
reinforced SLS checking. `run_reference_project` can execute the advanced Stage
D orchestration when explicit `AdvancedStageDInputs` are supplied.

Project-specific inputs that cannot safely be inferred remain explicit. Missing
or failing fatigue, construction-stage, bearing, splice or serviceability inputs
must continue to leave the project result incomplete; software V1 acceptance is
not permission to invent them.

## Deflection basis

There is deliberately no hidden universal road-bridge span-ratio limit.
`ProjectDeflectionCriterion` requires the selected limit and its provenance.
Underlying elastic displacements have external STAAD evidence, and the software
re-searches combined permanent + traffic displacement across retained traffic
cases. See `docs/BS_EN_DEFLECTION_BASIS.md`.

## Legacy BS 5400 / BD 37 — EXPANDED V1 CLOSED

The legacy path has an independent deterministic acceptance gate and an expanded
closure layer for the items that were previously left as deliberate boundaries.

The evidence package includes:

- official archived BD 37/01 source checks for HA, HB and HA+HB mechanics;
- combinations 1-3 from the native primary traffic engine;
- combination 4 source-pinned centrifugal, HA/HB longitudinal and skidding
  actions, plus an explicit factor/provenance interface for classified secondary
  actions such as parapet/collision effects;
- combination 5 permanent actions plus bearing-friction response at gamma_fL
  1.30 ULS / 1.00 SLS;
- a project-level full-combination layer retaining ULS/SLS combinations 1-5;
- genuine external STAAD response evidence for the verified BS traffic models;
- the owner-supplied Ragana shear benchmark;
- the separately reproduced Ragana doubly reinforced flexure benchmark;
- an independent BS 5400-4 crack-width worked example reproducing approximately
  96.9 mm compression depth, 87 mm `a_cr` and 0.22 mm crack width;
- source-pinned BS 5400-4 reinforcement/detailing limits for minimum/maximum
  main steel, side-face reinforcement, clear spacing, tension-bar spacing and
  beam-link spacing;
- the BS 5400 Part 10 standard 320 kN fatigue vehicle as four 80 kN axles at
  1.8/6.0/1.8 m spacing;
- the BS 5400-4 flexural-bar continuation rule `max(d, 12 phi)` beyond a
  theoretical cutoff; and
- discrete cage/link selection, station-wise reinforcement zoning, fatigue
  stress-range assessment, construction-stage stress, laps, bearing/end-zone
  checks, doubly reinforced SLS and advanced Stage D infrastructure.

`build_bs5400_full_project_combinations(...)` deliberately accepts structural
effects from an analysis model appropriate to each secondary/local/bearing
action. The vertical grillage is not allowed to fabricate horizontal response.
Likewise, fatigue resistance/detail category, bearing coefficient/type,
applicable secondary actions, project crack/deflection limits and other genuine
project choices remain explicit inputs rather than hidden defaults.

See `docs/BS5400_BD37_EXPANDED_V1_CLOSURE.md`.

## Deterministic V1 release position

**GO — both deterministic software profiles are accepted within their documented
V1 scopes:**

- **BS EN V1: GO**;
- **expanded legacy BS 5400 / BD 37 V1: GO**.

The two acceptance gates are independent. A future change to one code path must
not silently alter the other.

The deterministic engine may therefore move on to dataset generation, ANN
surrogate work, reliability analysis and RBDO using the code profile deliberately
selected for that study/project and only within its accepted deterministic
boundary.

This is **not** approval of a particular bridge for construction. Every real
project still requires its adopted code/authority basis, actual actions and
materials, project serviceability criteria, fatigue/detailing inputs, bearing
geometry and competent engineering review. A project with missing inputs or
failed checks must remain not-ready even though the underlying software
capability is accepted.

See:

- `docs/BS_EN_V1_DETERMINISTIC_CLOSURE.md`;
- `docs/BS5400_BD37_EXPANDED_V1_CLOSURE.md`;
- `src/rc_single_span/verification/acceptance.py`;
- `src/rc_single_span/verification/legacy_bs_expanded_acceptance.py`;
- `docs/CODE_LOADING_INDEPENDENT_AUDIT.md`;
- `docs/REINFORCEMENT_SYNTHESIS.md`;
- `docs/DETAILING_STAGE_D.md`.
