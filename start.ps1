param (
    [switch]$Stop
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

$PidFile = "$Root\.launcher_pids"

if ($Stop) {
    Write-Host "Stopping services..." -ForegroundColor Cyan
    if (Test-Path $PidFile) {
        $Pids = Get-Content $PidFile
        foreach ($p in $Pids) {
            if ($p -match '^\d+$') {
                $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
                if ($proc) {
                    Write-Host "Stopping process ID $p..."
                    Stop-Process -Id $p -Force
                }
            }
        }
        Remove-Item $PidFile -Force
        Write-Host "Services stopped." -ForegroundColor Green
    } else {
        Write-Host "No .launcher_pids file found. Services may not be running." -ForegroundColor Yellow
    }
    exit
}

Write-Host "Starting Shipping Document Verification System..." -ForegroundColor Cyan

# 1. Project root
Write-Host "Project Root: $Root"

# 2. Check Python
$PythonCmd = "python"
if (-not (Get-Command $PythonCmd -ErrorAction SilentlyContinue)) {
    Write-Error "Python is not installed or not in PATH."
    exit 1
}

# 3. Virtual Environment
$VenvDir = ""
if (Test-Path "$Root\.venv") {
    $VenvDir = "$Root\.venv"
} elseif (Test-Path "$Root\venv") {
    $VenvDir = "$Root\venv"
}

if (-not $VenvDir) {
    Write-Host "Creating virtual environment '.venv'..."
    & $PythonCmd -m venv .venv
    $VenvDir = "$Root\.venv"
}

$PythonExe = "$VenvDir\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    Write-Error "Could not find python.exe in virtual environment."
    exit 1
}
Write-Host "Using Python: $PythonExe"

# 4. Install dependencies
if (Test-Path "$Root\requirements.txt") {
    Write-Host "Installing dependencies..."
    & $PythonExe -m pip install -r requirements.txt --disable-pip-version-check | Out-Null
}

# 5. Load .env
if (Test-Path "$Root\.env") {
    $EnvContent = Get-Content "$Root\.env"
    $HasKey = $false
    foreach ($line in $EnvContent) {
        if ($line -match "^\s*GEMINI_API_KEY\s*=") {
            $HasKey = $true
            # Set the env var for the current process so child processes inherit it
            $val = $line -replace "^\s*GEMINI_API_KEY\s*=\s*", ""
            $env:GEMINI_API_KEY = $val.Trim("'").Trim('"')
            break
        }
    }
    if ($HasKey) {
        Write-Host "GEMINI_API_KEY detected in .env" -ForegroundColor Green
    } else {
        Write-Host "GEMINI_API_KEY NOT detected in .env" -ForegroundColor Yellow
    }
} else {
    Write-Host ".env file not found at project root." -ForegroundColor Yellow
}

# Ensure logs dir exists
if (-not (Test-Path "$Root\logs")) {
    New-Item -ItemType Directory -Path "$Root\logs" | Out-Null
}

$StartedPids = @()

# 6. Start FastAPI Backend
$BackendBusy = Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue
if ($BackendBusy) {
    Write-Host "Port 8080 is busy. Checking if it's our backend..."
    try {
        $res = Invoke-RestMethod -Uri "http://localhost:8080/health" -Method Get -TimeoutSec 2
        if ($res.status -eq "ok" -or $res -match "ok") {
            Write-Host "Our backend is already running on port 8080." -ForegroundColor Green
        } else {
            Write-Error "Port 8080 is busy by an unknown service."
            exit 1
        }
    } catch {
        Write-Error "Port 8080 is busy but /health failed. Please free port 8080."
        exit 1
    }
} else {
    Write-Host "Starting FastAPI backend on port 8080..."
    $env:DATA_DIR = "..\data_v2"
    $env:GROUND_TRUTH = "..\data_v2\ground_truth.json"
    
    $BackendProc = Start-Process -NoNewWindow -FilePath $PythonExe -ArgumentList "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080" -WorkingDirectory "$Root\server" -RedirectStandardOutput "$Root\logs\backend.log" -RedirectStandardError "$Root\logs\backend_error.log" -PassThru
    $StartedPids += $BackendProc.Id
    
    # 7. Wait for backend
    $BackendReady = $false
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep -Seconds 2
        try {
            $res = Invoke-RestMethod -Uri "http://localhost:8080/health" -Method Get -ErrorAction Stop
            $BackendReady = $true
            break
        } catch {
            if ($BackendProc.HasExited) {
                Write-Error "Backend process exited prematurely. Check logs/backend_error.log."
                if ($StartedPids.Count -gt 0) { Stop-Process -Id $StartedPids -Force -ErrorAction SilentlyContinue }
                exit 1
            }
        }
    }
    
    if (-not $BackendReady) {
        Write-Error "Backend failed to become ready in time."
        if ($StartedPids.Count -gt 0) { Stop-Process -Id $StartedPids -Force -ErrorAction SilentlyContinue }
        exit 1
    }
    Write-Host "Backend is ready!" -ForegroundColor Green
}

