# Quick Reference Card - Multi-Node Testing

## 🚀 Quick Start (30 seconds)

```powershell
# COMPUTER 1 (Central)
cd daemon_project
python app.py
# Visit: http://localhost:5000

# COMPUTER 2 (Edge Node)
cd energy-monitoring-temp\KPIs Extraction
# Edit config.json: "backend_url": "http://[COMPUTER1_IP]:5000"
python daemon.py
```

---

## 📍 Finding IPs

```powershell
# On each computer
ipconfig | findstr "IPv4"
# Look for WiFi adapter: 192.168.1.xxx
```

**Computer 1 (Central):** `192.168.1.100`
**Computer 2 (Edge Node):** `192.168.1.101`

---

## ✅ Connectivity Check

```powershell
# From Computer 2 to Computer 1
ping 192.168.1.100
curl http://192.168.1.100:5000
```

Expected: 4 packets received, 0% loss

---

## 🔧 Configuration

**File:** `KPIs Extraction\config.json`

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

| Field | Value |
|-------|-------|
| `node_id` | Unique name (e.g., "GPU-Laptop") |
| `workload_tag` | training, inference, data_prep |
| `backend_url` | **Computer 1's IP** (not localhost) |
| `dry_run` | true = test only, false = transmit |

---

## 🧪 Testing Journey

### Step 1: Start Backend (Computer 1)
```powershell
python app.py
# Logs show: "Running on http://0.0.0.0:5000"
```

### Step 2: Dry Run (Computer 2)
```powershell
# Set dry_run: true in config.json
python daemon.py
# Logs show: "[DRY-RUN] Would transmit X records"
```

### Step 3: Network Test (Computer 2)
```powershell
curl http://192.168.1.100:5000/api/dashboard/summary
# Should return JSON, not error
```

### Step 4: Live Test (Computer 2)
```powershell
# Set dry_run: false in config.json
python daemon.py
# Logs show: "Successfully transmitted X records"
```

### Step 5: Dashboard (Computer 1)
```
Open: http://localhost:5000
Expected: Node appears, metrics display
```

---

## 🔴 Common Issues & Fixes

| Problem | Fix |
|---------|-----|
| "Connection refused" | Check backend running, verify IP |
| "No nodes on dashboard" | Check daemon logs, verify network |
| No data updating | Restart daemon, check dry_run=false |
| Slow updates | Reduce poll_interval_sec (5.0 → 2.0) |
| Firewall blocks | `netsh advfirewall set allprofiles state off` |
| Power metrics missing | Install LibreHardwareMonitor (Windows) |

---

## 📊 Expected Dashboard

```
Node: edge-node-laptop
├─ Status: Connected ✅
├─ Last Update: 2 seconds ago
├─ Workload: training
│
├─ CPU_Utility: 45.5%
├─ Memory_Usage: 65.3%
├─ Disk_IO_Read_MB: 1024.5
├─ Power_Watts: 150.2W
│
└─ [Real-time graphs updating...]
```

---

## 🎯 Success Checklist

- [ ] Backend running (Computer 1)
- [ ] Daemon transmitting (Computer 2)
- [ ] Node shows "Connected" on dashboard
- [ ] Metrics updating every 5 seconds
- [ ] No errors in logs
- [ ] Graphs showing trends

---

## 📋 Key Commands

```powershell
# Kill daemon (Computer 2)
Ctrl+C

# Kill backend (Computer 1)
Ctrl+C

# Disable firewall (if needed)
netsh advfirewall set allprofiles state off

# Re-enable firewall
netsh advfirewall set allprofiles state on

# Check if port 5000 is open
netstat -an | findstr 5000
```

---

## 🌐 Access Points

| What | Where |
|------|-------|
| Dashboard | http://localhost:5000 (Computer 1) |
| Dashboard Remote | http://192.168.1.100:5000 (any browser) |
| API Status | http://192.168.1.100:5000/api/dashboard/summary |

---

## ⏱️ Timeline

| Phase | Time | Action |
|-------|------|--------|
| Setup | 5 min | Install deps, copy files, find IPs |
| Test Backend | 2 min | Start app.py, open dashboard |
| Test Daemon (Dry) | 3 min | Run with dry_run=true |
| Network Test | 1 min | Ping and curl tests |
| Live Test | 2 min | Set dry_run=false, run daemon |
| Verify | 2 min | Check dashboard, graphs, metrics |
| **Total** | **~15 min** | Full end-to-end test |

---

## 💾 File Locations

**Computer 1 (Backend):**
```
C:\...\daemon_project\
├── app.py          ← Start this
├── config.json     ← Backend config
├── requirements.txt
└── test_db\
    └── metrics.db  ← Data stored here
```

**Computer 2 (Daemon):**
```
C:\...\energy-monitoring-temp\KPIs Extraction\
├── daemon.py       ← Start this
├── config.json     ← EDIT THIS with Computer 1 IP
├── transformer.py
├── payload_builder.py
└── cpu_metrics.py
```

---

## 📞 Support

**Error logs location:**
- Wherever you ran `python app.py` or `python daemon.py`
- Print terminal output for debugging

**Key troubleshooting files:**
- See full guide: `TESTING_GUIDE_MULTINODE.md`
- Integration details: `KPIs Extraction\README_INTEGRATION.md`

---

**Last Updated:** April 4, 2026  
**Status:** ✅ Ready for Testing
