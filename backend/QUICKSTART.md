# Quick Start Guide - ML Workload Monitoring Dashboard

## 📋 What You Now Have

### Task 1 ✅ - Professional ML Dashboard
- **app.py** - Flask server with real-time WebSocket updates
- **dashboard.html** - Sleek ML-focused UI with:
  - Real-time KPI metrics by workload type
  - KPI filtering (CPU_Utility, Memory_Usage, GPU_Utilization, Model_Inference_Time, Disk_IO)
  - Workload-grouped display (training, inference, data_prep)
  - Node health status
  - Auto-refresh every 10 seconds

### Task 2 ✅ - Multi-Node Deployment
- **daemon.py** - Collects ML workload KPIs and pushes to central dashboard
- **DEPLOYMENT.md** - Complete multi-node deployment guide
- **setup_windows.ps1** - Automated Windows node setup
- **setup_linux.sh** - Automated Linux node setup

---

## 🚀 Quick Start (5 Minutes)

### Step 1: Start Dashboard Server (Central Machine)

**Windows:**
```powershell
cd C:\daemon_project
pip install -r requirements.txt
python app.py
```

**Linux:**
```bash
cd ~/daemon_project
sudo pip install -r requirements.txt
python3 app.py
```

**Expected Output:**
```
 * Running on http://0.0.0.0:5000
Listening for KPI data from daemon nodes...
```

### Step 2: Configure Node 1 (Windows Example)

Edit `config.json`:
```json
{
  "NodeID": "mlab_node_1",
  "dashboard_url": "http://192.168.1.100:5000",
  "polling_interval_seconds": 5
}
```

### Step 3: Start Daemon on Node 1

```powershell
# In a new terminal
cd C:\daemon_node
python daemon.py
```

**Expected Output:**
```
Node mlab_node_1 pushing KPI data to dashboard
Training workload detected: CPU_Utility=45.2%
Inference workload detected: Model_Inference_Time=125ms
Data prep workload detected: Disk_IO=285MB/s
Sent 6 KPI records to dashboard
```

### Step 4: View Dashboard

Open browser: **http://localhost:5000**

You should see:
- ✅ Node registered (mlab_node_1)
- ✅ Metrics updating in real-time
- ✅ Workload type cards (Training, Inference, Data Prep)
- ✅ KPI filter buttons to switch metrics
- ✅ Health status

---

## 🔧 Configuration for Multiple Nodes

### Data Structure Format

The daemon sends KPI data in this format:

```json
{
  "timestamp": "2024-01-15T14:30:45Z",
  "metrics": [
    {
      "NodeID": "mlab_node_1",
      "WorkloadTag": "training",
      "KPI_name": "CPU_Utility",
      "Value": 45.2
    },
    {
      "NodeID": "mlab_node_1",
      "WorkloadTag": "inference",
      "KPI_name": "Model_Inference_Time",
      "Value": 125.5
    },
    {
      "NodeID": "mlab_node_1",
      "WorkloadTag": "data_prep",
      "KPI_name": "Disk_IO",
      "Value": 285.0
    }
  ]
}
```

### Node Identifiers & Workloads
Set `NodeID` uniquely in each node's `config.json`:

```json
{
  "NodeID": "mlab_node_1",
  "dashboard_url": "http://192.168.1.100:5000",
  "polling_interval_seconds": 5
}
```

### Example Multi-Node Setup

| Node | OS | NodeID | Workloads | IP Address |
|------|-------|---------|-----------|--------|
| 1 | Windows | `mlab_node_1` | training, inference | 192.168.1.10 |
| 2 | Windows | `mlab_node_2` | data_prep, training | 192.168.1.11 |
| 3 | Linux | `mlab_node_3` | inference, data_prep | 192.168.1.20 |
| Dashboard | Any | N/A | N/A | 192.168.1.100 |

---

## 📊 Dashboard Features

### Summary Cards
- **Active Nodes**: Total deployed nodes count
- **Workload Distribution**: Training, Inference, Data Prep workload counts
- **KPI Metrics**: Real-time KPI values per workload
- **System Status**: Real-time update counter

### Node Metrics Section
Per-node display of:
- Current CPU utility (%)
- Max CPU usage
- Average frequency (MHz)
- Sample count
- Last update timestamp
- Health status badge

### Performance Trends
- **CPU Chart**: Line graph of CPU usage over time for all nodes
- **Frequency Chart**: Line graph of frequency for all nodes

### Connectivity View
- Visual status of each node (✅ Connected / ❌ Disconnected)
- Real-time indicators

---

## 🔌 Data Flow Verification

