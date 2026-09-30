# PyInstaller build definition for the local processing engine bundled with Electron.
from pathlib import Path

root = Path(SPECPATH).parent

a = Analysis(
    [str(root / "packaging" / "clippi_runtime.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[
        (str(root / "hp"), "."),
        (str(root / "connectors"), "connectors"),
        (str(root / "scripts" / "dashboard_template.html"), "scripts"),
        (str(root / "scripts" / "pdftext.swift"), "scripts"),
        (str(root / "vendor" / "plotly-basic.min.js"), "vendor"),
        (str(root / "assets" / "icons" / "clippi-health.png"), "assets/icons"),
    ],
    hiddenimports=["pypdf"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="clippi-runtime",
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="clippi-runtime",
)
