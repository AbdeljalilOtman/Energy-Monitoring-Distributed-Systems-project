# ML Workload Monitoring Deployment Guide

## Overview

This guide covers deploying the KPI daemon across multiple nodes (Windows and Linux workstations) for **ML workload monitoring** with a central dashboard server collecting and visualizing metrics from training, inference, and data preparation workloads.

---

## Architecture

```
                              ┌──────────────────────────────┐
                              │   Central Dashboard          │
                              │   (Flask + WebSocket)        │
                              │   ML Workload Monitoring     │
                              │   Port 5000                  │
                              └──────────┬───────────────────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    │                    │                    │
          ┌─────────▼──────────┐ ┌───────▼────────┐ ┌────────▼────────┐
          │ Windows Node 1     │ │ Windows Node 2 │ │ Linux Node 1    │
          │ Training, Inference│ │ Data Prep      │ │ Inference       │
          │ Daemon: KPI Push   │ │ Daemon: KPI    │ │ Daemon: KPI Sync│
          └────────────────────┘ └────────────────┘ └─────────────────┘
```

---

## Prerequisites

### Network Requirements
- All nodes must have **LAN connectivity** (as specified in MLab infrastructure)
- **Central dashboard server IP**: 192.168.1.100 (example - replace with your server IP)
- **Port 5000** must be open/accessible for HTTP on the central server
- All nodes must reach the central server on port 5000

### Software Requirements

**All Nodes (Windows & Linux):**
- Python 3.8+
- pip package manager
- Git (optional, for cloning repo)

**Central Dashboard Server:**
- Python 3.8+
- Same dependencies as nodes (can be any machine accessible by all nodes)

### Data Structure

The daemon sends KPI data in this format for workload classification:

```json
{
  "timestamp": "2024-01-15T14:30:45Z",
  "metrics": [
    {
      "NodeID": "mlab_node_1",
      "WorkloadTag": "training",
      "KPI_name": "CPU_Utility",
      "Value": 45.2
    }
  ]
}
```

---

## Step 1: Prepare Central Dashboard Server

### Option A: Windows Server

```powershell
# Run as Administrator
mkdir C:\daemon_project
cd C:\daemon_project

# Copy project files or clone repository

# Install Python dependencies
pip install -r requirements.txt

# Run the Flask dashboard server
python app.py
```

**Expected output:**
```
 * Running on http://0.0.0.0:5000
Listening for ML workload KPI data...
```

Access dashboard at: `http://192.168.1.100:5000`

### Option B: Linux Server

```bash
# Create project directory
sudo mkdir -p /opt/daemon_project
cd /opt/daemon_project

# Copy project files
sudo cp -r ~/daemon_project/* /opt/daemon_project/

# Install Python dependencies
sudo python3 -m pip install -r requirements.txt

# Run in background (option 1: tmux)
tmux new-session -d -s dashboard "python3 app.py"

# Or run in background (option 2: nohup)
nohup python3 app.py > dashboard.log 2>&1 &
```

**Verify running:**
```bash
curl http://localhost:5000
```

---

## Step 2: Deploy Daemon on Windows Nodes

### Automated Setup (Recommended)

Use the provided PowerShell script:

```powershell
# Run as Administrator
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\setup_windows.ps1 -DashboardURL "http://192.168.1.100:5000" `
                    -NodeID "mlab_node_1" `
                    -PollingInterval 5
```

### Manual Setup (Alternative)

```powershell
# Create directory
mkdir C:\daemon_node
cd C:\daemon_node

# Copy project files
# (daemon_project contents)

# Install Python dependencies
pip install -r requirements.txt

# Configure the daemon - IMPORTANT: Use NodeID, not node_id
# Edit config.json:
{
  "NodeID": "mlab_node_1",
  "dashboard_url": "http://192.168.1.100:5000",
  "polling_interval_seconds": 5
}

# Test daemon connection
python daemon.py

# For production: Use Windows Task Scheduler or create service
```

