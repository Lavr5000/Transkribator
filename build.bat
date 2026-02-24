@echo off
REM Transkribator Build Script
REM Shortcut script that runs the main build in Obsidian installer folder
REM
REM This file exists in the source project for convenience.
REM The actual build logic is in: 📁 Проекты\🎙️ Transkribator\installer\build.bat

setlocal

echo ========================================
echo Transkribator Build
echo ========================================
echo.
echo This will:
echo 1. Build EXE with PyInstaller
echo 2. Create installer with Inno Setup
echo.

set "OBSIDIAN_INSTALLER=C:\Users\user\ObsidianVault\📁 Проекты\🎙️ Transkribator\installer\build.bat"

if not exist "%OBSIDIAN_INSTALLER%" (
    echo ERROR: Installer build script not found!
    echo Expected: %OBSIDIAN_INSTALLER%
    pause
    exit /b 1
)

call "%OBSIDIAN_INSTALLER%"
