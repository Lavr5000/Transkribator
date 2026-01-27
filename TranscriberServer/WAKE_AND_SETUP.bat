@echo off
REM Wake-on-LAN + Remote Setup script
REM Wakes up remote PC and sets up Transcriber Server

echo ========================================
echo Transcriber Server - Wake + Setup
echo ========================================
echo.

set MAC_ADDR=08-BF-B8-6F-70-6C
set BROADCAST=192.168.31.255
set REMOTE_HOST=192.168.31.119
set REMOTE_USER=User1
set LOCAL_PATH=%~dp0

echo Step 1: Waking up remote PC...
echo MAC: %MAC_ADDR%
echo Broadcast: %BROADCAST%
echo.

REM Try WolCmd first
where wolcmd >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    wolcmd %MAC_ADDR% %BROADCAST% 255.255.255.0 7 9
    echo WolCmd sent WOL packet
) else (
    echo WolCmd not found, using PowerShell...
    powershell -Command "& {Add-Type -AssemblyName System.Net.Sockets;$client=New-Object System.Net.Sockets.UdpClient;$client.Connect([System.Net.IPAddress]::Broadcast,9);$mac=0x08,0xBF,0xB8,0x6F,0x70,0x6C;$packet=0xFF,0xFF,0xFF,0xFF,0xFF,0xFF;for($i=1;$i-le16;$i++){$packet+=$mac};$client.Send($packet,102);Write-Host 'WOL packet sent'}"
)

echo.
echo Step 2: Waiting for PC to wake up...
echo This may take 30-60 seconds...
timeout /t 30 /nobreak > nul

echo.
echo Step 3: Checking if PC is online...
ping -n 1 %REMOTE_HOST% >nul
if %ERRORLEVEL% NEQ 0 (
    echo PC is not responding yet. Waiting another 30 seconds...
    timeout /t 30 /nobreak > nul

    ping -n 1 %REMOTE_HOST% >nul
    if %ERRORLEVEL% NEQ 0 (
        echo.
        echo ERROR: PC is not responding.
        echo Please check:
        echo   1. PC is connected to network
        echo   2. PC is powered on
        echo   3. Wake-on-LAN is enabled in BIOS
        pause
        exit /b 1
    )
)

echo PC is online!
echo.
echo Step 4: Waiting for Windows to start...
echo This may take 1-2 minutes...
timeout /t 60 /nobreak > nul

echo.
echo Step 5: Running remote setup...
echo.

call "%LOCAL_PATH%REMOTE_SETUP.bat"

echo.
echo ========================================
echo COMPLETE!
echo ========================================
echo.
echo Remote PC is now configured and server should be running.
echo You can verify with:
echo   curl http://%REMOTE_HOST%:8000/health
echo.
pause
