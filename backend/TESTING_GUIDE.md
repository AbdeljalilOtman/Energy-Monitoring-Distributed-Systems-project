# Testing Guide - ML Workload Monitoring Dashboard

Complete step-by-step testing procedures for validating the ML workload monitoring deployment.

---

## Pre-Testing Setup

Ensure all files are in place:
```
daemon_project/
├── app.py
├── daemon.py
├── db_connector.py
├── config.json
├── kpi_data.json
├── requirements.txt
├── templates/dashboard.html
├── test_db/ (auto-created)
└── DEPLOYMENT.md
```

---

## Test 1: Dashboard Server Startup (Isolated)

**Objective:** Verify Flask dashboard starts without errors

**Prerequisites:** 
- Python 3.8+
- requirements.txt installed

**Steps:**

1. **Install dependencies:**
   ```powershell
   # Windows
   cd daemon_project
   pip install -r requirements.txt
   ```

2. **Start dashboard:**
   ```powershell
   python app.py
   ```

3. **Expected Output:**
   ```
   INFO - Starting ML Workload Monitoring Dashboard
    * Serving Flask app 'app'
    * Running on http://0.0.0.0:5000
   ```

4. **Verify:**
   ```powershell
   # In new terminal
   Invoke-WebRequest -Uri "http://localhost:5000" -UseBasicParsing
   # Should return status 200 OK
   ```

5. **Expected:** ✅ Dashboard accessible at `http://localhost:5000`

**Troubleshooting:**
- Port 5000 already in use: `netstat -ano | findstr :5000`
- Missing dependencies: `pip install flask flask-cors flask-socketio python-socketio`

---

## Test 2: Daemon Startup with ML Workload Data

**Objective:** Verify daemon starts and sends KPI data for training/inference/data_prep workloads

**Prerequisites:**
- Dashboard running on `http://localhost:5000`
- Valid config.json

**Steps:**

1. **Update config.json:**
   ```json
   {
     "polling_interval_seconds": 5,
     "NodeID": "test_node_1",
     "dashboard_url": "http://localhost:5000",
     "kpi_source": "kpi_data.json"
   }
   ```

2. **Start daemon:**
   ```powershell
   cd daemon_project
   python daemon.py
   ```

3. **Expected Output (Daemon console):**
   ```
   INFO - Node test_node_1 registered from 127.0.0.1
   INFO - Successfully registered with dashboard at http://localhost:5000
   INFO - Processed 2 node(s) KPI data
   INFO - Pushed 2 records to dashboard
   ```

4. **Expected Output (Daemon console):**
   ```
   INFO - Daemon started. Node ID: test_node_1
   INFO - Successfully registered with dashboard at http://localhost:5000
   INFO - Processed 2 node(s) KPI data
   INFO - Pushed 2 records to dashboard
   ```

5. **Verify dashboard shows node:**
   - Open `http://localhost:5000` in browser
   - Should see "1" under "Active Nodes"
   - Should see "test_node_1" card with metrics

**Expected:** ✅ Daemon registers and data flows to dashboard

---

## Test 3: Real-Time Dashboard Updates

**Objective:** Verify dashboard updates in real-time as daemon pushes data

**Prerequisites:**
- Dashboard running
- Daemon running
- Browser open to `http://localhost:5000`

**Steps:**

1. **Watch dashboard update counter:**
   - Bottom right shows update count
   - Should increment every 5 seconds (polling interval)

2. **Check graphs:**
   - Performance Trends section should show CPU and Frequency lines
   - Lines should have data points

3. **Verify node metrics:**
   - Node card shows:
     - ✅ CPU Usage (Avg)
     - ✅ CPU Usage (Max)
     - ✅ Frequency (Avg)
     - ✅ Sample count
     - ✅ Last Update timestamp

4. **Monitor console output:**
   ```
   Dashboard console shows:
   INFO - Received 2 KPI records from test_node_1
   ```

5. **Let it run for 60 seconds:**
   - Update counter should reach ~12 (60 sec / 5 sec polling)
   - Graphs should show multiple data points

**Expected:** ✅ Dashboard updates smoothly in real-time

---

## Test 4: Multi-Node Setup (Windows + Windows)

**Objective:** Verify two nodes reporting to same dashboard

**Prerequisites:**
- Dashboard running on `http://localhost:5000`
- Two separate terminals/machines available

**Steps:**

1. **Create second config for Node 2:**
   ```json
   {
     "polling_interval_seconds": 5,
     "node_id": "test_node_2",
     "dashboard_url": "http://localhost:5000",
     "kpi_source": "kpi_data.json",
     "database": {
       "type": "sqlite",
       "path": "test_db/benchmark_test.db"
     }
   }
   ```

