# Comprehensive Deployment & Architecture Guide

## System Overview

This document describes the complete distributed ML workload monitoring system, its architecture, and how to deploy it to 2+ computers via WiFi.

---

## Architecture

### **High-Level Design**

```
┌─────────────────────────────────────────────────────────────┐
│                    CENTRAL MONITORING SERVER                │
│                   (Computer 1: 192.168.1.100)               │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │          Flask Backend (app.py)                      │  │
│  │                                                      │  │
│  │  • HTTP Endpoints (REST API)                        │  │
│  │  • WebSocket Server (Real-time updates)            │  │
│  │  • SQLite Database (metrics storage)               │  │
│  │  • HTML Dashboard (frontend)                       │  │
│  │                                                     │  │
│  │  Listening on: 0.0.0.0:5000                        │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                           ▲
                    HTTP POST (every 5s)
                           │
                ┌──────────┴──────────┬──────────────┐
                │                     │              │
                │                     │              │
         ┌──────▼─────┐        ┌──────▼─────┐  ┌──────▼─────┐
         │    NODE 1   │        │    NODE 2   │  │    NODE N   │
         │ 192.168.1.101        │ 192.168.1.102  │ ...        │
         │             │        │             │  │             │
         │ daemon.py   │        │ daemon.py    │  │ daemon.py  │
         │ (Energy Mon)│        │ (Energy Mon) │  │ (Energy Mon)
         │             │        │             │  │             │
         │ Collecting: │        │ Collecting:  │  │ Collecting:│
         │ • CPU       │        │ • CPU        │  │ • CPU      │
         │ • Memory    │        │ • Memory     │  │ • Memory   │
         │ • Disk I/O  │        │ • Disk I/O   │  │ • Disk I/O │
         │ • Power     │        │ • Power      │  │ • Power    │
         │ • Temp      │        │ • Temp       │  │ • Temp     │
         │             │        │             │  │             │
         └─────────────┘        └─────────────┘  └─────────────┘

           WiFi Router
          192.168.1.1
```

---

## Component Overview

### **1. Central Backend System**

**Location:** `daemon_project/`

**Core Files:**
- `app.py` (250+ lines) - Flask server with REST API and WebSocket
- `db_connector.py` (50 lines) - SQLite database abstraction
- `dashboard.html` (595 lines) - Real-time web dashboard
- `config.json` - Server configuration
- `requirements.txt` - Python dependencies

**Responsibilities:**
- ✅ Receive metrics from edge nodes via HTTP POST
- ✅ Store metrics in SQLite database
- ✅ Serve HTTP REST API endpoints
- ✅ Broadcast real-time updates via WebSocket
- ✅ Serve dashboard HTML/JavaScript/CSS
- ✅ Aggregate and summarize metrics

**API Endpoints:**
```
POST   /api/kpi/submit              ← Edge nodes send data here
GET    /api/metrics/<node_id>       ← Retrieve node metrics
GET    /api/metrics/aggregated/<node_id>  ← Aggregated stats
GET    /api/dashboard/summary       ← Dashboard data
WebSocket /socket.io                ← Real-time updates
```

**Technology Stack:**
- Framework: Flask 2.x + Flask-CORS + Flask-SocketIO
- Database: SQLite3
- Frontend: HTML5 + JavaScript (Chart.js for graphs)
- Server: Development server (use production server for deployments)

---

### **2. Edge Node Daemon System**

**Location:** `energy-monitoring-temp/KPIs Extraction/`

**Core Files:**
- `daemon.py` (100+ lines) - Main daemon loop
- `payload_builder.py` (100+ lines) - Data collection orchestration
- `cpu_metrics.py` (150+ lines) - CPU, memory, disk metrics
- `power_metrics.py` (300+ lines) - Power/energy metrics (platform-specific)
- `transformer.py` (250+ lines) - Format converter (NEW)
- `config.json` - Node configuration

