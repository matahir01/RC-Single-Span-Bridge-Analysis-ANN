# Expanded BS 5400 / BD 37 deterministic V1 closure

Date: 26 September 2026

## Decision

The **expanded legacy BS 5400 / BD 37 deterministic software capability** is
accepted for V1 within the scope documented here. This expansion supersedes the
three deliberate software boundaries recorded in the earlier focused closure:

1. combination 4/5 mechanics;
2. the standard highway fatigue vehicle; and
3. the legacy flexural-bar curtailment continuation rule.

This is a software-capability decision, not approval of any particular bridge,
calculation package or reinforcement drawing. BS 5400 is a withdrawn legacy
basis and is to be used only where the project/client/approving authority
explicitly adopts it. The BS EN and legacy BS paths remain numerically isolated.

## Highway combinations 1-5

### Combinations 1-3

The existing HA, HB and HA+HB traffic engine continues to build the primary
highway ULS/SLS cases for combinations 1-3. Official archived BD 37/01 source
checks pin the HA UDL/KEL rules, HB vehicle geometry/factors, coexistence rules
and the implemented primary load factors.

### Combination 4 — secondary live actions

The code layer now represents each secondary live action separately together
with its associated primary live action, as required by BD 37/01. Source-pinned
helpers are implemented for the common highway actions whose factors and nominal
magnitudes are directly defined by clauses 6.9-6.11:

- centrifugal load, including `F_c = 40000/(r + 150)` kN for radii below 1000 m,
  with ULS/SLS gamma_fL 1.50/1.00;
- HA longitudinal traction/braking, `8L + 250` kN capped at 750 kN, with
  ULS/SLS gamma_fL 1.25/1.00;
- HB longitudinal traction/braking, 25% of the total nominal HB vehicle load,
  with ULS/SLS gamma_fL 1.10/1.00;
- accidental skidding, 300 kN, with ULS/SLS gamma_fL 1.25/1.00.

The factor model also supports **different gamma_fL values for the secondary and
associated primary action**. That is required for classified combination-4
cases such as parapet collision/global effects. Those factors are not inferred
from bridge geometry because containment class, massive/light classification,
bearing type and other authority decisions are project-specific. An explicit
`custom_combination4_factors(...)` interface requires both the adopted factors
and provenance.

### Combination 5 — bearing friction

Combination 5 is implemented as factored permanent effects plus the structural
effects of bearing-friction restraint. The BD 37/01 design factor is 1.30 at ULS
and 1.00 at SLS. A helper also derives the nominal friction force from nominal
vertical load and an explicit bearing coefficient of friction.

The coefficient/type of bearing is deliberately not guessed. It remains an
actual project/bearing input.

### Project-level combination layer

`build_bs5400_full_project_combinations(...)` keeps combinations 1-3 from the
native HA/HB/HA+HB engine and adds ULS/SLS combination-4 and combination-5 cases
with provenance. The complete result exposes all ULS and all SLS cases for
governing-envelope selection.

Combination 4 and 5 frequently contain horizontal, local or bearing actions
that a vertical grillage cannot physically represent. The software therefore
requires their **nominal structural effects** from an analysis model appropriate
to the action. It does not convert a scalar horizontal load into invented girder
M/V/T values. This is a modelling boundary of the physical solver, not a missing
combination-rule implementation.

## BS 5400 Part 10 standard fatigue vehicle

The legacy Stage D path no longer requires the code-defined highway fatigue
vehicle to be manually re-entered. `bs5400_standard_fatigue_vehicle()` supplies
the standard 320 kN vehicle as four 80 kN axles with longitudinal spacings:

- 1.8 m;
- 6.0 m;
- 1.8 m.

The vehicle feeds the existing moving-vehicle-to-cracked-reinforcement-stress
range calculation. The standard requires vehicles/lanes to be considered in the
appropriate fatigue assessment; project traffic, detail classification,
resistance curve or allowable resistance and other Part 10/Part 4 fatigue
parameters remain explicit because they are not one universal constant.

## BS 5400-4 flexural-bar curtailment

The normal legacy Stage D wrapper no longer requires an arbitrary user-entered
`tension_shift_length_m` merely to represent the BS flexural-bar continuation
rule. `bs5400_curtailment_extension_m(...)` implements the code continuation
beyond the theoretical cutoff as the greater of:

- effective depth `d`; and
- `12 phi`.

Support anchorage remains a separate detailing requirement and stays explicit.
The implementation therefore does not borrow the EC2 truss-model tension-shift
formula into the BS 5400 route.

`resolve_bs5400_stage_d_code_defaults(...)` and
`run_bs5400_complete_stage_d(...)` provide the expanded legacy path: the
code-defined fatigue vehicle and curtailment continuation are supplied by the
BS route, while genuine project-specific information remains explicit.

## Evidence and regression coverage

The expanded path has regression checks for:

- nominal HA/HB longitudinal actions;
- centrifugal and skidding nominal actions;
- source-pinned combination-4 ULS/SLS factors;
- classified combination-4 cases with distinct secondary/primary factors;
- combination-5 bearing-friction factor and combination arithmetic;
- project-level retention of primary combinations 1-3 plus supplementary 4-5;
- the 4 x 80 kN standard fatigue vehicle and axle spacings;
- the `max(d, 12 phi)` curtailment continuation rule;
- Stage D automatic resolution of the two former legacy placeholders; and
- an explicit expanded legacy acceptance gate.

The previously completed structural-response evidence remains unchanged:
**83/83 STAAD models, 410,576/410,576 expected fields and zero engineering
comparison failures** for the verified V1 model family, including HA, HB and
HA+HB traffic.

## Expanded legacy V1 boundary

The following are **project inputs**, not unresolved code defaults:

- whether a specific secondary action is applicable;
- parapet containment/structural classification and corresponding factors;
- wind, temperature, collision or other action effects from the appropriate
  structural model where required by the project combination;
- bearing type, coefficient of friction and local/bearing response model;
- HB unit count selected by the authority/project;
- fatigue traffic assumptions, detail class/resistance and design life inputs;
- construction-stage allowable reinforcement stress;
- splice policy, bearing/end-zone geometry and allowable local pressure;
- crack-width and deflection acceptance criteria; and
- competent engineering review of the final bridge design.

The software must continue to report a project as incomplete when applicable
inputs are absent. The fact that a code mechanism has a GO software gate is not
permission to fabricate project data.

## Final software position

Within the documented single-span, non-prestressed RC-girder V1 boundary:

- **BS EN deterministic software path: GO**;
- **expanded BS 5400 / BD 37 deterministic software path: GO**.

The expanded legacy gate is implemented in
`src/rc_single_span/verification/legacy_bs_expanded_acceptance.py`. The code
implementations are in:

- `src/rc_single_span/codes/bs5400/secondary.py`;
- `src/rc_single_span/traffic/bs5400_full_combinations.py`; and
- `src/rc_single_span/design/bs5400_advanced.py`.
