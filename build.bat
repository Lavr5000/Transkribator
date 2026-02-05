@echo off
REM Unified Build Script for Transkribator
REM Chains PyInstaller build with Inno Setup installer creation
REM
REM Usage:
REM   build.bat
REM
REM Output:
REM   1. dist\transkribator\ - PyInstaller output
REM   2. .planning\phases\01-foundation\installer\output\Transkribator-Setup.exe

setlocal enabledelayedexpansion

echo ========================================
echo Transkribator Unified Build Script
echo ========================================
echo.

REM Get the directory where this script is located
set "PROJECT_ROOT=%~dp0"
set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

REM Path to Obsidian project with planning files
set "OBSIDIAN_PROJECT=C:\Users\user\ObsidianVault\📁 Проекты\🎙️ Transkribator"
set "ISS_FILE=%OBSIDIAN_PROJECT%\.planning\phases\01-foundation\installer\transkribator.iss"

echo Project Root: %PROJECT_ROOT%
echo ISS File: %ISS_FILE%
echo.

REM Step 1: Build executable with PyInstaller
echo ========================================
echo Step 1: Building executable with PyInstaller
echo ========================================
echo.

call "%PROJECT_ROOT%\scripts\build_exe.bat"

REM Check if PyInstaller succeeded
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ========================================
    echo PYINSTALLER BUILD FAILED!
    echo ========================================
    echo.
    echo Cannot proceed to installer creation.
    echo Fix PyInstaller errors and run again.
    pause
    exit /b 1
)

echo.
echo ========================================
echo Step 2: Creating Inno Setup installer
echo ========================================
echo.

REM Step 2: Build installer with Inno Setup
REM Check if ISCC.exe exists
set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist "%ISCC_PATH%" (
    echo ERROR: Inno Setup compiler not found!
    echo Expected location: %ISCC_PATH%
    echo.
    echo Please install Inno Setup 6.x from:
    echo https://jrsoftware.org/isdl.php
    pause
    exit /b 1
)

REM Change to source project directory for correct relative paths
cd /d "%PROJECT_ROOT%"

echo Running Inno Setup compiler...
"%ISCC_PATH%" "%ISS_FILE%"

REM Check if ISCC succeeded
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ========================================
    echo INNO SETUP BUILD FAILED!
    echo ========================================
    pause
    exit /b 1
)

echo.
echo ========================================
echo BUILD COMPLETE!
echo ========================================
echo.
echo Output files:
echo   1. Executable: %PROJECT_ROOT%\dist\transkribator\Transkribator.exe
echo   2. Installer:  %OBSIDIAN_PROJECT%\.planning\phases\01-foundation\installer\output\Transkribator-Setup.exe
echo.

REM Check if installer was actually created
if exist "%OBSIDIAN_PROJECT%\.planning\phases\01-foundation\installer\output\Transkribator-Setup.exe" (
    for %%A in ("%OBSIDIAN_PROJECT%\.planning\phases\01-foundation\installer\output\Transkribator-Setup.exe") do (
        echo Installer size: %%~zA bytes
    )
    echo.
    echo SUCCESS: Installer is ready for distribution!
) else (
    echo WARNING: Installer file not found at expected location.
)

echo.
pause
