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

The subsequent
[half-step refinement](BS_TRAFFIC_GRID_REFINEMENT_2026-10-01.md) found that the
default HA+HB grid fails the provisional 5% response criterion: girder 5
torsion changes by 7.412%. The speed improvement does not resolve project
loading, code scope or independent bridge-review questions.

## Rejected load-indexing experiment

After this audit, a trial changed the prepared solver to group uniform and
point loads by member before each placement. The full default BS outputs were
identical to the preserved optimized snapshot. In a sequential same-machine
comparison, however, the previous source took **150.92 s** and the trial took
**176.32 s** (0.86×). The trial was **reverted** and is not in the executable.
The next performance batch should profile physical case assembly and solves,
then test a response-basis or batched-solve approach against exact physical
case and design outputs. Speed must be measured on paired runs before adoption.

## 2 October 2026 sparse traffic-load assembly

A subsequent profile of the coarse reference attributed about 2.04 s of its
4.37 s measured analysis to 556 prepared-grillage solves. The plan-load
builder produces mostly nodal loads and a few HB member point loads, with no
member UDL. The new solver branch assembles only loaded members for this
specific load-case shape, still in the prepared element order. Cases with a
member UDL continue through the existing general assembly. This differs from
the rejected experiment above, which indexed loads but still visited and
multiplied every unloaded member for each case.

The default GUI 15 m BS analysis, all three traffic searches, code-specific
design and GUI summary were captured on the same machine in sequence from
the prior source tree and the candidate source. See the exact JSON records:
[prior](benchmarks/bs_traffic_sparse_prior_2026-10-02.json.gz)
(SHA-256 `c0496ac6df86520a25f2deb1fae05d9b3d32af9017a2441754c5a9d717e5889c`)
and [candidate](benchmarks/bs_traffic_sparse_candidate_2026-10-02.json.gz)
(SHA-256 `19028ae45f5545feb5284837db26ef89512e49f428ef44a9f6eee66be68a987a`).
Use `python scripts/compare_bs_traffic.py <prior.json.gz> <candidate.json.gz>`.

| Same-machine run | Prior | Candidate | Ratio |
| --- | ---: | ---: | ---: |
| Default GUI BS analysis and design | 122.29 s | 100.05 s | 1.22x |
| HA / HB / HA+HB placements | 612 / 1,845 / 9,672 | 612 / 1,845 / 9,672 | Unchanged |

The comparison requires **exact JSON equality excluding elapsed time** and
passed: physical retained load cases, all case and member IDs, station and
girder effects, combinations, seven design rows and GUI summary rows. The
candidate also matched the older preserved optimized fine-grid snapshot.
A focused test forces the general solver with a zero-valued member UDL and
compares its entire response to both nodal-only and mixed nodal/member-point
fast-path cases. This speed ratio is local and does not certify convergence of
the BS placement grid. The coarse old/new same-runner CI gate continues to
check exact engine output on the runner used for that job.

## 2 October 2026 retained-case completion

An interactive BS run with `retain_all_cases=true` previously entered a
separate, extremely expensive combined permanent+traffic deflection search
after traffic and design. It swept each retained physical placement on every
girder, optimizing displacement within every longitudinal interval. The UI
called this work “Finalizing results 0%” and could not cancel it until a later
phase. Case retention and that optional all-placement verification are now
independent controls. The GUI keeps the former when requested and leaves the
separate exhaustive check off unless explicitly selected; the standalone
reference runner retains its original default behavior. When selected, the
check reports case progress and supports cancellation between cases.

On the same Linux source runner the default seven-girder BS grid completed
with all cases retained in **97.04 s**: HA 612/612, HB 1,845/1,845 and HA+HB
9,672/9,672 evaluated/retained. The phase advanced through “Finalizing
results 100%” to seven GUI rows. A paired coarse-grid test found identical
girder/station envelopes, BS combinations and GUI effect rows when retention
was switched on, and a real source package smoke produced both route PDFs
with 1,032/1,032 combined BS cases retained. This evidence does not measure
the exhaustive combined-deflection runtime; it remains an optional expensive
verification and is not silently represented as having run in the report.
The [Windows x64 packaged workflow](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/37070920678)
passed the same coarse retained-case scenario in the real EXE. The first
Linux legacy BS gate for this batch compared the new config record with an
older record lacking the optional deflection field and failed on metadata;
it did not report a physical effect difference. The comparator now restores
the historical default `true` for an absent field, then still requires exact
traffic, case, combination and configuration equality. A same-machine
old/new coarse run passed, 4.34 s versus 2.07 s (2.10x on that run). This
speed ratio is for `retain_all_cases=false` in the coarse regression case,
not for the default fine-grid study or for exhaustive deflection.
The follow-on [Linux CI run](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/37071660005)
passed the same-runner LM1 and BS old/new gates after this metadata fix.
