# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the agentrocky MCP sidecar.
# Build: pyinstaller mcp_server.spec --noconfirm

block_cipher = None

a = Analysis(
    ['mcp_server.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'mcp',
        'mcp.server',
        'mcp.server.stdio',
        'mcp.types',
        'anyio',
        'anyio._backends._asyncio',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt6'],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='mcp_server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
