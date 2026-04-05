"""
Flask Dashboard Server - Central Node Monitoring & Data Collection
Receives KPI data from multiple daemon nodes and displays in real-time dashboard
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
import sqlite3
import json
import logging
from collections import deque
from datetime import datetime, timedelta, timezone
from db_connector import DatabaseConnector
import threading
import time

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global state for connected nodes
connected_nodes = {}
nodes_lock = threading.Lock()

# Batched ingestion state
ingest_buffer = deque()
buffer_lock = threading.Lock()

# Tuning for SQLite batch insertion
BATCH_SIZE = 500
FLUSH_INTERVAL_SEC = 5

# Partial synchrony timeout model: T_heartbeat + Delta_network_delay
DEFAULT_HEARTBEAT_INTERVAL_SEC = 5
NETWORK_DELAY_BUDGET_SEC = 3
HEARTBEAT_CHECK_INTERVAL_SEC = 2

db_config = {
    "type": "sqlite",
    "path": "test_db/benchmark_test.db"
}

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(db_config["path"])
    conn.row_factory = sqlite3.Row
    return conn


def _flush_ingest_buffer(force=False):
    """Flush queued KPI records to SQLite in bulk with basic retry safety."""
    records_to_write = []
    with buffer_lock:
        if not ingest_buffer:
            return 0
        if not force and len(ingest_buffer) < BATCH_SIZE:
            return 0

        take_count = len(ingest_buffer) if force else min(BATCH_SIZE, len(ingest_buffer))
        for _ in range(take_count):
            records_to_write.append(ingest_buffer.popleft())

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.executemany('''
            INSERT INTO kpi_metrics (timestamp, NodeID, WorkloadTag, KPI_name, Value)
            VALUES (?, ?, ?, ?, ?)
        ''', [
            (
                record["timestamp"],
                record["NodeID"],
                record["WorkloadTag"],
                record["KPI_name"],
                record["Value"]
            )
            for record in records_to_write
        ])
        conn.commit()
        conn.close()
        return len(records_to_write)
    except Exception as e:
        logger.error(f"Batch insert failed for {len(records_to_write)} records: {e}")
        # Re-queue failed batch at the head so data is not lost.
        with buffer_lock:
            for record in reversed(records_to_write):
                ingest_buffer.appendleft(record)
        return 0


def _periodic_flush_worker():
    """Flush records periodically so low traffic doesn't stay buffered indefinitely."""
    while True:
        time.sleep(FLUSH_INTERVAL_SEC)
        inserted = _flush_ingest_buffer(force=True)
        if inserted > 0:
            logger.info(f"Periodic flush inserted {inserted} KPI records")


def _node_offline_checker():
    """Mark nodes offline under partial synchrony assumption when heartbeats are late."""
    while True:
        now = datetime.now(timezone.utc)
        changed_nodes = []

        with nodes_lock:
            for node_id, node_meta in connected_nodes.items():
                heartbeat_interval = node_meta.get("heartbeat_interval_sec", DEFAULT_HEARTBEAT_INTERVAL_SEC)
                timeout_window = heartbeat_interval + NETWORK_DELAY_BUDGET_SEC

                try:
                    last_seen = datetime.fromisoformat(node_meta.get("last_seen"))
                    if last_seen.tzinfo is None:
                        last_seen = last_seen.replace(tzinfo=timezone.utc)
                except Exception:
                    last_seen = now - timedelta(seconds=timeout_window + 1)

                was_status = node_meta.get("status", "unknown")
                is_offline = (now - last_seen).total_seconds() > timeout_window
                new_status = "offline" if is_offline else "active"

                if was_status != new_status:
                    node_meta["status"] = new_status
                    changed_nodes.append({"node_id": node_id, "status": new_status, "last_seen": node_meta.get("last_seen")})

        for changed in changed_nodes:
            socketio.emit('node_status_change', changed)
            logger.warning(
                f"Node {changed['node_id']} marked {changed['status']} "
                f"(partial synchrony timeout exceeded)"
            )

        time.sleep(HEARTBEAT_CHECK_INTERVAL_SEC)

@app.route('/')
def dashboard():
    """Serve dashboard HTML"""
    return render_template('dashboard.html')

@app.route('/api/nodes', methods=['GET'])
def get_nodes():
    """Get all registered nodes"""
    with nodes_lock:
        return jsonify(list(connected_nodes.values()))

