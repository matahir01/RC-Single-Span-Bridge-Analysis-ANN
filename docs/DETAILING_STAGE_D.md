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
2. **Moving-axle reinforcement fatigue.** An EN 1991-2 FLM3 axle-train helper is
   swept longitudinally and converted to cracked-section reinforcement stress
   range. Transverse distribution and fatigue resistance remain explicit.
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

## Reference-runner integration

`run_reference_project` now accepts explicit `AdvancedStageDInputs` and invokes
`run_eurocode_advanced_stage_d` after the BS EN design and basic detailing
results are available. The resulting `AdvancedGirderDetailingResult` is carried
in `ReferenceRunResult.eurocode_advanced_detailing`.

The same orchestration exists separately for the legacy BS route, but legacy
requirements do not alter the primary BS EN path.

## Evidence

The implemented Stage D mechanics are protected by regression checks covering:

- support shift and termination extensions;
- refusal to invent an unverified legacy BS tension shift;
- FLM3 vehicle sweep to reinforcement stress range;
- three construction-stage reinforcement stress states;
- lap/splice zoning;
- local bearing/end-zone pressure, spacing and congestion;
- doubly reinforced SLS with both reinforcement cages.

Independent/source-pinned evidence additionally covers:

- BS EN straight-bar anchorage against a published worked example;
- EC2/JRC tension-shift identity;
- the JRC bridge reinforcement-fatigue example, including equivalent stress
  ranges and design fatigue resistance.

## Explicit project inputs remain mandatory

The following cannot safely be inferred and therefore remain explicit inputs:

- fatigue transverse distribution and fatigue resistance/detail category;
- construction-stage allowable reinforcement stress;
- bearing dimensions and allowable bearing pressure;
- end-zone dimensions and congestion limits;
- splice length, exclusion zones and permitted splice fraction;
- actual project cover/aggregate/detailing geometry;
- project National Annex/NDP and other authority requirements.

A missing or failed check is not replaced with a generic default. The advanced
result is marked `complete` only when all configured checks resolve and pass.
Likewise, project-level reinforcement `final_design_ready` remains conservative.

## V1 status

The **Stage D software capability is accepted inside the focused BS EN V1
software boundary** because the mechanics are implemented, integrated into the
reference workflow, protected by regression tests and supported by independent
source checks for the critical anchorage/tension-shift/fatigue equations.

This acceptance does **not** mean a particular reinforcement drawing is approved.
A real bridge still needs its actual project inputs and competent engineering
review before construction use.

See `docs/BS_EN_V1_DETERMINISTIC_CLOSURE.md` and
`src/rc_single_span/verification/acceptance.py`.
