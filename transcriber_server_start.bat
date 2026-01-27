@echo off
REM ========================================
REM Transcriber Server - Quick Start
REM ========================================
echo Starting Transcriber Server...
cd C:\Users\User1\Desktop\Transcriber\TranscriberServer
python -m uvicorn server:app --host 0.0.0.0 --port 8000
pause