@app.route('/api/metrics/<node_id>', methods=['GET'])
def get_node_metrics(node_id):
    """Get metrics for a specific node (last 100 records)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT timestamp, NodeID, WorkloadTag, KPI_name, Value
            FROM kpi_metrics
            WHERE NodeID = ?
            ORDER BY timestamp DESC
            LIMIT 100
        ''', (node_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        metrics = [
            {
                "timestamp": row["timestamp"],
                "NodeID": row["NodeID"],
                "WorkloadTag": row["WorkloadTag"],
                "KPI_name": row["KPI_name"],
                "Value": row["Value"]
            }
            for row in rows
        ]
        return jsonify(metrics)
    except Exception as e:
        logger.error(f"Error fetching metrics for {node_id}: {e}")
        return jsonify({"error": str(e), "node_id": node_id}), 500

@app.route('/api/metrics/aggregated/<node_id>', methods=['GET'])
def get_aggregated_metrics(node_id):
    """Get aggregated metrics by KPI (last 24 hours)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        one_day_ago = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        
        cursor.execute('''
            SELECT 
                KPI_name,
                WorkloadTag,
                AVG(Value) as avg_value,
                MAX(Value) as max_value,
                MIN(Value) as min_value,
                COUNT(*) as sample_count
            FROM kpi_metrics
            WHERE NodeID = ? AND timestamp > ?
            GROUP BY KPI_name, WorkloadTag
        ''', (node_id, one_day_ago))
        
        rows = cursor.fetchall()
        conn.close()
        
        if rows:
            metrics = [
                {
                    "KPI_name": row["KPI_name"],
                    "WorkloadTag": row["WorkloadTag"],
                    "avg_value": round(row["avg_value"], 2),
                    "max_value": round(row["max_value"], 2),
                    "min_value": round(row["min_value"], 2),
                    "sample_count": row["sample_count"]
                }
                for row in rows
            ]
            return jsonify({
                "NodeID": node_id,
                "metrics": metrics
            })
        return jsonify({"NodeID": node_id, "metrics": []}), 200
    except Exception as e:
        logger.error(f"Error fetching aggregated metrics for {node_id}: {e}")
        return jsonify({"error": str(e), "node_id": node_id}), 500

