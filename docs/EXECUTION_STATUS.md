# Execution status

Updated: 1 October 2026 (UTC)

## Latest pushed code

- `c3c3fd571ba028a46e62a1d7d046badb78e8a191`: selected BS EN or
  separate BS 5400/BD 37 route; 237 tests and Ruff passed.
- `ccdb9843ac948609e30bad5cf75172ee8ad160d6`: ribbon input dialogs,
  project tree, bridge drawing, JSON save/open, stale-result guard, PDF report;
  242 tests and Ruff passed, offscreen layout inspected.
- `96db24a632e35757d93df90910f33a744cb0903c`: PyInstaller onedir
  specification, Windows x64 build and packaged-app smoke workflow. Local
  Linux bundle built with Qt platform and print plugins; 242 tests and Ruff
  passed. Its Windows Actions run is
  [36594986479](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/36594986479),
  used the computationally expensive default 0.6 m LM1 grid; its original
  Windows package smoke was still running when the next run finished.
- `d8851734f9bca4e7cd142d8e56e260f505ffbf3d`: audited 1.2 m package
  smoke grid; Ruff and 243 tests passed locally. [Windows Actions run
  36600269210](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/36600269210)
  **passed** the real Windows x64 PyInstaller build, Qt plugin check, packaged
  EXE launch, seven-girder analysis/design, JSON save/open and PDF report check.
  The [downloadable artifact](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/36600269210/artifacts/11049069112)
  is a GitHub Actions ZIP containing `RCBridgeAnalyzer-Windows-x64.zip`.
  The inner distribution ZIP SHA-256 is
  `6C35DB82ACD931A7C06F9EF05F7610D22FFE07E0ADA987EEDA7EAA667CCDE49F`.
  Extract the inner ZIP, retain the full folder, and launch
  `RCBridgeAnalyzer.exe`; `README_WINDOWS.txt` is included.
- `88712208e00ec4c8b4d79d8d2e46769b5681d5f4`: exploratory research
  runner/configuration and CI artifact workflow, reproducibility hashes and
  direct-MC confidence intervals. Ruff and 243 local tests passed; repository
  tests and [research Actions run 36671364046](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/36671364046)
  succeeded. The numerical study is **not accepted**; see
  [RESEARCH_EXPLORATORY_RESULTS.md](RESEARCH_EXPLORATORY_RESULTS.md).
- `e7b40c763dfe63afd62e6825cfc8bf6b8c9c0883`: numerical exploratory
  report, full research summary JSON, and pre-optimization 3.0 m LM1 golden
  snapshot.
- `b8fab9cd0470909744a11df69534e8a585cde436`: shared LM1 influence
  basis, vector placement search, deferred governing-case verification, and
  3.0 m regression. Local Ruff and 245 tests passed; Windows package build
  passed. The Ubuntu test job found a floating-point tie difference in the
  fixed cross-platform case-ID snapshot (78 versus 79 retained cases). The
  next batch adds an old/new same-runner comparison so ordinal IDs are tested
  on the same solver build.
- `0edbd7552afbd2ab274bc56d45ccf099019467b4`: GUI phase/elapsed progress,
  cancellation, and an old/new 3 m comparator including EC2 design. The GUI
  and Windows package workflows passed; Ubuntu pytest passed (239 passed, 2
  skipped). The comparison step could not access the old commit because CI
  checkout was shallow. Local same-environment comparison passed (108.36 s old,
  10.54 s new, matching physical cases/IDs, effects and design). The next
  commit configures full history checkout.
- `2faf442ae5b5e19c21cddbe2006e5191b3b20d4f`: Quick, Standard, Final and
  Custom accuracy modes; full-history LM1 comparison and 0.6 m baseline. Linux
  tests, same-runner legacy comparison, GUI smoke and Windows packaged EXE
  smoke all passed. Windows artifact 11079853650 includes the working EXE ZIP.
- `1c2c38ecf3a3133e48be8e37a8c97551503e0b11`: BS HA/HB/HA+HB
  per-search progress and cancellation, identical physical load reuse, saved
  coarse baseline and same-runner CI gate. 251 local tests and Ruff passed.
  Linux tests and real Windows package workflow passed: runs 36883772558 and
  36883772568. The default finer BS route still needs a timed convergence audit.