### Verify Daemon is Running

```powershell
# Check for Python process
Get-Process python

# Check dashboard received data
# Open http://192.168.1.100:5000 and confirm mlab_node_1 appears
```

---

## Step 3: Deploy Daemon on Linux Nodes

### Automated Setup (Recommended)

Use the provided Bash script:

```bash
chmod +x setup_linux.sh

sudo ./setup_linux.sh \
    --dashboard-url "http://192.168.1.100:5000" \
    --NodeID "mlab_node_2" \
    --polling-interval 5
```

### Manual Setup (Alternative)

```bash
# Create directory
sudo mkdir -p /opt/daemon_node
cd /opt/daemon_node

# Copy project files
sudo cp -r ~/daemon_project/* /opt/daemon_node/

# Install Python dependencies
sudo python3 -m pip install -r requirements.txt

# Configure the daemon - IMPORTANT: Use NodeID, not node_id
# Edit config.json:
{
  "NodeID": "mlab_node_2",
  "dashboard_url": "http://192.168.1.100:5000",
  "polling_interval_seconds": 5
}

sudo nano config.json

# Test daemon connection
sudo python3 daemon.py

# For production: Create systemd service (see below)
```

### Verify Daemon Connection

```bash
# Check Python process
ps aux | grep daemon.py

# Check dashboard received data
# Open http://192.168.1.100:5000 and confirm mlab_node_2 appears
# Verify workload tags: training, inference, data_prep
```

---

## Step 4: Production Deployment - Systemd Service (Linux)

### Create systemd Service File

```bash
sudo nano /etc/systemd/system/kpi-daemon.service
```

**Paste this content:**

```ini
[Unit]
Description=ML Workload KPI Monitoring Daemon
After=network.target

[Service]
Type=simple
User=daemon_user
WorkingDirectory=/opt/daemon_node
ExecStart=/usr/bin/python3 /opt/daemon_node/daemon.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Enable and start:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable kpi-daemon.service
sudo systemctl start kpi-daemon.service

# Verify status
sudo systemctl status kpi-daemon.service

# View logs
sudo journalctl -u kpi-daemon.service -f
```

---

## Step 5: Windows Service Setup (Optional)

### Using NSSM (Non-Sucking Service Manager)

```powershell
# Download and install NSSM
# From: https://nssm.cc/download

# Extract and navigate to NSSM folder
cd C:\nssm-2.24\win64

# Install service
.\nssm.exe install MLWorkloadDaemon "C:\Python39\python.exe" "C:\daemon_node\daemon.py"
.\nssm.exe set MLWorkloadDaemon AppDirectory "C:\daemon_node"
.\nssm.exe set MLWorkloadDaemon AppStdout "C:\daemon_node\logs\daemon.log"
.\nssm.exe set MLWorkloadDaemon AppStderr "C:\daemon_node\logs\daemon.log"

# Start service
net start MLWorkloadDaemon

# Verify in Services
services.msc
```

---

## Step 6: Multi-Node Configuration Examples

### Windows Node 1 - config.json
```json
{
  "polling_interval_seconds": 5,
  "NodeID": "mlab_node_1",
  "dashboard_url": "http://192.168.1.100:5000",
  "kpi_source": "kpi_data.json"
}
```

### Windows Node 2 - config.json
```json
{
  "polling_interval_seconds": 5,
  "NodeID": "mlab_node_2",
  "dashboard_url": "http://192.168.1.100:5000",
  "kpi_source": "kpi_data.json"
}
```

### Linux Node - config.json
```json
{
  "polling_interval_seconds": 5,
  "NodeID": "mlab_node_3",
  "dashboard_url": "http://192.168.1.100:5000",
  "kpi_source": "kpi_data.json"
}
```

---

## Step 7: Network Connectivity Verification

### From Windows Node

