# Stage D — Bridge Reinforcement Detailing

Stage D converts a globally adequate longitudinal cage into bridge-specific,
auditable detailing checks. It deliberately does not promote a bar schedule
merely because the midspan ULS steel area is adequate.

The primary modern route is BS EN. Legacy BS 5400 detailing remains separate.

## Basic project-detailing path

The BS EN project detailing path now covers:

- minimum and maximum longitudinal reinforcement limits;
- discrete longitudinal cage generation;
- actual cage centroid/effective-depth calculation and ULS recheck;
- shear-link selection and spacing limits;
- nominal cover checking;
- straight-bar anchorage calculation;
- station-wise reinforcement demand from the actual LM1 traffic search;
- preliminary anchorage-extended curtailment;
- doubly reinforced cage selection and final combined ULS recheck where needed.

The reference runner passes the actual LM1 traffic result into project detailing,
so the station-wise reinforcement envelope and preliminary curtailment path are
not skipped in the BS EN reference workflow.

## Advanced Stage D

`stage_d_project.py` wires the following checks into project-level detailing:

1. **Support anchorage, tension shift and termination.** The BS EN path applies
   the EC2 truss-model tension shift
   `a_l = z(cot(theta)-cot(alpha))/2` to the station-demand curtailment plan.
2. **Moving-axle reinforcement fatigue.** A fatigue vehicle is swept
   longitudinally and converted to cracked-section reinforcement stress range.
   Transverse distribution and fatigue resistance remain explicit.
3. **Construction-stage steel stress.** Permanent actions are accumulated by
   load-time stage and reinforcement stress is checked on the participating
   stage section.
4. **Lap/splice zoning.** End zones are excluded, the fraction of bars spliced
   together is limited and laps are restricted to configured lower-demand zones.
5. **Local bearing/end-zone checks.** Bearing pressure, longitudinal-bar clear
   spacing, link spacing and local reinforcement congestion are reported.
6. **Doubly reinforced SLS.** Selected top and bottom cages are both included in
   the cracked transformed-section service check, including tension/compression
   steel stress and crack control.

## BS EN reference-runner integration

`run_reference_project` accepts explicit `AdvancedStageDInputs` and invokes
`run_eurocode_advanced_stage_d` after the BS EN design and basic detailing
results are available. The resulting `AdvancedGirderDetailingResult` is carried
in `ReferenceRunResult.eurocode_advanced_detailing`.

## Expanded legacy BS 5400 Stage D

The legacy path uses the same generic Stage D mechanics but does not import the
BS EN tension-shift or fatigue load model.

The two code-defined legacy defaults that were previously left as explicit
placeholders are now resolved by `design/bs5400_advanced.py`:

- `bs5400_standard_fatigue_vehicle()` supplies the BS 5400 Part 10 standard
  highway fatigue vehicle: four 80 kN axles with 1.8/6.0/1.8 m longitudinal
  spacings;
- `bs5400_curtailment_extension_m(...)` supplies the BS 5400-4 clause 5.8.7
  continuation beyond a theoretical flexural-bar cutoff as `max(d, 12 phi)`.

`resolve_bs5400_stage_d_code_defaults(...)` inserts those code-defined values
only when the caller has not supplied an explicit adopted legacy value.
`run_bs5400_complete_stage_d(...)` then calls the existing legacy Stage D
orchestration with the resolved inputs.

This does **not** make project-specific fatigue/detailing data universal. Fatigue
resistance/detail class, transverse distribution, design-life/traffic basis,
construction-stage allowable stress, bearing geometry/resistance, splice policy
and local detailing dimensions remain actual project inputs.

Support anchorage also remains separate from the clause 5.8.7 continuation
length. The software therefore does not double-count an invented EC2-style
`tension shift` or borrow the EC2 truss expression into the BS 5400 route.

## Evidence

The implemented Stage D mechanics are protected by regression checks covering:

- support shift and termination extensions;
- the BS 5400 `max(d, 12 phi)` curtailment continuation rule;
- BS 5400 Part 10 standard fatigue-vehicle geometry;
- FLM3/legacy vehicle sweep to reinforcement stress range;
- three construction-stage reinforcement stress states;
- lap/splice zoning;
- local bearing/end-zone pressure, spacing and congestion;
- doubly reinforced SLS with both reinforcement cages.

Independent/source-pinned evidence additionally covers:

- BS EN straight-bar anchorage against a published worked example;
- EC2/JRC tension-shift identity;
- the JRC bridge reinforcement-fatigue example for the BS EN route;
- the historical BS 5400 Part 10 four-axle fatigue vehicle; and
- the BS 5400-4 clause 5.8.7 flexural-bar continuation rule.

## Explicit project inputs remain mandatory

The following cannot safely be inferred and therefore remain explicit inputs:

- fatigue transverse distribution and fatigue resistance/detail category;
- construction-stage allowable reinforcement stress;
- bearing dimensions and allowable bearing pressure;
- end-zone dimensions and congestion limits;
- splice length, exclusion zones and permitted splice fraction;
- actual project cover/aggregate/detailing geometry;
- project National Annex/NDP where the BS EN route is used; and
- legacy authority/project decisions where the BS 5400 route is used.

A missing or failed check is not replaced with a generic project default. The
advanced result is marked `complete` only when all applicable configured checks
resolve and pass. Likewise, project-level reinforcement `final_design_ready`
remains conservative.

## V1 status

The **Stage D software capability is accepted inside both documented V1 code
profiles** within their separate boundaries. The code-defined fatigue vehicle
and curtailment placeholder for the legacy path have now been closed; actual
project data remain mandatory where they genuinely vary by bridge, authority or
detail.

This acceptance does **not** mean a particular reinforcement drawing is approved.
A real bridge still needs its actual project inputs and competent engineering
review before construction use.

See `docs/BS_EN_V1_DETERMINISTIC_CLOSURE.md`,
`docs/BS5400_BD37_EXPANDED_V1_CLOSURE.md`, and the verification gate modules.
