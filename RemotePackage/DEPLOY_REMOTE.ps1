# ==============================================================================
# Remote Deployment Script for Transcriber Server
# ==============================================================================
# Выполняется на локальном ноутбуке после настройки WinRM на удаленном ПК
# ==============================================================================

$ErrorActionPreference = "Stop"

# Конфигурация
$RemotePC = "100.102.178.110"  # Tailscale IP удаленного ПК
$RemoteUser = "User1"
$RemotePath = "C:\Users\User1\Desktop\Transcriber"
$LocalSource = "C:\Users\user\.claude\0 ProEKTi\Transkribator\RemotePackage"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Развертывание Transcriber Server на удаленном ПК" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Проверка подключения
Write-Host "[1/6] Проверка подключения к $RemotePC..." -ForegroundColor Yellow
try {
    $credential = Get-Credential -UserName $RemoteUser -Message "Введите пароль для $RemoteUser"
    $session = New-PSSession -ComputerName $RemotePC -Credential $credential
    Write-Host "[OK] Подключено к $RemotePC" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Не удалось подключиться. Убедитесь, что WinRM настроен на удаленном ПК." -ForegroundColor Red
    Write-Host "Выполните SETUP_WINRM.bat на удаленном ПК через RDP." -ForegroundColor Red
    exit 1
}

# 2. Создание папки на удаленном ПК
Write-Host "[2/6] Создание папки $RemotePath..." -ForegroundColor Yellow
try {
    Invoke-Command -Session $session -ScriptBlock {
        param($path)
        if (-not (Test-Path $path)) {
            New-Item -ItemType Directory -Path $path -Force | Out-Null
            Write-Host "[OK] Папка создана: $path"
        } else {
            Write-Host "[OK] Папка уже существует: $path"
        }
    } -ArgumentList $RemotePath
} catch {
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    Exit-PSSession $session
    exit 1
}

# 3. Копирование файлов (через Robocopy через Tailscale)
Write-Host "[3/6] Копирование файлов на удаленный ПК..." -ForegroundColor Yellow
Write-Host "Это может занять время (копируются модели Whisper)..." -ForegroundColor Gray

$robocopyResult = robocopy $LocalSource "\\$RemotePC\C$\Users\User1\Desktop\Transcriber" /E /XD __pycache__ venv *.pyc tmpclaude-* /NFL /NDL /NJH /NJS

if ($LASTEXITCODE -lt 8) {
    Write-Host "[OK] Файлы скопированы" -ForegroundColor Green
} else {
    Write-Host "[WARNING] Robocopy завершился с кодом $LASTEXITCODE" -ForegroundColor Yellow
}

# 4. Установка автозапуска
Write-Host "[4/6] Установка автозапуска..." -ForegroundColor Yellow
try {
    Invoke-Command -Session $session -ScriptBlock {
        $source = "C:\Users\User1\Desktop\Transcriber\TranscriberServer\AUTOSTART_SERVEO_UPDATED.bat"
        $startup = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
        if (Test-Path $source) {
            Copy-Item -Path $source -Destination "$startup\TranscriberServer-Autostart.bat" -Force
            Write-Host "[OK] Автозапуск установлен"
        } else {
            Write-Host "[ERROR] Файл автозапуска не найден: $source"
        }
    }
} catch {
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
}

# 5. Настройка автологина (опционально)
Write-Host "[5/6] Настройка автологина..." -ForegroundColor Yellow
Write-Host "Для автологина выполните на удаленном ПК через RDP:" -ForegroundColor Gray
Write-Host "  1. Win+R -> netplwiz" -ForegroundColor Gray
Write-Host "  2. Снимите галочку 'Требовать ввод имени пользователя'" -ForegroundColor Gray
Write-Host "  3. Применить и введите пароль" -ForegroundColor Gray

# 6. Проверка сервера
Write-Host "[6/6] Проверка сервера..." -ForegroundColor Yellow
Write-Host "После перезагрузки удаленного ПК проверьте health check:" -ForegroundColor Gray
Write-Host "  curl http://100.102.178.110:8000/health" -ForegroundColor Cyan

# Завершение сессии
Remove-PSSession $session

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Развертывание завершено!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Следующие шаги:" -ForegroundColor Yellow
Write-Host "  1. Настройте автологин на удаленном ПК (через RDP + netplwiz)" -ForegroundColor White
Write-Host "  2. Перезагрузите удаленный ПК" -ForegroundColor White
Write-Host "  3. Подождите 3-5 минут для загрузки" -ForegroundColor White
Write-Host "  4. Проверьте health: curl http://100.102.178.110:8000/health" -ForegroundColor White
Write-Host ""
