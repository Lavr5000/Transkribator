@echo off
REM ==============================================================================
REM WinRM Setup Script for Remote Management
REM ==============================================================================
REM Выполнить на удаленном ПК через RDP (с правами администратора)
REM ==============================================================================

echo ============================================================
echo Настройка WinRM для удаленного управления
echo ============================================================
echo.

REM Проверка прав администратора
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Этот скрипт требует прав администратора!
    echo Нажмите правой кнопкой на файл - "Запуск от имени администратора"
    pause
    exit /b 1
)

echo [1/5] Включение WinRM服务...
winrm quickcmd -q
if %errorLevel% neq 0 (
    winrm quickconfig -q
)

echo [2/5] Настройка HTTP listener...
winrm set winrm/config/client '@{TrustedHosts="*"}'

echo [3/5] Настройка сервиса для максимальной совместимости...
winrm set winrm/config/service '@{AllowUnencrypted="true"}'
winrm set winrm/config/service/auth '@{Basic="true"}'

echo [4/5] Настройка клиента...
winrm set winrm/config/client '@{AllowNegotiate=true}'
winrm set winrm/config/client '@{Basic="true"}'

echo [5/5] Проверка статуса WinRM...
winrm enumerate winrm/config/listener

echo.
echo ============================================================
echo WinRM настроен успешно!
echo ============================================================
echo.
echo Для подключения с локального ПК используйте PowerShell:
echo.
echo   $cred = Get-Credential
echo   $session = New-PSSession -ComputerName 100.102.178.110 -Credential $cred
echo   Invoke-Command -Session $session -ScriptBlock { hostname }
echo.
echo Или через Enter-PSSession:
echo.
echo   Enter-PSSession -ComputerName 100.102.178.110 -Credential User1
echo.
pause
