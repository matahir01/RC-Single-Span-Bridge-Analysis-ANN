# Longitudinal Reinforcement Synthesis

The focused bridge application does not treat the minimum ULS tension-steel
area as the final longitudinal reinforcement cage.

The primary modern V1 route is **BS EN**. The legacy BS 5400 / BD 37 route is
kept separate and cannot donate factors, material definitions or detailing
rules to the BS EN design path.

## Design sequence

For each girder the deterministic BS EN path separates:

1. continuous ULS flexural steel demand;
2. code minimum longitudinal steel;
3. discrete cage generation from the available bar diameters and layer limits;
4. actual cage centroid and effective depth;
5. ULS flexural recheck using that actual effective depth;
6. SLS crack-width recheck using the selected bar diameter, spacing, steel area
   and cage centroid;
7. maximum-steel and explicit project deflection acceptance;
8. station-wise reinforcement demand and preliminary curtailment;
9. support anchorage, tension shift and termination extension;
10. moving-axle fatigue-to-steel stress-range checking;
11. construction-stage reinforcement stress checking;
12. lap/splice zoning;
13. local bearing/end-zone congestion checks;
14. SLS verification of selected doubly reinforced cages where required;
15. constructability ranking among cages that pass the implemented checks.

The discrete candidate generator can continue beyond the smallest cage that
satisfies continuous area demand. A nominally efficient cage can therefore be
rejected by actual ULS/SLS/detailing rechecks and replaced by a larger practical
arrangement.

## BS EN source-pinned rules

Independent/source-pinned regressions cover, among other items:

- BS EN 1992 flexural resistance against a published worked example;
- BS EN 1992 shear resistance against the JRC bridge worked example;
- minimum longitudinal reinforcement using the recommended
  `max(0.26 fctm/fyk, 0.0013) bt d` expression;
- minimum shear reinforcement and link-spacing limits;
- straight-bar anchorage against a published worked example;
- crack-width calculation against a published example, with the production
  close-spacing path using the same pinned formula;
- the EC2 truss-model tension-shift expression;
- reinforcement fatigue against the JRC bridge fatigue example.

National Annex/NDP-sensitive coefficients and project acceptance criteria remain
explicit. Recommended Eurocode values are not silently labelled as Nigerian
National Annex values.

## Candidate ranking

A cage is considered for ranking only after it passes every implemented
candidate-sensitive check. Passing cages are ranked transparently by:

1. fewer longitudinal layers;
2. fewer longitudinal bars;
3. lower provided steel area;
4. smaller bar diameter as final tie-break.

This ranking is a constructability heuristic, not a code rule. Available bar
diameters and maximum layer count remain explicit inputs.

## Effective depth

The program does not assume that the design-input effective depth remains the
effective depth of the final recommended cage. For a generated cage it computes
the bar-area centroid from the soffit using cover, link diameter, longitudinal
bar diameter, actual bars per layer and adopted clear vertical spacing. ULS and
crack-width checks are rerun using the resulting centroidal effective depth.

## Demand provenance

The result keeps named demand components distinct. The continuous ULS demand,
code minimum, selected cage, actual centroid, service stress, fatigue stress
range and detailing outputs remain traceable rather than being collapsed into a
single reinforcement number.

## Project-readiness boundary

The **software capability is accepted for focused BS EN V1**, but a particular
bridge cage is not automatically `final_design_ready`.

Project information that cannot safely be inferred remains explicit, including
where applicable:

- National Annex / NDP basis;
- crack-width and deflection criteria;
- fatigue resistance/detail category and fatigue factors;
- construction-stage reinforcement stress limits;
- bearing dimensions and local end-zone geometry/resistance;
- lap/splice policy and drawing-level congestion decisions.

Missing inputs are not replaced with fictitious defaults. The project-level
`final_design_ready` and advanced Stage D `complete` flags therefore remain
conservative and can remain false even though the underlying V1 software
capability has passed its verification gate.

## Verification status

The structural response has a completed external STAAD campaign at 83/83 models
and 410,576/410,576 fields with zero engineering comparison failures. BS EN LM1
search convergence is closed for the 15 m reference at a 0.6 m longitudinal
step (4.08765% change from the 1.2 m refinement, below the adopted 5% criterion).
Published/source-pinned examples cover the primary flexure, shear, cracking,
anchorage, tension-shift and fatigue equations.

The reference runner now feeds the actual LM1 traffic search into reinforcement
zoning/detailing and can invoke the advanced Stage D orchestration when explicit
project inputs are supplied.

See `docs/BS_EN_V1_DETERMINISTIC_CLOSURE.md`,
`docs/BS_EN_LM1_CONVERGENCE_AUDIT.md` and
`src/rc_single_span/verification/acceptance.py` for the accepted V1 software
boundary.
