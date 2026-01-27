@echo off
REM Auto-install Python 3.10 on remote PC
REM This script downloads and installs Python silently

echo ========================================
echo Python 3.10 - Auto-Install
echo ========================================
echo.

set PYTHON_VERSION=3.10.11
set PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-amd64.exe
set PYTHON_EXE=%TEMP%\python_installer.exe

echo Step 1: Downloading Python %PYTHON_VERSION%...
echo URL: %PYTHON_URL%
echo.

REM Download using PowerShell
powershell -Command "& {Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%PYTHON_EXE%'}"

if not exist "%PYTHON_EXE%" (
    echo ERROR: Failed to download Python installer
    echo.
    echo Please download manually:
    echo %PYTHON_URL%
    pause
    exit /b 1
)

echo Downloaded: %PYTHON_EXE%
echo.

echo Step 2: Installing Python silently...
echo This will take 1-2 minutes...
echo.

REM Install Python silently with:
REM - Prepend PATH (adds Python to beginning of PATH)
REM - Include all features
REM - Quiet installation (no UI)
"%PYTHON_EXE%" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Installation failed with code %ERRORLEVEL%
    pause
    exit /b 1
)

echo.
echo Step 3: Waiting for installation to complete...
timeout /t 30 /nobreak > nul

echo.
echo Step 4: Verifying installation...
"C:\Program Files\Python310\python.exe" --version

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python not found after installation
    echo Trying alternative location...
    "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python310\python.exe" --version

    if %ERRORLEVEL% NEQ 0 (
        echo ERROR: Python installation verification failed
        pause
        exit /b 1
    )
)

echo.
echo ========================================
echo SUCCESS!
echo ========================================
echo Python %PYTHON_VERSION% installed successfully!
echo.
echo IMPORTANT: Log off and log back on for PATH changes to take effect
echo.
echo To verify, run: python --version
echo.

REM Cleanup
del "%PYTHON_EXE%"

pause
