@echo off
REM ========================================
REM ONE-CLICK SHERPA INSTALLATION
REM Run this on REMOTE PC (192.168.31.9)
REM ========================================

title Installing Sherpa...

cd /d C:\Users\Denis\TranscriberServer

cls
echo.
echo ========================================
echo   SHERPA INSTALLATION
echo   Remote PC: 192.168.31.9
echo ========================================
echo.

REM Step 1
echo [1/5] Checking environment...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    pause
    exit /b 1
)
echo OK: Python installed

if exist src (
    echo OK: src folder exists
) else (
    echo ERROR: src folder missing!
    pause
    exit /b 1
)
echo.

REM Step 2
echo [2/5] Installing sherpa-onnx...
echo This may take 2-5 minutes...
pip install sherpa-onnx --quiet
if errorlevel 1 (
    echo WARNING: Installation may have failed
    echo Will try Whisper fallback...
    set USE_WHISPER=1
) else (
    echo OK: sherpa-onnx installed
    set USE_WHISPER=0
)
echo.

REM Step 3
echo [3/5] Configuring transcriber_wrapper.py...
if %USE_WHISPER%==1 (
    echo Switching to Whisper backend...
    powershell -Command "(gc transcriber_wrapper.py) -replace 'backend=\"sherpa\"', 'backend=\"whisper\"' -replace 'model_size=\"giga-am-v2-ru\"', 'model_size=\"base\"' | Set-Content transcriber_wrapper.py"
    echo Configured for Whisper
) else (
    echo Keeping Sherpa backend
)
echo.

REM Step 4
echo [4/5] Restarting server...
taskkill /F /IM python.exe >nul 2>&1
timeout /t 2 /nobreak >nul
start /B python server.py
timeout /t 5 /nobreak >nul
echo OK: Server restarted
echo.

REM Step 5
echo [5/5] Testing server...
curl -s http://192.168.31.9:8000/health > server_result.txt
type server_result.txt
echo.

findstr "transcriber_loaded.*true" server_result.txt >nul
if not errorlevel 1 (
    cls
    echo.
    echo ========================================
    echo   SUCCESS! SERVER WORKING!
    echo ========================================
    echo.
    echo transcriber_loaded: true
    echo.
    echo Now test on LAPTOP:
    echo 1. Press F9
    echo 2. Speak 3-5 seconds
    echo 3. Press F9
    echo 4. You should see 🌐 (globe) indicator!
    echo.
) else (
    cls
    echo.
    echo ========================================
    echo   WARNING: Model not loaded
    echo ========================================
    echo.
    echo transcriber_loaded: false
    echo.
    echo Troubleshooting:
    echo 1. Check transcriber_wrapper.py configuration
    echo 2. Check server log for errors
    echo 3. Try Whisper: backend="whisper", model_size="base"
    echo.
)

echo.
echo Press any key to exit...
pause >nul
