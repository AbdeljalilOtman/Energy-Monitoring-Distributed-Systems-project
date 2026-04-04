"""Quick test of the transformer module"""
from datetime import datetime, timezone
from transformer import transform_payload_to_backend, validate_transformed_payload
import json

# Create a test payload (colleague's format)
test_payload = {
    'timestamp': int(datetime.now(timezone.utc).timestamp()),
    'node_id': 'test-node-1',
    'workload_tag': 'training',
    'metrics': {
        'cpu_percent_total': 45.5,
        'cpu_percent_core_0': 50.2,
        'cpu_percent_core_1': 40.8,
        'memory_percent': 65.3,
        'disk_read_mb': 1024.5,
        'disk_write_mb': 256.3,
        'power_watts_package-0': 150.2
    }
}

print('INPUT (Colleague Format):')
print(json.dumps(test_payload, indent=2))
print('\n' + '='*60 + '\n')

# Transform to backend format
transformed = transform_payload_to_backend(test_payload)

print('OUTPUT (Backend Format):')
print(json.dumps(transformed, indent=2))
print('\n' + '='*60 + '\n')

# Validate
is_valid = validate_transformed_payload(transformed)
status = "PASSED" if is_valid else "FAILED"
print(f'Validation: {status}')
print(f'Record Count: {len(transformed["records"])}')
print('\nSample Record:')
if transformed['records']:
    print(json.dumps(transformed['records'][0], indent=2))
