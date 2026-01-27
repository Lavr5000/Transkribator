# Update Transkribator shortcut with PRO icon

$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = "$Desktop\Transkribator.lnk"
$IconPath = "C:\Users\user\.claude\0 ProEKTi\Transkribator\Transkribator_Pro.ico"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Updating Transkribator Shortcut" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "NEW: Professional icon (Sonic Resonance design)" -ForegroundColor Yellow
Write-Host "  - Microphone geometry" -ForegroundColor Gray
Write-Host "  - Sound waves (cyan gradient)" -ForegroundColor Gray
Write-Host "  - Stylized 'T' letter" -ForegroundColor Gray
Write-Host "  - Squircle shape (modern app icon)" -ForegroundColor Gray
Write-Host ""

if (!(Test-Path $ShortcutPath)) {
    Write-Host "ERROR: Shortcut not found!" -ForegroundColor Red
    exit 1
}

if (!(Test-Path $IconPath)) {
    Write-Host "ERROR: Icon not found at: $IconPath" -ForegroundColor Red
    exit 1
}

# Load shortcut and update icon
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.IconLocation = $IconPath
$Shortcut.Save()

Write-Host "[OK] Shortcut updated!" -ForegroundColor Green
Write-Host "  Location: $ShortcutPath" -ForegroundColor Cyan
Write-Host "  Icon: Transkribator_Pro.ico (512x512px source)" -ForegroundColor Cyan
Write-Host ""
Write-Host "Design Philosophy: Sonic Resonance" -ForegroundColor Yellow
Write-Host "  - Gradient: Navy #1a1a2e → Cyan #00d4ff" -ForegroundColor Gray
Write-Host "  - Shape: Rounded square (squircle)" -ForegroundColor Gray
Write-Host "  - Craftsmanship: Museum-quality precision" -ForegroundColor Gray
Write-Host ""
Write-Host "Refresh Explorer to see the new icon!" -ForegroundColor Yellow
