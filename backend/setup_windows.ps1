# KPI Daemon Setup Script for Windows
# Usage: .\setup_windows.ps1 -DashboardURL "http://192.168.1.100:5000" -NodeID "windows_workstation_1"

param(
    [string]$DashboardURL = "http://localhost:5000",
    [string]$NodeID = "windows_node_1",
    [int]$PollingInterval = 5,
    [string]$InstallDir = "C:\daemon_node"
)

# Colors
function Write-Success { Write-Host $args[0] -ForegroundColor Green }
function Write-Warning { Write-Host $args[0] -ForegroundColor Yellow }
function Write-Error { Write-Host $args[0] -ForegroundColor Red }

Write-Host ""
Write-Success "========================================"
Write-Success "KPI Daemon Setup Script for Windows"
Write-Success "========================================"
Write-Host ""

# Check if running as Administrator
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] 'Administrator')) {
    Write-Error "This script must be run as Administrator"
    exit 1
}

Write-Warning "Configuration:"
Write-Host "  Dashboard URL: $DashboardURL"
Write-Host "  Node ID: $NodeID"
Write-Host "  Polling Interval: ${PollingInterval}s"
Write-Host "  Install Directory: $InstallDir"
Write-Host ""

# Step 1: Check Python installation
Write-Warning "[1/6] Checking Python installation..."
try {
    $pythonVersion = python --version 2>&1
    Write-Success "✓ Python found: $pythonVersion"
} catch {
    Write-Error "Python is not installed or not in PATH"
    Write-Host "Download from: https://www.python.org/downloads/"
    exit 1
}
Write-Host ""

# Step 2: Create installation directory
Write-Warning "[2/6] Creating installation directory..."
if (Test-Path $InstallDir) {
    Write-Warning "Directory already exists at $InstallDir"
    $response = Read-Host "Overwrite? (y/N)"
    if ($response -ne 'y' -and $response -ne 'Y') {
        Write-Error "Aborting setup"
        exit 1
    }
    Remove-Item -Recurse -Force $InstallDir
}
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
New-Item -ItemType Directory -Path "$InstallDir\test_db" -Force | Out-Null
New-Item -ItemType Directory -Path "$InstallDir\logs" -Force | Out-Null
Write-Success "✓ Directory created"
Write-Host ""

# Step 3: Copy project files
Write-Warning "[3/6] Copying project files..."
$projectDir = Get-Location
Copy-Item -Path "$projectDir\daemon.py" -Destination $InstallDir -Force
Copy-Item -Path "$projectDir\db_connector.py" -Destination $InstallDir -Force
Copy-Item -Path "$projectDir\router.py" -Destination $InstallDir -Force
Copy-Item -Path "$projectDir\kpi_data.json" -Destination $InstallDir -Force
Copy-Item -Path "$projectDir\requirements.txt" -Destination $InstallDir -Force
Write-Success "✓ Files copied"
Write-Host ""

# Step 4: Install Python dependencies
Write-Warning "[4/6] Installing Python dependencies..."
Set-Location $InstallDir
python -m pip install -q -r requirements.txt
if ($LASTEXITCODE -eq 0) {
    Write-Success "✓ Dependencies installed"
} else {
    Write-Error "Failed to install dependencies"
    exit 1
}
Write-Host ""

# Step 5: Configure daemon
Write-Warning "[5/6] Configuring daemon..."
$configContent = @{
    polling_interval_seconds = $PollingInterval
    node_id = $NodeID
    kpi_source = "kpi_data.json"
    dashboard_url = $DashboardURL
    database = @{
        type = "sqlite"
        path = "$InstallDir\test_db\benchmark_test.db"
    }
} | ConvertTo-Json
$configContent | Out-File -FilePath "$InstallDir\config.json" -Encoding UTF8
Write-Success "✓ Config created at $InstallDir\config.json"
Write-Host ""

# Step 6: Create batch file for easy startup
Write-Warning "[6/6] Creating startup scripts..."
$batchContent = @"
@echo off
title KPI Daemon - $NodeID
cd /d "$InstallDir"
python daemon.py
"@
$batchContent | Out-File -FilePath "$InstallDir\start_daemon.bat" -Encoding ASCII
Write-Success "✓ Startup script created"
Write-Host ""

# Summary
Write-Host ""
Write-Success "========================================"
Write-Success "Setup Complete!"
Write-Success "========================================"
Write-Host ""

Write-Warning "Next Steps:"
Write-Host ""
Write-Host "1. Test the daemon (simple run):"
Write-Host "   ${GREEN}$InstallDir\start_daemon.bat${NC}"
Write-Host ""
Write-Host "2. Or run PowerShell directly:"
Write-Host "   Set-Location `"$InstallDir`""
Write-Host "   python daemon.py"
Write-Host ""
Write-Host "3. For production (Windows Service with NSSM):"
Write-Host "   Download NSSM from: https://nssm.cc/download"
Write-Host "   Then run (as Administrator):"
Write-Host "   nssm.exe install KPIDaemon `"$((Get-Command python).Source)`" `"$InstallDir\daemon.py`""
Write-Host "   nssm.exe start KPIDaemon"
Write-Host ""
Write-Host "4. Verify connection to dashboard:"
Write-Host "   Invoke-WebRequest -Uri `"$DashboardURL/api/nodes`" -UseBasicParsing"
Write-Host ""

Write-Warning "Configuration Details:"
Write-Host "  Config file: $InstallDir\config.json"
Write-Host "  Database: $InstallDir\test_db\benchmark_test.db"
Write-Host "  Startup script: $InstallDir\start_daemon.bat"
Write-Host ""
