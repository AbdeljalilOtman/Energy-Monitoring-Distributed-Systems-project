# Multi-Node Testing Guide: 2 Computers via WiFi Router

## Overview

This guide walks you through setting up a distributed ML workload monitoring system with **2 computers connected via WiFi router**:
- **Computer 1 (Central):** Runs Flask backend + dashboard (central monitoring server)
- **Computer 2 (Edge Node):** Runs energy monitoring daemon (transmits metrics to central)

Both computers sync in real-time, displaying performance metrics on a shared dashboard.

---

## Network Architecture

```
WiFi Router (192.168.1.1)
    |
    +--- Computer 1 (Central Server) --- 192.168.1.100
    |     ├── Flask Backend (port 5000)
    |     ├── Dashboard (port 5000)
    |     └── SQLite Database
    |
    +--- Computer 2 (Edge Node) --- 192.168.1.101
          └── Energy Monitoring Daemon
              └── Transmits to 192.168.1.100:5000
```

---

## Prerequisites

### **Computer 1 (Central Server)**

- Python 3.11+ installed
- Dependencies: `pip install flask flask-cors flask-socketio psutil requests python-socketio`
- Your backend project files:
  ```
  daemon_project/
  ├── app.py
  ├── daemon.py
  ├── db_connector.py
  ├── dashboard.html
  ├── requirements.txt
  └── config.json
  ```

### **Computer 2 (Edge Node)**

- Python 3.11+ installed  
- Dependencies: `pip install psutil requests`
- Colleague's daemon files:
  ```
  KPIs Extraction/
  ├── daemon.py
  ├── payload_builder.py
  ├── cpu_metrics.py
  ├── power_metrics.py
  ├── transformer.py
  └── config.json
  ```

### **Network Requirements**

- ✅ Both computers on same WiFi network
- ✅ Both can ping each other (no firewall blocking)
- ✅ No VPN or corporate network isolation
- ✅ Stable WiFi connection (2.4GHz or 5GHz)

---

## Step 1: Find Static IP Addresses

### **On Computer 1 (Central Server) — Windows:**

```powershell
# Get IP address
ipconfig

# Look for IPv4 Address under WiFi adapter (e.g., 192.168.1.100)
```

Expected output:
```
Wireless LAN adapter WiFi:
   Connection-specific DNS Suffix: local
   IPv4 Address. . . . . . . . . . : 192.168.1.100
   Subnet Mask . . . . . . . . . . : 255.255.255.0
   Default Gateway . . . . . . . . : 192.168.1.1
```

### **On Computer 2 (Edge Node) — Windows:**

```powershell
# Get IP address
ipconfig

# Look for IPv4 Address under WiFi adapter (e.g., 192.168.1.101)
```

### **Assign Static IPs (Recommended)**

To avoid IP changes, configure static IPs on your router:

1. **Log into router:** Open browser → `192.168.1.1`
2. **Find DHCP settings** in router admin panel
3. **Reserve IPs** for both computers:
   - Computer 1: `192.168.1.100`
   - Computer 2: `192.168.1.101`
4. **Save and restart** router

---

## Step 2: Verify Network Connectivity

### **From Computer 2 → Computer 1:**

```powershell
# Ping central server
ping 192.168.1.100

# Expected output: 4 packets sent, 4 received, 0% loss
```

### **From Computer 1 → Computer 2:**

```powershell
# Ping edge node
ping 192.168.1.101

# Expected output: 4 packets sent, 4 received, 0% loss
```

If ping fails:
- ✅ Check WiFi connection on both computers
- ✅ Verify same network (SSID)
- ✅ Disable Windows Firewall (temporarily for testing)
- ✅ Check router WiFi band (2.4GHz allows older devices)

---

## Step 3: Start Central Backend Server

### **On Computer 1:**

```powershell
# Navigate to backend directory
cd "C:\path\to\daemon_project"

# Install dependencies (if not done)
pip install -r requirements.txt

# Start Flask server (listens on 0.0.0.0:5000 = all interfaces)
python app.py

# Expected output:
# Running on http://0.0.0.0:5000
# WARNING: This is a development server. Do not use in production.
```

**Don't close this terminal!** The backend must stay running.

### **Verify Backend is Accessible:**

```powershell
# In new PowerShell window on Computer 1
curl http://localhost:5000

# Expected: HTML dashboard content returned
```

---

