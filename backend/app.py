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
db_config = {
    "type": "sqlite",
    "path": "test_db/benchmark_test.db"
}

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(db_config["path"])
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def dashboard():
    """Serve dashboard HTML"""
    return render_template('dashboard.html')

@app.route('/api/nodes', methods=['GET'])
def get_nodes():
    """Get all registered nodes"""
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
            
            summary.append({
                "NodeID": node_id,
                "status": "healthy" if is_healthy else "unhealthy",
                "last_update": last_update,
                "connected": node_id in connected_nodes,
                "kpi_count": row["kpi_count"],
                "workload_count": row["workload_count"]
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
    
    connected_nodes[node_id] = {
        "node_id": node_id,
        "ip_address": node_ip,
        "polling_interval": polling_interval,
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "status": "active"
    }
    
    logger.info(f"Node {node_id} registered from {node_ip}")
    socketio.emit('node_registered', connected_nodes[node_id])
    
    return jsonify({"status": "registered", "node_id": node_id})

@app.route('/api/kpi/submit', methods=['POST'])
def submit_kpi():
    """Receive KPI data from daemon and store in database (new ML format)"""
    try:
        data = request.json
        node_id = data.get("node_id")
        kpi_records = data.get("records", [])
        
        if not kpi_records:
            return jsonify({"error": "No records provided"}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        for record in kpi_records:
            cursor.execute('''
                INSERT INTO kpi_metrics (timestamp, NodeID, WorkloadTag, KPI_name, Value)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                record["timestamp"],
                record["NodeID"],
                record["WorkloadTag"],
                record["KPI_name"],
                record["Value"]
            ))
        
        conn.commit()
        conn.close()
        
        # Broadcast to dashboard subscribers
        socketio.emit('kpi_update', {
            "node_id": node_id,
            "record_count": len(kpi_records),
            "latest": kpi_records[-1]
        })
        
        logger.info(f"Received {len(kpi_records)} KPI records from {node_id}")
        return jsonify({"status": "accepted", "records_stored": len(kpi_records)})
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
    logger.info("Starting Flask Dashboard Server on 0.0.0.0:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
