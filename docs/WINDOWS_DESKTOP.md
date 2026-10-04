# Windows desktop distribution

The onedir build is made on a Windows x64 runner from `packaging/bridge_gui.spec`.
It includes the Qt runtime/plugins, deterministic engine and PySide6 GUI. The
ZIP contains the entire `RCBridgeAnalyzer` folder; extract it before starting
`RCBridgeAnalyzer.exe`.

## Download the built application

The Windows executable is produced by the `windows-exe` GitHub Actions workflow,
not stored in the source commit. Pushes to `main` and `codex/**` branches that
change the app, packaging, project configuration or this workflow build and
smoke-test the Windows package. Download the `RCBridgeAnalyzer-Windows-x64`
artifact from the successful run for that commit. Extract the downloaded Actions
ZIP, then extract the included `RCBridgeAnalyzer-Windows-x64.zip`; keep the
`RCBridgeAnalyzer` folder intact and run `RCBridgeAnalyzer.exe` inside it.

The CI packaged-app check starts **the built EXE**, constructs the 15 m,
seven-girder reference, saves and reopens its JSON file, executes deterministic
BS EN analysis and code-specific design checks, and writes a checked PDF
report with substituted calculations and three response plots. The workflow
fails if `qwindows.dll` is absent, the result-backed sheets are missing or a
check fails.
The smoke mode uses an explicit Custom 1.2 m LM1 search step to keep the packaged
check practical, while a normal new project selects Final Verification and
audits the 1.2 m and 0.6 m grids. Quick uses 3 m for exploratory modelling;
Standard tests 2.4 m against 1.2 m and refines to 0.6 m if the adopted 5%
criterion fails. Custom runs the edited grid without a convergence claim. The
GUI reports analysis phases and elapsed time; cancellation discards partial
results. The
15 m search-grid convergence audit reports the 1.2 m-to-0.6 m comparison,
and the smoke does not substitute for engineering verification. A Linux
offscreen source test alone does not establish a working Windows distribution.

To reproduce locally on Windows x64 with Python 3.11:

```powershell
python -m pip install -e ".[dev,gui]" "pyinstaller>=6.16,<7"
python -m PyInstaller --noconfirm --clean packaging/bridge_gui.spec
$env:QT_QPA_PLATFORM = 'offscreen'
Start-Process -FilePath .\dist\RCBridgeAnalyzer\RCBridgeAnalyzer.exe -ArgumentList '--package-smoke', '.\package-smoke' -Wait -PassThru
```

The smoke mode creates `reference_bridge.json`,
`reference_calculation_report.pdf` and `smoke_result.json` in the output
directory. Normal launches show the interactive GUI.

No code-signing certificate is configured; the ZIP is unsigned. The build
workflow records its SHA-256. Keep Qt plugins and DLLs in the unzipped folder.
Software verification is distinct from approval of a real bridge.

The legacy BS 5400 / BD 37 reference grid is still unverified. The updated
support-anchored audit completed 91,200 fine HA+HB placements with no equilibrium
failures, but default-to-half changed girder 5 torsion by 6.809% and station
shape by 26.510%; half-to-fine envelope change was 1.894% while station shape
changed by 26.938%. Both comparisons remain outside the provisional 5% screen.
See [`BS_TRAFFIC_GRID_REFINEMENT_2026-10-03.md`](BS_TRAFFIC_GRID_REFINEMENT_2026-10-03.md).
The GUI and worked sheets flag this. Their shear PASS/CHECK label is the
maximum web resistance limit only; required link steel is reported but no
provided-link schedule is checked.
