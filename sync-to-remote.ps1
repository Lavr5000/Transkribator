# Скрипт для обновления Transkribator на удалённом ПК
# Запустить из RDP на удалённом ПК или указать креды

$LocalPath = "C:\Users\user\.claude\0 ProEKTi\Transkribator"
$RemotePC = "100.102.178.110"
$RemotePath = "C:\Users\user\.claude\0 ProEKTi\Transkribator"

# Файлы для синхронизации (изменённые в этой сессии)
$FilesToSync = @(
    "src\audio_recorder.py",
    "src\config.py",
    "src\main_window.py"
)

Write-Host "=== Синхронизация Transkribator с удалённым ПК ===" -ForegroundColor Cyan
Write-Host "Удалённый ПК: $RemotePC" -ForegroundColor Yellow

# Проверка доступности
if (-not (Test-Connection -ComputerName $RemotePC -Count 1 -Quiet)) {
    Write-Host "ОШИБКА: Удалённый ПК недоступен!" -ForegroundColor Red
    exit 1
}

Write-Host "Удалённый ПК доступен. Копирую файлы..." -ForegroundColor Green

foreach ($File in $FilesToSync) {
    $Source = Join-Path $LocalPath $File
    $Dest = "\\$RemotePC\c$\Users\user\.claude\0 ProEKTi\Transkribator\$File"

    try {
        Copy-Item -Path $Source -Destination $Dest -Force -ErrorAction Stop
        Write-Host "  ✓ Скопирован: $File" -ForegroundColor Green
    }
    catch {
        Write-Host "  ✗ Ошибка копирования $File : $_" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "=== Синхронизация завершена ===" -ForegroundColor Cyan
Write-Host "Перезапустите Transkribator на удалённом ПК!" -ForegroundColor Yellow
