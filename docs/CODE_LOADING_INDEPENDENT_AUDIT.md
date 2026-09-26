# Code loading independent audit — closed primary BS EN V1, 26 September 2026

## Code basis and scope

The primary modern route is the British-adopted Eurocode family used by this
implementation: **BS EN 1990:2002+A1:2005**, **BS EN 1991-2:2003** and
**BS EN 1992-2:2005**, together with applicable BS EN 1992-1-1 provisions.
Internal package names may retain `eurocode`; user-facing provenance is BS EN.

Recommended Eurocode/JRC verification values are not labelled as Nigerian
National Annex values. Nationally Determined Parameters and authority adoption
remain explicit project inputs.

The legacy BS 5400 / BD 37/01 route remains separate and does not donate
traffic, combination, material or detailing factors to the primary BS EN path.

## BS EN 1991-2 LM1 geometry and adverse UDL search

The source-pinned suite checks the reference 7 m carriageway as two 3 m notional
lanes plus 1 m remaining area, both lane-numbering orientations, both possible
remaining-area edges, complete tandem systems, 1.2 m tandem axle spacing and
2.0 m transverse wheel spacing.

The production BS EN route does not use the historical whole-lane UDL
approximation. It builds a fixed common-grillage plan grid, evaluates unit
pressure cells, searches complete tandem-position vectors and retains only UDL
cells that increase each selected signed response. Governing physical tandem +
selected-UDL cases are then re-solved.

Responses searched include signed member-end bending, shear and torsion,
deflection stations and station-wise moment demand for reinforcement zoning.

### Numerical convergence — CLOSED for the 15 m reference

Search resolution is a numerical verification parameter rather than a code
constant. The repository therefore halves the tandem longitudinal step and
requires exhaustive tandem combinations at every refinement.

The pre-declared acceptance criterion is maximum relative envelope change <= 5%
across girder moment, shear, torsion and deflection.

- **2.4 m -> 1.2 m:** 13.4036%, governed by shear on girder 4 — **REJECTED**.
- **1.2 m -> 0.6 m:** 4.08765%, governed by torsion on girder 2 — **PASS**.
- At 0.6 m the exhaustive search contained 576 theoretical tandem combinations
  per transverse layout and 2,304 evaluated LM1 placements.

GitHub Actions run `36228438781` completed the accepted refinement. Its artifact
`bs-en-lm1-convergence-audit` has digest
`sha256:34c9540cc159ea882f5f65daac8f735caa477b953b24266dd7ff8bd270dc5dfc`.

`ReferenceRunConfig` therefore uses 0.6 m for the 15 m reference. This is not a
universal BS EN discretisation rule; materially different geometries must run
the same convergence process.

## BS EN frequent SLS — CLOSED

The JRC road-bridge verification basis uses distinct frequent LM1 component
factors, 0.75 for tandem systems and 0.40 for UDL. The engine applies those
factors before placement selection rather than rescaling an already-combined
characteristic envelope.

The implementation:

- accepts separate tandem and UDL frequent factors;
- rejects an invalid scalar frequent shortcut when the component factors differ;
- performs a separately weighted influence-surface traffic search;
- maps the weighted traffic case into the frequent combination at factor 1.0;
- retains quasi-permanent road traffic separately.

Genuine STAAD returns for the weighted campaign matched **46,189/46,189**
expected direct-global fields across 17 weighted frequent cases with zero
engineering comparison failures.

These factors are verification values, not a Nigerian National Annex selection.

## BS EN 1990 combinations — CLOSED for focused V1 actions

The primary combination module identifies its basis as BS EN 1990. JRC
road-bridge values are pinned numerically for the implemented permanent and road
traffic actions. Characteristic, frequent and quasi-permanent SLS forms are
kept distinct. Unfavourable/favourable permanent response has an explicit
`Gsup/Ginf` split helper, retaining physical response signs.

The accepted V1 combination scope is the focused primary gravity/road-traffic
action model. Wind, thermal, accidental and other actions are not claimed as
implemented merely because their general Eurocode framework exists.

A real design must record its adopted National Annex/NDP and add any actions
required by the project/authority.

## BS EN concrete design checks

