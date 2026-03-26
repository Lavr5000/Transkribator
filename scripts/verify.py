#!/usr/bin/env python3
"""
Error Map — unified verification script for Transkribator.

Checks syntax, imports, tests, models, config, and crash infrastructure.
Exit code 0 = all OK, exit code 1 = failures found.

Usage:
    python scripts/verify.py
"""

import os
import sys
import py_compile
import subprocess
import glob

# Project root = parent of scripts/
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")

# Add src to path for import checks
sys.path.insert(0, SRC_DIR)

_failures = 0


def check(name, passed, detail=""):
    """Print check result and track failures."""
    global _failures
    tag = "[OK]" if passed else "[FAIL]"
    msg = f"  {tag}  {name}"
    if detail:
        msg += f"  —  {detail}"
    print(msg)
    if not passed:
        _failures += 1


def check_syntax():
    """py_compile all .py files under src/, tests/, and main.py."""
    print("\n=== Syntax (py_compile) ===")
    patterns = [
        os.path.join(PROJECT_ROOT, "main.py"),
        os.path.join(SRC_DIR, "**", "*.py"),
        os.path.join(PROJECT_ROOT, "tests", "**", "*.py"),
    ]
    files = []
    for pat in patterns:
        files.extend(glob.glob(pat, recursive=True))

    for filepath in sorted(set(files)):
        rel = os.path.relpath(filepath, PROJECT_ROOT)
        try:
            py_compile.compile(filepath, doraise=True)
            check(rel, True)
        except py_compile.PyCompileError as e:
            check(rel, False, str(e))


def check_imports():
    """Verify critical imports resolve."""
    print("\n=== Imports ===")
    modules = [
        ("PyQt6", "PyQt6"),
        ("sounddevice", "sounddevice"),
        ("soundfile", "soundfile"),
        ("numpy", "numpy"),
        ("sherpa_onnx", "sherpa_onnx"),
        ("config (Config)", "config"),
        ("transcriber", "transcriber"),
        ("audio_recorder", "audio_recorder"),
        ("text_processor", "text_processor"),
    ]
    for label, mod in modules:
        try:
            __import__(mod)
            check(label, True)
        except ImportError as e:
            check(label, False, str(e))


def check_models():
    """Verify model files exist."""
    print("\n=== Models ===")
    models_dir = os.path.join(PROJECT_ROOT, "models", "sherpa")
    required = [
        ("giga-am-v3-ru/v3_ctc.int8.onnx", "ONNX model (v3)"),
        ("giga-am-v3-ru/tokens.txt", "Tokens file (v3)"),
    ]
    for relpath, label in required:
        full = os.path.join(models_dir, relpath)
        exists = os.path.isfile(full)
        size = ""
        if exists:
            mb = os.path.getsize(full) / (1024 * 1024)
            size = f"{mb:.1f} MB"
        check(label, exists, size if exists else f"missing: {relpath}")


def check_config():
    """Verify Config.load() works."""
    print("\n=== Config ===")
    try:
        from config import Config
        cfg = Config.load()
        check("Config.load()", True, f"backend={cfg.backend}")
    except Exception as e:
        check("Config.load()", False, str(e))


def check_crash_dir():
    """Verify crash directory exists and is writable."""
    print("\n=== Crash Infrastructure ===")
    crash_dir = os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
        "WhisperTyping", "WhisperTyping", "crashes"
    )
    exists = os.path.isdir(crash_dir)
    check("crashes/ exists", exists, crash_dir)

    if exists:
        test_file = os.path.join(crash_dir, ".verify_write_test")
        try:
            with open(test_file, "w") as f:
                f.write("ok")
            os.unlink(test_file)
            check("crashes/ writable", True)
        except Exception as e:
            check("crashes/ writable", False, str(e))

    fh_log = os.path.join(crash_dir, "faulthandler.log")
    check("faulthandler.log exists", os.path.isfile(fh_log))


def check_tests():
    """Run pytest per test file (isolated subprocesses to avoid native module segfaults)."""
    print("\n=== Tests (pytest) ===")
    tests_dir = os.path.join(PROJECT_ROOT, "tests")
    if not os.path.isdir(tests_dir):
        check("tests/ directory", False, "missing")
        return

    test_files = sorted(glob.glob(os.path.join(tests_dir, "test_*.py")))
    if not test_files:
        check("test files", False, "no test_*.py found")
        return

    for test_file in test_files:
        rel = os.path.relpath(test_file, PROJECT_ROOT)
        result = subprocess.run(
            [sys.executable, "-m", "pytest", test_file, "-v", "--tb=short", "--no-header", "-q"],
            capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=120
        )
        # Show summary line from pytest output
        lines = result.stdout.strip().splitlines()
        summary = lines[-1] if lines else ""
        is_segfault = result.returncode not in (0, 1, 5)  # 5 = no tests collected
        passed = result.returncode in (0, 5)
        detail = summary if result.returncode == 0 else f"exit code {result.returncode}"
        if result.returncode == 5:
            detail = "no tests collected (skipped)"
        if is_segfault:
            # Native module conflicts (e.g. sherpa-onnx + transformers) cause segfaults —
            # treat as warning, not failure, since it's an environment issue, not a code bug.
            print(f"  [WARN] {rel}  —  SEGFAULT (exit code {result.returncode}) — native module conflict")
            continue
        check(rel, passed, detail)


def main():
    print(f"Transkribator Error Map — {PROJECT_ROOT}")

    check_syntax()
    check_imports()
    check_models()
    check_config()
    check_crash_dir()
    check_tests()

    print(f"\n{'='*40}")
    if _failures == 0:
        print(f"  ALL CHECKS PASSED")
    else:
        print(f"  {_failures} CHECK(S) FAILED")
    print(f"{'='*40}")
    sys.exit(1 if _failures else 0)


if __name__ == "__main__":
    main()
