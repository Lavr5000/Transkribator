@echo off
REM ==============================================================================
REM Auto-Start Installation Script
REM ==============================================================================
REM Выполнить на удаленном ПК через RDP
REM Копирует BAT файл в папку автозагрузки
REM ==============================================================================

setlocal enabledelayedexpansion

echo ============================================================
echo Установка автозапуска Transcriber Server
echo ============================================================
echo.

REM Определяем пути
set "SOURCE_DIR=%~dp0TranscriberServer"
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "BAT_FILE=AUTOSTART_SERVEO_UPDATED.bat"

echo [1/4] Проверка исходных файлов...
if not exist "%SOURCE_DIR%\%BAT_FILE%" (
    echo [ERROR] Файл не найден: %SOURCE_DIR%\%BAT_FILE%
    pause
    exit /b 1
)
echo [OK] Исходный BAT файл найден

echo [2/4] Проверка папки автозагрузки...
if not exist "%STARTUP_FOLDER%" (
    echo [ERROR] Папка автозагрузки не найдена: %STARTUP_FOLDER%
    pause
    exit /b 1
)
echo [OK] Папка автозагрузки: %STARTUP_FOLDER%

echo [3/4] Копирование BAT файла в автозагрузку...
copy /Y "%SOURCE_DIR%\%BAT_FILE%" "%STARTUP_FOLDER%\TranscriberServer-Autostart.bat"
if %errorLevel% neq 0 (
    echo [ERROR] Не удалось скопировать файл
    pause
    exit /b 1
)
echo [OK] Файл скопирован

echo [4/4] Проверка Python...
where python >nul 2>&1
if %errorLevel% neq 0 (
    echo [WARNING] Python не найден в PATH!
    echo Убедитесь, что Python установлен или доступен portable Python
)
echo [OK] Python найден

echo.
echo ============================================================
echo Автозапуск установлен успешно!
echo ============================================================
echo.
echo Файл автозапуска: %STARTUP_FOLDER%\TranscriberServer-Autostart.bat
echo.
echo Для тестирования сейчас:
echo   1. Запустите: %SOURCE_DIR%\%BAT_FILE%
echo   2. Проверьте лог: %USERPROFILE%\Desktop\transcriber-server.log
echo   3. Проверьте health: curl http://100.102.178.110:8000/health
echo.
pause
