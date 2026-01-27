# Create Transkribator Desktop Shortcut (NO CONSOLE WINDOW)

$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = "$Desktop\Transkribator.lnk"
$Target = "C:\Users\user\.claude\0 ProEKTi\Transkribator\main.py"
$IconPath = "C:\Users\user\.claude\0 ProEKTi\Transkribator\Transcriber.ico"
$WorkingDir = "C:\Users\user\.claude\0 ProEKTi\Transkribator"

Write-Host "Creating Transkribator shortcut (SILENT MODE)..." -ForegroundColor Cyan
Write-Host "  Target: $Target" -ForegroundColor Gray
Write-Host "  Icon: $IconPath" -ForegroundColor Gray
Write-Host ""

# Check if icon exists
if (!(Test-Path $IconPath)) {
    Write-Host "ERROR: Icon not found at $IconPath" -ForegroundColor Red
    exit 1
}

# Remove old shortcut if exists
if (Test-Path $ShortcutPath) {
    Write-Host "Removing old shortcut..." -ForegroundColor Yellow
    Remove-Item $ShortcutPath -Force
}

# Create shortcut
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)

# CRITICAL: Use pythonw.exe instead of python.exe
# pythonw = runs Python WITHOUT console window
$Shortcut.TargetPath = "pythonw"
$Shortcut.Arguments = "`"$Target`""
$Shortcut.WorkingDirectory = $WorkingDir
$Shortcut.Description = "Transkribator - AI Speech to Text"
$Shortcut.IconLocation = $IconPath
$Shortcut.Save()

Write-Host ""
Write-Host "SUCCESS!" -ForegroundColor Green
Write-Host "  Shortcut: $ShortcutPath" -ForegroundColor Cyan
Write-Host "  Mode: SILENT (no console window)" -ForegroundColor Green
Write-Host "  Icon: Transcriber.ico" -ForegroundColor Green
Write-Host ""
Write-Host "Double-click to launch Transkribator!" -ForegroundColor Yellow
