# PyInstaller spec for NetMapGuard.
#
# Build a standalone, double-clickable executable:
#   pip install pyinstaller
#   pyinstaller netmapguard.spec
#
# The result is written to dist/netmapguard(.exe).

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("websockets")
    + [
        "geoip2.database",
        "geoip2.errors",
    ]
)

a = Analysis(
    ["main.py"],
    pathex=[SPECPATH],
    binaries=[],
    datas=[
        ("static", "static"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="netmapguard",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