# 8. Start Flask UI
$UiBusy = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue
if ($UiBusy) {
    Write-Host "Port 5000 is busy. Assuming UI is already running." -ForegroundColor Green
} else {
    Write-Host "Starting Flask UI on port 5000..."
    $UiProc = Start-Process -NoNewWindow -FilePath $PythonExe -ArgumentList "app_ui.py" -WorkingDirectory $Root -RedirectStandardOutput "$Root\logs\ui.log" -RedirectStandardError "$Root\logs\ui_error.log" -PassThru
    $StartedPids += $UiProc.Id
    
    # 9. Wait for UI
    $UiReady = $false
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep -Seconds 2
        try {
            $res = Invoke-WebRequest -Uri "http://localhost:5000" -Method Get -UseBasicParsing -ErrorAction Stop
            if ($res.StatusCode -eq 200) {
                $UiReady = $true
                break
            }
        } catch {
            if ($UiProc.HasExited) {
                Write-Error "UI process exited prematurely. Check logs/ui_error.log."
                if ($StartedPids.Count -gt 0) { Stop-Process -Id $StartedPids -Force -ErrorAction SilentlyContinue }
                exit 1
            }
        }
    }
    
    if (-not $UiReady) {
        Write-Error "UI failed to become ready in time."
        if ($StartedPids.Count -gt 0) { Stop-Process -Id $StartedPids -Force -ErrorAction SilentlyContinue }
        exit 1
    }
    Write-Host "UI is ready!" -ForegroundColor Green
}

# Save PIDs
if ($StartedPids.Count -gt 0) {
    if (Test-Path $PidFile) {
        $ExistingPids = Get-Content $PidFile
        $AllPids = $ExistingPids + $StartedPids | Select-Object -Unique
        $AllPids | Out-File $PidFile
    } else {
        $StartedPids | Out-File $PidFile
    }
}

# 10. Run complete pipeline
Write-Host "Running pipeline: python main.py . --submit" -ForegroundColor Cyan
$OldErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    $env:PYTHONUNBUFFERED = "1"
    & $PythonExe main.py . --submit 2>&1 | Tee-Object -FilePath "$Root\logs\pipeline.log"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Pipeline failed with exit code $LASTEXITCODE. See logs/pipeline.log."
    }
} catch {
    Write-Error "Failed to run pipeline: $_"
}
$ErrorActionPreference = $OldErrorActionPreference

# 12. Verify files
$SubFile = "$Root\submission.json"
$ScoreFile = "$Root\score_result.json"
if ((Test-Path $SubFile) -and (Test-Path $ScoreFile)) {
    Write-Host "Output files successfully generated." -ForegroundColor Green
    
    # 13. Read and display safe summary
    $ScoreData = Get-Content $ScoreFile | ConvertFrom-Json
    
    Write-Host ""
    Write-Host "==========================="
    Write-Host "      SAFE SUMMARY         "
    Write-Host "==========================="
    Write-Host "Stage 1 Macro F1: $($ScoreData.stage1.macro_f1)"
    Write-Host "Stage 3 Defect F1: $($ScoreData.stage3.defect_f1)"
    Write-Host "End to End Rate:  $($ScoreData.end_to_end.success) / $($ScoreData.end_to_end.total)"
    Write-Host "Final Score:      $($ScoreData.final_score)"
    Write-Host "==========================="
    Write-Host ""
    
    # 14. Open Browser
    Write-Host "Opening browser to http://localhost:5000"
    Start-Process "http://localhost:5000"
} else {
    Write-Error "Pipeline did not generate submission.json and score_result.json!"
}

Write-Host "Startup complete. Servers are running in the background." -ForegroundColor Cyan
Write-Host "To stop cleanly, run: .\start.ps1 -Stop" -ForegroundColor DarkGray
