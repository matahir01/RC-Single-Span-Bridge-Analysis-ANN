# Longitudinal Reinforcement Synthesis

The focused bridge application no longer treats the minimum ULS tension-steel
area as the final longitudinal reinforcement cage.

## Design sequence

For each girder the deterministic design path now separates:

1. continuous ULS flexural steel demand;
2. code minimum longitudinal steel;
3. discrete cage generation from the available bar diameters and layer limits;
4. actual cage centroid and effective depth;
5. ULS flexural recheck using that actual effective depth;
6. SLS crack-width recheck using the actual selected bar diameter, centre
   spacing, steel area and cage centroid;
7. maximum-steel and configured deflection acceptance;
8. constructability ranking among cages that pass the implemented checks.

The discrete candidate generator is intentionally allowed to continue beyond
the smallest cage that satisfies the continuous area requirement. This means a
nominally efficient cage can be rejected by the actual ULS/SLS rechecks and the
design can move to a larger arrangement.

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

The program no longer assumes the design-input effective depth is automatically
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
only where the current deterministic implementation genuinely solves one.

Currently numerical demands are available for:

- ULS flexure;
- code minimum longitudinal steel.

SLS crack control is enforced directly by candidate re-analysis rather than
being converted to an artificial independent area formula.

The following are deliberately reported as outstanding instead of being
invented:

- fatigue-specific reinforcement/stress-range design;
- construction-stage reinforcement stress/resistance;
- anchorage and curtailment;
- drawing-level local congestion and end-zone detailing;
- BS side-face steel integration into the final cage.

Accordingly, the synthesis result exposes `final_design_ready = False` until
those bridge-specific checks are implemented and accepted.

## Why this change matters

The previous detailing path could calculate a continuous ULS requirement and
immediately choose the least-area discrete cage that fitted the web. That is a
valid bar-fitting operation, but it is not a complete bridge reinforcement
design.

The revised path distinguishes:

`A_s,ULS -> candidate cages -> actual d -> ULS recheck -> SLS crack recheck -> recommended cage`

and retains the remaining bridge-design checks explicitly rather than silently
promoting a ULS-only cage to final reinforcement.
