# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Transkribator Pro

Build command:
    pyinstaller --clean transkribator.spec

Output: dist/transkribator/ directory with executable
"""

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Collect all data files from dependencies
datas = []
datas += collect_data_files('sherpa_onnx')
# Project models (sherpa ONNX models for transcription)
datas += [('models/sherpa/giga-am-v2-ru', 'models/sherpa/giga-am-v2-ru')]

# Collect all submodules to ensure complete packaging
hiddenimports = []
hiddenimports += collect_submodules('sherpa_onnx')

# PyQt6 modules (explicitly required)
hiddenimports += [
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
]

# Project modules
hiddenimports += [
    'src.config',
    'src.main_window',
    'src.audio_recorder',
    'src.text_processor',
    'src.text_processor_enhanced',
    'src.history_manager',
    'src.hotkeys',
    'src.morphology',
    'src.phonetics',
    'src.proper_nouns',
    'src.mouse_handler',
    'src.transcriber',
    'src.backends',
    'src.remote_client',
]

# Additional dependencies
hiddenimports += [
    'numpy',
    'soundfile',
    'pyaudio',
    'pynput',
]

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['src'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Transkribator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI application - no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='Transkribator_Pro.ico',  # Application icon
)

# Use onedir mode (not onefile) for better performance and compatibility
# This creates a directory with the executable and all dependencies
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='transkribator',
)
