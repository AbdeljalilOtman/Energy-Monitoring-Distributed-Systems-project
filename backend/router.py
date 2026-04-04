import logging
from db_connector import DatabaseConnector

logger = logging.getLogger(__name__)

class KPIRouter:
    def __init__(self, db_config):
        self.db_config = db_config
        self.connector = DatabaseConnector(db_config)
        self.connector.initialize_schema()

    def send_to_database(self, kpi_records):
        """Route KPI data to the appropriate database"""
        try:
            for record in kpi_records:
                self.connector.insert_kpi(record)
            logger.info(f"Successfully routed {len(kpi_records)} records to database")
        except Exception as e:
            logger.error(f"Routing failed: {e}")
            raise