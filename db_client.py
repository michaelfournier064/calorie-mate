"""
Raw SQL Database Client for CalorieMate
Replaces SQLAlchemy ORM with direct MySQL operations using PyMySQL.
"""

import pymysql
import pymysql.cursors
from contextlib import contextmanager
from typing import Optional, List, Dict, Any, Union
import os
from datetime import datetime
import logging
import threading
from queue import Queue, Empty


class DatabasePool:
    """Simple connection pooling for MySQL connections."""
    
    def __init__(self, host, user, password, database, port=3306, max_connections=20):
        self.connection_config = {
            'host': host,
            'user': user,
            'password': password,
            'database': database,
            'port': port,
            'charset': 'utf8mb4',
            'autocommit': False,
            'cursorclass': pymysql.cursors.DictCursor
        }
        self.max_connections = max_connections
        self._pool = Queue(maxsize=max_connections)
        self._lock = threading.Lock()
        
        # Pre-populate pool with connections
        for _ in range(min(5, max_connections)):
            try:
                conn = pymysql.connect(**self.connection_config)
                self._pool.put(conn)
            except Exception as e:
                logging.error(f"Failed to create initial connection: {e}")
    
    def get_connection(self):
        """Get a connection from the pool or create a new one."""
        try:
            # Try to get existing connection
            conn = self._pool.get_nowait()
            if conn.open:
                # Verify connection is still alive with a simple ping
                try:
                    conn.ping(reconnect=False)
                    return conn
                except:
                    # Connection is stale, close it and create new one
                    conn.close()
                    return pymysql.connect(**self.connection_config)
            else:
                # Connection is closed, create new one
                return pymysql.connect(**self.connection_config)
        except Empty:
            # Pool is empty, create new connection
            return pymysql.connect(**self.connection_config)
    
    def return_connection(self, conn):
        """Return a connection to the pool."""
        if conn and conn.open:
            try:
                # Reset connection state before returning to pool
                conn.rollback()  # Ensure any uncommitted transactions are rolled back
                # Reset any session variables if needed
                self._pool.put_nowait(conn)
            except:
                # Pool is full or connection error, close the connection
                conn.close()
        elif conn:
            conn.close()
    
    def clear_pool(self):
        """Clear all connections from the pool."""
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                if conn:
                    conn.close()
            except Empty:
                break


