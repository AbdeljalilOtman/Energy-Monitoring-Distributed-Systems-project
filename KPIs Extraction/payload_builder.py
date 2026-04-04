"""
Micro-Step 3 (Revised): Nested JSON Payload Builder

This module collects hardware metrics and neatly packages them into a 
single optimized JSON envelope. 

The backend server will later be responsible for unpacking this envelope
and flattening the data into the database rows to satisfy the architecture spec.
"""

import time
from cpu_metrics import collect_cpu_metrics
from power_metrics import collect_power_metrics


def build_payload(node_id, workload_tag, interval=1.0):
    """
    Collects hardware metrics and formats them into a flat matrix.

    Args:
        node_id (str): Identifier for this workstation/node.
        workload_tag (str): The current workload context (e.g. 'idle', 'resnet').
        interval (float): Polling duration for the collectors.

    Returns:
        dict: A structured JSON envelope containing all KPIs.
    """
    # 1. Get exact time of collection (Epoch seconds)
    timestamp = int(time.time())

    # 2. Collect raw metrics
    # Note: collect_power_metrics has a built-in sleep(interval),
    # so we shouldn't pass interval to both to avoid double-sleeping.
    # To be perfectly precise with our timing: we just let the power collector 
    # handle the time gap, and cpu_percent handles its own gap.
    # Since cpu_percent is blocking, we collect CPU, then collect Power.
    # Total blocking time = CPU interval + Power interval. 
    # For now, we will run them sequentially. When we optimize (Phase 4), 
    # we can thread them.
    cpu_data = collect_cpu_metrics(percpu_interval=interval)
    power_data = collect_power_metrics(interval=interval)

    metrics = {}

    # Helper function to append a standardized row
    def add_metric(kpi_name, value):
        if value is not None:
            metrics[kpi_name] = value

    # 3. Flatten CPU Metrics
    add_metric("cpu_percent_total", cpu_data.get("cpu_percent_total"))

    for i, pct in enumerate(cpu_data.get("cpu_percent_per_core", [])):
        add_metric(f"cpu_percent_core_{i}", pct)

    for i, freq in enumerate(cpu_data.get("cpu_freq_current_mhz", [])):
        add_metric(f"cpu_freq_core_{i}_mhz", freq)

    add_metric("cpu_freq_min_mhz", cpu_data.get("cpu_freq_min_mhz"))
    add_metric("cpu_freq_max_mhz", cpu_data.get("cpu_freq_max_mhz"))

    # Temperature from cpu_metrics (Linux/Pi) or power_metrics (Windows LHM / Pi fallback)
    combined_temp = cpu_data.get("cpu_temperature_c") or power_data.get("cpu_temperature_c")
    add_metric("cpu_temperature_c", combined_temp)

    # Voltage (Windows LHM / Pi)
    add_metric("cpu_voltage_v", power_data.get("cpu_voltage_v"))

    # 4. Flatten Power/Energy Metrics
    for domain in power_data.get("domains", []):
        name = domain["name"]  # e.g., 'package-0'
        add_metric(f"power_watts_{name}", domain["power_watts"])
        add_metric(f"energy_joules_{name}", domain["energy_delta_joules"])

    return {
        "timestamp": timestamp,
        "node_id": node_id,
        "workload_tag": workload_tag,
        "metrics": metrics
    }

