@echo off
REM Thin wrapper over scripts\build_release.py — the real build.
REM
REM The release is built from a CLEAN GIT WORKTREE in a fresh venv, never from
REM the working directory: a repo in daily use carries debug.log, the owner's
REM config and downloaded models, and PyInstaller happily ships all of it.
REM
REM Usage:
REM   scripts\build_exe.bat                 build HEAD, produce the ZIP
REM   scripts\build_exe.bat --dry-run       build and scan, no ZIP
REM   scripts\build_exe.bat --commit v2.4.0
REM
REM Output: dist\Transkribator-v<version>-win64.zip + dist\SHA256SUMS.txt

setlocal
cd /d "%~dp0.."
python scripts\build_release.py %*
exit /b %ERRORLEVEL%
