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

The default finer BS grids, all-cases retention and design calculation remain
to be timed and checked after this coarse gate. This optimization does not
establish traffic-search convergence, correctness of project load assumptions,
or approval of a real bridge.
