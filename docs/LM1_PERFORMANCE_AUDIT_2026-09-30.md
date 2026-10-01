# LM1 influence-search performance and identity audit

The C35/45 B500 seven-girder 15 m thesis reference was run with the same
project, BS EN route, 34,000 MPa modulus, separately weighted frequent LM1
factors (TS 0.75, UDL 0.40) and exhaustive tandem placements. The old engine
is commit `88712208e00ec4c8b4d79d8d2e46769b5681d5f4`. The optimized
source adds a shared stiffness/UDL/tandem basis, indexed NumPy response
matrices, vector search, and physical solves of selected or close governing
cases. Re-solving near-equal member records preserves the original physical
winner and trial case ordinal.

| Grid | Placements | Old runtime | Optimized runtime | Speedup | Result comparison |
| --- | ---: | ---: | ---: | ---: | --- |
| 3.0 m | 144 | 108.36 s | 10.54 s | 10.28× | Same-runner old/new cases, IDs, loads, ULS/frequent effects and EC2 design within 1e-7 native units; Linux CI gate |
| 0.6 m | 2,304 | 3,051.38 s | 234.69 s | 13.00× | Exact JSON equality excluding elapsed time on this runner: 190 retained physical cases, all seven girder and station envelopes, their member/case IDs and ULS/frequent combinations |

The 0.6 m old-engine snapshot is
[`lm1_06m_legacy_2026-09-30.json`](benchmarks/lm1_06m_legacy_2026-09-30.json),
SHA-256 `41b472807f46d3074a86a967800508cedc3696082d56b1c716be72ae08604914`.
The 3.0 m old-engine snapshot is
[`lm1_3m_legacy_2026-09-30.json`](benchmarks/lm1_3m_legacy_2026-09-30.json).
`scripts/benchmark_lm1.py` can run either source checkout with an explicitly
selected step and capture the full comparison plus EC2 design, and
`scripts/compare_lm1_results.py` checks values, physical cases and IDs.
To repeat the strict 0.6 m comparison on one runner, capture an optimized
run with the same inputs and compare it to the saved old-engine result:

```bash
python scripts/benchmark_lm1.py --root . --step 0.6 \
  --output /tmp/bridge_optimized_06m.json
python scripts/compare_lm1_results.py --exact \
  docs/benchmarks/lm1_06m_legacy_2026-09-30.json \
  /tmp/bridge_optimized_06m.json
```

An exact cross-runner case-ID comparison may differ on floating-point ties;
use the same runner and solver dependencies for an identity check. The reported
13.00× result was measured on the same runner on 30 September 2026.

The old-engine 0.6 m run took about 51 minutes, so the automated push gate
compares 3.0 m old/new on the **same runner**. Case ordinals of exact
floating-point ties can vary across solver builds; a fixed JSON snapshot from
another runner is used only for numeric regression unless the solver
environment matches. The 0.6 m strict comparison was completed locally, not
claimed as a Windows CI identity test. The Windows CI package smoke separately
launches the packaged EXE at an explicit Custom 1.2 m functional grid.

The search-resolution criterion remains the separately recorded 2.4→1.2→0.6 m
convergence audit. This performance audit changes neither traffic factors nor
the adopted 5% grid-refinement threshold; it is software verification, not
approval of a bridge design.
