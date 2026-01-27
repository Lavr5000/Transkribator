# PowerShell script to create System-Level Scheduled Task for auto-start
# Run as Administrator on remote PC (192.168.31.9)
# This will start the server at SYSTEM BOOT (no login required!)

Write-Host "========================================"  -ForegroundColor Cyan
Write-Host "Transcriber Server - SYSTEM Startup Setup" -ForegroundColor Cyan
Write-Host "========================================"  -ForegroundColor Cyan
Write-Host ""

$TaskName = "TranscriberServer-System"
$ScriptPath = Join-Path $PSScriptRoot "START_SERVER.bat"
$WorkingDir = $PSScriptRoot

# Проверяем существование скрипта
if (-not (Test-Path $ScriptPath)) {
    Write-Host "ERROR: START_SERVER.bat not found at: $ScriptPath" -ForegroundColor Red
    exit 1
}

# Удаляем старые задачи если существуют
$oldTasks = @("TranscriberServer", "TranscriberServer-System")
foreach ($oldTask in $oldTasks) {
    $existingTask = Get-ScheduledTask -TaskName $oldTask -ErrorAction SilentlyContinue
    if ($existingTask) {
        Write-Host "Removing old task: $oldTask" -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $oldTask -Confirm:$false
    }
}

# Создаем действие
$action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$ScriptPath`"" `
    -WorkingDirectory $WorkingDir

# Создаем триггер - ПРИ СТАРТЕ СИСТЕМЫ (не требует логина!)
$trigger = New-ScheduledTaskTrigger -AtStartup

# Создаем principal - СИСТЕМНЫЙ АККАУНТ (для работы без логина)
$principal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -LogonType ServiceAccount `
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
Write-Host "System-level task created: $TaskName" -ForegroundColor Green
Write-Host "Server will auto-start at SYSTEM BOOT (no login required!)" -ForegroundColor Green
Write-Host ""
Write-Host "To test now, run: START_SERVER.bat" -ForegroundColor Cyan
Write-Host "To manage task, open: Task Scheduler" -ForegroundColor Cyan
Write-Host ""
Write-Host "IMPORTANT: Server runs as SYSTEM user" -ForegroundColor Yellow
Write-Host "Check logs in server console window" -ForegroundColor Yellow
Write-Host ""
