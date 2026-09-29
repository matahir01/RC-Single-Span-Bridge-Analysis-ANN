# Execution status

Updated: 29 September 2026 (UTC)

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
  currently testing the packaged executable with the default 0.6 m LM1 grid.

## Current Windows batch

The default 0.6 m longitudinal grid is computationally expensive for a
functional package gate. The updated packaged-app smoke asserts the normal
default is 0.6 m, then saves/runs an explicit 1.2 m grid. This grid is among
the repository's independently audited comparisons (4.09% maximum response
envelope change versus 0.6 m, under the documented 5% criterion), but a
package smoke is **only a functionality check**. Local Linux source smoke
completed: seven girders, seven design rows, project JSON save/reopen, and
40 KB PDF with a valid header. Windows build, packaged-app smoke, ZIP and
download/hash still need to pass on a Windows runner. Ruff and 243 tests passed.

Exact next action: monitor the new Windows Actions job, inspect plugin and
report checks, and only then deliver the tested ZIP and use instructions.
If it fails, fix and rerun on Windows.

## Research

The source and evidence register is in `docs/RESEARCH_EVIDENCE_REGISTER.md`.
An exploratory config and runner are being verified separately. The source
profiles for concrete, steel, geometry and generic model error are recorded;
DL/LL distributions, dependence and project criteria are still provisional.
Any exploratory numbers must remain labelled as sensitivity calculations.
Direct Monte Carlo locally reports Wilson binomial confidence bounds, including
the zero-failure case. The running study will evaluate dataset splits, fresh
and near-limit ANN checks, response/sample-size convergence, direct and
surrogate reliability, and an RBDO candidate recheck; its result and any
failure will be recorded after execution. Neither software verification nor
this exploratory study approves a real bridge.