**Responsibilities:**
- ✅ Periodically collect system metrics
- ✅ Aggregate metrics into payload
- ✅ Transform to backend-compatible format
- ✅ Transmit to central server via HTTP POST
- ✅ Handle failures gracefully
- ✅ Support dry-run mode for testing

**Metric Collection:**
```
collector.py
   ├── collect_cpu_metrics()        → cpu_percent, frequency, temperature
   ├── collect_memory_metrics()     → memory usage in %, GB
   ├── collect_disk_metrics()       → disk read/write operations
   └── collect_power_metrics()      → watts, joules (platform-specific)
        ├── RAPL (Linux + Intel)
        ├── LibreHardwareMonitor (Windows)
        └── Simulated (fallback)
```

**Data Transformation:**
```
Internal Format (Nested)
{
  "timestamp": 1775338913,
  "node_id": "node-1",
  "workload_tag": "training",
  "metrics": {
    "cpu_percent_total": 45.5,
    "memory_percent": 65.3,
    ...
  }
}
        ↓ Transformer
Backend Format (Flat Array)
{
  "node_id": "node-1",
  "records": [
    {
      "timestamp": "2026-04-04T21:41:53+00:00",
      "NodeID": "node-1",
      "WorkloadTag": "training",
      "KPI_name": "CPU_Utility",
      "Value": 45.5
    },
    ...
  ]
}
```

**Technology Stack:**
- Runtime: Python 3.11+
- System Libraries: psutil (cross-platform system metrics)
- Network: urllib.request (standard library HTTP)
- Logging: Python logging module

---

## Data Flow - Step by Step

### **Scenario: Edge node sends metrics to central server**

```
Timestamp: 10:00:00 (every 5 seconds)

1. daemon.py:start_daemon()
   └─ Calls build_payload()

2. payload_builder.build_payload()
   ├─ Calls collect_cpu_metrics()
   │  └─ Returns: cpu %, frequency, temperature
   ├─ Calls collect_memory_metrics()
   │  └─ Returns: memory %, available MB
   ├─ Calls collect_disk_metrics()
   │  └─ Returns: read/write MB, operations
   └─ Calls collect_power_metrics()
      └─ Returns: watts, joules (platform-specific)

3. Payload Built (Nested Format)
   {
     "timestamp": 1775338913,
     "node_id": "edge-node-1",
     "workload_tag": "training",
     "metrics": {25+ KPI entries}
   }

4. transformer.transform_payload_to_backend()
   ├─ Convert timestamp: epoch → ISO 8601 with UTC
   ├─ Map metric names → standardized KPI names
   ├─ Create records array: one per metric
   └─ Validate structure

5. Transformed Payload (Flat Array)
   {
     "node_id": "edge-node-1",
     "records": [
       {"timestamp": "...", "NodeID": "...", "KPI_name": "CPU_Utility", "Value": 45.5},
       {"timestamp": "...", "NodeID": "...", "KPI_name": "Memory_Usage", "Value": 65.3},
       ...
     ]
   }

6. HTTP POST to Central Server
   POST http://192.168.1.100:5000/api/kpi/submit
   Content-Type: application/json
   [transformed payload]

7. Central Backend (app.py):_post_to_backend()
   ├─ Receive POST request
   ├─ Parse JSON payload
   ├─ Extract records array
   └─ For each record:
      ├─ Validate format
      ├─ Insert into SQLite database
      └─ Broadcast via WebSocket

8. Database (metrics.db)
   INSERT INTO kpi_metrics (timestamp, NodeID, WorkloadTag, KPI_name, Value)
   VALUES ("2026-04-04T21:41:53+00:00", "edge-node-1", "training", "CPU_Utility", 45.5)

9. WebSocket Broadcast
   Emit event to all connected dashboard clients:
   {node: "edge-node-1", metrics: {latest data}}

10. Dashboard Update
    JavaScript receives WebSocket message
    └─ Update charts/graphs in real-time
    └─ Refresh node status
    └─ Show last update timestamp
```