2. **Terminal 1 - Start Node 1:**
   ```powershell
   cd daemon_project
   python daemon.py
   ```

3. **Terminal 2 - Start Node 2:**
   ```powershell
   cd daemon_project
   # Copy config_node2.json first
   python daemon.py
   ```

4. **Check dashboard:**
   - Should show "2" under Active Nodes
   - Should see both cards: test_node_1 and test_node_2
   - Each should have independent metrics

5. **Verify in console:**
   ```
   Dashboard should log:
   INFO - Node test_node_1 registered from 127.0.0.1
   INFO - Node test_node_2 registered from 127.0.0.1
   INFO - Received 2 KPI records from test_node_1
   INFO - Received 2 KPI records from test_node_2
   ```

**Expected:** ✅ Both nodes visible on dashboard with independent metrics

---

## Test 5: Network Connectivity (Windows ↔ Linux Simulation)

**Objective:** Verify daemon can push to remote dashboard (simulated)

**Prerequisites:**
- Know dashboard server IP address
- Network connectivity between machines

**Steps:**

1. **Update daemon config to use remote IP:**
   ```json
   {
     "node_id": "remote_test_node",
     "dashboard_url": "http://192.168.1.100:5000"
   }
   ```

2. **Test connectivity:**
   ```powershell
   # Windows
   Test-NetConnection -ComputerName 192.168.1.100 -Port 5000
   
   # Linux
   nc -zv 192.168.1.100 5000
   ```

3. **Start daemon:**
   ```powershell
   python daemon.py
   ```

4. **Check logs:**
   - Daemon should succeed or show clear error
   - Dashboard should show registration if network OK

**Expected:** ✅ Connection attempt succeeds or shows clear error message

---

## Test 6: Database Persistence

**Objective:** Verify data persists in SQLite database

**Prerequisites:**
- Daemon has been running for at least 30 seconds
- SQLite installed or use Python sqlite3

**Steps:**

1. **Query database:**
   ```powershell
   # Windows
   python -c "import sqlite3; conn = sqlite3.connect('daemon_project/test_db/benchmark_test.db'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM node_kpis'); print('Total records:', cursor.fetchone()[0])"
   ```

2. **View sample records:**
   ```powershell
   python -c "import sqlite3; conn = sqlite3.connect('daemon_project/test_db/benchmark_test.db'); cursor = conn.cursor(); cursor.execute('SELECT node_id, frequency_mhz, cpu_utility_percent, collected_at FROM node_kpis LIMIT 5'); [print(row) for row in cursor.fetchall()]"
   ```

3. **Expected Output:**
   ```
   Total records: 15
   ('test_node_1', 2400.0, 45.5, '2026-03-30T10:30:00.000000')
   ('test_node_1', 2400.0, 45.5, '2026-03-30T10:30:05.000000')
   ...
   ```

**Expected:** ✅ Records persisted with correct structure

---

## Test 7: Health Status Detection

**Objective:** Verify dashboard correctly marks nodes healthy/unhealthy

**Prerequisites:**
- Daemon was running and registered
- Dashboard can detect if daemon stops

**Steps:**

1. **Daemon running:**
   - Dashboard shows "healthy" status
   - Last Update is recent

2. **Stop daemon (Ctrl+C):**
   ```powershell
   # In daemon terminal, press Ctrl+C
   ```

3. **Wait 35+ seconds:**
   - Dashboard should still show node (with unhealthy status)
   - Status badge changes to red

4. **Restart daemon:**
   ```powershell
   python daemon.py
   ```

5. **Verify:**
   - Status changes back to "healthy"
   - Last Update refreshes

**Expected:** ✅ Status updates correctly based on data freshness

---

## Test 8: Polling Interval Configuration

**Objective:** Verify polling interval affects update frequency

**Prerequisites:**
- Dashboard and daemon running
- Dashboard update counter visible

**Steps:**

1. **Current polling interval (5 seconds):**
   - Watch update counter
   - Should increment every ~5 seconds
   - 60 seconds ≈ 12 updates

2. **Change config.json:**
   ```json
   "polling_interval_seconds": 2
   ```

3. **Restart daemon:**
   ```powershell
   # Ctrl+C to stop
   python daemon.py
   ```

4. **Watch update counter:**
   - Should increment every ~2 seconds
   - 60 seconds ≈ 30 updates

5. **Verify CPU impact:**
   - Open Task Manager
   - Check python.exe CPU usage
   - More frequent polling = higher CPU

