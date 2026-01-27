@echo off
REM Refresh Windows icon cache to show new shortcut icon

echo Refreshing icon cache...
echo.

REM Delete icon cache database
taskkill /f /im explorer.exe > nul 2>&1
timeout /t 2 /nobreak > nul

del /f /s /q /a "%userprofile%\AppData\Local\IconCache.db" > nul 2>&1
del /f /s /q /a "%userprofile%\AppData\Local\Microsoft\Windows\Explorer\*.db" > nul 2>&1

echo Icon cache cleared.
echo.
echo Starting Explorer...
start explorer.exe

echo Done! Check your desktop shortcut.
timeout /t 3 /nobreak > nul
