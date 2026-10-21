# -*- mode: python ; coding: utf-8 -*-
import os
import sys

block_cipher = None

# Ensure current directory is in path
ROOT_DIR = os.path.abspath(SPECPATH)

datas = [
    (os.path.join(ROOT_DIR, 'models'), 'models'),
    (os.path.join(ROOT_DIR, 'assets'), 'assets'),
]

calib_path = os.path.join(ROOT_DIR, 'calibration.json')
if os.path.isfile(calib_path):
    datas.append((calib_path, '.'))

hiddenimports = [
    'engine',
    'engine.detector',
    'engine.decision',
    'engine.compositor',
    'engine.calibration',
    'engine.worker',
    'engine.updater',
    'engine.version',
    'engine.paths',
    'ui',
    'ui.styles',
    'ui.video_widget',
    'ui.asset_grid',
    'ui.calibration_dialog',
    'ui.tray',
    'ui.main_window',
    'ui.update_dialog',
    'mediapipe',
    'mediapipe.tasks',
    'mediapipe.tasks.python',
    'mediapipe.tasks.python.vision',
    'pyvirtualcam',
    'PIL',
    'PIL.Image',
    'PIL.PngImagePlugin',
    'PIL.JpegImagePlugin',
    'PIL.GifImagePlugin',
    'cv2',
    'numpy',
]

a = Analysis(
    ['app.py'],
    pathex=[ROOT_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ReactInMeetings',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ReactInMeetings',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='ReactInMeetings.app',
        icon=None,
        bundle_identifier='com.delightc123.reactinmeetings',
        info_plist={
            'CFBundleName': 'React in Meetings',
            'CFBundleDisplayName': 'React in Meetings',
            'CFBundleIdentifier': 'com.delightc123.reactinmeetings',
            'CFBundleVersion': '1.1.0',
            'CFBundleShortVersionString': '1.1.0',
            'NSCameraUsageDescription': 'React in Meetings requires camera access to detect facial expressions and gesture reactions in real time.',
            'NSHighResolutionCapable': 'True',
            'LSUIElement': '0',
            'NSPrincipalClass': 'NSApplication',
        },
    )
