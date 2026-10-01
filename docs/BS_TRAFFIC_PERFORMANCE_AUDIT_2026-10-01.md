# BS 5400 traffic progress and duplicate-load optimization audit

The 15 m seven-girder thesis reference was run on the BS 5400 / BD 37 route
with 45 HB units and the explicit coarse search steps in
`scripts/benchmark_bs_traffic.py`: HA 7.5 m, HB 15 m longitudinal / 3.5 m
transverse, and HA+HB 15 m / 3.5 m / 15 m. This is a software-regression grid,
not a BS traffic convergence result or a design-ready search resolution.

| Action | Evaluated placement records | Change |
| --- | ---: | --- |
| HA | 40 | Solves each physical case; placement progress and cancellation |
| HB | 129 | Solves each physical case; spacing and placement progress and cancellation |
| HA+HB | 1,032 | Reuses a solved response only within the same HB vehicle position, stiffness grid and exactly equal ordered physical load geometry and magnitudes; keeps each nominal case ID, load model and governing comparison |

The old reference output was captured before the BS code changed and saved as
[`bs_traffic_coarse_legacy_2026-10-01.json`](benchmarks/bs_traffic_coarse_legacy_2026-10-01.json).
SHA-256: `8f38b98ec6e357c5229bf002268cececc2085a116a5e91a179a20ac68256c698`.
On the same runner, the old full BS route took **7.62 s** and the modified
route **4.20 s** (about **1.81×** faster). Excluding elapsed time, the JSON
outputs were **exactly equal**: HA/HB/HA+HB girder and station envelopes,
member/case IDs, retained case IDs, and BS combination cases/governing values.

The CI gate checks the old and new source on one runner. It does not assert a
fixed speed ratio, since shared-runner timing varies. The GUI now receives
real case counts and cooperative cancellation through all three BS searches.
Cancellation is checked between placement solves and during HA+HB placement
generation. Grillage factorization itself is not interruptible mid-call.

## Default GUI fine-grid comparison

A second same-runner check used the normal GUI reference project and BS 5400
route with design enabled, 45 HB units and `retain_all_cases=false`. The
`ReferenceRunConfig` defaults were HA 1.0 m; HB 1.0 m longitudinal and 0.5 m
transverse; HA+HB 2.0 m HB longitudinal, 1.0 m transverse and 2.0 m HA KEL.
These are current software defaults, **not** a demonstrated convergence grid.

| Search | Placements | Retained physical cases |
| --- | ---: | ---: |
| HA | 612 | 14 |
| HB | 1,845 | 13 |
| HA+HB | 9,672 | 15 |

The pre-optimization commit `d84d423` took **263.73 s**; the current
`0bc6106` source took **150.33 s** with the same capture script and runner,
or **1.75×** faster. A separate interactive optimized run took 128.36 s,
showing ordinary timing variation; the paired 263.73/150.33 s result is the
reported comparison. The full JSON outputs were **exactly identical after
removing elapsed time**: all seven girder and station envelopes, retained case
IDs and physical load records, BS combinations, seven code-specific design
results, and GUI summary rows. No numerical tolerance was used.

Reproduce with `scripts/benchmark_bs_fine.py --root <checkout> --output
<path.json>` on each commit, then use `scripts/compare_bs_traffic.py <old.json>
<new.json>`. The preserved [legacy](benchmarks/bs_traffic_fine_legacy_2026-10-01.json.gz)
and [optimized](benchmarks/bs_traffic_fine_optimized_2026-10-01.json.gz)
records are compressed JSON; the comparison script reads `.json.gz` directly.
Their compressed-file SHA-256 values are
`97ad385beb819a02d661c90dd2bc8c1b122373eb4b58091510d565aba5374dd2`
and `171e89479458066a440055e1690a0b81b3c227fc2d379933d3e510f867b0487e`,
respectively. The CI gate still compares the faster coarse grid on one runner;
this default fine comparison is a preserved local audit, not a CI job.

All-cases retention remains unbenchmarked. The subsequent
[half-step refinement](BS_TRAFFIC_GRID_REFINEMENT_2026-10-01.md) found that the
default HA+HB grid fails the provisional 5% response criterion: girder 5
torsion changes by 7.412%. The speed improvement does not resolve project
loading, code scope or independent bridge-review questions.
