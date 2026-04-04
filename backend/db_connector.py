import sqlite3
import logging

logger = logging.getLogger(__name__)

class DatabaseConnector:
    def __init__(self, config):
        self.db_type = config["type"]
        self.db_path = config["path"]
        self.connection = None

    def _get_connection(self):
        if self.connection is None:
            self.connection = sqlite3.connect(self.db_path)
        return self.connection

    def initialize_schema(self):
        """Create tables for ML workload KPI monitoring"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS kpi_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                NodeID TEXT NOT NULL,
                WorkloadTag TEXT NOT NULL,
                KPI_name TEXT NOT NULL,
                Value REAL NOT NULL
            )
        ''')
        conn.commit()
        logger.info("Database schema initialized with new KPI structure")

    def insert_kpi(self, record):
        """Insert a KPI record"""
        conn = self._get_connection()
        cursor = conn.cursor()
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

    def close(self):
        if self.connection:
            self.connection.close()