## Step 4: Configure Edge Node Daemon

### **On Computer 2:**

Edit `KPIs Extraction\config.json`:

```json
{
  "node_config": {
    "node_id": "edge-node-laptop",
    "workload_tag": "training",
    "poll_interval_sec": 5.0,
    "backend_url": "http://192.168.1.100:5000",
    "dry_run": false
  }
}
```

**Key Changes:**
- `node_id`: Descriptive name for this node (e.g., "GPU-Laptop", "Server-2")
- `backend_url`: **MUST be Computer 1's IP**, not localhost
- `dry_run`: **false** to actually transmit (test with true first)

---

## Step 5: Test Daemon in Dry-Run Mode (Local Only)

### **On Computer 2:**

```powershell
# Navigate to daemon directory
cd "C:\path\to\energy-monitoring-temp\KPIs Extraction"

# Update config: set dry_run: true
# Edit config.json → "dry_run": true

# Run daemon (prints to console, no network transmission)
python daemon.py

# Expected output:
# Starting Telemetry Daemon on Node [edge-node-laptop]
# Poll Interval: 5.0s | Workload: training
# Running in DRY RUN mode. Data will NOT be transmitted.
# [DRY-RUN] Would transmit 25 records to backend.
# [DRY-RUN] Would transmit 25 records to backend.
# (repeats every 5 seconds)
```

### **Verify Metrics Collection:**

If metrics are printed, the collector is working ✅

If errors appear:
- Check psutil is installed: `pip install psutil`
- On Windows, power metrics may need LibreHardwareMonitor running
- Temperature sensors might not be available on some systems (OK, will show None)

---

## Step 6: Test Network Connectivity (Before Live Transmission)

### **On Computer 2:**

```powershell
# Test if Computer 1 is reachable
curl http://192.168.1.100:5000/api/dashboard/summary

# Expected: JSON response with empty arrays (no data yet)
# Example:
# {
#   "nodes": [],
#   "summary": {...}
# }
```

If this fails:
- ✅ Check Computer 1 IP address is correct
- ✅ Verify backend is still running
- ✅ Check Windows Firewall allows Python
- ✅ Disable firewall: `netsh advfirewall set allprofiles state off`

---

## Step 7: Enable Live Transmission

### **On Computer 2:**

Edit `config.json`:

```json
{
  "node_config": {
    "node_id": "edge-node-laptop",
    "workload_tag": "training",
    "poll_interval_sec": 5.0,
    "backend_url": "http://192.168.1.100:5000",
    "dry_run": false
  }
}
```

Change `"dry_run": false` to **enable transmission**.

### **Start Daemon:**

```powershell
# Start sending real data to backend
python daemon.py

# Expected output:
# Starting Telemetry Daemon on Node [edge-node-laptop]
# Poll Interval: 5.0s | Workload: training
# Successfully transmitted 25 records to backend
# Successfully transmitted 25 records to backend.
# (repeats every 5 seconds)
```

**Keep this running!** The daemon will continuously send data.

---

## Step 8: Open Dashboard

### **On Computer 1 (or any browser on network):**

Open browser and navigate to:

```
http://localhost:5000
```

Or from another computer:

```
http://192.168.1.100:5000
```

### **Expected Dashboard:**

```
┌─────────────────────────────────────┐
│   ML Workload Monitoring Dashboard  │
├─────────────────────────────────────┤
│                                     │
│  Connected Nodes: 1                 │
│  ├─ edge-node-laptop                │
│  │  Status: Connected               │
│  │  Last Update: 2m ago             │
│  │  Workload: training              │
│  │                                  │
│  │  CPU_Utility:      45.5%         │
│  │  Memory_Usage:     65.3%         │
│  │  Power_Watts:      150.2W        │
│  │                                  │
│  │  [Real-time graphs showing...]   │
│  │                                  │
└─────────────────────────────────────┘
```

---

## Step 9: Verify Real-Time Data Flow

### **Dashboard Verification:**

| Metric | Expected Behavior | Status |
|--------|-------------------|--------|
| Node appears | "edge-node-laptop" shows in connected nodes | ✅ |
| Status shows "Connected" | Green indicator, timestamp updates | ✅ |
| Metrics update every 5s | CPU, Memory, Power values change | ✅ |
| Graphs animate | Real-time line charts show trends | ✅ |
| Workload tag shows | "training" displays in node details | ✅ |

### **Testing Workload Change:**

