# Windows desktop distribution

The onedir build is made on a Windows x64 runner from `packaging/bridge_gui.spec`.
It includes the Qt runtime/plugins, deterministic engine and PySide6 GUI. The
ZIP contains the entire `RCBridgeAnalyzer` folder; extract it before starting
`RCBridgeAnalyzer.exe`.

The CI packaged-app check starts **the built EXE**, constructs the 15 m,
seven-girder reference, saves and reopens its JSON file, executes deterministic
BS EN analysis and code-specific design checks, and writes a checked PDF
report. The workflow fails if `qwindows.dll` is absent or if a check fails.
The smoke mode uses a 1.2 m LM1 search step to keep the packaged check
practical, while a normal new project defaults to the verified 0.6 m grid. The
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
