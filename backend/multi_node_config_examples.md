# Multi-Node Configuration Examples

## Windows Node Configuration (Local)
File: `config_windows_node1.json`
```json
{
  "polling_interval_seconds": 5,
  "node_id": "windows_workstation_1",
  "kpi_source": "kpi_data.json",
  "dashboard_url": "http://192.168.1.100:5000",
  "database": {
    "type": "sqlite",
    "path": "test_db/benchmark_test.db"
  }
}
```

## Linux Node Configuration (Remote)
File: `config_linux_node1.json`
```json
{
  "polling_interval_seconds": 5,
  "node_id": "linux_vm_1",
  "kpi_source": "kpi_data.json",
  "dashboard_url": "http://192.168.1.100:5000",
  "database": {
    "type": "sqlite",
    "path": "/opt/daemon/test_db/benchmark_test.db"
  }
}
```

## Dashboard Server Configuration
File: `config_dashboard.json` (Optional - app.py has hardcoded values)
```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 5000,
    "debug": false
  },
  "database": {
    "type": "sqlite",
    "path": "test_db/benchmark_test.db"
  }
}
```
