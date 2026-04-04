"""
Micro-Step 4: The Daemon Transmission Loop

This is the main entry point for the Edge Node. It runs continuously,
calling the Payload Builder every N seconds, and pushes the resulting JSON
to the Backend.

For this phase, since the backend API does not exist yet, we implemented a 
'dry_run' mode that just prints to the console. 
"""

import time
import logging
import json
import urllib.request
import urllib.error

from payload_builder import build_payload

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
    backend_url: str = None,
    dry_run: bool = True
):
    """
    Main monitoring loop.
    
    Args:
        node_id: Identity of the edge node answering the telemetry.
        workload_tag: Contextual label (e.g. "training-resnet").
        poll_interval_sec: Time to wait between measurements.
        backend_url: The HTTP POST endpoint of the database ingest server.
        dry_run: If True, prints JSON locally instead of sending generic HTTP.
    """
    logging.info(f"Starting MLab Telemetry Daemon on Node [{node_id}]")
    logging.info(f"Poll Interval: {poll_interval_sec}s | Workload: {workload_tag}")
    
    if dry_run:
        logging.warning("Running in DRY RUN mode. Data will NOT be transmitted.")
    elif not backend_url:
        logging.error("No backend_url provided and dry_run=False. Exiting.")
        return

    try:
        while True:
            # 1. Build the Data Envelope
            # Note: build_payload takes time to complete based on interval.
            payload = build_payload(node_id, workload_tag, interval=poll_interval_sec)

            # 2. Transmit 
            if dry_run:
                # Pretty-print the metric count instead of the whole payload to keep logs clean
                metric_count = len(payload.get("metrics", {}))
                logging.info(f"[DRY-RUN] Would transmit JSON ({metric_count} metrics) to backend.")
            else:
                _post_to_backend(payload, backend_url)

            # 3. Wait for the next cycle
            # We don't sleep here! build_payload() already blocks for the duration
            # of the `poll_interval_sec` while it measures hardware diffs.
            
    except KeyboardInterrupt:
        logging.info("Daemon stopped by user. Exiting gracefully.")
    except Exception as e:
        logging.error(f"Daemon crashed: {e}")


def _post_to_backend(payload: dict, url: str):
    """Internal helper to shoot the JSON over standard HTTP POST."""
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
    except urllib.error.URLError as e:
        logging.error(f"Transmission failed: {e.reason}")


if __name__ == "__main__":
    # Example usage for direct execution. In a production deployment, 
    # these would come from sys.argv or a .env file.
    import socket
    local_hostname = socket.gethostname()
    
    start_daemon(
        node_id=f"{local_hostname}-dev",
        workload_tag="idle",
        poll_interval_sec=2.0,   # Slower polling for terminal readability
        backend_url="http://127.0.0.1:8080/ingest", # Pointing to our new Mock Server
        dry_run=False            # TURNING DRY RUN OFF!
    )
