#!/usr/bin/env python3
"""
Diagnostic script for Transcriber Server.
Run this on the remote PC (192.168.31.9) to check dependencies and model loading.
"""

import sys
import subprocess
import os

def run_command(cmd):
    """Run command and return output."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip(), result.returncode
    except Exception as e:
        return str(e), -1

print("=" * 70)
print("TRANSCRIBER SERVER DIAGNOSTIC")
print("=" * 70)

# 1. Check Python version
print("\n[1/10] Python version:")
print(f"  {sys.version}")

# 2. Check current directory
print("\n[2/10] Current directory:")
print(f"  {os.getcwd()}")

# 3. Check required packages
print("\n[3/10] Checking required packages:")
packages = [
    "fastapi",
    "uvicorn",
    "faster-whisper",
    "torch",
    "soundfile",
    "numpy"
]

for pkg in packages:
    output, code = run_command(f"pip show {pkg}")
    if code == 0:
        version_line = [l for l in output.split('\n') if l.startswith('Version:')]
        version = version_line[0].split(':')[1].strip() if version_line else "unknown"
        print(f"  [OK] {pkg}: {version}")
    else:
        print(f"  [MISSING] {pkg}")

# 4. Check if sherpa-onnx is installed
print("\n[4/10] Checking sherpa-onnx:")
output, code = run_command("pip show sherpa-onnx")
if code == 0:
    print("  [OK] sherpa-onnx is installed")
    version_line = [l for l in output.split('\n') if l.startswith('Version:')]
    if version_line:
        print(f"  Version: {version_line[0].split(':')[1].strip()}")
else:
    print("  [MISSING] sherpa-onnx NOT installed!")
    print("  This is required for Sherpa backend!")

# 5. Check if transcriber_wrapper.py exists
print("\n[5/10] Checking transcriber_wrapper.py:")
if os.path.exists("transcriber_wrapper.py"):
    print("  [OK] transcriber_wrapper.py exists")
else:
    print("  [ERROR] transcriber_wrapper.py NOT found!")

# 6. Check if src/ folder exists (for local imports)
print("\n[6/10] Checking src/ folder:")
if os.path.exists("src"):
    print("  [OK] src/ folder exists")
    print(f"  Files: {os.listdir('src')}")
else:
    print("  [MISSING] src/ folder NOT found!")
    print("  This is required for Transcriber import!")

# 7. Try importing transcriber
print("\n[7/10] Testing transcriber import:")
sys.path.insert(0, os.getcwd())
try:
    from transcriber_wrapper import transcriber
    print("  [OK] transcriber_wrapper imported successfully")
    print(f"  Transcriber type: {type(transcriber)}")
except Exception as e:
    print(f"  [ERROR] Failed to import: {e}")

# 8. Check if transcriber has model loaded
print("\n[8/10] Checking if model is loaded:")
try:
    from transcriber_wrapper import transcriber
    if hasattr(transcriber, 'transcriber'):
        inner = transcriber.transcriber
        print(f"  Inner transcriber type: {type(inner)}")

        # Check for sherpa-specific attributes
        if hasattr(inner, 'model'):
            print(f"  [OK] Model loaded: {type(inner.model)}")
        else:
            print("  [WARNING] No 'model' attribute found")

        # Check for recognizer (sherpa-onnx uses this)
        if hasattr(inner, 'recognizer'):
            print(f"  [OK] Recognizer loaded: {type(inner.recognizer)}")
        else:
            print("  [WARNING] No 'recognizer' attribute found")

        # Check if transcribe() works with dummy audio
        print("\n[9/10] Testing transcribe() with dummy audio:")
        import numpy as np
        audio = np.zeros(16000, dtype=np.float32)  # 1 sec silence
        text, duration = inner.transcribe(audio, 16000)
        print(f"  [OK] transcribe() works in {duration:.2f}s")
        print(f"  Result: '{text}'")
except Exception as e:
    print(f"  [ERROR] {e}")
    import traceback
    traceback.print_exc()

# 10. Final summary
print("\n" + "=" * 70)
print("DIAGNOSTIC COMPLETE")
print("=" * 70)
print("\nCommon issues:")
print("1. sherpa-onnx not installed → pip install sherpa-onnx")
print("2. src/ folder missing → Copy from laptop")
print("3. Model files missing → Download GigaAM model")
print("\nFor installation help, see: SETUP_GUIDE.md")