**Expected:** ✅ Polling interval directly affects update frequency

---

## Test 9: Error Handling - Missing kpi_data.json

**Objective:** Verify daemon handles missing input file gracefully

**Prerequisites:**
- Daemon running

**Steps:**

1. **Rename kpi_data.json:**
   ```powershell
   Rename-Item kpi_data.json kpi_data.json.bak
   ```

2. **Watch daemon output:**
   ```
   ERROR - Failed to read KPI data: [Errno 2] No such file or directory
   ```

3. **Daemon should:**
   - ✅ Continue running
   - ✅ Retry on next polling interval
   - ❌ NOT crash

4. **Restore file:**
   ```powershell
   Rename-Item kpi_data.json.bak kpi_data.json
   ```

5. **Verify recovery:**
   - Daemon continues without restart
   - Data resumes flowing

**Expected:** ✅ Graceful error handling with recovery

---

## Test 10: Load Test - Multiple Rapid Registrations

**Objective:** Verify dashboard handles multiple simultaneous connections

**Prerequisites:**
- Dashboard running on fresh instance

**Steps:**

1. **Start 3 daemons in quick succession:**
   ```powershell
   # Terminal 1
   python daemon.py (with node_id: load_test_1)
   
   # Terminal 2
   python daemon.py (with node_id: load_test_2)
   
   # Terminal 3
   python daemon.py (with node_id: load_test_3)
   ```

2. **Check dashboard:**
   - All 3 nodes appear
   - No errors in console
   - All metrics display correctly

3. **Monitor console for registration:**
   ```
   INFO - Node load_test_1 registered from 127.0.0.1
   INFO - Node load_test_2 registered from 127.0.0.1
   INFO - Node load_test_3 registered from 127.0.0.1
   ```

4. **Verify data flows:**
   - All 3 nodes showing "healthy"
   - Graphs have data for all nodes
   - Update counter increments

**Expected:** ✅ Dashboard handles multiple nodes smoothly

---

## Automated Test Script (Optional)

```powershell
# test_deployment.ps1
$dashboardRunning = $false
$daemonRunning = $false

# Start dashboard
Start-Process python -ArgumentList "app.py" -NoNewWindow
Start-Sleep -Seconds 3

# Test connectivity
try {
    $response = Invoke-WebRequest -Uri "http://localhost:5000/api/nodes" -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Host "✓ Dashboard is running"
        $dashboardRunning = $true
    }
} catch {
    Write-Host "✗ Dashboard not accessible"
}

# Start daemon
Start-Process python -ArgumentList "daemon.py" -NoNewWindow
Start-Sleep -Seconds 5

# Check if nodes registered
try {
    $nodes = Invoke-RestMethod -Uri "http://localhost:5000/api/nodes"
    if ($nodes.Count -gt 0) {
        Write-Host "✓ Daemon registered successfully"
        Write-Host "✓ Total nodes: $($nodes.Count)"
        $daemonRunning = $true
    }
} catch {
    Write-Host "✗ No nodes registered"
}

# Summary
Write-Host ""
if ($dashboardRunning -and $daemonRunning) {
    Write-Host "✓ All tests PASSED"
} else {
    Write-Host "✗ Some tests FAILED"
}
```

---

## Test Results Summary

Create a checklist after testing:

- [ ] Test 1: Dashboard starts cleanly
- [ ] Test 2: Single daemon registers
- [ ] Test 3: Real-time updates work
- [ ] Test 4: Multiple nodes visible
- [ ] Test 5: Network connectivity OK
- [ ] Test 6: Database records persisted
- [ ] Test 7: Health status detection works
- [ ] Test 8: Polling interval configurable
- [ ] Test 9: Error handling graceful
- [ ] Test 10: Multiple simultaneous nodes work

**Status:** 🟢 All tests passed / 🟡 Some issues / 🔴 Critical failure

---

## Common Issues & Solutions

| Issue | Check | Solution |
|-------|-------|----------|
| Port 5000 in use | `netstat -ano \| findstr :5000` | Kill process or change port in app.py |
| Dashboard not found | `Invoke-WebRequest http://localhost:5000` | Restart Flask server |
| No node registration | Check config.json dashboard_url | Verify URL and network access |
| Graphs empty | Check kpi_data.json exists | Verify file path in config |
| No database records | `sqlite3 test_db/benchmark_test.db` | Run daemon longer (min 30 sec) |
| Connection timeout | Ping dashboard server | Check network and firewall |

---

**Questions?** Refer to DEPLOYMENT.md or QUICKSTART.md
