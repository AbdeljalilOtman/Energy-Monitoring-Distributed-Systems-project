"""
Validation script for Micro-Step 2: Power Metrics.

Verifies that collect_power_metrics() returns well-structured data,
whether using real RAPL readings or simulated fallback.
"""

import json
import platform
from power_metrics import collect_power_metrics


def validate():
    print("=" * 60)
    print("MICRO-STEP 2 VALIDATION: Power Metrics (RAPL / Simulated)")
    print("=" * 60)
    print(f"Platform: {platform.system()} / {platform.machine()}")

    metrics = collect_power_metrics(interval=1.0)

    # Pretty-print
    print("\n[RAW OUTPUT]")
    print(json.dumps(metrics, indent=2))

    errors = []

    # --- Structure checks ---
    if "domains" not in metrics:
        errors.append("Missing 'domains' key")
    else:
        domains = metrics["domains"]
        if not isinstance(domains, list) or len(domains) == 0:
            errors.append("'domains' must be a non-empty list")
        else:
            for i, d in enumerate(domains):
                # Each domain must have name, power_watts, energy_delta_joules
                for key in ("name", "power_watts", "energy_delta_joules"):
                    if key not in d:
                        errors.append(f"Domain {i} missing key '{key}'")

                # power_watts must be non-negative
                pw = d.get("power_watts", -1)
                if not isinstance(pw, (int, float)) or pw < 0:
                    errors.append(f"Domain {i} ({d.get('name')}) power_watts invalid: {pw}")

                # energy_delta_joules must be non-negative
                ej = d.get("energy_delta_joules", -1)
                if not isinstance(ej, (int, float)) or ej < 0:
                    errors.append(f"Domain {i} ({d.get('name')}) energy_delta_joules invalid: {ej}")

    # --- Mode reporting ---
    if metrics.get("rapl_available"):
        print("\n[MODE] Real Intel RAPL readings")
    elif metrics.get("simulated"):
        print("\n[MODE] Simulated data (non-Linux or RAPL not found)")
        print("       This is expected on Windows / AMD / VM systems.")
        print("       Deploy to a Linux+Intel machine for real readings.")
    else:
        print("\n[MODE] RAPL detected but returned no domains")

    # --- Result ---
    if errors:
        print("\n[FAILED] Validation errors:")
        for e in errors:
            print(f"  - {e}")
    else:
        print("\n[PASSED] All checks passed.")


if __name__ == "__main__":
    validate()