@app.route('/api/dashboard/summary', methods=['GET'])
def get_dashboard_summary():
    """Get summary for all nodes with KPI breakdown"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                NodeID,
                MAX(timestamp) as last_update,
                COUNT(DISTINCT KPI_name) as kpi_count,
                COUNT(DISTINCT WorkloadTag) as workload_count
            FROM kpi_metrics
            GROUP BY NodeID
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        summary = []
        summary_by_node = {}
        for row in rows:
            node_id = row["NodeID"]
            last_update = row["last_update"]
            
            # Check if node is responsive (updated within last 30 seconds)
            # Parse timestamp and ensure it's timezone-aware
            last_update_time = datetime.fromisoformat(last_update)
            if last_update_time.tzinfo is None:
                # Make naive datetime aware (UTC)
                last_update_time = last_update_time.replace(tzinfo=timezone.utc)
            is_healthy = (datetime.now(timezone.utc) - last_update_time).total_seconds() < 30
            
            entry = {
                "NodeID": node_id,
                "status": "healthy" if is_healthy else "unhealthy",
                "last_update": last_update,
                "connected": False,
                "kpi_count": row["kpi_count"],
                "workload_count": row["workload_count"]
            }
            summary.append(entry)
            summary_by_node[node_id] = entry

        with nodes_lock:
            for node_id, node_meta in connected_nodes.items():
                if node_id in summary_by_node:
                    summary_by_node[node_id]["connected"] = node_meta.get("status") == "active"
                    # Prefer heartbeat state if available.
                    if node_meta.get("status") == "offline":
                        summary_by_node[node_id]["status"] = "unhealthy"
                else:
                    summary.append({
                        "NodeID": node_id,
                        "status": "healthy" if node_meta.get("status") == "active" else "unhealthy",
                        "last_update": node_meta.get("last_seen", node_meta.get("registered_at")),
                        "connected": node_meta.get("status") == "active",
                        "kpi_count": 0,
                        "workload_count": 0
                    })
        
        return jsonify(summary)
    except Exception as e:
        logger.error(f"Error fetching dashboard summary: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/nodes/register', methods=['POST'])
def register_node():
    """Register a new node (called by daemon on startup)"""
    data = request.json
    node_id = data.get("node_id")
    node_ip = request.remote_addr
    polling_interval = data.get("polling_interval", 5)
    heartbeat_interval = data.get("heartbeat_interval_sec", DEFAULT_HEARTBEAT_INTERVAL_SEC)
    now_iso = datetime.now(timezone.utc).isoformat()
    
    with nodes_lock:
        connected_nodes[node_id] = {
            "node_id": node_id,
            "ip_address": node_ip,
            "polling_interval": polling_interval,
            "heartbeat_interval_sec": heartbeat_interval,
            "registered_at": now_iso,
            "last_seen": now_iso,
            "status": "active"
        }
    
    logger.info(f"Node {node_id} registered from {node_ip}")
    with nodes_lock:
        socketio.emit('node_registered', connected_nodes[node_id])
    
    return jsonify({"status": "registered", "node_id": node_id})


@app.route('/api/nodes/heartbeat', methods=['POST'])
def node_heartbeat():
    """Receive lightweight heartbeat ping from edge nodes."""
    try:
        data = request.json or {}
        node_id = data.get("node_id")
        if not node_id:
            return jsonify({"error": "node_id is required"}), 400

        now_iso = datetime.now(timezone.utc).isoformat()
        heartbeat_interval = data.get("heartbeat_interval_sec", DEFAULT_HEARTBEAT_INTERVAL_SEC)

        with nodes_lock:
            node_state = connected_nodes.get(node_id)
            if not node_state:
                node_state = {
                    "node_id": node_id,
                    "ip_address": request.remote_addr,
                    "polling_interval": data.get("polling_interval", DEFAULT_HEARTBEAT_INTERVAL_SEC),
                    "heartbeat_interval_sec": heartbeat_interval,
                    "registered_at": now_iso,
                    "last_seen": now_iso,
                    "status": "active"
                }
                connected_nodes[node_id] = node_state
            else:
                node_state["ip_address"] = request.remote_addr
                node_state["last_seen"] = now_iso
                node_state["heartbeat_interval_sec"] = heartbeat_interval
                node_state["status"] = "active"

        return jsonify({"status": "ok", "node_id": node_id, "last_seen": now_iso})
    except Exception as e:
        logger.error(f"Heartbeat processing failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/kpi/submit', methods=['POST'])
def submit_kpi():
    """Receive KPI data from daemon and enqueue for batched persistence."""
    try:
        data = request.json
        node_id = data.get("node_id")
        kpi_records = data.get("records", [])
        
        if not kpi_records:
            return jsonify({"error": "No records provided"}), 400
        
        with buffer_lock:
            for record in kpi_records:
                ingest_buffer.append(record)

        # Opportunistic flush on size threshold.
        inserted_now = _flush_ingest_buffer(force=False)

        now_iso = datetime.now(timezone.utc).isoformat()
        if node_id:
            with nodes_lock:
                node_state = connected_nodes.get(node_id, {
                    "node_id": node_id,
                    "ip_address": request.remote_addr,
                    "polling_interval": DEFAULT_HEARTBEAT_INTERVAL_SEC,
                    "heartbeat_interval_sec": DEFAULT_HEARTBEAT_INTERVAL_SEC,
                    "registered_at": now_iso
                })
                node_state["last_seen"] = now_iso
                node_state["status"] = "active"
                connected_nodes[node_id] = node_state
        
        # Broadcast to dashboard subscribers
        socketio.emit('kpi_update', {
            "node_id": node_id,
            "record_count": len(kpi_records),
            "latest": kpi_records[-1]
        })
        
        logger.info(
            f"Received {len(kpi_records)} KPI records from {node_id}; "
            f"buffer_size={len(ingest_buffer)}; flushed_now={inserted_now}"
        )
        return jsonify({
            "status": "accepted",
            "records_received": len(kpi_records),
            "records_flushed_now": inserted_now,
            "buffer_size": len(ingest_buffer)
        })
    except Exception as e:
        logger.error(f"Error submitting KPI: {e}")
        return jsonify({"error": str(e)}), 500

@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    logger.info(f"Client connected: {request.sid}")
    emit('connection_response', {'data': 'Connected to dashboard'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    logger.info(f"Client disconnected: {request.sid}")

@socketio.on('request_update')
def handle_update_request(data):
    """Handle real-time update requests"""
    node_id = data.get("node_id")
    if node_id in connected_nodes:
        emit('node_status', connected_nodes[node_id])

if __name__ == '__main__':
    db = DatabaseConnector(db_config)
    db.initialize_schema()

    threading.Thread(target=_periodic_flush_worker, daemon=True).start()
    threading.Thread(target=_node_offline_checker, daemon=True).start()

    logger.info("Starting Flask Dashboard Server on 0.0.0.0:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
