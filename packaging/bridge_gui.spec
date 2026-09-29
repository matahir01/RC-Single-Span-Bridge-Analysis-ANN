# Build on Windows x64 with: python -m PyInstaller --noconfirm --clean packaging/bridge_gui.spec
# The entire onedir folder, including Qt platform plugins, is distributed.
from pathlib import Path

project_root = Path(SPECPATH).resolve().parent

a = Analysis(
    [str(project_root / "src/rc_single_span/gui/app.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    excludes=["tensorflow"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="RCBridgeAnalyzer", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="RCBridgeAnalyzer")