---

## Database Schema

**Table: `kpi_metrics`**

```sql
CREATE TABLE kpi_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,          -- ISO 8601: "2026-04-04T21:41:53+00:00"
    NodeID TEXT NOT NULL,              -- "edge-node-1"
    WorkloadTag TEXT NOT NULL,         -- "training", "inference", "data_prep"
    KPI_name TEXT NOT NULL,            -- "CPU_Utility", "Memory_Usage", etc.
    Value REAL NOT NULL               -- 45.5, 65.3, etc.
)
```

**Indexes (for performance):**
```sql
CREATE INDEX idx_nodeid ON kpi_metrics(NodeID);
CREATE INDEX idx_timestamp ON kpi_metrics(timestamp);
CREATE INDEX idx_workload ON kpi_metrics(WorkloadTag);
```

**Sample Query:**
```sql
-- Get last 1 hour of CPU metrics for node-1
SELECT timestamp, Value 
FROM kpi_metrics 
WHERE NodeID = 'edge-node-1' 
  AND KPI_name = 'CPU_Utility'
  AND timestamp > datetime('now', '-1 hour')
ORDER BY timestamp DESC
```

---

## KPI Reference

### **All Supported KPIs**

| KPI Name | Range | Unit | Source | Notes |
|----------|-------|------|--------|-------|
| CPU_Utility | 0-100 | % | cpu_metrics | System-wide CPU usage |
| CPU_Utility_core_N | 0-100 | % | cpu_metrics | Per-core breakdown |
| Memory_Usage | 0-100 | % | cpu_metrics | Used RAM percentage |
| Memory_Available_MB | 0-∞ | MB | cpu_metrics | Available RAM |
| Memory_Used_MB | 0-∞ | MB | cpu_metrics | Used RAM amount |
| Memory_Total_MB | 0-∞ | MB | cpu_metrics | Total RAM |
| Disk_IO_Read_MB | 0-∞ | MB | cpu_metrics | Cumulative |
| Disk_IO_Write_MB | 0-∞ | MB | cpu_metrics | Cumulative |
| Disk_IO_Read_Count | 0-∞ | Ops | cpu_metrics | Cumulative |
| Disk_IO_Write_Count | 0-∞ | Ops | cpu_metrics | Cumulative |
| Power_Watts_package-0 | 0-500 | W | power_metrics | Instantaneous |
| Energy_Joules_package-0 | 0-∞ | J | power_metrics | Cumulative |
| CPU_Freq_Min_MHz | 800-4000 | MHz | cpu_metrics | Base frequency |
| CPU_Freq_Max_MHz | 1200-5000 | MHz | cpu_metrics | Max frequency |
| CPU_Freq_Core_N_MHz | 800-5000 | MHz | cpu_metrics | Per-core current |
| CPU_Temperature_C | 20-120 | °C | cpu_metrics | Core temperature |
| CPU_Voltage_V | 0.5-1.5 | V | power_metrics | Supply voltage |

---

## Configuration Files

### **Central Server Config**

