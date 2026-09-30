# Execution status

Updated: 30 September 2026 (UTC)

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

## Windows package check

The default 0.6 m longitudinal grid is computationally expensive for a
functional package gate. The updated packaged-app smoke asserts the normal
default is 0.6 m, then saves/runs an explicit 1.2 m grid. This grid is among
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
cell signs, including support roundoff. The optimized 0.6 m reference run
completed in 213.89 s with 190 retained cases; the pre-change 0.6 m run is
still computing. The subsequent progress/cancellation batch passes 246 local
tests and Ruff. CI will run the old and new 3.0 m engines on the same runner
and compare girder/station case IDs, retained loads, combinations and EC2
design outputs. GUI progress now reports real phases and elapsed time; cancel
checks between influence solves and governing searches and discards partial
results. This GUI batch is local until its CI comparison passes.

Exact next action: finish the pre-change 0.6 m run and compare governing
values, station/case IDs, retained physical loads and combinations; verify the
same-runner 3.0 m comparison, then push the GUI progress/cancellation and CI
repair batch. Add explicit Quick/Standard/Final verification modes and run the
packaged Windows application with the updated engine. For research, retain
`assumptions_confirmed=false` and obtain action/correlation/project criteria
before any accepted reliability or RBDO result.