### 1. Check Node Registration
Dashboard console should show:
```
INFO - Node windows_workstation_1 registered from 192.168.1.10
INFO - Node linux_vm_1 registered from 192.168.1.20
```

### 2. Check Data Submission
Dashboard console should show:
```
INFO - Received 2 KPI records from windows_workstation_1
INFO - Pushed 2 records to dashboard
```

### 3. Verify Database
```bash
# Windows/Linux
sqlite3 test_db/benchmark_test.db "SELECT COUNT(*) FROM node_kpis;"
```

---

## ⚙️ Polling Interval Optimization

To minimize overhead on nodes, adjust polling interval:

```json
{
  "polling_interval_seconds": 10  // Increase from 5 for less CPU impact
}
```

| Interval | Use Case | CPU Impact |
|----------|----------|-----------|
| 2-3 sec | Real-time monitoring | High |
| **5-10 sec** | **Balanced (RECOMMENDED)** | **Medium** |
| 30+ sec | Low overhead monitoring | Low |

---

## 🐛 Troubleshooting

### Node not appearing in dashboard
```bash
# 1. Check connectivity
ping 192.168.1.100

# 2. Test HTTP connection
curl http://192.168.1.100:5000/api/nodes

# 3. Verify config.json dashboard_url is correct
cat config.json | grep dashboard_url
```

### No data in graphs
```bash
# 1. Check kpi_data.json has fresh timestamps
cat kpi_data.json

# 2. Check daemon is running and not erroring
# (Look at daemon console output)

# 3. Check database for records
sqlite3 test_db/benchmark_test.db "SELECT * FROM node_kpis LIMIT 5;"
```

### Dashboard shows "Unhealthy"
- Nodes marked unhealthy if no update in 30 seconds
- Increase polling frequency in `config.json`
- Restart daemon

---

## 📁 Project Structure

```
daemon_project/
├── daemon.py              # Main daemon (reads JSON, pushes to dashboard)
├── app.py                 # Flask server (central dashboard)
├── router.py              # Routing logic
├── db_connector.py        # Database operations
├── config.json            # Daemon configuration
├── kpi_data.json          # Sample KPI data
├── requirements.txt       # Python dependencies
├── DEPLOYMENT.md          # Full deployment guide
├── setup_windows.ps1      # Automated Windows setup
├── setup_linux.sh         # Automated Linux setup
├── templates/
│   └── dashboard.html     # Dashboard UI
└── test_db/
    └── benchmark_test.db  # SQLite database (auto-created)
```

---

## 🚀 Production Deployment

### Linux Service (Recommended)
```bash
sudo ./setup_linux.sh --dashboard-url "http://192.168.1.100:5000" \
                       --node-id "linux_vm_1"

# Start
sudo systemctl start kpi-daemon.service
```

### Windows Service (Using NSSM)
```powershell
# See DEPLOYMENT.md for detailed instructions
# Quick summary:
.\setup_windows.ps1 -DashboardURL "http://192.168.1.100:5000" `
                    -NodeID "windows_workstation_1"
```

---

## ✅ Deployment Checklist

- [ ] Dashboard server started on central machine
- [ ] All nodes can ping dashboard server
- [ ] All nodes have correct `dashboard_url` in config.json
- [ ] All nodes have unique `node_id`
- [ ] Daemons started on all nodes
- [ ] Dashboard shows all nodes registered
- [ ] Data flowing to database (check graphs)
- [ ] Health status is "Healthy" for active nodes
- [ ] Graphs showing real-time updates

---

## 📝 Next Phase

Once confirmed working:
1. Replace SQLite with MongoDB/PostgreSQL for benchmarking
2. Add alerting on threshold violations
3. Implement longer-term data retention
4. Add query/reporting interface
5. Set up log aggregation

---

## 🎯 Architecture Summary

```
┌─────────────────────────────────────────────┐
│     Central Dashboard Server (Flask)         │
│     Port 5000                               │
│  ┌─────────────────────────────────────┐   │
│  │ Real-time Metrics Display           │   │
│  │ - Node status & health              │   │
│  │ - CPU & Frequency graphs            │   │
│  │ - WebSocket updates                 │   │
│  └─────────────────────────────────────┘   │
└────────┬─────────────────────────────┬──────┘
         │                             │
   ┌─────▼────┐               ┌────────▼────┐
   │ Windows   │               │  Linux VM  │
   │ Node 1    │               │  Node 1    │
   │ Daemon    │               │ Daemon     │
   │ (Push)    │               │ (Push)     │
   └───────────┘               └────────────┘
   
   → Both push data to central dashboard
   → Real-time graphs updated via WebSocket
   → Data persisted in shared SQLite DB
```

---

**Questions?** Refer to DEPLOYMENT.md for detailed instructions on any step.
