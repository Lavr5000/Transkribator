# Скрипт обновления Transkribator на удалённом ПК через git pull
# Запустить на УДАЛЁННОМ ПК (192.168.31.119) через RDP

$RemotePath = "C:\Users\user\.claude\0 ProEKTi\Transkribator"

Write-Host "=== Обновление Transkribator на удалённом ПК ===" -ForegroundColor Cyan
Write-Host "Путь: $RemotePath" -ForegroundColor Yellow

# Проверяем наличие папки
if (-not (Test-Path $RemotePath)) {
    Write-Host "ОШИБКА: Папка не найдена!" -ForegroundColor Red
    pause
    exit 1
}

# Переходим в папку проекта
Set-Location $RemotePath

# Показываем текущий статус
Write-Host ""
Write-Host "=== Текущий статус git ===" -ForegroundColor Yellow
git status

# Обновляем из GitHub
Write-Host ""
Write-Host "=== Загрузка изменений из GitHub ===" -ForegroundColor Green
git pull origin master

# Перезапуск службы (если нужна)
Write-Host ""
Write-Host "=== Обновление завершено ===" -ForegroundColor Green
Write-Host "Перезапустите Transkribator!" -ForegroundColor Yellow

pause
