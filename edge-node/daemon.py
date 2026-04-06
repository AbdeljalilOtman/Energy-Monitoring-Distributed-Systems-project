"""
Micro-Step 4: The Daemon Transmission Loop

This is the main entry point for the Edge Node. It runs continuously,
calling the Payload Builder every N seconds, and pushes the resulting JSON
to the Backend.

"""

import time
import logging
import json
import threading
import urllib.request
import urllib.error

from payload_builder import build_payload
from transformer import transform_payload_to_backend, validate_transformed_payload

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def start_daemon(
    node_id: str,
    workload_tag: str = "idle",
    poll_interval_sec: float = 1.0,
    heartbeat_interval_sec: float = 5.0,
    backend_url: str = None,
    dry_run: bool = True
):
    """
    Main monitoring loop.
    
    Args:
        node_id: Identity of the edge node answering the telemetry (e.g., "node-1", "laptop-ml-gpu").
        workload_tag: Contextual label for the current workload (e.g., "training", "inference", "data_prep").
        poll_interval_sec: Time to wait between measurements (in seconds).
        heartbeat_interval_sec: Edge heartbeat interval used for liveness checks.
        backend_url: The base URL of the backend server (e.g., "http://localhost:5000").
                     The daemon will automatically append "/api/kpi/submit" to this URL.
        dry_run: If True, prints JSON locally instead of sending HTTP. Set to False for production.
    """
    logging.info(f"Starting Telemetry Daemon on Node [{node_id}]")
    logging.info(f"Poll Interval: {poll_interval_sec}s | Workload: {workload_tag}")
    
    if dry_run:
        logging.warning("Running in DRY RUN mode. Data will NOT be transmitted to backend.")
    elif not backend_url:
        logging.error("No backend_url provided and dry_run=False. Exiting.")
        return

    stop_event = threading.Event()
    heartbeat_thread = None

    if not dry_run and backend_url:
        _register_node(node_id, backend_url, poll_interval_sec, heartbeat_interval_sec)
        heartbeat_thread = threading.Thread(
            target=_heartbeat_loop,
            args=(stop_event, node_id, workload_tag, poll_interval_sec, heartbeat_interval_sec, backend_url),
            daemon=True
        )
        heartbeat_thread.start()

    try:
        while True:
            # 1. Build the Data Envelope (nested format)
            # Note: build_payload takes time to complete based on interval.
            payload = build_payload(node_id, workload_tag, interval=poll_interval_sec)

            # 2. Transform to backend format (flat array)
            transformed_payload = transform_payload_to_backend(payload)
            
            # 3. Validate transformed payload
            if not validate_transformed_payload(transformed_payload):
                logging.error("Transformed payload validation failed!")
                continue

            # 4. Transmit 
            if dry_run:
                # Pretty-print the record count instead of the whole payload to keep logs clean
                record_count = len(transformed_payload.get("records", []))
                logging.info(f"[DRY-RUN] Would transmit {record_count} records to backend.")
            else:
                _post_to_backend(transformed_payload, backend_url)

            # 5. Wait for the next cycle
            # We don't sleep here! build_payload() already blocks for the duration
            # of the `poll_interval_sec` while it measures hardware diffs.
            
    except KeyboardInterrupt:
        stop_event.set()
        logging.info("Daemon stopped by user. Exiting gracefully.")
    except Exception as e:
        stop_event.set()
        logging.error(f"Daemon crashed: {e}")


def _make_endpoint_url(base_url: str, endpoint: str):
    if base_url.endswith(endpoint):
        return base_url
    if base_url.endswith("/"):
        return base_url + endpoint.lstrip("/")
    return base_url + endpoint


def _post_json(url: str, payload: dict, timeout: float = 5.0):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.status


def _register_node(node_id: str, backend_url: str, poll_interval_sec: float, heartbeat_interval_sec: float):
    """Best-effort registration call so backend can initialize node state."""
    register_url = _make_endpoint_url(backend_url, "/api/nodes/register")
    payload = {
        "node_id": node_id,
        "polling_interval": poll_interval_sec,
        "heartbeat_interval_sec": heartbeat_interval_sec
    }
    try:
        _post_json(register_url, payload, timeout=3.0)
        logging.info(f"Node registration sent to {register_url}")
    except Exception as e:
        logging.warning(f"Node registration failed: {e}")


def _heartbeat_loop(
    stop_event: threading.Event,
    node_id: str,
    workload_tag: str,
    poll_interval_sec: float,
    heartbeat_interval_sec: float,
    backend_url: str
):
    """Send lightweight heartbeat pings to support liveness detection at server side."""
    heartbeat_url = _make_endpoint_url(backend_url, "/api/nodes/heartbeat")
    while not stop_event.is_set():
        payload = {
            "node_id": node_id,
            "workload_tag": workload_tag,
            "polling_interval": poll_interval_sec,
            "heartbeat_interval_sec": heartbeat_interval_sec,
            "sent_at": time.time()
        }
        try:
            status = _post_json(heartbeat_url, payload, timeout=3.0)
            if status not in (200, 201, 202):
                logging.warning(f"Heartbeat returned non-success status: {status}")
        except Exception as e:
            logging.warning(f"Heartbeat failed: {e}")

        stop_event.wait(max(1.0, heartbeat_interval_sec))


def _post_to_backend(payload: dict, url: str):
    """
    Internal helper to transmit the transformed payload to the backend.
    
    Args:
        payload (dict): Transformed payload with flat array format
        url (str): Backend URL (should be the base URL, e.g., http://localhost:5000)
                   The function will append /api/kpi/submit to this URL.
    """
    # Ensure URL has /api/kpi/submit endpoint
    url = _make_endpoint_url(url, "/api/kpi/submit")
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url, 
        data=data, 
        headers={'Content-Type': 'application/json'},
        method='POST'
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status not in (200, 201, 202):
                logging.warning(f"Backend returned non-success status: {response.status}")
            else:
                logging.info(f"Successfully transmitted {len(payload.get('records', []))} records to backend")
    except urllib.error.URLError as e:
        logging.error(f"Transmission failed: {e.reason}")


if __name__ == "__main__":
    # Example usage for direct execution. In a production deployment, 
    # these would come from sys.argv, environment variables, or a config file.
    import socket
    local_hostname = socket.gethostname()
    
    start_daemon(
        node_id=f"{local_hostname}-node",
        workload_tag="testing",
        poll_interval_sec=1.0,
        heartbeat_interval_sec=1.0,
        backend_url="https://g2f61m5t-5000.uks1.devtunnels.ms/",  # Points to Flask backend
        dry_run=False   # Set to False to actually transmit data
    )
