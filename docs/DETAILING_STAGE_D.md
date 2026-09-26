# Stage D — Bridge Reinforcement Detailing

Stage D converts a globally adequate longitudinal cage into bridge-specific,
auditable detailing checks. It deliberately does not promote a bar schedule
merely because the midspan ULS steel area is adequate.

The primary modern route is BS EN. Legacy BS 5400 detailing remains separate and
now has its own accepted focused V1 software boundary.

## Basic project-detailing path

The project detailing infrastructure covers:

- minimum and maximum longitudinal reinforcement limits;
- discrete longitudinal cage generation;
- actual cage centroid/effective-depth calculation and ULS recheck;
- shear-link selection and spacing limits;
- project cover/spacing checks;
- station-wise reinforcement demand from the actual code-specific traffic search;
- preliminary anchorage/curtailment zoning;
- doubly reinforced cage selection and final combined ULS recheck where needed.

For BS EN, the reference runner passes the actual LM1 traffic result into project
detailing. For the legacy BS route, the HA/HB/HA+HB common-grid traffic suite is
passed into the separate BS 5400 reinforcement-envelope/detailing path.

## Advanced Stage D

`stage_d_project.py` wires the following checks into project-level detailing:

1. **Support anchorage, tension shift and termination.** The BS EN path applies
   the EC2 truss-model tension shift
   `a_l = z(cot(theta)-cot(alpha))/2`. The legacy BS path requires an explicit
   verified legacy tension-shift/curtailment input rather than reusing EC2.
2. **Moving-axle reinforcement fatigue.** The BS EN path provides the FLM3
   helper. The legacy path requires an explicit verified fatigue vehicle/model.
   Transverse distribution and fatigue resistance remain explicit project data.
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

`run_reference_project` accepts explicit `AdvancedStageDInputs` and invokes the
code-specific advanced Stage D orchestrator after design and basic detailing are
available. Results are carried separately in:

- `ReferenceRunResult.eurocode_advanced_detailing`; and
- `ReferenceRunResult.bs5400_advanced_detailing`.

The two paths do not share code-specific defaults.

## Evidence

The implemented Stage D mechanics are protected by regression checks covering:

- support shift and termination extensions;
- refusal to invent an unverified legacy BS tension shift;
- moving-vehicle sweep to reinforcement stress range;
- three construction-stage reinforcement stress states;
- lap/splice zoning;
- local bearing/end-zone pressure, spacing and congestion;
- doubly reinforced SLS with both reinforcement cages.

Independent/source-pinned evidence additionally covers the primary BS EN
anchorage, tension-shift and fatigue equations. For the legacy BS route,
source-pinned BS 5400-4 detailing regressions now cover minimum/maximum main
steel, side-face reinforcement, clear bar spacing, tension-bar spacing and beam
link spacing. Legacy fatigue and tension-shift rules remain explicit verified
project inputs instead of invented defaults.

## Explicit project inputs remain mandatory

The following cannot safely be inferred and therefore remain explicit inputs as
applicable to the selected code route:

- fatigue transverse distribution and fatigue resistance/detail category;
- for legacy BS, the verified fatigue vehicle/model and verified legacy
  tension-shift/curtailment input;
- construction-stage allowable reinforcement stress;
- bearing dimensions and allowable bearing pressure;
- end-zone dimensions and congestion limits;
- splice length, exclusion zones and permitted splice fraction;
- actual project cover/aggregate/detailing geometry;
- project National Annex/NDP or other authority requirements.

A missing or failed check is not replaced with a generic default. The advanced
result is marked `complete` only when all configured checks resolve and pass.
Likewise, project-level reinforcement `final_design_ready` remains conservative.

## V1 status

The **Stage D software infrastructure is accepted inside both documented focused
V1 deterministic boundaries**:

- BS EN Stage D software capability: accepted;
- legacy BS 5400 / BD 37 Stage D software capability: accepted when its explicit
  legacy inputs are supplied.

For the legacy route, requiring a verified fatigue model and verified
curtailment/tension-shift input is part of the accepted safety boundary; it is
not an invitation to fabricate a default value.

This acceptance does **not** mean a particular reinforcement drawing is approved.
A real bridge still needs its actual project inputs and competent engineering
review before construction use.

See `docs/BS_EN_V1_DETERMINISTIC_CLOSURE.md`,
`docs/BS5400_BD37_V1_DETERMINISTIC_CLOSURE.md` and
`src/rc_single_span/verification/acceptance.py`.
