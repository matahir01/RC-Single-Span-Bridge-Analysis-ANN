# BS 5400 / BD 37 expanded source audit

Date: 26 September 2026

This note records the source basis for the legacy V1 expansion beyond the
original combinations 1-3 / explicit-placeholder boundary.

## BD 37/01 combination 4

The archived Highways Agency BD 37/01 composite BS 5400 Part 2 source requires
each secondary live load to be considered separately with the corresponding
primary live load in combination 4.

The implementation pins the directly defined highway actions:

| Action | Nominal rule | ULS gamma_fL | SLS gamma_fL | Source |
|---|---|---:|---:|---|
| Centrifugal | `40000/(r+150)` kN for `r < 1000 m` | 1.50 | 1.00 | BD 37/01 6.9 |
| HA longitudinal | `8L + 250` kN, maximum 750 kN | 1.25 | 1.00 | BD 37/01 6.10 |
| HB longitudinal | 25% of total nominal HB load | 1.10 | 1.00 | BD 37/01 6.10 |
| Accidental skidding | 300 kN | 1.25 | 1.00 | BD 37/01 6.11 |

Parapet/collision/global-effect factors depend on containment level, element
classification, structural mass class and/or bearing type. The software does
not infer those classifications. `custom_combination4_factors(...)` requires
separate secondary and associated-primary ULS/SLS factors plus provenance, so
the table values selected by the project/authority can be represented without
forcing the simpler 6.9-6.11 shared-factor pattern.

## BD 37/01 combination 5

BD 37/01 defines combination 5 as permanent loads together with friction at
bearings. Clause 5.4.8.3 gives gamma_fL = 1.30 at ULS and 1.00 at SLS. The
nominal bearing-friction helper keeps the bearing coefficient of friction
explicit rather than assuming a bearing type.

## Structural-effect boundary

Combination 4 and 5 actions are frequently horizontal, local or bearing actions.
The verified common grillage is a vertical-response model. The project-level
full-combination layer therefore accepts nominal structural `LoadEffects` from
an analysis model appropriate to the action and then applies the BS combination
rules. It does not manufacture vertical-girder moments/shears/torsions from a
horizontal force.

This is intentional separation between **code combination mechanics** and the
**structural model required by the action**.

## BS 5400 Part 10 fatigue vehicle

The standard highway fatigue vehicle is implemented as four 80 kN standard
axles, total 320 kN, with longitudinal spacings 1.8 m, 6.0 m and 1.8 m. The
vehicle can be swept through the existing influence/stress-range machinery.

The code-defined vehicle is no longer a manual placeholder. Project/detail
fatigue resistance, traffic/design-life assumptions and applicable detail
classification remain explicit because BS 5400 does not reduce those to one
universal resistance value.

## BS 5400-4 curtailment

The flexural-bar continuation beyond the theoretical point at which a bar is no
longer required is implemented as the greater of effective depth `d` and
`12 phi`. Support anchorage remains separately explicit.

This legacy rule is not replaced with the BS EN/EC2 truss-model tension-shift
expression.

## Acceptance interpretation

The source audit closes the former software placeholders for combination 4/5
mechanics, the standard fatigue vehicle and the basic legacy flexural-bar
curtailment continuation rule. The expanded software gate is separate from the
question of whether a particular project supplies every applicable secondary
action, bearing property, fatigue resistance and detailing input.
