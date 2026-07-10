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
# Bundle ONLY the app's default model (giga-am-v3-ru-punct). Other models are
# selectable but not bundled (v2.2.0 shipped v2+v3 — 442MB — while the actual
# default v3-punct was absent, breaking offline first-run).
datas += [('models/sherpa/giga-am-v3-ru-punct', 'models/sherpa/giga-am-v3-ru-punct')]
# Silero VAD must ship locally: anonymous HuggingFace downloads 401 since 2026-04.
datas += [('models/sherpa/silero-vad', 'models/sherpa/silero-vad')]
# Proper-noun dictionaries (cities/names/countries) — capitalization is dead without them.
datas += [('src/data', 'src/data')]
# pymorphy3 dictionaries (lazy-imported, PyInstaller can't auto-detect the data files).
datas += collect_data_files('pymorphy3')
datas += collect_data_files('pymorphy3_dicts_ru')

# Collect all submodules to ensure complete packaging
hiddenimports = []
hiddenimports += collect_submodules('sherpa_onnx')
hiddenimports += ['pymorphy3', 'pymorphy3_dicts_ru']

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
    'src.crash_reporter',
    'src.notifier',
    'src.quality_monitor',
    'src.widgets',
    'src.settings_dialog',
    'src.morph_singleton',
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
    excludes=[
        'torch', 'torchvision', 'torchaudio',
        'transformers', 'tokenizers', 'huggingface_hub',
        'sklearn', 'scikit-learn',
        'matplotlib', 'PIL', 'Pillow',
        'cv2', 'opencv-python',
        'pandas', 'scipy',
        'tensorflow', 'keras',
        'yt_dlp',
        'sympy', 'numba', 'llvmlite',
        'sqlalchemy', 'psycopg2',
        'faster_whisper', 'ctranslate2',
        'groq',
        'telethon', 'cryptg',
        'tkinter', '_tkinter',
    ],
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
