# Script to start transcriber server on remote PC
$RemoteHost = "User1@100.102.178.110"

Write-Host "Starting transcriber server on remote PC..." -ForegroundColor Cyan

# Kill existing Python processes
ssh -o StrictHostKeyChecking=no $RemoteHost "taskkill /F /IM python.exe 2`$null"

# Wait a bit
Start-Sleep -Seconds 2

# Start server in background using wmic
ssh -o StrictHostKeyChecking=no $RemoteHost "wmic process call create 'python -m uvicorn server:app --host 0.0.0.0 --port 8000','C:\Users\User1\Desktop\Transcriber\TranscriberServer'"

Write-Host "Server start command sent. Waiting for initialization..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Check if port is open
$Result = Test-NetConnection -ComputerName 100.102.178.110 -Port 8000
if ($Result.TcpTestSucceeded) {
    Write-Host "SUCCESS: Port 8000 is open!" -ForegroundColor Green
    curl -s http://100.102.178.110:8000/health
} else {
    Write-Host "FAILED: Port 8000 is still closed" -ForegroundColor Red
    Write-Host "Checking Python processes..."
    ssh -o StrictHostKeyChecking=no $RemoteHost "tasklist | findstr python"
}