```powershell
# Test connectivity to dashboard
Test-Connection -ComputerName 192.168.1.100 -Count 4

# Test port 5000
Test-NetConnection -ComputerName 192.168.1.100 -Port 5000
```

### From Linux Node

```bash
# Test connectivity to dashboard
ping -c 4 192.168.1.100

# Test port 5000
telnet 192.168.1.100 5000
# Or using nc (netcat)
nc -zv 192.168.1.100 5000
```

---

## Step 8: Data Flow Verification

### Check Dashboard Registration

```
Dashboard console output should show:
INFO - Node windows_workstation_1 registered from 192.168.1.x
INFO - Node linux_vm_1 registered from 192.168.1.y
```

### Check Data Submission

```
Dashboard console should show:
INFO - Received 2 KPI records from windows_workstation_1
INFO - Received 2 KPI records from linux_vm_1
```

### View Dashboard

Open browser: `http://192.168.1.100:5000`

Expected to see:
- ✅ Active nodes count
- ✅ Node health status (Healthy/Unhealthy)
- ✅ CPU utility and frequency graphs
- ✅ Real-time updates

---

## Step 9: Optimize Polling Intervals

To **minimize CPU overhead** on nodes:

| Scenario | Interval | Rationale |
|----------|----------|-----------|
| Real-time monitoring | 2-3 sec | Frequent updates, higher CPU |
| Balanced | 5-10 sec | **RECOMMENDED** |
| Low overhead | 30+ sec | Minimal CPU impact, less granular |

### Adjust in `config.json`

```json
"polling_interval_seconds": 10  // Increase for lower overhead
```

---

## Troubleshooting

### Node not appearing in dashboard

1. **Check connectivity:**
   ```bash
   ping 192.168.1.100
   curl http://192.168.1.100:5000/api/nodes
   ```

2. **Check daemon logs:**
   ```
   Windows: Look at console output
   Linux: sudo journalctl -u kpi-daemon.service -n 50
   ```

3. **Verify config.json:**
   - `dashboard_url` must be correct
   - Node must be able to reach that IP/port

### Data not updating

1. **Check `kpi_data.json` file:**
   ```bash
   # Verify file exists and is valid JSON
   cat kpi_data.json
   ```

2. **Check daemon is running:**
   ```bash
   # Windows: Check Task Manager or Services
   # Linux: sudo systemctl status kpi-daemon.service
   ```

3. **Increase polling interval to test:**
   ```json
   "polling_interval_seconds": 2
   ```

### Dashboard showing unhealthy nodes

- Nodes are marked unhealthy if no update in 30 seconds
- Check `kpi_data.json` is being updated regularly
- Verify daemon is still running

---

## Performance Tuning

### Reduce Network Overhead

```json
{
  "polling_interval_seconds": 10,  // Increase from 5 to 10
  "kpi_source": "kpi_data.json",
  ...
}
```

### Optimize Dashboard Query Load

```python
# In app.py - modify data retention
# Limit to last 50 records per node instead of 100
QUERY_LIMIT = 50
```

---

## Rollback & Cleanup

### Windows

```powershell
# Stop daemon
net stop KPIDaemon  # If running as service
# Or kill process
taskkill /IM python.exe /F

# Remove directory
Remove-Item -Recurse C:\daemon_node
```

### Linux

```bash
# Stop systemd service
sudo systemctl stop kpi-daemon.service
sudo systemctl disable kpi-daemon.service

# Remove systemd file
sudo rm /etc/systemd/system/kpi-daemon.service
sudo systemctl daemon-reload

# Remove directory
sudo rm -rf /opt/daemon_node
```

---

## Next Steps

1. ✅ Dashboard is viewing real-time data from multiple nodes
2. ✅ Configure alerting based on thresholds
3. ✅ Set up log aggregation
4. ✅ Add more nodes as needed
5. ✅ Switch to production database (MongoDB, PostgreSQL)
