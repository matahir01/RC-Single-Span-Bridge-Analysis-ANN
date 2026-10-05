# BS 5400 HA+HB fixed design-station audit

Updated: 5 October 2026. This matched-station audit supersedes the station-shape
figures in the [3 October placement-grid audit](BS_TRAFFIC_GRID_REFINEMENT_2026-10-03.md).
The earlier 26.510% and 26.938% figures compared different station sets and
interpolated the coarse envelope. The audit below samples the same 31 requested
design stations, every 0.5 m from 0 to 15 m, directly in all three searches.
No interpolation is used.

## Reference model and search

The reference is the GUI-default 15 m, seven-girder bridge with 45 HB units.
The HA KEL and HB placement searches use exhaustive, support-anchored,
nested grids. Every solved physical load passed the existing strict
vertical-equilibrium check. All captures use `retain_all_cases=false`; this
audit does not check retention or the all-case combined-deflection search.

Each station-shape change is the maximum absolute difference between the two
search envelopes at the identical requested stations, divided by that girder's
peak fine-grid absolute-moment envelope. Girder response-envelope change is the
largest relative change across moment, shear, torsion and deflection.

| Refinement | HA KEL / HB longitudinal / HB transverse (m) | Placements | Girder response-envelope change | Fixed-station moment-shape change | 5% screen |
| --- | --- | ---: | --- | --- | --- |
| Default → half | 2.0 / 2.0 / 1.0 → 1.0 / 1.0 / 0.5 | 9,672 → 27,060 | **4.889%**, torsion, girder 5 | **6.714%**, girder 2 at x = 13.0 m | Fail |
| Half → fine | 1.0 / 1.0 / 0.5 → 0.5 / 0.5 / 0.25 | 27,060 → 91,200 | **1.250%**, shear, girder 1 | **3.513%**, girder 4 at x = 13.5 m | Pass |

The fine search completed in 2,219.8 s on the capture machine. These elapsed
times are run records, not paired performance benchmarks. The first refinement
still fails the provisional station-shape screen, so the reference BS grid
remains **unverified**. A second-refinement pass does not establish global
convergence or bound changes between the 31 evaluation stations. Do not use
this audit alone to justify reinforcement zoning or a project design.

## Captures and reproduction

The compressed [default](benchmarks/bs_traffic_designstations_default_2026-10-05.json.gz),
[half-step](benchmarks/bs_traffic_designstations_half_2026-10-05.json.gz) and
[fine](benchmarks/bs_traffic_designstations_fine_2026-10-05.json.gz) snapshots
record settings, placements, all design-station responses and snapshot hashes.
The [machine-readable comparison](benchmarks/bs_traffic_grid_refinement_designstations_2026-10-05.json)
records per-girder changes and the evaluation method.

Regenerate all captures and the comparison on the reference project with:

```bash
python examples/audit_bs_combined_second_refinement.py \
  --run-default --run-half --run \
  --default docs/benchmarks/bs_traffic_designstations_default_2026-10-05.json.gz \
  --half docs/benchmarks/bs_traffic_designstations_half_2026-10-05.json.gz \
  --fine docs/benchmarks/bs_traffic_designstations_fine_2026-10-05.json.gz \
  --output docs/benchmarks/bs_traffic_grid_refinement_designstations_2026-10-05.json
```

This is a numerical search-sensitivity check only. Project-specific actions,
code applicability, reinforcement and shear-link details, serviceability
criteria, and independent engineering review remain separate requirements.
