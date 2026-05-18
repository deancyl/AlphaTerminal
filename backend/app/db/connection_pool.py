"""SQLite Connection Pool for concurrent access.

Provides thread-safe connection pooling for SQLite databases with WAL mode
and busy_timeout support for better concurrent access handling.
"""

import sqlite3
import threading
import queue
import os
from contextlib import contextmanager
from typing import Optional

# Default database path (same as database.py)
DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "alphaterminal.db")


class SQLiteConnectionPool:
    """Thread-safe SQLite connection pool with WAL mode support.
    
    Features:
    - Connection pooling for efficient resource reuse
    - WAL mode for better concurrent read/write performance
    - Busy timeout for handling concurrent access
    - Thread-safe connection management
    - Context manager support for automatic connection cleanup
    
    Example:
        pool = SQLiteConnectionPool("/path/to/db.sqlite")
        
        # Using context manager (recommended)
        with pool.connection() as conn:
            cursor = conn.execute("SELECT * FROM users")
            results = cursor.fetchall()
        
        # Manual connection management
        conn = pool.get()
        try:
            cursor = conn.execute("SELECT * FROM users")
            results = cursor.fetchall()
        finally:
            pool.put(conn)
    """
    
    def __init__(self, db_path: str, max_connections: int = 20):
        """Initialize the connection pool.
        
        Args:
            db_path: Path to the SQLite database file
            max_connections: Maximum number of connections in the pool
        """
        self.db_path = os.path.abspath(db_path)
        self.max_connections = max_connections
        self._pool: queue.Queue[sqlite3.Connection] = queue.Queue(maxsize=max_connections)
        self._lock = threading.Lock()
        self._created = 0
        self._closed = False
        
        # Ensure database directory exists
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
    
    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection with optimized settings.
        
        Returns:
            sqlite3.Connection: A new database connection
            
        Raises:
            sqlite3.Error: If connection creation fails
        """
        conn = sqlite3.connect(
            self.db_path,
            timeout=30,
            check_same_thread=False,
            isolation_level=None  # Autocommit mode for better control
        )
        conn.row_factory = sqlite3.Row
        
        # Enable WAL mode for better concurrent access
        conn.execute("PRAGMA journal_mode=WAL")
        
        # Set busy timeout to 30 seconds for handling concurrent writes
        conn.execute("PRAGMA busy_timeout=30000")
        
        # Enable foreign key constraints
        conn.execute("PRAGMA foreign_keys=ON")
        
        # Optimize for performance
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        conn.execute("PRAGMA temp_store=MEMORY")
        
        return conn
    
    def get(self, timeout: float = 5.0) -> sqlite3.Connection:
        """Get a connection from the pool.
        
        If the pool is empty and we haven't reached max_connections,
        create a new connection. Otherwise, wait for a connection
        to become available.
        
        Args:
            timeout: Maximum time to wait for a connection (seconds)
            
        Returns:
            sqlite3.Connection: A database connection
            
        Raises:
            queue.Empty: If no connection is available within timeout
            RuntimeError: If the pool is closed
        """
        if self._closed:
            raise RuntimeError("Connection pool is closed")
        
        # Try to get an existing connection
        try:
            conn = self._pool.get_nowait()
            # Verify connection is still valid
            try:
                conn.execute("SELECT 1")
                return conn
            except sqlite3.Error:
                # Connection is broken, create a new one
                with self._lock:
                    self._created -= 1
                return self._create_connection()
        except queue.Empty:
            pass
        
        # No available connection, try to create a new one
        with self._lock:
            if self._created < self.max_connections:
                self._created += 1
                return self._create_connection()
        
        # Wait for a connection to become available
        try:
            conn = self._pool.get(timeout=timeout)
            # Verify connection is still valid
            try:
                conn.execute("SELECT 1")
                return conn
            except sqlite3.Error:
                # Connection is broken, create a new one
                with self._lock:
                    self._created -= 1
                return self._create_connection()
        except queue.Empty:
            raise queue.Empty(
                f"No connection available within {timeout}s. "
                f"Pool size: {self._created}/{self.max_connections}"
            )
    
    def put(self, conn: sqlite3.Connection) -> None:
        """Return a connection to the pool.
        
        Args:
            conn: The connection to return to the pool
        """
        if self._closed:
            try:
                conn.close()
            except sqlite3.Error:
                pass
            return
        
        try:
            # Reset connection state
            conn.rollback()
            
            # Try to return to pool
            try:
                self._pool.put_nowait(conn)
            except queue.Full:
                # Pool is full, close the connection
                with self._lock:
                    self._created -= 1
                conn.close()
        except sqlite3.Error:
            # Connection is broken, don't return it
            with self._lock:
                self._created -= 1
            try:
                conn.close()
            except sqlite3.Error:
                pass
    
    @contextmanager
    def connection(self, timeout: float = 5.0):
        """Context manager for automatic connection management.
        
        Args:
            timeout: Maximum time to wait for a connection (seconds)
            
        Yields:
            sqlite3.Connection: A database connection
            
        Example:
            with pool.connection() as conn:
                cursor = conn.execute("SELECT * FROM users")
                results = cursor.fetchall()
        """
        conn = self.get(timeout)
        try:
            yield conn
        finally:
            self.put(conn)
    
    @contextmanager
    def transaction(self, timeout: float = 5.0):
        """Context manager for transaction with automatic commit/rollback.
        
        Args:
            timeout: Maximum time to wait for a connection (seconds)
            
        Yields:
            sqlite3.Connection: A database connection with active transaction
            
        Example:
            with pool.transaction() as conn:
                conn.execute("INSERT INTO users (name) VALUES (?)", ("John",))
                conn.execute("INSERT INTO logs (action) VALUES (?)", ("user_created",))
                # Auto-commits on success, rollback on exception
        """
        conn = self.get(timeout)
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self.put(conn)
    
    def close(self) -> None:
        """Close all connections in the pool."""
        self._closed = True
        
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except (queue.Empty, sqlite3.Error):
                pass
        
        with self._lock:
            self._created = 0
    
    def __enter__(self):
        """Support for context manager."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close pool on context exit."""
        self.close()
        return False
    
    @property
    def size(self) -> int:
        """Current number of connections in the pool."""
        return self._created
    
    @property
    def available(self) -> int:
        """Number of available connections in the pool."""
        return self._pool.qsize()


