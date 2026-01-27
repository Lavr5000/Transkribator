@echo off
REM ========================================
REM Run this on REMOTE PC (192.168.31.9)
REM ========================================

cd /d "%~dp0"
echo.
echo ========================================
echo Sherpa Installation on Remote PC
echo ========================================
echo.

echo Current directory: %CD%
echo.

REM Check Python
echo [1/6] Checking Python...
python --version
if errorlevel 1 (
    echo ERROR: Python not found
    pause
    exit /b 1
)
echo OK: Python installed
echo.

REM Check src folder
echo [2/6] Checking src folder...
if exist src (
    echo OK: src folder exists
    dir src | find "File(s)"
) else (
    echo ERROR: src folder missing!
    echo Please copy src folder from laptop first
    pause
    exit /b 1
)
echo.

REM Install sherpa-onnx
echo [3/6] Installing sherpa-onnx...
pip install sherpa-onnx
if errorlevel 1 (
    echo WARNING: Installation may have failed
) else (
    echo OK: sherpa-onnx installed
)
echo.

REM Verify installation
echo [4/6] Verifying installation...
python -c "import sherpa_onnx; print('OK: sherpa-onnx version:', sherpa_onnx.__version__)" 2>nul
if errorlevel 1 (
    echo WARNING: sherpa-onnx import failed
) else (
    echo OK: sherpa-onnx works
)
echo.

REM Stop old server
echo [5/6] Stopping old server...
taskkill /F /IM python.exe > nul 2>&1
timeout /t 2 /nobreak > nul
echo OK: Server stopped
echo.

REM Start server
echo [6/6] Starting server...
start /B python server.py
timeout /t 5 /nobreak > nul
echo OK: Server started
echo.

REM Check health
echo Checking server health...
curl -s http://192.168.31.119:8000/health
echo.

echo ========================================
echo Installation complete!
echo ========================================
echo.
echo Check "Loaded" field above:
echo - If "true": SUCCESS! Sherpa works!
echo - If "false": See notes below
echo.
echo ========================================
echo If Loaded=false, run this to switch to Whisper:
echo ========================================
echo.
echo cd /d "%~dp0"
echo powershell -Command "(gc transcriber_wrapper.py) -replace 'backend=\"sherpa\"', 'backend=\"whisper\"' -replace 'model_size=\"giga-am-v2-ru\"', 'model_size=\"base\"' ^| Set-Content transcriber_wrapper.py"
echo taskkill /F /IM python.exe
echo timeout /t 2 /nobreak ^> nul
echo start /B python server.py
echo timeout /t 5 /nobreak ^> nul
echo curl -s http://192.168.31.119:8000/health
echo.
pause
