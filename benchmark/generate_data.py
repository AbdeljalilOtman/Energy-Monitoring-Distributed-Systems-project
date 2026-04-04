#!/usr/bin/env python3
"""
MLab Benchmark — Data Generator
=================================
Generates a CSV file matching the MLab daemon payload schema:

  Timestamp, Node_ID, Workload_Tag, KPI_Name, Value

KPIs (from SRS Section 3.1):
  - CPU utilization per core (%)
  - CPU frequency per core (MHz)
  - CPU voltage per core (V)
  - CPU temperature per core (°C)
  - Process-specific energy consumption per ML workload (Joules, Watts, CPU%)

Usage:
  python generate_data.py                                    # 1M rows, 5 nodes, 4 cores
  python generate_data.py --rows 5000000                     # 5M rows
  python generate_data.py --rows 10000000 --nodes 10 --cores 8
  python generate_data.py --rows 1000000 --output data_1M.csv
"""

import argparse
import csv
import os
import random
import time
from datetime import datetime, timezone, timedelta


# ---------------------------------------------------------------------------
# ML processes running on the workstations
# ---------------------------------------------------------------------------

ML_PROCESSES = [
    "resnet-train",
    "bert-finetune",
    "yolo-inference",
    "data-preprocessing",
    "model-evaluation",
    "hyperparameter-search",
    "idle",
]


# ---------------------------------------------------------------------------
# KPI definitions (exactly what the daemon collects per core)
# ---------------------------------------------------------------------------

def build_per_core_kpis(num_cores: int) -> list[dict]:
    """
    Per-core hardware KPIs.
    Each entry: {name, min, max}
    """
    kpis = []
    for i in range(num_cores):
        kpis.append({"name": f"cpu_percent_core_{i}", "min": 0, "max": 100})
        kpis.append({"name": f"cpu_freq_core_{i}_mhz", "min": 800, "max": 4500})
        kpis.append({"name": f"cpu_voltage_core_{i}_v", "min": 0.6, "max": 1.5})
        kpis.append({"name": f"cpu_temp_core_{i}_celsius", "min": 30, "max": 100})
    return kpis


# Process-specific energy KPIs (use Workload_Tag to identify the process)
PROCESS_KPIS = [
    {"name": "process_energy_joules", "min": 0.1, "max": 500},
    {"name": "process_cpu_percent", "min": 0, "max": 100},
    {"name": "process_power_watts", "min": 0.5, "max": 150},
]


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

