# Verify Transkribator Pro Icon

$ShortcutPath = "$([Environment]::GetFolderPath('Desktop'))\Transkribator.lnk"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Transkribator Pro Icon Verification" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)

Write-Host "SHORTCUT PROPERTIES:" -ForegroundColor Yellow
Write-Host "---------------------" -ForegroundColor Yellow
Write-Host ""
Write-Host "Target:        " -NoNewline
Write-Host $Shortcut.TargetPath -ForegroundColor Green
Write-Host "Arguments:     " -NoNewline
Write-Host $Shortcut.Arguments -ForegroundColor Green
Write-Host "Working Dir:   " -NoNewline
Write-Host $Shortcut.WorkingDirectory -ForegroundColor Green
Write-Host "Icon:          " -NoNewline
$iconPath = $Shortcut.IconLocation
Write-Host $iconPath -ForegroundColor Cyan
Write-Host ""
Write-Host "ICON DETAILS:" -ForegroundColor Yellow
Write-Host "-------------" -ForegroundColor Yellow

# Check which icon file is being used
if ($iconPath -like "*Transkribator_Pro.ico*") {
    Write-Host "  Status: " -NoNewline
    Write-Host "PROFESSIONAL ICON ACTIVE" -ForegroundColor Green
    Write-Host "  Design: Sonic Resonance" -ForegroundColor Cyan
    Write-Host "  Source: Transkribator_Icon.png (512x512px)" -ForegroundColor Gray
} elseif ($iconPath -like "*Transcriber.ico*") {
    Write-Host "  Status: " -NoNewline
    Write-Host "OLD ICON (basic)" -ForegroundColor Yellow
    Write-Host "  Design: Telegram-style (circle with T)" -ForegroundColor Gray
} else {
    Write-Host "  Status: " -NoNewline
    Write-Host "UNKNOWN ICON" -ForegroundColor Red
}

Write-Host ""
Write-Host "LAUNCH MODE:" -ForegroundColor Yellow
Write-Host "------------" -ForegroundColor Yellow

if ($Shortcut.TargetPath -like "*pythonw.exe*") {
    Write-Host "  Mode: " -NoNewline
    Write-Host "SILENT (no console)" -ForegroundColor Green
    Write-Host "  User sees: GUI window only" -ForegroundColor Gray
} else {
    Write-Host "  Mode: " -NoNewline
    Write-Host "NORMAL (with console)" -ForegroundColor Yellow
    Write-Host "  User sees: Console + GUI" -ForegroundColor Gray
}

Write-Host ""
Write-Host "DESIGN PHILOSOPHY:" -ForegroundColor Yellow
Write-Host "-----------------" -ForegroundColor Yellow
Write-Host "  Movement: Sonic Resonance" -ForegroundColor Cyan
Write-Host "  Concept: Sound as tangible geometry" -ForegroundColor Gray
Write-Host "  Colors: Navy #1a1a2e → Cyan #00d4ff" -ForegroundColor Gray
Write-Host "  Shape: Squircle (rounded square)" -ForegroundColor Gray
Write-Host "  Elements: Microphone + waves + 'T'" -ForegroundColor Gray
Write-Host "  Craftsmanship: Museum-quality precision" -ForegroundColor Gray
Write-Host ""
