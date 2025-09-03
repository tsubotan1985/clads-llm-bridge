"""Database connection management."""

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

# Global database connection instance
_db_connection = None


def get_db_path() -> str:
    """Get the current database path."""
    global _db_connection
    if _db_connection is None:
        _db_connection = DatabaseConnection()
    return _db_connection.get_db_path()


def get_db_connection() -> 'DatabaseConnection':
    """Get the global database connection instance."""
    global _db_connection
    if _db_connection is None:
        _db_connection = DatabaseConnection()
    return _db_connection


class DatabaseConnection:
    """Manages SQLite database connections with thread safety."""
    
    def __init__(self, db_path: str = "data/clads_llm_bridge.db"):
        """Initialize database connection manager.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
    
    def get_connection(self) -> sqlite3.Connection:
        """Get a thread-local database connection."""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0
            )
            # Enable foreign key constraints
            self._local.connection.execute("PRAGMA foreign_keys = ON")
            # Set row factory for dict-like access
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    @contextmanager
    def get_cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        """Get a database cursor with automatic transaction management."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
    
    def execute_script(self, script: str) -> None:
        """Execute a SQL script."""
        with self.get_cursor() as cursor:
            cursor.executescript(script)
    
    def execute_query(self, query: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Execute a SELECT query and return results."""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
    
    def execute_update(self, query: str, params: tuple = ()) -> int:
        """Execute an INSERT/UPDATE/DELETE query and return affected rows."""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.rowcount
    
    def get_db_path(self) -> str:
        """Get the database file path."""
        return str(self.db_path)
    
    def close(self) -> None:
        """Close the database connection."""
        if hasattr(self._local, 'connection'):
            self._local.connection.close()
            delattr(self._local, 'connection')