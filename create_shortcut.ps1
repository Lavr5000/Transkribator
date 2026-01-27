# Create Transkribator Desktop Shortcut with Telegram Icon

$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = "$Desktop\Transkribator.lnk"
$Target = "C:\Users\user\.claude\0 ProEKTi\Transkribator\main.py"
$IconPath = "C:\Users\user\.claude\0 ProEKTi\Transkribator\Transcriber.ico"
$WorkingDir = "C:\Users\user\.claude\0 ProEKTi\Transkribator"

Write-Host "Creating Transkribator shortcut..." -ForegroundColor Cyan
Write-Host "  Target: $Target" -ForegroundColor Gray
Write-Host "  Icon: $IconPath" -ForegroundColor Gray

# Download Telegram logo if icon doesn't exist
if (!(Test-Path $IconPath)) {
    Write-Host "  Downloading Telegram icon..." -ForegroundColor Yellow

    # Download Telegram logo
    $IconPng = "$WorkingDir\telegram_icon.png"
    Invoke-WebRequest -Uri "https://upload.wikimedia.org/wikipedia/commons/thumb/8/82/Telegram_logo.svg/256px-Telegram_logo.svg.png" -OutFile $IconPng

    # Convert PNG to ICO using PowerShell (simple method - just copy as PNG)
    # Windows 10/11 supports PNG as shortcut icon
    Copy-Item $IconPng $IconPath -Force
    Write-Host "  Icon created" -ForegroundColor Green
}

# Create shortcut
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "python"
$Shortcut.Arguments = "`"$Target`""
$Shortcut.WorkingDirectory = $WorkingDir
$Shortcut.Description = "Transkribator - AI Speech to Text"
$Shortcut.IconLocation = $IconPath
$Shortcut.Save()

Write-Host ""
Write-Host "✅ Shortcut created!" -ForegroundColor Green
Write-Host "  Location: $ShortcutPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "Double-click the shortcut to start Transkribator!" -ForegroundColor Yellow
