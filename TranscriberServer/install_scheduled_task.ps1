# PowerShell script to create Scheduled Task for auto-start
# Run as Administrator on remote PC (192.168.31.9)

Write-Host "========================================"  -ForegroundColor Cyan
Write-Host "Transcriber Server - Scheduled Task Setup" -ForegroundColor Cyan
Write-Host "========================================"  -ForegroundColor Cyan
Write-Host ""

$TaskName = "TranscriberServer"
$ScriptPath = Join-Path $PSScriptRoot "START_SERVER.bat"
$WorkingDir = $PSScriptRoot

# Проверяем существование скрипта
if (-not (Test-Path $ScriptPath)) {
    Write-Host "ERROR: START_SERVER.bat not found at: $ScriptPath" -ForegroundColor Red
    exit 1
}

# Удаляем старую задачу если существует
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "Removing existing task..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Создаем действие
$action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$ScriptPath`"" `
    -WorkingDirectory $WorkingDir

# Создаем триггер (при логоне)
$trigger = New-ScheduledTaskTrigger -AtLogon

# Создаем principal (текущий пользователь, с повышенными правами)
$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Highest

# Регистрируем задачу
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Force

Write-Host ""
Write-Host "SUCCESS!" -ForegroundColor Green
Write-Host "Scheduled Task created: $TaskName" -ForegroundColor Green
Write-Host "Server will auto-start on next logon" -ForegroundColor Green
Write-Host ""
Write-Host "To test now, run: START_SERVER.bat" -ForegroundColor Cyan
Write-Host "To manage task, open: Task Scheduler" -ForegroundColor Cyan
Write-Host ""
