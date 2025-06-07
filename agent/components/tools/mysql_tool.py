import os
import mysql.connector
from typing import Optional, Dict
import requests, json, datetime
import decimal


class MySQLTool:
    """Tool for executing read-only SQL queries against MySQL database.
    
    Uses environment variables for connection:
    - MYSQL_HOST: database host
    - MYSQL_PORT: database port
    - MYSQL_USER: read-only user
    - MYSQL_PASSWORD: user password
    - MYSQL_DATABASE: database name
    """
    def __init__(self):
        self.used_show_ids = []

    def execute_db_query(self, sql: str) -> str:
        """Executes any read-only SQL query and returns results as JSON."""
        # Validate query is read-only
        if not sql.lower().strip().startswith(('select', 'show', 'describe', 'desc', 'explain')):
            raise ValueError("Only read-only queries are allowed")

        try:
            # Connect using environment variables
            conn = mysql.connector.connect(
                host=os.environ['MYSQL_HOST'],
                port=int(os.environ.get('MYSQL_PORT', 3306)),
                user=os.environ['MYSQL_USER'],
                password=os.environ['MYSQL_PASSWORD'],
                database=os.environ['MYSQL_DATABASE'],
                charset='utf8mb4',
                collation='utf8mb4_unicode_ci'
            )

            cursor = conn.cursor(dictionary=True)
            cursor.execute(sql)
            results = cursor.fetchall()

            return json.dumps(results, ensure_ascii=False, indent=4, default=self.json_serializer)

        except mysql.connector.Error as e:
            return json.dumps({"error": f"MySQL Error: {str(e)}"}, ensure_ascii=False)

        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()

    @staticmethod
    def json_serializer(obj):
        """Custom JSON serializer for non-serializable types."""
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        elif isinstance(obj, datetime.time):
            return obj.strftime("%H:%M:%S")
        elif isinstance(obj, decimal.Decimal):
            return float(obj)
        return str(obj)

