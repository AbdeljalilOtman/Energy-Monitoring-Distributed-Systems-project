"""
Validation script for Micro-Step 1.

Run this to verify that collect_cpu_metrics() works on your machine.
Expected: prints a dict with real CPU data, all values are numeric,
          per-core lists have length == number of logical CPUs.
"""

import json
import psutil
from cpu_metrics import collect_cpu_metrics


def validate():
    print("=" * 60)
    print("MICRO-STEP 1 VALIDATION: CPU Metrics via psutil")
    print("=" * 60)

    metrics = collect_cpu_metrics(percpu_interval=1.0)

    # Pretty-print the raw output
    print("\n[RAW OUTPUT]")
    print(json.dumps(metrics, indent=2))

    # --- Assertions ---
    logical_cpus = psutil.cpu_count(logical=True)
    print(f"\nLogical CPUs detected: {logical_cpus}")

    errors = []

    # 1. Total CPU percent must be a float in [0, 100]
    t = metrics["cpu_percent_total"]
    if not (isinstance(t, (int, float)) and 0.0 <= t <= 100.0):
        errors.append(f"cpu_percent_total out of range: {t}")

    # 2. Per-core list length must match logical CPU count
    pcp = metrics["cpu_percent_per_core"]
    if len(pcp) != logical_cpus:
        errors.append(
            f"cpu_percent_per_core length {len(pcp)} != {logical_cpus}"
        )

    # 3. Each per-core percent must be in [0, 100]
    for i, v in enumerate(pcp):
        if not (0.0 <= v <= 100.0):
            errors.append(f"Core {i} percent out of range: {v}")

    # 4. Frequency list should be non-empty (unless running in a VM)
    freqs = metrics["cpu_freq_current_mhz"]
    if not freqs:
        print("\n[WARNING] No per-core frequency data — this is normal in VMs.")
    else:
        for i, f in enumerate(freqs):
            if f <= 0:
                errors.append(f"Core {i} frequency non-positive: {f}")

    # --- Result ---
    if errors:
        print("\n[FAILED] Validation errors:")
        for e in errors:
            print(f"  - {e}")
    else:
        print("\n[PASSED] All checks passed.")


if __name__ == "__main__":
    validate()
