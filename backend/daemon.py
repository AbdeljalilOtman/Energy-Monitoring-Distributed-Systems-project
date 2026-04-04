import json
import time
import logging
import requests
from datetime import datetime, timezone
from router import KPIRouter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KPIDaemon:
    def __init__(self, config_path="config.json"):
        self.config = self._load_config(config_path)
        self.polling_interval = self.config["polling_interval_seconds"]
        self.kpi_source = self.config["kpi_source"]
        self.node_id = self.config.get("node_id", "local_node")
        self.dashboard_url = self.config.get("dashboard_url", None)
        self.running = False
        
        # Initialize router for local database storage
        self.router = KPIRouter(self.config["database"])
        
        # Register with central dashboard if URL provided
        if self.dashboard_url:
            self._register_with_dashboard()

    def _load_config(self, path):
        with open(path, 'r') as f:
            return json.load(f)

    def _register_with_dashboard(self):
        """Register this daemon instance with the central dashboard"""
        try:
            payload = {
                "node_id": self.node_id,
                "polling_interval": self.polling_interval
            }
            response = requests.post(
                f"{self.dashboard_url}/api/nodes/register",
                json=payload,
                timeout=5
            )
            if response.status_code == 200:
                logger.info(f"Successfully registered with dashboard at {self.dashboard_url}")
            else:
                logger.warning(f"Dashboard registration failed with status {response.status_code}")
        except Exception as e:
            logger.warning(f"Could not connect to dashboard at {self.dashboard_url}: {e}")

    def _read_kpi_data(self):
        """Read KPI data from JSON file"""
        try:
            with open(self.kpi_source, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read KPI data: {e}")
            return None

    def _extract_kpis(self, raw_data):
        """Extract KPI metrics from JSON data (timestamp, NodeID, WorkloadTag, KPI_name, Value)"""
        extracted = []
        # Always use current UTC time as timestamp for fresh data (timezone-aware)
        timestamp = datetime.now(timezone.utc).isoformat()
        
        for metric in raw_data.get("metrics", []):
            extracted.append({
                "timestamp": timestamp,
                "NodeID": metric["NodeID"],
                "WorkloadTag": metric["WorkloadTag"],
                "KPI_name": metric["KPI_name"],
                "Value": metric["Value"]
            })
        return extracted

    def _push_to_dashboard(self, kpi_records):
        """Push KPI records to central dashboard"""
        if not self.dashboard_url or not kpi_records:
            return
        
        try:
            payload = {
                "node_id": self.node_id,
                "records": kpi_records
            }
            response = requests.post(
                f"{self.dashboard_url}/api/kpi/submit",
                json=payload,
                timeout=5
            )
            if response.status_code == 200:
                logger.info(f"Pushed {len(kpi_records)} records to dashboard")
            else:
                logger.warning(f"Dashboard push failed with status {response.status_code}")
        except Exception as e:
            logger.warning(f"Could not push data to dashboard: {e}")

    def run(self):
        """Main daemon loop"""
        self.running = True
        logger.info(f"Daemon started. Node ID: {self.node_id}")
        logger.info(f"Polling every {self.polling_interval} seconds.")
        if self.dashboard_url:
            logger.info(f"Dashboard URL: {self.dashboard_url}")
        
        while self.running:
            try:
                # 1. Read KPI data
                raw_data = self._read_kpi_data()
                if raw_data:
                    # 2. Extract relevant KPIs
                    kpis = self._extract_kpis(raw_data)
                    
                    # 3. Route to local database
                    self.router.send_to_database(kpis)
                    logger.info(f"Processed {len(kpis)} node(s) KPI data")
                    
                    # 4. Push to dashboard if configured
                    self._push_to_dashboard(kpis)
                
                time.sleep(self.polling_interval)
            except KeyboardInterrupt:
                self.stop()
            except Exception as e:
                logger.error(f"Unexpected error in daemon loop: {e}")
                time.sleep(self.polling_interval)

    def stop(self):
        self.running = False
        logger.info("Daemon stopped.")

if __name__ == "__main__":
    daemon = KPIDaemon()
    daemon.run()