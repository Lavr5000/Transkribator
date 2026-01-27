@echo off
REM ==============================================================================
REM Remote Deployment Script for Transcriber Server
REM Creates directory structure and copies files via SSH
REM ==============================================================================

set REMOTE_HOST=User1@100.102.178.110
set REMOTE_DIR=C:\Users\User1\Desktop\Transcriber
set LOCAL_SRC=%~dp0

echo ========================================
echo Transcriber Remote Deployment
echo ========================================
echo.
echo Remote: %REMOTE_HOST%
echo Source: %LOCAL_SRC%
echo.

REM Step 1: Create directory structure
echo [1/5] Creating directory structure...
ssh -o StrictHostKeyChecking=no %REMOTE_HOST% "mkdir %REMOTE_DIR%\TranscriberServer 2>nul & mkdir %REMOTE_DIR%\TranscriberServer\uploads 2>nul & mkdir %REMOTE_DIR%\TranscriberServer\results 2>nul & mkdir %REMOTE_DIR%\src 2>nul & echo Directories created"

REM Step 2: Copy server files
echo.
echo [2/5] Copying server files...
scp -o StrictHostKeyChecking=no "%LOCAL_SRC%server.py" %REMOTE_HOST%:%REMOTE_DIR%/TranscriberServer/
scp -o StrictHostKeyChecking=no "%LOCAL_SRC%transcriber_wrapper.py" %REMOTE_HOST%:%REMOTE_DIR%/TranscriberServer/
scp -o StrictHostKeyChecking=no "%LOCAL_SRC%requirements.txt" %REMOTE_HOST%:%REMOTE_DIR%/TranscriberServer/

REM Step 3: Copy source files
echo.
echo [3/5] Copying source files...
scp -o StrictHostKeyChecking=no "%LOCAL_SRC%..\src\transcriber.py" %REMOTE_HOST%:%REMOTE_DIR%/src/
scp -o StrictHostKeyChecking=no "%LOCAL_SRC%..\src\config.py" %REMOTE_HOST%:%REMOTE_DIR%/src/
scp -o StrictHostKeyChecking=no "%LOCAL_SRC%..\src\text_processor.py" %REMOTE_HOST%:%REMOTE_DIR%/src/

REM Step 4: Create src/backends and copy backend files
echo.
echo [4/5] Copying backend files...
ssh -o StrictHostKeyChecking=no %REMOTE_HOST% "mkdir %REMOTE_DIR%\src\backends 2>nul"
scp -o StrictHostKeyChecking=no "%LOCAL_SRC%..\src\backends\*.py" %REMOTE_HOST%:%REMOTE_DIR%/src/backends/
scp -o StrictHostKeyChecking=no "%LOCAL_SRC%..\src\__init__.py" %REMOTE_HOST%:%REMOTE_DIR%/src/

REM Step 5: Copy and install BAT file
echo.
echo [5/5] Installing autostart script...
scp -o StrictHostKeyChecking=no "%LOCAL_SRC%AUTOSTART_SERVEO_FINAL.bat" %REMOTE_HOST%:%REMOTE_DIR%/TranscriberServer/AUTOSTART.bat

REM Install dependencies
echo.
echo Installing Python dependencies...
ssh -o StrictHostKeyChecking=no %REMOTE_HOST% "cd %REMOTE_DIR%\TranscriberServer && python -m pip install -q fastapi uvicorn python-multipart faster-whisper torch torchaudio"

echo.
echo ========================================
echo Deployment complete!
echo ========================================
echo.
echo Next steps:
echo 1. SSH to remote: ssh %REMOTE_HOST%
echo 2. Test server: cd %REMOTE_DIR%\TranscriberServer && python -m uvicorn server:app --host 0.0.0.0 --port 8000
echo 3. Check health: curl http://100.102.178.110:8000/health
echo.
pause