Independent/source-pinned evidence attached to the primary route includes:

- **Flexure:** Concrete Centre published worked beam example; the implementation
  reproduces the published lever arm and required tension steel to rounding when
  the example's explicit `alpha_cc` is supplied.
- **Shear:** JRC concrete-bridge worked example; the implementation reproduces
  the concrete resistance and required vertical-link demand on the example
  basis.
- **Minimum longitudinal steel:** source-pinned
  `max(0.26 fctm/fyk, 0.0013) bt d` form, with overrideable NDP-sensitive
  coefficients.
- **Shear detailing:** minimum-link ratio and link-spacing rules are pinned
  separately from legacy BS 5400.
- **Cracking:** a published example gives approximately 0.184 mm; the production
  close-spacing route calls the same pinned formula.
- **Anchorage:** straight-bar anchorage has a published worked-example
  regression.
- **Tension shift:** `a_l = z(cot(theta)-cot(alpha))/2` is source-pinned.
- **Fatigue:** the reinforcement fatigue calculation reproduces the JRC bridge
  example, including the example's equivalent stress ranges and fatigue
  resistance check.

The external STAAD campaign separately checks the elastic structural responses
feeding the design path.

## Serviceability / deflection boundary

The software does not invent one universal road-bridge deflection limit.
`ProjectDeflectionCriterion` requires the allowable limit and provenance
explicitly. Underlying elastic displacements are externally checked by STAAD,
and the software performs an all-retained-case combined permanent + traffic
search. The project-limit arithmetic/provenance path has a traceable independent
hand-calculation regression.

This closes the V1 software capability while preserving the requirement that a
real project supply its own adopted criterion.

## Reinforcement / Stage D boundary

The primary path separates continuous ULS demand, code minimum steel, discrete
cage generation, actual cage centroid/effective-depth recheck, SLS crack checks,
station-wise demand, curtailment and the advanced Stage D checks.

Advanced Stage D infrastructure covers support anchorage/tension shift,
moving-axle fatigue-to-steel stress range, construction-stage reinforcement
stress, lap/splice zoning, local bearing/end-zone congestion and doubly
reinforced SLS. Source-pinned examples independently check anchorage, EC2
tension shift and fatigue; regression checks exercise the remaining mechanics.

`run_reference_project` now passes the actual LM1 search into basic detailing
and can execute `run_eurocode_advanced_stage_d` when explicit
`AdvancedStageDInputs` are supplied.

Project-specific fatigue resistance/category, construction-stage allowable steel
stress, bearing geometry/resistance, splice limits and drawing-level decisions
remain explicit. Missing or failed project inputs must keep the project result
incomplete; they are not replaced by fictitious defaults.

## Structural solver evidence

The external STAAD evidence set is complete for the verified model family at
**83/83 models**, **410,576/410,576 expected fields** and **zero engineering
comparison failures**. It includes construction stages, permanent components,
characteristic traffic, separately weighted frequent LM1 and corrected
HB/HA+HB output completeness.

## Legacy BS 5400 / BD 37 evidence

Official archived BD 37/01 material remains the primary legacy traffic source.
Tests pin HA UDL/KEL, HB geometry/factors and HA+HB coexistence mechanics.
Legacy external STAAD structural-response evidence is included in the 83-model
campaign.

The owner-supplied Ragana calculation remains a narrow legacy RC benchmark. Its
shear and separately corrected doubly reinforced flexure paths are reproduced.
Its printed crack calculation remains internally inconsistent and is not used as
acceptance evidence. None of those legacy assumptions alters the BS EN path.

## Primary BS EN V1 decision

The focused **BS EN deterministic software capability is GO for V1** within the
documented scope. The formal closure boundary is recorded in
`docs/BS_EN_V1_DETERMINISTIC_CLOSURE.md` and the primary acceptance items in
`src/rc_single_span/verification/acceptance.py` are now accepted.

This software decision does **not** approve a real bridge design. Every real
project still requires actual project actions/materials, the adopted National
Annex/NDP basis, serviceability criteria, fatigue/detailing data, local bearing
geometry and competent engineering review. Expanding the action model, bridge
topology or response formulations re-opens the relevant verification gates.
