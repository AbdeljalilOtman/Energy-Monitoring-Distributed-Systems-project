"""
Validation script for Micro-Step 3: Payload Builder.

Verifies that the merged output follows the optimized nested JSON schema
(Option B from our architectural decision).
"""

import json
from payload_builder import build_payload


def validate():
    print("=" * 60)
    print("MICRO-STEP 3 VALIDATION: The Payload Formatter (JSON Envelope)")
    print("=" * 60)

    # Use a dummy node ID and workload tag for testing
    NODE_ID = "mlab-win-01"
    WORKLOAD_TAG = "idle"

    print("Collecting metrics... (this will take ~2 seconds because of the intervals)")
    payload = build_payload(NODE_ID, WORKLOAD_TAG, interval=1.0)

    # Print the JSON nicely
    print("\n[GENERATED PAYLOAD]")
    print(json.dumps(payload, indent=2))

    # --- Assertions ---
    errors = []

    if not isinstance(payload, dict):
        errors.append("Payload must be a dictionary.")
    else:
        # Check root keys
        for key in ["timestamp", "node_id", "workload_tag", "metrics"]:
            if key not in payload:
                errors.append(f"Missing root key: {key}")

        if "metrics" in payload:
            if not isinstance(payload["metrics"], dict):
                errors.append("'metrics' must be a dictionary.")
            else:
                for k, v in payload["metrics"].items():
                    if not isinstance(k, str):
                        errors.append(f"Metric key '{k}' must be a string.")
                    if not isinstance(v, (int, float)):
                        errors.append(f"Metric value '{k}' must be numeric, got {type(v)}")

    # --- Result ---
    if errors:
        print("\n[FAILED] Validation errors:")
        for e in errors:
            print(f"  - {e}")
    else:
        num_metrics = len(payload.get("metrics", {}))
        print(f"\nSuccessfully packaged {num_metrics} KPIs into a single JSON envelope.")
        print("[PASSED] Payload structural validation successful (Option B selected).")


if __name__ == "__main__":
    validate()

