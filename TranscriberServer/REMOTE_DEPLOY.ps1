# Remote Deployment Script for Transcriber Server
# Copies files to remote PC via SSH

$RemoteHost = "User1@100.102.178.110"
$RemoteDir = "C:\Users\User1\Desktop\Transcriber"
$LocalSrc = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Transcriber Remote Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Remote: $RemoteHost"
Write-Host "Source: $LocalSrc"
Write-Host ""

# Step 1: Create directory structure via SSH
Write-Host "[1/6] Creating directory structure..." -ForegroundColor Yellow
ssh -o StrictHostKeyChecking=no $RemoteHost "mkdir $RemoteDir\TranscriberServer 2`$null; mkdir $RemoteDir\TranscriberServer\uploads 2`$null; mkdir $RemoteDir\TranscriberServer\results 2`$null; mkdir $RemoteDir\src 2`$null; mkdir $RemoteDir\src\backends 2`$null; echo Directories created"

# Step 2: Copy server files
Write-Host ""
Write-Host "[2/6] Copying server files..." -ForegroundColor Yellow
scp -o StrictHostKeyChecking=no "$LocalSrc\server.py" "${RemoteHost}:${RemoteDir}/TranscriberServer/"
scp -o StrictHostKeyChecking=no "$LocalSrc\transcriber_wrapper.py" "${RemoteHost}:${RemoteDir}/TranscriberServer/"
scp -o StrictHostKeyChecking=no "$LocalSrc\requirements.txt" "${RemoteHost}:${RemoteDir}/TranscriberServer/"

# Step 3: Copy source files
Write-Host ""
Write-Host "[3/6] Copying source files..." -ForegroundColor Yellow
$SrcDir = Join-Path $LocalSrc "..\src"
scp -o StrictHostKeyChecking=no "$SrcDir\transcriber.py" "${RemoteHost}:${RemoteDir}/src/"
scp -o StrictHostKeyChecking=no "$SrcDir\config.py" "${RemoteHost}:${RemoteDir}/src/"
scp -o StrictHostKeyChecking=no "$SrcDir\text_processor.py" "${RemoteHost}:${RemoteDir}/src/"
scp -o StrictHostKeyChecking=no "$SrcDir\__init__.py" "${RemoteHost}:${RemoteDir}/src/"

# Step 4: Copy backend files
Write-Host ""
Write-Host "[4/6] Copying backend files..." -ForegroundColor Yellow
scp -o StrictHostKeyChecking=no "$SrcDir\backends\base.py" "${RemoteHost}:${RemoteDir}/src/backends/"
scp -o StrictHostKeyChecking=no "$SrcDir\backends\whisper_backend.py" "${RemoteHost}:${RemoteDir}/src/backends/"
scp -o StrictHostKeyChecking=no "$SrcDir\backends\__init__.py" "${RemoteHost}:${RemoteDir}/src/backends/"

# Step 5: Copy BAT file
Write-Host ""
Write-Host "[5/6] Installing autostart script..." -ForegroundColor Yellow
scp -o StrictHostKeyChecking=no "$LocalSrc\AUTOSTART_SERVEO_FINAL.bat" "${RemoteHost}:${RemoteDir}/TranscriberServer/AUTOSTART.bat"

# Step 6: Install dependencies
Write-Host ""
Write-Host "[6/6] Installing Python dependencies..." -ForegroundColor Yellow
ssh -o StrictHostKeyChecking=no $RemoteHost "cd $RemoteDir\TranscriberServer && python -m pip install -q --upgrade pip"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Deployment complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Test server manually:"
Write-Host "   ssh $RemoteHost"
Write-Host "   cd $RemoteDir\TranscriberServer"
Write-Host "   python -m uvicorn server:app --host 0.0.0.0 --port 8000"
Write-Host ""
Write-Host "2. Check health from local:"
Write-Host "   curl http://100.102.178.110:8000/health"
Write-Host ""