**File:** `daemon_project/config.json`

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 5000,
    "debug": false,
    "database_path": "test_db/metrics.db"
  },
  "dashboard": {
    "refresh_interval_ms": 1000,
    "history_window_hours": 24
  }
}
```

### **Edge Node Config**

**File:** `energy-monitoring-temp/KPIs Extraction/config.json`

```json
{
  "node_config": {
    "node_id": "edge-node-1",
    "workload_tag": "training",
    "poll_interval_sec": 5.0,
    "backend_url": "http://192.168.1.100:5000",
    "dry_run": false
  }
}
```

**Configuration Options:**

| Option | Type | Description |
|--------|------|-------------|
| `node_id` | string | Unique identifier (e.g., "gpu-laptop", "server-1") |
| `workload_tag` | string | Workload context: training, inference, data_prep |
| `poll_interval_sec` | float | Measurement interval in seconds (recommend 5.0) |
| `backend_url` | string | Central server URL (e.g., http://192.168.1.100:5000) |
| `dry_run` | boolean | Test mode (true) vs. live transmission (false) |

---

## Deployment Checklist

### **Pre-Deployment**

- [ ] Python 3.11+ installed on both computers
- [ ] All dependencies installed (`pip install -r requirements.txt`)
- [ ] WiFi connectivity verified between computers
- [ ] Static IPs assigned (recommended)
- [ ] Firewall configured to allow port 5000

### **Central Server Deployment**

- [ ] Clone/copy `daemon_project/` to Computer 1
- [ ] Install dependencies: `pip install flask flask-cors flask-socketio psutil`
- [ ] Verify `config.json` has correct paths
- [ ] Start server: `python app.py`
- [ ] Verify dashboard: `curl http://localhost:5000`

### **Edge Node Deployment**

- [ ] Clone/copy `energy-monitoring-temp/KPIs Extraction/` to Computer 2
- [ ] Install dependencies: `pip install psutil`
- [ ] Update `config.json`:
  - Set `node_id` (unique per node)
  - Set `backend_url` to central server IP
  - Set `workload_tag` appropriately
- [ ] Test dry-run: `python daemon.py` with `dry_run: true`
- [ ] Test connectivity: `curl http://192.168.1.100:5000/api/dashboard/summary`
- [ ] Enable live transmission: `python daemon.py` with `dry_run: false`

### **Verification**

- [ ] Central server logs show "Running on 0.0.0.0:5000"
- [ ] Dashboard loads: http://localhost:5000
- [ ] Edge node logs show "Successfully transmitted X records"
- [ ] Dashboard displays node as "Connected"
- [ ] Metrics update every 5 seconds
- [ ] No errors in logs

---

## Performance Characteristics

### **Resource Usage**

| Component | CPU | Memory | Network |
|-----------|-----|--------|---------|
| **Central Server** | 1-2% | 30-50 MB | <1 KB/s (idle) |
| **Edge Daemon** | 2-5% | 25-40 MB | ~10 KB/5s (1 transmission) |
| **Dashboard (JS)** | 0-1% | 50-100 MB | <1 KB/s (WebSocket) |

### **Scalability**

- **Nodes per server:** 100+ (depends on `poll_interval`)
- **Storage:** ~1 KB per metric record → ~100 GB/year for 100 nodes at 5s intervals
- **Network:** 25 records × 2 KB ≈ 50 KB per transmission

### **Latency**

- **Data collection:** 5-10 seconds (configurable)
- **Transmission time:** <100 ms (local WiFi)
- **Dashboard update:** <500 ms (WebSocket)
- **Total end-to-end latency:** 5-11 seconds

---

## Security Considerations

### **Current (Development)**

⚠️ **NOT SUITABLE FOR PRODUCTION**

- No authentication (anyone with IP can access)
- No encryption (HTTP, not HTTPS)
- No rate limiting
- Database file unprotected

### **For Production Deployment**

1. **Add HTTPS:** Use nginx reverse proxy + self-signed certificates
2. **Add Authentication:** Flask-Login + JWT tokens
3. **Rate Limiting:** Flask-Limiter to prevent abuse
4. **Database:** Use PostgreSQL instead of SQLite for concurrent access
5. **Firewall:** Only allow dashboard access from trusted IPs
6. **Logging:** Archive logs for audit trail

---

## Troubleshooting Guide

### **Central Server Issues**

**Server won't start:**
```
Error: Address already in use
→ Kill process: netstat -an | findstr 5000, taskkill /PID <pid> /F
```

**Database errors:**
```
Error: database is locked
→ Close all connections and restart server
```

**WebSocket not connecting:**
```
Error: Connection refused
→ Check firewall allows port 5000
→ Verify Flask-SocketIO is installed
```

