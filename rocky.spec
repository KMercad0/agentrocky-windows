# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for agentrocky Rocky GUI.
# Build: pyinstaller rocky.spec --noconfirm
#
# Notes:
# - sounds/ is bundled (CC-BY-NC-4.0, attribution kept).
# - sprites/ is NOT bundled. End-user copies 6 PNGs next to rocky.exe in sprites/.
# - mcp_server.exe must sit next to rocky.exe (built separately via mcp_server.spec).

block_cipher = None

a = Analysis(
    ['rocky.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('sounds', 'sounds'),
    ],
    hiddenimports=[
        'winrt.windows.ui.notifications',
        'winrt.windows.data.xml.dom',
        'winrt.windows.foundation',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['mcp'],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='rocky',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# onedir build — dist/rocky/rocky.exe + sibling _internal/. Cold start ~3-5x
# faster than onefile (no per-launch temp extraction). End-user drops sprites/
# next to rocky.exe and mcp_server.exe alongside it.
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='rocky',
)
