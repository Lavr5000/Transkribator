# Execute task on remote Claude Code via WinRM

$RemotePC = "192.168.31.119"

Write-Host "Executing task on remote Claude Code..." -ForegroundColor Cyan

# Command to run on remote PC
$RemoteCommand = {
    # Navigate to TranscriberServer directory
    cd C:\Users\user\.claude\0 ProEKTi\Transkribator\TranscriberServer

    # Step 1: Install sherpa-onnx
    Write-Output "[1/5] Installing sherpa-onnx..."
    pip install sherpa-onnx --quiet 2>&1 | Write-Output

    # Step 2: Verify src folder
    Write-Output "[2/5] Checking src folder..."
    if (Test-Path "src") {
        Write-Output "  src folder exists"
        Get-ChildItem src | Measure-Object | Select-Object -ExpandProperty Count | ForEach-Object { Write-Output "  Files: $_" }
    } else {
        Write-Output "  ERROR: src folder missing!"
    }

    # Step 3: Stop server
    Write-Output "[3/5] Stopping old server..."
    taskkill /F /IM python.exe 2>$null | Write-Output
    Start-Sleep -Seconds 2

    # Step 4: Start server
    Write-Output "[4/5] Starting server..."
    Start-Process python -ArgumentList "server.py" -WindowStyle Hidden
    Start-Sleep -Seconds 5

    # Step 5: Check health
    Write-Output "[5/5] Checking health..."
    try {
        $Response = Invoke-RestMethod -Uri "http://192.168.31.119:8000/health" -TimeoutSec 10
        Write-Output "  Status: $($Response.status)"
        Write-Output "  Loaded: $($Response.transcriber_loaded)"

        if (-not $Response.transcriber_loaded) {
            Write-Output "  WARNING: Model not loaded. Switching to Whisper..."

            # Edit transcriber_wrapper.py to use Whisper
            $WrapperPath = "C:\Users\Denis\TranscriberServer\transcriber_wrapper.py"
            if (Test-Path $WrapperPath) {
                $Content = Get-Content $WrapperPath -Raw
                $Content = $Content -replace 'backend="sherpa"', 'backend="whisper"'
                $Content = $Content -replace 'model_size="giga-am-v2-ru"', 'model_size="base"'
                $Content | Set-Content $WrapperPath -Force
                Write-Output "  Updated to Whisper backend"

                # Restart server
                taskkill /F /IM python.exe 2>$null | Write-Output
                Start-Sleep -Seconds 2
                Start-Process python -ArgumentList "server.py" -WindowStyle Hidden
                Start-Sleep -Seconds 5

                # Check again
                $Response = Invoke-RestMethod -Uri "http://192.168.31.119:8000/health" -TimeoutSec 10
                Write-Output "  After Whisper switch - Loaded: $($Response.transcriber_loaded)"
            }
        }
    } catch {
        Write-Output "  ERROR: $_"
    }

    Write-Output "Done!"
}

# Execute on remote PC
try {
    Invoke-Command -ComputerName $RemotePC -ScriptBlock $RemoteCommand -ErrorAction Stop
} catch {
    Write-Host "ERROR: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "Check results above" -ForegroundColor Cyan
