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

### Secondary legacy route

BS 5400 / BD 37/01 is retained as a **legacy** profile for older projects and
comparison work. It remains separate from BS EN; traffic, material, resistance
and detailing factors are not borrowed between the two routes.

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
reinforced SLS checking. `run_reference_project` can now execute the advanced
Stage D orchestration when explicit `AdvancedStageDInputs` are supplied.

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

## Legacy BS 5400 / BD 37

The legacy path remains available and independently tracked. Official archived
BD 37/01 evidence pins HA/HB/HA+HB mechanics and primary combinations 1-3. The
Ragana calculation is retained as a narrow legacy RC benchmark. Unfinished
legacy-detailing evidence does **not** block the primary BS EN V1 gate.

## Deterministic V1 release position

**GO — the focused BS EN deterministic software capability is accepted for V1
within the documented scope.**

The acceptance matrix now closes the primary BS EN software-capability gate, and
the deterministic engine may move on to dataset generation, ANN surrogate work,
reliability analysis and RBDO within that accepted V1 boundary.

This is **not** approval of a particular bridge for construction. Every real
project still requires its adopted National Annex/NDP basis, actual actions and
materials, project serviceability criteria, fatigue/detailing inputs, bearing
geometry and competent engineering review. A project with missing inputs or
failed checks must remain not-ready even though the underlying V1 software
capability is accepted.

See:

- `docs/BS_EN_V1_DETERMINISTIC_CLOSURE.md`;
- `src/rc_single_span/verification/acceptance.py`;
- `docs/CODE_LOADING_INDEPENDENT_AUDIT.md`;
- `docs/REINFORCEMENT_SYNTHESIS.md`;
- `docs/DETAILING_STAGE_D.md`.