def generate_csv(
    output_path: str,
    total_rows: int,
    num_nodes: int,
    num_cores: int,
    num_processes: int,
    interval_seconds: float,
    start_time: datetime,
    seed: int,
):
    random.seed(seed)

    node_ids = [f"workstation-{i+1:02d}" for i in range(num_nodes)]
    core_kpis = build_per_core_kpis(num_cores)

    # Calculate rows per tick
    # Each tick: every node emits all core KPIs + process KPIs for active processes
    core_rows_per_node = len(core_kpis)                    # 4 KPIs × num_cores
    process_rows_per_node = len(PROCESS_KPIS) * num_processes  # 3 KPIs × num_processes
    rows_per_node = core_rows_per_node + process_rows_per_node
    rows_per_tick = rows_per_node * num_nodes

    print(f"Generating {total_rows:,} rows...")
    print(f"  Nodes:              {num_nodes} ({', '.join(node_ids[:3])}{'...' if num_nodes > 3 else ''})")
    print(f"  CPU cores/node:     {num_cores}")
    print(f"  Active processes:   {num_processes} per node")
    print(f"  KPIs per node:")
    print(f"    Per-core:         {core_rows_per_node} ({num_cores} cores × 4 KPIs: util, freq, voltage, temp)")
    print(f"    Per-process:      {process_rows_per_node} ({num_processes} processes × 3 KPIs: energy, cpu%, power)")
    print(f"    Total per node:   {rows_per_node}")
    print(f"  Rows per tick:      {rows_per_tick} ({num_nodes} nodes × {rows_per_node} KPIs)")
    print(f"  Polling interval:   {interval_seconds}s")
    print(f"  Seed:               {seed}")
    print(f"  Output:             {output_path}")
    print()

    written = 0
    report_interval = max(1, total_rows // 20)
    gen_start = time.monotonic()

    # Each node has active processes that change occasionally
    node_processes = {}
    for node in node_ids:
        active = random.sample(ML_PROCESSES, min(num_processes, len(ML_PROCESSES)))
        node_processes[node] = active

    process_change_probability = 0.005  # 0.5% chance per tick

    current_ts = start_time

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "Node_ID", "Workload_Tag", "KPI_Name", "Value"])

        while written < total_rows:
            ts_str = current_ts.strftime("%Y-%m-%dT%H:%M:%S.") + \
                     f"{current_ts.microsecond // 1000:03d}+00:00"

            for node_id in node_ids:
                if written >= total_rows:
                    break

                # Occasionally change which processes are running
                if random.random() < process_change_probability:
                    node_processes[node_id] = random.sample(
                        ML_PROCESSES, min(num_processes, len(ML_PROCESSES))
                    )

                # --- Per-core KPIs (Workload_Tag = "system") ---
                for kpi in core_kpis:
                    if written >= total_rows:
                        break
                    value = round(random.uniform(kpi["min"], kpi["max"]), 6)
                    writer.writerow([ts_str, node_id, "system", kpi["name"], value])
                    written += 1

                # --- Process-specific KPIs (Workload_Tag = process name) ---
                for process_name in node_processes[node_id]:
                    if written >= total_rows:
                        break
                    for pkpi in PROCESS_KPIS:
                        if written >= total_rows:
                            break
                        value = round(random.uniform(pkpi["min"], pkpi["max"]), 6)
                        writer.writerow([ts_str, node_id, process_name, pkpi["name"], value])
                        written += 1

                if written % report_interval == 0:
                    elapsed = time.monotonic() - gen_start
                    rate = written / elapsed if elapsed > 0 else 0
                    pct = (written / total_rows) * 100
                    print(f"  {pct:5.1f}% | {written:>12,} rows | "
                          f"{rate:,.0f} rows/sec | {elapsed:.1f}s")

            current_ts += timedelta(seconds=interval_seconds)

    elapsed = time.monotonic() - gen_start
    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    ticks = max(1, written / rows_per_tick)
    span = timedelta(seconds=ticks * interval_seconds)

    print(f"\nDone!")
    print(f"  Total rows:        {written:,}")
    print(f"  File size:         {file_size_mb:.1f} MB")
    print(f"  Time taken:        {elapsed:.1f}s")
    print(f"  Generation rate:   {written / elapsed:,.0f} rows/sec")
    print(f"  Time span covered: {span.days} days, {span.seconds // 3600} hours")
    print(f"\nSample rows:")

    with open(output_path) as f:
        for i, line in enumerate(f):
            if i > 6:
                break
            print(f"  {line.rstrip()}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate benchmark data matching the MLab daemon payload schema",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Schema:
  Timestamp, Node_ID, Workload_Tag, KPI_Name, Value

Per-core KPIs (Workload_Tag = "system"):
  cpu_percent_core_X       CPU utilization (0-100%%)
  cpu_freq_core_X_mhz      CPU frequency (800-4500 MHz)
  cpu_voltage_core_X_v      CPU voltage (0.6-1.5 V)
  cpu_temp_core_X_celsius   CPU temperature (30-100 °C)

Per-process KPIs (Workload_Tag = process name):
  process_energy_joules     Energy consumed (0.1-500 J)
  process_cpu_percent       CPU usage (0-100%%)
  process_power_watts       Power draw (0.5-150 W)

Examples:
  python generate_data.py --rows 1000000
  python generate_data.py --rows 5000000 --nodes 10 --cores 8
  python generate_data.py --rows 10000000 --nodes 5 --processes 3 --output data_10M.csv
        """,
    )
    parser.add_argument("--rows", type=int, default=1_000_000,
                        help="Total rows to generate (default: 1,000,000)")
    parser.add_argument("--nodes", type=int, default=5,
                        help="Number of workstations (default: 5)")
    parser.add_argument("--cores", type=int, default=4,
                        help="CPU cores per node (default: 4)")
    parser.add_argument("--processes", type=int, default=2,
                        help="Active ML processes per node (default: 2)")
    parser.add_argument("--interval", type=float, default=2.0,
                        help="Seconds between collection ticks (default: 2.0)")
    parser.add_argument("--start", default="2025-01-01T00:00:00",
                        help="Start timestamp (default: 2025-01-01T00:00:00)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility (default: 42)")
    parser.add_argument("--output", "-o", default="benchmark_data.csv",
                        help="Output file path (default: benchmark_data.csv)")
    args = parser.parse_args()

    start_time = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)

    generate_csv(
        output_path=args.output,
        total_rows=args.rows,
        num_nodes=args.nodes,
        num_cores=args.cores,
        num_processes=args.processes,
        interval_seconds=args.interval,
        start_time=start_time,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()