"""
Micro-Step 2: Power Metrics Collector via Intel RAPL.

Reads energy counters from /sys/class/powercap/intel-rapl/ (Linux + Intel only).
Computes instantaneous power (Watts) by taking two readings separated by a
time delta.

On non-Linux or non-Intel systems, falls back to simulation mode so the
rest of the pipeline can be developed and tested.
"""

import os
import time
import glob
import platform


# ---------------------------------------------------------------------------
# RAPL sysfs path (Linux only)
# ---------------------------------------------------------------------------
RAPL_BASE = "/sys/class/powercap"


def _discover_rapl_domains():
    """
    Scan sysfs to find all RAPL energy domains.

    Returns:
        list[dict]: Each dict has:
            - name (str): human-readable domain name (e.g. "package-0", "core", "uncore")
            - path (str): full path to the energy_uj file
    """
    domains = []
    pattern = os.path.join(RAPL_BASE, "intel-rapl:*", "energy_uj")
    # Also pick up sub-domains like intel-rapl:0:0
    sub_pattern = os.path.join(RAPL_BASE, "intel-rapl:*", "intel-rapl:*:*", "energy_uj")

    for p in sorted(glob.glob(pattern) + glob.glob(sub_pattern)):
        # Read the domain name from the sibling "name" file
        name_file = os.path.join(os.path.dirname(p), "name")
        try:
            with open(name_file, "r") as f:
                name = f.read().strip()
        except OSError:
            name = os.path.basename(os.path.dirname(p))
        domains.append({"name": name, "path": p})

    return domains


def _read_energy_uj(path):
    """Read a single energy_uj file and return value in microjoules (int)."""
    with open(path, "r") as f:
        return int(f.read().strip())


def collect_power_metrics_rapl(interval=1.0):
    """
    Collect power draw from all discovered Intel RAPL domains.

    Takes two energy readings separated by `interval` seconds and computes
    instantaneous power in Watts.

    Args:
        interval: Seconds between the two energy readings. Longer = more
                  accurate but slower. 1.0s is a good default.

    Returns:
        dict with keys:
            - rapl_available (bool): whether RAPL was found
            - domains (list[dict]): each has:
                - name (str): domain name
                - power_watts (float): computed power draw
                - energy_delta_joules (float): energy consumed during interval
    """
    domains = _discover_rapl_domains()

    if not domains:
        return {"rapl_available": False, "domains": []}

    # --- First reading ---
    readings_1 = []
    for d in domains:
        readings_1.append(_read_energy_uj(d["path"]))
    t1 = time.monotonic()

    # --- Wait ---
    time.sleep(interval)

    # --- Second reading ---
    t2 = time.monotonic()
    readings_2 = []
    for d in domains:
        readings_2.append(_read_energy_uj(d["path"]))

    dt = t2 - t1  # actual elapsed seconds

    results = []
    for i, d in enumerate(domains):
        delta_uj = readings_2[i] - readings_1[i]

        # Handle counter wraparound (RAPL counters are 32-bit on some systems)
        if delta_uj < 0:
            # Read max_energy_range_uj to handle wrap
            max_file = os.path.join(os.path.dirname(d["path"]), "max_energy_range_uj")
            try:
                with open(max_file, "r") as f:
                    max_uj = int(f.read().strip())
                delta_uj += max_uj
            except OSError:
                delta_uj = 0  # can't recover, skip this sample

        delta_joules = delta_uj / 1_000_000.0
        power_watts = delta_joules / dt

        results.append({
            "name": d["name"],
            "power_watts": round(power_watts, 3),
            "energy_delta_joules": round(delta_joules, 4),
        })

    return {"rapl_available": True, "domains": results}


# ---------------------------------------------------------------------------
# Windows via LibreHardwareMonitor Local API
# ---------------------------------------------------------------------------

def collect_power_metrics_windows(interval=1.0):
    """
    Attempts to read power metrics from LibreHardwareMonitor (LHM) on Windows.
    LHM must be running with 'Web Server' enabled (default port 8085).
    """
    import urllib.request
    import json

    # We sleep to mimic the blocking interval (since LibreHardware Monitor reads instantaneously)
    time.sleep(interval)

    domains = []
    extra_metrics = {}
    try:
        # Request data from LHM local API
        req = urllib.request.Request("http://localhost:8085/data.json")
        with urllib.request.urlopen(req, timeout=1.0) as response:
            data = json.loads(response.read().decode('utf-8'))
            
        def find_sensors(node, inside_cpu=False):
            text = node.get("Text", "")
            node_type = node.get("Type", "")
            val_str = str(node.get("Value", ""))
            
            # Detect if we have traversed into the CPU hardware block
            if "intel" in text.lower() or "amd" in text.lower() or "cpu" in text.lower():
                inside_cpu = True
                
            if inside_cpu and val_str:
                # Capture Temperature
                if node_type == "Temperature" and ("Core" in text or "Package" in text):
                    try:
                        extra_metrics["cpu_temperature_c"] = float(val_str.replace(" °C", "").replace(",", "."))
                    except ValueError: pass
                # Capture Voltage
                elif node_type == "Voltage" and ("Core" in text or "VCore" in text or "VID" in text):
                    try:
                        extra_metrics["cpu_voltage_v"] = float(val_str.replace(" V", "").replace(",", "."))
                    except ValueError: pass

            # Check if this node is a Power sensor
            if node_type == "Power" or ("Power" in text and "Value" in node):
                val_clean = val_str.replace(" W", "").replace(",", ".")
                try:
                    watts = float(val_clean)
                    domains.append({
                        "name": text.replace(" ", "_").lower(),
                        "power_watts": round(watts, 3),
                        "energy_delta_joules": round(watts * interval, 4) 
                    })
                except ValueError:
                    pass
            
            # Recurse
            for child in node.get("Children", []):
                find_sensors(child, inside_cpu)
                
        find_sensors(data)
        
        if domains:
            return {"lhm_available": True, "simulated": False, "domains": domains, **extra_metrics}

    except Exception:
        pass
        
    return {"lhm_available": False, "simulated": False, "domains": []}


