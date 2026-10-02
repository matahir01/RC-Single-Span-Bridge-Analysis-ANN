# Execution status

Updated: 2 October 2026 (UTC)

## Latest interactive BS stall fix (Windows package verified)

The user observed “Finalizing results 0%” for over 237 s with “Retain all
traffic cases” selected. The runner was actually reoptimizing combined
permanent+traffic displacement over every retained placement, seven girders
and every longitudinal interval without progress/cancellation. A separate,
explicit BS 5400 combined-deflection checkbox now controls this expensive
check. Retaining cases alone leaves it off; saved JSON, GUI and report show
the choice. The standalone reference runner retains the historical all-case
default. An explicit exhaustive run now reports total case progress and
checks Cancel between cases. Its runtime has **not** been benchmarked or
claimed fast. No design or traffic formula changed.

Pushed source commit: `5fa9be0bec10ede8d062207ae0bbd896dc9c3954`.
Local full suite: 261 passed, Ruff clean; paired coarse BS runs with case retention
on/off matched all girder/station traffic effects, BS combinations and GUI
effect rows. Source package smoke completed BS EN and BS analysis,
save/reopen, seven design rows per route and two PDFs; the BS case count was
1,032/1,032 retained. A normal seven-girder default BS grid with 612 HA,
1,845 HB and 9,672 HA+HB cases retained completed in 97.04 s on this runner;
Finalizing results reached 100%, with seven GUI rows returned. This grid is
**not converged** and the existing BS warning remains. The 93,480-case finer
audit remains blocked by the strict equilibrium failure documented below.

[Windows x64 workflow 37070920678](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/37070920678)
**passed** source GUI tests, PyInstaller onedir, `qwindows.dll`, packaged EXE
BS EN and BS analysis/design, project save/open, both PDFs, and the new
1,032/1,032 retained-case BS smoke. [Download artifact
11253799153](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/37070920678/artifacts/11253799153)
before 31 December 2026. Its outer Actions ZIP SHA-256 is
`cd48ec2f7ca14f11ea0df02ffe8e38051b38383e32dc31ae518bc6b1ecd2a466`.
Extract the outer ZIP and inner `RCBridgeAnalyzer-Windows-x64.zip`; keep the
full folder together and launch `RCBridgeAnalyzer.exe`. This package is the
verified `5fa9be0` app; the follow-on comparison-gate metadata fix changes
only a developer script and test.

The same push's [Linux tests 37070920683](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/37070920683)
passed Ruff, pytest and the old/new LM1 comparison, then failed the old/new
BS JSON comparison because `ReferenceRunConfig` has a new verification
option absent in the historical baseline. The follow-on comparison-gate fix
normalizes this one missing field to its old default `true`; it still rejects
changed traffic values or a changed option. Actual same-runner old/new coarse
outputs then compared **exactly equal**, 4.34 s old versus 2.07 s new on
this machine. The follow-on CI run must still pass before closing that gate.

Exact next action for this batch: push the comparator fix after local tests,
confirm the new Linux CI old/new BS comparison passes, and preserve the
Windows artifact link. Next engineering work: resolve the conditioned
BS KEL grid before any fine-grid convergence claim, then address the research
source and validation blockers at the end of this file.

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
- `9e214e1b2ef07d90f5afba43d8ff17cf7dcf61cc`: exploratory independent
  LHS extension to 8,000 samples, with reproducible script, exact input hash
  and source register update. Every new adjacent-size step failed the adopted
  5% response rule; no sample size is accepted. Local research tests (7) and
  Ruff passed. GitHub [tests run 36920444192](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/36920444192)
  passed.
- `7a317106177550e8a99771e352e1d6455aa57876`: exhaustive half-step BS
  traffic audit, replicated LHS and saved-ANN direct-boundary challenge,
  plus GUI/report BS grid warnings. Local 257 tests, Ruff and a rendered BS
  analysis sheet passed. [GUI workflow 36927717170](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/36927717170)
  passed. The Linux test job failed during collection because the new audit
  test imported `examples` as a package in installed-package CI.
