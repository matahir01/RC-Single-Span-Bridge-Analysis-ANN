# Longitudinal Reinforcement Synthesis

The focused bridge application does not treat the minimum ULS tension-steel
area as the final longitudinal reinforcement cage.

The primary modern V1 route is **BS EN**. The legacy BS 5400 / BD 37 route is
kept separate and must not donate factors, material definitions or detailing
rules to the BS EN design path.

## Design sequence

For each girder the deterministic design path separates:

1. continuous ULS flexural steel demand;
2. code minimum longitudinal steel;
3. discrete cage generation from the available bar diameters and layer limits;
4. actual cage centroid and effective depth;
5. ULS flexural recheck using that actual effective depth;
6. SLS crack-width recheck using the actual selected bar diameter, centre
   spacing, steel area and cage centroid;
7. maximum-steel and configured deflection acceptance;
8. station-wise reinforcement demand and preliminary curtailment;
9. support anchorage, tension shift and termination extension;
10. moving-axle fatigue-to-steel stress-range checking;
11. construction-stage reinforcement stress checking;
12. lap/splice zoning;
13. local bearing/end-zone congestion checks;
14. SLS verification of selected doubly reinforced cages where required;
15. constructability ranking among cages that pass the implemented checks.

The discrete candidate generator is intentionally allowed to continue beyond
the smallest cage that satisfies the continuous area requirement. A nominally
efficient cage can therefore be rejected by the actual ULS/SLS/detailing
rechecks and the design can move to a larger practical arrangement.

## BS EN source-pinned rules

The primary route now has independent/source-pinned regression checks for, among
other items:

- BS EN 1992 flexural resistance against a published worked example;
- BS EN 1992 shear resistance against the JRC bridge worked example;
- minimum longitudinal reinforcement using the recommended
  `max(0.26 fctm/fyk, 0.0013) bt d` expression;
- minimum shear reinforcement and link-spacing limits;
- straight-bar anchorage against a published worked example;
- crack-width calculation against a published example, with the production
  close-spacing path calling the same source-pinned formula;
- the EC2 truss-model tension-shift expression;
- reinforcement fatigue against the JRC bridge fatigue example.

Where a coefficient or limit can be changed by a National Annex, project
specification or approval authority, it remains an explicit input. Recommended
Eurocode values are not silently labelled as Nigerian National Annex values.

## Candidate ranking

A cage is considered for ranking only after it passes every currently
implemented candidate-sensitive check. Passing cages are ranked transparently
by:

1. fewer longitudinal layers;
2. fewer longitudinal bars;
3. lower provided steel area;
4. smaller bar diameter as the final tie-break.

This ranking is a constructability heuristic, not a code provision. The
available bar diameters and maximum layer count remain explicit user/design
inputs.

## Effective depth

The program does not assume the design-input effective depth is automatically
the effective depth of the final recommended cage. For a generated cage it
computes the bar-area centroid from the soffit using:

- nominal cover;
- selected link diameter;
- longitudinal bar diameter;
- actual number of bars in each layer;
- actual adopted clear vertical layer spacing.

The ULS and crack-width checks are then rerun using the resulting centroidal
effective depth.

## Demand provenance

The result carries named demand components. A numerical steel area is reported
only where the deterministic implementation genuinely solves one. The design
path keeps the continuous ULS demand, code minimum, selected cage, actual
centroid, service stress, fatigue stress range and detailing outputs distinct so
that a later report can show how each recommendation was obtained.

Project-specific information that cannot safely be inferred remains explicit,
including where applicable:

- the National Annex / NDP basis;
- crack-width and deflection acceptance criteria;
- fatigue resistance/detail category and project fatigue factors;
- construction-stage reinforcement stress limits;
- bearing dimensions and local end-zone geometry;
- lap locations and drawing-level congestion decisions.

These unresolved project inputs are not replaced with fictitious defaults.
`final_design_ready` therefore remains conservative until every required
project-specific check is supplied and passes.

## Verification status

Implementation is not the same as engineering acceptance. The software's
structural response has a completed external STAAD comparison campaign, while
BS EN loading, resistance, serviceability and detailing are being closed with
source-pinned examples, hand calculations and convergence evidence. See the
acceptance matrix and `docs/BS_EN_LM1_CONVERGENCE_AUDIT.md` for the current
boundary.
