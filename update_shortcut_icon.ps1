# Update Transkribator shortcut with icon

$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = "$Desktop\Transkribator.lnk"
$IconPath = "C:\Users\user\.claude\0 ProEKTi\Transkribator\Transcriber.png"

Write-Host "Updating shortcut icon..." -ForegroundColor Cyan
Write-Host "  Shortcut: $ShortcutPath" -ForegroundColor Gray
Write-Host "  Icon: $IconPath" -ForegroundColor Gray

if (!(Test-Path $ShortcutPath)) {
    Write-Host "ERROR: Shortcut not found!" -ForegroundColor Red
    exit 1
}

if (!(Test-Path $IconPath)) {
    Write-Host "ERROR: Icon not found!" -ForegroundColor Red
    exit 1
}

# Load shortcut and update icon
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.IconLocation = $IconPath
$Shortcut.Save()

Write-Host ""
Write-Host "[OK] Shortcut icon updated!" -ForegroundColor Green
Write-Host "  Location: $ShortcutPath" -ForegroundColor Cyan
