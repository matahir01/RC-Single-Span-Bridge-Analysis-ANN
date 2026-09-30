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
An exploratory config and runner are under verification. The source
profiles for concrete, steel, geometry and generic model error are recorded;
DL/LL distributions, dependence and project criteria are still provisional.
Any exploratory numbers must remain labelled as sensitivity calculations.
The next research batch adds a reproducible CI study and artifact, explicit
exploratory flag, output hashes, source-derived material/geometry priors,
direct-MC Wilson confidence bounds and RBDO candidate recheck. The action
models and dependence remain unconfirmed; its numerical result will be
reported only after the CI artifact is inspected. Neither software
verification nor this exploratory study approves a real bridge.

Exact next action: push the verified research-code batch, inspect the CI study
artifact and held-out/near-limit errors, convergence, FORM/MC intervals and
RBDO candidate training-domain flag. Record numerical outcomes and decisions
in the evidence register; keep `assumptions_confirmed=false` until action,
correlation and project criteria evidence closes.