- `d84d423a758d463b6b5d8fe7c7af2696487ced36`: 0.6 m LM1 near-tie
  physical check and strict identity audit; 248 local tests and Ruff passed.
  The 0.6 m old/new result matched exactly apart from elapsed time on the
  local runner (3,051.38 s to 234.69 s); CI still gates same-runner 3.0 m.
- `0bc6106b0b4b677466f13eef36f926223131bc67`: result-backed worked
  analysis/design sheets and three diagrams, BS EN and BS 5400/BD 37 routes.
  252 local tests and Ruff passed; a real source GUI run saved/reopened the
  15 m project and rendered a 12-page PDF. GitHub [tests run
  36915851648](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/36915851648),
  [GUI run 36915851439](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/36915851439),
  and [Windows EXE run 36915851447](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/36915851447)
  all passed. The [downloadable Windows artifact](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/36915851447/artifacts/11188993946)
  contains the full folder ZIP and README. Inner distribution ZIP SHA-256:
  `08DA8FB4340D324C370BD93DAE6F66ED9CBEF277C62F0469401DD38000E57702`;
  Actions artifact SHA-256:
  `4de8194f54c30b8bd2508da99261390c292ca2dcfdcf5626df9cb06ae0005e08`.
- `0ed9e7d18d95f1483c4cb084d0303ca82b90a709`: reproducible default
  fine BS old/new capture and compressed outputs. Identical results excluding
  time; 263.73 to 150.33 s (1.75x). Ruff and direct comparison passed;
  [tests run 36918836325](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/36918836325)
  passed.

## Windows package check

The default Final Verification mode audits the 1.2 m and 0.6 m longitudinal
grids and is computationally expensive for a functional package gate. The
updated packaged-app smoke asserts the normal displayed step is 0.6 m, then
saves/runs an explicit Custom 1.2 m grid. This grid is among
the repository's independently audited comparisons (4.09% maximum response
envelope change versus 0.6 m, under the documented 5% criterion), but a
package smoke is **only a functionality check**. The current Linux source
smoke completed seven girders, seven design rows, JSON save/reopen and a
178 KB, 12-page PDF containing the calculation sheets and three diagrams.
Windows CI built the actual EXE, found `qwindows.dll`, ran the packaged
reference workflow and uploaded the ZIP on 1 October. The distribution is
unsigned; the Actions artifact expires on 30 December 2026.

## Research

The source and evidence register is in `docs/RESEARCH_EVIDENCE_REGISTER.md`.
An exploratory config and runner produced a reproducible CI artifact. The source
profiles for concrete, steel, geometry and generic model error are recorded;
DL/LL distributions, dependence and project criteria are still provisional.
Any exploratory numbers must remain labelled as sensitivity calculations.
The 1,500-point study split is leakage controlled, but its LHS convergence
check still changed 5.469% at 2,000 points against the declared 5% rule; no
fresh near-flexure/deflection points were sampled. All baseline FORM searches
failed to converge. Direct shear MC reported Pf=0.4022 [0.3887, 0.4159]
under the provisional no-designed-link model; continuous-As RBDO failed and
its candidate is outside the training domain. The source/action/dependence
issues and numerical blockers remain open. Neither software verification nor
this exploratory study approves a real bridge.
An additional independent-LHS audit with 2,000, 3,000, 4,000, 6,000 and
8,000 points (seeds 20261001–20261005) failed the same 5% adjacent response
criterion at every step; the shear-margin lower 5% quantile dominates.
The result and runnable script are in `docs/research_runs/2026-10-01_lhs_extension.json`
and `examples/audit_provisional_lhs.py`. No larger count is accepted yet.

## LM1 performance verification