# ---------------------------------------------------------------------------
# Raspberry Pi (ARM) Power Check
# ---------------------------------------------------------------------------

def collect_power_metrics_rpi(interval=1.0):
    """
    Attempts to read Raspberry Pi power. Natively, Pi only reports core voltage.
    Real MLabs use I2C INA219/INA260 sensors. Here we provide the stub for it.
    """
    import subprocess
    
    time.sleep(interval)
    domains = []
    try:
        # 1. Read standard Pi Core Voltage
        out = subprocess.check_output(["vcgencmd", "measure_volts", "core"], text=True)
        if "volt=" in out:
            volts = float(out.split("=")[1].replace("V", "").strip())
            extra_metrics["cpu_voltage_v"] = volts
            estimated_watts = (volts * 2.5) 
            
            domains.append({
                "name": "rpi_core",
                "power_watts": round(estimated_watts, 3),
                "energy_delta_joules": round(estimated_watts * interval, 4)
            })

        # 2. Read standard Pi Core Temperature
        temp_out = subprocess.check_output(["vcgencmd", "measure_temp"], text=True)
        if "temp=" in temp_out:
            temp_c = float(temp_out.split("=")[1].replace("'C", "").strip())
            extra_metrics["cpu_temperature_c"] = temp_c

    except Exception:
        pass
        
    if domains:
        return {"rpi_available": True, "simulated": False, "domains": domains, **extra_metrics}
        
    return {"rpi_available": False, "simulated": False, "domains": []}


# ---------------------------------------------------------------------------
# Simulated fallback (for development without hardware tools)
# ---------------------------------------------------------------------------

def collect_power_metrics_simulated(interval=1.0):
    """
    Returns realistic fake data if Linux/RAPL, Windows/LHM, and Pi fail.
    """
    import random
    # time.sleep is handled by the caller or inside the block, but simulated needs it
    # wait, if LHM failed, it already slept. We only sleep if calling this directly.
    # We will just sleep anyway to be safe, except let's trust the interval
    # Actually, we shouldn't double sleep. Let's just return immediately because 
    # the failure above already took time. Wait, if Pi fails it takes time. 
    # If RAPL fails, it returns instantly. So let's sleep here for RAPL failure.
    time.sleep(interval) 
    return {
        "rapl_available": False,
        "lhm_available": False,
        "rpi_available": False,
        "simulated": True,
        "cpu_temperature_c": round(random.uniform(40.0, 65.0), 1),
        "cpu_voltage_v": round(random.uniform(1.1, 1.3), 2),
        "domains": [
            {
                "name": "package-0",
                "power_watts": round(random.uniform(15.0, 65.0), 3),
                "energy_delta_joules": round(random.uniform(15.0, 65.0) * interval, 4),
            },
            {
                "name": "core",
                "power_watts": round(random.uniform(5.0, 35.0), 3),
                "energy_delta_joules": round(random.uniform(5.0, 35.0) * interval, 4),
            },
            {
                "name": "uncore",
                "power_watts": round(random.uniform(1.0, 10.0), 3),
                "energy_delta_joules": round(random.uniform(1.0, 10.0) * interval, 4),
            },
        ],
    }


# ---------------------------------------------------------------------------
# Unified entry point
# ---------------------------------------------------------------------------

def collect_power_metrics(interval=1.0):
    """
    Auto-detect platform and collect power metrics.

    - Linux + Intel RAPL available → real readings
    - Windows + LibreHardwareMonitor → real readings
    - Raspberry Pi (ARM) → Vcore approximation / I2C Stub
    - Otherwise → simulated data (flagged in output)

    Args:
        interval: Seconds for the measurement window.

    Returns:
        dict: Power metrics containing watts and joules.
    """
    system = platform.system()
    machine = platform.machine().lower()

    if system == "Linux":
        if os.path.isdir(RAPL_BASE):
            result = collect_power_metrics_rapl(interval)
            if result.get("rapl_available"):
                return result
                
        if "arm" in machine or "aarch" in machine:
            result = collect_power_metrics_rpi(interval)
            if result.get("rpi_available"):
                return result
                
    elif system == "Windows":
        result = collect_power_metrics_windows(interval)
        if result.get("lhm_available"):
            return result

    # Fallback to simulation if all hardware checks fail or aren't running


    # Fallback to simulation
    return collect_power_metrics_simulated(interval)
