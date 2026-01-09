@echo off
REM WhisperTyping Installation Script for Windows

echo ==================================
echo   WhisperTyping Installer
echo ==================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found. Please install Python 3.9 or later.
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Found Python:
python --version

REM Create virtual environment
echo.
echo Creating virtual environment...
python -m venv venv

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Upgrade pip
echo.
echo Upgrading pip...
python -m pip install --upgrade pip

REM Ask for GPU support
echo.
set /p GPU_SUPPORT="Do you have an NVIDIA GPU and want GPU acceleration? (y/n): "

if /i "%GPU_SUPPORT%"=="y" (
    echo.
    echo Installing GPU version...
    pip install -r requirements-gpu.txt
) else (
    echo.
    echo Installing CPU version...
    pip install -r requirements.txt
)

REM Install package
echo.
echo Installing WhisperTyping...
pip install -e .

REM Create shortcut
echo.
echo Creating desktop shortcut...

set SCRIPT_PATH=%~dp0
set SHORTCUT_PATH=%USERPROFILE%\Desktop\WhisperTyping.bat

(
echo @echo off
echo cd /d "%SCRIPT_PATH%.."
echo call venv\Scripts\activate.bat
echo python main.py
) > "%SHORTCUT_PATH%"

echo Desktop shortcut created: %SHORTCUT_PATH%

echo.
echo ==================================
echo   Installation Complete!
echo ==================================
echo.
echo To run WhisperTyping:
echo   1. Double-click WhisperTyping.bat on your desktop
echo   OR
echo   2. Run: venv\Scripts\activate ^& python main.py
echo.

pause
