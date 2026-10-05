# BS 5400 HA+HB support-anchored grid audit

Updated: 3 October 2026. This follow-up replaces the failed dense-grid attempt
in the [1 October audit](BS_TRAFFIC_GRID_REFINEMENT_2026-10-01.md) for the
current placement generator. The older measurements remain historical; their
step-dependent KEL edge coordinates are not comparable with the new search.

**The station-shape measurements in this historical 3 October audit are
superseded by the matched fixed-design-station audit from 5 October.** Its
26.510% and 26.938% values used different station sets and coarse interpolation;
the corrected direct comparisons are reported in
[BS_TRAFFIC_DESIGN_STATION_AUDIT_2026-10-05.md](BS_TRAFFIC_DESIGN_STATION_AUDIT_2026-10-05.md).
Use that audit for current GUI/report sensitivity figures.

## Placement-grid change

HA KEL positions now start at the supports and advance from `x = 0` by the
requested step, with bridge midspan included. The support coordinates are
existing grillage stations, so edge placements do not create the former
`step / 100` short members. The KEL step must be at least 0.05 m; a final
interior point is omitted if it would leave a smaller-than-0.05 m interval to
the support. The standard 2.0, 1.0 and 0.5 m grids are nested. This is a
numerical conditioning rule for this placement search, not a code-prescribed
traffic offset.

## Matched reference searches

The audits use the GUI-default 15 m, seven-girder bridge, 45 HB units and
`retain_all_cases=false`. All three searches were exhaustive for lane assignments
and KEL combinations, used matching halved steps, and passed the strict
scale-aware vertical-equilibrium check for every solved physical load.

| Refinement | HA KEL / HB longitudinal / HB transverse (m) | Placements | Maximum girder M/V/T/deflection change | Station-shape change | 5% screen |
| --- | ---: | ---: | --- | --- | --- |
| Default → half | 2.0 / 2.0 / 1.0 → 1.0 / 1.0 / 0.5 | 9,672 → 27,060 | **6.809%**, torsion, girder 5 | **26.510%**, girder 7 at x = 7.2 m | Fail |
| Half → fine | 1.0 / 1.0 / 0.5 → 0.5 / 0.5 / 0.25 | 27,060 → 91,200 | 1.894%, shear, girder 1 | **26.938%**, girder 7 at x = 7.7 m | Fail |

The station-shape comparison interpolates the coarse absolute-moment envelope
linearly onto every fine-grid station. It normalizes each girder's maximum
pointwise change by that girder's peak fine-grid moment envelope, which avoids
unstable ratios near zero. This shows sizeable station-wise changes even though
the finer M/V/T/deflection maxima change by less than 5%; station-wise
reinforcement zoning is therefore still sensitive to search resolution.

The 0.5 / 0.5 / 0.25 m search completed in 2,127.7 s on the capture machine.
The timings in the snapshots are local runtimes, not paired performance
benchmarks. The [compressed default](benchmarks/bs_traffic_anchored_default_grid_2026-10-03.json.gz),
[half-step](benchmarks/bs_traffic_anchored_halved_grid_2026-10-03.json.gz),
[fine](benchmarks/bs_traffic_anchored_second_refinement_2026-10-03.json.gz)
snapshots and [hash-backed comparison](benchmarks/bs_traffic_grid_refinement_2026-10-03.json)
record the per-girder envelopes, station moments, settings, retained cases,
exhaustiveness and hashes.

## Decision

The support-anchored 0.5 m search resolved the previous case-3 equilibrium
failure: all **91,200** placements passed the existing strict gate. It does
not establish grid convergence. Default-to-half exceeds the provisional 5%
envelope screen, and both pairings exceed the 5% station-shape screen. The GUI
and calculation report therefore continue to mark BS traffic grids
**unverified**. Do not use these results to justify reinforcement zoning or a
project design without further refinement and independent review.

The [32-case equilibrium probe](benchmarks/bs_dense_equilibrium_probe_2026-10-03.json)
also passed before the full run. Reproduce the exhaustive snapshots and audit
with `python examples/audit_bs_combined_second_refinement.py --run-default
--run-half --run`; the fine search takes tens of minutes on the reference
runner. The audit checks response envelopes and station shapes, not all-cases
retention, code applicability or real-bridge approval.
