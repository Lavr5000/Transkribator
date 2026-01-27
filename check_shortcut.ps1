# Check shortcut properties

$ShortcutPath = "$([Environment]::GetFolderPath('Desktop'))\Transkribator.lnk"

Write-Host "Shortcut Properties:" -ForegroundColor Cyan
Write-Host "==================" -ForegroundColor Cyan
Write-Host ""

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)

Write-Host "Target:        " -NoNewline
Write-Host $Shortcut.TargetPath -ForegroundColor Green
Write-Host "Arguments:     " -NoNewline
Write-Host $Shortcut.Arguments -ForegroundColor Green
Write-Host "Working Dir:   " -NoNewline
Write-Host $Shortcut.WorkingDirectory -ForegroundColor Green
Write-Host "Icon:          " -NoNewline
Write-Host $Shortcut.IconLocation -ForegroundColor Green
Write-Host "Description:   " -NoNewline
Write-Host $Shortcut.Description -ForegroundColor Green
Write-Host ""
Write-Host "NOTE: Target is 'pythonw' - this runs WITHOUT console window!" -ForegroundColor Yellow
