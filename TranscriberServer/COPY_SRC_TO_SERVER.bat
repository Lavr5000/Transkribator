@echo off
REM Copy src/ folder to remote server via network share
REM Run this on the LAPTOP (192.168.31.9 must be accessible)

set REMOTE_PC=192.168.31.9
set REMOTE_PATH=\\%REMOTE_PC%\C$\Users\Denis\TranscriberServer
set LOCAL_SRC=C:\Users\user\.claude\0 ProEKTi\Transkribator\src

echo ========================================
echo Copying src/ to Remote Server
echo ========================================
echo.
echo Remote: %REMOTE_PATH%
echo Local:  %LOCAL_SRC%
echo.

REM Check if remote is accessible
if not exist "%REMOTE_PATH%" (
    echo ERROR: Cannot access %REMOTE_PATH%
    echo.
    echo Possible reasons:
    echo 1. Remote PC is off
    echo 2. Network share not enabled
    echo 3. Wrong credentials
    echo.
    echo Try:
    echo 1. Enable network sharing on remote PC
    echo 2. Or use RDP to remote PC and copy manually
    pause
    exit /b 1
)

echo [1/3] Creating remote src folder...
if not exist "%REMOTE_PATH%\src" mkdir "%REMOTE_PATH%\src"

echo [2/3] Copying files...
robocopy "%LOCAL_SRC%" "%REMOTE_PATH%\src" /E /R:1 /W:1 /NFL /NDL /NJH /NJS

echo [3/3] Verifying...
dir "%REMOTE_PATH%\src" | find "File(s)"
echo.

echo ========================================
echo Complete!
echo ========================================
echo.
echo src/ folder copied to remote server.
echo Now run MANUAL_SHERPA_INSTALL.md steps on remote PC.
echo.
pause