The optimized engine shares characteristic/frequent stiffness, tandem and unit
cell solutions, indexes member/nodal responses, vectorizes the placement search,
and physically re-solves deferred unique cases with superposition checks. Its
3.0 m C35/B500 BS EN reference run took 11.27 s versus 96.88 s before the
change (about 8.6 times faster). The saved pre-change run is
`docs/benchmarks/lm1_3m_legacy_2026-09-30.json`. A golden regression checks
all seven governing girders, station IDs, retained physical case IDs/loads,
and characteristic/frequent design combination effects. These match the
pre-change run; differing numerical effects are under 1e-7 in native units.
Near-tie selection preserves the original Python sum order and exact Hermite
cell signs, including support roundoff. An initial optimized 0.6 m reference
run completed in 213.89 s with 190 retained cases; the pre-change run took
3,051.38 s with 190 retained cases.
The baseline snapshot is `docs/benchmarks/lm1_06m_legacy_2026-09-30.json`
(SHA-256 `41b472807f46d3074a86a967800508cedc3696082d56b1c716be72ae08604914`).
The seven girder numerical effects differ by at most approximately 2.6e-10,
station moment effects by 8.6e-10 and design combinations by 1.2e-9 native
units. Five near-tied governing components choose a different member/case;
190 retained cases occur in both runs but case IDs/loads are not all identical.
The near-tie physical check restores exact JSON equality (apart from
elapsed time) with the saved baseline: all 190 retained cases and IDs,
girder/station envelopes and combinations agree. The final optimized 0.6 m
run took 234.69 s versus 3,051.38 s, a 13.00x speedup. The 3 m strict
golden regression passed. This 0.6 m identity check was local, not a CI gate.
The subsequent progress/cancellation batch passes 246 local
tests and Ruff. CI will run the old and new 3.0 m engines on the same runner
and compare girder/station case IDs, retained loads, combinations and EC2
design outputs. GUI progress now reports real phases and elapsed time; cancel
checks between influence solves and governing searches and discards partial
results. A later local batch adds Quick (3 m exploratory), Standard (2.4 to
1.2 m, then 0.6 m if needed), Final Verification (1.2 to 0.6 m) and Custom
(explicit grid without convergence claim). The real Standard 15 m run
finished in 256.76 s: it correctly rejected 2.4 to 1.2 m at 13.404% and
accepted 1.2 to 0.6 m at 4.088%, retaining 0.6 m. Local Ruff and 248 tests
pass, including a real Quick analysis.

The pushed BS batch adds progress and cooperative cancellation inside
HA, HB and HA+HB searches. Identical HA+HB physical loads within a fixed HB
position reuse the solved response while retaining each model and case ID.
On the explicit coarse benchmark, 40/129/1,032 cases took 7.62 s before and
4.20 s after (1.81x); full JSON outputs excluding elapsed time matched
exactly. The same-runner BS comparison and Windows EXE smoke passed in CI at commit `1c2c38e`.
See [BS_TRAFFIC_PERFORMANCE_AUDIT_2026-10-01.md](BS_TRAFFIC_PERFORMANCE_AUDIT_2026-10-01.md).
The default GUI BS grid with code-specific design was also compared on one
runner: 612/1,845/9,672 placements took 263.73 s before versus 150.33 s
after (1.75x). Complete captured JSON outputs were identical excluding time,
including retained case IDs/loads, girder/station envelopes, combinations,
seven design results and summary rows. Both fine snapshots and the capture
script are preserved in this repository. This is a local fine-grid check; CI
continues to gate the coarse same-runner comparison. BS grid convergence and
all-cases retention remain unverified.

## Calculation-sheet batch (pushed and Windows verified)

The clean checkout from `9a46d55` has a new result-backed report generator:
analysis load cases and factored substitutions, per-girder BS/EC2 design
checks, nominal physical traffic case/member IDs, and three plotted response
curves. The permanent bending and shear plots use the summed construction
loads; the traffic moment plot is explicitly an absolute station envelope,
not a single-case signed bending diagram. The program never assigns a
deflection pass without a project-supplied criterion. The BS coarse design
PDF renders to 12 A4 pages and was visually checked; the BS EN Quick PDF
renders to 6 pages. A real BS EN source application smoke with code-specific
design at 1.2 m saved/reopened the reference project and exported a 12-page,
177+ KB PDF. The full suite passed (252 tests), and Ruff passed. The Windows
package smoke now requires equations, diagrams and a substantive PDF. The
built Windows EXE passed that packaged smoke and the ZIP was uploaded.

Exact next action: verify DL/LL and dependence inputs, physical shear links
and a project deflection criterion; then design replicated/tail-focused
sampling and near-limit ANN validation using the recorded 2,000–8,000 failures.
Rerun reliability and RBDO only within a validated design domain and without
extrapolating unconverged FORM results. Keep
`assumptions_confirmed=false` until action/correlation/project criteria are
verified; exploratory reliability results do not approve a bridge.