class DatabaseClient:
    """
    Raw SQL database client using PyMySQL.
    Provides methods for CRUD operations, transactions, and connection management.
    """
    
    def __init__(self, database_uri: str = None):
        """Initialize database client with connection pool."""
        self.logger = logging.getLogger(__name__)
        
        # Parse database URI (mysql+pymysql://user:pass@host:port/database)
        if not database_uri:
            database_uri = os.getenv('DATABASE_URI', 'mysql+pymysql://root:@localhost:3306/caloriemate')
        
        # Extract connection details from URI
        if '://' in database_uri:
            _, uri_parts = database_uri.split('://', 1)
            if '@' in uri_parts:
                auth_part, host_db_part = uri_parts.split('@', 1)
                if ':' in auth_part:
                    user, password = auth_part.split(':', 1)
                else:
                    user, password = auth_part, ''
            else:
                user, password = 'root', ''
                host_db_part = uri_parts
            
            if '/' in host_db_part:
                host_port, database = host_db_part.split('/', 1)
            else:
                host_port, database = host_db_part, 'caloriemate'
            
            if ':' in host_port:
                host, port = host_port.split(':', 1)
                port = int(port)
            else:
                host, port = host_port, 3306
        else:
            # Fallback defaults
            host, port, user, password, database = 'localhost', 3306, 'root', '', 'caloriemate'
        
        # Initialize connection pool
        self.pool = DatabasePool(host, user, password, database, port)
        self.logger.info(f"Database client initialized for {host}:{port}/{database}")
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = None
        try:
            conn = self.pool.get_connection()
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            self.logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                self.pool.return_connection(conn)
    
    @contextmanager
    def transaction(self):
        """Context manager for database transactions."""
        with self.get_connection() as conn:
            try:
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                self.logger.error(f"Transaction error: {e}")
                raise
    
    def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return results."""
        with self.get_connection() as conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute(query, params or ())
                    return cursor.fetchall()
            finally:
                # Ensure any uncommitted changes are rolled back for read operations
                conn.rollback()
    
    def execute_insert(self, query: str, params: tuple = None) -> int:
        """Execute INSERT query and return the last inserted ID."""
        with self.transaction() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params or ())
                return cursor.lastrowid
    
    def execute_update(self, query: str, params: tuple = None) -> int:
        """Execute UPDATE query and return affected rows count."""
        with self.transaction() as conn:
            with conn.cursor() as cursor:
                affected_rows = cursor.execute(query, params or ())
                return affected_rows
    
    def execute_ddl(self, statement: str) -> bool:
        """Execute DDL statement (CREATE, ALTER, DROP, etc.) without parameters."""
        try:
            with self.transaction() as conn:
                with conn.cursor() as cursor:
                    # Execute DDL statement directly without parameter formatting
                    cursor.execute(statement)
                    return True
        except Exception as e:
            logging.error(f"DDL execution failed: {e}")
            logging.error(f"Statement: {statement[:100]}...")
            return False
    
    def execute_delete(self, query: str, params: tuple = None) -> int:
        """Execute DELETE query and return affected rows count."""
        with self.transaction() as conn:
            with conn.cursor() as cursor:
                affected_rows = cursor.execute(query, params or ())
                return affected_rows
    
    def execute_script(self, script: str) -> None:
        """Execute multiple SQL statements (for schema creation)."""
        with self.transaction() as conn:
            with conn.cursor() as cursor:
                # Split script by semicolons and execute each statement
                statements = [stmt.strip() for stmt in script.split(';') if stmt.strip()]
                for statement in statements:
                    cursor.execute(statement)
    
    def fetch_one(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """Execute query and return single row or None."""
        with self.get_connection() as conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute(query, params or ())
                    return cursor.fetchone()
            finally:
                # Ensure any uncommitted changes are rolled back for read operations
                conn.rollback()
    
    def fetch_paginated(self, query: str, params: tuple = None, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """Execute paginated query and return results with pagination info."""
        offset = (page - 1) * per_page
        
        # Count total rows
        count_query = f"SELECT COUNT(*) as total FROM ({query}) as count_query"
        total_result = self.fetch_one(count_query, params)
        total = total_result['total'] if total_result else 0
        
        # Get paginated results
        paginated_query = f"{query} LIMIT %s OFFSET %s"
        paginated_params = (params or ()) + (per_page, offset)
        results = self.execute_query(paginated_query, paginated_params)
        
        return {
            'items': results,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page if per_page > 0 else 0,
            'has_prev': page > 1,
            'has_next': page * per_page < total
        }
    
    def build_where_clause(self, conditions: Dict[str, Any]) -> tuple:
        """Build WHERE clause from dictionary of conditions."""
        if not conditions:
            return "", ()
        
        where_parts = []
        params = []
        
        for key, value in conditions.items():
            if value is None:
                where_parts.append(f"{key} IS NULL")
            elif isinstance(value, (list, tuple)):
                placeholders = ', '.join(['%s'] * len(value))
                where_parts.append(f"{key} IN ({placeholders})")
                params.extend(value)
            elif isinstance(value, bool):
                # Convert Python boolean to MySQL TINYINT (1 for True, 0 for False)
                where_parts.append(f"{key} = %s")
                params.append(1 if value else 0)
            else:
                where_parts.append(f"{key} = %s")
                params.append(value)
        
        where_clause = " AND ".join(where_parts)
        return f" WHERE {where_clause}", tuple(params)
    
    def insert_record(self, table: str, data: Dict[str, Any]) -> int:
        """Insert a record into table and return the ID."""
        import json
        
        if not data:
            raise ValueError("Data cannot be empty")
        
        # Add created_at if not present
        if 'created_at' not in data and self.table_has_column(table, 'created_at'):
            data['created_at'] = datetime.utcnow()
        
        # Process data to handle JSON fields
        processed_data = {}
        for key, value in data.items():
            if value is None:
                processed_data[key] = None
            elif isinstance(value, (list, dict)):
                # Serialize JSON fields
                processed_data[key] = json.dumps(value)
            else:
                processed_data[key] = value
        
        columns = list(processed_data.keys())
        placeholders = ', '.join(['%s'] * len(columns))
        column_names = ', '.join(columns)
        
        query = f"INSERT INTO {table} ({column_names}) VALUES ({placeholders})"
        params = tuple(processed_data.values())
        
        return self.execute_insert(query, params)
    
    def update_record(self, table: str, data: Dict[str, Any], conditions: Dict[str, Any]) -> int:
        """Update records in table based on conditions."""
        import json
        
        if not data:
            raise ValueError("Data cannot be empty")
        if not conditions:
            raise ValueError("Conditions cannot be empty")
        
        # Add updated_at if not present
        if 'updated_at' not in data and self.table_has_column(table, 'updated_at'):
            data['updated_at'] = datetime.utcnow()
        
        # Process data to handle JSON fields
        processed_data = {}
        for key, value in data.items():
            if value is None:
                processed_data[key] = None
            elif isinstance(value, (list, dict)):
                # Serialize JSON fields
                processed_data[key] = json.dumps(value)
            else:
                processed_data[key] = value
        
        set_parts = [f"{key} = %s" for key in processed_data.keys()]
        set_clause = ", ".join(set_parts)
        
        where_clause, where_params = self.build_where_clause(conditions)
        
        query = f"UPDATE {table} SET {set_clause}{where_clause}"
        params = tuple(processed_data.values()) + where_params
        
        return self.execute_update(query, params)
    
    def delete_record(self, table: str, conditions: Dict[str, Any]) -> int:
        """Delete records from table based on conditions."""
        if not conditions:
            raise ValueError("Conditions cannot be empty for delete operation")
        
        where_clause, params = self.build_where_clause(conditions)
        query = f"DELETE FROM {table}{where_clause}"
        
        return self.execute_delete(query, params)
    
    def select_records(self, table: str, conditions: Dict[str, Any] = None, 
                      columns: str = "*", order_by: str = None, limit: int = None) -> List[Dict[str, Any]]:
        """Select records from table with optional conditions."""
        query = f"SELECT {columns} FROM {table}"
        params = ()
        
        if conditions:
            where_clause, params = self.build_where_clause(conditions)
            query += where_clause
        
        if order_by:
            query += f" ORDER BY {order_by}"
        
        if limit:
            query += f" LIMIT {limit}"
        
        return self.execute_query(query, params)
    
    def table_has_column(self, table: str, column: str) -> bool:
        """Check if table has a specific column."""
        query = """
        SELECT COUNT(*) as count 
        FROM information_schema.COLUMNS 
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s
        """
        result = self.fetch_one(query, (table, column))
        return result['count'] > 0 if result else False
    
    def table_exists(self, table: str) -> bool:
        """Check if table exists."""
        query = """
        SELECT COUNT(*) as count 
        FROM information_schema.TABLES 
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
        """
        result = self.fetch_one(query, (table,))
        return result['count'] > 0 if result else False


# Global database client instance
db_client = None


def init_db_client(database_uri: str = None):
    """Initialize global database client."""
    global db_client
    # Clear any existing client and its connections
    if db_client and hasattr(db_client, 'pool'):
        db_client.pool.clear_pool()
    db_client = DatabaseClient(database_uri)
    return db_client


def get_db_client() -> DatabaseClient:
    """Get global database client instance."""
    global db_client
    if db_client is None:
        db_client = DatabaseClient()
    return db_client
