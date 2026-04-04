"""
Transformer: Convert Colleague's Nested Format → Backend Flat Array Format

Converts the nested payload format:
    {timestamp: epoch_seconds, node_id, workload_tag, metrics: {dict}}

To your backend's flat array format:
    {node_id: "string", records: [{timestamp ISO, NodeID, WorkloadTag, KPI_name, Value}]}
"""

from datetime import datetime, timezone
import logging

logging.basicConfig(level=logging.INFO)


def transform_payload_to_backend(payload):
    """
    Transform colleague's nested payload to backend's flat array format.
    
    Args:
        payload (dict): Colleague's payload with nested metrics structure
            {
                "timestamp": 1712282400,
                "node_id": "node-1",
                "workload_tag": "training",
                "metrics": {
                    "cpu_percent_total": 45.5,
                    "cpu_percent_core_0": 50,
                    "memory_percent": 65.3,
                    ...
                }
            }
    
    Returns:
        dict: Backend-compatible format
            {
                "node_id": "node-1",
                "records": [
                    {
                        "timestamp": "2026-04-04T22:00:00+00:00",
                        "NodeID": "node-1",
                        "WorkloadTag": "training",
                        "KPI_name": "CPU_Utility",
                        "Value": 45.5
                    },
                    ...
                ]
            }
    """
    try:
        # Extract components from colleague's payload
        timestamp_epoch = payload.get("timestamp")
        node_id = payload.get("node_id")
        workload_tag = payload.get("workload_tag")
        metrics = payload.get("metrics", {})
        
        # Convert epoch timestamp to ISO 8601 with UTC timezone
        dt = datetime.fromtimestamp(timestamp_epoch, tz=timezone.utc)
        timestamp_iso = dt.isoformat()
        
        # Build records array
        records = []
        
        # Mapping function: colleague's metric name → your KPI name
        def map_kpi(colleague_name, value):
            """
            Map colleague's metric names to your standardized KPI names.
            Keeps per-core CPU metrics as separate utilities.
            
            Examples:
                "cpu_percent_total" → "CPU_Utility"
                "memory_percent" → "Memory_Usage"
                "disk_write_mb" → "Disk_IO"
                "cpu_percent_core_0" → "CPU_Utility_core_0"  (as separate utility)
            """
            
            # CPU Metrics - MAIN
            if colleague_name == "cpu_percent_total":
                return "CPU_Utility"
            elif colleague_name.startswith("cpu_percent_core_"):
                # Keep per-core as separate metrics (e.g., "CPU_Utility_core_0")
                core_num = colleague_name.replace("cpu_percent_core_", "")
                return f"CPU_Utility_core_{core_num}"
            
            # Memory Metrics
            elif colleague_name == "memory_percent":
                return "Memory_Usage"
            elif colleague_name == "memory_available_mb":
                return "Memory_Available_MB"
            elif colleague_name == "memory_used_mb":
                return "Memory_Used_MB"
            elif colleague_name == "memory_total_mb":
                return "Memory_Total_MB"
            
            # Disk I/O Metrics
            elif colleague_name == "disk_read_mb":
                return "Disk_IO_Read_MB"
            elif colleague_name == "disk_write_mb":
                return "Disk_IO_Write_MB"
            elif colleague_name == "disk_read_count":
                return "Disk_IO_Read_Count"
            elif colleague_name == "disk_write_count":
                return "Disk_IO_Write_Count"
            
            # Power Metrics (keep as-is but prefix with Power_)
            elif colleague_name.startswith("power_watts_"):
                domain = colleague_name.replace("power_watts_", "")
                return f"Power_Watts_{domain}"
            elif colleague_name.startswith("energy_joules_"):
                domain = colleague_name.replace("energy_joules_", "")
                return f"Energy_Joules_{domain}"
            
            # CPU Frequency Metrics
            elif colleague_name.startswith("cpu_freq_core_") and colleague_name.endswith("_mhz"):
                return colleague_name.replace("_mhz", "").upper() + "_MHz"
            elif colleague_name == "cpu_freq_min_mhz":
                return "CPU_Freq_Min_MHz"
            elif colleague_name == "cpu_freq_max_mhz":
                return "CPU_Freq_Max_MHz"
            
            # Temperature & Voltage
            elif colleague_name == "cpu_temperature_c":
                return "CPU_Temperature_C"
            elif colleague_name == "cpu_voltage_v":
                return "CPU_Voltage_V"
            
            # Default: use colleague's name as-is (unknown metrics)
            else:
                return colleague_name
        
        # Convert each metric to a record
        for colleague_kpi_name, value in metrics.items():
            # Skip None values
            if value is None:
                continue
            
            # Map to backend KPI name
            backend_kpi_name = map_kpi(colleague_kpi_name, value)
            
            # Create record entry
            record = {
                "timestamp": timestamp_iso,
                "NodeID": node_id,
                "WorkloadTag": workload_tag,
                "KPI_name": backend_kpi_name,
                "Value": value
            }
            records.append(record)
        
        # Return backend-compatible format
        return {
            "node_id": node_id,
            "records": records
        }
        
    except Exception as e:
        logging.error(f"Transformation failed: {e}")
        raise


def validate_transformed_payload(payload):
    """
    Validate that the transformed payload has correct structure.
    
    Args:
        payload (dict): Transformed payload to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    required_keys = {"node_id", "records"}
    if not isinstance(payload, dict) or not all(k in payload for k in required_keys):
        logging.error("Missing required keys: node_id or records")
        return False
    
    if not isinstance(payload["records"], list):
        logging.error("records must be a list")
        return False
    
    required_record_keys = {"timestamp", "NodeID", "WorkloadTag", "KPI_name", "Value"}
    for record in payload["records"]:
        if not isinstance(record, dict) or not all(k in record for k in required_record_keys):
            logging.error(f"Record missing required keys: {record}")
            return False
    
    return True
