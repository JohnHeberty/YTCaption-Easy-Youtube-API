# Clothes Segmentation API â€” Makefile.ps1 (PowerShell 5.1)

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("install", "start", "stop", "test", "clean", "checkpoints", "deps-check", "lint", "format", "reset", "help")]
    [string]$Target
)

$ErrorActionPreference = "Stop"

$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

$ProjectRoot  = $PSScriptRoot
$SrcDir       = Join-Path $ProjectRoot "src"
$Checkpoints  = Join-Path $ProjectRoot "checkpoints"
$Port         = 8001

function Write-Step($Msg) { Write-Host ("`n=== " + $Msg + " ===`n") -ForegroundColor Cyan }
function Write-Ok($Msg)   { Write-Host ("[OK] " + $Msg) -ForegroundColor Green }
function Write-Err($Msg)  { Write-Host ("[FAIL] " + $Msg) -ForegroundColor Red }

function Invoke-Help {
    Write-Host ""
    Write-Host "========================================="
    Write-Host "  Clothes Segmentation â€” Makefile.ps1"
    Write-Host "========================================="
    Write-Host ""
    Write-Host "  Usage: .\Makefile.ps1 -Target install|start|stop|test|clean"
    Write-Host ""
    Write-Host "  Commands:"
    Write-Host "    install       Install all Python dependencies"
    Write-Host "    start         Start API server (port 8001)"
    Write-Host "    stop          Stop API server"
    Write-Host "    test          Run regression tests against API"
    Write-Host "    clean         Remove __pycache__, .pyc, temp files"
    Write-Host "    checkpoints   Check if checkpoint files exist"
    Write-Host "    deps-check    Verify all dependencies installed"
    Write-Host "    lint          Run ruff linter"
    Write-Host "    format        Format code with ruff"
    Write-Host "    reset         Full clean + reinstall dependencies"
    Write-Host ""
}

function Invoke-Install {
    Write-Step "Installing dependencies"
    pip install -r (Join-Path $ProjectRoot "requirements.txt")
    if ($?) { Write-Ok "Dependencies installed" } else { Write-Err "Install failed" }
}

function Invoke-DepsCheck {
    Write-Step "Checking dependencies"
    python -c "import fastapi, uvicorn, torch, torchvision, cv2, supervision, PIL, numpy, h5py, pydantic" 2>$null
    if ($?) { Write-Ok "All dependencies OK" } else { Write-Err "Missing deps â€” run: .\Makefile.ps1 -Target install" }
}

function Invoke-Lint {
    Write-Step "Running ruff linter"
    ruff check (Join-Path $ProjectRoot "src") 2>&1
}

function Invoke-Format {
    Write-Step "Running ruff format"
    ruff format (Join-Path $ProjectRoot "src") 2>&1
}

function Invoke-Checkpoints {
    Write-Step "Verifying checkpoint files"
    $files = @("groundingdino_swint_ogc.pth", "sam2_hiera_large.pt", "sam2_hiera_tiny.pt")
    foreach ($f in $files) {
        $path = Join-Path $Checkpoints $f
        if (Test-Path $path) {
            $size = [math]::Round((Get-Item $path).Length / 1MB, 1)
            Write-Ok ($f + " (" + $size + " MB)")
        } else {
            Write-Err ($f + " MISSING")
        }
    }
}

function Invoke-Start {
    Write-Step ("Starting API server on port " + $Port)
    $portInUse = netstat -ano | Select-String (":" + $Port + " ")
    if ($portInUse) {
        Write-Err ("Port " + $Port + " is already in use. Run: .\Makefile.ps1 -Target stop")
        exit 1
    }
    $env:PYTHONPATH = $SrcDir
    Start-Process -FilePath "powershell" -ArgumentList "-NoExit", "-Command", ("`$env:Path=[System.Environment]::GetEnvironmentVariable('Path','Machine')+';'+[System.Environment]::GetEnvironmentVariable('Path','User'); `$env:PYTHONPATH='" + $SrcDir + "'; python -m clothes_segmentation.api.server") -WindowStyle Normal
    Write-Host "Server starting... (wait ~35s for model loading)" -ForegroundColor Yellow
    Start-Sleep 38
    $portCheck = netstat -ano | Select-String (":" + $Port + " ")
    if ($portCheck) {
        Write-Ok ("API server running on http://localhost:" + $Port)
    } else {
        Write-Err "Server failed to start. Check the PowerShell window."
    }
}

function Invoke-Stop {
    Write-Step "Stopping API server"
    $portInfo = netstat -ano | Select-String (":" + $Port + " ") | Select-Object -First 1
    if ($portInfo) {
        $pidMatch = [regex]::Matches($portInfo.Line, '\s+(\d+)\s*$')
        if ($pidMatch.Count -gt 0) {
            $pid = $pidMatch[0].Groups[1].Value
            Write-Host ("Killing PID " + $pid) -ForegroundColor Yellow
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Ok "Server stopped"
}

function Invoke-Test {
    Write-Step "Running regression tests"
    & "$PSScriptRoot\Makefile.ps1" -Target start
    try {
        Write-Host "`nWaiting 45s for model loading..." -ForegroundColor Yellow
        Start-Sleep 45
        $testFile = Join-Path $ProjectRoot "tests" "test_api.py"
        if (Test-Path $testFile) {
            python $testFile
            if ($?) { Write-Ok "Tests passed" } else { Write-Err "Tests failed" }
        } else {
            Write-Err ("test_api.py not found at " + $testFile)
        }
    } finally {
        & "$PSScriptRoot\Makefile.ps1" -Target stop
    }
}

function Invoke-Clean {
    Write-Step "Cleaning cache files"
    Get-ChildItem -Path $ProjectRoot -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
    Get-ChildItem -Path $ProjectRoot -Recurse -Include "*.pyc", "*.pyo" -File -ErrorAction SilentlyContinue | Remove-Item -Force
    Get-ChildItem -Path $ProjectRoot -Recurse -Directory -Filter ".ruff_cache" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
    Write-Ok "Clean complete"
}

function Invoke-Reset {
    & "$PSScriptRoot\Makefile.ps1" -Target clean
    & "$PSScriptRoot\Makefile.ps1" -Target install
}

# Dispatch
if ($Target -eq "help")        { Invoke-Help }
elseif ($Target -eq "install") { Invoke-Install }
elseif ($Target -eq "deps-check") { Invoke-DepsCheck }
elseif ($Target -eq "lint")    { Invoke-Lint }
elseif ($Target -eq "format")  { Invoke-Format }
elseif ($Target -eq "checkpoints") { Invoke-Checkpoints }
elseif ($Target -eq "start")   { Invoke-Start }
elseif ($Target -eq "stop")    { Invoke-Stop }
elseif ($Target -eq "test")    { Invoke-Test }
elseif ($Target -eq "clean")   { Invoke-Clean }
elseif ($Target -eq "reset")   { Invoke-Reset }