### **Edge Node Issues**

**Cannot connect to backend:**
```
Error: Connection refused
→ Verify backend is running
→ Check backend_url in config.json
→ Test with: curl http://192.168.1.100:5000
```

**Metrics collection fails:**
```
Error: Failed to collect [metric]
→ Ensure psutil is installed
→ Check system permissions
→ On Windows, power metrics may require admin or LibreHardwareMonitor
```

### **Dashboard Issues**

**No nodes appear:**
```
→ Check daemon is transmitting (logs show "Successfully transmitted")
→ Refresh browser (Ctrl+Shift+R)
→ Check database: should have kpi_metrics table
```

**Graphs not updating:**
```
→ Check WebSocket connection in browser console (F12)
→ Verify daemon is still running
→ Reduce poll_interval if too slow
```

---

## File Structure

```
distributed_Systems_Project/
│
├── daemon_project/                          [CENTRAL SERVER]
│   ├── app.py                               (Flask backend - main entry point)
│   ├── daemon.py                            (Sensor daemon - reads kpi_data.json)
│   ├── db_connector.py                      (Database abstraction)
│   ├── router.py                            (Data routing)
│   ├── dashboard.html                       (Web UI)
│   ├── templates/
│   │   └── (additional templates)
│   ├── config.json                          (Server config)
│   ├── requirements.txt                     (Python dependencies)
│   ├── test_db/
│   │   └── metrics.db                       (SQLite database)
│   └── README.md                            (Backend docs)
│
├── energy-monitoring-temp/                  [COLLEAGUE'S REPO]
│   ├── KPIs Extraction/                     [EDGE NODES]
│   │   ├── daemon.py                        (Main daemon - MODIFIED)
│   │   ├── payload_builder.py               (Data aggregation - MODIFIED)
│   │   ├── cpu_metrics.py                   (System metrics - ENHANCED)
│   │   ├── power_metrics.py                 (Power metrics)
│   │   ├── transformer.py                   (Format converter - NEW)
│   │   ├── config.json                      (Node config - NEW)
│   │   ├── test_transformer.py              (Validation - NEW)
│   │   ├── mock_backend.py
│   │   ├── validate_step1.py
│   │   └── validate_step2.py
│   ├── Doc/                                 (Documentation)
│   ├── Documents/                           (Specification)
│   └── README_INTEGRATION.md                (Integration guide - NEW)
│
├── QUICK_REFERENCE.md                       (Quick setup card - NEW)
├── TESTING_GUIDE_MULTINODE.md               (2-computer testing - NEW)
└── DEPLOYMENT_GUIDE.md                      (This file - NEW)
```

---

## Next Steps

### **Phase 1: Quick Testing (15 min)**
1. Follow QUICK_REFERENCE.md for rapid setup
2. Test with `dry_run: true` locally
3. Enable live transmission and verify dashboard

### **Phase 2: Multi-Computer Testing (30 min)**
1. Follow TESTING_GUIDE_MULTINODE.md in detail
2. Test 2-computer setup with WiFi
3. Verify data flow and performance
4. Stress test with load

### **Phase 3: Production Deployment**
1. Set up production environment
2. Implement security measures (HTTPS, auth)
3. Use stable storage (PostgreSQL instead of SQLite)
4. Set up monitoring/alerting
5. Archive historical data

### **Phase 4: Scale & Optimize**
1. Add more edge nodes
2. Monitor performance metrics
3. Tune poll_interval for desired latency
4. Implement data aggregation/downsampling

---

## Contact & Support

- **Integration Questions:** See `energy-monitoring-temp/KPIs Extraction/README_INTEGRATION.md`
- **Testing Issues:** See `TESTING_GUIDE_MULTINODE.md` troubleshooting section
- **Backend Issues:** Check `daemon_project/README.md`

---

**Document Version:** 1.0  
**Last Updated:** April 4, 2026  
**Status:** ✅ Complete and ready for deployment
