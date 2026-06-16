# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for agentrocky Rocky GUI.
# Build: pyinstaller rocky.spec --noconfirm
#
# Notes:
# - sounds/ is bundled (CC-BY-NC-4.0, attribution kept).
# - sprites/ is NOT bundled. End-user copies 6 PNGs next to rocky.exe in sprites/.
# - mcp_server.exe must sit next to rocky.exe (built separately via mcp_server.spec).

block_cipher = None

# --- app icon ---------------------------------------------------------------
# Embed Rocky (sprites/stand.png) as the exe icon. sprites/ is gitignored, so the
# .ico is a build-time derivative — generated here, never committed. Content is
# cropped to Rocky, square-padded, and centered so he fills the icon. If the
# sprite or Pillow is missing, the build still succeeds with the default icon.
import os
ICON = None
_src = os.path.join('sprites', 'stand.png')
if os.path.exists(_src):
    try:
        from PIL import Image
        _img = Image.open(_src).convert('RGBA')
        _bbox = _img.getbbox() or (0, 0, _img.width, _img.height)
        _crop = _img.crop(_bbox)
        _side = max(_crop.size)
        _canvas = Image.new('RGBA', (_side, _side), (0, 0, 0, 0))
        _canvas.paste(_crop, ((_side - _crop.width) // 2,
                              (_side - _crop.height) // 2), _crop)
        _canvas.save('app.ico', sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                                       (64, 64), (128, 128), (256, 256)])
        ICON = 'app.ico'
    except Exception as _e:
        print(f"[rocky.spec] app icon skipped: {_e}")

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
    icon=ICON,
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
