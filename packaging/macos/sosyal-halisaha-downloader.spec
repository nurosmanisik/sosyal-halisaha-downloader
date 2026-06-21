# -*- mode: python ; coding: utf-8 -*-

import os

ROOT = os.path.abspath(os.path.join(SPECPATH, "../.."))

a = Analysis(
    [os.path.join(ROOT, "desktop_app.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[
        (os.path.join(ROOT, "templates"), "templates"),
        (os.path.join(ROOT, "static"), "static"),
    ],
    hiddenimports=[
        "webview.platforms.cocoa",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Sosyal Hali Saha Downloader",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Sosyal Hali Saha Downloader",
)
app = BUNDLE(
    coll,
    name="Sosyal Hali Saha Downloader.app",
    icon=None,
    bundle_identifier="com.local.sosyal-halisaha-downloader",
    info_plist={
        "CFBundleDisplayName": "Sosyal Hali Saha Downloader",
        "CFBundleName": "Sosyal Hali Saha Downloader",
        "LSMinimumSystemVersion": "10.15",
        "NSHighResolutionCapable": True,
    },
)