- `4fb027930ac235c72549d493867359286da3235d`: fixed that test import
  by loading the script by path; focused test and Ruff passed locally.
  [Linux tests 36927972278](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/36927972278)
  **passed**, including the same-runner legacy engine comparisons.
  [Windows EXE 36927717385](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/36927717385)
  **passed** source GUI tests, PyInstaller build, Qt plugin and packaged
  reference workflow, ZIP creation and upload. [Artifact 11195350209](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/36927717385/artifacts/11195350209)
  expires 30 December 2026; Actions artifact SHA-256 is
  `8371a9118b642239b0b5b422283319fe02ddc6dfaf5bcba8148e3d9d37ca97bd`.
  [Research 36927717493](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/36927717493)
  **passed**; the correction changed only a Linux test import.
- `431adf00dee1b6c6fe556a228a25ac7549bf0e9d`: GUI results and report
  identify the maximum web resistance check, state that installed shear
  links are not assessed, and no longer label it as a complete shear pass.
  The paired slower load-indexing solver trial was reverted. Local 257 tests,
  Ruff and the focused BS worked-sheet PDF test passed. [GUI smoke
  36930169645](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/36930169645)
  **passed**; [tests 36930169650](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/36930169650)
  and [Windows EXE 36930169662](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/36930169662)
  **passed**.
- `7ddf82900b22d0dcdb8e1eceef86ee64ff1803ba`: README, packaged-app
  usage instructions and checkpoint aligned with the BS grid and shear scope.
  [Linux tests 36930527724](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/36930527724)
  **passed**. [Windows build 36930527695](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/36930527695)
  **passed** source GUI workflow tests, actual Windows x64 PyInstaller build,
  Qt plugin check, packaged reference analysis/design, save/open, PDF, ZIP
  creation and upload. [Download artifact 11194984935](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/36930527695/artifacts/11194984935)
  before its 30 December 2026 expiry; GitHub Actions artifact SHA-256:
  `c7a40ba8cdb89eca9c6442fabd88521e34245a684a70b07cc7915c98fc235a20`.
- `88d296a9f1d55c8f8346bf9337ae413c47751b13`: six editable BS traffic
  steps in GUI/project JSON/report, construction-stage equilibrium, bending
  and stiffness substitutions checked against the engine result, and Windows
  usage instructions. Local 257 tests, Ruff and rendered 13-page BS PDF
  passed. [Linux tests 37018347964](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/37018347964),
  [GUI smoke 37018347853](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/37018347853),
  and [Windows EXE 37018348130](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/37018348130)
  **passed**. [Download Windows artifact 11232036651](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/37018348130/artifacts/11232036651)
  before 31 December 2026; Actions artifact SHA-256:
  `08a7d2cb79ed3a449a0f01736f2172926face6547f94c30042e73a8504b70495`.
- `2ec4f99795df68d494578b4e1959db931f29dce0`: sparse nodal/member-point
  traffic assembly with the old general member-UDL path preserved, and a
  second Windows packaged smoke route for coarse BS 5400 analysis, save/open
  and a BS PDF. Paired default fine BS outputs match exactly excluding time,
  122.29 to 100.05 s (1.22x). Local 258 tests, Ruff, exact full capture
  comparison, and source two-code package smoke passed. [Linux tests
  37020255989](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/37020255989)
  and [GUI smoke 37020256023](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/37020256023)
  **passed**, including the legacy-engine CI comparison. [Windows EXE
  37020255807](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/37020255807)
  **passed** the extended two-code packaged workflow, including Qt plugin,
  two seven-girder analyses/designs, save/reopen and two PDFs. [Download its
  artifact 11232379819](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/37020255807/artifacts/11232379819)
  before 31 December 2026; Actions ZIP SHA-256:
  `d5a17b1f7a34fe4f7c9c53a1c5984717c1d826326beb26a2502a580d8260e61e`.
- `e96febe78f097b7d658af0a37ed2b90d0f6a34bd`: auditable script and
  checkpoint for the next exhaustive combined BS grid. It was linted and its
  same-grid comparison sanity check passed. The attempted full run stopped at
  case 3 on vertical-equilibrium failure; see below. A completed envelope was
  not generated.

