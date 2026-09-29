# Execution status

Updated: 29 September 2026 (UTC)

## Repository checkpoint
- Main before this documentation commit: `bef26032aa65fc6f1080c518c78f001ff5c62d0e` (26 September 2026). The live tree had PySide6 GUI source, Linux GUI smoke and deterministic/research infrastructure, but no Windows distribution/build workflow.
- This file is an interruption checkpoint. No Windows executable is delivered or verified yet.
- The local working copy at `/workspace/scratch/729b9c7bc3cb/rc-single-span` contains **uncommitted and unverified** GUI, reporting, Windows packaging, route-selection and GUI-test drafts. The execution environment disconnected during testing. These files may disappear with the transient workspace; inspect them before any reconstruction.

## Completed and verified before interruption
- Existing `main` was checked against README, project documentation, tests and CI. No `AGENTS.md` was found.
- Installed GUI/dev dependencies and ran `QT_QPA_PLATFORM=offscreen python -m pytest -q tests/test_gui_smoke.py tests/test_gui_design_adapter.py`: 5 passed on the initial GUI edits. This was **before** later packaging/route edits and does not verify the current drafts.
- Inspected existing source-backed probabilistic basis and pipeline; important unresolved items include permanent/traffic probabilistic model, dependence, sample-size convergence, independent ANN validation, and final RBDO study. The example study remains explicitly unconfirmed.

## Unverified local drafts
- Ribbon input dialogs (Project, Layout, section, Deck, Materials, Loads, Traffic, Design), navigation tree and original live bridge schematic.
- Result invalidation on input edits, JSON save/open, calculation report/PDF.
- Selected-code-route execution to avoid running both BS EN and BS 5400 traffic calculations for every GUI run.
- PyInstaller onedir spec, Windows x64 Actions build/smoke workflow, packaged EXE smoke mode and Windows use notes.
- New GUI workflow tests.

## Exact next action
1. Restore the execution workspace and inspect `git status`. If the local drafts remain, fix Ruff/import issues and review the route-selection changes; if lost, resume from the repo and this checkpoint.
2. Run GUI workflow tests and the full relevant test suite. Benchmark the route-specific reference run; the earlier two-route run exceeded 20 minutes and was interrupted.
3. Run the packaged-app smoke through a **real Windows x64** Actions build. Check the built EXE, bundled `qwindows.dll`, JSON save/reopen, seven-girder analysis and PDF; fix failures and publish the verified ZIP artifact.
4. Commit and push verified code batches, updating this file with exact commits, tests and remaining tasks.
5. Complete the open source/evidence register and reproducible ANN/RBDO numerical study without turning illustrative assumptions into unqualified research conclusions.

Software verification does not approve any real bridge. BS EN and BS 5400 / BD 37 remain separate routes; National Annex choices are project-specific.
