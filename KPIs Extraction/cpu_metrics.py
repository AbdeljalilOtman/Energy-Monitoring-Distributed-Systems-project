"""
Micro-Step 1: CPU Metrics Collector using psutil.

Retrieves CPU utilization (total + per-core) and CPU frequency
from the local machine. Designed as a pure data-extraction function
that returns a structured dict — no side effects (no printing, no
network calls). This makes it testable and composable.
"""

import psutil


def collect_cpu_metrics(percpu_interval=1.0):
    """
    Collect CPU utilization and frequency metrics.

    Args:
        percpu_interval: Seconds to block while measuring CPU percent.
                         psutil needs a non-zero interval to compare
                         two snapshots of /proc/stat. 1.0s is the default;
                         lower values (e.g. 0.1) are faster but less accurate.

    Returns:
        dict with keys:
            - cpu_percent_total (float): system-wide CPU usage %
            - cpu_percent_per_core (list[float]): per-core CPU usage %
            - cpu_freq_current_mhz (list[float]): per-core current freq in MHz
            - cpu_freq_min_mhz (float | None): min freq (if reported by OS)
            - cpu_freq_max_mhz (float | None): max freq (if reported by OS)
    """
    # --- CPU Utilization ---
    # interval > 0 makes this a blocking call that compares two snapshots
    per_core_percent = psutil.cpu_percent(interval=percpu_interval, percpu=True)
    total_percent = sum(per_core_percent) / len(per_core_percent)

    # --- CPU Frequency ---
    freq_per_core = psutil.cpu_freq(percpu=True)

    # On some systems (e.g. VMs), percpu=True may return a single-element list.
    # We handle both cases gracefully.
    if freq_per_core:
        current_freqs = [f.current for f in freq_per_core]
        freq_min = freq_per_core[0].min  # min/max are usually the same across cores
        freq_max = freq_per_core[0].max
    else:
        # Fallback: try the aggregate call
        freq_agg = psutil.cpu_freq(percpu=False)
        if freq_agg:
            current_freqs = [freq_agg.current]
            freq_min = freq_agg.min
            freq_max = freq_agg.max
        else:
            current_freqs = []
            freq_min = None
            freq_max = None

    # --- CPU Temperature ---
    # psutil supports temperatures on Linux/macOS/Pi. On Windows it returns an empty dict or raises.
    temp_c = None
    if hasattr(psutil, "sensors_temperatures"):
        try:
            temps = psutil.sensors_temperatures()
            # Target well-known CPU thermals first
            for name in ('coretemp', 'k10temp', 'cpu_thermal', 'cpu-thermal'):
                if name in temps and temps[name]:
                    temp_c = temps[name][0].current
                    break
            # Generic fallback
            if temp_c is None and temps:
                temp_c = list(temps.values())[0][0].current
        except Exception:
            pass

    return {
        "cpu_percent_total": round(total_percent, 2),
        "cpu_percent_per_core": [round(p, 2) for p in per_core_percent],
        "cpu_freq_current_mhz": [round(f, 2) for f in current_freqs],
        "cpu_freq_min_mhz": freq_min,
        "cpu_freq_max_mhz": freq_max,
        "cpu_temperature_c": temp_c,
    }