While daemon is running, on Computer 2:

```powershell
# Stop daemon (Ctrl+C)
# Edit config.json → change "workload_tag": "inference"
# Restart daemon

python daemon.py

# On dashboard: workload tag should update to "inference"
```

---

## Step 10: Multi-Computer Stress Test

### **Add Load to Computer 2:**

While daemon is running, simulate workload:

```powershell
# Option 1: CPU stress (opens many processes)
# Create CPU load script: stress.py
# for i in range(8): # 8 threads
#     import multiprocessing
#     p = multiprocessing.Process(target=lambda: sum(range(10**7)) for _ in range(100))
#     p.start()
# time.sleep(60)
# p.terminate()

python stress.py

# Option 2: Memory stress
# python -c "x = [1]*int(1e8); import time; time.sleep(60)"

# Option 3: Disk stress
# dd if=/dev/zero of=testfile.bin bs=1M count=1000

# Watch dashboard: CPU_Utility should spike to 60-90%
```

### **On Dashboard:**

Observe:
- ✅ CPU_Utility increases to 60-90%
- ✅ Memory_Usage spikes
- ✅ Graphs show real-time response
- ✅ Data updates every 5 seconds without interruption

---

## Step 11: Add Second Edge Node (Optional)

To test multiple nodes:

### **On Computer 2 (or a Third Computer):**

Create second daemon instance:

```powershell
# Copy KPIs Extraction folder to new location (or Computer 3)
# Edit config.json:

{
  "node_config": {
    "node_id": "edge-node-server-2",
    "workload_tag": "inference",
    "poll_interval_sec": 5.0,
    "backend_url": "http://192.168.1.100:5000",
    "dry_run": false
  }
}

# Start daemon
python daemon.py
```

### **On Dashboard:**

You should now see:

```
Connected Nodes: 2
├─ edge-node-laptop (workload: training)
└─ edge-node-server-2 (workload: inference)
```

Each node displays independently with separate metrics and graphs.

---

## Troubleshooting Guide

### **Issue 1: Dashboard shows "No Nodes Connected"**

**Symptoms:** Dashboard loads but no nodes appear.

**Solutions:**
1. ✅ Check backend is running: `curl http://localhost:5000/api/dashboard/summary`
2. ✅ Check daemon logs: Should show "Successfully transmitted X records"
3. ✅ Verify daemon is running on Computer 2
4. ✅ Check `backend_url` in config matches Computer 1 IP
5. ✅ Disable firewall: `netsh advfirewall set allprofiles state off`

---

### **Issue 2: Daemon shows "Transmission failed: Connection refused"**

**Symptoms:** Daemon logs: `ERROR - Transmission failed: [Errno 111] Connection refused`

**Solutions:**
1. ✅ Verify backend is running on Computer 1
2. ✅ Check IP address: `ipconfig` on Computer 1
3. ✅ Verify port 5000 is open: `netstat -an | findstr 5000`
4. ✅ Test connectivity: `ping 192.168.1.100`
5. ✅ Try with Windows Firewall disabled (temporary)

---

### **Issue 3: High latency / slow data updates**

**Symptoms:** Dashboard updates slowly, delays of 10+ seconds

**Solutions:**
1. ✅ Reduce `poll_interval_sec` in config (currently 5.0s)
2. ✅ Check WiFi signal strength: Should be -40 to -70 dBm
3. ✅ Move closer to router or switch to 5GHz band
4. ✅ Check network interference: WiFi analyzer shows channel saturation
5. ✅ Restart router / WiFi connection

---

### **Issue 4: Missing power metrics / temperature shows None**

**Symptoms:** Power_Watts, CPU_Temperature show as None or 0.0

**Solutions:**
1. ✅ **Windows:** Install and run LibreHardwareMonitor with Web Server enabled (port 8085)
   - Download: https://github.com/LibreHardwareMonitor/LibreHardwareMonitor
   - Run as Administrator
   - Enable Web Server in settings

2. ✅ **Linux:** Install powercap tools: `sudo apt install linux-tools-generic`

3. ✅ Power metrics are optional; CPU/Memory still work without them

---

### **Issue 5: Dashboard refreshes but no data points**

**Symptoms:** Dashboard loads, node appears, but no metrics display

**Solutions:**
1. ✅ Check daemon is collecting metrics: Run locally with `dry_run: true`
2. ✅ Verify database file exists: `daemon_project/test_db/metrics.db`
3. ✅ Check backend logs for errors
4. ✅ Restart backend server

