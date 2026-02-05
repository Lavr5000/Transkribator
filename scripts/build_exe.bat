@echo off
REM Build Transkribator executable using PyInstaller
REM
REM Usage:
REM   scripts\build_exe.bat
REM
REM Output:
REM   dist\transkribator\Transkribator.exe

setlocal enabledelayedexpansion

echo ========================================
echo Transkribator Build Script
echo ========================================
echo.

REM Check if pyinstaller is available
where pyinstaller >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: PyInstaller not found!
    echo Please install: pip install pyinstaller
    exit /b 1
)

REM Clean previous builds
echo Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
echo Done.
echo.

REM Run PyInstaller
echo Building executable...
pyinstaller --clean transkribator.spec

REM Check exit code
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ========================================
    echo BUILD FAILED!
    echo ========================================
    exit /b 1
)

echo.
echo ========================================
echo BUILD SUCCESS!
echo ========================================
echo.
echo Output location: dist\transkribator\
echo Executable: dist\transkribator\Transkribator.exe
echo.

pause
