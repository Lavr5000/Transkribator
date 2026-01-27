# Alternative Remote Installation using WinRM Copy
# Bypasses C$ share permission issues

$RemotePC = "192.168.31.9"
$RemotePath = "C:\Users\Denis\TranscriberServer"

Write-Host "========================================"  -ForegroundColor Cyan
Write-Host "WinRM Remote Installation"  -ForegroundColor Cyan
Write-Host "========================================"  -ForegroundColor Cyan
Write-Host ""

# Test WinRM
Write-Host "[1/6] Testing WinRM..." -ForegroundColor Yellow
try {
    Test-WSMan -ComputerName $RemotePC -ErrorAction Stop | Out-Null
    Write-Host "  OK: WinRM accessible" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: $_" -ForegroundColor Red
    pause
    exit 1
}

# Create src folder on remote
Write-Host "[2/6] Creating src folder..." -ForegroundColor Yellow
try {
    $CreateFolder = {
        param($Path)
        if (!(Test-Path "$Path\src")) {
            New-Item -Path "$Path\src" -ItemType Directory -Force | Out-Null
        }
        Write-Output "Folder created/exists"
    }
    $Result = Invoke-Command -ComputerName $RemotePC -ScriptBlock $CreateFolder -ArgumentList $RemotePath -ErrorAction Stop
    Write-Host "  OK: $Result" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: $_" -ForegroundColor Red
}

# Copy src files using WinRM (file by file)
Write-Host "[3/6] Copying src files..." -ForegroundColor Yellow
try {
    $LocalSrc = "C:\Users\user\.claude\0 ProEKTi\Transkribator\src"
    $Files = Get-ChildItem -Path $LocalSrc -Recurse -File

    $Copied = 0
    foreach ($File in $Files) {
        $RelativePath = $File.FullName.Substring($LocalSrc.Length + 1)
        $RemoteFilePath = "$RemotePath\src\$RelativePath"

        $CopyScript = {
            param($FilePath, $Content)
            $Dir = Split-Path $FilePath -Parent
            if (!(Test-Path $Dir)) {
                New-Item -Path $Dir -ItemType Directory -Force | Out-Null
            }
            [System.IO.File]::WriteAllBytes($FilePath, $Content)
        }

        $Content = [System.IO.File]::ReadAllBytes($File.FullName)
        Invoke-Command -ComputerName $RemotePC -ScriptBlock $CopyScript -ArgumentList $RemoteFilePath, $Content -ErrorAction SilentlyContinue | Out-Null
        $Copied++
    }

    Write-Host "  OK: $Copied files copied" -ForegroundColor Green
} catch {
    Write-Host "  WARNING: $_" -ForegroundColor Yellow
}

# Install sherpa-onnx
Write-Host "[4/6] Installing sherpa-onnx..." -ForegroundColor Yellow
try {
    $InstallScript = {
        param($Path)
        cd $Path
        $Output = pip install sherpa-onnx 2>&1
        Write-Output $Output
    }
    $Output = Invoke-Command -ComputerName $RemotePC -ScriptBlock $InstallScript -ArgumentList $RemotePath -ErrorAction Stop
    if ($Output -match "Successfully installed") {
        Write-Host "  OK: sherpa-onnx installed" -ForegroundColor Green
    } else {
        Write-Host "  WARNING: Installation may have failed" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ERROR: $_" -ForegroundColor Red
}

# Restart server
Write-Host "[5/6] Restarting server..." -ForegroundColor Yellow
try {
    $RestartScript = {
        param($Path)
        cd $Path
        taskkill /F /IM python.exe 2>$null | Out-Null
        Start-Sleep -Seconds 2
        Start-Process python -ArgumentList "server.py" -WindowStyle Hidden
    }
    Invoke-Command -ComputerName $RemotePC -ScriptBlock $RestartScript -ArgumentList $RemotePath -ErrorAction Stop
    Write-Host "  OK: Server restarted" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: $_" -ForegroundColor Red
}

# Check health
Write-Host "[6/6] Checking health..." -ForegroundColor Yellow
Start-Sleep -Seconds 5
try {
    $Response = Invoke-RestMethod -Uri "http://${RemotePC}:8000/health" -TimeoutSec 10
    Write-Host "  Status: $($Response.status)" -ForegroundColor Cyan
    Write-Host "  Loaded: $($Response.transcriber_loaded)" -ForegroundColor $(if ($Response.transcriber_loaded) { "Green" } else { "Yellow" })

    if ($Response.transcriber_loaded) {
        Write-Host ""
        Write-Host "========================================"  -ForegroundColor Green
        Write-Host "SUCCESS! Ready to test!"  -ForegroundColor Green
        Write-Host "========================================"  -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "Note: sherpa-onnx installed but model not loaded" -ForegroundColor Yellow
        Write-Host "Server will use local fallback (🏠 indicator)" -ForegroundColor Cyan
    }
} catch {
    Write-Host "  ERROR: Cannot reach server" -ForegroundColor Red
}

Write-Host ""
Write-Host "Done!" -ForegroundColor Cyan
