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
- `d84d423a758d463b6b5d8fe7c7af2696487ced36`: 0.6 m LM1 near-tie
  physical check and strict identity audit; 248 local tests and Ruff passed.
  The 0.6 m old/new result matched exactly apart from elapsed time on the
  local runner (3,051.38 s to 234.69 s); CI still gates same-runner 3.0 m.

## Windows package check

The default Final Verification mode audits the 1.2 m and 0.6 m longitudinal
grids and is computationally expensive for a functional package gate. The
updated packaged-app smoke asserts the normal displayed step is 0.6 m, then
saves/runs an explicit Custom 1.2 m grid. This grid is among
the repository's independently audited comparisons (4.09% maximum response
envelope change versus 0.6 m, under the documented 5% criterion), but a
package smoke is **only a functionality check**. Local Linux source smoke
completed: seven girders, seven design rows, project JSON save/reopen, and
40 KB PDF with a valid header. The Windows CI package check and ZIP upload
passed on 29 September. The distribution is unsigned and the GitHub Actions
artifact has a finite retention period.

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

The current local BS batch adds progress and cooperative cancellation inside
HA, HB and HA+HB searches. Identical HA+HB physical loads within a fixed HB
position reuse the solved response while retaining each model and case ID.
On the explicit coarse benchmark, 40/129/1,032 cases took 7.62 s before and
4.20 s after (1.81x); full JSON outputs excluding elapsed time matched
exactly. The old/new same-runner CI comparison is prepared but not pushed yet.
See [BS_TRAFFIC_PERFORMANCE_AUDIT_2026-10-01.md](BS_TRAFFIC_PERFORMANCE_AUDIT_2026-10-01.md).

Exact next action: push the verified BS traffic progress/optimization batch,
then replace the GUI calculation summary with paginated, source-labelled
calculation sheets whose equations and substituted values come from the
completed engine result. Rebuild and smoke-test the Windows ZIP. For research,
retain
`assumptions_confirmed=false` and obtain action/correlation/project criteria
before any accepted reliability or RBDO result.