The former “Shear PASS” field is explicitly the **maximum web resistance**
check. The worked sheets state that required link steel is calculated but
installed links were not provided; a complete shear reinforcement pass is not
asserted. A separate trial indexed per-member loads in the prepared solver.
Default BS outputs were identical, but a paired same-machine benchmark took
150.92 s for the prior engine and 176.32 s for the trial; it was rejected and
reverted. See `docs/BS_TRAFFIC_PERFORMANCE_AUDIT_2026-10-01.md`.

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
The subsequent updated GUI/report build also passed the Windows packaged
smoke. [Download the latest two-code artifact](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/37020255807/artifacts/11232379819),
extract the outer Actions ZIP, then extract `RCBridgeAnalyzer-Windows-x64.zip`
and run `RCBridgeAnalyzer.exe` from the full folder. This build includes the
BS grid warning and editable placement steps in the GUI and calculation sheets.
Its packaged smoke now runs both the primary BS EN and coarse legacy BS routes.

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
Three independent LHS replications at each of 2,000, 4,000 and 8,000 points
still fail the 5% response-stability screen at the last size (7.417% between
seeds). A restored, unchanged ANN reproduced the held-out test metrics to
floating-point precision, but at a fresh direct shear `g=0` point it predicted
**+3.805 kN** safe margin. The direct search found no flexure/deflection
bracket in the chosen marginal quantile hyperrectangle; that does not certify
their reliability. See `docs/research_runs/2026-10-01_replicated_lhs_boundary.json`
and `docs/RESEARCH_EXPLORATORY_RESULTS.md`. This ANN is not accepted for tail
probability or RBDO decisions.

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
all-cases retention remain unverified. A subsequent exhaustive half-step audit
found the default HA and HB searches within the provisional 5% girder response
criterion, but the default HA+HB grid **failed** at 7.412% torsion change on
girder 5. See `docs/BS_TRAFFIC_GRID_REFINEMENT_2026-10-01.md`. The GUI and
calculation sheets now flag this limitation; neither default nor half-step
combined grid is accepted as a final converged traffic search.

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

The pushed source batch exposes the six BS HA/HB/HA+HB placement steps in the GUI,
persists them in project JSON and the report, and expands construction-stage
worked sheets with equilibrium and bending substitutions checked against the
engine. Local 257 tests, Ruff and focused 13-page PDF visual inspection passed;
Windows packaged-app verification passed on its pushed commit. The next
package gate additionally exercises the **BS** route inside the executable.

The pushed sparse-load solver batch leaves general member-UDL assembly
unchanged and assembles only loaded members for the nodal/member-point traffic
cases. The paired full default BS route took 122.29 s before versus 100.05 s
after (1.22x) on one machine. Captured HA/HB/HA+HB physical cases, case/member
IDs, girder and station responses, combinations, seven design results and GUI
rows were exactly identical after excluding elapsed time. The two compressed
captures and SHA-256 values are in
`docs/BS_TRAFFIC_PERFORMANCE_AUDIT_2026-10-01.md`. Local 258 tests and Ruff
passed. Linux CI passed the same-runner legacy-engine comparison. A source
package smoke ran the BS EN reference and a coarse BS route,
saved/reopened both projects and produced both calculation PDFs. The new
Windows packaged smoke has not yet completed.

The follow-on combined BS search at HB longitudinal/transverse and HA KEL
steps of **0.5 / 0.25 / 0.5 m** has **stopped at case 3** because the strict
vertical-equilibrium check failed: -0.001828735 kN residual versus a
0.001352612 kN tolerance. Its generator counted **93,480** cases versus
27,060 at 1.0 / 0.5 / 1.0 m. A reproducible probe found 4,625 grid nodes,
5,368 members and a 0.005 m minimum longitudinal segment; the entire
optimized/general solver result was identical for the failing case. The
probe JSON, code and decision are in
`docs/BS_TRAFFIC_GRID_REFINEMENT_2026-10-01.md`. No second-grid envelope or
convergence result exists. The default BS grid warning remains necessary.

Exact next action: investigate a numerically conditioned and consistently
nested KEL edge/grid construction while preserving the documented placement
model, verify strict equilibrium on the first 32 and all subsequently solved
cases, then rerun the 93,480-placement combined search and compare all seven
girder/station responses against the 27,060-placement record. Benchmark any further speedup
against the preserved exact-output legacy gate. Obtain defensible DL/LL and dependence
inputs, physical shear-link data and a project deflection criterion; build
tail-focused training and independent direct boundary validation before
retrying FORM/RBDO within a validated design domain. Keep
`assumptions_confirmed=false` until action/correlation/project criteria are
verified; exploratory reliability results do not approve a bridge.