---

### **Issue 6: Firewall blocking Port 5000**

**Symptoms:** Can ping computer but `curl http://192.168.1.100:5000` times out

**Solutions:**

**Option A: Disable Firewall (Testing Only)**
```powershell
# Disable Windows Firewall
netsh advfirewall set allprofiles state off

# Re-enable when done
netsh advfirewall set allprofiles state on
```

**Option B: Add Firewall Exception (Recommended)**
```powershell
# Allow Python through firewall
netsh advfirewall firewall add rule name="Python" dir=in action=allow program="C:\Python311\python.exe"

# Allow port 5000
netsh advfirewall firewall add rule name="Port 5000" dir=in action=allow protocol=tcp localport=5000
```

---

## Testing Checklist

Print this out and check off as you go:

### **Pre-Deployment**
- [ ] Both computers on same WiFi network
- [ ] Static IPs assigned (192.168.1.100, 192.168.1.101)
- [ ] Ping test successful both directions
- [ ] Python 3.11+ installed on both
- [ ] Dependencies installed: `pip install flask flask-cors flask-socketio psutil requests`

### **Backend Setup**
- [ ] Backend files copied to Computer 1
- [ ] Flask server starts: `python app.py`
- [ ] Dashboard accessible: `http://localhost:5000`
- [ ] API endpoint works: `curl http://localhost:5000/api/dashboard/summary`

### **Daemon Setup**
- [ ] Daemon files copied to Computer 2
- [ ] config.json updated with Computer 1 IP
- [ ] Dry-run test successful (prints metrics)
- [ ] Network test successful: `curl http://192.168.1.100:5000`

### **Live Testing**
- [ ] Daemon configured with `dry_run: false`
- [ ] Daemon transmits successfully (logs show "Successfully transmitted")
- [ ] Dashboard shows node as "Connected"
- [ ] Metrics display and update every 5 seconds
- [ ] Change workload_tag and verify update on dashboard

### **Stress Testing**
- [ ] Applied CPU load, CPU_Utility increases
- [ ] Applied memory load, Memory_Usage increases
- [ ] Graphs show real-time trends
- [ ] No data loss during load

### **Multi-Node Testing (Optional)**
- [ ] Second node configured
- [ ] Dashboard shows 2 connected nodes
- [ ] Each node has separate metrics
- [ ] Independent workload tags working

---

## Performance Baseline

Expected metrics on typical systems:

| Metric | Typical Range | Notes |
|--------|---|---|
| CPU_Utility | 5-15% (idle) | Spikes during workload |
| Memory_Usage | 30-60% | Depends on OS/apps |
| Disk_IO_Write_MB | 0-50 MB/5s | Depends on write activity |
| Power_Watts | 20-100W (idle) | Varies by hardware |
| Data Transmission | 1-2 KB per record | ~25 records = 50KB per transmission |
| Network Latency | <10ms on LAN | <100ms acceptable |

---

## Post-Testing Cleanup

When testing is complete:

```powershell
# On Computer 2: Stop daemon (Ctrl+C)

# On Computer 1: Stop backend (Ctrl+C)

# Optional: Re-enable firewall
netsh advfirewall set allprofiles state on

# Optional: Clean up test files
rm -r test_db/
rm -r *.db
```

---

## Success Criteria

✅ **Testing is successful if:**
1. Two computers communicate over WiFi
2. Backend runs continuously without crashes
3. Daemon transmits metrics every 5 seconds
4. Dashboard displays real-time data from 1+ nodes
5. Node status shows "Connected" with recent timestamp
6. Metrics update without missing data points
7. Workload tags are correctly displayed
8. No errors in backend or daemon logs

---

## Next Steps

Once testing succeeds:

1. **Deploy to Production:** Use static IPs and fixed locations
2. **Scale Up:** Add more nodes with different workload_tags
3. **Monitor:** Keep dashboard open during actual ML workloads
4. **Optimize:** Adjust `poll_interval_sec` based on real-time needs
5. **Archive:** Implement data archival for long-term history

---

**Need Help?** Check the troubleshooting section above or review logs:
- Backend logs: Look at terminal output where `python app.py` is running
- Daemon logs: Look at terminal output where `python daemon.py` is running

**Status:** ✅ Ready for 2-computer testing!