# Global connection pool instance
_global_pool: Optional[SQLiteConnectionPool] = None
_global_pool_lock = threading.Lock()


def get_connection_pool(db_path: Optional[str] = None, max_connections: int = 20) -> SQLiteConnectionPool:
    """Get or create the global connection pool.
    
    Args:
        db_path: Path to the database file (uses default if not provided)
        max_connections: Maximum number of connections
        
    Returns:
        SQLiteConnectionPool: The global connection pool instance
    """
    global _global_pool
    
    if _global_pool is not None:
        return _global_pool
    
    with _global_pool_lock:
        if _global_pool is not None:
            return _global_pool
        
        if db_path is None:
            db_path = os.path.abspath(DEFAULT_DB_PATH)
        
        _global_pool = SQLiteConnectionPool(db_path, max_connections=max_connections)
        return _global_pool


def close_connection_pool() -> None:
    """Close the global connection pool."""
    global _global_pool
    
    if _global_pool is not None:
        with _global_pool_lock:
            if _global_pool is not None:
                _global_pool.close()
                _global_pool = None


@contextmanager
def get_db_connection(timeout: float = 5.0):
    """Convenience context manager for getting a connection from the global pool.
    
    Args:
        timeout: Maximum time to wait for a connection (seconds)
        
    Yields:
        sqlite3.Connection: A database connection
        
    Example:
        with get_db_connection() as conn:
            cursor = conn.execute("SELECT * FROM users")
            results = cursor.fetchall()
    """
    pool = get_connection_pool()
    with pool.connection(timeout) as conn:
        yield conn


@contextmanager
def get_db_transaction(timeout: float = 5.0):
    """Convenience context manager for getting a transaction from the global pool.
    
    Args:
        timeout: Maximum time to wait for a connection (seconds)
        
    Yields:
        sqlite3.Connection: A database connection with active transaction
        
    Example:
        with get_db_transaction() as conn:
            conn.execute("INSERT INTO users (name) VALUES (?)", ("John",))
    """
    pool = get_connection_pool()
    with pool.transaction(timeout) as conn:
        yield conn
