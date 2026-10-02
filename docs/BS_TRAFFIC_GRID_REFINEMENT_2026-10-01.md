# BS 5400 reference traffic-grid refinement

The default GUI 15 m, seven-girder rectangular model, 45 HB units, and
`retain_all_cases=false` were evaluated with the currently optimized engine.
The default search records are from
[`bs_traffic_fine_optimized_2026-10-01.json.gz`](benchmarks/bs_traffic_fine_optimized_2026-10-01.json.gz).
The independent half-step searches are preserved in
[`bs_traffic_halved_grid_2026-10-01.json.gz`](benchmarks/bs_traffic_halved_grid_2026-10-01.json.gz).
The exact snapshot hashes, settings, all girder comparison values, placement
counts and decisions are in
[`bs_traffic_grid_refinement_2026-10-01.json`](benchmarks/bs_traffic_grid_refinement_2026-10-01.json).
Run `python examples/audit_bs_reference_grid.py` to check the stored records;
add `--run` to recalculate the half-step records (several minutes).

| Search | Default steps, m | Half steps, m | Half-step placements | Maximum change / half-step value | Provisional 5% girder test |
| --- | --- | --- | ---: | ---: | --- |
| HA | longitudinal 1.0 | 0.5 | 2,112 | 1.383% (torsion, girder 7) | Pass |
| HB | longitudinal 1.0, transverse 0.5 | 0.5, 0.25 | 5,700 | 1.894% (shear, girder 7) | Pass |
| HA+HB | HB longitudinal 2.0, transverse 1.0, HA KEL 2.0 | 1.0, 0.5, 1.0 | 27,060 | **7.412% (torsion, girder 5)** | **Fail** |

Each comparison covers all seven girders' governing absolute moment, shear,
torsion and deflection magnitudes. The HA KEL-position and HA+HB KEL and lane
assignment searches report **exhaustive** on the refined settings; HB checked
all generated positions. Changing grid steps changes case IDs, so the old/new
case-ID identity gate for engine optimization does not apply here. The
half-step combined search took 486.83 s locally, after 19.56 s for HA and
333.67 s for HB; these are not paired speed benchmarks.

The default BS route **fails** the adopted response-grid check and must not be
reported as converged. The current half-step combined result is a sensitivity
point, not an accepted final grid: another refinement or an independent
continuous placement study is needed. Station moment shape convergence and
all-cases retention were not checked. The GUI and calculation sheets now flag
BS traffic grid status explicitly; design ratios derived from an unverified
traffic envelope remain conditional on its load search.

## Attempted second refinement (2 October 2026)

The next exhaustive combined search was prepared at HB longitudinal 0.5 m,
transverse 0.25 m and HA KEL 0.5 m. The placement generator counts **93,480**
cases over the five HB axle spacings, compared with 27,060 in the saved
half-step search. The reproducible comparison and capture script is
[`audit_bs_combined_second_refinement.py`](../examples/audit_bs_combined_second_refinement.py).

The solver stopped at **case 3**, before a snapshot or envelope could be
produced. Applied vertical load was -1352.611619963 kN, summed reaction
1352.609791229 kN, and the residual -0.001828735 kN exceeded the strict
scale-aware tolerance 0.001352612 kN. The grid had 4,625 nodes, 5,368 members,
and minimum longitudinal/transverse segments 0.005/0.05 m. The HA KEL search
places an edge location at `step/100`, which shrinks to 0.005 m at this
refinement and creates very short elements in a large grillage.

The [reproducible equilibrium probe](../examples/probe_bs_dense_grid_equilibrium.py)
and [its JSON record](benchmarks/bs_dense_equilibrium_probe_2026-10-02.json)
compare the optimized sparse-load assembly to the general prepared solver
using an exactly zero member UDL. The **entire first failing analysis result
is identical** in both paths, including the residual; the new speed branch
did not cause this failure. No tolerance was relaxed, no unconverged result
was exported, and the 93,480-case search has **no accepted outcome**.

A fixed 0.01 m KEL edge position cleared the first 32 placements in a
diagnostic run, but that changes the placement family and is only a lead for
investigation. It is not an accepted second-grid analysis. A numerically
conditioned, consistently nested KEL grid and a repeatable equilibrium audit
are needed before running the next full search. Compare all seven girder
responses and station shapes after that; keep the default BS route labelled
unverified until the required engineering and numerical gates pass.
