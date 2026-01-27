@echo off
REM Remote setup script - Run from LAPTOP to configure remote PC
REM This will copy files and setup autostart via SSH

echo ========================================
echo Transcriber Server - Remote Setup
echo ========================================
echo.

set REMOTE_HOST=192.168.31.9
set REMOTE_USER=User1
set LOCAL_PATH=%~dp0
set REMOTE_PATH=C:\TranscriberServer

REM Check if SSH is available
where ssh >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: SSH not found. Please install OpenSSH client.
    echo On Windows 10/11: Settings -> Apps -> Optional Features -> OpenSSH Client
    pause
    exit /b 1
)

echo This script will:
echo 1. Copy files to remote PC (%REMOTE_HOST%)
echo 2. Setup system-level autostart (runs at boot, no login needed!)
echo.
echo Press any key to continue or Ctrl+C to cancel...
pause >nul

echo.
echo [1/4] Creating remote directory...
ssh %REMOTE_USER%@%REMOTE_HOST% "if not exist %REMOTE_PATH% mkdir %REMOTE_PATH%"

echo.
echo [2/4] Copying files to remote PC...
REM Copy using SCP (requires OpenSSH)
scp -r "%LOCAL_PATH%server.py" "%REMOTE_USER%@%REMOTE_HOST%:%REMOTE_PATH%\"
scp -r "%LOCAL_PATH%transcriber_wrapper.py" "%REMOTE_USER%@%REMOTE_HOST%:%REMOTE_PATH%\"
scp -r "%LOCAL_PATH%START_SERVER.bat" "%REMOTE_USER%@%REMOTE_HOST%:%REMOTE_PATH%\"
scp -r "%LOCAL_PATH%install_scheduled_task_system.ps1" "%REMOTE_USER%@%REMOTE_HOST%:%REMOTE_PATH%\"

echo.
echo [3/4] Setting up system-level autostart...
ssh %REMOTE_USER%@%REMOTE_HOST% "powershell -ExecutionPolicy Bypass -File %REMOTE_PATH%\install_scheduled_task_system.ps1"

echo.
echo [4/4] Verifying installation...
ssh %REMOTE_USER%@%REMOTE_HOST% "schtasks /Query /TN TranscriberServer-System"

echo.
echo ========================================
echo SETUP COMPLETE!
echo ========================================
echo.
echo Server is configured to auto-start at system boot.
echo No login required - server runs as SYSTEM service.
echo.
echo To test immediately:
echo   ssh %REMOTE_USER%@%REMOTE_HOST% "%REMOTE_PATH%\START_SERVER.bat"
echo.
echo To check status:
echo   curl http://%REMOTE_HOST%:8000/health
echo.
pause
